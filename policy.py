"""
Credit policy as a DMN 1.3 decision table, and the engine that executes it.

The DMN XML is the single source of truth: rules are serialised to XML, and every
decision is taken by parsing that XML back and evaluating its rows (hit policy FIRST).
No language model is involved in this file.
"""
import hashlib
import math
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"
POLICY_NAME = "Commercial Credit Policy"
RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")

# (variable, label, FEEL type)
INPUTS = [
    ("dscr", "DSCR (EBITDA / annual debt service)", "number"),
    ("ltv", "LTV (requested amount / collateral value)", "number"),
    ("years_in_business", "Years in business", "number"),
    ("tax_returns_verified", "Tax returns verified", "boolean"),
]
INPUT_IDS = [i[0] for i in INPUTS]
OUTPUTS = [("status", "string"), ("category", "string"), ("apr", "number"), ("reason", "string")]

REQUIRED_FIELDS = [
    "requested_amount_eur", "ebitda_eur", "annual_debt_service_eur",
    "collateral_value_eur", "years_in_business", "tax_returns_verified",
]
FIELD_LABELS = {
    "requested_amount_eur": "requested amount",
    "ebitda_eur": "EBITDA",
    "annual_debt_service_eur": "annual debt service",
    "collateral_value_eur": "collateral value",
    "years_in_business": "years in business",
    "tax_returns_verified": "tax return verification",
    "annual_revenue_eur": "annual revenue",
    "total_existing_debt_eur": "total existing debt",
}


def _rule(rid, label, tests, status, category, apr, reason):
    return {"id": rid, "label": label, "tests": dict(zip(INPUT_IDS, tests)),
            "out": {"status": status, "category": category, "apr": apr, "reason": reason}}


BASE_RULES = [
    _rule("R1_TaxUnverified", "Tax returns not verified", ["-", "-", "-", "false"],
          "ABSTAIN", "ABSTAIN_DATA_INCOMPLETE", None,
          "Tax returns are stated as not verified; a credit officer must review the case"),
    _rule("R2_LowDSCR", "Debt service coverage below floor", ["< 1.15", "-", "-", "-"],
          "DENIED", "DENIED_CREDIT_POLICY", None,
          "Debt service coverage ratio is below the minimum of 1.15"),
    _rule("R3_HighLTV", "Loan-to-value above ceiling", ["-", "> 0.85", "-", "-"],
          "DENIED", "DENIED_CREDIT_POLICY", None,
          "Loan-to-value is above the maximum of 85%"),
    _rule("R4_ShortHistory", "Operating history too short", ["-", "-", "< 2", "-"],
          "DENIED", "DENIED_CREDIT_POLICY", None,
          "Fewer than 2 years in business"),
    _rule("R5_Prime", "Prime tier", [">= 1.35", "<= 0.70", ">= 3", "true"],
          "GRANTED", "APPROVED_PRIME", 5.5,
          "Prime tier: strong debt coverage and conservative loan-to-value"),
    _rule("R6_Standard", "Standard tier", [">= 1.20", "<= 0.80", ">= 2", "true"],
          "GRANTED", "APPROVED_STANDARD", 7.2,
          "Standard tier: coverage and loan-to-value within policy limits"),
    _rule("R7_Uncovered", "No rule covers the case", ["-", "-", "-", "-"],
          "ABSTAIN", "REFER_UNCOVERED_CASE", None,
          "The case falls between the policy's grant and denial rules; a credit officer decides"),
]

_TEST_RE = re.compile(r"(>=|<=|<|>)\s*(-?\d+(?:\.\d+)?)")


# ---------------------------------------------------------------- DMN XML

def rules_to_dmn(rules: List[Dict[str, Any]]) -> str:
    def lit(v):
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return repr(v)
        return '"' + str(v).replace('"', "'") + '"'

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<definitions xmlns="{DMN_NS}" id="Definitions_CreditPolicy" name="{escape(POLICY_NAME)}"',
           '             namespace="https://example.org/dmn/credit-policy">',
           '  <decision id="Decision_CreditRuling" name="Credit ruling">',
           '    <decisionTable id="DecisionTable_CreditPolicy" hitPolicy="FIRST">']
    for var, label, typ in INPUTS:
        out += [f'      <input id="Input_{var}" label="{escape(label)}">',
                f'        <inputExpression id="InputExpr_{var}" typeRef="{typ}"><text>{var}</text></inputExpression>',
                '      </input>']
    for name, typ in OUTPUTS:
        out.append(f'      <output id="Output_{name}" name="{name}" label="{name}" typeRef="{typ}" />')
    for r in rules:
        out.append(f'      <rule id="{escape(r["id"])}">')
        out.append(f'        <description>{escape(r["label"])}</description>')
        for var in INPUT_IDS:
            out.append(f'        <inputEntry id="{r["id"]}_in_{var}"><text>{escape(r["tests"][var])}</text></inputEntry>')
        for name, _ in OUTPUTS:
            out.append(f'        <outputEntry id="{r["id"]}_out_{name}"><text>{escape(lit(r["out"][name]))}</text></outputEntry>')
        out.append('      </rule>')
    out += ['    </decisionTable>', '  </decision>', '</definitions>']
    return "\n".join(out)


def dmn_to_rules(xml: str) -> List[Dict[str, Any]]:
    """Parse a DMN decision table back into executable rules."""
    q = lambda tag: f"{{{DMN_NS}}}{tag}"
    table = ET.fromstring(xml.encode("utf-8")).find(f".//{q('decisionTable')}")
    if table is None or table.get("hitPolicy") != "FIRST":
        raise ValueError("Expected one decisionTable with hitPolicy FIRST")
    in_vars = [i.find(f"{q('inputExpression')}/{q('text')}").text.strip() for i in table.findall(q("input"))]
    out_names = [o.get("name") for o in table.findall(q("output"))]

    def unlit(t):
        t = (t or "").strip()
        if t == "null" or t == "":
            return None
        if t.startswith('"') and t.endswith('"'):
            return t[1:-1]
        return float(t)

    rules = []
    for r in table.findall(q("rule")):
        desc = r.find(q("description"))
        tests = [(e.find(q("text")).text or "-").strip() for e in r.findall(q("inputEntry"))]
        outs = [unlit(e.find(q("text")).text) for e in r.findall(q("outputEntry"))]
        rules.append({"id": r.get("id"), "label": desc.text if desc is not None else r.get("id"),
                      "tests": dict(zip(in_vars, tests)), "out": dict(zip(out_names, outs))})
    return rules


# ---------------------------------------------------------------- engine

def valid_test(var: str, test: str) -> bool:
    test = test.strip()
    if test == "-":
        return True
    if var == "tax_returns_verified":
        return test in ("true", "false")
    return bool(_TEST_RE.fullmatch(test))


def eval_test(test: str, value: Any) -> bool:
    test = test.strip()
    if test == "-":
        return True
    if value is None:
        return False
    if test in ("true", "false"):
        return bool(value) == (test == "true")
    m = _TEST_RE.fullmatch(test)
    if not m:
        raise ValueError(f"Unsupported unary test: {test}")
    op, num = m.group(1), float(m.group(2))
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return {">=": value >= num, "<=": value <= num, "<": value < num, ">": value > num}[op]


def evaluate_table(rules: List[Dict[str, Any]], values: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Hit policy FIRST. Returns the rule that fired and the trace of every row checked before it."""
    trace = []
    for r in rules:
        checks = [{"input": v, "test": r["tests"][v], "actual": values.get(v), "ok": eval_test(r["tests"][v], values.get(v))}
                  for v in INPUT_IDS]
        matched = all(c["ok"] for c in checks)
        trace.append({"rule_id": r["id"], "matched": matched, "checks": checks})
        if matched:
            return r, trace
    raise ValueError("No rule matched and the table has no default row")


def derive(values: Dict[str, Any]) -> Dict[str, Any]:
    e, ds = values.get("ebitda_eur"), values.get("annual_debt_service_eur")
    req, col = values.get("requested_amount_eur"), values.get("collateral_value_eur")
    debt = values.get("total_existing_debt_eur")
    return {
        "dscr": round(e / ds, 4) if e is not None and ds else None,
        "ltv": round(req / col, 4) if req is not None and col else None,
        "debt_to_ebitda": round(debt / e, 4) if debt is not None and e and e > 0 else None,
    }


def eur(x) -> str:
    return f"€{x:,.0f}"


def _test_words(var: str, test: str) -> str:
    if var == "tax_returns_verified":
        return "tax returns are verified" if test == "true" else "tax returns are not verified"
    m = _TEST_RE.fullmatch(test.strip())
    op = {">=": "at least", "<=": "at most", "<": "below", ">": "above"}[m.group(1)]
    num = float(m.group(2))
    if var == "ltv":
        return f"loan-to-value is {op} {num * 100:g}%"
    if var == "dscr":
        return f"debt service coverage (DSCR) is {op} {num:g}"
    return f"years in business is {op} {num:g}"


def _figures(values, d) -> str:
    return (f"DSCR {d['dscr']:.2f} (EBITDA {eur(values['ebitda_eur'])} ÷ annual debt service {eur(values['annual_debt_service_eur'])}); "
            f"loan-to-value {d['ltv'] * 100:.1f}% (requested {eur(values['requested_amount_eur'])} ÷ collateral {eur(values['collateral_value_eur'])}); "
            f"{values['years_in_business']:g} years in business; "
            f"tax returns {'verified' if values['tax_returns_verified'] else 'not verified'}.")


def _counterfactual(values, rules, fired) -> Optional[Dict[str, Any]]:
    """Smallest change to the applicant's figures that reaches a grant rule, confirmed by re-running the table."""
    d = derive(values)
    table_in = {**d, "years_in_business": values["years_in_business"], "tax_returns_verified": values["tax_returns_verified"]}
    best = None
    for r in rules:
        if r["out"]["status"] != "GRANTED":
            continue
        unmet = [v for v in INPUT_IDS if not eval_test(r["tests"][v], table_in[v])]
        if best is None or len(unmet) <= len(best[1]):
            best = (r, unmet)
    if best is None or not best[1]:
        return None
    target, unmet = best
    new, changes = dict(values), []
    for v in unmet:
        test = target["tests"][v]
        if v == "tax_returns_verified":
            new[v] = True
            changes.append("tax returns were verified")
            continue
        num = float(_TEST_RE.fullmatch(test.strip()).group(2))
        if v == "dscr":
            need = math.ceil(num * values["annual_debt_service_eur"])
            new["ebitda_eur"] = need
            changes.append(f"EBITDA were at least {eur(need)} instead of {eur(values['ebitda_eur'])} (DSCR ≥ {num:g})")
        elif v == "ltv":
            cap = math.floor(num * values["collateral_value_eur"])
            new["requested_amount_eur"] = cap
            changes.append(f"the requested amount were at most {eur(cap)} instead of {eur(values['requested_amount_eur'])} (loan-to-value ≤ {num * 100:g}%)")
        elif v == "years_in_business":
            new[v] = num
            changes.append(f"the company had {num:g} years in business instead of {values[v]:g}")
    nd = derive(new)
    rerun, _ = evaluate_table(rules, {**nd, "years_in_business": new["years_in_business"], "tax_returns_verified": new["tax_returns_verified"]})
    ok = rerun["out"]["status"] == "GRANTED"
    apr = rerun["out"]["apr"]
    text = "If " + ", and ".join(changes) + (
        f", the application would be granted at {apr:g}% APR under rule {rerun['id']}." if ok
        else f", rule {rerun['id']} would apply instead ({rerun['out']['status']}).")
    return {"text": text, "changed_inputs": {k: new[k] for k in new if new[k] != values.get(k)},
            "resulting_rule": rerun["id"], "resulting_status": rerun["out"]["status"], "confirmed_by_rerun": ok}


def decide(values: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    """Pure function of (inputs, policy version): the same pair always returns the same result."""
    rules = dmn_to_rules(policy["xml"])  # the engine executes the DMN file itself
    d = derive(values)
    pol = {"name": POLICY_NAME, "version": policy["version"], "sha256": policy["sha"]}

    missing = [f for f in REQUIRED_FIELDS if values.get(f) is None]
    if not missing and d["dscr"] is None:
        missing.append("annual_debt_service_eur (zero, so DSCR is undefined)")
    if not missing and d["ltv"] is None:
        missing.append("collateral_value_eur (zero, so LTV is undefined)")
    if missing:
        names = ", ".join(FIELD_LABELS.get(m, m) for m in missing)
        return {
            "outcome": {"status": "ABSTAIN", "category": "ABSTAIN_DATA_INCOMPLETE", "apr": None,
                        "reason": f"Required inputs missing or flagged as unverified: {names}"},
            "rule": {"id": "GATE_INPUT_COMPLETENESS", "label": "Input completeness gate (runs before the decision table)", "tests": {}},
            "policy": pol, "derived": d, "missing": missing, "trace": [],
            "explanation": (f"No automated decision was taken. The documents did not give, or gave only as pending or unverified: {names}. "
                            "Nothing was assumed in its place; the case goes to a credit officer."),
            "counterfactual": None,
        }

    table_in = {**d, "years_in_business": values["years_in_business"], "tax_returns_verified": values["tax_returns_verified"]}
    fired, trace = evaluate_table(rules, table_in)
    conds = [_test_words(v, fired["tests"][v]) for v in INPUT_IDS if fired["tests"][v].strip() != "-"]
    when = " and ".join(conds) if conds else "no earlier rule of the policy matches"
    verdict = {"GRANTED": f"Granted at {fired['out']['apr']:g}% APR" if fired["out"]["apr"] is not None else "Granted",
               "DENIED": "Declined", "ABSTAIN": "No automated decision; referred to a credit officer"}[fired["out"]["status"]]
    explanation = (f"{verdict}. Rule applied: {fired['id']} ({fired['label']}), policy version {policy['version']} [{policy['sha']}]. "
                   f"This rule applies when {when}. Figures used: {_figures(values, d)}")
    return {
        "outcome": dict(fired["out"]),
        "rule": {"id": fired["id"], "label": fired["label"], "tests": fired["tests"]},
        "policy": pol, "derived": d, "missing": [], "trace": trace,
        "explanation": explanation,
        "counterfactual": _counterfactual(values, rules, fired) if fired["out"]["status"] != "GRANTED" else None,
    }


# ---------------------------------------------------------------- versions

class PolicyStore:
    """Every edit creates a new immutable version; old versions stay executable for replay."""

    def __init__(self):
        self.versions: List[Dict[str, Any]] = []
        self.by_sha: Dict[str, Dict[str, Any]] = {}
        self._add(BASE_RULES, "Initial policy")

    def _add(self, rules, note):
        xml = rules_to_dmn(rules)
        sha = hashlib.sha256(xml.encode("utf-8")).hexdigest()[:12]
        v = {"version": len(self.versions) + 1, "sha": sha, "xml": xml, "rules": dmn_to_rules(xml),
             "note": note, "created_at": datetime.now().isoformat(timespec="seconds")}
        self.versions.append(v)
        self.by_sha[sha] = v
        try:
            os.makedirs(os.path.join(RUNS_DIR, "policies"), exist_ok=True)
            with open(os.path.join(RUNS_DIR, "policies", f"{sha}.dmn"), "w", encoding="utf-8") as f:
                f.write(xml)
        except OSError:
            pass
        return v

    def current(self) -> Dict[str, Any]:
        return self.versions[-1]

    def get(self, sha: str) -> Optional[Dict[str, Any]]:
        if sha in self.by_sha:
            return self.by_sha[sha]
        path = os.path.join(RUNS_DIR, "policies", f"{sha}.dmn")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                xml = f.read()
            v = {"version": "archived", "sha": sha, "xml": xml, "rules": dmn_to_rules(xml), "note": "Loaded from disk", "created_at": None}
            self.by_sha[sha] = v
            return v
        return None

    def edit(self, rule_id: str, var: str, test: str) -> Dict[str, Any]:
        test = " ".join(test.split())
        if var not in INPUT_IDS or not valid_test(var, test):
            raise ValueError(f"'{test}' is not a valid test for {var}. Use -, true/false, or a comparison such as >= 1.25")
        rules = [dict(r, tests=dict(r["tests"]), out=dict(r["out"])) for r in self.current()["rules"]]
        target = next((r for r in rules if r["id"] == rule_id), None)
        if target is None:
            raise ValueError(f"Unknown rule {rule_id}")
        old = target["tests"][var]
        if old == test:
            return self.current()
        target["tests"][var] = test
        return self._add(rules, f"{rule_id}: {var} changed from '{old}' to '{test}'")

    def reset(self) -> Dict[str, Any]:
        if self.current()["sha"] != self.versions[0]["sha"]:
            self._add(BASE_RULES, "Reset to initial policy")
        return self.current()

    def public(self) -> Dict[str, Any]:
        c = self.current()
        return {"name": POLICY_NAME, "version": c["version"], "sha": c["sha"], "rules": c["rules"], "note": c["note"],
                "inputs": [{"id": i, "label": l} for i, l, _ in INPUTS],
                "history": [{"version": v["version"], "sha": v["sha"], "note": v["note"], "created_at": v["created_at"]} for v in self.versions]}


STORE = PolicyStore()
