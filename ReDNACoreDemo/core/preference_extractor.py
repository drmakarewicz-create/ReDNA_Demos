"""
LLM-based preference extraction from conversation.

This module uses an LLM to extract structured preferences from user messages,
going beyond simple keyword matching to understand nuanced statements like:
- "I love comedies but hate horror films"
- "I'm tall with brown hair"
- "I usually watch sci-fi shows"
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from . import chat_providers

logger = logging.getLogger(__name__)


# Extraction prompt template
EXTRACTION_PROMPT = """You are analyzing a user's message to extract specific preferences and facts.

Extract ANY preferences, likes, dislikes, or factual statements about the person.

User message: "{message}"

Extract structured preferences in this JSON format:
{{
  "preferences": [
    {{
      "category": "entertainment.tv_genres" | "entertainment.movie_genres" | "entertainment.books" | "food" | "music" | "sports" | "physical_attributes" | "personality" | "lifestyle" | "other",
      "item": "specific thing they mentioned (e.g., 'comedy', 'pizza', 'tall')",
      "sentiment": "loves" | "likes" | "neutral" | "dislikes" | "hates",
      "value": 0-100 (0=hates, 25=dislikes, 50=neutral, 75=likes, 100=loves),
      "confidence": 0-100 (how sure you are about this extraction)
    }}
  ],
  "facts": [
    {{
      "category": "physical.height" | "physical.hair_color" | "physical.eye_color" | "age" | "location" | "occupation" | "relationship_status" | "other",
      "value": "the specific value or description",
      "confidence": 0-100
    }}
  ]
}}

Rules:
- Only extract if explicitly stated
- Do NOT infer beyond what's said
- Be conservative with confidence scores
- If nothing to extract, return empty arrays

Respond with ONLY the JSON, no other text."""


class PreferenceExtractor:
    """LLM-based preference and fact extractor."""

    def __init__(self, provider_name: str = "ollama"):
        """
        Initialize the preference extractor.

        Args:
            provider_name: Chat provider to use (default: ollama)
        """
        self.provider_name = provider_name
        self.provider = None

    def extract_preferences(
        self,
        message: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract preferences and facts from a user message using LLM.

        Args:
            message: User's message text
            user_id: Optional user identifier for logging

        Returns:
            Dict with "preferences" and "facts" arrays
        """
        if not message or not message.strip():
            return {"preferences": [], "facts": []}

        # Get chat provider
        if not self.provider:
            try:
                self.provider = chat_providers.get_provider(self.provider_name)
            except Exception as e:
                logger.error(f"Failed to get chat provider '{self.provider_name}': {e}")
                return {"preferences": [], "facts": []}

        # Build extraction prompt
        prompt = EXTRACTION_PROMPT.format(message=message)

        # Call LLM using streaming API
        try:
            messages = [{"role": "user", "content": prompt}]

            # Use lower temperature for more deterministic extraction
            # Collect streamed response
            response_chunks = []
            for chunk in self.provider.stream(
                system_prompt="",  # Prompt is in user message
                persona="",
                messages=messages,
                model=None,  # Use default
                temperature=0.3,
                max_tokens=800,
            ):
                response_chunks.append(chunk)

            response_text = "".join(response_chunks).strip()

            if not response_text:
                logger.warning(f"Empty LLM response for preference extraction")
                return {"preferences": [], "facts": []}

            # Parse JSON response
            try:
                extracted = json.loads(response_text)

                if not isinstance(extracted, dict):
                    logger.warning(f"LLM returned non-dict: {type(extracted)}")
                    return {"preferences": [], "facts": []}

                # Validate structure
                preferences = extracted.get("preferences", [])
                facts = extracted.get("facts", [])

                if not isinstance(preferences, list):
                    preferences = []
                if not isinstance(facts, list):
                    facts = []

                logger.info(
                    f"Extracted {len(preferences)} preferences and {len(facts)} facts "
                    f"from message for user {user_id or 'unknown'}"
                )

                return {
                    "preferences": preferences,
                    "facts": facts,
                }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                logger.debug(f"Response was: {response_text[:500]}")
                return {"preferences": [], "facts": []}

        except Exception as e:
            logger.error(f"LLM preference extraction failed: {e}", exc_info=True)
            return {"preferences": [], "facts": []}

    def preferences_to_observations(
        self,
        extracted: Dict[str, List[Dict[str, Any]]],
        timestamp: str,
        message: str,
    ) -> List[Dict[str, Any]]:
        """
        Convert extracted preferences to observation format for storage.

        Args:
            extracted: Output from extract_preferences()
            timestamp: ISO timestamp
            message: Original message text

        Returns:
            List of observation dicts compatible with conversation_analyzer format
        """
        observations = []

        # Convert preferences
        for pref in extracted.get("preferences", []):
            if not isinstance(pref, dict):
                continue

            category = pref.get("category", "other")
            item = pref.get("item", "")
            value = pref.get("value", 50)
            confidence = pref.get("confidence", 70)
            sentiment = pref.get("sentiment", "neutral")

            if not item:
                continue

            observations.append({
                "trait_category": "preferences",
                "signal": f"{sentiment} {item}",
                "preference_category": category,
                "preference_item": item,
                "preference_value": value,
                "confidence": confidence,
                "raw_text": message,
                "timestamp": timestamp,
                "extraction_method": "llm",
            })

        # Convert facts
        for fact in extracted.get("facts", []):
            if not isinstance(fact, dict):
                continue

            category = fact.get("category", "other")
            value = fact.get("value", "")
            confidence = fact.get("confidence", 70)

            if not value:
                continue

            observations.append({
                "trait_category": "facts",
                "signal": f"{category}: {value}",
                "fact_category": category,
                "fact_value": value,
                "confidence": confidence,
                "raw_text": message,
                "timestamp": timestamp,
                "extraction_method": "llm",
            })

        return observations


# Global extractor instance (lazy-loaded)
_extractor: Optional[PreferenceExtractor] = None


def extract_from_message(message: str, user_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convenience function to extract preferences from a message.

    Args:
        message: User's message text
        user_id: Optional user identifier

    Returns:
        Dict with "preferences" and "facts" arrays
    """
    global _extractor
    if _extractor is None:
        _extractor = PreferenceExtractor()

    return _extractor.extract_preferences(message, user_id)


def to_observations(
    extracted: Dict[str, List[Dict[str, Any]]],
    timestamp: str,
    message: str,
) -> List[Dict[str, Any]]:
    """
    Convenience function to convert extracted data to observations.

    Args:
        extracted: Output from extract_from_message()
        timestamp: ISO timestamp
        message: Original message text

    Returns:
        List of observation dicts
    """
    global _extractor
    if _extractor is None:
        _extractor = PreferenceExtractor()

    return _extractor.preferences_to_observations(extracted, timestamp, message)
