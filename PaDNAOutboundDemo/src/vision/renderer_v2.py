"""Descriptor-aware PaDNA avatar renderer."""

from __future__ import annotations

import base64
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:  # Optional dependency; renderer still works without YAML file.
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

from .palette_loader import get_palette, load_palettes
from .renderer_mappings import to_palette

DEFAULT_SKIN = {
    "fill": "#C98E6B",
    "shadow": "#AE7054",
    "highlight": "#DDA47F",
    "line": "#8C5E41",
    "blush": "#D98A76",
    "freckles": "#8E634F",
}
DEFAULT_HAIR = {
    "base": "#6B4A31",
    "low": "#4E3320",
    "hi": "#8A6242",
    "line": "#3B2414",
}
DEFAULT_EYES = {
    "iris": "#5A4634",
    "ring": "#3C2C1F",
    "inner": "#745743",
    "pupil": "#181818",
    "sclera": "#F4F6F8",
}

THEMES_DIR = Path(__file__).resolve().parent / "themes"
RENDERER_MAP_PATH = Path(__file__).resolve().parent.parent.parent / "config/renderer_trait_map.yaml"


def _load_renderer_map(path: Path = RENDERER_MAP_PATH) -> Dict[str, Dict[str, Any]]:
    if yaml is None or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        traits = data.get("traits") if isinstance(data.get("traits"), dict) else {}
        out: Dict[str, Dict[str, Any]] = {}
        for canonical, spec in traits.items():
            if not isinstance(canonical, str) or not isinstance(spec, dict):
                continue
            out[canonical] = spec
        return out
    except Exception:
        return {}


RENDERER_MAP = _load_renderer_map()
THEME_CACHE: Dict[str, str] = {}


def _load_theme_defs(theme: str) -> str:
    theme_key = theme.lower()
    if theme_key in THEME_CACHE:
        return THEME_CACHE[theme_key]
    path = THEMES_DIR / f"{theme_key}.svg"
    if not path.exists():
        THEME_CACHE[theme_key] = ""
        return ""
    try:
        THEME_CACHE[theme_key] = path.read_text(encoding="utf-8")
    except Exception:
        THEME_CACHE[theme_key] = ""
    return THEME_CACHE[theme_key]


def _padna_from_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        return {}

    padna: Dict[str, Any] = {}

    if isinstance(bundle.get("resolved_flat"), Iterable):
        for row in bundle.get("resolved_flat", []):
            if not isinstance(row, dict):
                continue
            canonical_path = row.get("canonical_path")
            if isinstance(canonical_path, str) and canonical_path.startswith("PaDNA."):
                value = row.get("canonical_value", row.get("value"))
                if value not in (None, ""):
                    padna[canonical_path] = value

    if "padna" in bundle and isinstance(bundle.get("padna"), dict):
        for key, value in bundle["padna"].items():
            if value in (None, ""):
                continue
            padna.setdefault(key, value)

    descriptors = bundle.get("results", {}).get("descriptors", {})
    for path, meta in descriptors.items():
        if not isinstance(meta, dict):
            continue
        value = meta.get("value")
        if value in (None, ""):
            continue
        padna.setdefault(path, value)
    return padna


def _first(*keys: str, padna: Dict[str, Any], default: str) -> str:
    for key in keys:
        if key in padna:
            return str(padna[key])
    return default


def _features_from_bundle(bundle: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    padna = _padna_from_bundle(bundle)
    if not RENDERER_MAP:
        return {}, padna

    features: Dict[str, Any] = {}
    for canonical, spec in RENDERER_MAP.items():
        feature = spec.get("feature") if isinstance(spec, dict) else None
        if not feature:
            continue
        value = padna.get(canonical)
        if value in (None, ""):
            continue
        features[feature] = value
    return features, padna


def _feature_value(
    features: Dict[str, Any],
    padna: Dict[str, Any],
    feature_name: str,
    fallback_keys: Iterable[str],
    default: str,
) -> str:
    value = features.get(feature_name)
    if value not in (None, ""):
        return str(value)
    return _first(*fallback_keys, padna=padna, default=default)


def _normalise_text(value: Any) -> str:
    return str(value).strip().lower() if value not in (None, "") else ""


_SKIN_TONE_MAP = {
    "veryfair": "fair",
    "very-fair": "fair",
    "fair": "fair",
    "light": "fair",
    "light-medium": "medium",
    "medium": "medium",
    "tan": "medium",
    "olive": "medium",
    "dark": "deep",
    "deep": "deep",
    "very-dark": "deep",
}

_UNDERTONE_MAP = {
    "cool": "cool",
    "neutral": "neutral",
    "warm": "warm",
    "olive": "neutral",
    "reddish": "warm",
    "golden": "warm",
}

_HAIR_KEYWORDS = {
    "platinum": "platinum_blonde",
    "strawberry": "strawberry_blonde",
    "copper": "copper_red",
    "ginger": "copper_red",
    "auburn": "auburn",
    "light blonde": "light_blonde",
    "blonde": "light_blonde",
    "dark blonde": "strawberry_blonde",
    "light brown": "medium_brown",
    "medium brown": "medium_brown",
    "brown": "dark_brown",
    "dark brown": "dark_brown",
    "black": "black",
}

_EYE_KEYWORDS = {
    "blue": "blue_light",
    "deep blue": "blue_deep",
    "green": "green",
    "hazel": "hazel",
    "amber": "hazel",
    "light brown": "brown_light",
    "brown": "brown_deep",
    "dark brown": "brown_deep",
    "gray": "gray",
}

_LIP_KEYWORDS = {
    "natural": "natural_pink",
    "pink": "natural_pink",
    "rose": "rose",
    "nude": "nude",
}

_BROW_KEYWORDS = {
    "blonde": "blonde",
    "light": "light_brown",
    "medium": "medium_brown",
    "dark": "dark_brown",
    "auburn": "auburn",
    "black": "black",
}


def _hex_channel(value: str, index: int) -> int:
    return int(value[index : index + 2], 16)


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) != 6:
        return (128, 128, 128)
    return (_hex_channel(color, 0), _hex_channel(color, 2), _hex_channel(color, 4))


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(channel)))) for channel in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _mix_color(color: str, factor: float) -> str:
    """Lighten (>0) or darken (<0) color by the given factor."""

    base = _hex_to_rgb(color)
    if factor >= 0:
        mixed = tuple(channel + (255 - channel) * factor for channel in base)
    else:
        mixed = tuple(channel * (1 + factor) for channel in base)
    return _rgb_to_hex(mixed)


def _tattoo_elements(location: str, color: str) -> str:
    loc = location.lower()
    shapes = []
    if "sleeve" in loc or "arm" in loc:
        shapes.append(
            f'<path d="M230,420 q-30,-40 -20,-120" stroke="{color}" stroke-width="6" fill="none" opacity="0.85" />'
        )
    if "forearm" in loc or "wrist" in loc:
        shapes.append(
            f'<circle cx="260" cy="520" r="14" stroke="{color}" stroke-width="4" fill="none" opacity="0.8" />'
        )
    if "neck" in loc:
        shapes.append(
            f'<path d="M480,360 q20,16 40,0" stroke="{color}" stroke-width="4" fill="none" opacity="0.75" />'
        )
    if not shapes:
        shapes.append(
            f'<circle cx="720" cy="440" r="18" stroke="{color}" stroke-width="5" fill="none" opacity="0.7" />'
        )
    return "\n".join(shapes)


def _theme_assets(theme: str, accent_primary: str, accent_secondary: str) -> Tuple[str, str, Dict[str, Any]]:
    theme_key = (theme or "flat_cartoon").lower()
    defs_snippet = _load_theme_defs(theme_key)
    settings: Dict[str, Any] = {
        "hair_shadow_opacity": 0.45,
        "cheek_alpha": 0.14,
        "line_art": False,
        "hair_gradient": False,
    }

    if theme_key == "shaded":
        defs_extra = f"""
    <radialGradient id="bgShaded" cx="50%" cy="40%" r="70%">
      <stop offset="0%" stop-color="{_mix_color(accent_secondary, -0.2)}" stop-opacity="0.08" />
      <stop offset="100%" stop-color="{_mix_color(accent_primary, -0.4)}" stop-opacity="0.35" />
    </radialGradient>
    <linearGradient id="hairGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="rgba(0,0,0,0.18)" />
      <stop offset="100%" stop-color="rgba(0,0,0,0.0)" />
    </linearGradient>
    """
        background = "<rect width=\"100%\" height=\"100%\" fill=\"url(#bgShaded)\" />"
        settings.update({"hair_shadow_opacity": 0.7, "cheek_alpha": 0.18, "hair_gradient": True})
    elif theme_key == "line_art":
        defs_extra = "<style>.line-art-stroke{fill:none;stroke-width:4;stroke:#1F1F1F;stroke-linecap:round;}</style>"
        background = "<rect width='100%' height='100%' fill='#F8F9FA' />"
        settings.update({"hair_shadow_opacity": 0.0, "cheek_alpha": 0.12, "line_art": True})
    else:  # flat_cartoon
        defs_extra = ""
        background = "<rect width='100%' height='100%' fill='#F6F7FB' />"

    defs_combined = "<defs>" + defs_snippet + defs_extra + "</defs>"
    return defs_combined, background, settings


def _freckle_layer(freckles: Any) -> str:
    if not freckles:
        return ""

    if isinstance(freckles, dict):
        color = freckles.get("color") or DEFAULT_SKIN["freckles"]
        density = _normalise_text(freckles.get("density", "medium")) or "medium"
        size = _normalise_text(freckles.get("size", "small")) or "small"
        spread = _normalise_text(freckles.get("spread", "nose_cheeks")) or "nose_cheeks"
    else:
        color = str(freckles)
        density = "medium"
        size = "small"
        spread = "nose_cheeks"

    if density in {"none", "absent", "off"}:
        return ""

    density_settings = {
        "light": {"count": 6, "opacity": 0.14},
        "medium": {"count": 10, "opacity": 0.18},
        "dense": {"count": 14, "opacity": 0.23},
        "heavy": {"count": 14, "opacity": 0.23},
        "sparse": {"count": 6, "opacity": 0.12},
    }
    size_map = {"tiny": 1.6, "small": 2.2, "medium": 2.8, "large": 3.4}
    spread_map = {
        "nose_cheeks": (14.0, 8.0),
        "full": (20.0, 12.0),
        "cheeks": (16.0, 10.0),
    }

    density_key = density if density in density_settings else "medium"
    size_key = size if size in size_map else "small"
    spread_key = spread if spread in spread_map else "nose_cheeks"

    settings = density_settings[density_key]
    count = settings["count"]
    opacity = settings["opacity"]
    base_radius = size_map[size_key]
    amp_x, amp_y = spread_map[spread_key]

    base_positions = [
        (500.0, 392.0),
        (482.0, 398.0),
        (518.0, 398.0),
        (470.0, 410.0),
        (530.0, 410.0),
        (456.0, 420.0),
        (544.0, 420.0),
        (488.0, 430.0),
        (512.0, 430.0),
        (474.0, 404.0),
    ]

    dots: List[str] = []
    for idx in range(count):
        base_x, base_y = base_positions[idx % len(base_positions)]
        phase = idx + 1
        jitter_x = math.sin(phase * 2.17) * amp_x * 0.35
        jitter_y = math.cos(phase * 1.91) * amp_y * 0.35
        radius_variation = math.sin(phase * 1.73) * 0.35
        radius = max(1.2, base_radius + radius_variation)
        cx = base_x + jitter_x
        cy = base_y + jitter_y
        dots.append(
            f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='{radius:.2f}' fill='{color}' opacity='{opacity:.2f}' />"
        )
    return "".join(dots)


def _compose_hair_layer(hair_fill_ref: str, hair_hi: str, hair_line: str, hair_geometry: Dict[str, Any]) -> str:
    part = _normalise_text(hair_geometry.get("part", "center"))
    overlay = _normalise_text(hair_geometry.get("overlay", "none"))

    part_offset = {"left": -32, "center": 0, "right": 32}.get(part, 0)
    part_stroke = _mix_color(hair_line, -0.18)

    part_path = (
        f"<path d='M{500 + part_offset},230 q-8,110 -6,210' stroke='{part_stroke}' stroke-width='4' "
        "stroke-linecap='round' fill='none' opacity='0.55' />"
    )

    overlay_path = ""
    if overlay == "side_sweep":
        sweep_color = _mix_color(hair_hi, -0.1)
        overlay_path = (
            f"<path d='M{480 + part_offset},250 q120,60 60,170' stroke='{sweep_color}' stroke-width='18' "
            "stroke-linecap='round' fill='none' opacity='0.38' />"
        )

    hairline_stroke = _mix_color(hair_line, 0.05)

    return (
        f"<ellipse cx='500' cy='360' rx='220' ry='260' fill='{hair_fill_ref}' stroke='{hair_line}' stroke-width='2' opacity='0.95' />"
        f"<path d='M340,250 q160,-110 320,0' fill='{hair_hi}' opacity='0.32' />"
        f"<path d='M360,320 q80,-140 280,-120' stroke='{hairline_stroke}' stroke-width='24' stroke-linecap='round' fill='none' opacity='0.58' />"
        f"<path d='M420,320 q-10,40 20,80' stroke='{hair_line}' stroke-width='4' fill='none' opacity='0.75' />"
        f"<path d='M580,320 q10,40 -20,80' stroke='{hair_line}' stroke-width='4' fill='none' opacity='0.75' />"
        f"{part_path}"
        f"{overlay_path}"
    )


def _compose_eye_layer(eyes_palette: Dict[str, str], eye_geometry: Dict[str, Any]) -> str:
    shape = _normalise_text(eye_geometry.get("shape", "almond")) or "almond"
    size = _normalise_text(eye_geometry.get("size", "m")) or "m"

    sclera_rx_map = {"round": 44, "almond": 50}
    sclera_ry_map = {"round": 28, "almond": 24}
    iris_map = {"s": 18, "m": 22, "l": 26}
    pupil_map = {"s": 6.0, "m": 7.5, "l": 9.0}

    sclera_rx = sclera_rx_map.get(shape, sclera_rx_map["almond"])
    sclera_ry = sclera_ry_map.get(shape, sclera_ry_map["almond"])
    iris_radius = iris_map.get(size, iris_map["m"])
    pupil_radius = pupil_map.get(size, pupil_map["m"])
    inner_radius = iris_radius * 0.55

    iris_color = _mix_color(eyes_palette.get("iris", DEFAULT_EYES["iris"]), 0.08)
    ring_color = _mix_color(eyes_palette.get("ring", DEFAULT_EYES["ring"]), -0.12)
    inner_color = _mix_color(eyes_palette.get("inner", DEFAULT_EYES["inner"]), 0.12)
    pupil_color = eyes_palette.get("pupil", DEFAULT_EYES["pupil"])
    sclera_color = eyes_palette.get("sclera", DEFAULT_EYES["sclera"])

    def _sclera_path(cx: float, cy: float) -> str:
        if shape == "almond":
            left = cx - sclera_rx
            right = cx + sclera_rx
            top = cy - sclera_ry
            bottom = cy + sclera_ry
            return (
                f"<path d='M{left},{cy} Q{cx},{top} {right},{cy} Q{cx},{bottom} {left},{cy} Z' fill='{sclera_color}' />"
            )
        return f"<ellipse cx='{cx}' cy='{cy}' rx='{sclera_rx}' ry='{sclera_ry}' fill='{sclera_color}' />"

    def _eye_stack(cx: float, cy: float) -> str:
        highlight_x = cx - iris_radius * 0.35
        highlight_y = cy - iris_radius * 0.35
        return (
            _sclera_path(cx, cy)
            + f"<circle cx='{cx}' cy='{cy}' r='{iris_radius}' fill='{iris_color}' stroke='{ring_color}' stroke-width='3.4' />"
            + f"<circle cx='{cx}' cy='{cy}' r='{inner_radius:.1f}' fill='{inner_color}' opacity='0.85' />"
            + f"<circle cx='{cx}' cy='{cy}' r='{pupil_radius:.1f}' fill='{pupil_color}' />"
            + f"<circle cx='{highlight_x:.1f}' cy='{highlight_y:.1f}' r='{iris_radius * 0.18:.1f}' fill='#FFFFFF' opacity='0.55' />"
        )

    return _eye_stack(440.0, 360.0) + _eye_stack(560.0, 360.0)


def _compose_brow_layer(brow_geometry: Dict[str, Any]) -> str:
    color = brow_geometry.get("color", DEFAULT_HAIR["line"])
    thickness = _normalise_text(brow_geometry.get("thickness", "medium")) or "medium"
    arch = _normalise_text(brow_geometry.get("arch", "soft")) or "soft"

    stroke_map = {"thin": 6.0, "medium": 8.0, "thick": 10.0}
    arch_ctrl = {
        "flat": {"ctrl": -16.0, "end": -6.0},
        "soft": {"ctrl": -28.0, "end": -10.0},
        "high": {"ctrl": -36.0, "end": -14.0},
    }

    ctrl = arch_ctrl.get(arch, arch_ctrl["soft"])
    stroke_width = stroke_map.get(thickness, stroke_map["medium"])

    left = (
        f"<path d='M392,320 q48,{ctrl['ctrl']} 96,{ctrl['end']}' stroke='{color}' stroke-width='{stroke_width}' "
        "stroke-linecap='round' stroke-linejoin='round' fill='none' />"
    )
    right = (
        f"<path d='M608,320 q-48,{ctrl['ctrl']} -96,{ctrl['end']}' stroke='{color}' stroke-width='{stroke_width}' "
        "stroke-linecap='round' stroke-linejoin='round' fill='none' />"
    )
    return left + right


def _compose_nose_layer(skin_line: str, skin_shadow: str, face_geometry: Dict[str, Any]) -> str:
    nose = _normalise_text(face_geometry.get("nose", "medium")) or "medium"
    highlight = _mix_color(skin_shadow, 0.32)

    if nose == "slim":
        main = f"<path d='M500,350 q-6,64 -2,124' stroke='{skin_line}' stroke-width='2.4' stroke-linecap='round' fill='none' opacity='0.58' />"
        base = f"<path d='M486,504 q28,12 56,0' stroke='{skin_line}' stroke-width='1.8' stroke-linecap='round' fill='none' opacity='0.45' />"
    elif nose == "broad":
        main = f"<path d='M498,348 q-4,68 6,126' stroke='{skin_line}' stroke-width='3.4' stroke-linecap='round' fill='none' opacity='0.62' />"
        base = f"<path d='M468,508 q40,22 80,0' stroke='{skin_line}' stroke-width='2.6' stroke-linecap='round' fill='none' opacity='0.5' />"
    else:
        main = f"<path d='M500,348 q-6,66 2,124' stroke='{skin_line}' stroke-width='3.0' stroke-linecap='round' fill='none' opacity='0.6' />"
        base = f"<path d='M474,506 q36,18 72,0' stroke='{skin_line}' stroke-width='2.2' stroke-linecap='round' fill='none' opacity='0.48' />"

    bridge = f"<path d='M502,340 q-3,42 0,88' stroke='{highlight}' stroke-width='1.6' stroke-linecap='round' fill='none' opacity='0.35' />"
    return bridge + main + base


def _compose_lip_layer(lips_palette: Dict[str, str], lip_geometry: Dict[str, Any]) -> str:
    fullness = _normalise_text(lip_geometry.get("fullness", "medium")) or "medium"
    style = _normalise_text(lip_geometry.get("style", "bow")) or "bow"

    lip_fill = lips_palette.get("fill", "#D98E8C")
    lip_line = lips_palette.get("line", "#A56564")
    lip_highlight = lips_palette.get("highlight", "#E7A9A7")

    upper_amp_map = {"thin": 24.0, "medium": 38.0, "full": 48.0}
    lower_amp_map = {"thin": 20.0, "medium": 42.0, "full": 56.0}

    upper_amp = upper_amp_map.get(fullness, upper_amp_map["medium"])
    lower_amp = lower_amp_map.get(fullness, lower_amp_map["medium"])

    if style == "straight":
        upper_amp *= 0.65

    highlight_amp = max(upper_amp - 14.0, 16.0)

    return (
        f"<path d='M430,480 q70,{upper_amp:.1f} 140,0' stroke='{lip_line}' stroke-width='8.5' fill='none' stroke-linecap='round' />"
        f"<path d='M430,478 q70,{lower_amp:.1f} 140,0' stroke='{lip_fill}' stroke-width='7.5' fill='none' stroke-linecap='round' opacity='0.88' />"
        f"<path d='M452,464 q48,{highlight_amp:.1f} 96,0' stroke='{lip_highlight}' stroke-width='3.6' fill='none' stroke-linecap='round' opacity='0.55' />"
    )


def _compose_face_layers(
    skin_fill: str,
    skin_line: str,
    skin_shadow: str,
    face_geometry: Dict[str, Any],
) -> Tuple[str, Dict[str, float]]:
    shape = _normalise_text(face_geometry.get("shape", "oval")) or "oval"
    jaw = _normalise_text(face_geometry.get("jaw", "neutral")) or "neutral"
    cheeks = _normalise_text(face_geometry.get("cheeks", "normal")) or "normal"

    templates = {
        "oval": {"rx": 170, "ry": 210, "jaw_width": 160, "chin_drop": 120, "shadow_y": 470},
        "round": {"rx": 182, "ry": 198, "jaw_width": 170, "chin_drop": 110, "shadow_y": 468},
        "heart": {"rx": 166, "ry": 208, "jaw_width": 142, "chin_drop": 132, "shadow_y": 472},
        "square": {"rx": 174, "ry": 205, "jaw_width": 184, "chin_drop": 104, "shadow_y": 466},
    }
    jaw_curve_map = {"soft": 72.0, "neutral": 62.0, "angular": 48.0}
    cheek_map = {
        "subtle": {"rx": 30.0, "ry": 20.0, "alpha": 0.12},
        "normal": {"rx": 34.0, "ry": 22.0, "alpha": 0.16},
        "defined": {"rx": 38.0, "ry": 24.0, "alpha": 0.20},
    }

    template = templates.get(shape, templates["oval"])
    jaw_curve = jaw_curve_map.get(jaw, jaw_curve_map["neutral"])
    jaw_width = template["jaw_width"]
    chin_drop = template["chin_drop"]
    shadow_y = template["shadow_y"]

    base = (
        f"<ellipse cx='500' cy='380' rx='{template['rx']}' ry='{template['ry']}' fill='{skin_fill}' stroke='{skin_line}' stroke-width='1.8' />"
    )

    first_ctrl_y = jaw_curve * 0.55
    second_ctrl_x = max(8.0, jaw_curve * 0.18)
    shadow_color = _mix_color(skin_shadow, -0.04)

    shadow = (
        f"<path d='M500,{shadow_y} q-{jaw_curve:.1f},{first_ctrl_y:.1f} -{jaw_width:.1f},0 q{second_ctrl_x:.1f},{chin_drop:.1f} {jaw_width:.1f},{chin_drop:.1f} "
        f"q{jaw_width + jaw_curve * 0.8:.1f},{-chin_drop * 0.36:.1f} {jaw_width + 16:.1f},{-chin_drop * 0.46:.1f} q-{jaw_curve:.1f},{first_ctrl_y:.1f} -{jaw_width:.1f},0' "
        f"fill='{shadow_color}' opacity='0.12' />"
    )

    cheek_dims = cheek_map.get(cheeks, cheek_map["normal"])
    return base + shadow, cheek_dims


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return default


def render_svg(bundle: Dict[str, Any], *, width: int = 1000, height: int = 900) -> Dict[str, Any]:
    features, padna = _features_from_bundle(bundle)
    missing_traits = []
    if RENDERER_MAP:
        missing_traits = [
            canonical
            for canonical in RENDERER_MAP
            if canonical.startswith("PaDNA.") and canonical not in padna
        ]

    renderer_cfg = bundle.get("renderer") if isinstance(bundle.get("renderer"), dict) else {}
    theme = (renderer_cfg.get("theme") or "flat_cartoon").lower()
    user_palette_keys = renderer_cfg.get("palette_keys") if isinstance(renderer_cfg.get("palette_keys"), dict) else {}

    palette_info = to_palette(padna)
    palette_keys = dict(palette_info.get("palette_keys", {}))
    palette_values = dict(palette_info.get("palette", {}))
    default_toggles = dict(palette_info.get("feature_toggles", {}))
    mapping_notes = list(palette_info.get("notes", []))
    traits_used = dict(palette_info.get("traits_used", {}))
    geometry = {key: dict(value) for key, value in (palette_info.get("geometry", {}) or {}).items() if isinstance(value, dict)}
    fallback_notes: List[str] = []

    for key, value in user_palette_keys.items():
        if not isinstance(value, str):
            continue
        palette_keys[key] = value
        if key == "skin":
            palette_values["skin"] = get_palette("skin", value, default=palette_values.get("skin", DEFAULT_SKIN))
        elif key == "hair":
            palette_values["hair"] = get_palette("hair", value, default=palette_values.get("hair", DEFAULT_HAIR))
        elif key == "eyes":
            palette_values["eyes"] = get_palette("eyes", value, default=palette_values.get("eyes", DEFAULT_EYES))
        elif key == "lips":
            palette_values["lips"] = get_palette(
                "lips",
                value,
                default=palette_values.get("lips", {"fill": "#D98E8C", "line": "#A56564", "highlight": "#E7A9A7"}),
            )
        elif key == "brows":
            brow_map = load_palettes().get("brows", {})
            if isinstance(brow_map, dict):
                palette_values["brows"] = brow_map.get(value, palette_values.get("brows", DEFAULT_HAIR["line"]))
        elif key == "accent":
            accent_hex = get_palette("accent", value, default=None)
            if isinstance(accent_hex, str):
                palette_values["accent"] = {"primary": accent_hex, "secondary": _mix_color(accent_hex, 0.2)}

    palette_spec = renderer_cfg.get("palette_spec") if isinstance(renderer_cfg.get("palette_spec"), dict) else None
    if palette_spec:
        spec_palette = palette_spec.get("palette") if isinstance(palette_spec.get("palette"), dict) else {}

        if isinstance(spec_palette.get("skin"), dict):
            current = dict(palette_values.get("skin", DEFAULT_SKIN))
            current.update(spec_palette["skin"])
            palette_values["skin"] = current

        if isinstance(spec_palette.get("hair"), dict):
            hair_override = {k: v for k, v in spec_palette["hair"].items() if k in {"base", "low", "hi", "line"}}
            if hair_override:
                current = dict(palette_values.get("hair", DEFAULT_HAIR))
                current.update(hair_override)
                palette_values["hair"] = current
            hair_geometry = geometry.setdefault("hair", {})
            if "part" in spec_palette["hair"]:
                part_value = _normalise_text(spec_palette["hair"].get("part"))
                if part_value in {"left", "right", "center"}:
                    hair_geometry["part"] = part_value
                else:
                    fallback_notes.append(f"hair part '{spec_palette['hair'].get('part')}' → center")
                    hair_geometry["part"] = "center"
            if "overlay" in spec_palette["hair"]:
                overlay_value = _normalise_text(spec_palette["hair"].get("overlay"))
                if overlay_value in {"side_sweep", "none"}:
                    hair_geometry["overlay"] = overlay_value
                else:
                    fallback_notes.append(f"hair overlay '{spec_palette['hair'].get('overlay')}' unsupported → none")
                    hair_geometry["overlay"] = "none"

        if isinstance(spec_palette.get("eyes"), dict):
            eye_override = {k: v for k, v in spec_palette["eyes"].items() if k in {"iris", "ring", "inner", "pupil", "sclera"}}
            if eye_override:
                current = dict(palette_values.get("eyes", DEFAULT_EYES))
                current.update(eye_override)
                palette_values["eyes"] = current
            eye_geometry = geometry.setdefault("eyes", {})
            if "shape" in spec_palette["eyes"]:
                shape_value = _normalise_text(spec_palette["eyes"].get("shape"))
                if shape_value in {"round", "almond"}:
                    eye_geometry["shape"] = shape_value
                else:
                    fallback_notes.append(f"eye shape '{spec_palette['eyes'].get('shape')}' → almond")
                    eye_geometry["shape"] = "almond"
            if "size" in spec_palette["eyes"]:
                size_value = _normalise_text(spec_palette["eyes"].get("size"))
                if size_value in {"s", "m", "l"}:
                    eye_geometry["size"] = size_value
                else:
                    fallback_notes.append(f"eye size '{spec_palette['eyes'].get('size')}' → m")
                    eye_geometry["size"] = "m"

        if isinstance(spec_palette.get("lips"), dict):
            lip_override = {k: v for k, v in spec_palette["lips"].items() if k in {"fill", "line", "highlight"}}
            if lip_override:
                current = dict(palette_values.get("lips", {"fill": "#D98E8C", "line": "#A56564", "highlight": "#E7A9A7"}))
                current.update(lip_override)
                palette_values["lips"] = current
            lip_geometry = geometry.setdefault("lips", {})
            if "fullness" in spec_palette["lips"]:
                lip_geometry["fullness"] = _normalise_text(spec_palette["lips"].get("fullness", "medium")) or "medium"
            if "style" in spec_palette["lips"]:
                lip_geometry["style"] = _normalise_text(spec_palette["lips"].get("style", "bow")) or "bow"

        if isinstance(spec_palette.get("brows"), dict):
            brow_geometry = geometry.setdefault("brows", {})
            color_override = spec_palette["brows"].get("color")
            if isinstance(color_override, str) and color_override:
                palette_values["brows"] = color_override
                brow_geometry["color"] = color_override
            if "thickness" in spec_palette["brows"]:
                brow_geometry["thickness"] = _normalise_text(spec_palette["brows"].get("thickness", "medium")) or "medium"
            if "arch" in spec_palette["brows"]:
                brow_geometry["arch"] = _normalise_text(spec_palette["brows"].get("arch", "soft")) or "soft"

        if isinstance(spec_palette.get("accent"), dict):
            accent_spec = spec_palette["accent"]
            if "primary" in accent_spec and "secondary" in accent_spec:
                palette_values["accent"] = {
                    "primary": accent_spec.get("primary", palette_values.get("accent", {}).get("primary", "#ADB5BD")),
                    "secondary": accent_spec.get("secondary", palette_values.get("accent", {}).get("secondary", _mix_color("#ADB5BD", 0.2))),
                }

    # Defaults for geometry keys to avoid KeyError downstream
    hair_geometry = geometry.setdefault("hair", {})
    hair_geometry.setdefault("part", "center")
    hair_geometry.setdefault("overlay", "none")
    eye_geometry = geometry.setdefault("eyes", {})
    eye_geometry.setdefault("shape", "almond")
    eye_geometry.setdefault("size", "m")
    brow_geometry = geometry.setdefault("brows", {})
    lip_geometry = geometry.setdefault("lips", {})
    lip_geometry.setdefault("fullness", "medium")
    lip_geometry.setdefault("style", "bow")
    face_geometry = geometry.setdefault("face", {})
    face_geometry.setdefault("shape", "oval")
    face_geometry.setdefault("jaw", "neutral")
    face_geometry.setdefault("cheeks", "normal")
    face_geometry.setdefault("nose", "medium")

    if face_geometry.get("shape") not in {"oval", "heart", "round", "square"}:
        fallback_notes.append(f"face shape '{face_geometry.get('shape')}' → oval")
        face_geometry["shape"] = "oval"
    if face_geometry.get("jaw") not in {"soft", "neutral", "angular"}:
        if "jaw" in face_geometry:
            fallback_notes.append(f"jawline '{face_geometry.get('jaw')}' → neutral")
        face_geometry["jaw"] = "neutral"
    if face_geometry.get("cheeks") not in {"subtle", "normal", "defined"}:
        if "cheeks" in face_geometry:
            fallback_notes.append(f"cheek descriptor '{face_geometry.get('cheeks')}' → normal")
        face_geometry["cheeks"] = "normal"
    if face_geometry.get("nose") not in {"slim", "medium", "broad"}:
        if "nose" in face_geometry:
            fallback_notes.append(f"nose '{face_geometry.get('nose')}' → medium")
        face_geometry["nose"] = "medium"

    if lip_geometry.get("fullness") not in {"thin", "medium", "full"}:
        fallback_notes.append(f"lip fullness '{lip_geometry.get('fullness')}' → medium")
        lip_geometry["fullness"] = "medium"
    if lip_geometry.get("style") not in {"bow", "straight"}:
        fallback_notes.append(f"lip style '{lip_geometry.get('style')}' → bow")
        lip_geometry["style"] = "bow"

    if brow_geometry.get("thickness") not in {"thin", "medium", "thick"}:
        if "thickness" in brow_geometry:
            fallback_notes.append(f"brow thickness '{brow_geometry.get('thickness')}' → medium")
        brow_geometry["thickness"] = "medium"
    if brow_geometry.get("arch") not in {"flat", "soft", "high"}:
        if "arch" in brow_geometry:
            fallback_notes.append(f"brow arch '{brow_geometry.get('arch')}' → soft")
        brow_geometry["arch"] = "soft"

    skin_palette = dict(palette_values.get("skin", DEFAULT_SKIN))
    hair_palette = dict(palette_values.get("hair", DEFAULT_HAIR))
    eyes_palette = dict(palette_values.get("eyes", DEFAULT_EYES))
    lips_palette = dict(palette_values.get("lips", {"fill": "#D98E8C", "line": "#A56564", "highlight": "#E7A9A7"}))
    brow_color = palette_values.get("brows", hair_palette.get("line", DEFAULT_HAIR["line"]))
    if brow_geometry.get("color"):
        brow_color = brow_geometry["color"]
    else:
        brow_geometry["color"] = brow_color
    palette_values["brows"] = brow_color
    accent_palette = palette_values.get("accent", {"primary": "#ADB5BD", "secondary": "#C2C8CE"})
    accent_primary = accent_palette.get("primary", "#ADB5BD")
    accent_secondary = accent_palette.get("secondary", _mix_color(accent_primary, 0.2))

    posture = _feature_value(
        features,
        padna,
        "body.posture",
        ["PaDNA.PostureDNA", "BodyDNA.Posture", "PostureDNA"],
        "neutral",
    )
    apparel_palette = _first(
        "PaDNA.ApparelDNA.Palette",
        "ApparelDNA.Palette",
        padna=padna,
        default=palette_keys.get("accent", "neutral"),
    )
    apparel_style = _first(
        "PaDNA.ApparelDNA.Style",
        "ApparelDNA.Style",
        padna=padna,
        default="classic",
    )
    apparel_fit = _first(
        "PaDNA.ApparelDNA.Fit",
        "ApparelDNA.Fit",
        padna=padna,
        default="regular",
    )
    tattoos = _first(
        "PaDNA.DistinguishingMarksDNA.Tattoos.Location",
        "DistinguishingMarksDNA.Tattoos.Location",
        padna=padna,
        default="",
    )
    tattoos_present = _first(
        "PaDNA.DistinguishingMarksDNA.Tattoos",
        "DistinguishingMarksDNA.Tattoos",
        padna=padna,
        default="none",
    )
    glasses = _first("PaDNA.GlassesDNA", "GlassesDNA", padna=padna, default="none")

    if palette_spec:
        apparel_override = palette_spec.get("apparel") if isinstance(palette_spec.get("apparel"), dict) else {}
        if apparel_override:
            apparel_style = apparel_override.get("style", apparel_style)
            apparel_fit = apparel_override.get("fit", apparel_fit)
            apparel_palette = apparel_override.get("palette", apparel_palette)
        if palette_spec.get("posture"):
            posture = str(palette_spec["posture"])
        if "tattoos" in palette_spec:
            tattoos = palette_spec.get("tattoos", tattoos)
            tattoos_present = palette_spec.get("tattoos", tattoos_present)

    default_toggles.setdefault("show_ears", False)
    default_toggles.setdefault("show_neck_ring", False)
    default_toggles.setdefault("show_cheek_shade", True)
    default_toggles.setdefault("show_hair_shadow", True)
    default_toggles.setdefault("show_freckles", True)
    feature_toggles_cfg = renderer_cfg.get("feature_toggles") if isinstance(renderer_cfg.get("feature_toggles"), dict) else {}
    feature_toggles = {
        key: _bool(feature_toggles_cfg.get(key), default)
        for key, default in default_toggles.items()
    }

    freckles_entry = skin_palette.get("freckles")
    if isinstance(freckles_entry, dict):
        density_value = _normalise_text(freckles_entry.get("density", "medium"))
        feature_toggles["show_freckles"] = density_value not in {"none", "absent", "off"}
    elif not freckles_entry:
        feature_toggles["show_freckles"] = False

    debug_layers = _bool(renderer_cfg.get("debug_layers"), False)

    posture_shift = {
        "slight-tilt-left": -35,
        "slight-tilt-right": 35,
        "upright": 0,
        "neutral": 0,
        "slouched": 0,
    }.get(posture.lower(), 0)
    shoulder_tilt = -10 if posture.lower() == "slouched" else 0

    fit_scale = {
        "relaxed": 1.15,
        "regular": 1.0,
        "tailored": 0.92,
        "fitted": 0.9,
    }.get(apparel_fit.lower(), 1.0)

    hair_texture = _feature_value(
        features,
        padna,
        "hair.texture",
        ["PaDNA.HairDNA.Texture", "HairDNA.Texture"],
        "straight",
    ).lower()
    has_tattoos = str(tattoos_present).lower() not in {"none", "false"}

    defs_block, background_rect, theme_settings = _theme_assets(theme, accent_primary, accent_secondary)

    skin_fill = skin_palette.get("fill", DEFAULT_SKIN["fill"])
    skin_shadow = skin_palette.get("shadow", DEFAULT_SKIN["shadow"])
    skin_highlight = skin_palette.get("highlight", DEFAULT_SKIN["highlight"])
    skin_line = skin_palette.get("line", DEFAULT_SKIN["line"])
    blush_color = skin_palette.get("blush", DEFAULT_SKIN["blush"])
    hair_base = hair_palette.get("base", DEFAULT_HAIR["base"])
    hair_low = hair_palette.get("low", DEFAULT_HAIR["low"])
    hair_hi = hair_palette.get("hi", DEFAULT_HAIR["hi"])
    hair_line = hair_palette.get("line", DEFAULT_HAIR["line"])

    hair_fill_ref = hair_base
    if theme_settings.get("hair_gradient"):
        hair_fill_ref = "url(#hairGrad)"

    coat_color = accent_primary
    accent_color = accent_secondary
    if theme_settings.get("line_art"):
        coat_color = "#FFFFFF"
        accent_color = accent_primary

    tattoo_layer = _tattoo_elements(tattoos, accent_color) if has_tattoos else ""
    glasses_layer = ""
    if str(glasses).lower() in {"yes", "regular", "occasional"}:
        stroke = _mix_color(accent_color, -0.4)
        glasses_layer = (
            f"<path d='M396,230 h48 a20,20 0 0 1 0,40 h-48 z' stroke='{stroke}' stroke-width='6' fill='none'/>"
            f"<path d='M556,230 h48 a20,20 0 0 1 0,40 h-48 z' stroke='{stroke}' stroke-width='6' fill='none'/>"
            f"<line x1='444' y1='250' x2='556' y2='250' stroke='{stroke}' stroke-width='4'/>"
        )

    hair_texture_layer = ""
    if feature_toggles["show_hair_shadow"] and hair_texture in {"wavy", "curly", "coily"} and theme_settings.get("hair_shadow_opacity", 0) > 0:
        wave_path = (
            "M320,240 q40,40 0,80 \n"
            "M360,240 q40,40 0,80 \n"
            "M640,240 q-40,40 0,80 \n"
            "M600,240 q-40,40 0,80"
        )
        hair_texture_layer = (
            f"<path d='{wave_path}' stroke='{hair_low}' stroke-width='8' fill='none' opacity='{theme_settings['hair_shadow_opacity']:.2f}' />"
        )

    lower_style = (apparel_style or "").lower()
    apparel_allowed = lower_style in {"hooded", "scarf", "jacket"}
    style_overlay = ""
    if apparel_allowed:
        if lower_style == "hooded":
            hood_color = _mix_color(coat_color, -0.08)
            style_overlay = (
                f"<path d='M300,232 q200,-160 400,0 q-18,168 -200,240 q-186,-64 -200,-240' fill='{hood_color}' opacity='0.6' />"
                f"<path d='M340,520 q160,120 320,0' fill='none' stroke='{_mix_color(hood_color, -0.2)}' stroke-width='10' opacity='0.42' />"
            )
        elif lower_style == "scarf":
            scarf_color = _mix_color(coat_color, -0.12)
            style_overlay = (
                f"<path d='M360,560 q140,80 280,0 q-14,52 -140,94 q-128,-34 -140,-94' fill='{scarf_color}' opacity='0.76' />"
                f"<path d='M488,602 q36,52 -14,116' stroke='{_mix_color(scarf_color, -0.22)}' stroke-width='12' stroke-linecap='round' opacity='0.52' />"
            )
        elif lower_style == "jacket":
            lapel_color = _mix_color(coat_color, -0.18)
            style_overlay = (
                f"<path d='M360,520 l88,148' stroke='{lapel_color}' stroke-width='10' stroke-linecap='round' opacity='0.5' fill='none' />"
                f"<path d='M640,520 l-88,148' stroke='{lapel_color}' stroke-width='10' stroke-linecap='round' opacity='0.5' fill='none' />"
            )
    else:
        if lower_style not in {"", "classic", "none", "neutral"}:
            fallback_notes.append(f"apparel style '{apparel_style}' skipped (no collar mode)")
        style_overlay = ""

    ear_layer = ""
    if feature_toggles["show_ears"]:
        ear_layer = (
            f"<ellipse cx='320' cy='480' rx='48' ry='118' fill='{skin_fill}' opacity='0.92' stroke='{skin_line}' stroke-width='1.2' />"
            f"<ellipse cx='680' cy='480' rx='48' ry='118' fill='{skin_fill}' opacity='0.92' stroke='{skin_line}' stroke-width='1.2' />"
        )

    neck_ring_layer = ""
    if feature_toggles["show_neck_ring"]:
        ring_color = _mix_color(accent_secondary, -0.25)
        neck_ring_layer = f"<ellipse cx='500' cy='600' rx='210' ry='110' fill='{ring_color}' opacity='0.45' />"

    face_base_layer, cheek_dims = _compose_face_layers(skin_fill, skin_line, skin_shadow, face_geometry)

    cheek_layer = ""
    if feature_toggles["show_cheek_shade"]:
        cheek_opacity_scale = theme_settings.get("cheek_alpha", 0.16) / 0.16
        cheek_alpha = cheek_dims["alpha"] * cheek_opacity_scale
        cheek_layer = (
            f"<ellipse cx='430' cy='420' rx='{cheek_dims['rx']}' ry='{cheek_dims['ry']}' fill='{skin_shadow}' opacity='{cheek_alpha:.2f}' />"
            f"<ellipse cx='570' cy='420' rx='{cheek_dims['rx']}' ry='{cheek_dims['ry']}' fill='{skin_shadow}' opacity='{cheek_alpha:.2f}' />"
        )

    freckles_layer = ""
    if feature_toggles["show_freckles"]:
        freckles_layer = _freckle_layer(skin_palette.get("freckles"))

    hair_layer = _compose_hair_layer(hair_fill_ref, hair_palette.get("hi", hair_hi), hair_palette.get("line", hair_line), hair_geometry)
    eyes_layer = _compose_eye_layer(eyes_palette, eye_geometry)
    brow_layer = _compose_brow_layer(brow_geometry)
    nose_layer = _compose_nose_layer(skin_line, skin_shadow, face_geometry)
    lip_layer = _compose_lip_layer(lips_palette, lip_geometry)

    clothing_layer = ""
    if apparel_allowed:
        clothing_color = coat_color if lower_style != "scarf" else _mix_color(coat_color, -0.06)
        clothing_layer = (
            f"<path d='M320,520 q180,{140 * fit_scale:.1f} 360,0 q-20,200 -180,240 q-160,-40 -180,-240' fill='{clothing_color}' opacity='0.9' transform='rotate({shoulder_tilt} 500 650)' />"
        )

    debug_overlay = ""
    if debug_layers:
        debug_overlay = (
            "<g id='debug_overlay' fill='none' stroke='rgba(255,0,0,0.35)' stroke-dasharray='6 4'>"
            "<rect x='260' y='240' width='480' height='440' />"
            "</g>"
        )

    svg = f"""
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  {defs_block}
  {background_rect}
  <g transform="translate({posture_shift},0)">
    {neck_ring_layer}
    {clothing_layer}
    {style_overlay}
    {tattoo_layer}
    {face_base_layer}
    {cheek_layer}
    {ear_layer}
    {hair_texture_layer}
    {hair_layer}
    {eyes_layer}
    {brow_layer}
    {nose_layer}
    {lip_layer}
    {freckles_layer}
    {glasses_layer}
  </g>
  {debug_overlay}
</svg>
"""

    data_url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {
        "svg": svg,
        "data_url": data_url,
        "padna": padna,
        "features": features,
        "missing_traits": missing_traits,
        "palette": {
            "skin": skin_palette,
            "hair": hair_palette,
            "eyes": eyes_palette,
            "lips": lips_palette,
            "brows": brow_color,
            "accent": {"primary": accent_primary, "secondary": accent_secondary},
        },
        "apparel": {
            "style": apparel_style,
            "fit": apparel_fit,
            "palette": apparel_palette,
        },
        "posture": posture,
        "tattoos": tattoos if has_tattoos else "none",
        "geometry": geometry,
        "config": {
            "theme": theme,
            "palette_keys": palette_keys,
            "feature_toggles": feature_toggles,
            "debug_layers": debug_layers,
            "palette_spec": palette_spec or {},
        },
        "debug": {
            "traits_used": traits_used,
            "palette_keys": palette_keys,
            "mapping_notes": mapping_notes,
            "feature_toggles": feature_toggles,
            "geometry": geometry,
            "fallbacks": fallback_notes,
        },
    }


__all__ = ["render_svg"]
