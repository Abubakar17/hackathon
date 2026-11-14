"""
AI Underwriting Analyst Agent.
Interacts with the Vercel AI Gateway (Claude) to perform:
1. Unstructured extraction with citations.
2. Professional Underwriting Memorandum synthesis.
3. Robust JSON parsing with regex fallback.
4. Seamless fallback to deterministic engine on timeout or offline mode.
"""
import os
import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional, List

from models import ExtractedFinancials, FinancialRatios
from extractor import extract_financials_from_text

GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"

def load_gateway_key() -> Optional[str]:
    key = os.environ.get("AI_GATEWAY_API_KEY")
    if key and key.strip():
        return key.strip()
    
    env_paths = [".env", "../.env", os.path.join(os.path.dirname(__file__), ".env")]
    for p in env_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("AI_GATEWAY_API_KEY="):
                        val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
    return None

def call_ai_agent(prompt: str, system_prompt: str, model: str = DEFAULT_MODEL, timeout_seconds: int = 12) -> Optional[str]:
    api_key = load_gateway_key()
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "max_tokens": 1200,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        req = urllib.request.Request(
            GATEWAY_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[AI Agent Notice] Gateway call not completed ({e}); using deterministic fallback.")
        return None

def robust_parse_json(resp_text: str) -> Optional[Dict[str, Any]]:
    if not resp_text:
        return None
    cleaned = resp_text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]
    cleaned = cleaned.strip()

    # Attempt 1: Standard JSON parse
    try:
        return json.loads(cleaned, strict=False)
    except Exception:
        pass

    # Attempt 2: Regex extraction fallback if internal unescaped quotes broke json.loads
    data: Dict[str, Any] = {}
    m_name = re.search(r'"company_name":\s*"([^"]+)"', cleaned)
    if m_name:
        data["company_name"] = m_name.group(1).strip()
    else:
        return None

    for k in ["requested_amount_eur", "annual_revenue_eur", "ebitda_eur", "annual_debt_service_eur", "total_existing_debt_eur", "collateral_value_eur"]:
        m = re.search(r'"' + k + r'":\s*([0-9\.]+)', cleaned)
        data[k] = float(m.group(1)) if m else None

    m_yib = re.search(r'"years_in_business":\s*([0-9]+)', cleaned)
    data["years_in_business"] = int(m_yib.group(1)) if m_yib else None

    m_tax = re.search(r'"tax_returns_verified":\s*(true|false)', cleaned, re.I)
    data["tax_returns_verified"] = (m_tax.group(1).lower() == "true") if m_tax else None

    m_memo = re.search(r'"underwriter_memo":\s*"(.*?)"\s*[\},]', cleaned, re.DOTALL)
    data["underwriter_memo"] = m_memo.group(1).strip() if m_memo else "AI underwriter synthesis complete."

    return data

def analyze_with_ai(raw_text: str) -> Optional[Dict[str, Any]]:
    system_prompt = """You are a Senior Commercial Credit Underwriting Analyst AI.
Extract financial numbers from the credit application packet and return ONLY valid JSON:
{
  "company_name": "string",
  "requested_amount_eur": number or null,
  "annual_revenue_eur": number or null,
  "ebitda_eur": number or null,
  "annual_debt_service_eur": number or null,
  "total_existing_debt_eur": number or null,
  "collateral_value_eur": number or null,
  "years_in_business": integer or null,
  "tax_returns_verified": boolean or null,
  "underwriter_memo": "2-sentence executive assessment of borrower risk profile"
}
CRITICAL RULES:
1. Never hallucinate numbers. If an item is missing or unverified, use null.
2. In 'underwriter_memo', do NOT use double quotes. Use single quotes for any quoted terms.
3. Output ONLY the raw JSON object."""

    resp_text = call_ai_agent(f"Analyze this credit memorandum:\n\n{raw_text}", system_prompt)
    if not resp_text:
        return None

    return robust_parse_json(resp_text)

def extract_financials_smart(raw_text: str, prefer_ai: bool = True) -> Tuple[ExtractedFinancials, FinancialRatios, List[str], str, str]:
    """
    Attempts AI extraction if prefer_ai is True and Gateway is reachable.
    Falls back deterministically to rule-based regex extraction.
    Returns: (ExtractedFinancials, FinancialRatios, missing_fields, underwriter_memo, engine_source)
    """
    if prefer_ai:
        ai_data = analyze_with_ai(raw_text)
        if ai_data and ai_data.get("company_name"):
            req = ai_data.get("requested_amount_eur")
            ebitda = ai_data.get("ebitda_eur")
            ds = ai_data.get("annual_debt_service_eur")
            tot_debt = ai_data.get("total_existing_debt_eur")
            col = ai_data.get("collateral_value_eur")
            tax_v = ai_data.get("tax_returns_verified")
            yib = ai_data.get("years_in_business")
            memo = ai_data.get("underwriter_memo", "AI credit synthesis complete.")

            missing_fields = []
            if req is None: missing_fields.append("requested_amount_eur")
            if ebitda is None: missing_fields.append("ebitda_eur")
            if ds is None: missing_fields.append("annual_debt_service_eur")
            if col is None: missing_fields.append("collateral_value_eur")
            if tax_v is None or tax_v is False: missing_fields.append("tax_returns_verified")

            dscr = (ebitda / ds) if (ebitda is not None and ds is not None and ds > 0) else None
            ltv = (req / col) if (req is not None and col is not None and col > 0) else None
            debt_to_ebitda = (tot_debt / ebitda) if (tot_debt is not None and ebitda is not None and ebitda > 0) else None

            financials = ExtractedFinancials(
                company_name=ai_data.get("company_name", "Unknown Applicant"),
                requested_amount_eur=req,
                annual_revenue_eur=ai_data.get("annual_revenue_eur"),
                ebitda_eur=ebitda,
                annual_debt_service_eur=ds,
                total_existing_debt_eur=tot_debt,
                collateral_value_eur=col,
                years_in_business=yib,
                tax_returns_verified=tax_v,
                extraction_source="ai_agent:anthropic/claude-haiku-5.5"
            )
            ratios = FinancialRatios(dscr=dscr, ltv=ltv, debt_to_ebitda=debt_to_ebitda)
            return financials, ratios, missing_fields, memo, "AI Agent (Claude 3.5 Haiku via Vercel Gateway)"

    # Fallback to local deterministic extraction
    fin, rat, missing = extract_financials_from_text(raw_text)
    return fin, rat, missing, "Deterministic heuristic extraction complete.", "Deterministic Rule Engine (Offline)"
