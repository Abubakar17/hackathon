"""
AI extraction agent (Claude via the Vercel AI Gateway).

The model only proposes inputs. Each proposed value must come with a verbatim quote,
and code checks that the quote is in the document and that the number is in the quote.
A value that fails the check is dropped and counts as missing. The model never sees
the policy and never decides anything. Falls back to the rule-based extractor offline.
"""
import json
import os
import re
import urllib.request
from typing import Any, Dict, Optional

from extractor import ALL_FIELDS, HEDGE, extract_with_rules, numbers_in

GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
MODEL = "anthropic/claude-haiku-5.5"
ENGINE_LABEL = f"AI agent ({MODEL} via Vercel AI Gateway), every value checked against its quote"

SYSTEM_PROMPT = """You extract inputs for a credit decision from a loan application document.
Return ONLY a JSON object of this shape, with no other text:
{"company_name": "string",
 "fields": {
  "requested_amount_eur": {"value": number or null, "quote": "string or null"},
  "annual_revenue_eur": {"value": number or null, "quote": "string or null"},
  "ebitda_eur": {"value": number or null, "quote": "string or null"},
  "annual_debt_service_eur": {"value": number or null, "quote": "string or null"},
  "total_existing_debt_eur": {"value": number or null, "quote": "string or null"},
  "collateral_value_eur": {"value": number or null, "quote": "string or null"},
  "years_in_business": {"value": integer or null, "quote": "string or null"},
  "tax_returns_verified": {"value": true, false or null, "quote": "string or null"}}}
Rules:
1. "value" is a plain number of euros (convert 450k to 450000, 1,2 mio to 1200000). Negative figures stay negative.
2. "quote" is copied character for character from one line of the document, at most 120 characters, and contains the figure.
3. If a figure is absent, or the document calls it pending, unverified, draft or not provided, value is null. A figure the document states plainly is extracted even if it is labelled "estimated" or carries a comment. Liabilities count as existing debt. Never calculate or guess a figure.
4. tax_returns_verified is true only if the document says the returns are verified or audited, false if it says they are unverified, draft, pending or missing, null if it does not say.
5. Do not judge the application. Do not recommend anything."""


def load_gateway_key() -> Optional[str]:
    key = os.environ.get("AI_GATEWAY_API_KEY")
    if key and key.strip():
        return key.strip()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("AI_GATEWAY_API_KEY="):
                    val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    return None


def call_gateway(user_text: str, timeout_seconds: int = 15) -> Optional[str]:
    key = load_gateway_key()
    if not key:
        return None
    payload = {"model": MODEL, "max_tokens": 1200, "temperature": 0.0,
               "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_text}]}
    try:
        req = urllib.request.Request(GATEWAY_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
    except Exception as e:  # network, quota, timeout: the caller falls back to the offline extractor
        print(f"[extraction] gateway call failed ({e}); using the rule-based extractor")
        return None


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1], strict=False)
    except ValueError:
        return None


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def ground(name: str, proposed: Any, source_norm: str) -> Dict[str, Any]:
    """Keep a proposed value only if its quote is in the document and supports the value."""
    if not isinstance(proposed, dict) or proposed.get("value") is None:
        return {"value": None, "quote": None, "note": None}
    value, quote = proposed.get("value"), proposed.get("quote")
    drop = lambda why: {"value": None, "quote": quote if isinstance(quote, str) else None, "note": f"AI value {value!r} dropped: {why}"}
    if not isinstance(quote, str) or not quote.strip() or _norm(quote) not in source_norm:
        return drop("its quote is not in the document")
    if name == "tax_returns_verified":
        if not isinstance(value, bool):
            return drop("not a true/false value")
        if value and HEDGE.search(quote):
            return {"value": False, "quote": quote, "note": "AI said verified, but the quote says pending or unverified"}
        return {"value": value, "quote": quote, "note": None}
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return drop("not a number")
    if HEDGE.search(quote):
        return drop("the document marks this figure as pending or unverified")
    if not any(abs(n - value) <= 0.005 * max(abs(value), 1) for n in numbers_in(quote)):
        return drop("the number is not in its quote")
    return {"value": int(value) if name == "years_in_business" else float(value), "quote": quote, "note": None}


def extract(raw_text: str, use_ai: bool = True) -> Dict[str, Any]:
    if use_ai:
        resp = call_gateway(f"Document:\n\n{raw_text}")
        data = _parse_json(resp) if resp else None
        if data and isinstance(data.get("fields"), dict):
            src = _norm(raw_text)
            fields = {name: ground(name, data["fields"].get(name), src) for name in ALL_FIELDS}
            return {"company_name": str(data.get("company_name") or "Unknown applicant"), "fields": fields,
                    "engine": ENGINE_LABEL,
                    "dropped": [f"{n}: {f['note']}" for n, f in fields.items() if f["note"] and f["value"] is None]}
    return extract_with_rules(raw_text)
