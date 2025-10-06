# shared/hierarchy_v33.py
"""
Shared hierarchy for ReDNA v3.3 — minimal but extensible.
Both Core and UCN/RR import from here so they stay in sync.
"""

from __future__ import annotations
from typing import Dict, List

# Five umbrellas (v3.3)
TOP_LEVEL_DNAS: List[str] = ["IntDNA", "PaDNA", "EmDNA", "PsyDNA", "SpDNA"]

# Non-exhaustive children (safe to add more; unknown leaves still work via dot-path fallback)
CHILDREN: Dict[str, List[str]] = {
    # Interpersonal
    "IntDNA": [
        "RomanticStatus",  # e.g., "married"
        # add more interpersonal leaves as your spec expands…
    ],
    # Physical
    "PaDNA": [
        "Age",
        "SkinTone",
        "Height",
        "Weight",
        "Looks",
        "Language",  # parent: "LangDNA" in earlier notes; using simple "Language" leaf is OK
    ],
    # Emotional
    "EmDNA": [
        "Affect",
        "Regulation",
        "Attachment",
    ],
    # Psychological
    "PsyDNA": [
        "Personality",
        "Habits",
        "MentalHealth",
        "Education",
        "Preferences",
        "Orientation",
        "Tech",
    ],
    # Spiritual
    "SpDNA": [
        "Religion",
        "Spirituality",
        "Existential",
    ],
}


def is_top_level(name: str) -> bool:
    return name in TOP_LEVEL_DNAS


def infer_path_from_name(dna_name: str) -> List[str]:
    """
    Best-effort inference:
      - If name already looks like 'Umbrella.Leaf', split it.
      - If name itself is a top-level umbrella, return [name].
      - Else try to match to a known child; otherwise treat the whole name as a leaf without umbrella.
    """
    if "." in dna_name:
        parts = [p.strip() for p in dna_name.split(".") if p.strip()]
        return parts if parts else [dna_name]

    if is_top_level(dna_name):
        return [dna_name]

    # Try to find which umbrella claims this child
    for umbrella, kids in CHILDREN.items():
        if dna_name in kids:
            return [umbrella, dna_name]

    # Unknown leaf — leave as single-segment path so downstream can still store it
    return [dna_name]