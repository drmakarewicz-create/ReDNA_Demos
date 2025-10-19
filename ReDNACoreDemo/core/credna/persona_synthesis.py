"""
CReDNA Persona Synthesis Engine
================================

Builds style/persona envelopes per (user_id, coach_id, intent) via:

    final_style = blend(user_style, role_overlay, weights) ⊕ apply(user_coach_deltas) ⊕ apply(manual_prefs)

With lazy materialization (per-user-per-coach files created only when training happens).

Special case - ChatDNA Coach:
    ChatDNA Coach simulates the USER talking to themselves, not a coach personality.
    Use compute_user_style_only(user_id) for user self-simulation.
    Use build_envelope(user_id, coach_id, intent) for coach personalities.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Dimension bounds and categorical mappings
DIMENSION_CATEGORIES = {
    "tone": ["cool", "neutral", "warm", "encouraging", "reflective", "optimistic"],
    "cadence": ["slow", "medium", "medium-fast", "fast"],
    "formality": ["casual", "neutral", "semi-formal", "formal"],
    "vocabulary": ["low", "medium", "high"],
    "hedging": ["low", "medium", "high"],
    "humor": ["none", "dry", "witty", "playful"],
    "directness": ["indirect", "balanced", "direct"],
    "empathy": ["low", "moderate", "high"],
}

# Numeric scale for delta calculations (maps to categorical)
DIMENSION_SCALES = {
    "tone": ["cool", "neutral", "warm", "encouraging", "reflective", "optimistic"],
    "cadence": ["slow", "medium", "medium-fast", "fast"],
    "formality": ["casual", "neutral", "semi-formal", "formal"],
    "vocabulary": ["low", "medium", "high"],
    "hedging": ["low", "medium", "high"],
    "humor": ["none", "dry", "witty", "playful"],
    "directness": ["indirect", "balanced", "direct"],
    "empathy": ["low", "moderate", "high"],
}

# Default weights for blending
DEFAULT_WEIGHTS = {
    "user_style": 0.6,
    "coach_role": 0.4,
    "user_delta": 0.2,  # Additive adjustments
    "manual_prefs": 0.0,  # Override (applied last, not weighted)
}


def build_envelope(
    user_id: str,
    coach_id: str,
    intent: str = "default",
    opts: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a CReDNA Style/Persona Envelope for a specific (user, coach, intent).

    IMPORTANT: This is for COACH PERSONALITIES only.
    DO NOT use for chatdna_coach (user self-simulation) - use compute_user_style_only() instead.

    Layering:
        1. role_overlay (global per coach/intent)
        2. user_style (computed from User ReDNA)
        3. user_coach_deltas (learned from feedback)
        4. manual_prefs (explicit user overrides)

    Args:
        user_id: User identifier
        coach_id: Coach identifier (e.g., "career_coach")
        intent: Intent/mode (e.g., "default", "supportive", "analytical")
        opts: Optional overrides (e.g., skip_cache=True)

    Returns:
        CReDNA envelope dict with tone, cadence, formality, etc.

    Raises:
        ValueError: If coach_id is "chatdna_coach" (use compute_user_style_only instead)
    """
    opts = opts or {}

    # Enforce architectural boundary: ChatDNA is user-self simulation, not CReDNA
    if coach_id == "chatdna_coach":
        raise ValueError(
            "ChatDNA Coach uses user self-simulation (ReDNA only). "
            "Use compute_user_style_only(user_id) instead of build_envelope(). "
            "ChatDNA does not use CReDNA overlays, deltas, or prefs."
        )

    # 1. Load role overlay
    role_overlay = _load_role_overlay(coach_id, intent)

    # 2. Compute user style from ReDNA
    user_style = _compute_user_style(user_id)

    # 3. Load per-user-per-coach deltas (lazy)
    user_coach_deltas, materialized = _load_deltas(user_id, coach_id)

    # 4. Load manual prefs (lazy)
    manual_prefs = _load_prefs(user_id, coach_id)
    if manual_prefs:
        materialized = True

    # 5. Blend layers
    envelope = _blend_layers(
        role_overlay=role_overlay,
        user_style=user_style,
        user_deltas=user_coach_deltas,
        manual_prefs=manual_prefs,
        weights=DEFAULT_WEIGHTS
    )

    # 6. Apply consent gates
    envelope = _apply_consent_gates(envelope, user_id)

    # 7. Add metadata
    envelope["merge_weights"] = DEFAULT_WEIGHTS.copy()
    envelope["sources"] = _determine_sources(role_overlay, user_style, user_coach_deltas, manual_prefs)
    envelope["materialized"] = materialized
    envelope["credna_version"] = "0.2"
    envelope["policy"] = {
        "overlay_id": f"{coach_id}/{intent}",
        "consent_applied": True,
        "sensitive_suppressed": []  # Populated by _apply_consent_gates
    }

    return envelope


def _load_role_overlay(coach_id: str, intent: str) -> Dict[str, Any]:
    """Load global role overlay for coach+intent."""
    overlays_file = Path(__file__).parent / "overlays" / "role_overlays.yaml"

    if not overlays_file.exists():
        logger.warning(f"Role overlays file not found: {overlays_file}")
        return _get_default_overlay()

    try:
        with open(overlays_file, 'r') as f:
            overlays = yaml.safe_load(f)

        # Look for coach-specific intent, then coach default, then global default
        coach_overlays = overlays.get(coach_id, {})
        if intent in coach_overlays:
            return coach_overlays[intent]
        elif "default" in coach_overlays:
            return coach_overlays["default"]
        else:
            return overlays.get("_default", _get_default_overlay())

    except Exception as e:
        logger.error(f"Error loading role overlay: {e}")
        return _get_default_overlay()


def _get_default_overlay() -> Dict[str, Any]:
    """Fallback neutral overlay."""
    return {
        "tone": "neutral",
        "cadence": "medium",
        "formality": "neutral",
        "vocabulary": "medium",
        "hedging": "medium",
        "humor": "none",
        "directness": "balanced",
        "empathy": "moderate",
        "stance_hints": []
    }


def compute_user_style_only(user_id: str) -> Dict[str, Any]:
    """
    PUBLIC API: Extract user's natural conversational style from their ReDNA.

    Use this for ChatDNA Coach (user self-simulation).
    DO NOT use this for coach personalities - use build_envelope() instead.

    Args:
        user_id: User identifier

    Returns:
        Style dict with tone, cadence, formality, vocabulary, etc.
    """
    return _compute_user_style(user_id)


def _compute_user_style(user_id: str) -> Dict[str, Any]:
    """
    Compute user's natural style from their ReDNA profile.

    Extracts:
    - LanguageStyleDNA (cadence, vocabulary, hedging, formality)
    - PersonalityDNA.AgreeablenessDNA (empathy/warmth)
    - InteractionStyleDNA (directness)
    """
    from ..storage import read_user_state

    try:
        resolved, _, _ = read_user_state(user_id)
    except Exception as e:
        logger.warning(f"Could not load user state for {user_id}: {e}")
        return _get_default_overlay()

    style = {}

    # Cadence from LanguageStyleDNA.CadenceDNA
    cadence_data = resolved.get("LanguageStyleDNA.CadenceDNA", {})
    cadence_rr = cadence_data.get("rr", 50)
    if cadence_rr > 70:
        style["cadence"] = "fast"
    elif cadence_rr > 50:
        style["cadence"] = "medium-fast"
    elif cadence_rr > 30:
        style["cadence"] = "medium"
    else:
        style["cadence"] = "slow"

    # Vocabulary from LanguageStyleDNA.VocabularyDensityDNA
    vocab_data = resolved.get("LanguageStyleDNA.VocabularyDensityDNA", {})
    vocab_rr = vocab_data.get("rr", 50)
    if vocab_rr > 60:
        style["vocabulary"] = "high"
    elif vocab_rr > 30:
        style["vocabulary"] = "medium"
    else:
        style["vocabulary"] = "low"

    # Hedging from LanguageStyleDNA.HedgingPatternDNA
    hedging_data = resolved.get("LanguageStyleDNA.HedgingPatternDNA", {})
    hedging_rr = hedging_data.get("rr", 50)
    if hedging_rr > 60:
        style["hedging"] = "high"
    elif hedging_rr > 30:
        style["hedging"] = "medium"
    else:
        style["hedging"] = "low"

    # Formality from LanguageStyleDNA.FormalityDNA
    formality_data = resolved.get("LanguageStyleDNA.FormalityDNA", {})
    formality_rr = formality_data.get("rr", 50)
    if formality_rr > 70:
        style["formality"] = "formal"
    elif formality_rr > 50:
        style["formality"] = "semi-formal"
    elif formality_rr > 30:
        style["formality"] = "neutral"
    else:
        style["formality"] = "casual"

    # Empathy/warmth from PersonalityDNA.BigFiveDNA.AgreeablenessDNA
    agree_data = resolved.get("PsyDNA.PersonalityDNA.BigFiveDNA.AgreeablenessDNA", {})
    agree_rr = agree_data.get("rr", 50)
    if agree_rr > 65:
        style["tone"] = "warm"
        style["empathy"] = "high"
    elif agree_rr > 40:
        style["tone"] = "neutral"
        style["empathy"] = "moderate"
    else:
        style["tone"] = "cool"
        style["empathy"] = "low"

    # Directness (placeholder - could map from assertiveness or extraversion)
    style["directness"] = "balanced"

    # Humor (placeholder - future: could infer from playfulness traits)
    style["humor"] = "none"

    # Stance hints from BeliefValueDNA (privacy-aware)
    style["stance_hints"] = []

    return style


def _load_deltas(user_id: str, coach_id: str) -> Tuple[Dict[str, Any], bool]:
    """
    Load learned deltas for (user_id, coach_id).

    Returns:
        (deltas_dict, materialized_flag)
    """
    deltas_file = Path("data/users") / user_id / "credna" / coach_id / "deltas.json"

    if not deltas_file.exists():
        return {}, False

    try:
        with open(deltas_file, 'r') as f:
            deltas = json.load(f)
        return deltas, True
    except Exception as e:
        logger.error(f"Error loading deltas for {user_id}/{coach_id}: {e}")
        return {}, False


def _load_prefs(user_id: str, coach_id: str) -> Dict[str, Any]:
    """Load manual preference overrides for (user_id, coach_id)."""
    prefs_file = Path("data/users") / user_id / "credna" / coach_id / "prefs.json"

    if not prefs_file.exists():
        return {}

    try:
        with open(prefs_file, 'r') as f:
            prefs = json.load(f)
        return prefs
    except Exception as e:
        logger.error(f"Error loading prefs for {user_id}/{coach_id}: {e}")
        return {}


def _blend_layers(
    role_overlay: Dict[str, Any],
    user_style: Dict[str, Any],
    user_deltas: Dict[str, Any],
    manual_prefs: Dict[str, Any],
    weights: Dict[str, float]
) -> Dict[str, Any]:
    """
    Blend the four layers into final envelope.

    Logic:
    1. Start with role_overlay
    2. Blend in user_style (weighted)
    3. Apply user_deltas (additive numeric shifts)
    4. Apply manual_prefs (final overrides)
    """
    envelope = {}

    # For each dimension, blend role and user style
    for dim in DIMENSION_CATEGORIES.keys():
        role_val = role_overlay.get(dim)
        user_val = user_style.get(dim)

        # If no user style, use role
        if not user_val:
            envelope[dim] = role_val or DIMENSION_CATEGORIES[dim][0]
        # If no role, use user
        elif not role_val:
            envelope[dim] = user_val
        # Blend with weights (categorical → numeric → categorical)
        else:
            envelope[dim] = _blend_categorical(
                role_val,
                user_val,
                weights["coach_role"],
                weights["user_style"],
                dim
            )

        # Apply deltas (numeric shifts)
        if dim in user_deltas:
            envelope[dim] = _apply_delta(envelope[dim], user_deltas[dim], dim)

        # Apply manual prefs (overrides)
        if dim in manual_prefs:
            envelope[dim] = manual_prefs[dim]

    # Stance hints (combine from all layers)
    envelope["stance_hints"] = list(set(
        role_overlay.get("stance_hints", []) +
        user_style.get("stance_hints", [])
    ))

    return envelope


def _blend_categorical(
    val1: str,
    val2: str,
    weight1: float,
    weight2: float,
    dimension: str
) -> str:
    """
    Blend two categorical values with weights.

    Convert to numeric indices, blend, convert back.
    """
    scale = DIMENSION_SCALES.get(dimension, [])
    if not scale:
        return val1  # Fallback

    try:
        idx1 = scale.index(val1)
        idx2 = scale.index(val2)
    except ValueError:
        return val1  # If value not in scale, use first

    # Weighted blend
    blended_idx = int(round(idx1 * weight1 + idx2 * weight2))
    blended_idx = max(0, min(len(scale) - 1, blended_idx))

    return scale[blended_idx]


def _apply_delta(current_val: str, delta: int, dimension: str) -> str:
    """Apply numeric delta to categorical value."""
    scale = DIMENSION_SCALES.get(dimension, [])
    if not scale:
        return current_val

    try:
        current_idx = scale.index(current_val)
    except ValueError:
        return current_val

    new_idx = current_idx + delta
    new_idx = max(0, min(len(scale) - 1, new_idx))

    return scale[new_idx]


def _apply_consent_gates(envelope: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Apply consent gates to suppress sensitive traits.

    For now, placeholder - future: check consent flags.
    """
    # TODO: Implement consent checking
    envelope["policy"]["sensitive_suppressed"] = []
    return envelope


def _determine_sources(
    role_overlay: Dict[str, Any],
    user_style: Dict[str, Any],
    user_deltas: Dict[str, Any],
    manual_prefs: Dict[str, Any]
) -> List[str]:
    """Determine which sources contributed to the envelope."""
    sources = ["role_overlay"]

    if user_style:
        sources.append("user_style")

    if user_deltas:
        sources.append("user_delta")

    if manual_prefs:
        sources.append("manual_prefs")

    return sources
