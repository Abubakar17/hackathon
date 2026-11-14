"""
Pipeline: document -> extracted inputs (with evidence) -> DMN decision table -> decision record.

The record freezes the inputs and the policy version. Replaying a record re-runs the
engine on those frozen inputs, so the language model is never in the replay path.
"""
import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from ai_analyst import extract
from policy import RUNS_DIR, STORE, decide

_RECORDS: Dict[str, Dict[str, Any]] = {}
_LOG = os.path.join(RUNS_DIR, "decisions.jsonl")
_REVIEW_LOG = os.path.join(RUNS_DIR, "reviews.jsonl")
_REVIEWS: Dict[str, Dict[str, Any]] = {}
DELIVERY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "delivery")


def _conflicts(fields: Dict[str, Dict[str, Any]]) -> Dict[str, list]:
    """Field -> the different values the documents state for it. Read from the stored inputs, so replay needs no model."""
    return {n: [c["value"] for c in f["conflict"]] for n, f in fields.items() if f.get("conflict")}


def _record_id(values: Dict[str, Any], policy_sha: str, conflicts: Optional[Dict[str, list]] = None) -> str:
    body = {"inputs": values, "policy": policy_sha}
    if conflicts:
        body["conflicts"] = conflicts
    canon = json.dumps(body, sort_keys=True)
    return "DEC-" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:10].upper()


def process_credit_application(raw_text: str, use_ai: bool = True, persist: bool = True) -> Dict[str, Any]:
    extraction = extract(raw_text, use_ai=use_ai)
    values = {name: f["value"] for name, f in extraction["fields"].items()}
    policy = STORE.current()
    conflicts = _conflicts(extraction["fields"])
    result = decide(values, policy, conflicts)

    record = {
        "record_id": _record_id(values, policy["sha"], conflicts),
        "decided_at": datetime.now().isoformat(timespec="seconds"),
        "applicant": extraction["company_name"],
        **result,
        "inputs": extraction["fields"],
        "extraction": {"engine": extraction["engine"], "dropped": extraction["dropped"],
                       "document_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]},
    }
    if persist:
        _RECORDS[record["record_id"]] = record
        try:
            os.makedirs(RUNS_DIR, exist_ok=True)
            with open(_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            os.makedirs(DELIVERY_DIR, exist_ok=True)
            with open(os.path.join(DELIVERY_DIR, "decision_object.json"), "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
            with open(os.path.join(DELIVERY_DIR, "ruling.dmn"), "w", encoding="utf-8") as f:
                f.write(policy["xml"])
        except OSError:
            pass
    return record


def _load(record_id: str) -> Optional[Dict[str, Any]]:
    if record_id in _RECORDS:
        return _RECORDS[record_id]
    if os.path.exists(_LOG):
        with open(_LOG, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                _RECORDS[rec["record_id"]] = rec
    return _RECORDS.get(record_id)


def replay(record_id: str) -> Dict[str, Any]:
    """Re-run a stored record: once under the policy version it was decided with, once under today's policy."""
    rec = _load(record_id)
    if rec is None:
        raise KeyError(record_id)
    values = {name: f["value"] for name, f in rec["inputs"].items()}
    original_policy = STORE.get(rec["policy"]["sha256"])
    if original_policy is None:
        raise KeyError(f"policy {rec['policy']['sha256']} is no longer stored")
    conflicts = _conflicts(rec["inputs"])
    again = decide(values, original_policy, conflicts)
    current = STORE.current()
    now = decide(values, current, conflicts)
    brief = lambda r: {"status": r["outcome"]["status"], "category": r["outcome"]["category"], "apr": r["outcome"]["apr"],
                       "rule_id": r["rule"]["id"], "policy_version": r["policy"]["version"], "policy_sha": r["policy"]["sha256"]}
    return {
        "record_id": record_id,
        "original": brief(rec),
        "same_policy": {**brief(again), "record_id": _record_id(values, original_policy["sha"], conflicts),
                        "identical": again["outcome"] == rec["outcome"] and again["rule"]["id"] == rec["rule"]["id"]},
        "current_policy": {**brief(now), "policy_note": current["note"],
                           "changed": now["outcome"] != rec["outcome"] or now["rule"]["id"] != rec["rule"]["id"]},
    }


# ---------------------------------------------------------------- human review

def review(record_id: str, action: str, reviewer: str, note: str = "", persist: bool = True) -> Dict[str, Any]:
    """The credit officer's final word on a record. Stored beside the record, which is never rewritten.

    Accepting means the loan goes ahead, rejecting means it does not. A choice that differs from the
    engine's result (or any acceptance of a case the engine did not grant) is an override and needs a note.
    """
    rec = _load(record_id)
    if rec is None:
        raise KeyError(record_id)
    action, reviewer, note = str(action).strip().lower(), str(reviewer).strip(), str(note).strip()
    if action not in ("accept", "reject"):
        raise ValueError("The review must be 'accept' or 'reject'")
    if not reviewer:
        raise ValueError("Enter the reviewer's name")
    status = rec["outcome"]["status"]
    if status == "ABSTAIN":
        relation = "decides"  # the engine took no decision, so the officer takes it
    else:
        relation = "confirms" if (action == "accept") == (status == "GRANTED") else "overrides"
    if relation != "confirms" and not note:
        raise ValueError("A note is required: " + ("the engine took no decision, so say what the decision rests on"
                                                   if relation == "decides" else "this overrides the engine's result"))
    entry = {"record_id": record_id, "action": action, "reviewer": reviewer[:80], "note": note[:500],
             "reviewed_at": datetime.now().isoformat(timespec="seconds"), "engine_status": status,
             "engine_rule": rec["rule"]["id"], "policy_sha": rec["policy"]["sha256"], "relation": relation}
    _REVIEWS[record_id] = entry
    if persist:
        try:
            os.makedirs(RUNS_DIR, exist_ok=True)
            with open(_REVIEW_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
    return entry


def latest_review(record_id: str) -> Optional[Dict[str, Any]]:
    if record_id not in _REVIEWS and os.path.exists(_REVIEW_LOG):
        with open(_REVIEW_LOG, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                _REVIEWS[e["record_id"]] = e
    return _REVIEWS.get(record_id)
