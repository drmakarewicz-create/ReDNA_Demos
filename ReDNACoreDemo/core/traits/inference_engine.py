from __future__ import annotations
import yaml
import pathlib
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

_RULES_PATH = pathlib.Path(__file__).with_name("inference_rules.yaml")
_RULES = yaml.safe_load(_RULES_PATH.read_text()) if _RULES_PATH.exists() else []


def run_inference(canonical_evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Run inference rules on canonical evidence to generate additional trait inferences.

    This implements a declarative rules engine that:
    1. Checks observed traits against rule conditions
    2. Proposes additional inferred traits with low confidence
    3. Tags all inferences with provenance and needs_confirmation hints

    ETHICAL GUARDRAILS:
    - All inferred traits have ucn_prior between 0.15-0.25 (low confidence)
    - All include provenance: "inference:<rule_id>"
    - All include display_hint: "needs_confirmation"
    - Sensitive inferences marked ui_hidden: true

    Args:
        canonical_evidence: List of evidence dicts with canonical trait IDs

    Returns:
        List of inferred evidence items to add to the trait system
    """
    inferred: List[Dict[str, Any]] = []

    # Build a set of (trait_id, normalized_value) tuples for fast lookup
    # Evidence comes in validated format: {trait_id, value: {enum|number|text}, ...}
    observed = set()
    for ev in canonical_evidence:
        trait_id = ev.get("trait_id")
        if not trait_id:
            continue

        # Extract scalar value from canonical value shape
        value_obj = ev.get("value", {})
        if isinstance(value_obj, dict):
            # Try enum, then number, then text
            scalar_value = value_obj.get("enum") or value_obj.get("number") or value_obj.get("text")
        else:
            # Fallback to fact_value for backward compatibility
            scalar_value = ev.get("fact_value")

        if scalar_value:
            observed.add((trait_id, str(scalar_value).lower()))

    logger.info(f"Running inference on {len(observed)} observed traits")

    # Check each rule
    for rule in _RULES or []:
        rule_id = rule.get("id", "unknown")
        cond = rule.get("when", {})
        tid = cond.get("trait_id")
        equals = str(cond.get("equals", "")).lower()

        if not tid or not equals:
            logger.warning(f"Rule {rule_id} has invalid condition")
            continue

        # Check if this rule's condition is satisfied
        if (tid, equals) in observed:
            logger.info(f"Rule {rule_id} triggered by {tid}={equals}")

            # Add all inferred traits from this rule
            for item in rule.get("infer", []):
                inferred_trait = {
                    "trait_id": item["trait_id"],
                    "fact_value": item["value"],
                    "ucn_prior": float(item.get("ucn_prior", 0.15)),
                    "provenance": f"inference:{rule_id}",
                    "display_hint": item.get("display_hint", "needs_confirmation"),
                    "ui_hidden": bool(item.get("ui_hidden", False)),
                    "inference_source": {
                        "rule_id": rule_id,
                        "triggered_by": {"trait_id": tid, "value": equals},
                        "notes": rule.get("notes", "")
                    }
                }
                inferred.append(inferred_trait)
                logger.info(f"  → Inferred {item['trait_id']}={item['value']} (ucn={inferred_trait['ucn_prior']})")

    logger.info(f"Inference generated {len(inferred)} new trait proposals")
    return inferred
