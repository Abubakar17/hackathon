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
from xml.sax.saxutils import escape, quoteattr

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"
CITE_NS = "https://example.org/dmn/citation"
CITE_KEYS = ["source", "locator", "quote", "url", "note"]
POLICY_NAME = "Commercial Credit Policy"
RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")

# (variable, label, FEEL type)
INPUTS = [
    ("dscr", "DSCR (EBITDA / annual debt service)", "number"),
    ("ltv", "LTV (requested amount / collateral value)", "number"),
    ("years_in_business", "Years in business", "number"),
    ("tax_returns_verified", "Tax returns verified", "boolean"),
    ("equity_eur", "Net equity (€)", "number"),
    ("days_past_due", "Days past due", "number"),
    ("leverage", "Leverage ((existing debt + requested) / EBITDA)", "number"),
]
# Inputs the document may not give. A rule that tests one of them cannot fire without it,
# and the decision record lists it as "not checked".
OPTIONAL_INPUTS = {"equity_eur": "net equity", "days_past_due": "days past due",
                   "leverage": "total existing debt (needed for leverage)"}
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
    "equity_eur": "net equity",
    "days_past_due": "days past due",
}


def _cite(source, locator, quote, url, note):
    return {"source": source, "locator": locator, "quote": quote, "url": url, "note": note}


def _rule(rid, label, tests, status, category, apr, reason, citation=None):
    """tests is a dict of the inputs the rule looks at; every other input is '-' (any)."""
    return {"id": rid, "label": label, "tests": {v: tests.get(v, "-") for v in INPUT_IDS},
            "out": {"status": status, "category": category, "apr": apr, "reason": reason},
            "citation": citation}


# Public sources. Each quote was read in the document at the URL given; the note says how
# far the rule in this table departs from what the source actually covers.
_CRR_178 = _cite(
    "Regulation (EU) No 575/2013 (CRR), OJ L 176, 27.6.2013", "Article 178(1)(b)",
    "the obligor is past due more than 90 days on any material credit obligation to the institution",
    "https://www.legislation.gov.uk/eur/2013/575/article/178/adopted",
    "The article defines default towards the lending institution. Here it is applied to any past-due figure "
    "stated in the application, and the materiality threshold of Delegated Regulation (EU) 2018/171 is not tested. "
    "Quote read in the as-adopted text.")
_CNDCEC_URL = "https://www.dirittobancario.it/wp-content/uploads/sites/default/files/allegati/inidici_dallerta.pdf"
_CNDCEC_SRC = "CNDCEC, Gli indici dell'allerta ex art. 13, co. 2 Codice della Crisi e dell'Insolvenza (draft of 19 October 2019)"
_CNDCEC_EQUITY = _cite(
    _CNDCEC_SRC, "section 3.1, index (i)",
    "Sono indici che fanno ragionevolmente presumere la sussistenza di uno stato di crisi dell'impresa, i seguenti: i. patrimonio netto negativo",
    _CNDCEC_URL,
    "An Italian professional early-warning index, not a lending rule; the bank uses it as a ground for refusal. "
    "Its current legal status was not verified.")
_CNDCEC_DSCR = _cite(
    _CNDCEC_SRC, "section 3.1, index (ii)",
    "DSCR a sei mesi inferiore a 1",
    _CNDCEC_URL,
    "The source measures DSCR on forecast cash flows over the next six months. This table uses annual EBITDA "
    "over annual debt service as a proxy. Professional early-warning index; its current legal status was not verified.")
_ECB_URL = "https://www.bankingsupervision.europa.eu/ecb/pub/pdf/ssm.leveraged_transactions_guidance_201705.en.pdf"
_ECB_SRC = "ECB Banking Supervision, Guidance on leveraged transactions (May 2017)"
_ECB_NOTE = ("The guidance is addressed to significant banks and leaves out SMEs and exposures below €5 million; "
             "the bank borrows its threshold as a referral trigger. Total debt is taken as existing debt plus the "
             "requested amount; undrawn commitments are not captured.")
_ECB_6X = _cite(
    _ECB_SRC, "section 5",
    "For most industries, a leverage level in excess of 6.0 times Total Debt to EBITDA raises concerns.",
    _ECB_URL, _ECB_NOTE)
_ECB_4X = _cite(
    _ECB_SRC, "section 3, condition 1",
    "all types of loan or credit exposure where the borrower's post-financing level of leverage exceeds a Total Debt to EBITDA ratio of 4.0 times",
    _ECB_URL, _ECB_NOTE)

BASE_RULES = [
    _rule("R1_TaxUnverified", "Tax returns not verified", {"tax_returns_verified": "false"},
          "ABSTAIN", "ABSTAIN_DATA_INCOMPLETE", None,
          "Tax returns are stated as not verified; a credit officer must review the case"),
    _rule("C1_PastDue90", "More than 90 days past due", {"days_past_due": "> 90"},
          "DENIED", "DENIED_PAST_DUE_DEFAULT", None,
          "The applicant is more than 90 days past due on a credit obligation", _CRR_178),
    _rule("C2_NegativeEquity", "Negative net equity", {"equity_eur": "< 0"},
          "DENIED", "DENIED_CRISIS_INDICATOR", None,
          "Net equity is negative, which is a recognised indicator of a state of crisis", _CNDCEC_EQUITY),
    _rule("C3_DSCRBelowOne", "Debt service not covered", {"dscr": "< 1"},
          "DENIED", "DENIED_CRISIS_INDICATOR", None,
          "Debt service coverage ratio is below 1: earnings do not cover debt service", _CNDCEC_DSCR),
    _rule("R2_LowDSCR", "Debt service coverage below floor", {"dscr": "< 1.15"},
          "DENIED", "DENIED_CREDIT_POLICY", None,
          "Debt service coverage ratio is below the minimum of 1.15"),
    _rule("R3_HighLTV", "Loan-to-value above ceiling", {"ltv": "> 0.85"},
          "DENIED", "DENIED_CREDIT_POLICY", None,
          "Loan-to-value is above the maximum of 85%"),
    _rule("R4_ShortHistory", "Operating history too short", {"years_in_business": "< 2"},
          "DENIED", "DENIED_CREDIT_POLICY", None,
          "Fewer than 2 years in business"),
    _rule("C4_ExceptionalLeverage", "Leverage above 6 times EBITDA", {"leverage": "> 6"},
          "ABSTAIN", "REFER_EXCEPTIONAL_LEVERAGE", None,
          "Total debt after the new loan exceeds 6 times EBITDA; the case is escalated to a credit officer", _ECB_6X),
    _rule("C5_Leveraged", "Leveraged transaction", {"leverage": "> 4"},
          "ABSTAIN", "REFER_LEVERAGED_TRANSACTION", None,
          "Total debt after the new loan exceeds 4 times EBITDA; an independent risk review is required", _ECB_4X),
    _rule("R5_Prime", "Prime tier",
          {"dscr": ">= 1.35", "ltv": "<= 0.70", "years_in_business": ">= 3", "tax_returns_verified": "true"},
          "GRANTED", "APPROVED_PRIME", 5.5,
          "Prime tier: strong debt coverage and conservative loan-to-value"),
    _rule("R6_Standard", "Standard tier",
          {"dscr": ">= 1.20", "ltv": "<= 0.80", "years_in_business": ">= 2", "tax_returns_verified": "true"},
          "GRANTED", "APPROVED_STANDARD", 7.2,
          "Standard tier: coverage and loan-to-value within policy limits"),
    _rule("R7_Uncovered", "No rule covers the case", {},
          "ABSTAIN", "REFER_UNCOVERED_CASE", None,
          "The case falls between the policy's grant and denial rules; a credit officer decides"),
]
NO_CITATION_TEXT = "This rule is the bank's own credit policy; no external source is cited for its thresholds."

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
           f'             xmlns:cite="{CITE_NS}" namespace="https://example.org/dmn/credit-policy">',
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
        if r.get("citation"):
            attrs = " ".join(f"{k}={quoteattr(r['citation'][k])}" for k in CITE_KEYS)
            out.append(f'        <extensionElements><cite:citation {attrs} /></extensionElements>')
        for var in INPUT_IDS:
            out.append(f'        <inputEntry id="{r["id"]}_in_{var}"><text>{escape(r["tests"].get(var, "-"))}</text></inputEntry>')
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
        cite = r.find(f"{q('extensionElements')}/{{{CITE_NS}}}citation")
        rules.append({"id": r.get("id"), "label": desc.text if desc is not None else r.get("id"),
                      "tests": dict(zip(in_vars, tests)), "out": dict(zip(out_names, outs)),
                      "citation": {k: cite.get(k, "") for k in CITE_KEYS} if cite is not None else None})
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
    for r in rules:  # a policy version saved before an input existed simply does not test it
        checks = [{"input": v, "test": r["tests"].get(v, "-"), "actual": values.get(v),
                   "ok": eval_test(r["tests"].get(v, "-"), values.get(v))}
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
        # post-financing leverage: the new loan counts as debt
        "leverage": round((debt + req) / e, 4) if debt is not None and req is not None and e and e > 0 else None,
    }


def table_inputs(values: Dict[str, Any], d: Dict[str, Any]) -> Dict[str, Any]:
    return {"dscr": d["dscr"], "ltv": d["ltv"], "leverage": d["leverage"],
            "years_in_business": values.get("years_in_business"),
            "tax_returns_verified": values.get("tax_returns_verified"),
            "equity_eur": values.get("equity_eur"), "days_past_due": values.get("days_past_due")}


def eur(x) -> str:
    return f"-€{-x:,.0f}" if x < 0 else f"€{x:,.0f}"


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
    if var == "equity_eur":
        return f"net equity is {op} {eur(num)}"
    if var == "days_past_due":
        return f"the applicant is {op} {num:g} days past due"
    if var == "leverage":
        return f"total debt after the new loan is {op} {num:g} times EBITDA"
    return f"years in business is {op} {num:g}"


def _figures(values, d) -> str:
    text = (f"DSCR {d['dscr']:.2f} (EBITDA {eur(values['ebitda_eur'])} ÷ annual debt service {eur(values['annual_debt_service_eur'])}); "
            f"loan-to-value {d['ltv'] * 100:.1f}% (requested {eur(values['requested_amount_eur'])} ÷ collateral {eur(values['collateral_value_eur'])}); "
            f"{values['years_in_business']:g} years in business; "
            f"tax returns {'verified' if values['tax_returns_verified'] else 'not verified'}")
    if d.get("leverage") is not None:
        text += (f"; leverage {d['leverage']:.2f}x (existing debt {eur(values['total_existing_debt_eur'])} "
                 f"+ requested {eur(values['requested_amount_eur'])}, ÷ EBITDA)")
    if values.get("equity_eur") is not None:
        text += f"; net equity {eur(values['equity_eur'])}"
    if values.get("days_past_due") is not None:
        text += f"; {values['days_past_due']:g} days past due"
    return text + "."


def _citation_text(citation: Optional[Dict[str, str]]) -> str:
    if not citation:
        return NO_CITATION_TEXT
    return (f"Source for this rule: {citation['source']}, {citation['locator']}: “{citation['quote']}” "
            f"({citation['url']}). {citation['note']}")


def _not_checked(rules, table_in) -> List[Dict[str, str]]:
    """Rules that could not be evaluated because the document did not give an optional input."""
    out = []
    for r in rules:
        for v, label in OPTIONAL_INPUTS.items():
            if r["tests"].get(v, "-").strip() != "-" and table_in.get(v) is None:
                out.append({"rule_id": r["id"], "label": r["label"], "missing_input": label,
                            "cited": bool(r.get("citation"))})
    return out


def _counterfactual(values, rules, fired) -> Optional[Dict[str, Any]]:
    """Smallest change to the applicant's figures that reaches a grant rule, confirmed by re-running the table."""
    d = derive(values)
    table_in = table_inputs(values, d)
    best = None
    for r in rules:
        if r["out"]["status"] != "GRANTED":
            continue
        unmet = [v for v in INPUT_IDS if not eval_test(r["tests"].get(v, "-"), table_in[v])]
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
        m = _TEST_RE.fullmatch(test.strip())
        if not m or v not in ("dscr", "ltv", "years_in_business"):
            return None  # no figure of the applicant's to move for this input
        num = float(m.group(2))
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
    rerun, _ = evaluate_table(rules, table_inputs(new, derive(new)))
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
            "rule": {"id": "GATE_INPUT_COMPLETENESS", "label": "Input completeness gate (runs before the decision table)",
                     "tests": {}, "citation": None},
            "policy": pol, "derived": d, "missing": missing, "trace": [], "not_checked": [],
            "explanation": (f"No automated decision was taken. The documents did not give, or gave only as pending or unverified: {names}. "
                            f"Nothing was assumed in its place; the case goes to a credit officer. {NO_CITATION_TEXT}"),
            "counterfactual": None,
        }

    table_in = table_inputs(values, d)
    fired, trace = evaluate_table(rules, table_in)
    conds = [_test_words(v, fired["tests"][v]) for v in INPUT_IDS if fired["tests"].get(v, "-").strip() != "-"]
    when = " and ".join(conds) if conds else "no earlier rule of the policy matches"
    verdict = {"GRANTED": f"Granted at {fired['out']['apr']:g}% APR" if fired["out"]["apr"] is not None else "Granted",
               "DENIED": "Declined", "ABSTAIN": "No automated decision; referred to a credit officer"}[fired["out"]["status"]]
    explanation = (f"{verdict}. Rule applied: {fired['id']} ({fired['label']}), policy version {policy['version']} [{policy['sha']}]. "
                   f"This rule applies when {when}. Figures used: {_figures(values, d)} {_citation_text(fired.get('citation'))}")
    return {
        "outcome": dict(fired["out"]),
        "rule": {"id": fired["id"], "label": fired["label"], "tests": fired["tests"], "citation": fired.get("citation")},
        "policy": pol, "derived": d, "missing": [], "trace": trace, "not_checked": _not_checked(rules, table_in),
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
        old = target["tests"].get(var, "-")
        if old == test:
            return self.current()
        target["tests"][var] = test
        note = f"{rule_id}: {var} changed from '{old}' to '{test}'"
        if target.get("citation"):  # the source no longer says what the rule says
            target["citation"] = None
            note += "; its citation was removed because the rule no longer matches the source"
        return self._add(rules, note)

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
