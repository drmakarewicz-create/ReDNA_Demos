from __future__ import annotations
from typing import Dict, Any, List
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


def validate_and_fix(ev: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize a single evidence record.

    Accepts legacy formats and converts to canonical:
    - "trait" → "trait_id"
    - "fact_value" → "value"
    - Raw values → typed value shape

    Args:
        ev: Evidence record dict

    Returns:
        Validated and normalized evidence record

    Raises:
        ValueError: If evidence is missing required fields
    """
    out = dict(ev)

    # Accept multiple trait ID formats
    if "trait_id" not in out:
        if "trait" in out:
            out["trait_id"] = out.pop("trait")
        elif "trait_category" in out and "fact_category" in out:
            # Chat extractor format: trait_category.fact_category
            out["trait_id"] = f"{out.pop('trait_category')}.{out.pop('fact_category')}"
        else:
            raise ValueError(f"evidence missing trait_id/trait/trait_category: {list(out.keys())}")

    if "value" not in out:
        # Accept legacy 'fact_value'
        if "fact_value" in out:
            out["value"] = normalize_value(out.pop("fact_value"))
        else:
            raise ValueError(f"evidence missing value/fact_value: {list(out.keys())}")
    else:
        out["value"] = normalize_value(out["value"])

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
