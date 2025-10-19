from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import re

# Canonical evidence record the resolver expects:
# {
#   "trait_id": "PaDNA.EyeDNA.IrisColor",
#   "value": {"enum": "blue"} | {"number": 47} | {"text": "..."},   # ONE of enum/number/text
#   "source": "chat|onboarding|goal|...",
#   "ts": "2025-10-13T19:20:00Z"
# }


def normalize_value(raw: Any) -> Dict[str, Any]:
    """
    Convert various value formats to the canonical typed value shape.

    Maps:
    - Numbers → {"number": X}
    - Simple tokens → {"enum": "x"}
    - Complex strings → {"text": "..."}
    - Already structured → pass through

    Args:
        raw: Value in any format (scalar, dict, etc.)

    Returns:
        Canonical value dict with one key: enum, number, or text
    """
    if isinstance(raw, (int, float)):
        return {"number": raw}

    if isinstance(raw, str):
        s = raw.strip()
        # Simple enum heuristic: single token, lowercase alnum/underscore
        if re.fullmatch(r"[A-Za-z_]+", s):
            return {"enum": s.lower()}
        return {"text": s}

    # Already structured?
    if isinstance(raw, dict) and any(k in raw for k in ("enum", "number", "text")):
        return raw

    # Fallback to text
    return {"text": str(raw)}


class EvidenceValidationError(Exception):
    """
    Exception raised when evidence validation fails in strict mode.

    Attributes:
        error_code: Machine-readable error code
        message: Human-readable error message
        evidence_sample: Sample of the invalid evidence
        suggestions: List of suggested fixes
    """
    def __init__(
        self,
        error_code: str,
        message: str,
        evidence_sample: Dict[str, Any],
        suggestions: Optional[List[Dict[str, Any]]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.evidence_sample = evidence_sample
        self.suggestions = suggestions or []
        super().__init__(message)


def validate_and_fix(ev: Dict[str, Any], strict: bool = None) -> Dict[str, Any]:
    """
    Validate and normalize a single evidence record.

    Accepts legacy formats and converts to canonical:
    - "trait" → "trait_id"
    - "fact_value" → "value"
    - Raw values → typed value shape

    Args:
        ev: Evidence record dict
        strict: If True, raise EvidenceValidationError on missing fields.
                If None, read from EVIDENCE_STRICT env var (default: false).

    Returns:
        Validated and normalized evidence record

    Raises:
        EvidenceValidationError: If evidence is invalid and strict mode is enabled
        ValueError: If evidence is invalid and strict mode is disabled (legacy)
    """
    if strict is None:
        strict = os.getenv("EVIDENCE_STRICT", "false").lower() in ("1", "true", "yes")

    out = dict(ev)

    # Accept multiple trait ID formats
    if "trait_id" not in out:
        if "trait" in out:
            out["trait_id"] = out.pop("trait")
        elif "trait_category" in out and "fact_category" in out:
            # Chat extractor format: trait_category.fact_category
            out["trait_id"] = f"{out.pop('trait_category')}.{out.pop('fact_category')}"
        else:
            if strict:
                raise EvidenceValidationError(
                    error_code="MISSING_TRAIT_ID",
                    message="Evidence record missing trait identifier. Expected 'trait_id', 'trait', or 'trait_category'+'fact_category'.",
                    evidence_sample=ev,
                    suggestions=[
                        {"hint": "Add 'trait_id' field", "example": "trait_id: 'PaDNA.EyeDNA.IrisColor'"},
                        {"hint": "Or use legacy 'trait' field", "example": "trait: 'PaDNA.EyeDNA.IrisColor'"}
                    ]
                )
            raise ValueError(f"evidence missing trait_id/trait/trait_category: {list(out.keys())}")

    if "value" not in out:
        # Accept legacy 'fact_value'
        if "fact_value" in out:
            out["value"] = normalize_value(out.pop("fact_value"))
        else:
            if strict:
                raise EvidenceValidationError(
                    error_code="MISSING_VALUE",
                    message="Evidence record missing value. Expected 'value' or 'fact_value'.",
                    evidence_sample=ev,
                    suggestions=[
                        {"hint": "Add 'value' field with typed value", "example": "value: {'enum': 'blue'}"},
                        {"hint": "Or use legacy 'fact_value' field", "example": "fact_value: 'blue'"}
                    ]
                )
            raise ValueError(f"evidence missing value/fact_value: {list(out.keys())}")
    else:
        out["value"] = normalize_value(out["value"])

    # Validate value is properly typed
    if strict and "value" in out:
        val = out["value"]
        if not isinstance(val, dict) or not any(k in val for k in ("enum", "number", "text")):
            raise EvidenceValidationError(
                error_code="INVALID_VALUE_SHAPE",
                message="Evidence value must be a dict with one of: enum, number, or text",
                evidence_sample=ev,
                suggestions=[
                    {"hint": "For categorical values", "example": "value: {'enum': 'blue'}"},
                    {"hint": "For numeric values", "example": "value: {'number': 6.2}"},
                    {"hint": "For text values", "example": "value: {'text': 'medium height'}"}
                ]
            )

    return out


def validate_batch(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and normalize a batch of evidence records.

    Args:
        batch: List of evidence dicts

    Returns:
        List of validated evidence records

    Raises:
        ValueError: If any evidence record is invalid
    """
    return [validate_and_fix(x) for x in batch]
