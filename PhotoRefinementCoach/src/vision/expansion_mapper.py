# src/vision/expansion_mapper.py
# Turn a list of basic per-photo predictions into a normalized PaDNA bundle (v1.1)

from typing import List, Dict, Any
import statistics

def _majority(values: List[str], default: str) -> str:
    if not values:
        return default
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]

def _first(values: List[str], default: str) -> str:
    for v in values:
        if v:
            return v
    return default

def expanded_from_basic(basic=None, photos: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Input (examples):
      photos = [
        {
          "photo_id": "A", "recency": "RECENT",
          "traits": {
            "Hair.Color": "dark-blonde",
            "Hair.Length": "long",
            "Hair.Style": "loose",
            "Hair.Texture": "wavy",
            "Hair.Part": "center",
            "Eye.Color": "hazel",
            "Skin.Tone": "light-medium",
            "Skin.Undertone": "warm",
            "Eye.Shape": "almond",
            "Brow.Thickness": "medium",
            "Brow.Arch": "soft",
            "Lashes.Length": "long",
            "Lips.Fullness": "full",
            "Earrings": "hoop"
          }
        },
        ...
      ]
    Returns a PaDNA bundle with dot-keys under bundle['padna'].
    """
    photos = photos or []
    traits_list = [p.get("traits", {}) for p in photos]

    def collect(key: str) -> List[str]:
        return [str(t.get(key, "")).strip() for t in traits_list if t.get(key) is not None]

    # Majority vote / first non-empty for each
    padna = {
        "PaDNA.Face.Shape": _first(collect("Face.Shape"), "oval"),
        "PaDNA.Face.Jawline": _first(collect("Face.Jawline"), "soft"),
        "PaDNA.Face.Forehead.Height": _first(collect("Face.Forehead.Height"), "medium"),
        "PaDNA.Face.Symmetry": _first(collect("Face.Symmetry"), "balanced"),

        "PaDNA.SkinDNA.Tone": _majority(collect("Skin.Tone"), "medium"),
        "PaDNA.SkinDNA.Undertone": _majority(collect("Skin.Undertone"), "neutral"),
        "PaDNA.SkinDNA.Freckles": _majority(collect("Skin.Freckles"), "none"),
        "PaDNA.SkinDNA.Moles": _majority(collect("Skin.Moles"), "none"),

        "PaDNA.HairDNA.Color": _majority(collect("Hair.Color"), "brown"),
        "PaDNA.HairDNA.Length": _majority(collect("Hair.Length"), "long"),
        "PaDNA.HairDNA.Style": _majority(collect("Hair.Style"), "loose"),
        "PaDNA.HairDNA.Texture": _majority(collect("Hair.Texture"), "wavy"),
        "PaDNA.HairDNA.Part": _majority(collect("Hair.Part"), "center"),
        "PaDNA.HairDNA.Volume": _majority(collect("Hair.Volume"), "medium"),
        "PaDNA.HairDNA.Bangs": _majority(collect("Hair.Bangs"), "none"),

        "PaDNA.EyeDNA.Color": _majority(collect("Eye.Color"), "brown"),
        "PaDNA.EyeDNA.Shape": _majority(collect("Eye.Shape"), "almond"),
        "PaDNA.EyeDNA.Iris.Ring": _majority(collect("Eye.Iris.Ring"), "subtle"),
        "PaDNA.EyeDNA.Lashes.Length": _majority(collect("Lashes.Length"), "long"),
        "PaDNA.EyeDNA.Lashes.Density": _majority(collect("Lashes.Density"), "full"),
        "PaDNA.EyeDNA.Eyeliner.Style": _majority(collect("Eyeliner.Style"), "tightline"),

        "PaDNA.EyebrowDNA.Thickness": _majority(collect("Brow.Thickness"), "medium"),
        "PaDNA.EyebrowDNA.Arch": _majority(collect("Brow.Arch"), "soft"),
        "PaDNA.EyebrowDNA.DistanceToEye": _majority(collect("Brow.DistanceToEye"), "normal"),

        "PaDNA.NoseDNA.Width": _majority(collect("Nose.Width"), "medium"),
        "PaDNA.NoseDNA.Bridge": _majority(collect("Nose.Bridge"), "straight"),
        "PaDNA.NoseDNA.Tip": _majority(collect("Nose.Tip"), "rounded"),
        "PaDNA.NoseDNA.Nostrils": _majority(collect("Nose.Nostrils"), "oval"),

        "PaDNA.LipDNA.Fullness": _majority(collect("Lips.Fullness"), "medium"),
        "PaDNA.LipDNA.Shape": _majority(collect("Lips.Shape"), "bow"),
        "PaDNA.LipDNA.MouthWidth": _majority(collect("Lips.MouthWidth"), "medium"),

        "PaDNA.EarDNA.Visible": _majority(collect("Ear.Visible"), "partial"),
        "PaDNA.Accessories.Earrings": _majority(collect("Earrings"), "none"),
        "PaDNA.Accessories.Glasses": _majority(collect("Glasses"), "none"),

        "PaDNA.NeckDNA.Length": _majority(collect("Neck.Length"), "medium"),
        "PaDNA.NeckDNA.Width": _majority(collect("Neck.Width"), "medium"),

        "PaDNA.MakeupDNA.Foundation.Coverage": _majority(collect("Makeup.Foundation.Coverage"), "light"),
        "PaDNA.MakeupDNA.Contour": _majority(collect("Makeup.Contour"), "soft"),
        "PaDNA.MakeupDNA.Highlighter": _majority(collect("Makeup.Highlighter"), "subtle"),
        "PaDNA.MakeupDNA.EyeShadow.Hue": _majority(collect("Makeup.EyeShadow.Hue"), "neutral"),
        "PaDNA.MakeupDNA.EyeShadow.Intensity": _majority(collect("Makeup.EyeShadow.Intensity"), "soft"),
        "PaDNA.MakeupDNA.Lip.Color": _majority(collect("Makeup.Lip.Color"), "nude"),
        "PaDNA.MakeupDNA.Lip.Finish": _majority(collect("Makeup.Lip.Finish"), "satin"),
    }

    return {
        "padna": padna,
        "photos": photos,  # preserve originals for provenance
        "meta": {
            "source": "PhotoRefinementCoach/expanded_from_basic",
            "schema_version": "padna_v1.1"
        }
    }