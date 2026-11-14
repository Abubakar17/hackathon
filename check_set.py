"""
Automated Verification Check Set: 10 diverse commercial underwriting test cases.
Evaluates deterministic accuracy of decisions, DMN constraints, and abstention triggers.
"""
import sys
from pipeline import process_credit_application

CHECK_SET_CASES = [
    {
        "id": "CASE-01",
        "name": "Alpha Logistics Corp (Prime Pass)",
        "text": "Applicant: Alpha Logistics. Requested Amount: €500,000. Annual Revenue: €4,250,000. EBITDA: €720,000. Annual Debt Service: €380,000. Collateral Value: €950,000. Years in Business: 6. Tax Filings: verified.",
        "expected_status": "GRANTED",
        "expected_category": "APPROVED_PRIME"
    },
    {
        "id": "CASE-02",
        "name": "Delta Industrial Supplies (Standard Pass)",
        "text": "Applicant: Delta Industrial. Requested Amount: €300,000. Annual Revenue: €2,500,000. EBITDA: €320,000. Annual Debt Service: €250,000. Collateral Value: €400,000. Years in Business: 3. Tax Filings: verified.",
        "expected_status": "GRANTED",
        "expected_category": "APPROVED_STANDARD"
    },
    {
        "id": "CASE-03",
        "name": "Torino Precision Machining (Standard Pass - High DSCR, High LTV)",
        "text": "Applicant: Torino Machining. Loan Request: €600,000. Annual Revenue: €3,800,000. EBITDA: €650,000. Annual Debt Service: €400,000. Collateral: €780,000. Years in Business: 5. Tax Returns: verified.",
        "expected_status": "GRANTED",
        "expected_category": "APPROVED_STANDARD"
    },
    {
        "id": "CASE-04",
        "name": "Nova Tech Solutions (Young Company Denial)",
        "text": "Applicant: Nova Tech. Requested Amount: €200,000. Gross Revenue: €1,200,000. EBITDA: €250,000. Annual Debt Service: €150,000. Collateral: €350,000. Years in Business: 1. Tax Returns: verified.",
        "expected_status": "DENIED",
        "expected_category": "DENIED_CREDIT_POLICY"
    },
    {
        "id": "CASE-05",
        "name": "Beta Precision Tooling (Sub-1.15 DSCR Denial)",
        "text": "Applicant: Beta Tooling. Loan Request: €850,000. Annual Revenue: €2,100,000. EBITDA: €210,000. Debt Service: €200,000. Collateral: €900,000. Years in Business: 4. Tax Returns: verified.",
        "expected_status": "DENIED",
        "expected_category": "DENIED_CREDIT_POLICY"
    },
    {
        "id": "CASE-06",
        "name": "Piemonte Agro Distribution (High LTV Denial)",
        "text": "Applicant: Piemonte Agro. Facility Size: €900,000. Revenue: €3,000,000. EBITDA: €450,000. Debt Service: €300,000. Collateral: €1,000,000. Years in Business: 7. Tax Returns: verified.",
        "expected_status": "DENIED",
        "expected_category": "DENIED_CREDIT_POLICY"
    },
    {
        "id": "CASE-07",
        "name": "Vanchiglia Gastronomy (Severe Debt Overhang Denial)",
        "text": "Applicant: Vanchiglia Gastronomy. Loan Request: €400,000. Revenue: €800,000. EBITDA: €60,000. Debt Service: €90,000. Collateral: €420,000. Years in Business: 2. Tax Returns: verified.",
        "expected_status": "DENIED",
        "expected_category": "DENIED_CREDIT_POLICY"
    },
    {
        "id": "CASE-08",
        "name": "Gamma Biotech Labs (Missing Tax Filings - Abstain)",
        "text": "Applicant: Gamma Biotech Labs. Facility Size: €600,000. Revenue: €3,500,000. EBITDA: €550,000. Debt Service: €300,000. Collateral: €800,000. Years in Business: 2. Tax Filings: unverified.",
        "expected_status": "ABSTAIN",
        "expected_category": "ABSTAIN_DATA_INCOMPLETE"
    },
    {
        "id": "CASE-09",
        "name": "Moncalieri Logistics (Missing Debt Service - Abstain)",
        "text": "Applicant: Moncalieri Logistics. Requested Amount: €450,000. Annual Revenue: €2,800,000. EBITDA: €400,000. Collateral: €650,000. Years in Business: 4. Tax Filings: verified.",
        "expected_status": "ABSTAIN",
        "expected_category": "ABSTAIN_DATA_INCOMPLETE"
    },
    {
        "id": "CASE-10",
        "name": "Rivoli Clean Energy (Missing Collateral Valuation - Abstain)",
        "text": "Applicant: Rivoli Clean Energy. Requested Loan: €750,000. Annual Revenue: €4,100,000. EBITDA: €650,000. Annual Debt Service: €400,000. Years in Business: 5. Tax Returns: verified.",
        "expected_status": "ABSTAIN",
        "expected_category": "ABSTAIN_DATA_INCOMPLETE"
    }
]

def run_check_set() -> bool:
    print("=" * 80)
    print("CREDIT DMN DECISION PIPELINE — 10-CASE VERIFICATION CHECK SET")
    print("=" * 80)
    passed = 0
    total = len(CHECK_SET_CASES)

    for case in CHECK_SET_CASES:
        decision, _ = process_credit_application(case["text"], use_ai=False)
        status_match = (decision.status == case["expected_status"])
        cat_match = (decision.ruling_category == case["expected_category"])
        ok = status_match and cat_match

        mark = "[PASS]" if ok else "[FAIL]"
        if ok:
            passed += 1

        print(f"{mark} {case['id']}: {case['name']:<42} -> Got {decision.status} ({decision.ruling_category})")
        if not ok:
            print(f"      Expected: {case['expected_status']} ({case['expected_category']})")
            print(f"      Ratios: {decision.financial_ratios}")
            print(f"      Narrative: {decision.audit_narrative}")

    print("-" * 80)
    print(f"CHECK SET RESULT: {passed}/{total} passed ({passed/total*100:.1f}%)")
    print("=" * 80)
    return passed == total

if __name__ == "__main__":
    success = run_check_set()
    sys.exit(0 if success else 1)
