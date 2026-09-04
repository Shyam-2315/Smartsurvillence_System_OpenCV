"""Text-only, bounded web-search providers. Images and metadata never leave this module."""
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import requests
import config

TRACKING = {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid"}

def _clean_url(url):
    p=urlsplit(url); query=[(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, urlencode(query), ""))

def domain(url): return urlsplit(url).hostname.lower() if urlsplit(url).hostname else ""

def source_type(url, title=""):
    host=domain(url); text=(host+" "+title).lower()
    if "official" in title.lower(): return "official"
    if any(x in host for x in ("docs.", "support.", "developer.")) or "documentation" in text: return "documentation"
    if any(x in host for x in ("amazon.", "walmart.", "ebay.", "bestbuy.", "flipkart.")): return "retailer"
    if any(x in host for x in ("reddit.", "forum.", "community.")): return "community"
    if any(x in host for x in ("news", "bbc.", "reuters.", "cnn.")): return "news"
    if any(x in host for x in ("review", "techradar.", "cnet.")): return "review"
    if any(x in host for x in ("lenovo.", "dell.", "hp.", "apple.", "samsung.", "microsoft.")): return "manufacturer"
    return "unknown"

def status():
    s=config.settings
    if not s.web_search_enabled: return {"configured":False,"status":"Disabled","reason":"Web Intelligence is not configured."}
    if s.web_search_provider != "brave": return {"configured":False,"status":"Error","reason":"Configured web-search provider is unsupported"}
    if not s.web_search_api_key: return {"configured":False,"status":"Error","reason":"API key missing"}
    return {"configured":True,"status":"Configured","provider":"brave"}

def queries(ocr, entities, detections, selected_text=None):
    """Rank query candidates deterministically from textual visual evidence only."""
    ocr_values=[x["text"].strip() for x in ocr if x.get("confidence",0)>=.55 and len(x.get("text","").strip())>=3]
    if selected_text: ocr_values=[selected_text.strip()]
    tokens=[]
    for value in ocr_values + entities.get("organizations",[]) + entities.get("model_codes",[]) + entities.get("domains",[]) + entities.get("qr_content",[]):
        if value and value not in tokens and not any(value.lower() in prior.lower() for prior in tokens): tokens.append(value)
    phrase=" ".join(tokens)[:160].strip()
    if not phrase: return []
    evidence=[f"OCR: {x}" for x in ocr_values] + [f"Model code: {x}" for x in entities.get("model_codes",[]) if x in phrase] + [f"Object: {x['class']}" for x in detections[:2]]
    score=min(.99, .45+min(.40,.20*len(ocr_values))+(.10 if entities.get("model_codes") else 0)+(.06 if detections else 0))
    variants=[phrase]
    if entities.get("organizations") or entities.get("model_codes"): variants += [phrase+" official", phrase+" specifications"]
    return [{"query":q,"score":round(score-(i*.03),2),"evidence":evidence} for i,q in enumerate(dict.fromkeys(variants))][:getattr(config.settings,"web_search_max_queries",3)]

def search(query_list):
    state=status()
    if not state["configured"]: return [], state["reason"]
    results=[]; limit=getattr(config.settings,"web_search_results_per_query",5)
    for item in query_list[:getattr(config.settings,"web_search_max_queries",3)]:
        query=item["query"] if isinstance(item,dict) else item
        try:
            response=requests.get("https://api.search.brave.com/res/v1/web/search", params={"q":query,"count":limit}, headers={"Accept":"application/json","X-Subscription-Token":config.settings.web_search_api_key}, timeout=getattr(config.settings,"web_search_timeout_seconds",8))
            if getattr(response,"status_code",200) in (401,403): return results,"Brave Search authorization failed. Ask an administrator to verify the API key."
            if getattr(response,"status_code",200) == 429: return results,"Brave Search rate limit reached. Try again later."
            response.raise_for_status()
        except requests.Timeout: return results,"Brave Search timed out. Try again later."
        except requests.RequestException: return results,"Brave Search network request failed. Try again later."
        for rank, raw in enumerate(response.json().get("web",{}).get("results",[])[:limit],1):
            url=_clean_url(raw.get("url", ""))
            if url: results.append({"query":query,"title":raw.get("title", ""),"url":url,"domain":domain(url),"snippet":raw.get("description", ""),"rank":rank,"provider":"brave","retrieved_at":datetime.now(timezone.utc).isoformat(),"source_type":source_type(url,raw.get("title",""))})
    seen=set(); return [x for x in results if not (x["url"] in seen or seen.add(x["url"]))],None
