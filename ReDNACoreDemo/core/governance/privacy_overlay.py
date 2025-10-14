"""
Privacy Overlay Indicators - Phase 6

Visual indicators when sensitive DNA data is accessed.

Privacy levels:
- GREEN: Public data (SkillDNA, ProfDNA)
- YELLOW: Sensitive data (ChatDNA, RelationshipDNA)
- RED: Highly sensitive (PsyDNA, BeliefDNA)

Usage:
    level = check_privacy_level("PsyDNA")
    indicator = get_privacy_indicator(level)
    # Returns: {"color": "red", "label": "Highly Sensitive", "requires_consent": True}
"""

from enum import Enum
from typing import Dict, Any


class PrivacyLevel(str, Enum):
    """Privacy sensitivity levels."""

    PUBLIC = "public"  # Green
    SENSITIVE = "sensitive"  # Yellow
    HIGHLY_SENSITIVE = "highly_sensitive"  # Red


# DNA namespace privacy mappings
DNA_PRIVACY_LEVELS: Dict[str, PrivacyLevel] = {
    "SkillDNA": PrivacyLevel.PUBLIC,
    "ProfDNA": PrivacyLevel.PUBLIC,
    "ChatDNA": PrivacyLevel.SENSITIVE,
    "RelationshipDNA": PrivacyLevel.SENSITIVE,
    "PsyDNA": PrivacyLevel.HIGHLY_SENSITIVE,
    "BeliefDNA": PrivacyLevel.HIGHLY_SENSITIVE,
}


def check_privacy_level(namespace: str) -> PrivacyLevel:
    """
    Check privacy level for a DNA namespace.

    Args:
        namespace: DNA namespace (e.g., "PsyDNA")

    Returns:
        PrivacyLevel enum
    """
    return DNA_PRIVACY_LEVELS.get(namespace, PrivacyLevel.SENSITIVE)


def get_privacy_indicator(level: PrivacyLevel) -> Dict[str, Any]:
    """
    Get visual indicator for privacy level.

    Args:
        level: PrivacyLevel

    Returns:
        Dictionary with indicator properties
    """
    indicators = {
        PrivacyLevel.PUBLIC: {
            "color": "green",
            "hex": "#10b981",
            "label": "Public",
            "icon": "🟢",
            "requires_consent": False,
            "description": "Generally accessible data",
        },
        PrivacyLevel.SENSITIVE: {
            "color": "yellow",
            "hex": "#f59e0b",
            "label": "Sensitive",
            "icon": "🟡",
            "requires_consent": True,
            "description": "Requires explicit consent",
        },
        PrivacyLevel.HIGHLY_SENSITIVE: {
            "color": "red",
            "hex": "#ef4444",
            "label": "Highly Sensitive",
            "icon": "🔴",
            "requires_consent": True,
            "description": "Strictly controlled access",
        },
    }

    return indicators[level]


def get_namespace_indicator(namespace: str) -> Dict[str, Any]:
    """
    Get privacy indicator for a DNA namespace.

    Args:
        namespace: DNA namespace

    Returns:
        Dictionary with indicator properties
    """
    level = check_privacy_level(namespace)
    indicator = get_privacy_indicator(level)
    indicator["namespace"] = namespace
    return indicator


__all__ = [
    "PrivacyLevel",
    "check_privacy_level",
    "get_privacy_indicator",
    "get_namespace_indicator",
]
