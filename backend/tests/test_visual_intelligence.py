"""Offline Visual Intelligence V1 coverage: no webcam, GPU, model download, or internet."""
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import bcrypt
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def visual_env(monkeypatch, tmp_path):
    import config
    from storage import init_db
    from visual_intelligence import service
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "visual.db"))
    monkeypatch.setenv("CAPTURE_DIRECTORY", str(tmp_path / "outputs"))
    monkeypatch.setenv("VISUAL_MAX_UPLOAD_MB", "1")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-must-be-at-least-thirty-two-bytes")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", bcrypt.hashpw(b"password", bcrypt.gensalt()).decode())
    monkeypatch.setenv("PROTECT_MONITORING_ROUTES", "false")
    settings = config.reload_settings()
    service.ROOT = Path(settings.capture_directory).resolve() / "visual_intelligence"
    init_db(settings.database_path)
    yield settings
    config.reload_settings()


def image_bytes(ext=".jpg"):
    ok, encoded = cv2.imencode(ext, np.full((24, 32, 3), 180, dtype=np.uint8))
    assert ok
    return encoded.tobytes()


@pytest.mark.parametrize("filename", ["evidence.jpg", "evidence.png"])
def test_valid_uploads_sha_and_immutable_original(visual_env, filename):
    from visual_intelligence import service
    raw = image_bytes(".png" if filename.endswith("png") else ".jpg")
    record = service.create_bytes(raw, filename)
    stored = service._safe(record["stored_original_path"])
    assert stored.read_bytes() == raw
    assert record["sha256"] == hashlib.sha256(raw).hexdigest()
    result = service.make_enhancement(record["id"], {"auto_contrast": True, "upscale": 2})
    assert service._safe(result["stored_original_path"]).read_bytes() == raw
    assert result["metadata"]["derivatives"]["enhanced"] != result["stored_original_path"]


def test_upload_rejections_and_safe_paths(visual_env, monkeypatch):
    from fastapi import HTTPException
    from visual_intelligence import service
    with pytest.raises(HTTPException, match="Supported"):
        service.create_bytes(image_bytes(), "malware.gif")
    with pytest.raises(HTTPException, match="valid image"):
        service.create_bytes(b"not an image", "bad.jpg")
    with pytest.raises(HTTPException, match="exceeds"):
        service.create_bytes(b"x" * (visual_env.visual_max_upload_mb * 1024 * 1024 + 1), "large.jpg")
    with pytest.raises(HTTPException): service._safe("../outside.txt")
    outside = Path(visual_env.capture_directory).parent / "outside.jpg"; outside.write_bytes(image_bytes())
    service._paths(); link = service.ROOT / "originals" / "escape.jpg"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(HTTPException): service._safe("originals/escape.jpg")


def test_analysis_persistence_ocr_objects_entities_qr_and_disabled_web(visual_env, monkeypatch):
    from visual_intelligence import service
    monkeypatch.setattr(service.ocr, "read_with_status", lambda _: ([{"text":"ACME ZX-440 support@example.com https://example.com", "confidence":.97,"box":[[1,1],[2,1],[2,2],[1,2]]}], None))
    monkeypatch.setattr(service.ocr, "qr", lambda _: ["https://qr.example"])
    monkeypatch.setattr(service.detection, "detect", lambda _: [{"class":"laptop","confidence":.9,"bbox":[1,1,10,10]}])
    record=service.analyze(service.create_bytes(image_bytes(), "evidence.jpg")["id"])
    assert record["status"] == "complete" and record["detections"][0]["class"] == "laptop"
    assert "support@example.com" in record["entities"]["emails"]
    assert "example.com" in record["entities"]["domains"] and "ZX-440" in record["entities"]["model_codes"]
    assert record["entities"]["qr_content"] == ["https://qr.example"]
    assert "No external search has been run" in record["summary"]["web_intelligence"]["notice"]
    assert service._safe(record["metadata"]["derivatives"]["ocr_overlay"]).is_file()
    assert service.get(record["id"])["sha256"] == record["sha256"]


def test_roi_bounds_and_child_persistence(visual_env, monkeypatch):
    from fastapi import HTTPException
    from visual_intelligence import service
    monkeypatch.setattr(service.ocr, "read_with_status", lambda _: ([], None))
    monkeypatch.setattr(service.ocr, "qr", lambda _: [])
    monkeypatch.setattr(service.detection, "detect", lambda _: [])
    parent=service.create_bytes(image_bytes(), "evidence.jpg")
    child=service.create_region(parent["id"], {"x":.1,"y":.1,"width":.5,"height":.5})
    assert child["parent_analysis_id"] == parent["id"] and child["source_type"] == "region"
    with pytest.raises(HTTPException): service.create_region(parent["id"], {"x":1,"y":1,"width":.1,"height":.1})


def test_entity_and_search_provider_behavior(monkeypatch):
    from visual_intelligence import entities, search
    out=entities.extract([{"text":"Call +1 555 123 4567, APEX T14-GEN5, https://example.org/a"}])
    assert "example.org" in out["domains"] and "T14-GEN5" in out["model_codes"]
    monkeypatch.setattr(search.config, "settings", SimpleNamespace(web_search_enabled=False, web_search_api_key=None, web_search_provider="disabled"))
    assert search.search(["test"])[1] == "Web Intelligence is not configured."
    monkeypatch.setattr(search.config, "settings", SimpleNamespace(web_search_enabled=True, web_search_api_key="key", web_search_provider="brave"))
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"web":{"results":[{"title":"A","url":"https://a.example/x","description":"one"},{"title":"A duplicate","url":"https://a.example/x","description":"two"}]}}
    monkeypatch.setattr(search.requests, "get", lambda *a, **k: Response())
    results, notice=search.search(["one"])
    assert notice is None and len(results) == 1 and results[0]["provider"] == "brave"


def test_ocr_unavailable_and_router_auth(visual_env, monkeypatch):
    import api
    from visual_intelligence import ocr, service
    monkeypatch.setattr(api.worker, "start", lambda: None); monkeypatch.setattr(api.worker, "stop", lambda: None)
    monkeypatch.setattr(service.ocr, "read_with_status", lambda _: ([], "OCR unavailable: test"))
    monkeypatch.setattr(service.ocr, "qr", lambda _: [])
    monkeypatch.setattr(service.detection, "detect", lambda _: [])
    monkeypatch.setattr(ocr, "_reader", None)
    with TestClient(api.app) as client:
        assert client.post("/visual-intelligence/analyze", files={"image":("x.jpg",image_bytes(),"image/jpeg")}).status_code == 401
        token=client.post("/auth/login",json={"username":"admin","password":"password"}).json()["access_token"]
        response=client.post("/visual-intelligence/analyze", headers={"Authorization":f"Bearer {token}"}, files={"image":("x.jpg",image_bytes(),"image/jpeg")})
        assert response.status_code == 201 and response.json()["id"]
        analysis_id = response.json()["id"]
        # Cost-bearing web mutation remains admin-only even when monitoring reads are public.
        client.cookies.clear()
        assert client.post(f"/visual-intelligence/analyses/{analysis_id}/web-search", json={}).status_code == 401
        assert client.post(f"/visual-intelligence/analyses/{analysis_id}/web-search", headers={"Authorization":f"Bearer {token}"}, json={}).status_code == 200
        assert client.post(f"/visual-intelligence/analyses/{analysis_id}/regions/analyze", headers={"Authorization":f"Bearer {token}"}, json={"x":.9,"y":.1,"width":.2,"height":.2}).status_code == 422
        assert client.post(f"/visual-intelligence/analyses/{analysis_id}/regions/analyze", headers={"Authorization":f"Bearer {token}"}, json={"x":.1,"y":.1,"width":0,"height":.2}).status_code == 422
