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
DELIVERY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "delivery")


def _record_id(values: Dict[str, Any], policy_sha: str) -> str:
    canon = json.dumps({"inputs": values, "policy": policy_sha}, sort_keys=True)
    return "DEC-" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:10].upper()


def process_credit_application(raw_text: str, use_ai: bool = True, persist: bool = True) -> Dict[str, Any]:
    extraction = extract(raw_text, use_ai=use_ai)
    values = {name: f["value"] for name, f in extraction["fields"].items()}
    policy = STORE.current()
    result = decide(values, policy)

    record = {
        "record_id": _record_id(values, policy["sha"]),
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
    again = decide(values, original_policy)
    current = STORE.current()
    now = decide(values, current)
    brief = lambda r: {"status": r["outcome"]["status"], "category": r["outcome"]["category"], "apr": r["outcome"]["apr"],
                       "rule_id": r["rule"]["id"], "policy_version": r["policy"]["version"], "policy_sha": r["policy"]["sha256"]}
    return {
        "record_id": record_id,
        "original": brief(rec),
        "same_policy": {**brief(again), "record_id": _record_id(values, original_policy["sha"]),
                        "identical": again["outcome"] == rec["outcome"] and again["rule"]["id"] == rec["rule"]["id"]},
        "current_policy": {**brief(now), "policy_note": current["note"],
                           "changed": now["outcome"] != rec["outcome"] or now["rule"]["id"] != rec["rule"]["id"]},
    }
