"""
Deterministic extractor: reads the declared policy inputs out of application text.
Every value comes with the exact snippet it was read from. A value the document
itself marks as pending or unverified is treated as missing, never used.
"""
import re
from typing import Any, Dict, Optional

NUM = r"[0-9](?:[0-9.,]*[0-9])?"
SUFFIX = r"(?:\s?(?:k|m|mio|mln|million|thousand)\b)?"
AMOUNT = rf"[-−]?[€$]?\s?[-−]?{NUM}{SUFFIX}"
HEDGE = re.compile(r"pending|unverified|not\s+provided|not\s+yet|to\s+be\s+confirmed|\btbc\b|\btbd\b|\bdraft\b", re.I)

AMOUNT_LABELS = {
    "requested_amount_eur": r"(?:Requested(?:\s+Loan)?(?:\s+Amount)?|Facility\s+(?:Size|Request)|Loan\s+Request|Loan\s+Amount)",
    "annual_revenue_eur": r"(?:Gross\s+Revenue|Annual\s+Revenue|Turnover|Revenue)",
    "ebitda_eur": r"(?:Operating\s+Profit\s*/\s*EBITDA|Operating\s+Profit|EBITDA)",
    "annual_debt_service_eur": r"(?:Annual\s+Debt\s+Service|Debt\s+Service|Annual\s+P&I|P&I)",
    "total_existing_debt_eur": r"(?:Total\s+Existing\s+Liabilities|Total\s+Existing\s+Debt|Total\s+Liabilities|Existing\s+Debt)",
    "collateral_value_eur": r"(?:Collateral(?:\s+Value)?|Real\s+Estate\s+Appraisal|Appraisal)",
}
ALL_FIELDS = list(AMOUNT_LABELS) + ["years_in_business", "tax_returns_verified"]


def parse_amount(text: Optional[str]) -> Optional[float]:
    """Parses '€500,000', '500.000,00', '€450k', '1.2m', '-€72,000' into a float number of euros."""
    if not text:
        return None
    s = text.strip().lower().replace("−", "-")
    neg = "-" in s
    s = s.replace("-", "").replace("€", "").replace("$", "").strip()
    mult = 1.0
    m = re.search(r"(k|thousand|mio|mln|million|m)$", s)
    if m:
        mult = 1_000.0 if m.group(1) in ("k", "thousand") else 1_000_000.0
        s = s[:m.start()].strip()
    if "." in s and "," in s:  # the last separator is the decimal one
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif "." in s and mult == 1.0 and re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")  # 500.000 written the European way
    try:
        val = float(s) * mult
    except ValueError:
        return None
    return -val if neg else val


def numbers_in(text: str):
    return [v for v in (parse_amount(m.group(0)) for m in re.finditer(AMOUNT, text, re.I)) if v is not None]


def _field(value=None, quote=None, note=None) -> Dict[str, Any]:
    return {"value": value, "quote": quote, "note": note}


def extract_with_rules(raw_text: str) -> Dict[str, Any]:
    fields: Dict[str, Dict[str, Any]] = {}

    for name, label in AMOUNT_LABELS.items():
        pattern = rf"{label}[^\n\r:=0-9]{{0,35}}?[:=]?[ \t]*(?P<amt>{AMOUNT})"
        result = _field()
        for m in re.finditer(pattern, raw_text, re.I):
            snippet = " ".join(m.group(0).split())
            if HEDGE.search(snippet):
                result = _field(None, snippet, "the document marks this figure as pending or unverified, so it is not used")
                continue
            val = parse_amount(m.group("amt"))
            if val is not None:
                result = _field(val, snippet)
                break
        fields[name] = result

    m = (re.search(r"(?:Years\s+in\s+Business|Operating\s+History)[ \t]*[:=][ \t]*([0-9]+)", raw_text, re.I)
         or re.search(r"([0-9]+)\+?\s+years?\s+in\s+business", raw_text, re.I))
    fields["years_in_business"] = _field(int(m.group(1)), " ".join(m.group(0).split())) if m else _field()

    tax = _field()
    for m in re.finditer(r"Tax\s+(?:Returns?|Filings?)[^\n\r:]{0,20}:[ \t]*([^\n\r.;]{0,60})", raw_text, re.I):
        quote = " ".join(m.group(0).split())
        state = m.group(1).strip().lower()
        if re.match(r"(unverified|missing|pending|unconfirmed|no\b|not\s)", state) or HEDGE.search(state):
            tax = _field(False, quote)
            break
        if re.match(r"(verified|audited|confirmed|yes\b|compliant)", state):
            tax = _field(True, quote)
            break
    fields["tax_returns_verified"] = tax

    m = re.search(r"(?:Company(?:\s+Name)?|Applicant(?:\s+Entity)?|Entity):[ \t]*([^\n\r,.;]+)", raw_text, re.I)
    return {"company_name": m.group(1).strip() if m else "Unknown applicant", "fields": fields,
            "engine": "Rule-based extractor (offline)", "dropped": []}
