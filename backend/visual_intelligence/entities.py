import re
from urllib.parse import urlparse

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
URL = re.compile(r"\b(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:/[^\s]*)?", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")
MODEL = re.compile(r"\b(?=[A-Z0-9-]{4,}\b)(?=.*\d)[A-Z]{1,6}[A-Z0-9-]*\b")

def extract(ocr: list[dict], qr_values: list[str] | None = None) -> dict:
    text = "\n".join(str(item.get("text", "")) for item in ocr)
    urls = sorted(set(URL.findall(text)))
    domains = sorted({urlparse(u if "://" in u else "//" + u).netloc.lower() for u in urls})
    orgs = sorted({line.strip() for line in text.splitlines() if re.fullmatch(r"[A-Z][A-Za-z0-9 &.-]{2,60}", line.strip()) and not any(c.isdigit() for c in line)})[:10]
    return {"emails": sorted(set(EMAIL.findall(text))), "urls": urls, "domains": domains,
            "phones": sorted(set(PHONE.findall(text))), "model_codes": sorted(set(MODEL.findall(text.upper()))),
            "organizations": orgs, "qr_content": qr_values or []}
