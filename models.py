"""
Core data structures for Credit DMN Decision Pipeline.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

@dataclass
class ExtractedFinancials:
    company_name: str
    requested_amount_eur: Optional[float] = None
    annual_revenue_eur: Optional[float] = None
    ebitda_eur: Optional[float] = None
    annual_debt_service_eur: Optional[float] = None
    total_existing_debt_eur: Optional[float] = None
    collateral_value_eur: Optional[float] = None
    years_in_business: Optional[int] = None
    tax_returns_verified: Optional[bool] = None
    credit_rating: Optional[str] = None
    extraction_source: str = "unstructured_text"

@dataclass
class FinancialRatios:
    dscr: Optional[float] = None  # EBITDA / Annual Debt Service
    ltv: Optional[float] = None   # Requested Amount / Collateral Value
    debt_to_ebitda: Optional[float] = None  # Total Debt / EBITDA

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dscr": round(self.dscr, 2) if self.dscr is not None else None,
            "ltv": round(self.ltv, 2) if self.ltv is not None else None,
            "debt_to_ebitda": round(self.debt_to_ebitda, 2) if self.debt_to_ebitda is not None else None,
        }

@dataclass
class ConstraintEvaluation:
    rule_name: str
    description: str
    condition: str
    actual_value: str
    result: str  # PASS | FAIL | UNKNOWN

@dataclass
class DecisionObject:
    decision_id: str
    timestamp: str
    applicant_name: str
    status: str  # GRANTED | DENIED | ABSTAIN
    ruling_category: str  # APPROVED_PRIME | APPROVED_STANDARD | DENIED_CREDIT_POLICY | ABSTAIN_DATA_INCOMPLETE
    interest_rate_apr: Optional[float]
    financial_ratios: Dict[str, Any]
    constraints_evaluated: List[Dict[str, Any]]
    rule_id_triggered: str
    tripwires_and_bounds: Dict[str, Any]
    alternatives_rejected: List[Dict[str, str]]
    missing_evidence: List[str]
    audit_narrative: str
    provenance: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
