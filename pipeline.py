"""
Pipeline coordinator: Ingests unstructured application text, extracts financials (via AI Agent or fallback),
evaluates DMN rules, and emits both OMG DMN XML and auditable Decision Objects.
"""
import uuid
from datetime import datetime
from typing import Tuple, Dict, Any, Optional

from models import DecisionObject
from ai_analyst import extract_financials_smart
from dmn_generator import generate_dmn_xml, evaluate_dmn_rules

def process_credit_application(raw_text: str, output_dir: Optional[str] = None, use_ai: bool = True) -> Tuple[DecisionObject, str]:
    """
    Executes the end-to-end decision pipeline:
    raw_text -> AI/Heuristic Extracted Financials & Ratios -> DMN Evaluation -> DecisionObject & DMN XML.
    """
    # 1. Smart Extraction (AI Agent with deterministic fallback)
    financials, ratios, missing_fields, memo, engine_source = extract_financials_smart(raw_text, prefer_ai=use_ai)

    # 2. DMN Rule Evaluation
    eval_result = evaluate_dmn_rules(financials, ratios, missing_fields)

    # 3. Generate OMG DMN 1.3 XML
    dmn_xml = generate_dmn_xml(model_name=f"DMN_Ruling_{financials.company_name.replace(' ', '_')}")

    # 4. Construct Immutable Decision Object
    decision_id = f"DEC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    timestamp = datetime.now().isoformat()

    # Combine DMN rule rationale with AI Underwriting synthesis
    combined_narrative = eval_result.get("rationale", "")
    if memo and memo != "Deterministic heuristic extraction complete.":
        combined_narrative += f" [Underwriting Memo: {memo}]"

    decision_obj = DecisionObject(
        decision_id=decision_id,
        timestamp=timestamp,
        applicant_name=financials.company_name,
        status=eval_result["status"],
        ruling_category=eval_result["ruling_category"],
        interest_rate_apr=eval_result.get("interest_rate_apr"),
        financial_ratios=ratios.to_dict(),
        constraints_evaluated=eval_result.get("constraints_evaluated", []),
        rule_id_triggered=eval_result.get("rule_id", "Unknown"),
        tripwires_and_bounds=eval_result.get("tripwires_and_bounds", {}),
        alternatives_rejected=eval_result.get("alternatives_rejected", []),
        missing_evidence=eval_result.get("missing_evidence", []),
        audit_narrative=combined_narrative,
        provenance=[
            "OMG_DMN_1.3_SPEC_20191111",
            f"EXTRACTION_ENGINE: {engine_source}",
            "CREDIT_UNDERWRITING_POLICY_V4.2",
            f"DATA_INTEGRITY: {'100%_VALID' if not missing_fields else 'INCOMPLETE_ABSTAIN'}"
        ]
    )

    # 5. Persist artifacts if output_dir specified
    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "ruling.dmn"), "w", encoding="utf-8") as f:
            f.write(dmn_xml)
        with open(os.path.join(output_dir, "decision_object.json"), "w", encoding="utf-8") as f:
            f.write(decision_obj.to_json())

    return decision_obj, dmn_xml
