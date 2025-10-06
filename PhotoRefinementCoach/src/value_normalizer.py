"""Helpers for coercing values during soft PaDNA imports."""

from __future__ import annotations

import math
import re
from typing import Any, List, Optional, Tuple

_HEIGHT_PATTERN_FEET = re.compile(
    r"^(?P<feet>\d+)\s*(?:'|ft|feet)\s*(?:(?P<inches>\d+)\s*(?:\"|in|inches)?)?\s*$",
    re.IGNORECASE,
)
_HEIGHT_PATTERN_METRIC = re.compile(
    r"^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>cm|centimeter|centimeters|m|meter|meters)\s*$",
    re.IGNORECASE,
)
_HEIGHT_PATTERN_INCH = re.compile(
    r"^(?P<value>\d+(?:\.\d+)?)\s*(?:\"|in|inch|inches)\s*$",
    re.IGNORECASE,
)
_WEIGHT_PATTERN = re.compile(
    r"^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|kilogram|kilograms|lb|lbs|pound|pounds|stone|stones|st)\s*$",
    re.IGNORECASE,
)
_BOOLEAN_STRINGS = {
    "true": True,
    "t": True,
    "yes": True,
    "y": True,
    "1": True,
    "false": False,
    "f": False,
    "no": False,
    "n": False,
    "0": False,
}


NumberResult = Tuple[Optional[float], List[str]]
ValueResult = Tuple[Any, List[str]]


def normalize_value_for_path(path: str, value: Any) -> ValueResult:
    """Normalize common value patterns keyed by canonical PaDNA paths."""

    warnings: List[str] = []
    canonical = path.strip()

    if canonical == "PaDNA.BodyDNA.HeightCM":
        coerced, notes = _normalize_height(value)
        warnings.extend(notes)
        return coerced if coerced is not None else value, warnings

    if canonical == "PaDNA.BodyDNA.WeightKG":
        coerced, notes = _normalize_weight(value)
        warnings.extend(notes)
        return coerced if coerced is not None else value, warnings

    if canonical in {"confidence", "Confidence"}:
        coerced, notes = normalize_confidence(value)
        warnings.extend(notes)
        return coerced if coerced is not None else value, warnings

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return "", warnings
        normalized = title_case_enum(cleaned)
        if normalized != value:
            warnings.append("value coerced to title case")
        return normalized, warnings

    return value, warnings


def title_case_enum(raw: str) -> str:
    """Title-case strings while preserving apostrophes and hyphens."""

    def _title_fragment(fragment: str) -> str:
        if not fragment:
            return fragment
        return fragment[0].upper() + fragment[1:].lower()

    parts = re.split(r"([\s\-_/]+)", raw)
    rebuilt: List[str] = []
    for token in parts:
        if not token:
            continue
        if re.fullmatch(r"[\s\-_/]+", token):
            rebuilt.append(token)
        else:
            rebuilt.append(_title_fragment(token))
    return "".join(rebuilt)


def _normalize_height(value: Any) -> NumberResult:
    warnings: List[str] = []
    if value is None:
        return None, warnings
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 0:
            warnings.append("height dropped (non-positive numeric)")
            return None, warnings
        return number, warnings

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None, warnings
        normalized = cleaned.replace("’", "'").replace("“", '"').replace("”", '"')

        match = _HEIGHT_PATTERN_FEET.match(normalized)
        if match:
            feet = int(match.group("feet"))
            inches = int(match.group("inches")) if match.group("inches") else 0
            total_inches = feet * 12 + inches
            cm_value = total_inches * 2.54
            warnings.append("height interpreted as feet/inches")
            return cm_value, warnings

        match = _HEIGHT_PATTERN_METRIC.match(normalized)
        if match:
            number = float(match.group("value"))
            unit = match.group("unit").lower()
            if unit.startswith("m") and not unit.startswith("cm"):
                warnings.append("height converted from meters")
                return number * 100.0, warnings
            warnings.append("height parsed in centimeters")
            return number, warnings

        match = _HEIGHT_PATTERN_INCH.match(normalized)
        if match:
            number = float(match.group("value"))
            warnings.append("height converted from inches")
            return number * 2.54, warnings

        try:
            numeric = float(normalized)
        except ValueError:
            warnings.append("height not recognized; leaving raw")
            return None, warnings
        if numeric <= 0:
            warnings.append("height dropped (non-positive numeric)")
            return None, warnings
        warnings.append("height assumed centimeters without unit")
        return numeric, warnings

    warnings.append("height not recognized; leaving raw")
    return None, warnings


def _normalize_weight(value: Any) -> NumberResult:
    warnings: List[str] = []
    if value is None:
        return None, warnings
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 0:
            warnings.append("weight dropped (non-positive numeric)")
            return None, warnings
        return number, warnings

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None, warnings
        normalized = cleaned.replace("lbs", "lb")
        match = _WEIGHT_PATTERN.match(normalized)
        if match:
            number = float(match.group("value"))
            unit = match.group("unit").lower()
            if unit.startswith("kg"):
                warnings.append("weight parsed in kilograms")
                return number, warnings
            if unit in {"lb", "pound"}:
                warnings.append("weight converted from pounds")
                return number * 0.45359237, warnings
            if unit in {"stone", "st"}:
                warnings.append("weight converted from stone")
                return number * 6.35029318, warnings
        try:
            numeric = float(normalized)
        except ValueError:
            warnings.append("weight not recognized; leaving raw")
            return None, warnings
        if numeric <= 0:
            warnings.append("weight dropped (non-positive numeric)")
            return None, warnings
        warnings.append("weight assumed kilograms without unit")
        return numeric, warnings

    warnings.append("weight not recognized; leaving raw")
    return None, warnings


def normalize_confidence(value: Any) -> NumberResult:
    warnings: List[str] = []
    if value is None:
        return None, warnings
    if isinstance(value, bool):
        return float(value), warnings
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None, warnings
        percent = cleaned.endswith("%")
        stripped = cleaned[:-1] if percent else cleaned
        try:
            number = float(stripped)
        except ValueError:
            warnings.append("confidence not recognized; leaving raw")
            return None, warnings
        if percent:
            number /= 100.0
            warnings.append("confidence converted from percent notation")
    else:
        warnings.append("confidence not recognized; leaving raw")
        return None, warnings

    if number > 1:
        warnings.append("confidence scaled from 0-100 range")
        number /= 100.0
    number = max(0.0, min(1.0, number))
    return number, warnings


def normalize_boolean(value: Any) -> Tuple[Optional[bool], List[str]]:
    warnings: List[str] = []
    if isinstance(value, bool):
        return value, warnings
    if isinstance(value, (int, float)) and value in {0, 1}:
        warnings.append("boolean coerced from numeric")
        return bool(int(value)), warnings
    if isinstance(value, str):
        result = _BOOLEAN_STRINGS.get(value.strip().lower())
        if result is not None:
            warnings.append("boolean coerced from string")
            return result, warnings
    warnings.append("boolean not recognized; leaving raw")
    return None, warnings


def clamp_numeric(value: Any, minimum: float, maximum: float) -> NumberResult:
    warnings: List[str] = []
    if not isinstance(value, (int, float)):
        return None, warnings
    number = float(value)
    if number < minimum:
        warnings.append("value raised to minimum bound")
        return minimum, warnings
    if number > maximum:
        warnings.append("value lowered to maximum bound")
        return maximum, warnings
    return number, warnings


def is_close_enough(left: float, right: float, tolerance: float = 1e-6) -> bool:
    return math.isclose(left, right, abs_tol=tolerance)
