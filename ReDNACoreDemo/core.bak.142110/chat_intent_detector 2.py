"""
Chat Intent Detector
====================

Detects user intents from chat messages, particularly coach switching requests.
"""

import re
from typing import Optional, Dict, Any

# Coach name mappings
COACH_PATTERNS = {
    "photo_coach": [
        r"\bphoto\s+coach\b",
        r"\bphoto\b.*\bcoach\b",
        r"\bappearance\s+coach\b",
        r"\bvisual\s+coach\b",
    ],
    "relationship_coach": [
        r"\brelationship\s+coach\b",
        r"\brelationship\b.*\bcoach\b",
        r"\brc\b",  # Common abbreviation
        r"\bemotional\s+coach\b",
        r"\bpsych.*coach\b",
    ],
    "personality_test_coach": [
        r"\bpersonality\s+(?:test\s+)?coach\b",
        r"\bpersonality\b.*\bcoach\b",
        r"\btest\s+coach\b",
    ],
    "career_coach": [
        r"\bcareer\s+coach\b",
        r"\bcareer\b.*\bcoach\b",
        r"\bprofessional\s+coach\b",
        r"\bwork\s+coach\b",
    ],
}

# Switching intent patterns
SWITCH_PATTERNS = [
    r"\bswitch\s+(?:to|mode|coach)",
    r"\btalk\s+(?:to|with)\s+(?:the\s+)?(\w+)",
    r"\bconnect\s+(?:me\s+)?(?:to|with)\s+(?:the\s+)?(\w+)",
    r"\bgo\s+to\s+(?:the\s+)?(\w+)",
    r"\buse\s+(?:the\s+)?(\w+)",
    r"\bmove\s+to\s+(?:the\s+)?(\w+)",
    r"\bchange\s+to\s+(?:the\s+)?(\w+)",
]


def detect_coach_switch_intent(message: str) -> Optional[Dict[str, Any]]:
    """
    Detect if the user is requesting to switch coaches.

    Args:
        message: User's chat message

    Returns:
        Dict with detected intent or None if no intent detected:
        {
            "intent": "switch_coach",
            "target_coach": "career_coach",
            "confidence": 0.9
        }
    """
    message_lower = message.lower()

    # First check if there's any switching language
    has_switch_intent = False
    for pattern in SWITCH_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            has_switch_intent = True
            break

    if not has_switch_intent:
        return None

    # Now find which coach they're referring to
    for coach_id, patterns in COACH_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                # Calculate confidence based on explicitness
                confidence = 0.9 if "switch" in message_lower or "connect" in message_lower else 0.7

                return {
                    "intent": "switch_coach",
                    "target_coach": coach_id,
                    "confidence": confidence,
                    "user_message": message
                }

    # User wants to switch but didn't specify which coach
    return {
        "intent": "switch_coach_unspecified",
        "confidence": 0.5,
        "user_message": message
    }


def detect_coach_inquiry_intent(message: str) -> Optional[Dict[str, Any]]:
    """
    Detect if the user is asking about available coaches.

    Returns:
        Dict with detected intent or None
    """
    message_lower = message.lower()

    inquiry_patterns = [
        r"\bwhat\s+coaches",
        r"\bwhich\s+coaches",
        r"\bavailable\s+coaches",
        r"\blist\s+(?:of\s+)?coaches",
        r"\btell\s+me\s+about.*coaches",
        r"\bshow\s+me.*coaches",
    ]

    for pattern in inquiry_patterns:
        if re.search(pattern, message_lower, re.IGNORECASE):
            return {
                "intent": "list_coaches",
                "confidence": 0.8,
                "user_message": message
            }

    return None
