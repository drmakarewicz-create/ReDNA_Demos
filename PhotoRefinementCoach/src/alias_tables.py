"""Alias tables for soft PaDNA imports."""

from __future__ import annotations

from typing import Dict

# Keys are stored in lowercase to simplify lookups during soft-import parsing.
COMMON_PATH_ALIASES: Dict[str, str] = {
    "face.shape": "PaDNA.FacialDNA.FaceShape",
    "facialdna.faceshape": "PaDNA.FacialDNA.FaceShape",
    "padna.face.shape": "PaDNA.FacialDNA.FaceShape",
    "padna.facialdna.faceshape": "PaDNA.FacialDNA.FaceShape",
    "hair.color": "PaDNA.HairDNA.Color",
    "hair_colour": "PaDNA.HairDNA.Color",
    "hairdna.colorbase": "PaDNA.HairDNA.Color",
    "padna.hairdna.color": "PaDNA.HairDNA.Color",
    "padna.hairdna.colorbase": "PaDNA.HairDNA.Color",
    "eyes.iris_color": "PaDNA.EyeDNA.IrisColor",
    "eye.iris_color": "PaDNA.EyeDNA.IrisColor",
    "padna.eyedna.iriscolor": "PaDNA.EyeDNA.IrisColor",
    "body.height": "PaDNA.BodyDNA.HeightCM",
    "height_cm": "PaDNA.BodyDNA.HeightCM",
    "padna.bodydna.height": "PaDNA.BodyDNA.HeightCM",
    "padna.bodydna.heightcm": "PaDNA.BodyDNA.HeightCM",
    "body.weight": "PaDNA.BodyDNA.WeightKG",
    "weight_kg": "PaDNA.BodyDNA.WeightKG",
    "padna.bodydna.weight": "PaDNA.BodyDNA.WeightKG",
    "padna.bodydna.weightkg": "PaDNA.BodyDNA.WeightKG",
}


def lookup_common_path(path: str) -> str | None:
    """Return the canonical PaDNA path if the provided key matches a known alias."""

    key = path.strip().lower()
    if not key:
        return None
    return COMMON_PATH_ALIASES.get(key)
