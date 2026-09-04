import hashlib, json, mimetypes, shutil, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
from fastapi import HTTPException
from PIL import Image
import config
from . import correlation, detection, entities, ocr, search
from .enhancement import enhance

ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
ROOT = Path(config.settings.capture_directory).resolve() / "visual_intelligence"

def _paths():
    for name in ("originals", "enhanced", "overlays", "crops"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)

def _safe(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try: path.relative_to(ROOT.resolve())
    except ValueError: raise HTTPException(404, "Evidence file not found")
    return path

def _conn():
    conn = sqlite3.connect(config.settings.database_path, timeout=10); conn.row_factory=sqlite3.Row; return conn

def _row(row):
    if not row: raise HTTPException(404, "Analysis not found")
    result=dict(row)
    for key in ("enhancement_params_json","ocr_json","detections_json","entities_json","search_queries_json","web_results_json","summary_json","metadata_json"):
        result[key.removesuffix("_json")] = json.loads(result.pop(key) or ("[]" if key in {"ocr_json","detections_json","search_queries_json","web_results_json"} else "{}"))
    return result

def get(analysis_id: str):
    conn=_conn(); row=conn.execute("SELECT * FROM visual_analysis WHERE id=?",(analysis_id,)).fetchone(); conn.close(); return _row(row)

def list_all(limit=100):
    conn=_conn(); rows=conn.execute("SELECT * FROM visual_analysis ORDER BY created_at DESC LIMIT ?",(max(1,min(limit,200)),)).fetchall(); conn.close(); return [_row(r) for r in rows]

def _load(record):
    path=_safe(record["stored_original_path"])
    image=cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None: raise HTTPException(422,"Stored evidence cannot be decoded")
    return image

def create_bytes(data: bytes, filename: str, source_type="upload", source_incident_id=None, parent_analysis_id=None,
                 source_metadata=None, mission_id=None, mission_event_id=None, evidence_id=None,
                 video_timestamp_seconds=None):
    suffix=Path(filename).suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(415,"Supported image types: .jpg, .jpeg, .png, .webp")
    if len(data)>config.settings.visual_max_upload_mb*1024*1024: raise HTTPException(413,"Image exceeds configured upload limit")
    try:
        with Image.open(__import__('io').BytesIO(data)) as check: check.verify()
        image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
        if image is None: raise ValueError()
    except Exception: raise HTTPException(422,"Uploaded bytes are not a valid image")
    _paths(); aid=str(uuid.uuid4()); ext=".jpg" if suffix==".jpeg" else suffix; rel=f"originals/{aid}{ext}"; target=_safe(rel); target.write_bytes(data)
    h,w=image.shape[:2]; now=datetime.now(timezone.utc).isoformat(); sha=hashlib.sha256(data).hexdigest()
    conn=_conn(); conn.execute("""INSERT INTO visual_analysis (id,created_at,source_type,source_incident_id,parent_analysis_id,original_filename,stored_original_path,sha256,width,height,mime_type,status,metadata_json,mission_id,mission_event_id,evidence_id,video_timestamp_seconds)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(aid,now,source_type,source_incident_id,parent_analysis_id,Path(filename).name,rel,sha,w,h,mimetypes.guess_type(filename)[0] or "image/jpeg","created",json.dumps({"derivatives":{},"evidence_notice":"Original evidence is immutable; derivatives do not reconstruct missing detail.","source_context":source_metadata or {}}),mission_id,mission_event_id,evidence_id,video_timestamp_seconds)); conn.commit(); conn.close()
    return get(aid)

def _save_derivative(record, image, folder, suffix):
    _paths(); rel=f"{folder}/{record['id']}_{uuid.uuid4().hex[:8]}.jpg"; path=_safe(rel)
    if not cv2.imwrite(str(path), image): raise HTTPException(500,"Could not save derivative")
    return rel

def _overlay(image, ocr_rows, objects):
    out=image.copy()
    for item in ocr_rows:
        pts=np.array(item["box"],np.int32); cv2.polylines(out,[pts],True,(0,255,255),2); cv2.putText(out,item["text"][:40],tuple(pts[0]),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1)
    for item in objects:
        x1,y1,x2,y2=item["bbox"]; cv2.rectangle(out,(x1,y1),(x2,y2),(0,220,0),2); cv2.putText(out,f"{item['class']} {item['confidence']:.0%}",(x1,max(16,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,220,0),1)
    return out

def analyze(analysis_id: str):
    record=get(analysis_id); image=_load(record); text, ocr_notice=ocr.read_with_status(image); objects=detection.detect(image); qr=ocr.qr(image); clues=entities.extract(text,qr); q=search.queries(text,clues,objects)
    # Searching is deliberately analyst-controlled; this path makes no external request.
    web=[]; notice="No external search has been run. Generate queries or search selected OCR text when ready."
    assessment={"summary":"Evidence analysis completed. Review observed evidence and web sources separately before drawing conclusions.","candidate_matches":[],"confidence":"low","limitations":["OCR and object detection are probabilistic.","No face identification or biometric lookup is performed."]}
    if text or objects: assessment["confidence"]="medium"
    report={"observations":{"objects":objects,"ocr":text,"entities":clues,"qr_content":qr},"web_intelligence":{"status":search.status(),"queries":q,"sources":web,"notice":notice},"correlation":correlation.correlate(text,objects,clues,web),"assessment":assessment}
    meta=record["metadata"]
    meta["ocr_status"] = ocr.status()
    if ocr_notice: meta["ocr_notice"] = ocr_notice
    meta["derivatives"]["ocr_overlay"]=_save_derivative(record,_overlay(image,text,[]),"overlays","ocr")
    meta["derivatives"]["object_overlay"]=_save_derivative(record,_overlay(image,[],objects),"overlays","objects")
    conn=_conn(); conn.execute("UPDATE visual_analysis SET status=?,ocr_json=?,detections_json=?,entities_json=?,search_queries_json=?,web_results_json=?,summary_json=?,metadata_json=? WHERE id=?",("complete",json.dumps(text),json.dumps(objects),json.dumps(clues),json.dumps(q),json.dumps(web),json.dumps(report),json.dumps(meta),analysis_id)); conn.commit(); conn.close(); return get(analysis_id)

def web_search(analysis_id, selected_text=None):
    """Run the explicitly requested, textual search and persist the retrieved evidence."""
    record=get(analysis_id)
    q=search.queries(record["ocr"], record["entities"], record["detections"], selected_text)
    web, notice=search.search(q)
    report=record["summary"] or {}; web_report=report.setdefault("web_intelligence", {})
    web_report.update({"status":search.status(),"queries":q,"sources":web,"notice":notice})
    report["correlation"]=correlation.correlate(record["ocr"],record["detections"],record["entities"],web)
    conn=_conn(); conn.execute("UPDATE visual_analysis SET search_queries_json=?,web_results_json=?,summary_json=? WHERE id=?",(json.dumps(q),json.dumps(web),json.dumps(report),analysis_id)); conn.commit(); conn.close()
    return get(analysis_id)

def make_enhancement(analysis_id, options):
    record=get(analysis_id); rel=_save_derivative(record,enhance(_load(record),options),"enhanced","enhanced"); meta=record["metadata"]; meta["derivatives"]["enhanced"]=rel
    conn=_conn(); conn.execute("UPDATE visual_analysis SET enhancement_params_json=?,metadata_json=? WHERE id=?",(json.dumps(options),json.dumps(meta),analysis_id)); conn.commit(); conn.close(); return get(analysis_id)

def create_region(analysis_id, region):
    record=get(analysis_id); image=_load(record); h,w=image.shape[:2]; x,y=int(region["x"]*w),int(region["y"]*h); x2,y2=min(w,int((region["x"]+region["width"])*w)),min(h,int((region["y"]+region["height"])*h))
    if x2<=x or y2<=y: raise HTTPException(422,"Region is outside the image")
    crop=image[y:y2,x:x2]; ok, data=cv2.imencode(".jpg",crop)
    if not ok: raise HTTPException(500,"Could not create crop")
    child=create_bytes(data.tobytes(),f"region_{analysis_id}.jpg","region",parent_analysis_id=analysis_id); child_meta=child["metadata"]; child_meta["region_normalized"]=region
    conn=_conn(); conn.execute("UPDATE visual_analysis SET metadata_json=? WHERE id=?",(json.dumps(child_meta),child["id"])); conn.commit(); conn.close(); return analyze(child["id"])

def delete(analysis_id):
    record=get(analysis_id); conn=_conn(); conn.execute("DELETE FROM visual_analysis WHERE id=? OR parent_analysis_id=?",(analysis_id,analysis_id)); conn.commit(); conn.close()
    for rel in [record["stored_original_path"],*record["metadata"].get("derivatives",{}).values()]:
        path=_safe(rel)
        if path.is_file(): path.unlink()
