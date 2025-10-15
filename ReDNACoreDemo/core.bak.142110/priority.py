from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

try:  # PyYAML is optional; fall back to JSON-only if unavailable
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None

_DEFAULT_IMPORTANCE = 1.0
_PRIORITY_BOOST = 0.1


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def priority_score(rr: float, trait_importance: float, contradiction: bool) -> float:
    """Compute a bounded priority score for coach consumption.

    Args:
        rr: Reliability Rating scaled to [0, 1].
        trait_importance: Trait importance weight in [0, 1].
        contradiction: Whether the signal conflicts with existing evidence.
    """

    rr_clamped = _clamp(rr)
    importance = _clamp(trait_importance)
    base_need = 1.0 - rr_clamped
    weighted = base_need * (0.5 + 0.5 * importance)
    boost = _PRIORITY_BOOST if contradiction else 0.0
    return _clamp(weighted + boost)


def trait_importance_for(trait: str) -> float:
    """Return the configured importance (0..1) for a trait or family."""

    if not trait:
        return _DEFAULT_IMPORTANCE
    trimmed = trait.strip()
    mapping = _trait_importance_map()
    if trimmed in mapping:
        return mapping[trimmed]
    family = trimmed.split(".", 1)[0]
    return mapping.get(family, _DEFAULT_IMPORTANCE)


@lru_cache(maxsize=1)
def _trait_importance_map() -> Dict[str, float]:
    config_dir = Path(__file__).resolve().parents[1] / "data" / "config"
    for filename, loader in (
        ("trait_importance.json", _load_json_map),
        ("trait_importance.yaml", _load_yaml_map),
        ("trait_importance.yml", _load_yaml_map),
    ):
        if loader is None:
            continue
        path = config_dir / filename
        if not path.exists():
            continue
        try:
            data = loader(path)
        except Exception:
            continue
        if data:
            return data
    return {}


def _load_json_map(path: Path) -> Dict[str, float]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return _normalize_map(payload)


def _load_yaml_map(path: Path) -> Dict[str, float]:  # pragma: no cover - optional dependency
    if yaml is None:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return _normalize_map(payload)


def _normalize_map(raw: Any) -> Dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    normalized: Dict[str, float] = {}
    for key, value in raw.items():
        try:
            normalized[str(key).strip()] = _clamp(float(value))
        except (TypeError, ValueError):
            continue
    return normalized
