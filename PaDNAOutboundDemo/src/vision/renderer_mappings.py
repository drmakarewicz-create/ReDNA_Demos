"""Canonical trait + geometry mapping helpers for the PaDNA renderer."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Canonical key aliases (flat resolved dicts may use several spellings)
# ---------------------------------------------------------------------------

CANON_KEYS: Dict[str, List[str]] = {
    "hair_color": ["PaDNA.HairDNA.Color", "HairDNA.Color", "Hair.Color"],
    "hair_dyed": ["PaDNA.HairDNA.DyedColor", "HairDNA.DyedColor"],
    "hair_length": ["PaDNA.HairDNA.Length", "HairDNA.Length"],
    "hair_style": ["PaDNA.HairDNA.Style", "HairDNA.Style"],
    "hair_part": ["PaDNA.HairDNA.Part", "HairDNA.Part"],
    "hair_texture": ["PaDNA.HairDNA.Texture", "HairDNA.Texture"],
    "hair_density": ["PaDNA.HairDNA.Density", "HairDNA.Density"],
    "skin_tone": ["PaDNA.SkinDNA.Tone", "SkinDNA.Tone", "Skin.Tone"],
    "skin_undertone": ["PaDNA.SkinDNA.Undertone", "SkinDNA.Undertone"],
    "freckles": ["PaDNA.SkinDNA.Freckles", "SkinDNA.Freckles"],
    "sun_behavior": ["PaDNA.SkinDNA.SunBehavior", "SkinDNA.SunBehavior"],
    "moles": ["PaDNA.SkinDNA.Moles", "SkinDNA.Moles"],
    "eye_color": ["PaDNA.EyeDNA.IrisColor", "EyeDNA.IrisColor", "Eye.Color"],
    "eye_shape": ["PaDNA.EyeDNA.Shape", "EyeDNA.Shape"],
    "eye_size": ["PaDNA.EyeDNA.Size", "EyeDNA.Size"],
    "lashes": ["PaDNA.EyeDNA.Lashes", "EyeDNA.Lashes"],
    "brows": ["PaDNA.EyeDNA.Brows", "EyeDNA.Brows", "Brows"],
    "eyelid_crease": ["PaDNA.EyeDNA.EyelidCrease", "EyeDNA.EyelidCrease"],
    "sclera_tint": ["PaDNA.EyeDNA.ScleraTint", "EyeDNA.ScleraTint"],
    "face_shape": ["PaDNA.FacialDNA.FaceShape", "FacialDNA.FaceShape"],
    "cheeks": ["PaDNA.FacialDNA.Cheeks", "FacialDNA.Cheeks"],
    "jawline": ["PaDNA.FacialDNA.Jawline", "FacialDNA.Jawline"],
    "lips": ["PaDNA.FacialDNA.Lips", "FacialDNA.Lips"],
    "nose": ["PaDNA.FacialDNA.Nose", "FacialDNA.Nose"],
    "forehead": ["PaDNA.FacialDNA.Forehead", "FacialDNA.Forehead"],
    "symmetry": ["PaDNA.FacialDNA.Symmetry", "FacialDNA.Symmetry"],
    "posture": ["PaDNA.BodyDNA.Posture", "BodyDNA.Posture", "Posture"],
    "gait": ["PaDNA.BodyDNA.Gait", "BodyDNA.Gait", "Gait"],
    "height": ["PaDNA.BodyDNA.Height", "BodyDNA.Height", "Height", "PaDNA.BodyDNA.HeightCM", "BodyDNA.HeightCM"],
    "weight": ["PaDNA.BodyDNA.Weight", "BodyDNA.Weight", "Weight", "PaDNA.BodyDNA.WeightKG", "BodyDNA.WeightKG"],
    "ratios": ["PaDNA.BodyDNA.Ratios", "BodyDNA.Ratios"],
    "body_distinctive": ["PaDNA.BodyDNA.Distinctive", "BodyDNA.Distinctive"],
}

# ---------------------------------------------------------------------------
# Palette ramps (updated blonde tones, etc.)
# ---------------------------------------------------------------------------

HAIR_HEX: Dict[str, Dict[str, str]] = {
    "platinum_blonde": {"base": "#E9E1C9", "low": "#CFC5A8", "hi": "#F5F0DA", "line": "#B9AD8C"},
    "light_blonde": {"base": "#E7D18D", "low": "#BEA662", "hi": "#F6EEC4", "line": "#8E7A42"},
    "dark_blonde": {"base": "#D4B774", "low": "#AB8F53", "hi": "#E6D59B", "line": "#7D6A3A"},
    "strawberry_blonde": {"base": "#E6B07E", "low": "#C98E59", "hi": "#F3C7A0", "line": "#A8724A"},
    "copper_red": {"base": "#C7672E", "low": "#9E4F22", "hi": "#DC7B3E", "line": "#7F3E1B"},
    "auburn": {"base": "#8E3F2C", "low": "#6B2F22", "hi": "#A6503A", "line": "#56251B"},
    "medium_brown": {"base": "#6C4B35", "low": "#523827", "hi": "#7E5A41", "line": "#3E2A1E"},
    "dark_brown": {"base": "#473224", "low": "#342318", "hi": "#5A4635", "line": "#26170F"},
    "black": {"base": "#27211C", "low": "#191513", "hi": "#3C332B", "line": "#120E0C"},
}

SKIN_HEX: Dict[str, Dict[str, str]] = {
    "very_fair_cool": {"fill": "#F5D9C9", "shadow": "#E3B9A4", "highlight": "#FFE7D8", "line": "#C79C86", "freckles": "#A46E5A"},
    "very_fair_neutral": {"fill": "#F4D3C1", "shadow": "#E2B39A", "highlight": "#FFDECF", "line": "#C19682", "freckles": "#9F6C57"},
    "fair_neutral": {"fill": "#F0CDBB", "shadow": "#D9AD96", "highlight": "#F8DCCD", "line": "#BF927D", "freckles": "#B07963"},
    "fair_warm": {"fill": "#E7C2A4", "shadow": "#C9A383", "highlight": "#F3D7B9", "line": "#9A7A60", "freckles": "#8C5E41"},
    "medium_neutral": {"fill": "#C98E6B", "shadow": "#AE7054", "highlight": "#DDA47F", "line": "#8C5E41", "freckles": "#7A523F"},
    "medium_warm": {"fill": "#C4906B", "shadow": "#A67455", "highlight": "#D3A281", "line": "#765941", "freckles": "#6A4A34"},
    "deep_cool": {"fill": "#8D5C4B", "shadow": "#6F4638", "highlight": "#9E6C58", "line": "#54372C", "freckles": "#43271F"},
    "deep_warm": {"fill": "#6D4436", "shadow": "#523328", "highlight": "#7D5142", "line": "#3D271F", "freckles": "#2F1F1A"},
}

EYE_HEX: Dict[str, Dict[str, str]] = {
    "blue_light": {"iris": "#5AA4D6", "ring": "#274A70", "inner": "#82BEEA", "pupil": "#0F0F10", "sclera": "#F5F7FB"},
    "blue_deep": {"iris": "#356FAD", "ring": "#1E4165", "inner": "#608FC9", "pupil": "#0D0D0D", "sclera": "#F5F7FB"},
    "green": {"iris": "#6AAD6A", "ring": "#2E6B3B", "inner": "#90C68D", "pupil": "#101310", "sclera": "#F5F7FB"},
    "hazel": {"iris": "#8A6E3E", "ring": "#3F321D", "inner": "#B89252", "pupil": "#131313", "sclera": "#F5F7FB"},
    "brown_light": {"iris": "#7A5235", "ring": "#3F2C1D", "inner": "#9B6A44", "pupil": "#111111", "sclera": "#F3F5F7"},
    "brown_deep": {"iris": "#513523", "ring": "#322115", "inner": "#6B452D", "pupil": "#0B0B0B", "sclera": "#F3F5F7"},
    "gray": {"iris": "#8DA3B3", "ring": "#4C6071", "inner": "#ADBECA", "pupil": "#111111", "sclera": "#F5F7FB"},
}

BROW_REFERENCE = {"blonde": "#BE9E67", "light": "#7A5A40", "medium": "#614731", "dark": "#3E2C1F", "auburn": "#7E3E2C", "black": "#201912"}

LIP_PRESETS: Dict[str, Dict[str, str]] = {
    "natural": {"fill": "#D98E8C", "line": "#A56564", "highlight": "#E7A9A7"},
    "rose": {"fill": "#C76876", "line": "#964658", "highlight": "#D98290"},
    "nude": {"fill": "#B9806B", "line": "#875C4C", "highlight": "#C89681"},
}

ACCENT_PRESETS = {"cool": "#9CB4D7", "warm": "#E1A36B", "neutral": "#ADB5BD"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return re.sub(r"\s+", " ", text).strip().lower()


def first_present(flat: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        if key in flat:
            return flat[key]
    return None


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) != 6:
        return (128, 128, 128)
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(channel)))) for channel in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _mix(color: str, factor: float) -> str:
    base = _hex_to_rgb(color)
    if factor >= 0:
        mixed = tuple(channel + (255 - channel) * factor for channel in base)
    else:
        mixed = tuple(channel * (1 + factor) for channel in base)
    return _rgb_to_hex(mixed)


def _darken_desaturate(color: str, darken: float = 0.12, desat: float = 0.08) -> str:
    r, g, b = _hex_to_rgb(color)
    # darken
    r *= (1 - darken)
    g *= (1 - darken)
    b *= (1 - darken)
    # desaturate towards grey
    avg = (r + g + b) / 3
    r = r + (avg - r) * desat
    g = g + (avg - g) * desat
    b = b + (avg - b) * desat
    return _rgb_to_hex((r, g, b))

# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _map_hair(color_raw: Any, dyed_raw: Any, part_raw: Any, style_raw: Any) -> Tuple[str, Dict[str, str], Dict[str, str], List[str]]:
    notes: List[str] = []
    hair_value = _normalise(dyed_raw) if dyed_raw else _normalise(color_raw)
    mapping = {
        "platinum": "platinum_blonde",
        "ash": "light_blonde",
        "light blonde": "light_blonde",
        "dark blonde": "dark_blonde",
        "strawberry": "strawberry_blonde",
        "copper": "copper_red",
        "ginger": "copper_red",
        "auburn": "auburn",
        "medium brown": "medium_brown",
        "light brown": "medium_brown",
        "brown": "dark_brown",
        "dark brown": "dark_brown",
        "black": "black",
        "red": "copper_red",
    }
    palette_key = next((value for token, value in mapping.items() if token in hair_value), "medium_brown")
    if palette_key == "medium_brown" and not hair_value:
        notes.append("hair color missing → default medium_brown")
    elif palette_key == "medium_brown" and hair_value and "brown" not in hair_value:
        notes.append(f"hair color '{color_raw}' not recognised → medium_brown")
    if dyed_raw and dyed_raw != color_raw:
        notes.append(f"used dyed color '{dyed_raw}' over natural '{color_raw}'")

    palette = HAIR_HEX.get(palette_key, HAIR_HEX["medium_brown"])

    part_value = _normalise(part_raw)
    if "right" in part_value:
        hair_part = "right"
    elif "left" in part_value:
        hair_part = "left"
    elif "side" in part_value:
        hair_part = "left"
    else:
        hair_part = "center"

    style_value = _normalise(style_raw)
    overlay = "none"
    if any(token in style_value for token in ["sweep", "side", "fringe", "bang"]):
        overlay = "side_sweep"

    geometry = {
        "part": hair_part,
        "overlay": overlay,
    }
    return palette_key, palette, geometry, notes


def _map_skin(tone_raw: Any, undertone_raw: Any, freckles_raw: Any) -> Tuple[str, Dict[str, Any], bool, List[str]]:
    notes: List[str] = []
    tone_norm = _normalise(tone_raw)
    under_norm = _normalise(undertone_raw)

    base = "fair"
    if any(token in tone_norm for token in ["very fair", "veryfair", "pale", "ivory"]):
        base = "very_fair"
    elif any(token in tone_norm for token in ["tan", "olive", "medium"]):
        base = "medium"
    elif any(token in tone_norm for token in ["deep", "dark", "rich"]):
        base = "deep"

    under = "neutral"
    if "cool" in under_norm:
        under = "cool"
    elif any(token in under_norm for token in ["warm", "gold", "peach"]):
        under = "warm"

    key = f"{base}_{under}"
    if key not in SKIN_HEX:
        notes.append(f"skin tone '{tone_raw}' / undertone '{undertone_raw}' not mapped → fair_neutral")
        key = "fair_neutral"

    palette = dict(SKIN_HEX[key])

    has_freckles = False
    if isinstance(freckles_raw, dict):
        spec = {
            "color": freckles_raw.get("color", palette.get("freckles", palette["line"])),
            "density": _normalise(freckles_raw.get("density", "medium")) or "medium",
            "size": _normalise(freckles_raw.get("size", "small")) or "small",
            "spread": _normalise(freckles_raw.get("spread", "nose_cheeks")) or "nose_cheeks",
        }
        palette["freckles"] = spec
        has_freckles = spec["density"] not in {"none", "absent"}
    else:
        freckles_norm = _normalise(freckles_raw)
        if freckles_norm and freckles_norm not in {"none", "absent", "false"}:
            has_freckles = True

    return key, palette, has_freckles, notes


def _map_eyes(color_raw: Any, shape_raw: Any, size_raw: Any) -> Tuple[str, Dict[str, str], Dict[str, str], List[str]]:
    notes: List[str] = []
    color_norm = _normalise(color_raw)
    mapping = {
        "light blue": "blue_light",
        "deep blue": "blue_deep",
        "blue": "blue_light",
        "green": "green",
        "hazel": "hazel",
        "amber": "hazel",
        "light brown": "brown_light",
        "brown": "brown_deep",
        "dark brown": "brown_deep",
        "gray": "gray",
    }
    palette_key = next((value for token, value in mapping.items() if token in color_norm), "brown_light")
    if palette_key == "brown_light" and color_norm and "brown" not in color_norm:
        notes.append(f"eye color '{color_raw}' not recognised → brown_light")

    palette = EYE_HEX.get(palette_key, EYE_HEX["brown_light"])

    shape_norm = _normalise(shape_raw)
    if "round" in shape_norm or "wide" in shape_norm:
        eye_shape = "round"
    elif "almond" in shape_norm or "hood" in shape_norm:
        eye_shape = "almond"
    else:
        eye_shape = "almond" if palette_key != "brown_light" else "round"

    size_norm = _normalise(size_raw)
    if size_norm in {"small", "s"}:
        eye_size = "s"
    elif size_norm in {"large", "big", "l"}:
        eye_size = "l"
    else:
        eye_size = "m"

    geometry = {
        "shape": eye_shape,
        "size": eye_size,
    }
    return palette_key, palette, geometry, notes


def _map_brows(brows_raw: Any, hair_palette: Dict[str, str]) -> Tuple[str, Dict[str, Any], List[str]]:
    notes: List[str] = []
    color = None
    thickness = "medium"
    arch = "soft"

    if isinstance(brows_raw, dict):
        color = brows_raw.get("color")
        thickness = _normalise(brows_raw.get("thickness", "medium")) or "medium"
        arch = _normalise(brows_raw.get("arch", "soft")) or "soft"
    else:
        norm = _normalise(brows_raw)
        if "thin" in norm:
            thickness = "thin"
        elif "thick" in norm or "dense" in norm:
            thickness = "thick"

        if "flat" in norm:
            arch = "flat"
        elif "high" in norm or "arched" in norm:
            arch = "high"

        color_map = {
            "black": BROW_REFERENCE["black"],
            "dark": BROW_REFERENCE["dark"],
            "medium": BROW_REFERENCE["medium"],
            "light": BROW_REFERENCE["light"],
            "blonde": BROW_REFERENCE["blonde"],
            "auburn": BROW_REFERENCE["auburn"],
        }
        for token, shade in color_map.items():
            if token in norm:
                color = shade
                break

    if not color:
        hair_line = hair_palette.get("line", "#3E2A1E")
        color = _darken_desaturate(hair_line, darken=0.14, desat=0.08)
        notes.append("brow color derived from hair line")

    geometry = {
        "thickness": thickness if thickness in {"thin", "medium", "thick"} else "medium",
        "arch": arch if arch in {"flat", "soft", "high"} else "soft",
        "color": color,
    }
    return color, geometry, notes


def _map_lips(lips_raw: Any, undertone_raw: Any) -> Tuple[str, Dict[str, str], Dict[str, str], List[str]]:
    notes: List[str] = []
    fullness = "medium"
    style = "bow"

    if isinstance(lips_raw, dict):
        norm = _normalise(lips_raw.get("shape", ""))
        if "thin" in norm:
            fullness = "thin"
        elif "full" in norm:
            fullness = "full"
        style = _normalise(lips_raw.get("style", "bow")) or "bow"
        color_hint = lips_raw.get("color")
    else:
        norm = _normalise(lips_raw)
        if "thin" in norm:
            fullness = "thin"
        elif "full" in norm or "plush" in norm:
            fullness = "full"
        if "straight" in norm:
            style = "straight"
        color_hint = None

    palette_key = "natural"
    if color_hint:
        hint_norm = _normalise(color_hint)
    else:
        hint_norm = _normalise(lips_raw)
    if any(token in hint_norm for token in ["rose", "berry", "red"]):
        palette_key = "rose"
    elif any(token in hint_norm for token in ["nude", "neutral", "mauve"]):
        palette_key = "nude"
    elif any(token in hint_norm for token in ["pink", "natural"]):
        palette_key = "natural"
    else:
        undertone = _normalise(undertone_raw)
        if "warm" in undertone:
            palette_key = "nude"

    palette = dict(LIP_PRESETS.get(palette_key, LIP_PRESETS["natural"]))

    geometry = {
        "fullness": fullness,
        "style": style if style in {"bow", "straight"} else "bow",
    }

    return palette_key, palette, geometry, notes


def _map_face(face_shape_raw: Any, jaw_raw: Any, cheeks_raw: Any, nose_raw: Any, symmetry_raw: Any) -> Tuple[Dict[str, str], List[str]]:
    notes: List[str] = []
    shape_norm = _normalise(face_shape_raw)
    if "round" in shape_norm:
        face_shape = "round"
    elif "heart" in shape_norm:
        face_shape = "heart"
    elif "square" in shape_norm or "angular" in shape_norm:
        face_shape = "square"
    else:
        face_shape = "oval"
        if shape_norm and "oval" not in shape_norm:
            notes.append(f"face shape '{face_shape_raw}' → oval fallback")

    jaw_norm = _normalise(jaw_raw)
    if "sharp" in jaw_norm or "defined" in jaw_norm:
        jaw = "angular"
    elif "soft" in jaw_norm or "rounded" in jaw_norm:
        jaw = "soft"
    else:
        jaw = "neutral"

    cheeks_norm = _normalise(cheeks_raw)
    cheeks = "normal"
    if "prominent" in cheeks_norm or "high" in cheeks_norm:
        cheeks = "defined"
    elif "flat" in cheeks_norm or "subtle" in cheeks_norm:
        cheeks = "subtle"

    nose_norm = _normalise(nose_raw)
    if "slim" in nose_norm or "narrow" in nose_norm:
        nose = "slim"
    elif "wide" in nose_norm or "broad" in nose_norm:
        nose = "broad"
    else:
        nose = "medium"

    symmetry_norm = _normalise(symmetry_raw)
    symmetry = "balanced"
    if "high" in symmetry_norm or "excellent" in symmetry_norm:
        symmetry = "high"
    elif "low" in symmetry_norm or "asym" in symmetry_norm:
        symmetry = "low"

    geometry = {
        "shape": face_shape,
        "jaw": jaw,
        "cheeks": cheeks,
        "nose": nose,
        "symmetry": symmetry,
    }
    return geometry, notes


def _map_accent(undertone_raw: Any) -> Tuple[str, Dict[str, str]]:
    undertone = _normalise(undertone_raw)
    if "cool" in undertone:
        key = "cool"
    elif any(token in undertone for token in ["warm", "gold", "bronze"]):
        key = "warm"
    else:
        key = "neutral"
    primary = ACCENT_PRESETS.get(key, ACCENT_PRESETS["neutral"])
    secondary = _mix(primary, 0.18)
    return key, {"primary": primary, "secondary": secondary}

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def to_palette(resolved: Dict[str, Any]) -> Dict[str, Any]:
    """Produce palette + geometry + debug notes from resolved trait dictionary."""

    notes: List[str] = []
    traits_used: Dict[str, Any] = {}

    hair_palette_key, hair_palette, hair_geometry, hair_notes = _map_hair(
        first_present(resolved, CANON_KEYS["hair_color"]),
        first_present(resolved, CANON_KEYS["hair_dyed"]),
        first_present(resolved, CANON_KEYS["hair_part"]),
        first_present(resolved, CANON_KEYS["hair_style"]),
    )
    notes.extend(hair_notes)
    traits_used["hair_palette"] = hair_palette_key

    skin_key, skin_palette, has_freckles, skin_notes = _map_skin(
        first_present(resolved, CANON_KEYS["skin_tone"]),
        first_present(resolved, CANON_KEYS["skin_undertone"]),
        first_present(resolved, CANON_KEYS["freckles"]),
    )
    notes.extend(skin_notes)
    traits_used["skin_palette"] = skin_key

    eye_palette_key, eye_palette, eye_geometry, eye_notes = _map_eyes(
        first_present(resolved, CANON_KEYS["eye_color"]),
        first_present(resolved, CANON_KEYS["eye_shape"]),
        first_present(resolved, CANON_KEYS["eye_size"]),
    )
    notes.extend(eye_notes)
    traits_used["eye_palette"] = eye_palette_key

    brow_color, brow_geometry, brow_notes = _map_brows(
        first_present(resolved, CANON_KEYS["brows"]),
        hair_palette,
    )
    notes.extend(brow_notes)
    traits_used["brow_color"] = brow_color

    lip_key, lip_palette, lip_geometry, lip_notes = _map_lips(
        first_present(resolved, CANON_KEYS["lips"]),
        first_present(resolved, CANON_KEYS["skin_undertone"]),
    )
    notes.extend(lip_notes)
    traits_used["lip_palette"] = lip_key

    face_geometry, face_notes = _map_face(
        first_present(resolved, CANON_KEYS["face_shape"]),
        first_present(resolved, CANON_KEYS["jawline"]),
        first_present(resolved, CANON_KEYS["cheeks"]),
        first_present(resolved, CANON_KEYS["nose"]),
        first_present(resolved, CANON_KEYS["symmetry"]),
    )
    notes.extend(face_notes)
    traits_used["face_shape"] = face_geometry["shape"]

    accent_key, accent_palette = _map_accent(first_present(resolved, CANON_KEYS["skin_undertone"]))
    traits_used["accent_palette"] = accent_key

    geometry = {
        "hair": hair_geometry,
        "eyes": eye_geometry,
        "brows": brow_geometry,
        "lips": lip_geometry,
        "face": face_geometry,
    }

    return {
        "palette": {
            "skin": skin_palette,
            "hair": hair_palette,
            "eyes": eye_palette,
            "brows": brow_geometry["color"],
            "lips": lip_palette,
            "accent": accent_palette,
        },
        "palette_keys": {
            "skin": skin_key,
            "hair": hair_palette_key,
            "eyes": eye_palette_key,
            "brows": brow_geometry["color"],
            "lips": lip_key,
            "accent": accent_key,
        },
        "feature_toggles": {
            "show_ears": False,
            "show_neck_ring": False,
            "show_cheek_shade": True,
            "show_hair_shadow": True,
            "show_freckles": has_freckles,
        },
        "geometry": geometry,
        "traits_used": traits_used,
        "notes": notes,
    }


__all__ = ["CANON_KEYS", "first_present", "to_palette"]
