# ReDNACoreDemo/core/hierarchy.py
"""
Trait registry with canonical keys the Core recognizes.
You can add or prune freely; the rest of the Core is data-driven.

PaDNA and other umbrellas derived from your “Hierarchy of DNAs v4.0”.
"""

from __future__ import annotations
from typing import Dict, List

# Canonical trait keys (flattened dot-paths)
# — Start with PaDNA (priority for Renderer work), plus scaffolding for others.

REGISTRY: Dict[str, List[str]] = {
    "PaDNA.HairDNA": [
        "Color.Natural",         # e.g., Blue/Green/Red→ for hair use: Black/Brown/Blonde/Red/Gray/White/Mixed
        "Color.Dyed",
        "Length",                 # buzzed/short/medium/long/xlong
        "Style",                  # straight/wavy/curly/coiled/kinky/braided/dreads/…
        "Texture",                # fine/thick/coarse/silky/wiry
        "Density",                # sparse/normal/full/very_dense
        "Hairline",               # straight/receding/widows_peak
        "Part",                   # center/side/none
        "Condition",              # dry/oily/frizzy/smooth
        "Distinctive.Bald",       # bool
        "Distinctive.BaldSpot",   # bool/location
        "Distinctive.Streak",     # e.g., white_streak
    ],
    "PaDNA.EyeDNA": [
        "IrisColor",              # blue/green/brown/hazel/gray/etc.
        "Shape",                  # almond/round/monolid/hooded/etc.
        "Size",                   # small/average/large
        "Sclera",                 # bright/veined/tinted
        "Lashes.Length",          # short/average/long
        "Brows.Shape",            # arched/straight/angled
        "Brows.Density",          # thin/thick/bushy
        "Distinctive.Heterochromia",
    ],
    "PaDNA.SkinDNA": [
        "Tone",                   # Fitz I..VI + nuance
        "Undertone",              # cool/warm/neutral/olive/…
        "Freckles",
        "Birthmarks",
        "Moles",
        "Texture",
        "Conditions",             # list: acne/rosacea/eczema/…
        "SunBehavior",            # burns_easily/tans_deeply/…
        "WrinklePatterns",
    ],
    "PaDNA.FacialDNA": [
        "FaceShape",
        "Forehead",
        "Nose",
        "Lips",
        "MouthSize",
        "Teeth",
        "Cheeks",
        "Jawline",
        "Chin",
        "Ears",
        "Symmetry",
        "FacialHair",             # presence/density/color/pattern
    ],
    "PaDNA.BodyDNA": [
        "Height",
        "Weight",
        "BodyShape",
        "Proportions.TorsoLegRatio",
        "Proportions.ArmRatio",
        "Hands.Size",
        "ShoulderWidth",
        "HipWidth",
        "WaistHipRatio",
        "Chest",
        "Posture",
        "Gait",
        "Distinctive",            # tattoos/piercings/scars
        "Flexibility",
    ],
    "PaDNA.Other": [
        "Voice",
        "Scent",
        "Hands.Nails",
        "MovementStyle",
    ],

    # Scaffolding for the rest (you can add rows immediately):
    "PsyDNA.PersonalityDNA": [],
    "PsyDNA.MotivationDNA": [],
    "PsyDNA.BeliefDNA": [],
    "EmDNA": [],
    "CogDNA": [],
    "SocDNA": [],
    "BehDNA": [],
    "HistDNA": [],
    "PrefDNA": [],
    "SkillDNA": [],
    "MetaDNA": [],
}

# Helper: return every fully-qualified trait key (umbrella + subkey)
def all_trait_keys() -> List[str]:
    out: List[str] = []
    for family, keys in REGISTRY.items():
        if not keys:
            out.append(family)  # umbrella-level placeholder trait
            continue
        for k in keys:
            out.append(f"{family}.{k}")
    return out