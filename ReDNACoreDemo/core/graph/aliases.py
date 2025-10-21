"""
Trait ID aliases for cross-namespace compatibility.

Some traits are stored under different namespaces in different systems:
- UCNRR uses BehaviorDNA.Sleep.Chronotype
- Graph uses PaDNA.Chronotype

Phase 10: Added hierarchy aliases for ReDNA redefinition:
- RelationalDNA → RelDNA (legacy compatibility)
- Relational DNA → RelDNA (string label compatibility)

This module provides bidirectional mapping for read-time alias resolution.
"""

from typing import List, Set

# Bidirectional alias map: trait_id -> list of equivalent trait_ids
# Each entry should include both directions for easy lookup
TRAIT_ALIASES = {
    # Chronotype aliases
    "PaDNA.Chronotype": ["BehaviorDNA.Sleep.Chronotype"],
    "BehaviorDNA.Sleep.Chronotype": ["PaDNA.Chronotype"],

    # Phase 10: DNA category aliases (hierarchy redefinition)
    "RelDNA": ["RelationalDNA", "Relational DNA"],
    "RelationalDNA": ["RelDNA"],
    "BehDNA": ["BehaviorDNA"],
    "BehaviorDNA": ["BehDNA"],

    # Add more aliases here as needed
    # Example:
    # "PaDNA.EyeColor": ["PaDNA.EyeDNA.IrisColor"],
    # "PaDNA.EyeDNA.IrisColor": ["PaDNA.EyeColor"],
}


def get_all_aliases(trait_id: str) -> List[str]:
    """
    Get all aliases for a given trait_id, including the original trait_id.

    Args:
        trait_id: The trait ID to expand

    Returns:
        List of trait IDs including the original and all aliases

    Example:
        >>> get_all_aliases("PaDNA.Chronotype")
        ["PaDNA.Chronotype", "BehaviorDNA.Sleep.Chronotype"]
        >>> get_all_aliases("BehaviorDNA.Sleep.Chronotype")
        ["BehaviorDNA.Sleep.Chronotype", "PaDNA.Chronotype"]
    """
    aliases = TRAIT_ALIASES.get(trait_id, [])
    # Always include the original trait_id
    result = [trait_id] + aliases
    # Deduplicate while preserving order
    seen: Set[str] = set()
    return [t for t in result if not (t in seen or seen.add(t))]  # type: ignore


def get_canonical_trait_id(trait_id: str) -> str:
    """
    Get the canonical (preferred) trait ID for a given alias.

    Currently prefers PaDNA.* over BehaviorDNA.* when available.

    Args:
        trait_id: Any trait ID or alias

    Returns:
        The canonical trait ID (PaDNA namespace preferred)

    Example:
        >>> get_canonical_trait_id("BehaviorDNA.Sleep.Chronotype")
        "PaDNA.Chronotype"
        >>> get_canonical_trait_id("PaDNA.Chronotype")
        "PaDNA.Chronotype"
    """
    all_aliases = get_all_aliases(trait_id)

    # Prefer PaDNA namespace
    for alias in all_aliases:
        if alias.startswith("PaDNA."):
            return alias

    # Otherwise return the original
    return trait_id
