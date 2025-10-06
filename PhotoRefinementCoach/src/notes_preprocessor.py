"""Pre-processor to convert unstructured notes into PaDNA observations."""

from typing import Any, Dict, List
import re


def extract_traits_from_notes(notes: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Extract structured PaDNA traits from natural language notes.

    This is a simple rule-based extractor that looks for keywords and patterns.
    For production use, consider using an LLM-based approach.
    """
    observations: Dict[str, Dict[str, Any]] = {}

    # Combine all notes into searchable text
    full_text = " ".join(notes).lower()

    # Hair patterns
    if "auburn" in full_text or "reddish" in full_text:
        if "auburn" in full_text:
            observations["PaDNA.HairDNA.Color"] = {"resolved_value": "Auburn", "ucn": 85.0}
        else:
            observations["PaDNA.HairDNA.Color"] = {"resolved_value": "Reddish", "ucn": 80.0}

    if "wavy" in full_text:
        observations["PaDNA.HairDNA.Texture"] = {"resolved_value": "Wavy", "ucn": 85.0}

    if "thick" in full_text and "hair" in full_text:
        observations["PaDNA.HairDNA.Volume"] = {"resolved_value": "Thick", "ucn": 85.0}

    # Length
    if "long" in full_text and "hair" in full_text:
        observations["PaDNA.HairDNA.Length"] = {"resolved_value": "Long", "ucn": 80.0}

    # Parting
    if "parted to the side" in full_text or "side part" in full_text:
        observations["PaDNA.HairDNA.Parting"] = {"resolved_value": "Side part", "ucn": 75.0}

    # Eye patterns
    if "green" in full_text and ("eyes" in full_text or "eye color" in full_text):
        if "hazel" in full_text:
            observations["PaDNA.EyeDNA.Color"] = {"resolved_value": "Green with hazel", "ucn": 85.0}
        else:
            observations["PaDNA.EyeDNA.Color"] = {"resolved_value": "Green", "ucn": 85.0}

    # Skin patterns
    if "fair" in full_text and "skin" in full_text:
        observations["PaDNA.SkinDNA.Tone"] = {"resolved_value": "Fair", "ucn": 85.0}

    if "freckles" in full_text:
        if "lots of freckles" in full_text or "very present" in full_text:
            observations["PaDNA.SkinDNA.Freckles"] = {"resolved_value": "Present, prominent", "ucn": 90.0}
        else:
            observations["PaDNA.SkinDNA.Freckles"] = {"resolved_value": "Present", "ucn": 85.0}

    if "sun-sensitive" in full_text or "sun sensitive" in full_text:
        observations["PaDNA.SkinDNA.SunSensitivity"] = {"resolved_value": "High", "ucn": 85.0}

    # Body/Height patterns
    height_match = re.search(r"(\d+)'(\d+)", full_text)
    if height_match:
        feet = int(height_match.group(1))
        inches = int(height_match.group(2))
        height_cm = int((feet * 12 + inches) * 2.54)
        observations["PaDNA.BodyDNA.HeightEstimateCM"] = {"resolved_value": height_cm, "ucn": 70.0}

    if "slim" in full_text or "slender" in full_text:
        if "curvy" in full_text or "hourglass" in full_text:
            observations["PaDNA.BodyDNA.Build"] = {"resolved_value": "Slim/Curvy", "ucn": 80.0}
            observations["PaDNA.BodyDNA.WaistHipRatio"] = {"resolved_value": "Hourglass", "ucn": 80.0}
        else:
            observations["PaDNA.BodyDNA.Build"] = {"resolved_value": "Slim", "ucn": 80.0}

    if "belly button piercing" in full_text or "navel piercing" in full_text:
        observations["PaDNA.BodyDNA.Navel"] = {"resolved_value": "Pierced", "ucn": 95.0}

    if "toned" in full_text:
        if "legs" in full_text:
            observations["PaDNA.BodyDNA.Legs"] = {"resolved_value": "Toned", "ucn": 85.0}
        if "stomach" in full_text or "abdomen" in full_text:
            observations["PaDNA.FitnessDNA.Indicators"] = {
                "resolved_value": ["Flat abdomen", "Toned legs"],
                "ucn": 85.0
            }

    # Smile/Teeth patterns
    if "straight" in full_text and "teeth" in full_text:
        observations["PaDNA.SmileDNA.Teeth"] = {"resolved_value": "Straight, white", "ucn": 90.0}

    if "bright smile" in full_text or "broad smile" in full_text:
        observations["PaDNA.SmileDNA.SmileShape"] = {"resolved_value": "Broad smile", "ucn": 85.0}

    # Expression patterns
    if "confident" in full_text and "pos" in full_text:
        observations["PaDNA.ExpressionDNA.TypicalExpression"] = {
            "resolved_value": "Confident, playful",
            "ucn": 80.0
        }

    # Apparel patterns
    apparel_items = []
    if "crop top" in full_text:
        apparel_items.append("Crop tops")
    if "bikini" in full_text:
        apparel_items.append("Bikinis")
    if "low-rise shorts" in full_text or "low-rise" in full_text:
        apparel_items.append("Low-rise shorts")
    if "boots" in full_text:
        apparel_items.append("Boots")

    if apparel_items:
        observations["PaDNA.ApparelDNA.FrequentTops"] = {
            "resolved_value": apparel_items,
            "ucn": 75.0
        }

    style_themes = []
    if "playful" in full_text:
        style_themes.append("Playful")
    if "flirty" in full_text:
        style_themes.append("Flirty")
    if "2000s" in full_text:
        style_themes.append("2000s aesthetic")

    if style_themes:
        observations["PaDNA.ApparelDNA.StyleThemes"] = {
            "resolved_value": style_themes,
            "ucn": 80.0
        }

    # Jewelry
    if "layered" in full_text and ("necklace" in full_text or "pendant" in full_text):
        observations["PaDNA.ApparelDNA.Jewelry.Necklace"] = {
            "resolved_value": "Layered pendants",
            "ucn": 80.0
        }

    if "hoop" in full_text or "stud" in full_text:
        observations["PaDNA.ApparelDNA.Jewelry.Earrings"] = {
            "resolved_value": "Small hoops/studs",
            "ucn": 80.0
        }

    return observations


def preprocess_messy_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a messy, unstructured JSON payload into a structured PaDNA import format.

    Args:
        payload: Messy JSON with notes, extra fields, etc.

    Returns:
        Structured JSON ready for import
    """
    result: Dict[str, Any] = {}

    # Extract user_id from various possible fields
    for key in ["user_id", "id", "subject", "name"]:
        if key in payload and isinstance(payload[key], str):
            result["user_id"] = payload[key]
            break

    # Start with empty observations
    observations: Dict[str, Dict[str, Any]] = {}

    # Process notes if present
    notes = payload.get("notes")
    if isinstance(notes, list):
        extracted = extract_traits_from_notes(notes)
        observations.update(extracted)

    # Process extra fields
    extra = payload.get("extra")
    if isinstance(extra, dict):
        if "fashionEra" in extra:
            observations["StyleContext.EraInference"] = {
                "resolved_value": extra["fashionEra"],
                "ucn": 85.0
            }

        if "freckles" in extra:
            # Only add if not already present from notes
            if "PaDNA.SkinDNA.Freckles" not in observations:
                observations["PaDNA.SkinDNA.Freckles"] = {
                    "resolved_value": extra["freckles"],
                    "ucn": 80.0
                }

        if "personalityInference" in extra:
            observations["BehavioralDNA.SocialProjection"] = {
                "resolved_value": extra["personalityInference"],
                "ucn": 75.0
            }

    result["observations"] = observations

    # Add default provenance
    result["provenance"] = {
        "source": "manual-notes",
        "actor": "preprocessor",
        "via": "notes_extraction"
    }

    return result
