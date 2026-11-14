"""
DMN Generator and Rule Evaluator.
Produces OMG DMN 1.3 compliant XML and executes deterministic decision logic.
Reads the canonical policy file from credit_policy.dmn if present.
"""
import os
from typing import Dict, Any, Tuple, List
from xml.sax.saxutils import escape
from models import FinancialRatios, ExtractedFinancials, ConstraintEvaluation

CANONICAL_DMN_PATH = os.path.join(os.path.dirname(__file__), "credit_policy.dmn")

def generate_dmn_xml(model_name: str = "Commercial_Credit_Ruling_Model") -> str:
    """
    Returns the OMG DMN 1.3 XML definition.
    Loads from canonical credit_policy.dmn if present on disk.
    """
    if os.path.exists(CANONICAL_DMN_PATH):
        with open(CANONICAL_DMN_PATH, "r", encoding="utf-8") as f:
            return f.read()

    # Fallback inline definition
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/"
             xmlns:dmndi="https://www.omg.org/spec/DMN/20191111/DMNDI/"
             xmlns:dc="http://www.omg.org/spec/DMN/20180521/DC/"
             id="Definitions_CreditRuling"
             name="{escape(model_name)}"
             namespace="http://kakashi.ventures/hackathon/dmn/credit">

  <decision id="Decision_LoanGrant" name="Commercial Loan Approval Decision">
    <decisionTable id="DecisionTable_CreditPolicy" hitPolicy="FIRST">
      
      <!-- Inputs -->
      <input id="Input_DSCR" label="Debt Service Coverage Ratio (DSCR)">
        <inputExpression id="InputExpr_DSCR" typeRef="number">
          <text>dscr</text>
        </inputExpression>
      </input>
      <input id="Input_LTV" label="Loan-to-Value (LTV)">
        <inputExpression id="InputExpr_LTV" typeRef="number">
          <text>ltv</text>
        </inputExpression>
      </input>
      <input id="Input_Years" label="Years in Business">
        <inputExpression id="InputExpr_Years" typeRef="integer">
          <text>years_in_business</text>
        </inputExpression>
      </input>
      <input id="Input_TaxVerified" label="Tax Returns Verified">
        <inputExpression id="InputExpr_TaxVerified" typeRef="boolean">
          <text>tax_returns_verified</text>
        </inputExpression>
      </input>

      <!-- Outputs -->
      <output id="Output_Ruling" label="Ruling" name="ruling" typeRef="string" />
      <output id="Output_APR" label="Offered APR (%)" name="interest_rate_apr" typeRef="number" />
      <output id="Output_Rationale" label="Ruling Rationale" name="rationale" typeRef="string" />

      <!-- Rule 1: Prime Approval -->
      <rule id="Rule_1_Prime">
        <inputEntry id="IE_1_1"><text>&gt;= 1.35</text></inputEntry>
        <inputEntry id="IE_1_2"><text>&lt;= 0.70</text></inputEntry>
        <inputEntry id="IE_1_3"><text>&gt;= 3</text></inputEntry>
        <inputEntry id="IE_1_4"><text>true</text></inputEntry>
        <outputEntry id="OE_1_1"><text>"GRANTED_PRIME"</text></outputEntry>
        <outputEntry id="OE_1_2"><text>5.5</text></outputEntry>
        <outputEntry id="OE_1_3"><text>"Prime commercial tier: robust debt coverage and conservative leverage"</text></outputEntry>
      </rule>

      <!-- Rule 2: Standard Approval -->
      <rule id="Rule_2_Standard">
        <inputEntry id="IE_2_1"><text>&gt;= 1.20</text></inputEntry>
        <inputEntry id="IE_2_2"><text>&lt;= 0.80</text></inputEntry>
        <inputEntry id="IE_2_3"><text>&gt;= 2</text></inputEntry>
        <inputEntry id="IE_2_4"><text>true</text></inputEntry>
        <outputEntry id="OE_2_1"><text>"GRANTED_STANDARD"</text></outputEntry>
        <outputEntry id="OE_2_2"><text>7.2</text></outputEntry>
        <outputEntry id="OE_2_3"><text>"Standard commercial tier: acceptable cashflow coverage within underwriting limits"</text></outputEntry>
      </rule>

      <!-- Rule 3: Insufficient DSCR Denial -->
      <rule id="Rule_3_LowDSCR">
        <inputEntry id="IE_3_1"><text>&lt; 1.15</text></inputEntry>
        <inputEntry id="IE_3_2"><text>-</text></inputEntry>
        <inputEntry id="IE_3_3"><text>-</text></inputEntry>
        <inputEntry id="IE_3_4"><text>-</text></inputEntry>
        <outputEntry id="OE_3_1"><text>"DENIED_CREDIT_POLICY"</text></outputEntry>
        <outputEntry id="OE_3_2"><text>null</text></outputEntry>
        <outputEntry id="OE_3_3"><text>"Breach of minimum debt service coverage covenant (DSCR &lt; 1.15)"</text></outputEntry>
      </rule>

      <!-- Rule 4: Excessive LTV Denial -->
      <rule id="Rule_4_HighLTV">
        <inputEntry id="IE_4_1"><text>-</text></inputEntry>
        <inputEntry id="IE_4_2"><text>&gt; 0.85</text></inputEntry>
        <inputEntry id="IE_4_3"><text>-</text></inputEntry>
        <inputEntry id="IE_4_4"><text>-</text></inputEntry>
        <outputEntry id="OE_4_1"><text>"DENIED_CREDIT_POLICY"</text></outputEntry>
        <outputEntry id="OE_4_2"><text>null</text></outputEntry>
        <outputEntry id="OE_4_3"><text>"Breach of maximum loan-to-value ceiling (LTV &gt; 85%)"</text></outputEntry>
      </rule>

      <!-- Rule 5: Missing or Unverified Tax Filings (Abstain) -->
      <rule id="Rule_5_Abstain_Tax">
        <inputEntry id="IE_5_1"><text>-</text></inputEntry>
        <inputEntry id="IE_5_2"><text>-</text></inputEntry>
        <inputEntry id="IE_5_3"><text>-</text></inputEntry>
        <inputEntry id="IE_5_4"><text>false</text></inputEntry>
        <outputEntry id="OE_5_1"><text>"ABSTAIN_DATA_INCOMPLETE"</text></outputEntry>
        <outputEntry id="OE_5_2"><text>null</text></outputEntry>
        <outputEntry id="OE_5_3"><text>"Mandatory audited tax filings absent or unverified; system refuses to guess"</text></outputEntry>
      </rule>

      <!-- Rule 6: Fallback Default Policy Rejection -->
      <rule id="Rule_6_DefaultReject">
        <inputEntry id="IE_6_1"><text>-</text></inputEntry>
        <inputEntry id="IE_6_2"><text>-</text></inputEntry>
        <inputEntry id="IE_6_3"><text>-</text></inputEntry>
        <inputEntry id="IE_6_4"><text>-</text></inputEntry>
        <outputEntry id="OE_6_1"><text>"DENIED_CREDIT_POLICY"</text></outputEntry>
        <outputEntry id="OE_6_2"><text>null</text></outputEntry>
        <outputEntry id="OE_6_3"><text>"Credit application falls outside prime and standard risk tolerances"</text></outputEntry>
      </rule>

    </decisionTable>
  </decision>
</definitions>
"""
    return xml.strip()

def evaluate_dmn_rules(financials: ExtractedFinancials, ratios: FinancialRatios, missing_fields: List[str]) -> Dict[str, Any]:
    """
    Deterministically evaluates the DMN decision table.
    Returns ruling dictionary, constraints list, tripwires, and rejected alternatives.
    """
    dscr = ratios.dscr
    ltv = ratios.ltv
    years = financials.years_in_business if financials.years_in_business is not None else 0
    tax_verified = financials.tax_returns_verified is True

    # 1. Check Hard Abstention (Missing required evidence)
    if "tax_returns_verified" in missing_fields or not tax_verified or dscr is None or ltv is None:
        missing_reasons = []
        if not tax_verified:
            missing_reasons.append("Audited IRS/ECB tax filings not verified")
        if dscr is None:
            missing_reasons.append("EBITDA or Debt Service missing; cannot compute DSCR")
        if ltv is None:
            missing_reasons.append("Collateral valuation missing; cannot compute LTV")

        return {
            "status": "ABSTAIN",
            "ruling_category": "ABSTAIN_DATA_INCOMPLETE",
            "rule_id": "Rule_5_Abstain_Tax",
            "interest_rate_apr": None,
            "rationale": "Missing mandatory underwriting evidence: " + "; ".join(missing_reasons),
            "constraints_evaluated": [
                {"rule": "MANDATORY_EVIDENCE_CHECK", "condition": "All critical financial metrics present", "actual": f"Missing: {missing_fields}", "result": "FAIL"},
                {"rule": "TAX_FILING_AUDIT", "condition": "Tax returns verified == true", "actual": str(tax_verified), "result": "FAIL" if not tax_verified else "PASS"}
            ],
            "tripwires_and_bounds": {},
            "alternatives_rejected": [
                {"action": "AUTO_REJECT", "reason": "Unfair to applicant without verifying true financial health"},
                {"action": "AUTO_APPROVE", "reason": "Illegal under regulatory banking compliance to approve without verified tax documents"}
            ],
            "missing_evidence": missing_fields
        }

    # 2. Constraints Tracking
    c_dscr = {
        "rule": "DSCR_COVENANT",
        "condition": "DSCR >= 1.20 (Standard) or >= 1.35 (Prime)",
        "actual": f"{dscr:.2f}",
        "result": "PASS" if dscr >= 1.20 else "FAIL"
    }
    c_ltv = {
        "rule": "LTV_CEILING",
        "condition": "LTV <= 0.80 (Standard) or <= 0.70 (Prime)",
        "actual": f"{ltv*100:.1f}%",
        "result": "PASS" if ltv <= 0.80 else "FAIL"
    }
    c_yib = {
        "rule": "OPERATING_TRACK_RECORD",
        "condition": "Years in business >= 2",
        "actual": f"{years} years",
        "result": "PASS" if years >= 2 else "FAIL"
    }
    c_tax = {
        "rule": "TAX_FILING_AUDIT",
        "condition": "Tax returns verified == true",
        "actual": "Verified",
        "result": "PASS"
    }
    constraints = [c_dscr, c_ltv, c_yib, c_tax]

    # Rule 1: Prime Approval
    if dscr >= 1.35 and ltv <= 0.70 and years >= 3 and tax_verified:
        return {
            "status": "GRANTED",
            "ruling_category": "APPROVED_PRIME",
            "rule_id": "Rule_1_Prime",
            "interest_rate_apr": 5.5,
            "rationale": f"Prime commercial credit grant: DSCR of {dscr:.2f} (exceeds 1.35 benchmark) and LTV of {ltv*100:.1f}% (under 70% threshold).",
            "constraints_evaluated": constraints,
            "tripwires_and_bounds": {
                "max_draw_period_months": 36,
                "annual_financial_reporting_covenant": "Audited balance sheet due within 90 days of fiscal year end",
                "minimum_ongoing_dscr": 1.25,
                "revocation_trigger": "DSCR falls below 1.15 in any trailing two quarters"
            },
            "alternatives_rejected": [
                {"action": "STANDARD_TIER", "reason": "Applicant qualifies for prime pricing based on exemplary liquidity and low leverage"},
                {"action": "REJECTION", "reason": "No policy covenants breached"}
            ],
            "missing_evidence": []
        }

    # Rule 2: Standard Approval
    if dscr >= 1.20 and ltv <= 0.80 and years >= 2 and tax_verified:
        return {
            "status": "GRANTED",
            "ruling_category": "APPROVED_STANDARD",
            "rule_id": "Rule_2_Standard",
            "interest_rate_apr": 7.2,
            "rationale": f"Standard commercial credit grant: DSCR of {dscr:.2f} satisfies standard coverage, LTV of {ltv*100:.1f}% supported by pledged collateral.",
            "constraints_evaluated": constraints,
            "tripwires_and_bounds": {
                "max_draw_period_months": 24,
                "semi_annual_covenant_check": "DSCR reporting every 6 months",
                "minimum_ongoing_dscr": 1.18,
                "revocation_trigger": "LTV exceeds 85% or DSCR falls below 1.10"
            },
            "alternatives_rejected": [
                {"action": "PRIME_TIER", "reason": "DSCR < 1.35 or LTV > 70% does not satisfy prime margin of safety"},
                {"action": "REJECTION", "reason": "Sufficient operating history and debt service capability"}
            ],
            "missing_evidence": []
        }

    # Rule 3: Low DSCR Denial
    if dscr < 1.15:
        return {
            "status": "DENIED",
            "ruling_category": "DENIED_CREDIT_POLICY",
            "rule_id": "Rule_3_LowDSCR",
            "interest_rate_apr": None,
            "rationale": f"Application denied under Rule 3: DSCR of {dscr:.2f} is below the non-negotiable floor of 1.15. Cashflow cannot absorb interest rate shocks.",
            "constraints_evaluated": constraints,
            "tripwires_and_bounds": {},
            "alternatives_rejected": [
                {"action": "APPROVAL_WITH_SURCHARGE", "reason": "Regulated lending policy forbids granting credit with sub-1.15 DSCR"},
                {"action": "SUBORDINATED_DEBT", "reason": "Senior debt coverage insufficient"}
            ],
            "missing_evidence": []
        }

    # Rule 4: Excessive LTV Denial
    if ltv > 0.85:
        return {
            "status": "DENIED",
            "ruling_category": "DENIED_CREDIT_POLICY",
            "rule_id": "Rule_4_HighLTV",
            "interest_rate_apr": None,
            "rationale": f"Application denied under Rule 4: LTV of {ltv*100:.1f}% exceeds bank regulatory cap of 85%. Inadequate recovery buffer in default scenario.",
            "constraints_evaluated": constraints,
            "tripwires_and_bounds": {},
            "alternatives_rejected": [
                {"action": "APPROVAL", "reason": "Collateral shortfall exposes institution to unsecured loss in default"}
            ],
            "missing_evidence": []
        }

    # Fallback Default Rejection
    return {
        "status": "DENIED",
        "ruling_category": "DENIED_CREDIT_POLICY",
        "rule_id": "Rule_6_DefaultReject",
        "interest_rate_apr": None,
        "rationale": f"Application falls outside acceptable risk boundaries (DSCR: {dscr:.2f}, LTV: {ltv*100:.1f}%, History: {years} yrs).",
        "constraints_evaluated": constraints,
        "tripwires_and_bounds": {},
        "alternatives_rejected": [
            {"action": "APPROVAL", "reason": "Composite risk score below underwriting threshold"}
        ],
        "missing_evidence": []
    }
