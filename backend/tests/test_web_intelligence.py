"""Offline V1.5 web-intelligence tests; requests is always mocked."""
from types import SimpleNamespace
import sys
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def settings(**values):
    base=dict(web_search_enabled=True, web_search_provider="brave", web_search_api_key="secret", web_search_max_queries=3, web_search_results_per_query=2, web_search_timeout_seconds=1)
    base.update(values); return SimpleNamespace(**base)

def test_ranked_queries_strong_and_weak_evidence(monkeypatch):
    from visual_intelligence import search
    monkeypatch.setattr(search.config,"settings",settings())
    strong=search.queries([{"text":"Lenovo","confidence":.99},{"text":"ThinkPad T14 Gen 5","confidence":.98}], {"organizations":["Lenovo"],"model_codes":["T14"],"domains":[],"qr_content":[]}, [{"class":"laptop"}])
    assert strong[0]["query"] == "Lenovo ThinkPad T14 Gen 5" and strong[0]["score"] >= .9 and "laptop" not in strong[0]["query"]
    assert search.queries([{"text":"x","confidence":.2}], {"organizations":[],"model_codes":[],"domains":[],"qr_content":[]}, []) == []

def test_status_classification_and_limits(monkeypatch):
    from visual_intelligence import search
    monkeypatch.setattr(search.config,"settings",settings(web_search_enabled=False)); assert search.status()["status"] == "Disabled"
    monkeypatch.setattr(search.config,"settings",settings(web_search_api_key=None)); assert search.status()["reason"] == "API key missing"
    assert search.source_type("https://support.example.com/a") == "documentation"
    assert search.source_type("https://lenovo.com/x", "Official product") == "official"

def test_provider_success_dedupe_tracking_timeout_and_errors(monkeypatch):
    from visual_intelligence import search
    monkeypatch.setattr(search.config,"settings",settings())
    class Ok:
        status_code=200
        def raise_for_status(self): pass
        def json(self): return {"web":{"results":[{"title":"A","url":"https://a.example/x?utm_source=z","description":"one"},{"title":"dup","url":"https://a.example/x","description":"two"},{"title":"extra","url":"https://b.example","description":"three"}]}}
    calls=[]
    def get(*args,**kwargs): calls.append(kwargs); return Ok()
    monkeypatch.setattr(search.requests,"get",get)
    found, notice=search.search([{"query":"ZX-440"}]*4)
    assert notice is None and len(found)==1 and "utm_source" not in found[0]["url"] and len(calls)==3 and calls[0]["params"]["count"]==2
    monkeypatch.setattr(search.requests,"get",lambda *a,**k: (_ for _ in ()).throw(requests.Timeout()))
    assert "timed out" in search.search([{"query":"x"}])[1]
    class Limited: status_code=429
    monkeypatch.setattr(search.requests,"get",lambda *a,**k: Limited())
    assert "rate limit" in search.search([{"query":"x"}])[1]

def test_correlation_confidence_and_contradiction():
    from visual_intelligence.correlation import correlate
    out=correlate([{"text":"Lenovo","confidence":.9},{"text":"T14 Gen 5","confidence":.9}], [{"class":"laptop"}], {"model_codes":["T14","T14-GEN5"]}, [{"title":"Lenovo T14 Gen 5 official","domain":"lenovo.com","url":"https://lenovo.com","source_type":"official"}])
    assert out["inferred"]["candidate_matches"][0]["confidence"] == "HIGH"
    assert "inconsistent" in out["inferred"]["contradictions"][0]
