"""
Trait ontology and metadata lookup.

This module provides canonical trait specifications including:
- Type (enum, number, text)
- Valid enum values
- Default UCN priors
- Other metadata for resolver decisions

Expand this as the trait map grows.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional


# Canonical trait specifications
_TRAITS: Dict[str, Dict[str, Any]] = {
    # Physical Appearance DNA
    "PaDNA.EyeDNA.IrisColor": {
        "type": "enum",
        "enums": ["blue", "green", "hazel", "brown", "gray", "amber"],
        "ucn_prior": 0.25,
        "category": "physical_appearance"
    },
    "PaDNA.EyeDNA.Shape": {
        "type": "enum",
        "enums": ["almond", "round", "hooded", "monolid", "upturned", "downturned"],
        "ucn_prior": 0.25,
        "category": "physical_appearance"
    },
    "PaDNA.HairDNA.Color": {
        "type": "enum",
        "enums": ["black", "brown", "blonde", "red", "gray", "white"],
        "ucn_prior": 0.25,
        "category": "physical_appearance"
    },
    "PaDNA.HairDNA.Texture": {
        "type": "enum",
        "enums": ["straight", "wavy", "curly", "coily"],
        "ucn_prior": 0.25,
        "category": "physical_appearance"
    },
    "PaDNA.HairDNA.Length": {
        "type": "enum",
        "enums": ["short", "medium", "long", "bald"],
        "ucn_prior": 0.25,
        "category": "physical_appearance"
    },
    "PaDNA.Height": {
        "type": "number",
        "unit": "cm",
        "ucn_prior": 0.2,
        "category": "physical_appearance"
    },
    "PaDNA.Build": {
        "type": "enum",
        "enums": ["slim", "athletic", "average", "stocky", "heavy"],
        "ucn_prior": 0.25,
        "category": "physical_appearance"
    },

    # Personality DNA - Big Five
    "PeDNA.BigFive.Openness": {
        "type": "number",
        "range": [0, 100],
        "ucn_prior": 0.15,
        "category": "personality"
    },
    "PeDNA.BigFive.Conscientiousness": {
        "type": "number",
        "range": [0, 100],
        "ucn_prior": 0.15,
        "category": "personality"
    },
    "PeDNA.BigFive.Extraversion": {
        "type": "number",
        "range": [0, 100],
        "ucn_prior": 0.15,
        "category": "personality"
    },
    "PeDNA.BigFive.Agreeableness": {
        "type": "number",
        "range": [0, 100],
        "ucn_prior": 0.15,
        "category": "personality"
    },
    "PeDNA.BigFive.Neuroticism": {
        "type": "number",
        "range": [0, 100],
        "ucn_prior": 0.15,
        "category": "personality"
    },

    # Basic DNA
    "BasicDNA.Age": {
        "type": "number",
        "unit": "years",
        "ucn_prior": 0.3,
        "category": "basic"
    },
    "BasicDNA.Gender": {
        "type": "enum",
        "enums": ["male", "female", "non-binary", "other"],
        "ucn_prior": 0.4,
        "category": "basic"
    },
    "BasicDNA.Name": {
        "type": "text",
        "ucn_prior": 0.5,
        "category": "basic"
    },
    "BasicDNA.Location": {
        "type": "text",
        "ucn_prior": 0.3,
        "category": "basic"
    },
    "BasicDNA.Orientation": {
        "type": "enum",
        "enums": ["heterosexual", "homosexual", "bisexual", "pansexual", "asexual", "other"],
        "ucn_prior": 0.3,
        "category": "basic"
    },
    "BasicDNA.RelationshipStatus": {
        "type": "enum",
        "enums": ["single", "dating", "in_relationship", "engaged", "married", "divorced", "widowed"],
        "ucn_prior": 0.35,
        "category": "basic"
    },

    # Interests DNA
    "InterestsDNA.Hobbies": {
        "type": "text",
        "ucn_prior": 0.2,
        "category": "interests"
    },
    "InterestsDNA.Sports": {
        "type": "text",
        "ucn_prior": 0.2,
        "category": "interests"
    },
    "InterestsDNA.Music": {
        "type": "text",
        "ucn_prior": 0.2,
        "category": "interests"
    },
    "InterestsDNA.Movies": {
        "type": "text",
        "ucn_prior": 0.2,
        "category": "interests"
    },
}


def get_trait_spec(trait_id: str) -> Dict[str, Any]:
    """
    Get canonical specification for a trait.

    Args:
        trait_id: Canonical trait ID

    Returns:
        Trait spec dict with type, enums (if applicable), ucn_prior, etc.
        Returns a default spec if trait_id is not found.
    """
    return _TRAITS.get(trait_id, {
        "type": "text",
        "ucn_prior": 0.2,
        "category": "unknown"
    })


def get_all_trait_ids() -> List[str]:
    """Get list of all known trait IDs."""
    return list(_TRAITS.keys())


def get_traits_by_category(category: str) -> Dict[str, Dict[str, Any]]:
    """Get all traits in a given category."""
    return {
        tid: spec
        for tid, spec in _TRAITS.items()
        if spec.get("category") == category
    }
