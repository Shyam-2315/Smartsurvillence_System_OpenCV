def correlate(ocr, detections, entities, sources):
    """Keep direct observation, retrieved text, and cautious inference distinct."""
    observed=[x.get("text","") for x in ocr]; candidates=[]
    for source in sources:
        title=source.get("title",""); hits=[v for v in observed if len(v)>=3 and v.lower() in title.lower()]
        if not hits: continue
        support=[f"OCR: {v}" for v in hits]+[f"{source.get('source_type','unknown').title()} source: {source.get('domain','')}"]+[f"Object: {d['class']}" for d in detections[:1]]
        score=.45+min(.35,.12*len(hits))+(.12 if source.get("source_type") in {"official","manufacturer","documentation"} else .03)+(.06 if detections else 0)
        candidates.append({"name":title,"confidence":"HIGH" if score>=.78 else "MEDIUM" if score>=.58 else "LOW","evidence_score":round(score,2),"supporting_evidence":support,"source_url":source.get("url")})
    models=entities.get("model_codes",[])
    contradictions=["Evidence is inconsistent; exact model or generation cannot be confirmed."] if len(models)>1 else []
    return {"observed":{"ocr":ocr,"objects":detections,"entities":entities},"retrieved":{"sources":sources},"inferred":{"candidate_matches":candidates,"contradictions":contradictions}}
