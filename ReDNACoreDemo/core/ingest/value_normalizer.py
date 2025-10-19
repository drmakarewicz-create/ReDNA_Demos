"""
Value Normalizer - Phase 4.0a

Conservative value normalization for traits that Core is allowed to promote in
the precision lock pass. Anything outside this allowlist intentionally returns
None so snapshot.traits only contains finalized, high-confidence facts.
"""
from __future__ import annotations

import re
from typing import Optional


def _ftin_to_cm(feet: int, inches: int = 0) -> str:
    total_inches = feet * 12 + inches
    cm = round(total_inches * 2.54)
    return f"{cm}cm"


def _has(tokens: list[str], text: str) -> bool:
    """
    Return True when any token appears in the lower-cased *text*.
    """
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _normalize_work_location(text: str):
    s = text.lower()
    s = s.replace("in-office", "in office")

    remote_tokens = ["work from home", "remote", "wfh"]
    onsite_tokens = ["onsite", "on-site", "in office"]
    hybrid_tokens = ["hybrid", "split schedule", "mix of remote and office"]

    has_remote = any(tok in s for tok in remote_tokens)
    has_onsite = any(tok in s for tok in onsite_tokens)
    has_hybrid_word = any(tok in s for tok in hybrid_tokens)

    # hybrid if explicitly stated OR both remote and onsite indicators present
    if has_hybrid_word or (has_remote and has_onsite):
        return "hybrid"
    if has_remote:
        return "remote"
    if has_onsite:
        return "onsite"
    return None


def _normalize_chronotype(text: str):
    s = text.lower()

    # simple substring checks handle punctuation/commas robustly
    if "morning person" in s or "early riser" in s or ("up before" in s and "sunrise" in s):
        return "morning"
    if (
        "night owl" in s
        or "stay up late" in s
        or "up past midnight" in s
        or "in bed after midnight" in s
    ):
        return "evening"

    # regex fallbacks (time-based variants)
    if re.search(r"\bup\s+(?:before|by)\s+(?:sunrise|[56](?::[0-5]\d)?)\b", s):
        return "morning"
    if re.search(r"\b(in bed after|up past)\s+(?:midnight|1[0-2])\b", s):
        return "evening"

    return None


def normalize_value(trait_id: str, text: str) -> Optional[str | bool]:
    """
    Normalize extracted values for the precision-allowlisted traits.

    Returns:
        - str: Canonicalized value
        - bool: For boolean traits (e.g., Outdoor exercise indicator)
        - None: When the text does not strongly support a normalized value
    """
    if not trait_id or not text:
        return None

    s = text.lower()

    # Eye color requires explicit eye/iris mention plus a known color token.
    if trait_id == "PaDNA.EyeDNA.IrisColor":
        if not _has(["eye", "eyes", "iris"], s):
            return None
        if "blue" in s and "gray" in s:
            return "blue_gray"
        if "blueish" in s and "gray" in s:
            return "blue_gray"
        if "blue" in s:
            return "blue"
        if "brown" in s:
            return "brown"
        if "green" in s:
            return "green"
        if "hazel" in s:
            return "hazel"
        return None

    if trait_id == "PaDNA.HairDNA.Color.Natural":
        if not _has(["hair"], s):
            return None

        hair_colors = ["brown", "blonde", "black", "red", "gray", "grey"]
        non_hair_colors = ["blue", "green", "purple", "pink", "orange", "violet", "teal"]

        if any(color in s for color in non_hair_colors):
            return None

        found = [color for color in hair_colors if f" {color} " in f" {s} "]
        if not found:
            for color in hair_colors:
                if re.search(rf"\b{color}\b", s):
                    found.append(color)

        if len(found) == 1:
            return "gray" if found[0] == "grey" else found[0]
        return None

    if trait_id == "BasicDNA.Age":
        if "in my early 30s" in s or "early 30s" in s:
            return "30s"
        if "in my late 20s" in s or "late 20s" in s:
            return "20s"
        match = re.search(r"\b(i am|i'm)\s+(\d{1,3})\b", s)
        if match:
            return match.group(2)
        match = re.search(r"\b(\d{1,3})\s+years?\s+old\b", s)
        if match:
            return match.group(1)
        return None

    if trait_id == "BasicDNA.RelationshipStatus":
        if "i am married" in s or "i'm married" in s:
            return "married"
        if "i am single" in s or "i'm single" in s:
            return "single"
        for value in ["divorced", "widowed", "engaged", "separated"]:
            if value in s:
                return value
        return None

    if trait_id == "PaDNA.BodyDNA.Height":
        # "I am 6 feet tall" / "I'm 6 feet tall"
        match = re.search(r"\b(i am|i'm)\s+(\d{1,2})\s*(feet|foot|ft)\s+tall\b", s)
        if match:
            feet = int(match.group(2))
            return _ftin_to_cm(feet, 0)

        # "5 ft 10 in" / "5ft 10in" / "5 ft 10 inches"
        match = re.search(r"\b(\d{1,2})\s*(ft|feet|foot)\s*(\d{1,2})\s*(in|inch|inches)\b", s)
        if match:
            feet = int(match.group(1))
            inches = int(match.group(3))
            return _ftin_to_cm(feet, inches)

        # Apostrophe form: 5'11" / 5' 11"
        match = re.search(r"\b(\d{1,2})\s*'\s*(\d{1,2})?\s*(\"|in)?\b", s)
        if match:
            feet = int(match.group(1))
            inches = int(match.group(2) or 0)
            return _ftin_to_cm(feet, inches)

        # Metric centimeters
        match = re.search(r"\b(\d{2,3})\s*cm\b", s)
        if match:
            return f"{int(match.group(1))}cm"

        # Metric meters (1.83 m)
        match = re.search(r"\b(\d(?:\.\d{1,2})?)\s*m\b", s)
        if match:
            cm = round(float(match.group(1)) * 100)
            return f"{cm}cm"

        return None

    # Outdoor exercise: positive outdoor cues AND no negating indoor cues.
    if trait_id == "BehaviorDNA.Exercise.Outdoor":
        positive = any(keyword in s for keyword in [
            "hike",
            "hiking",
            "trail",
            "run outside",
            "outdoor run",
            "trail run",
            "jog outside",
        ])
        negation = any(keyword in s for keyword in [
            "stay in",
            "staying in",
            "indoors",
            "inside",
            "no plans",
            "quiet weekend",
            "stay home",
            "at home",
        ])
        return True if positive and not negation else None

    # Exercise frequency: require an exercise verb plus explicit cadence.
    if trait_id == "BehaviorDNA.Exercise.Frequency":
        has_exercise = any(keyword in s for keyword in [
            "run",
            "running",
            "jog",
            "hike",
            "hiking",
            "trail",
            "workout",
            "gym",
            "swim",
            "bike",
            "yoga",
        ])
        if not has_exercise:
            return None
        weekly = (
            "every weekend" in s
            or "each weekend" in s
            or "every saturday" in s
            or "every sunday" in s
        )
        daily = (
            "every day" in s
            or "everyday" in s
            or "daily" in s
        )
        twice = (
            "twice a week" in s
            or "two times a week" in s
            or "2x a week" in s
        )
        if weekly:
            return "weekly"
        if daily:
            return "daily"
        if twice:
            return "2_per_week"
        return None

    if trait_id == "BehaviorDNA.Sleep.Chronotype":
        return _normalize_chronotype(text)

    if trait_id == "BehaviorDNA.Health.Diet":
        if "don't eat meat" in s or "do not eat meat" in s or "avoid meat" in s:
            return "vegetarian"
        for value, normalized in [
            ("vegan", "vegan"),
            ("pescatarian", "pescatarian"),
            ("keto", "keto"),
            ("gluten free", "gluten_free"),
            ("gluten-free", "gluten_free"),
        ]:
            if value in s:
                return normalized
        return None

    if trait_id == "BehaviorDNA.Work.Location":
        return _normalize_work_location(text)

    if trait_id == "PreferenceDNA.Social.GroupSize":
        if any(keyword in s for keyword in ["quiet weekend", "stay in and read", "prefer small group", "small group"]):
            return "small"
        if any(keyword in s for keyword in ["love big parties", "large crowd", "prefer big groups"]):
            return "large"
        return None

    if trait_id == "BehaviorDNA.Exercise.Type":
        for token, normalized in [
            ("run", "running"),
            ("swim", "swimming"),
            ("bike", "cycling"),
            ("yoga", "yoga"),
        ]:
            if token in s:
                return normalized
        return None

    # All other traits are intentionally unsupported in this precision pass.
    return None
