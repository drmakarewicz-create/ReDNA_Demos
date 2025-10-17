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


# Phase 4.0a: Post-processing filter configuration
CONF_MIN = 0.70  # Minimum confidence threshold (0-1 scale)

# Phatic/acknowledgment phrases that should not trigger extractions
PHATIC_PHRASES = {
    "got it", "thanks", "okay", "sure", "sounds good", "great", "cool", "nice",
    "alright", "perfect", "understood", "yes", "no", "maybe", "k", "ok",
    "thank you", "ty", "thx", "awesome", "sweet", "right", "good", "fine",
}

# Canonical schema whitelist (Phase 4.0a Iteration 1 - expanded for recall)
CANONICAL_SCHEMA = {
    # Physical traits
    "PaDNA.EyeDNA.IrisColor",
    "PaDNA.HairDNA.Color.Natural",
    "PaDNA.BodyDNA.Height",

    # Demographics
    "BasicDNA.Age",
    "BasicDNA.Gender",
    "BasicDNA.RelationshipStatus",
    "BasicDNA.Location.City",
    "BasicDNA.Occupation",

    # Sleep & Routine
    "BehaviorDNA.Sleep.Chronotype",
    "BehaviorDNA.Sleep.Duration",
    "BehaviorDNA.Schedule.WorkHours",
    "BehaviorDNA.Routine.Morning",

    # Exercise & Fitness
    "BehaviorDNA.Exercise.Outdoor",
    "BehaviorDNA.Exercise.Frequency",
    "BehaviorDNA.Exercise.Type",
    "BehaviorDNA.Fitness.Level",

    # Social & Leisure
    "BehaviorDNA.Leisure.Indoor",
    "BehaviorDNA.Social.Style",
    "PreferenceDNA.Social.GroupSize",

    # Health & Wellness
    "BehaviorDNA.Health.Diet",
    "BehaviorDNA.Health.CaffeineIntake",
    "BehaviorDNA.Health.Commitment",
    "BehaviorDNA.Wellness.ColdTherapy",

    # Work
    "BehaviorDNA.Work.Location",

    # Communication & Organization
    "BehaviorDNA.Communication.ResponseStyle",
    "BehaviorDNA.Organization.Level",
    "BehaviorDNA.Learning.Style",

    # Food Preferences
    "PreferenceDNA.Food.Pizza",
    "PreferenceDNA.Food.AsianCuisine",
}

# Value whitelists for specific traits
VALUE_WHITELISTS = {
    "BehaviorDNA.Work.Location": {"remote", "onsite", "office", "hybrid"},
    "BehaviorDNA.Health.Diet": {"vegetarian", "vegan", "pescatarian", "keto", "omnivore", "gluten_free"},
    "PreferenceDNA.Social.GroupSize": {"small", "large", "one-on-one"},
    "BehaviorDNA.Sleep.Chronotype": {"morning", "evening", "neutral"},
    "BehaviorDNA.Exercise.Frequency": {"daily", "weekly", "2_per_week", "monthly", "rarely"},
}


def _filter_and_map_extractions(
    extracted: Dict[str, List[Dict[str, Any]]],
    message: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Phase 4.0a: Post-processing filter for extracted traits.

    Filters:
    1. Confidence gate (≥ CONF_MIN)
    2. Phatic/acknowledgment filter
    3. Schema whitelist
    4. Value sanity checks

    Args:
        extracted: Raw LLM extraction output
        message: Original user message

    Returns:
        Filtered extraction dict
    """
    # Filter 1: Phatic/ack detection - drop all extractions if message is conversational
    msg_lower = message.lower().strip()
    if any(phrase in msg_lower for phrase in PHATIC_PHRASES):
        # Check if the message ONLY contains phatic content (not mixed with facts)
        if len(msg_lower.split()) <= 3:  # Short phatic messages
            logger.debug(f"Phatic filter: Dropping extractions for '{message}'")
            return {"preferences": [], "facts": []}

    filtered_prefs = []
    filtered_facts = []

    # Filter preferences
    for pref in extracted.get("preferences", []):
        # Filter 2: Confidence gate
        conf = pref.get("confidence", 0) / 100.0  # Convert 0-100 to 0-1
        if conf < CONF_MIN:
            logger.debug(f"Confidence filter: Skipping {pref.get('category')} (conf={conf:.2f} < {CONF_MIN})")
            continue

        # Filter 3: Schema whitelist
        trait_id = pref.get("category", "")
        if trait_id not in CANONICAL_SCHEMA:
            logger.debug(f"Schema filter: Skipping non-canonical trait '{trait_id}'")
            continue

        # Filter 4: Value sanity check
        if trait_id in VALUE_WHITELISTS:
            item_val = str(pref.get("item", "")).lower()
            if item_val not in VALUE_WHITELISTS[trait_id]:
                logger.debug(f"Value filter: Skipping {trait_id}='{item_val}' (not in whitelist)")
                continue

        filtered_prefs.append(pref)

    # Filter facts
    for fact in extracted.get("facts", []):
        # Filter 2: Confidence gate
        conf = fact.get("confidence", 0) / 100.0
        if conf < CONF_MIN:
            logger.debug(f"Confidence filter: Skipping fact {fact.get('category')} (conf={conf:.2f} < {CONF_MIN})")
            continue

        # Filter 3: Schema whitelist
        trait_id = fact.get("category", "")
        if trait_id not in CANONICAL_SCHEMA:
            logger.debug(f"Schema filter: Skipping non-canonical fact '{trait_id}'")
            continue

        # Filter 4: Value sanity check
        if trait_id in VALUE_WHITELISTS:
            fact_val = str(fact.get("value", "")).lower()
            if fact_val not in VALUE_WHITELISTS[trait_id]:
                logger.debug(f"Value filter: Skipping {trait_id}='{fact_val}' (not in whitelist)")
                continue

        filtered_facts.append(fact)

    return {"preferences": filtered_prefs, "facts": filtered_facts}


# Extraction prompt template (Phase 4.0a - Canonical Schema + Few-Shot)
EXTRACTION_PROMPT = """You are analyzing a user's message to extract preferences and factual traits.

CRITICAL: Use ONLY canonical trait IDs from the schema below. Never invent new namespaces.

User message: "{message}"

CANONICAL TRAIT SCHEMA:
- PaDNA.EyeDNA.IrisColor (eye color: blue, brown, green, hazel, gray)
- PaDNA.HairDNA.Color.Natural (hair color: blonde, brown, black, red, gray)
- PaDNA.BodyDNA.Height (height: "6 feet", "tall", or numeric)
- BasicDNA.Age (age: "30", "early 30s", "25-34")
- BasicDNA.Gender (gender: male, female, non-binary)
- BasicDNA.RelationshipStatus (status: single, married, divorced)
- BasicDNA.Location.City (city of residence)
- BasicDNA.Occupation (job/profession)
- BehaviorDNA.Sleep.Chronotype (morning/evening person: morning, evening, neutral)
- BehaviorDNA.Schedule.WorkHours (work schedule)
- BehaviorDNA.Routine.Morning (morning routine elements)
- BehaviorDNA.Exercise.Outdoor (outdoor exercise: hiking, running)
- BehaviorDNA.Exercise.Frequency (frequency: daily, weekly, 2_per_week, monthly, rarely)
- BehaviorDNA.Exercise.Type (exercise type)
- BehaviorDNA.Fitness.Level (fitness: moderate, high, athletic)
- BehaviorDNA.Leisure.Indoor (indoor activities: true if prefers indoor)
- BehaviorDNA.Social.Style (social: introvert, extrovert, ambivert)
- PreferenceDNA.Social.GroupSize (group size: small, large, one-on-one)
- BehaviorDNA.Wellness.ColdTherapy (cold therapy: true if practices)
- BehaviorDNA.Health.Diet (diet: vegetarian, vegan, pescatarian, omnivore)
- BehaviorDNA.Health.CaffeineIntake (caffeine consumption)
- BehaviorDNA.Work.Location (work: remote, office, hybrid)
- BehaviorDNA.Communication.ResponseStyle (communication: prompt, delayed)
- BehaviorDNA.Organization.Level (organization: high, moderate, low)
- BehaviorDNA.Learning.Style (learning: visual, kinesthetic, auditory)
- PreferenceDNA.Food.Pizza (pizza preference: true/false)
- PreferenceDNA.Food.AsianCuisine (asian food preference)

FEW-SHOT EXAMPLES:
1. "I'm a morning person" → BehaviorDNA.Sleep.Chronotype: morning (conf: 70)
2. "I start work at 6 AM" → BehaviorDNA.Schedule.WorkHours: "6 AM" + BehaviorDNA.Sleep.Chronotype: morning (conf: 60)
3. "I usually stay in and read" → BehaviorDNA.Leisure.Indoor: true + PreferenceDNA.Social.GroupSize: small (conf: 50)
4. "I don't eat meat" → BehaviorDNA.Health.Diet: vegetarian (conf: 85)
5. "I take cold showers every morning" → BehaviorDNA.Wellness.ColdTherapy: true (conf: 90)
6. "I work from home" → BehaviorDNA.Work.Location: remote (conf: 80)
7. "I'm married" → BasicDNA.RelationshipStatus: married (conf: 90)
8. "I have blue eyes" → PaDNA.EyeDNA.IrisColor: blue (conf: 90)

Extract in this JSON format:
{{
  "preferences": [
    {{
      "category": "<canonical_trait_id>",
      "item": "<specific value>",
      "sentiment": "loves" | "likes" | "neutral" | "dislikes" | "hates",
      "value": 0-100,
      "confidence": 0-100
    }}
  ],
  "facts": [
    {{
      "category": "<canonical_trait_id>",
      "value": "<specific value or description>",
      "confidence": 0-100
    }}
  ]
}}

RULES:
1. Use ONLY canonical trait IDs from schema above
2. Extract 1-3 traits per message (avoid over-extraction)
3. For frequency: use daily, weekly, 2_per_week, monthly, rarely
4. Only extract if explicitly stated or strongly implied
5. Confidence 0-100: 90-100=direct fact, 60-80=clear, 30-50=implied, <30=uncertain
6. If nothing to extract, return empty arrays

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

                # Phase 4.0a: Apply post-processing filters
                raw_result = {
                    "preferences": preferences,
                    "facts": facts,
                }
                filtered_result = _filter_and_map_extractions(raw_result, message)

                filtered_prefs = len(filtered_result.get("preferences", []))
                filtered_facts = len(filtered_result.get("facts", []))
                if filtered_prefs != len(preferences) or filtered_facts != len(facts):
                    logger.info(
                        f"Post-filter: {len(preferences)}→{filtered_prefs} prefs, "
                        f"{len(facts)}→{filtered_facts} facts"
                    )

                return filtered_result

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

            # Map LLM categories to trait_id format expected by mapper
            # physical.eye_color -> attributes.physical.eye_color
            # physical.hair_color -> attributes.physical.hair_color
            category_map = {
                "physical.eye_color": "attributes.physical.eye_color",
                "physical.hair_color": "attributes.physical.hair_color",
                "physical.height": "attributes.physical.height",
                "age": "attributes.age",
                "gender": "attributes.gender",
                "orientation": "attributes.orientation",
                "relationship_status": "attributes.relationship_status",
            }

            trait_id = category_map.get(category, f"attributes.{category}")

            observations.append({
                "trait_id": trait_id,
                "fact_value": value,
                "confidence": confidence,
                "raw_text": message,
                "timestamp": timestamp,
                "extraction_method": "llm",
                "signal": f"{category}: {value}",  # Keep for debugging
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
