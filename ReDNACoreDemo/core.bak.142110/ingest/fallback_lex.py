"""
Fallback lexical extractor for critical traits.

Used as a safety net when the primary LLM extractor returns zero evidence.
Handles common factual statements like "I have blue eyes", "My hair is brown", "I am 47".

This is minimal by design - only high-signal patterns for critical traits.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any


# Controlled vocabularies for normalization
EYE_COLORS = {"blue", "green", "brown", "hazel", "gray", "grey", "amber"}
HAIR_COLORS = {"blonde", "blond", "brown", "black", "red", "auburn", "gray", "grey", "white"}
HAIR_LENGTHS = {"short", "medium", "long", "bald"}


def _tokenize(s: str) -> str:
    """Normalize text for pattern matching."""
    return re.sub(r"[^a-z0-9_ ]+", "", s.lower()).strip()


def fallback_extract(text: str) -> List[Dict[str, Any]]:
    """
    Minimal lexical extraction for common high-signal traits.

    Returns canonical Evidence records with PaDNA/BasicDNA IDs.
    Only used when the primary extractor yields 0 items.

    Args:
        text: User message text

    Returns:
        List of evidence dicts with trait_id and value
    """
    s = _tokenize(text)
    out: List[Dict[str, Any]] = []

    # Eye color patterns: "I have blue eyes", "my eyes are green", "eyes: brown"
    m_eye = re.search(
        r"\b(eye[s]?\s*(are|is|=|:)?\s*|i have\s+)(blue|green|brown|hazel|gray|grey|amber)(\s+eyes)?\b",
        s
    )
    if m_eye:
        color = m_eye.group(3)
        # Normalize grey -> gray
        color = "gray" if color == "grey" else color
        out.append({
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "value": {"enum": color}
        })

    # Hair color patterns: "my hair is brown", "I have black hair", "hair: blonde"
    m_hair = re.search(
        r"\b(hair\s*(are|is|=|:)?\s*|my\s+hair\s*(is|=|:)?\s*|i have\s+)(blonde|blond|brown|black|red|auburn|gray|grey|white)(\s+hair)?\b",
        s
    )
    if m_hair:
        color = m_hair.group(4)
        # Normalize variants
        color = "gray" if color == "grey" else ("blonde" if color == "blond" else color)
        out.append({
            "trait_id": "PaDNA.HairDNA.Color",
            "value": {"enum": color}
        })

    # Hair length patterns: "I have short hair", "my hair is long"
    m_hair_len = re.search(
        r"\b(hair\s*(is|=|:)?\s*|i have\s+|my\s+hair\s+is\s+)(short|medium|long)(\s+hair)?\b",
        s
    )
    if m_hair_len:
        length = m_hair_len.group(3)
        out.append({
            "trait_id": "PaDNA.HairDNA.Length",
            "value": {"enum": length}
        })

    # Bald/balding patterns: "I'm bald", "pretty bald", "shaved head"
    if re.search(r"\b(bald|balding)\b", s):
        out.append({
            "trait_id": "PaDNA.HairDNA.Bald",
            "value": {"enum": "true"}
        })

    if re.search(r"\bshaved\s+head\b", s) or "hairless" in s:
        out.append({
            "trait_id": "PaDNA.HairDNA.BaldPattern",
            "value": {"enum": "shaved"}
        })

    # Age patterns: "I am 47", "I'm 47", "age: 47", "47 years old"
    m_age = re.search(
        r"\b(i am|i'm|im|age is|age:|i\s+am)\s+(\d{1,3})(\s+years?\s+(old)?)?",
        s
    )
    if m_age:
        try:
            age = int(m_age.group(2))
            # Sanity check: 1-120 years
            if 1 <= age <= 120:
                out.append({
                    "trait_id": "BasicDNA.Age",
                    "value": {"number": age}
                })
        except (ValueError, TypeError):
            pass

    # Height patterns: "I am 5'10", "I'm 180cm", "height: 6 feet"
    # Centimeters
    m_height_cm = re.search(r"\b(i am|i'm|im|height is|height:)\s+(\d{2,3})\s*(cm|centimeters?)", s)
    if m_height_cm:
        try:
            height = int(m_height_cm.group(2))
            if 50 <= height <= 300:  # Sanity check
                out.append({
                    "trait_id": "PaDNA.Height",
                    "value": {"number": height}
                })
        except (ValueError, TypeError):
            pass

    # Sexual orientation: "I am heterosexual", "I'm gay", etc.
    m_orient = re.search(
        r"\b(heterosexual|straight|gay|homosexual|lesbian|bisexual|bi|pansexual|asexual)\b",
        s
    )
    if m_orient:
        term = m_orient.group(1)
        # Normalize variants
        norm = {
            "straight": "heterosexual",
            "gay": "homosexual",
            "bi": "bisexual"
        }.get(term, term)
        out.append({
            "trait_id": "BasicDNA.Orientation",
            "value": {"enum": norm}
        })

    # Gender: "I am male", "I'm female", etc.
    m_gender = re.search(
        r"\b(i am|i'm|im|gender is|gender:)\s*(a\s+)?(male|female|man|woman|non-binary|nonbinary|other)\b",
        s
    )
    if m_gender:
        gender_term = m_gender.group(3)
        # Normalize variants
        norm = {
            "man": "male",
            "woman": "female",
            "nonbinary": "non-binary"
        }.get(gender_term, gender_term)
        out.append({
            "trait_id": "BasicDNA.Gender",
            "value": {"enum": norm}
        })

    # Name: "My name is John", "I'm called Jane"
    m_name = re.search(
        r"\b(my name is|i'm called|i am called|call me|name:)\s+([a-z]{2,20})\b",
        s
    )
    if m_name:
        name = m_name.group(2).capitalize()
        out.append({
            "trait_id": "BasicDNA.Name",
            "value": {"text": name}
        })

    return out


def format_fallback_summary(items: List[Dict[str, Any]]) -> str:
    """Format fallback extraction results for logging."""
    if not items:
        return "[]"
    trait_ids = [item.get("trait_id", "unknown") for item in items]
    return f"[{', '.join(trait_ids)}]"
