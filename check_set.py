"""
Check set: decision cases plus the properties the pitch claims
(abstain on missing data, same input gives the same decision, the DMN file is what runs).
Runs offline: python check_set.py
"""
import sys
import xml.etree.ElementTree as ET

from pipeline import process_credit_application, replay
from policy import BASE_RULES, STORE, dmn_to_rules, rules_to_dmn
from samples import SAMPLE_APPLICATIONS

BASE = "Applicant: {n}. Requested Amount: {req}. EBITDA: {e}. Annual Debt Service: {ds}. Collateral Value: {c}. Years in Business: {y}. Tax Filings: {t}."

CHECK_SET_CASES = [
    {"id": "CASE-01", "name": "Alpha Logistics (prime)", "expected_status": "GRANTED", "expected_category": "APPROVED_PRIME",
     "text": "Applicant: Alpha Logistics. Requested Amount: €500,000. Annual Revenue: €4,250,000. EBITDA: €720,000. Annual Debt Service: €380,000. Collateral Value: €950,000. Years in Business: 6. Tax Filings: verified."},
    {"id": "CASE-02", "name": "Delta Industrial (standard)", "expected_status": "GRANTED", "expected_category": "APPROVED_STANDARD",
     "text": "Applicant: Delta Industrial. Requested Amount: €300,000. Annual Revenue: €2,500,000. EBITDA: €320,000. Annual Debt Service: €250,000. Collateral Value: €400,000. Years in Business: 3. Tax Filings: verified."},
    {"id": "CASE-03", "name": "Torino Machining (standard, high LTV)", "expected_status": "GRANTED", "expected_category": "APPROVED_STANDARD",
     "text": "Applicant: Torino Machining. Loan Request: €600,000. Annual Revenue: €3,800,000. EBITDA: €650,000. Annual Debt Service: €400,000. Collateral: €780,000. Years in Business: 5. Tax Returns: verified."},
    {"id": "CASE-04", "name": "Nova Tech (1 year in business)", "expected_status": "DENIED", "expected_category": "DENIED_CREDIT_POLICY",
     "text": "Applicant: Nova Tech. Requested Amount: €200,000. Gross Revenue: €1,200,000. EBITDA: €250,000. Annual Debt Service: €150,000. Collateral: €350,000. Years in Business: 1. Tax Returns: verified."},
    {"id": "CASE-05", "name": "Beta Tooling (DSCR below 1.15)", "expected_status": "DENIED", "expected_category": "DENIED_CREDIT_POLICY",
     "text": "Applicant: Beta Tooling. Loan Request: €850,000. Annual Revenue: €2,100,000. EBITDA: €210,000. Debt Service: €200,000. Collateral: €900,000. Years in Business: 4. Tax Returns: verified."},
    {"id": "CASE-06", "name": "Piemonte Agro (LTV above 85%)", "expected_status": "DENIED", "expected_category": "DENIED_CREDIT_POLICY",
     "text": "Applicant: Piemonte Agro. Facility Size: €900,000. Revenue: €3,000,000. EBITDA: €450,000. Debt Service: €300,000. Collateral: €1,000,000. Years in Business: 7. Tax Returns: verified."},
    {"id": "CASE-07", "name": "Vanchiglia Gastronomy (DSCR 0.67)", "expected_status": "DENIED", "expected_category": "DENIED_CREDIT_POLICY",
     "text": "Applicant: Vanchiglia Gastronomy. Loan Request: €400,000. Revenue: €800,000. EBITDA: €60,000. Debt Service: €90,000. Collateral: €420,000. Years in Business: 2. Tax Returns: verified."},
    {"id": "CASE-08", "name": "Gamma Biotech (tax unverified)", "expected_status": "ABSTAIN", "expected_category": "ABSTAIN_DATA_INCOMPLETE",
     "text": "Applicant: Gamma Biotech Labs. Facility Size: €600,000. Revenue: €3,500,000. EBITDA: €550,000. Debt Service: €300,000. Collateral: €800,000. Years in Business: 2. Tax Filings: unverified."},
    {"id": "CASE-09", "name": "Moncalieri Logistics (no debt service)", "expected_status": "ABSTAIN", "expected_category": "ABSTAIN_DATA_INCOMPLETE",
     "text": "Applicant: Moncalieri Logistics. Requested Amount: €450,000. Annual Revenue: €2,800,000. EBITDA: €400,000. Collateral: €650,000. Years in Business: 4. Tax Filings: verified."},
    {"id": "CASE-10", "name": "Rivoli Clean Energy (no collateral value)", "expected_status": "ABSTAIN", "expected_category": "ABSTAIN_DATA_INCOMPLETE",
     "text": "Applicant: Rivoli Clean Energy. Requested Loan: €750,000. Annual Revenue: €4,100,000. EBITDA: €650,000. Annual Debt Service: €400,000. Years in Business: 5. Tax Returns: verified."},
    # Edge cases the first version got wrong
    {"id": "CASE-11", "name": "Negative EBITDA must not be read as positive", "expected_status": "DENIED", "expected_category": "DENIED_CREDIT_POLICY",
     "text": "Applicant: Loss Maker Srl. Requested Amount: €500,000. EBITDA of -€720,000. Annual Debt Service: €380,000. Collateral Value: €950,000. Years in Business: 6. Tax Filings: verified."},
    {"id": "CASE-12", "name": "Years in business missing: abstain, not deny", "expected_status": "ABSTAIN", "expected_category": "ABSTAIN_DATA_INCOMPLETE",
     "text": "Applicant: No History Stated. Requested Amount: €500,000. EBITDA: €720,000. Annual Debt Service: €380,000. Collateral Value: €950,000. Tax Filings: verified."},
    {"id": "CASE-13", "name": "Italian number format, mixed with k", "expected_status": "GRANTED", "expected_category": "APPROVED_PRIME",
     "text": BASE.format(n="Formato Italiano SpA", req="€500.000,00", e="720k", ds="€380.000", c="€950.000,00", y=6, t="verified")},
    {"id": "CASE-14", "name": "DSCR 1.17, between deny and grant: refer", "expected_status": "ABSTAIN", "expected_category": "REFER_UNCOVERED_CASE",
     "text": BASE.format(n="Gap Band Srl", req="€500,000", e="€117,000", ds="€100,000", c="€950,000", y=6, t="verified")},
    {"id": "CASE-15", "name": "Collateral given only as unverified book value", "expected_status": "ABSTAIN", "expected_category": "ABSTAIN_DATA_INCOMPLETE",
     "text": "Applicant: Hedged Srl. Requested Amount: €500,000. EBITDA: €720,000. Annual Debt Service: €380,000. Collateral Value: [appraisal pending - unverified book value €950k]. Years in Business: 6. Tax Filings: verified."},
    {"id": "CASE-16", "name": "Tax status not mentioned at all", "expected_status": "ABSTAIN", "expected_category": "ABSTAIN_DATA_INCOMPLETE",
     "text": "Applicant: Silent Srl. Requested Amount: €500,000. EBITDA: €720,000. Annual Debt Service: €380,000. Collateral Value: €950,000. Years in Business: 6."},
] + [
    {"id": f"DEMO-{i + 1}", "name": f"Demo preset: {s['title']}", "expected_status": s["expected_ruling"],
     "expected_category": s["expected_category"], "text": s["raw_text"]}
    for i, s in enumerate(SAMPLE_APPLICATIONS.values())
]


def run_cases():
    results = []
    for case in CHECK_SET_CASES:
        rec = process_credit_application(case["text"], use_ai=False, persist=False)
        got = rec["outcome"]
        results.append({"id": case["id"], "name": case["name"],
                        "expected_status": case["expected_status"], "expected_category": case["expected_category"],
                        "got_status": got["status"], "got_category": got["category"], "rule_id": rec["rule"]["id"],
                        "pass": got["status"] == case["expected_status"] and got["category"] == case["expected_category"]})
    return results


def run_properties():
    """Claims made in the pitch, checked on a private policy store so the live policy is untouched."""
    from policy import PolicyStore, decide
    props = []
    xml = rules_to_dmn(BASE_RULES)
    ET.fromstring(xml.encode("utf-8"))
    props.append(("The .dmn file is well-formed and parses back to the same rules", dmn_to_rules(xml) == BASE_RULES))

    text = CHECK_SET_CASES[1]["text"]
    a = process_credit_application(text, use_ai=False)
    b = process_credit_application(text, use_ai=False)
    props.append(("Same input and policy give the same decision and the same record id",
                  a["record_id"] == b["record_id"] and a["outcome"] == b["outcome"]))
    props.append(("Replay of a stored record reproduces it exactly", replay(a["record_id"])["same_policy"]["identical"]))

    store = PolicyStore()
    values = {n: f["value"] for n, f in a["inputs"].items()}
    before = decide(values, store.current())
    v2 = store.edit("R6_Standard", "dscr", ">= 1.30")
    after = decide(values, v2)
    props.append(("Editing one rule changes the policy version and the outcome of an affected case",
                  v2["sha"] != store.versions[0]["sha"] and before["outcome"]["status"] == "GRANTED" and after["outcome"]["status"] != "GRANTED"))
    props.append(("The old policy version still gives the old outcome", decide(values, store.versions[0])["outcome"] == before["outcome"]))

    denied = process_credit_application(CHECK_SET_CASES[4]["text"], use_ai=False, persist=False)
    cf = denied["counterfactual"]
    props.append(("A denial comes with a counterfactual that the engine confirms by re-running", bool(cf and cf["confirmed_by_rerun"])))
    return [{"name": n, "pass": bool(ok)} for n, ok in props]


def main() -> bool:
    if STORE.current()["sha"] != STORE.versions[0]["sha"]:
        STORE.reset()
    cases, props = run_cases(), run_properties()
    print("=" * 92)
    print("CREDIT POLICY CHECK SET")
    print("=" * 92)
    for r in cases:
        print(f"{'[PASS]' if r['pass'] else '[FAIL]'} {r['id']}: {r['name'][:50]:<50} -> {r['got_status']} ({r['got_category']}) via {r['rule_id']}")
        if not r["pass"]:
            print(f"       expected {r['expected_status']} ({r['expected_category']})")
    print("-" * 92)
    for p in props:
        print(f"{'[PASS]' if p['pass'] else '[FAIL]'} {p['name']}")
    ok_cases, ok_props = sum(r["pass"] for r in cases), sum(p["pass"] for p in props)
    print("-" * 92)
    print(f"CASES: {ok_cases}/{len(cases)} passed · PROPERTIES: {ok_props}/{len(props)} passed")
    return ok_cases == len(cases) and ok_props == len(props)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if main() else 1)
