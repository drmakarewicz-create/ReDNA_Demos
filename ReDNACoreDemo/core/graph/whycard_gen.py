"""
Why-Card generation for trait promotions (Phase 8 Stage 4).

Generates 3-part explainability cards using deterministic templates.
Stage 4.1+ can replace with LLM-powered generation if env flag set.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import logging
import os

from .schemas import WhyCard

logger = logging.getLogger(__name__)


def generate_why_card(
    user_id: str,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float],
    observation_text: str,
    observation_source: str,
    observation_node_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> WhyCard:
    """
    Generate Why-Card for a trait promotion.

    Stage 4 MVP: Uses deterministic templates.
    Stage 4.1+: Can switch to LLM generation via WHYCARD_USE_LLM=true.

    Args:
        user_id: User ID
        trait_id: Trait ID (e.g., "PaDNA.Chronotype")
        value: Trait value
        rr_score: RR score (0-1000)
        ucn: UCN scores {"u": float, "c": float, "n": float}
        observation_text: Raw observation text
        observation_source: Source of observation
        observation_node_id: ID of observation node
        metadata: Optional metadata

    Returns:
        WhyCard with 3-part template populated
    """
    use_llm = os.getenv("WHYCARD_USE_LLM", "false").lower() in ("true", "1", "yes")

    if use_llm:
        # Stage 4.1: LLM-powered generation (placeholder)
        logger.info(f"LLM Why-Card generation requested for {trait_id} (not yet implemented)")
        return _generate_why_card_llm(
            user_id, trait_id, value, rr_score, ucn,
            observation_text, observation_source, observation_node_id, metadata
        )
    else:
        # Stage 4 MVP: Template-based generation
        return _generate_why_card_template(
            user_id, trait_id, value, rr_score, ucn,
            observation_text, observation_source, observation_node_id, metadata
        )


def _generate_why_card_template(
    user_id: str,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float],
    observation_text: str,
    observation_source: str,
    observation_node_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> WhyCard:
    """Generate Why-Card using deterministic templates."""

    # Extract UCN components
    u = ucn.get("u", 0.5)
    c = ucn.get("c", 0.5)
    n = ucn.get("n", 0.5)

    # Format value for display
    if isinstance(value, dict):
        if "enum" in value:
            value_str = value["enum"]
        elif "int" in value or "float" in value:
            value_str = str(value.get("int") or value.get("float"))
        elif "range" in value:
            r = value["range"]
            value_str = f"{r.get('min', '?')} - {r.get('max', '?')}"
        else:
            value_str = str(value)
    else:
        value_str = str(value)

    # Truncate observation text for "what" section
    obs_preview = observation_text[:80] + "..." if len(observation_text) > 80 else observation_text

    # PART 1: WHAT - Evidence snippet
    what = f'You said: "{obs_preview}"'

    # PART 2: WHY - Promotion rationale with RR/UCN
    # Determine signal strength
    if rr_score >= 700:
        signal_strength = "strong"
    elif rr_score >= 400:
        signal_strength = "moderate"
    else:
        signal_strength = "weak"

    # Format UCN for readability
    ucn_str = f"uncertainty: {u:.2f}, confidence: {c:.2f}"

    # Get readable trait name (strip namespace)
    trait_name = trait_id.split(".")[-1] if "." in trait_id else trait_id

    why = (
        f"This is a {signal_strength} signal for {trait_name} = {value_str} "
        f"(RR score: {rr_score:.0f}/1000, {ucn_str})"
    )

    # PART 3: NEXT - What would increase confidence
    if u > 0.7:
        # High uncertainty - need more observations
        next = f"Additional observations about {trait_name} would significantly increase confidence"
    elif u > 0.4:
        # Medium uncertainty - need specific follow-up
        next = f"Confirming related behaviors or asking follow-up questions about {trait_name} would help"
    else:
        # Low uncertainty - already confident
        next = f"Confidence is already high; tracking consistency over time would validate this"

    return WhyCard(
        user_id=user_id,
        trait_id=trait_id,
        what=what,
        why=why,
        next=next,
        rr=rr_score,
        ucn=ucn,
        evidence_node_ids=[observation_node_id],
        metadata=metadata or {}
    )


def _generate_why_card_llm(
    user_id: str,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float],
    observation_text: str,
    observation_source: str,
    observation_node_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> WhyCard:
    """
    Generate Why-Card using LLM (Stage 4.1+).

    Placeholder for future LLM integration. For now, falls back to template.
    """
    logger.warning("LLM Why-Card generation not yet implemented, using templates")
    return _generate_why_card_template(
        user_id, trait_id, value, rr_score, ucn,
        observation_text, observation_source, observation_node_id, metadata
    )


# Export public API
__all__ = ["generate_why_card"]
