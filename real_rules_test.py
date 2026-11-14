"""
Side test: does the pipeline run on a published, real rule set?

Rule set: Fannie Mae Eligibility Matrix, "Standard Eligibility Requirements - Manual Underwriting",
principal residence, purchase / limited cash-out refinance, 1 unit, fixed rate.
  https://singlefamily.fanniemae.com/media/document/pdf/eligibility-matrix-current   (read 2026-11-14)
  Maximum DTI and minimum score: Selling Guide B3-6-02 and B3-5.1-01.

Only the zero-reserve tier of that row is encoded. The matrix also allows lower scores when the
borrower holds 2 or 6 months of reserves; those cases land on the default row and go to a person.

The applications below are test documents with invented borrowers. Real filled-in loan
applications are private and are not published anywhere we could lawfully use.

Run: python real_rules_test.py        (needs the AI gateway key; there is no offline extractor for these fields)
"""
import json
import os
import sys

from ai_analyst import extract
from policy import dmn_to_rules, evaluate_table, rules_to_dmn

SOURCE = "Fannie Mae Eligibility Matrix, manual underwriting, principal residence, purchase, 1 unit (zero-reserve tier)"

INPUTS = [
    ("ltv_pct", "LTV % (loan amount / property value)", "number"),
    ("dti_pct", "DTI % (total monthly debt payments / gross monthly income)", "number"),
    ("credit_score", "Representative credit score", "number"),
]
IDS = [i[0] for i in INPUTS]


def rule(rid, label, tests, status, category, reason):
    return {"id": rid, "label": label, "tests": dict(zip(IDS, tests)),
            "out": {"status": status, "category": category, "apr": None, "reason": reason}}


RULES = [
    rule("FM1_LTVOverMax", "LTV above the 95% maximum", ["> 95", "-", "-"], "DENIED", "INELIGIBLE", "LTV exceeds the 95% maximum for this transaction type"),
    rule("FM2_DTIOverMax", "DTI above the 45% maximum", ["-", "> 45", "-"], "DENIED", "INELIGIBLE", "DTI exceeds the 45% maximum for manually underwritten loans (B3-6-02)"),
    rule("FM3_ScoreUnderMin", "Credit score below 620", ["-", "-", "< 620"], "DENIED", "INELIGIBLE", "Credit score is below the 620 minimum for fixed-rate loans (B3-5.1-01)"),
    rule("FM4_DTI36_LTV75", "DTI up to 36%, LTV up to 75%, score 640+", ["<= 75", "<= 36", ">= 640"], "GRANTED", "ELIGIBLE", "Meets the matrix: DTI ≤ 36%, LTV ≤ 75%, score ≥ 640, no reserves required"),
    rule("FM5_DTI36_LTV95", "DTI up to 36%, LTV above 75%, score 680+", ["-", "<= 36", ">= 680"], "GRANTED", "ELIGIBLE", "Meets the matrix: DTI ≤ 36%, LTV > 75%, score ≥ 680, no reserves required"),
    rule("FM6_DTI45_LTV75", "DTI up to 45%, LTV up to 75%, score 680+", ["<= 75", "-", ">= 680"], "GRANTED", "ELIGIBLE", "Meets the matrix: DTI ≤ 45%, LTV ≤ 75%, score ≥ 680, no reserves required"),
    rule("FM7_DTI45_LTV95", "DTI up to 45%, LTV above 75%, score 720+", ["-", "-", ">= 720"], "GRANTED", "ELIGIBLE", "Meets the matrix: DTI ≤ 45%, LTV > 75%, score ≥ 720, no reserves required"),
    rule("FM8_Uncovered", "Zero-reserve tier not met", ["-", "-", "-"], "ABSTAIN", "REFER_UNCOVERED_CASE", "Does not meet the zero-reserve tier; may qualify with reserves, which this table does not encode"),
]

FIELDS = [
    ("loan_amount", "number", "mortgage loan amount requested"),
    ("property_value", "number", "appraised value of the property (use the appraisal, not the asking price)"),
    ("gross_monthly_income", "number", "borrower's total gross monthly income"),
    ("proposed_housing_payment", "number", "proposed total monthly housing payment (principal, interest, taxes, insurance)"),
    ("other_monthly_debts", "number", "total of all other monthly debt payments, only if the document states the total"),
    ("credit_score", "int", "representative credit score from the credit report"),
]

APPLICATIONS = [
    {"id": "FM-A", "expect": ("GRANTED", "FM5_DTI36_LTV95"), "note": "LTV 95%, DTI 34.2%, score 742", "text": """
UNIFORM RESIDENTIAL LOAN APPLICATION - summary sheet
Borrower: Maria Okafor            Occupancy: Primary residence     Property: single-family, 1 unit
Loan purpose: Purchase            Amortization: 30-year fixed rate
Section 4a. Loan amount: $380,000
Appraised value (appraisal dated 10/28/2026): $400,000
Section 1e. Total gross monthly income: $9,500
Section 2c. Liabilities - total other monthly payments: $600
Proposed monthly housing payment (PITI): $2,650
Credit report (tri-merge, 11/02/2026) representative score: 742
"""},
    {"id": "FM-B", "expect": ("ABSTAIN", "FM8_Uncovered"), "note": "LTV 71.3%, DTI 43.3%, score 665: needs reserves", "text": """
Loan file notes - purchase, primary residence, 1-unit condo, fixed rate
Applicant: Daniel Reyes
Loan amount: $285,000. Appraised value: $400,000.
Income (W-2, verified): gross monthly income $6,000
Proposed housing payment incl. taxes, insurance and HOA: $1,950 per month
Total other monthly debt payments: $650
Representative credit score: 665
"""},
    {"id": "FM-C", "expect": ("DENIED", "FM1_LTVOverMax"), "note": "LTV 98%", "text": """
From: loan officer
Subject: New purchase file - Priya Nair - primary residence, single unit, 30yr fixed

Hi, sending this one over for underwriting.
Loan amount: $392,000
Appraised value: $400,000 (asking price was $405,000)
Gross monthly income: $11,200
Proposed monthly housing payment: $2,900
Total other monthly debts: $450
Credit score (representative): 760
"""},
    {"id": "FM-D", "expect": ("DENIED", "FM2_DTIOverMax"), "note": "LTV 75%, DTI 49%, score 700", "text": """
Application summary - Tomasz Lewandowski - purchase, owner-occupied, 1 unit, fixed
Loan amount 300,000 USD | Appraised value 400,000 USD
Gross monthly income 5,000 USD
Proposed housing payment 2,000 USD per month
Total other monthly debts 450 USD
Representative credit score 700
"""},
    {"id": "FM-E", "expect": ("ABSTAIN", "GATE_INPUT_COMPLETENESS"), "note": "credit score not yet available", "text": """
Application summary - Aisha Bello - purchase, primary residence, 1 unit, fixed rate
Loan amount: $250,000
Appraised value: $330,000
Gross monthly income: $7,000
Proposed monthly housing payment: $1,800
Total other monthly debts: $300
Credit score: [credit report pending - not provided]
"""},
    {"id": "FM-F", "expect": ("GRANTED", "FM4_DTI36_LTV75"), "note": "LTV 75%, DTI 31.2%, score 652, messy formats", "text": """
hey - quick one for pre-review. Borrower is Luca Ferri, buying a single family home to live in, fixed rate.
He wants a loan amount of $240k, the appraised value came back at $320,000.
gross monthly income is $7,400 (two paystubs + employer letter in the folder)
proposed housing payment: $1,720 / month all in
total other monthly debts: $590 (car + student loan)
representative credit score 652
"""},
]


def decide(values, rules):
    missing = [name for name, _, _ in FIELDS if values.get(name) is None]
    if missing:
        return {"status": "ABSTAIN", "rule": "GATE_INPUT_COMPLETENESS", "reason": "Missing: " + ", ".join(missing), "derived": {}}
    derived = {
        "ltv_pct": round(100 * values["loan_amount"] / values["property_value"], 2),
        "dti_pct": round(100 * (values["proposed_housing_payment"] + values["other_monthly_debts"]) / values["gross_monthly_income"], 2),
        "credit_score": values["credit_score"],
    }
    fired, _ = evaluate_table(rules, derived)
    return {"status": fired["out"]["status"], "rule": fired["id"], "reason": fired["out"]["reason"], "derived": derived}


def main() -> bool:
    xml = rules_to_dmn(RULES, inputs=INPUTS, name=SOURCE)
    rules = dmn_to_rules(xml)  # decide from the DMN file, as the main pipeline does
    os.makedirs("real_test", exist_ok=True)
    with open(os.path.join("real_test", "fannie_mae_eligibility.dmn"), "w", encoding="utf-8", newline="\n") as f:
        f.write(xml + "\n")

    results, passed = [], 0
    print(f"Rule set: {SOURCE}\n")
    for app in APPLICATIONS:
        ex = extract(app["text"], use_ai=True, fields=FIELDS)
        values = {n: f["value"] for n, f in ex["fields"].items()}
        r = decide(values, rules)
        ok = (r["status"], r["rule"]) == app["expect"]
        passed += ok
        print(f"{'[PASS]' if ok else '[FAIL]'} {app['id']} {ex['company_name'][:22]:<22} {r['status']:<8} {r['rule']:<24} {r['derived']}")
        print(f"       {r['reason']}")
        if not ok:
            print(f"       expected {app['expect']} ({app['note']}); extracted {values}; dropped {ex['dropped']}")
        results.append({"id": app["id"], "applicant": ex["company_name"], "inputs": ex["fields"], "dropped": ex["dropped"],
                        **r, "expected": list(app["expect"]), "pass": ok})
    with open(os.path.join("real_test", "results.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"rule_set": SOURCE, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\n{passed}/{len(APPLICATIONS)} applications decided as the published matrix requires")
    return passed == len(APPLICATIONS)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if main() else 1)
