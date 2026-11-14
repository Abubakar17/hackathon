"""
Deterministic extractor: reads the declared policy inputs out of application text.
Every value comes with the exact snippet it was read from. A value the document
itself marks as pending or unverified is treated as missing, never used. A figure the
documents state with two different values is a conflict and is not used either.
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
    "equity_eur": r"(?:Net\s+Equity|Shareholders'?\s+Equity|Total\s+Equity|Net\s+Worth|Patrimonio\s+Netto)",
}
ALL_FIELDS = list(AMOUNT_LABELS) + ["years_in_business", "tax_returns_verified", "days_past_due"]
# Revenue is not used by any rule, so a second revenue figure (a prior year, a forecast) is not a conflict.
CONFLICT_FIELDS = [f for f in AMOUNT_LABELS if f != "annual_revenue_eur"]


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


CONFLICT_NOTE = "the documents give different values for this figure, so none of them is used"


def _distinct(found):
    """Statements of one figure that differ by more than 0.5% from every earlier one."""
    out = []
    for f in found:
        if not any(abs(f["value"] - o["value"]) <= 0.005 * max(abs(o["value"]), 1) for o in out):
            out.append(f)
    return out


def _conflict_field(distinct) -> Dict[str, Any]:
    return {"value": None, "quote": distinct[0]["quote"], "note": CONFLICT_NOTE, "conflict": distinct}


def find_conflicts(raw_text: str) -> Dict[str, Dict[str, Any]]:
    """Fields the documents state with two or more different values. Used by both readers."""
    return {n: f for n, f in extract_with_rules(raw_text)["fields"].items() if f.get("conflict")}


def extract_with_rules(raw_text: str) -> Dict[str, Any]:
    fields: Dict[str, Dict[str, Any]] = {}

    for name, label in AMOUNT_LABELS.items():
        pattern = rf"{label}[^\n\r:=0-9]{{0,35}}?[:=]?[ \t]*(?P<amt>{AMOUNT})"
        result, found = _field(), []
        for m in re.finditer(pattern, raw_text, re.I):
            snippet = " ".join(m.group(0).split())
            if HEDGE.search(snippet):
                if not found:
                    result = _field(None, snippet, "the document marks this figure as pending or unverified, so it is not used")
                continue
            val = parse_amount(m.group("amt"))
            if val is not None:
                found.append({"value": val, "quote": snippet})
        if found:
            result = _field(found[0]["value"], found[0]["quote"])
            if name in CONFLICT_FIELDS:
                distinct = _distinct(found)
                if len(distinct) > 1:
                    result = _conflict_field(distinct)
        fields[name] = result

    m = (re.search(r"(?:Years\s+in\s+Business|Operating\s+History)[ \t]*[:=][ \t]*([0-9]+)", raw_text, re.I)
         or re.search(r"([0-9]+)\+?\s+years?\s+in\s+business", raw_text, re.I))
    fields["years_in_business"] = _field(int(m.group(1)), " ".join(m.group(0).split())) if m else _field()

    m = (re.search(r"(?:Days\s+Past\s+Due|\bDPD\b)[^\n\r:=0-9]{0,25}[:=]?[ \t]*([0-9]+)", raw_text, re.I)
         or re.search(r"([0-9]+)\s+days?\s+past\s+due", raw_text, re.I))
    if m and HEDGE.search(m.group(0)):
        fields["days_past_due"] = _field(None, " ".join(m.group(0).split()), "the document marks this figure as pending or unverified, so it is not used")
    else:
        fields["days_past_due"] = _field(int(m.group(1)), " ".join(m.group(0).split())) if m else _field()

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
