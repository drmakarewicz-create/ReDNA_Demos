# shared/padna_schema_v1_1.py
# Minimal schema utilities: ensure keys exist, compute lightweight UCN/Curiosity,
# and normalize values so downstream renderers/consumers don't break.

from typing import Dict, Any
import math
import copy
import time

_SCALAR_DEFAULT_UCN = 600.0  # mid-confidence default
_MAX_UCN = 1000.0

# canonical PaDNA nesting for v1.1 additions (extensible)
_PADNA_KEYS = {
    "PaDNA.Face.Shape": "oval",
    "PaDNA.Face.Jawline": "soft",
    "PaDNA.Face.Forehead.Height": "medium",
    "PaDNA.Face.Symmetry": "balanced",

    "PaDNA.FacialDNA.ForeheadHeight": "unknown",
    "PaDNA.FacialDNA.ForeheadShape": "unknown",
    "PaDNA.FacialDNA.SmileStyle": "unknown",
    "PaDNA.FacialDNA.AgingFeatures": "unknown",
    "PaDNA.FacialDNA.SymmetryScore": "unknown",

    "PaDNA.SkinDNA.Tone": "medium",
    "PaDNA.SkinDNA.Undertone": "neutral",
    "PaDNA.SkinDNA.Freckles": "none",
    "PaDNA.SkinDNA.Moles": "none",
    "PaDNA.SkinDNA.ComplexionConsistency": "unknown",

    "PaDNA.HairDNA.Color": "brown",
    "PaDNA.HairDNA.Length": "long",
    "PaDNA.HairDNA.Style": "loose",
    "PaDNA.HairDNA.Texture": "wavy",
    "PaDNA.HairDNA.Part": "center",
    "PaDNA.HairDNA.Volume": "medium",
    "PaDNA.HairDNA.Bangs": "none",
    "PaDNA.HairDNA.BaldPattern": "none",

    "PaDNA.EyeDNA.Color": "brown",
    "PaDNA.EyeDNA.Shape": "almond",
    "PaDNA.EyeDNA.Iris.Ring": "subtle",
    "PaDNA.EyeDNA.Lashes.Length": "long",
    "PaDNA.EyeDNA.Lashes.Density": "full",
    "PaDNA.EyeDNA.Eyeliner.Style": "tightline",
    "PaDNA.EyeDNA.EyelidCrease": "unknown",
    "PaDNA.EyeDNA.ScleraTint": "bright_white",
    "PaDNA.EyeDNA.EyeSpacing": "average",
    "PaDNA.EyeDNA.IrisPattern": "solid",

    "PaDNA.EyebrowDNA.Thickness": "medium",
    "PaDNA.EyebrowDNA.Arch": "soft",
    "PaDNA.EyebrowDNA.DistanceToEye": "normal",

    "PaDNA.NoseDNA.Width": "medium",
    "PaDNA.NoseDNA.Bridge": "straight",
    "PaDNA.NoseDNA.Tip": "rounded",
    "PaDNA.NoseDNA.Nostrils": "oval",

    "PaDNA.LipDNA.Fullness": "medium",
    "PaDNA.LipDNA.Shape": "bow",
    "PaDNA.LipDNA.MouthWidth": "medium",

    "PaDNA.EarDNA.Visible": "partial",
    "PaDNA.Accessories.Earrings": "hoop",
    "PaDNA.Accessories.Glasses": "none",

    "PaDNA.NeckDNA.Length": "medium",
    "PaDNA.NeckDNA.Width": "medium",

    "PaDNA.BodyDNA.HeightCM": "unknown",
    "PaDNA.BodyDNA.WeightKG": "unknown",
    "PaDNA.BodyDNA.Build": "unknown",
    "PaDNA.BodyDNA.Handedness": "unknown",
    "PaDNA.BodyDNA.HandSize": "unknown",
    "PaDNA.BodyDNA.FootSize": "unknown",
    "PaDNA.BodyDNA.ShoulderShape": "unknown",
    "PaDNA.BodyDNA.NeckLength": "unknown",
    "PaDNA.BodyDNA.HandStructure": "unknown",

    "PaDNA.ApparelDNA.Style": "unknown",
    "PaDNA.ApparelDNA.Fit": "unknown",
    "PaDNA.ApparelDNA.FitPreference": "unknown",
    "PaDNA.ApparelDNA.Palette": "unknown",
    "PaDNA.ApparelDNA.PalettePreference": "unknown",
    "PaDNA.ApparelDNA.Accessories": "unknown",
    "PaDNA.ApparelDNA.FootwearStyle": "unknown",

    "PaDNA.MovementDNA.Gestures": "unknown",
    "PaDNA.MovementDNA.HeadMovement": "unknown",
    "PaDNA.MovementDNA.HandUsage": "unknown",
    "PaDNA.MovementDNA.Tempo": "unknown",
    "PaDNA.MovementDNA.SignatureMotion": "unknown",

    "PaDNA.MakeupDNA.Foundation.Coverage": "light",
    "PaDNA.MakeupDNA.Contour": "soft",
    "PaDNA.MakeupDNA.Highlighter": "subtle",
    "PaDNA.MakeupDNA.EyeShadow.Hue": "neutral",
    "PaDNA.MakeupDNA.EyeShadow.Intensity": "soft",
    "PaDNA.MakeupDNA.Lip.Color": "nude",
    "PaDNA.MakeupDNA.Lip.Finish": "satin",
}

def _ensure_paths(d: Dict[str, Any]) -> Dict[str, Any]:
    # Put everything under bundle['padna'] flat dict of dot-keys for simplicity
    bundle = copy.deepcopy(d) if d else {}
    padna = bundle.setdefault("padna", {})
    if not isinstance(padna, dict):
        bundle["padna"] = {}
        padna = bundle["padna"]

    for k, v in _PADNA_KEYS.items():
        padna.setdefault(k, v)

    # meta
    meta = bundle.setdefault("meta", {})
    meta.setdefault("schema_version", "padna_v1.1")
    meta.setdefault("calculated_at", int(time.time()))

    return bundle

def _compute_descriptor_ucn(value: Any) -> float:
    """Toy UCN heuristic: known string => higher; 'unknown' => lower."""
    if value in (None, "", "unknown"):
        return 350.0
    # Slightly reward specificity (strings with a dot path sub-attr already decided)
    if isinstance(value, str) and any(x in value for x in ["light", "medium", "dark", "warm", "cool", "neutral"]):
        return 700.0
    return _SCALAR_DEFAULT_UCN

def _aggregate_ucn(padna: Dict[str, Any]) -> float:
    if not padna:
        return 300.0
    vals = [_compute_descriptor_ucn(v) for v in padna.values()]
    if not vals:
        return 300.0
    # harmonic mean guards against a few low certainties
    denom = sum((1.0 / max(1e-6, v)) for v in vals)
    hm = len(vals) / max(1e-6, denom)
    return max(0.0, min(_MAX_UCN, hm))

def finalize_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure all new keys exist, compute overall UCN and Curiosity=1000-UCN,
    and tuck them in bundle['scores'].
    """
    bundle = _ensure_paths(bundle)
    padna = bundle["padna"]

    overall_ucn = _aggregate_ucn(padna)
    curiosity = max(0.0, _MAX_UCN - overall_ucn)

    scores = bundle.setdefault("scores", {})
    scores["ucn_overall"] = overall_ucn
    scores["curiosity_overall"] = curiosity

    # Also compute simple per-path UCN if missing
    per = scores.setdefault("ucn_per_path", {})
    for k, v in padna.items():
        per.setdefault(k, _compute_descriptor_ucn(v))

    return bundle
