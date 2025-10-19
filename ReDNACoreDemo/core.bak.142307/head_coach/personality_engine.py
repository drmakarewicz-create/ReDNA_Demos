"""
Head Coach Personality Engine
==============================

Integrates CReDNA personality synthesis with situational awareness and intent context
to provide context-aware, personalized coaching responses.

Combines:
1. User's conversational style (from ReDNA)
2. Head Coach role overlay (base personality)
3. Meta-dimensions (proactiveness, curiosity_drive, authority_level)
4. Awareness context (emotional tone, goals, curiosity hotspots)
5. Intent context (detected user intent, delegation state)

Produces personality envelope for LLM prompting or UI personalization.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PersonalityEngine:
    """
    Context-aware personality engine for Head Coach v2.

    Synthesizes personality based on:
    - User ReDNA (base style preferences)
    - Situational awareness (emotional state, goals, context)
    - Intent classification (what user wants)
    - CReDNA role overlay (Head Coach personality defaults)
    """

    def __init__(self):
        """Initialize personality engine."""
        self.version = "v1.0-jarvis"

    def build_personality_envelope(
        self,
        user_id: str,
        awareness_snapshot: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        override_intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build personality envelope for Head Coach based on context.

        Args:
            user_id: User ID
            awareness_snapshot: Situational awareness snapshot (from AwarenessEngine)
            intent_analysis: Intent classification result (from IntentClassifier)
            override_intent: Optional intent override (e.g., "supportive", "analytical")

        Returns:
            Personality envelope with style dimensions + meta-dimensions + context
        """
        # Import CReDNA here to avoid circular imports
        from ..credna.persona_synthesis import build_envelope

        # Determine intent for CReDNA lookup
        intent = self._determine_intent(
            awareness_snapshot=awareness_snapshot,
            intent_analysis=intent_analysis,
            override_intent=override_intent
        )

        # Build base CReDNA envelope
        try:
            credna_envelope = build_envelope(
                user_id=user_id,
                coach_id="head_coach",
                intent=intent
            )
        except Exception as e:
            logger.warning(f"CReDNA envelope build failed for user {user_id}: {e}. Using defaults.")
            credna_envelope = self._get_fallback_envelope(intent)

        # Enhance with context-aware adjustments
        personality = self._apply_context_adjustments(
            base_envelope=credna_envelope,
            awareness_snapshot=awareness_snapshot,
            intent_analysis=intent_analysis
        )

        # Add metadata
        personality["metadata"] = {
            "personality_version": self.version,
            "user_id": user_id,
            "intent_used": intent,
            "context_aware": True,
            "has_awareness": awareness_snapshot is not None,
            "has_intent": intent_analysis is not None
        }

        return personality

    def _determine_intent(
        self,
        awareness_snapshot: Optional[Dict[str, Any]],
        intent_analysis: Optional[Dict[str, Any]],
        override_intent: Optional[str]
    ) -> str:
        """
        Determine which CReDNA intent to use.

        Priority:
        1. Override (explicit request)
        2. Intent analysis (detected from message)
        3. Awareness context (emotional tone, delegation state)
        4. Default
        """
        # Priority 1: Explicit override
        if override_intent:
            return override_intent

        # Priority 2: Detected delegation intent
        if intent_analysis and intent_analysis.get("delegation_recommendation", {}).get("routing_strategy") == "direct":
            return "delegation_mode"

        # Priority 3: Emotional tone from awareness
        if awareness_snapshot:
            emotional_tone = awareness_snapshot.get("user_core_state", {}).get("emotional_tone")

            if emotional_tone in ["frustrated", "negative"]:
                return "supportive"
            elif emotional_tone == "curious":
                return "default"  # Default has high curiosity_drive

        # Priority 4: Intent confidence check
        if intent_analysis:
            confidence = intent_analysis.get("confidence", 0)
            primary_intent = intent_analysis.get("primary_intent")

            # High confidence on specific domain -> use analytical mode
            if confidence > 0.7 and primary_intent in ["career_guidance", "personality_assessment"]:
                return "analytical"

        # Default
        return "default"

    def _apply_context_adjustments(
        self,
        base_envelope: Dict[str, Any],
        awareness_snapshot: Optional[Dict[str, Any]],
        intent_analysis: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Apply context-aware adjustments to base CReDNA envelope.

        Adjustments based on:
        - Emotional tone (if user frustrated -> increase empathy)
        - Urgency level (if urgent -> increase directness)
        - Clarity need (if intent unclear -> increase hedging, decrease proactiveness)
        """
        envelope = base_envelope.copy()

        if not awareness_snapshot and not intent_analysis:
            # No context available - return base envelope
            envelope["context_adjustments"] = []
            return envelope

        adjustments = []

        # Emotional tone adjustments
        if awareness_snapshot:
            emotional_tone = awareness_snapshot.get("user_core_state", {}).get("emotional_tone")
            emotion_confidence = awareness_snapshot.get("user_core_state", {}).get("emotion_confidence", 0)

            if emotion_confidence > 0.6:  # Only adjust if confident
                if emotional_tone == "frustrated":
                    # Increase empathy, reduce directness
                    envelope["empathy"] = self._shift_dimension(envelope.get("empathy", "moderate"), "empathy", +1)
                    envelope["directness"] = self._shift_dimension(envelope.get("directness", "balanced"), "directness", -1)
                    envelope["proactiveness"] = self._shift_dimension(envelope.get("proactiveness", "moderate"), "proactiveness", +1)
                    adjustments.append("emotional_support_boost")

                elif emotional_tone == "positive":
                    # Maintain high curiosity, can be more direct
                    envelope["curiosity_drive"] = self._shift_dimension(envelope.get("curiosity_drive", "moderate"), "curiosity_drive", +1)
                    adjustments.append("positive_engagement_boost")

        # Intent clarity adjustments
        if intent_analysis:
            requires_clarification = intent_analysis.get("requires_clarification", False)
            confidence = intent_analysis.get("confidence", 1.0)

            if requires_clarification or confidence < 0.4:
                # Reduce proactiveness, increase hedging for clarification
                envelope["proactiveness"] = self._shift_dimension(envelope.get("proactiveness", "moderate"), "proactiveness", -1)
                envelope["hedging"] = self._shift_dimension(envelope.get("hedging", "medium"), "hedging", +1)
                adjustments.append("clarification_mode")

            # Urgency adjustments
            urgency = intent_analysis.get("metadata", {}).get("urgency_level")
            if urgency == "high" or urgency == "critical":
                envelope["directness"] = self._shift_dimension(envelope.get("directness", "balanced"), "directness", +1)
                envelope["cadence"] = self._shift_dimension(envelope.get("cadence", "medium"), "cadence", +1)
                envelope["proactiveness"] = self._shift_dimension(envelope.get("proactiveness", "moderate"), "proactiveness", +1)
                adjustments.append("urgency_response")

        envelope["context_adjustments"] = adjustments
        return envelope

    def _shift_dimension(
        self,
        current_value: str,
        dimension: str,
        delta: int
    ) -> str:
        """
        Shift a dimension value by delta steps.

        Args:
            current_value: Current dimension value
            dimension: Dimension name
            delta: Steps to shift (+1 = increase, -1 = decrease)

        Returns:
            New dimension value
        """
        # Dimension scales
        scales = {
            "empathy": ["low", "moderate", "high"],
            "directness": ["indirect", "balanced", "direct"],
            "hedging": ["low", "medium", "high"],
            "proactiveness": ["low", "moderate", "high"],
            "curiosity_drive": ["low", "moderate", "high"],
            "authority_level": ["gentle", "balanced", "assertive"],
            "cadence": ["slow", "medium", "medium-fast", "fast"]
        }

        scale = scales.get(dimension)
        if not scale:
            return current_value

        try:
            current_idx = scale.index(current_value)
        except ValueError:
            # Value not in scale - return unchanged
            return current_value

        new_idx = max(0, min(len(scale) - 1, current_idx + delta))
        return scale[new_idx]

    def _get_fallback_envelope(self, intent: str) -> Dict[str, Any]:
        """
        Get fallback envelope if CReDNA build fails.

        Returns basic Head Coach personality based on intent.
        """
        fallback_envelopes = {
            "default": {
                "tone": "encouraging",
                "cadence": "medium",
                "formality": "neutral",
                "vocabulary": "medium",
                "hedging": "low",
                "humor": "none",
                "directness": "balanced",
                "empathy": "moderate",
                "proactiveness": "moderate",
                "curiosity_drive": "high",
                "authority_level": "balanced",
                "stance_hints": []
            },
            "analytical": {
                "tone": "neutral",
                "cadence": "medium-fast",
                "formality": "semi-formal",
                "vocabulary": "high",
                "hedging": "low",
                "humor": "none",
                "directness": "direct",
                "empathy": "low",
                "proactiveness": "low",
                "curiosity_drive": "moderate",
                "authority_level": "assertive",
                "stance_hints": []
            },
            "supportive": {
                "tone": "warm",
                "cadence": "medium",
                "formality": "casual",
                "vocabulary": "medium",
                "hedging": "medium",
                "humor": "none",
                "directness": "balanced",
                "empathy": "high",
                "proactiveness": "high",
                "curiosity_drive": "high",
                "authority_level": "gentle",
                "stance_hints": []
            },
            "delegation_mode": {
                "tone": "neutral",
                "cadence": "medium-fast",
                "formality": "neutral",
                "vocabulary": "medium",
                "hedging": "low",
                "humor": "none",
                "directness": "direct",
                "empathy": "low",
                "proactiveness": "high",
                "curiosity_drive": "moderate",
                "authority_level": "assertive",
                "stance_hints": []
            }
        }

        return fallback_envelopes.get(intent, fallback_envelopes["default"])
