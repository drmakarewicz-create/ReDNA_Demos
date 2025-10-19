from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _REPO_ROOT / "data" / "config"
_OVERRIDE_DIR = _REPO_ROOT / "data" / "_config"
_DEFAULT_REGISTRY_FILENAME = "decay_registry.json"
_OVERRIDE_ENV = "CORE_DECAY_OVERRIDES"

_FULL_SCALE_THRESHOLD = 1.0  # values above this are treated as 0-100 scale


def _parse_iso(timestamp: Optional[str]) -> Optional[datetime]:
    if not timestamp:
        return None
    token = timestamp.strip()
    if not token:
        return None
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(token)
    except ValueError:
        return None


def _normalize_ucn(ucn: float) -> float:
    if ucn > _FULL_SCALE_THRESHOLD:
        return max(0.0, min(ucn / 100.0, 1.0))
    return max(0.0, min(ucn, 1.0))


def _denormalize_ucn(norm: float, reference: float) -> float:
    if reference > _FULL_SCALE_THRESHOLD:
        return max(0.0, min(norm * 100.0, 100.0))
    return max(0.0, min(norm, 1.0))


def _registry_override_path() -> Optional[Path]:
    env_path = os.getenv(_OVERRIDE_ENV)  # type: ignore[name-defined]
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate
    candidate = _OVERRIDE_DIR / _DEFAULT_REGISTRY_FILENAME
    if candidate.exists():
        return candidate
    return None


@lru_cache(maxsize=1)
def _load_registry() -> Dict[str, float]:
    base = _load_file(_CONFIG_DIR / _DEFAULT_REGISTRY_FILENAME)
    override_path = _registry_override_path()
    if override_path:
        override = _load_file(override_path)
        if override:
            base.update(override)
    return base


def _load_file(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}
    try:
        if path.suffix.lower() in {".yaml", ".yml"} and yaml is not None:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    registry: Dict[str, float] = {}
    for key, value in payload.items():
        try:
            half_life = float(value.get("half_life_days")) if isinstance(value, dict) else float(value)
        except (TypeError, ValueError):
            continue
        if half_life <= 0 or not half_life or half_life != half_life:
            continue
        registry[str(key).strip()] = half_life
    return registry


def half_life_for(trait: str) -> Optional[float]:
    registry = _load_registry()
    if not trait:
        return None
    trait_key = trait.strip()
    if trait_key in registry:
        return registry[trait_key]
    family = trait_key.split(".", 1)[0]
    return registry.get(family)


def apply_decay(resolved: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Dict[str, float]]:
    """Apply exponential decay to UCN values in-place based on half-life settings.

    Returns a mapping of trait -> decay metadata for logging (before/after values).
    """

    if not isinstance(resolved, dict):
        return {}

    now_dt = now or datetime.now(timezone.utc)
    changes: Dict[str, Dict[str, float]] = {}

    for trait, entry in resolved.items():
        if not isinstance(entry, dict):
            continue

        half_life = half_life_for(trait)
        if not half_life:
            continue

        last_updated = _parse_iso(entry.get("last_updated"))
        if last_updated is None:
            continue

        elapsed_days = (now_dt - last_updated).total_seconds() / 86400.0
        if elapsed_days <= 0:
            continue

        before_ucn = float(entry.get("ucn", 0.0))
        before_norm = _normalize_ucn(before_ucn)
        if before_norm <= 0.0:
            continue

        decay_factor = 0.5 ** (elapsed_days / half_life)
        after_norm = max(0.0, min(before_norm * decay_factor, 1.0))
        if after_norm >= before_norm:
            continue

        after_ucn = _denormalize_ucn(after_norm, before_ucn)
        entry["ucn"] = after_ucn
        entry.setdefault("decay", {})
        if isinstance(entry["decay"], dict):
            entry["decay"].update(
                {
                    "last_applied": now_dt.isoformat(),
                    "half_life_days": half_life,
                    "elapsed_days": round(elapsed_days, 3),
                }
            )
        entry["decay_applied"] = True

        changes[trait] = {
            "before_ucn": before_ucn,
            "after_ucn": after_ucn,
            "half_life_days": half_life,
            "elapsed_days": round(elapsed_days, 3),
        }

    return changes


__all__ = ["apply_decay", "half_life_for"]
