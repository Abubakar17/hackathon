"""
Realistic messy credit application packets for demo and check sets.
"""

SAMPLE_APPLICATIONS = {
    "alpha_logistics": {
        "title": "Alpha Logistics Corp (Prime Tier - Clean Pass)",
        "expected_ruling": "GRANTED",
        "expected_category": "APPROVED_PRIME",
        "raw_text": """
COMMERCIAL CREDIT APPLICATION & UNDERWRITING MEMORANDUM
Date: November 12, 2026
Applicant Entity: Alpha Logistics SpA
Headquarters: Corso Francia 140, Turin, Italy
Facility Request: €500,000 Senior Secured Term Loan
Purpose: Fleet electrification and acquisition of 8 commercial EV vans.

COMPANY OVERVIEW:
Alpha Logistics is a regional cold-chain distribution provider operating in Northern Italy.
Operating History: 6 years in business (incorporated 2020).
Credit Score: AAA equivalent internal risk rating.

FINANCIAL SUMMARY (FY 2025 Audited):
- Gross Revenue: €4,250,000 EUR
- Operating Profit / EBITDA: €720,000 EUR
- Existing Annual Debt Service (P&I): €380,000 EUR
- Total Existing Liabilities: €1,100,000 EUR

COLLATERAL & SECURITY:
Primary security offered: Freehold commercial distribution warehouse in Rivoli (Turin).
Independent RICS Real Estate Appraisal: €950,000 EUR.

COMPLIANCE & TAX RECORDS:
Tax Filings: verified and audited by PwC Italy. All fiscal declarations compliant through Q3 2026.
        """
    },

    "beta_precision": {
        "title": "Beta Precision Tooling (High Risk - Clean Denial)",
        "expected_ruling": "DENIED",
        "expected_category": "DENIED_CREDIT_POLICY",
        "raw_text": """
COMMERCIAL CREDIT APPLICATION & UNDERWRITING MEMORANDUM
Date: November 10, 2026
Applicant Entity: Beta Precision Tooling Srl
Headquarters: Via Bologna 88, Turin, Italy
Loan Request: €850,000 EUR
Purpose: Procurement of 5-axis CNC machining centers.

COMPANY OVERVIEW:
Subcontracted automotive parts manufacturer. Experiencing margin compression.
Years in Business: 4 years.

FINANCIAL SUMMARY (FY 2025 Stated):
- Annual Revenue: €2,100,000 EUR
- EBITDA: €210,000 EUR (down 18% YoY)
- Existing Annual Debt Service: €200,000 EUR
- Total Liabilities: €1,650,000 EUR (Highly leveraged)

COLLATERAL & SECURITY:
Offered collateral: Used industrial milling machinery.
Estimated Collateral Value: €900,000 EUR (Subject to high depreciation).

COMPLIANCE & TAX RECORDS:
Tax Returns: verified and current.
        """
    },

    "gamma_biotech": {
        "title": "Gamma Biotech Labs (Incomplete - Deterministic Abstain)",
        "expected_ruling": "ABSTAIN",
        "expected_category": "ABSTAIN_DATA_INCOMPLETE",
        "raw_text": """
COMMERCIAL CREDIT APPLICATION & UNDERWRITING MEMORANDUM
Date: November 14, 2026
Applicant: Gamma Biotech Labs Srl
Facility Size: €600,000 EUR
Purpose: Laboratory equipment lease expansion.

COMPANY OVERVIEW:
Early-stage diagnostic diagnostics developer.
Years in Business: 2 years.

FINANCIAL HIGHLIGHTS:
- Gross Revenue: €3,500,000 EUR
- EBITDA: €550,000 EUR
- Annual Debt Service: [Pending debt restructuring with venture debt syndicate - exact P&I schedule not provided]
- Total Existing Debt: €400,000 EUR

COLLATERAL:
Offered security: Unencumbered scientific patents and lab fixtures.
Collateral Value: [Independent appraisal pending - unverified book value €450k]

TAX & REGULATORY STATUS:
Tax Filings: unverified draft provided; final audited 2025 declaration not yet submitted to Agenzia delle Entrate.
        """
    }
}
