"""
Policy PDF text extraction and clause identification (India-oriented).

Nothing here is authoritative: every identified clause is stored as status "Extracted" and only becomes
part of a policy's terms after an authorised human marks it "Verified". Values that are not found in
the document are left empty; nothing is inferred or defaulted.
"""
import io
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

_NUM = r"(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_CUR = r"(?:₹|Rs\.?|INR)\s*"
_UNIT = r"(?:\s*(lakhs?|lacs?|crores?|crs?\.?))?"
AMOUNT_RE = re.compile(rf"{_CUR}{_NUM}{_UNIT}", re.IGNORECASE)

CATEGORY_RULES: List[Tuple[str, re.Pattern]] = [
    ("sum_insured", re.compile(r"sum\s+insured|insured\s+value|building\s+sum|value\s+at\s+risk|reinstatement\s+value", re.I)),
    ("sub_limit", re.compile(r"sub[\s-]?limit|limit\s+per\s+(?:item|event)|maximum\s+liability\s+(?:for|in\s+respect)|not\s+exceed", re.I)),
    ("deductible", re.compile(r"\bexcess\b|deductible|compulsory\s+(?:excess|deductible)|voluntary\s+(?:excess|deductible)", re.I)),
    ("exclusion", re.compile(r"\bexclusions?\b|not\s+covered|shall\s+not\s+(?:be\s+liable|cover)|excluded|we\s+(?:will\s+)?not\s+pay", re.I)),
    ("insured_peril", re.compile(
        r"perils?\s+covered|insured\s+perils?|\b(?:fire|lightning|explosion|implosion|storm|cyclone|typhoon|tempest|hurricane|tornado|"
        r"flood|inundation|impact\s+damage|subsidence|landslide|rockslide|bursting|overflowing|riot|strike|malicious|"
        r"earthquake|terroris[mt])\b", re.I)),
    ("usage", re.compile(r"occupancy|use\s+of\s+(?:the\s+)?(?:premises|building|property)|residential\s+use|commercial\s+use|change\s+in\s+(?:use|occupancy)", re.I)),
    ("condition", re.compile(r"alteration|material\s+(?:change|fact)|disclos|duty\s+of\s+(?:the\s+)?insured|average\s+clause|under[\s-]?insurance|"
                             r"notice\s+of\s+claim|within\s+\d+\s+days|condition", re.I)),
    ("endorsement", re.compile(r"endorsement|add[\s-]?on|extension|solar|photovoltaic", re.I)),
]

PERIL_VOCAB = {
    "Fire": ["fire"], "Lightning": ["lightning"], "Explosion/Implosion": ["explosion", "implosion"],
    "Aircraft damage": ["aircraft"], "Riot, strike, malicious damage": ["riot", "strike", "malicious"],
    "Storm, cyclone, typhoon, tempest, hurricane, tornado": ["storm", "cyclone", "typhoon", "tempest", "hurricane", "tornado"],
    "Flood and inundation": ["flood", "inundation"], "Impact damage": ["impact"],
    "Subsidence, landslide, rockslide": ["subsidence", "landslide", "rockslide"],
    "Bursting/overflowing of water tanks, apparatus, pipes": ["bursting", "overflowing"],
    "Missile testing operations": ["missile"], "Leakage from sprinkler installations": ["sprinkler"],
    "Bush fire": ["bush fire", "forest fire"], "Earthquake": ["earthquake"], "Terrorism": ["terroris"],
    "Hail": ["hail"],
}

_HEADING_RE = re.compile(r"^\s*((?:section|clause|condition|exclusion|article)?\s*\d+(?:\.\d+){0,3}[.)]?|[A-Z]\)|\([a-z0-9]{1,3}\))\s+(.{3,})$", re.I)


def parse_amount(text: str) -> Optional[float]:
    """Parse an Indian-format money amount (₹/Rs/INR, lakh/crore) from text. Returns None if absent."""
    m = AMOUNT_RE.search(text or "")
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    if unit.startswith(("lakh", "lac")):
        value *= 100_000
    elif unit.startswith(("crore", "cr")):
        value *= 10_000_000
    return value


def all_amounts(text: str) -> List[float]:
    out = []
    for m in AMOUNT_RE.finditer(text or ""):
        v = float(m.group(1).replace(",", ""))
        u = (m.group(2) or "").lower()
        v *= 100_000 if u.startswith(("lakh", "lac")) else 10_000_000 if u.startswith(("crore", "cr")) else 1
        out.append(v)
    return out


# --------------------------------------------------------------------------- text extraction
def extract_pdf_pages(data: bytes) -> Dict[str, Any]:
    """Return {"pages": [str,...], "method": str, "warnings": [...]}. Tries text layer, then OCR if installed."""
    warnings: List[str] = []
    pages: List[str] = []
    method = None
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                warnings.append("PDF is password protected; extraction not possible.")
                return {"pages": [], "method": None, "warnings": warnings}
        pages = [(p.extract_text() or "") for p in reader.pages]
        method = "pypdf-text-layer"
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"pypdf failed: {exc.__class__.__name__}")

    if not any(p.strip() for p in pages):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [(pg.extract_text() or "") for pg in pdf.pages]
            method = "pdfplumber-text-layer"
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"pdfplumber failed: {exc.__class__.__name__}")

    if not any(p.strip() for p in pages):
        try:  # OCR fallback for scanned policies (needs tesseract binary + pdf2image/poppler)
            import pytesseract
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(data, dpi=200)
            pages = [pytesseract.image_to_string(im) for im in images]
            method = "tesseract-ocr"
        except Exception as exc:  # noqa: BLE001
            warnings.append(
                "No text layer found and OCR is unavailable (install tesseract-ocr, poppler, pytesseract, pdf2image "
                f"to process scanned policies): {exc.__class__.__name__}"
            )
    return {"pages": pages, "method": method, "warnings": warnings}


# --------------------------------------------------------------------------- clause identification
def _classify(text: str) -> str:
    for cat, rx in CATEGORY_RULES:
        if rx.search(text):
            return cat
    return "other"


def _values_for(category: str, text: str) -> Dict[str, Any]:
    vals: Dict[str, Any] = {}
    amounts = all_amounts(text)
    if category in ("sum_insured", "deductible", "sub_limit") and amounts:
        vals["amounts_inr"] = amounts
        vals["amount_inr"] = amounts[0]
    if category == "deductible":
        vals["basis"] = "percentage" if re.search(r"%|per\s*cent", text, re.I) and not amounts else "fixed"
        pm = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if pm:
            vals["percent"] = float(pm.group(1))
    if category == "insured_peril":
        low = text.lower()
        vals["perils_mentioned"] = [name for name, kws in PERIL_VOCAB.items() if any(k in low for k in kws)]
    if category == "condition" and re.search(r"average\s+clause|under[\s-]?insurance|proportion", text, re.I):
        vals["average_clause"] = True
    return vals


def identify_clauses(pages: List[str], max_clause_chars: int = 1200) -> List[Dict[str, Any]]:
    """Split page text into numbered/bulleted clauses and classify them. Pure function; deterministic."""
    clauses: List[Dict[str, Any]] = []
    for page_no, page in enumerate(pages, start=1):
        cur_ref, cur_lines = None, []

        def flush():
            nonlocal cur_ref, cur_lines
            body = " ".join(" ".join(cur_lines).split())
            if len(body) >= 15:
                cat = _classify(body)
                if cat != "other":
                    clauses.append({
                        "page_number": page_no, "clause_ref": cur_ref, "category": cat,
                        "text": body[:max_clause_chars], "extracted_values": _values_for(cat, body),
                    })
            cur_ref, cur_lines = None, []

        for line in page.splitlines():
            if not line.strip():
                continue
            m = _HEADING_RE.match(line)
            if m:
                flush()
                cur_ref = m.group(1).strip()
                cur_lines = [m.group(2)]
            else:
                cur_lines.append(line.strip())
        flush()
    return clauses


def header_fields(pages: List[str]) -> Dict[str, Any]:
    """Best-effort policy schedule header fields (policy number, period). Suggestions only."""
    text = "\n".join(pages)
    out: Dict[str, Any] = {}
    m = re.search(r"Policy\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]{4,})", text, re.I)
    if m:
        out["policy_number"] = m.group(1)
    date = r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}|\d{4}-\d{2}-\d{2})"
    m = re.search(rf"(?:Period\s+of\s+Insurance|Policy\s+Period)[^\n]*?(?:From|:)\s*{date}\D+(?:to|To|until)\s*{date}", text)
    if m:
        out["period_from"], out["period_to"] = m.group(1), m.group(2)
    return out


# --------------------------------------------------------------------------- verified clauses -> terms
def terms_from_verified_clauses(clauses: List[Any]) -> Dict[str, Any]:
    """
    Build structured policy terms from clauses with status 'Verified' only.
    A clause may carry reviewer-corrected values in extracted_values (e.g. {"label": "wind_hail", "amount_inr": 50000}).
    """
    terms: Dict[str, Any] = {
        "coverage_limits": {}, "deductibles": {}, "exclusions": [], "endorsements": [],
        "structured_terms": {"insured_perils": [], "sub_limits": {}, "conditions": []},
    }
    st = terms["structured_terms"]
    for c in clauses:
        if c.status != "Verified":
            continue
        v = c.extracted_values or {}
        label = (v.get("label") or "").strip()
        amt = v.get("amount_inr")
        if c.category == "sum_insured" and amt is not None:
            terms["coverage_limits"][label or "dwelling"] = float(amt)
            if not label or label == "dwelling":
                st["sum_insured"] = float(amt)
            if v.get("reinstatement_value") is not None:
                st["reinstatement_value"] = float(v["reinstatement_value"])
        elif c.category == "deductible" and amt is not None:
            terms["deductibles"][label or "standard"] = float(amt)
        elif c.category == "sub_limit" and amt is not None and label:
            st["sub_limits"][label] = float(amt)
        elif c.category == "exclusion":
            terms["exclusions"].append(v.get("summary") or c.text)
        elif c.category == "insured_peril":
            perils = v.get("perils") or v.get("perils_mentioned") or []
            st["insured_perils"].extend(p for p in perils if p not in st["insured_perils"])
        elif c.category == "endorsement":
            terms["endorsements"].append(v.get("summary") or c.text)
        elif c.category == "usage" and v.get("insured_usage"):
            st["insured_usage"] = v["insured_usage"]
        elif c.category == "condition":
            st["conditions"].append(c.text)
            if v.get("average_clause"):
                st["average_clause"] = True
    return terms
