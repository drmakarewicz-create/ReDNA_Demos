"""
Conversation analyzer for extracting trait signals from user messages.

This module provides basic keyword-based extraction of observations
from Head Coach chat conversations.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


class ConversationAnalyzer:
    """Analyzes user messages to extract trait signals and observations."""

    # Relationship-related keywords
    RELATIONSHIP_KEYWORDS = {
        "dating", "partner", "boyfriend", "girlfriend", "husband", "wife",
        "relationship", "romance", "romantic", "date", "marriage", "married",
        "single", "divorced", "engaged", "crush", "love", "attraction"
    }

    # Family-related keywords
    FAMILY_KEYWORDS = {
        "family", "mom", "dad", "mother", "father", "parent", "parents",
        "sibling", "brother", "sister", "son", "daughter", "kids", "children",
        "grandparent", "grandmother", "grandfather", "relatives"
    }

    # Work/career-related keywords
    WORK_KEYWORDS = {
        "work", "job", "career", "office", "boss", "colleague", "coworker",
        "employee", "employer", "business", "company", "professional",
        "workplace", "hired", "fired", "promotion", "salary"
    }

    # Positive emotional keywords
    POSITIVE_EMOTIONS = {
        "happy", "great", "awesome", "excellent", "wonderful", "fantastic",
        "amazing", "love", "excited", "thrilled", "joy", "glad", "grateful",
        "thankful", "blessed", "fortunate", "lucky"
    }

    # Negative emotional keywords
    NEGATIVE_EMOTIONS = {
        "sad", "unhappy", "depressed", "frustrated", "angry", "mad",
        "upset", "disappointed", "worried", "anxious", "stressed",
        "nervous", "scared", "afraid", "hate", "terrible", "awful",
        "struggling", "tough", "hard", "difficult", "challenging"
    }

    # Desire/goal keywords
    DESIRE_KEYWORDS = {
        "want", "wish", "hope", "desire", "need", "looking for",
        "trying to", "hoping to", "would like", "seeking", "searching"
    }

    def __init__(self):
        """Initialize the conversation analyzer."""
        pass

    def extract_observations(
        self,
        user_id: str,
        message: str,
        timestamp: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract observations from a user message.

        Args:
            user_id: The ID of the user
            message: The user's message text
            timestamp: Optional ISO timestamp (defaults to now)

        Returns:
            List of observation dictionaries
        """
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        observations = []
        message_lower = message.lower()

        # Extract relationship signals
        if self._contains_keywords(message_lower, self.RELATIONSHIP_KEYWORDS):
            observations.append({
                "trait_category": "relationship",
                "signal": "mentioned romantic relationships",
                "raw_text": message,
                "timestamp": timestamp,
                "keywords_matched": self._get_matched_keywords(message_lower, self.RELATIONSHIP_KEYWORDS)
            })

        # Extract family signals
        if self._contains_keywords(message_lower, self.FAMILY_KEYWORDS):
            observations.append({
                "trait_category": "family",
                "signal": "mentioned family",
                "raw_text": message,
                "timestamp": timestamp,
                "keywords_matched": self._get_matched_keywords(message_lower, self.FAMILY_KEYWORDS)
            })

        # Extract work/career signals
        if self._contains_keywords(message_lower, self.WORK_KEYWORDS):
            observations.append({
                "trait_category": "work",
                "signal": "mentioned work or career",
                "raw_text": message,
                "timestamp": timestamp,
                "keywords_matched": self._get_matched_keywords(message_lower, self.WORK_KEYWORDS)
            })

        # Extract emotional tone
        positive_intensity = self._count_keywords(message_lower, self.POSITIVE_EMOTIONS)
        negative_intensity = self._count_keywords(message_lower, self.NEGATIVE_EMOTIONS)

        if positive_intensity > 0 or negative_intensity > 0:
            if positive_intensity > negative_intensity:
                valence = "positive"
                intensity = positive_intensity
                keywords = self._get_matched_keywords(message_lower, self.POSITIVE_EMOTIONS)
            else:
                valence = "negative"
                intensity = negative_intensity
                keywords = self._get_matched_keywords(message_lower, self.NEGATIVE_EMOTIONS)

            observations.append({
                "trait_category": "emotional_tone",
                "signal": f"{valence} emotional expression",
                "valence": valence,
                "intensity": min(intensity, 5),  # Cap at 5
                "raw_text": message,
                "timestamp": timestamp,
                "keywords_matched": keywords
            })

        # Extract desires/goals
        if self._contains_keywords(message_lower, self.DESIRE_KEYWORDS):
            observations.append({
                "trait_category": "goals",
                "signal": "expressed desire or goal",
                "raw_text": message,
                "timestamp": timestamp,
                "keywords_matched": self._get_matched_keywords(message_lower, self.DESIRE_KEYWORDS)
            })

        return observations

    def _contains_keywords(self, text: str, keywords: set) -> bool:
        """Check if text contains any of the keywords."""
        # Use word boundaries to avoid partial matches
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _count_keywords(self, text: str, keywords: set) -> int:
        """Count how many keywords appear in the text."""
        count = 0
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            count += len(re.findall(pattern, text, re.IGNORECASE))
        return count

    def _get_matched_keywords(self, text: str, keywords: set) -> List[str]:
        """Get list of keywords that matched in the text."""
        matched = []
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                matched.append(keyword)
        return matched


# Global analyzer instance
_analyzer = ConversationAnalyzer()


def analyze_message(user_id: str, message: str, timestamp: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to analyze a message and extract observations.

    Args:
        user_id: The ID of the user
        message: The user's message text
        timestamp: Optional ISO timestamp

    Returns:
        List of observation dictionaries
    """
    return _analyzer.extract_observations(user_id, message, timestamp)
