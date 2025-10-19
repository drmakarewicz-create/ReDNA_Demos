"""
Head Coach <-> Trait System Bridge
====================================

Bidirectional bridge between Head Coach conversations and ReDNA trait system.

Direction 1: INGEST (Conversation → Traits)
- Extract preferences and facts from user messages
- Store as evidence with provenance
- Trigger trait updates

Direction 2: RETRIEVE (Traits → Conversation)
- Load relevant user traits
- Build context snippet for LLM
- Personalize responses based on known preferences
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from . import storage, trait_container_discovery

logger = logging.getLogger(__name__)


class HCTraitBridge:
    """Bridge between Head Coach conversations and ReDNA trait system."""

    def __init__(self):
        """Initialize the bridge."""
        pass

    # ============================================================================
    # DIRECTION 1: INGEST (Conversation → Traits)
    # ============================================================================

    def store_conversation_observations(
        self,
        user_id: str,
        observations: List[Dict[str, Any]],
        conversation_ts: str,
        message_text: str,
    ) -> int:
        """
        Store conversation observations as evidence in the trait system.

        Args:
            user_id: User identifier
            observations: List of extracted observations from conversation_analyzer
            conversation_ts: ISO timestamp of the conversation
            message_text: Original message text for provenance

        Returns:
            Number of evidence items created
        """
        if not observations:
            return 0

        # Load current user state
        resolved, evidence, obs = storage.read_user_state(user_id)

        evidence_items = evidence.get("items", [])
        items_added = 0

        for observation in observations:
            # Convert observation to evidence format
            evidence_item = self._observation_to_evidence(
                observation,
                conversation_ts,
                message_text
            )

            if evidence_item:
                evidence_items.append(evidence_item)
                items_added += 1

        # Save updated evidence
        evidence["items"] = evidence_items
        storage.write_user_state(user_id, resolved, evidence, obs)

        logger.info(f"Stored {items_added} conversation observations as evidence for user {user_id}")
        return items_added

    def _observation_to_evidence(
        self,
        observation: Dict[str, Any],
        timestamp: str,
        source_text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a conversation observation to evidence format.

        Args:
            observation: Observation dict from conversation_analyzer
            timestamp: ISO timestamp
            source_text: Original message text

        Returns:
            Evidence item dict or None if observation can't be converted
        """
        trait_category = observation.get("trait_category")
        signal = observation.get("signal")

        if not trait_category or not signal:
            return None

        # Handle LLM-extracted preferences (more specific)
        if trait_category == "preferences":
            return self._preference_to_evidence(observation, timestamp, source_text)

        # Handle LLM-extracted facts
        if trait_category == "facts":
            return self._fact_to_evidence(observation, timestamp, source_text)

        # Map keyword-based categories to trait paths
        trait_path_map = {
            "relationship": "social.relationship_status",
            "family": "social.family_focus",
            "work": "professional.career_focus",
            "emotional_tone": "personality.emotional_expression",
            "goals": "motivations.active_goals",
        }

        trait_path = trait_path_map.get(trait_category)
        if not trait_path:
            logger.warning(f"No trait path mapping for category: {trait_category}")
            return None

        # Build evidence item for keyword-based extraction
        evidence_item = {
            "trait_id": trait_path,
            "value": self._infer_value_from_signal(observation),
            "confidence": observation.get("confidence", 70),
            "provenance": {
                "source": "head_coach_conversation",
                "method": observation.get("extraction_method", "keyword_extraction"),
                "timestamp": timestamp,
                "raw_input": source_text,
                "signal": signal,
                "keywords_matched": observation.get("keywords_matched", []),
            },
            "timestamp": timestamp,
        }

        return evidence_item

    def _preference_to_evidence(
        self,
        observation: Dict[str, Any],
        timestamp: str,
        source_text: str,
    ) -> Optional[Dict[str, Any]]:
        """Convert LLM-extracted preference to evidence."""
        pref_category = observation.get("preference_category", "other")
        pref_item = observation.get("preference_item", "")
        pref_value = observation.get("preference_value", 50)
        confidence = observation.get("confidence", 80)

        if not pref_item:
            return None

        # Build trait path from category and item
        # e.g., "entertainment.tv_genres" + "comedy" → "preferences.entertainment.tv_genres.comedy"
        trait_path = f"preferences.{pref_category}.{pref_item.lower().replace(' ', '_')}"

        # Discover container for this trait path
        try:
            trait_container_discovery.discover_from_trait_path(
                trait_path,
                category="Preferences",
                description=f"{pref_category.replace('_', ' ').title()} preferences",
                sensitive=False
            )
        except Exception as e:
            logger.error(f"Container discovery failed for {trait_path}: {e}")

        return {
            "trait_id": trait_path,
            "value": pref_value,
            "confidence": confidence,
            "provenance": {
                "source": "head_coach_conversation",
                "method": "llm_extraction",
                "timestamp": timestamp,
                "raw_input": source_text,
                "signal": observation.get("signal", ""),
            },
            "timestamp": timestamp,
        }

    def _fact_to_evidence(
        self,
        observation: Dict[str, Any],
        timestamp: str,
        source_text: str,
    ) -> Optional[Dict[str, Any]]:
        """Convert LLM-extracted fact to evidence."""
        fact_category = observation.get("fact_category", "other")
        fact_value = observation.get("fact_value", "")
        confidence = observation.get("confidence", 80)

        if not fact_value:
            return None

        # Build trait path
        # e.g., "physical.hair_color" → "attributes.physical.hair_color"
        trait_path = f"attributes.{fact_category}"

        # Discover container for this fact
        try:
            # Determine if physical attribute is sensitive
            sensitive = "physical" in fact_category or "biometric" in fact_category
            trait_container_discovery.discover_from_trait_path(
                trait_path,
                category="Physical Attributes",
                description=f"{fact_category.replace('_', ' ').title()} attributes",
                sensitive=sensitive
            )
        except Exception as e:
            logger.error(f"Container discovery failed for {trait_path}: {e}")

        # For facts, we need to store the actual value, not a 0-100 scale
        # Use a high numeric value (90) to indicate "confirmed fact"
        return {
            "trait_id": trait_path,
            "value": 90,  # High value indicates confirmed
            "confidence": confidence,
            "provenance": {
                "source": "head_coach_conversation",
                "method": "llm_extraction",
                "timestamp": timestamp,
                "raw_input": source_text,
                "signal": observation.get("signal", ""),
                "fact_value": fact_value,  # Store actual value here
            },
            "timestamp": timestamp,
        }

    def _infer_value_from_signal(self, observation: Dict[str, Any]) -> int:
        """
        Infer a ReDNA value (0-100) from an observation signal.

        Args:
            observation: Observation dict

        Returns:
            Integer value 0-100
        """
        # For emotional tone, use valence and intensity
        if observation.get("trait_category") == "emotional_tone":
            intensity = observation.get("intensity", 3)
            valence = observation.get("valence", "neutral")

            if valence == "positive":
                # Positive emotions: 60-100 based on intensity
                return min(50 + (intensity * 10), 100)
            elif valence == "negative":
                # Negative emotions: 0-40 based on intensity
                return max(40 - (intensity * 10), 0)
            else:
                return 50  # Neutral

        # For presence/mention signals (relationship, family, work, goals)
        # Just marking that this topic is relevant to the user
        return 70  # Moderate signal that this area is active

    # ============================================================================
    # DIRECTION 2: RETRIEVE (Traits → Conversation)
    # ============================================================================

    def get_user_context_for_hc(
        self,
        user_id: str,
        conversation_topic: Optional[str] = None,
    ) -> str:
        """
        Build a user context snippet for Head Coach LLM context.

        Args:
            user_id: User identifier
            conversation_topic: Optional topic hint to prioritize relevant traits

        Returns:
            Formatted context string to inject into LLM prompt
        """
        # Load user traits
        resolved, _, _ = storage.read_user_state(user_id)

        if not resolved:
            return ""

        # Extract relevant preferences and traits
        relevant_traits = self._extract_relevant_traits(resolved, conversation_topic)

        if not relevant_traits:
            return ""

        # Build formatted context
        context_parts = ["WHAT YOU KNOW ABOUT THIS PERSON:"]

        for category, traits_in_category in relevant_traits.items():
            if traits_in_category:
                context_parts.append(f"\n{category}:")
                for trait_name, trait_value in traits_in_category.items():
                    context_parts.append(f"  - {trait_name}: {trait_value}")

        return "\n".join(context_parts)

    def _extract_relevant_traits(
        self,
        resolved: Dict[str, Any],
        topic: Optional[str] = None,
    ) -> Dict[str, Dict[str, str]]:
        """
        Extract relevant traits from resolved state, formatted for LLM context.

        Args:
            resolved: Resolved traits dict
            topic: Optional topic hint

        Returns:
            Dict of {category: {trait_name: human_readable_value}}
        """
        relevant = {}

        # Entertainment preferences
        entertainment_traits = self._extract_entertainment_preferences(resolved)
        if entertainment_traits:
            relevant["Entertainment"] = entertainment_traits

        # Relationship status/interests
        relationship_traits = self._extract_relationship_info(resolved)
        if relationship_traits:
            relevant["Relationships"] = relationship_traits

        # Career/work interests
        work_traits = self._extract_work_info(resolved)
        if work_traits:
            relevant["Work & Career"] = work_traits

        # Goals and aspirations
        goal_traits = self._extract_goal_info(resolved)
        if goal_traits:
            relevant["Goals"] = goal_traits

        return relevant

    def _extract_entertainment_preferences(self, resolved: Dict[str, Any]) -> Dict[str, str]:
        """Extract entertainment preferences (TV, movies, etc.)."""
        prefs = {}

        # Look for entertainment-related traits
        for trait_id, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            # Check for preference paths
            if "preferences.entertainment" in trait_id or "media." in trait_id:
                value = trait_data.get("value")
                if value is not None:
                    # Convert numeric value to human-readable
                    if isinstance(value, (int, float)):
                        if value >= 70:
                            pref_level = "loves"
                        elif value >= 50:
                            pref_level = "likes"
                        elif value <= 30:
                            pref_level = "dislikes"
                        else:
                            continue  # Skip neutral values

                        # Extract friendly name from trait_id
                        trait_name = trait_id.split(".")[-1].replace("_", " ").title()
                        prefs[trait_name] = pref_level

        return prefs

    def _extract_relationship_info(self, resolved: Dict[str, Any]) -> Dict[str, str]:
        """Extract relationship status and interests."""
        info = {}

        for trait_id, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            if "relationship" in trait_id.lower() or "social." in trait_id:
                value = trait_data.get("value")
                if value is not None and isinstance(value, (int, float)) and value >= 60:
                    trait_name = trait_id.split(".")[-1].replace("_", " ").title()
                    info[trait_name] = "active interest"

        return info

    def _extract_work_info(self, resolved: Dict[str, Any]) -> Dict[str, str]:
        """Extract work and career information."""
        info = {}

        for trait_id, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            if "professional." in trait_id or "career" in trait_id.lower():
                value = trait_data.get("value")
                if value is not None and isinstance(value, (int, float)) and value >= 60:
                    trait_name = trait_id.split(".")[-1].replace("_", " ").title()
                    info[trait_name] = "active interest"

        return info

    def _extract_goal_info(self, resolved: Dict[str, Any]) -> Dict[str, str]:
        """Extract goals and aspirations."""
        info = {}

        for trait_id, trait_data in resolved.items():
            if not isinstance(trait_data, dict):
                continue

            if "goals" in trait_id.lower() or "motivation" in trait_id.lower():
                value = trait_data.get("value")
                if value is not None and isinstance(value, (int, float)) and value >= 60:
                    trait_name = trait_id.split(".")[-1].replace("_", " ").title()
                    info[trait_name] = "active"

        return info


# Global bridge instance
_bridge = HCTraitBridge()


def store_observations(
    user_id: str,
    observations: List[Dict[str, Any]],
    timestamp: str,
    message_text: str,
) -> int:
    """
    Convenience function to store conversation observations.

    Args:
        user_id: User identifier
        observations: List of observations from conversation_analyzer
        timestamp: ISO timestamp
        message_text: Original message text

    Returns:
        Number of evidence items created
    """
    return _bridge.store_conversation_observations(user_id, observations, timestamp, message_text)


def get_user_context(user_id: str, topic: Optional[str] = None) -> str:
    """
    Convenience function to get user context for HC.

    Args:
        user_id: User identifier
        topic: Optional conversation topic

    Returns:
        Formatted context string
    """
    return _bridge.get_user_context_for_hc(user_id, topic)
