"""
Extractor module: parses messy credit application text and computes financial risk ratios.
"""
import re
from typing import Tuple, List, Optional
from models import ExtractedFinancials, FinancialRatios

def parse_currency_amount(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    cleaned = text.lower().replace(",", "").replace("€", "").replace("$", "").replace("eur", "").replace("usd", "").strip()
    mult = 1.0
    if cleaned.endswith("k"):
        mult = 1_000.0
        cleaned = cleaned[:-1].strip()
    elif cleaned.endswith("m") or cleaned.endswith("mio"):
        mult = 1_000_000.0
        cleaned = cleaned.replace("mio", "").replace("m", "").strip()
    try:
        return float(cleaned) * mult
    except ValueError:
        return None

def extract_financials_from_text(raw_text: str) -> Tuple[ExtractedFinancials, FinancialRatios, List[str]]:
    """
    Parses messy text using financial keyword patterns.
    Returns (ExtractedFinancials, FinancialRatios, missing_mandatory_fields).
    """
    def find_amount(label_pattern: str) -> Optional[float]:
        pattern = label_pattern + r"[^\n\r:=0-9]{0,35}[:=]?\s*([€\$]?\s*[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?\s*(?:k|m|mio|eur|usd)?)"
        m = re.search(pattern, raw_text, re.IGNORECASE)
        return parse_currency_amount(m.group(1)) if m else None

    # 1. Company Name
    name_match = re.search(r"(?:Company(?:\s+Name)?|Applicant(?:\s+Entity)?|Entity):\s*([^\n\r,\.;]+)", raw_text, re.IGNORECASE)
    company_name = name_match.group(1).strip() if name_match else "Unknown Applicant"

    # 2. Financial Metrics
    requested_amount = find_amount(r"(?:Requested(?:\s+Loan)?(?:\s+Amount)?|Facility\s+(?:Size|Request)|Loan\s+Request)")
    revenue = find_amount(r"(?:Gross\s+Revenue|Annual\s+Revenue|Turnover|Revenue)")
    ebitda = find_amount(r"(?:Operating\s+Profit\s*/\s*EBITDA|Operating\s+Profit|EBITDA|Cash\s+Flow)")
    debt_service = find_amount(r"(?:Existing\s+Annual\s+Debt\s+Service|Annual\s+Debt\s+Service|Debt\s+Service|Annual\s+P&I|P&I)")
    total_debt = find_amount(r"(?:Total\s+Existing\s+Liabilities|Total\s+Existing\s+Debt|Total\s+Liabilities|Existing\s+Debt)")
    collateral = find_amount(r"(?:Collateral(?:\s+Value)?|Securities|Real\s+Estate\s+Appraisal|Appraisal|Collateral)")

    # 3. Years in Business
    yib_match = re.search(r"(?:Years\s+in\s+Business|Operating\s+History|Founded\s+Years\s+Ago):\s*([0-9]+)", raw_text, re.IGNORECASE)
    yib = int(yib_match.group(1)) if yib_match else None
    if yib is None:
        yib_inline = re.search(r"([0-9]+)\s+years\s+in\s+business", raw_text, re.IGNORECASE)
        yib = int(yib_inline.group(1)) if yib_inline else None

    # 4. Tax Returns Verified
    tax_verified = None
    if re.search(r"Tax\s+(?:Returns?|Filings?):\s*(?:verified|audited|confirmed|yes|compliant)", raw_text, re.IGNORECASE):
        tax_verified = True
    elif re.search(r"Tax\s+(?:Returns?|Filings?):\s*(?:unverified|missing|pending|unconfirmed|no|not\s+yet|not\s+provided)", raw_text, re.IGNORECASE):
        tax_verified = False

    # Check missing mandatory underwriting fields
    missing_fields = []
    if requested_amount is None:
        missing_fields.append("requested_amount_eur")
    if ebitda is None:
        missing_fields.append("ebitda_eur")
    if debt_service is None:
        missing_fields.append("annual_debt_service_eur")
    if collateral is None:
        missing_fields.append("collateral_value_eur")
    if tax_verified is None or tax_verified is False:
        missing_fields.append("tax_returns_verified")

    # Compute Ratios
    dscr = None
    if ebitda is not None and debt_service is not None and debt_service > 0:
        dscr = ebitda / debt_service

    ltv = None
    if requested_amount is not None and collateral is not None and collateral > 0:
        ltv = requested_amount / collateral

    debt_to_ebitda = None
    if total_debt is not None and ebitda is not None and ebitda > 0:
        debt_to_ebitda = total_debt / ebitda

    financials = ExtractedFinancials(
        company_name=company_name,
        requested_amount_eur=requested_amount,
        annual_revenue_eur=revenue,
        ebitda_eur=ebitda,
        annual_debt_service_eur=debt_service,
        total_existing_debt_eur=total_debt,
        collateral_value_eur=collateral,
        years_in_business=yib,
        tax_returns_verified=tax_verified
    )

    ratios = FinancialRatios(
        dscr=dscr,
        ltv=ltv,
        debt_to_ebitda=debt_to_ebitda
    )

    return financials, ratios, missing_fields
