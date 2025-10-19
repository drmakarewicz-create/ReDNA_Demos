"""RR/curiosity computations used by holistic review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

MIN_PRESENT_RR = 5.0
MIN_PRESENT_UCN = 50.0


@dataclass
class BaselineSpec:
    mean: float = 700.0
    std: float = 150.0


def _baseline_for(path: str, baselines: Optional[Dict[str, Any]]) -> BaselineSpec:
    traits = {}
    defaults = {}
    if isinstance(baselines, dict):
        traits = baselines.get("traits") if isinstance(baselines.get("traits"), dict) else {}
        defaults = baselines.get("defaults") if isinstance(baselines.get("defaults"), dict) else {}
    trait_conf = traits.get(path, {}) if isinstance(traits, dict) else {}
    mean = float(trait_conf.get("mean", defaults.get("mean", 700.0)))
    std = float(trait_conf.get("std", defaults.get("std", 150.0)))
    if std < 1.0:
        std = 150.0
    return BaselineSpec(mean=mean, std=std)


def compute_rr(
    path: str,
    value: Any,
    ucn: float,
    baselines: Optional[Dict[str, Any]] = None,
    previous_rr: Optional[float] = None,
) -> float:
    """Estimate RR (0-100) using UCN and trait baselines."""

    spec = _baseline_for(path, baselines)
    # Normalise UCN into [0, 100]
    ucn_score = max(0.0, min(100.0, (ucn / 1000.0) * 100.0))

    # Compare against baseline expectation (mean assumed in 0-1000 scale)
    z = (ucn - spec.mean) / spec.std
    baseline_rr = max(0.0, min(100.0, 50.0 + z * 10.0))

    estimate = (ucn_score + baseline_rr) / 2.0

    if previous_rr is not None:
        estimate = 0.7 * float(previous_rr) + 0.3 * estimate

    estimate = max(MIN_PRESENT_RR, min(100.0, estimate))
    return float(estimate)


def apply_floors(entry: Dict[str, Any]) -> None:
    """Ensure minimum floors for UCN/RR when a value is present."""

    value = entry.get("value")
    if value is None:
        value = entry.get("resolved_value")
    if value in (None, "", "unknown", "Unknown"):
        return

    if not isinstance(entry.get("ucn"), (int, float)) or entry.get("ucn", 0.0) < MIN_PRESENT_UCN:
        entry["ucn"] = float(MIN_PRESENT_UCN)

    if not isinstance(entry.get("rr"), (int, float)) or entry.get("rr", 0.0) < MIN_PRESENT_RR:
        entry["rr"] = float(MIN_PRESENT_RR)

    curiosity = 100.0 - float(entry.get("rr", MIN_PRESENT_RR))
    entry["curiosity"] = max(0.0, min(100.0, curiosity))


__all__ = ["compute_rr", "apply_floors", "MIN_PRESENT_RR", "MIN_PRESENT_UCN"]
