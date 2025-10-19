"""Evidence weighting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .models import Evidence, UserAssertion


BASE_PRIORS: Dict[str, float] = {
    "behavioral": 1.00,
    "third_party": 0.85,
    "document": 0.80,
    "sensor": 0.75,
    "model_inference": 0.70,
    "user_assertion": 0.40,
}


@dataclass
class WeightBreakdown:
    base: float
    consistency: float
    cost_risk: float
    time_decay: float
    context_match: float
    anonymity: float

    @property
    def total(self) -> float:
        value = self.base
        value *= self.consistency
        value *= self.cost_risk
        value *= self.time_decay
        value *= self.context_match
        value *= self.anonymity
        return max(0.0, value)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _modifier_from_provenance(evidence: Evidence, key: str, default: float = 1.0, *, low: float = 0.1, high: float = 1.2) -> float:
    raw = evidence.provenance.get(key, default)
    if isinstance(raw, (int, float)):
        return clamp(float(raw), low, high)
    return default


def baseline_weight(evidence: Evidence, *, user_base: Optional[float] = None) -> float:
    if isinstance(evidence, UserAssertion) or evidence.source_type == "user_assertion":
        base = user_base if user_base is not None else BASE_PRIORS["user_assertion"]
        return clamp(base, 0.2, 0.7)
    return BASE_PRIORS.get(evidence.source_type, 0.6)


def compute_effective_weight(evidence: Evidence, *, user_base: Optional[float] = None) -> WeightBreakdown:
    base = baseline_weight(evidence, user_base=user_base)
    breakdown = WeightBreakdown(
        base=base,
        consistency=_modifier_from_provenance(evidence, "consistency", default=1.0, low=0.5, high=1.2),
        cost_risk=_modifier_from_provenance(evidence, "cost_risk", default=1.0, low=0.7, high=1.3),
        time_decay=_time_decay(evidence),
        context_match=_modifier_from_provenance(evidence, "context_match", default=1.0, low=0.6, high=1.2),
        anonymity=_anonymity_factor(evidence),
    )
    return breakdown


def _time_decay(evidence: Evidence) -> float:
    decay = evidence.provenance.get("time_decay")
    if isinstance(decay, (int, float)):
        return clamp(float(decay), 0.4, 1.0)
    # Heuristic: older than 90 days halves the weight
    timestamp = evidence.timestamp
    if timestamp is None:
        return 1.0
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    delta = now - timestamp.replace(tzinfo=timezone.utc)
    days = delta.days + delta.seconds / 86400
    if days <= 7:
        return 1.0
    if days >= 90:
        return 0.5
    # interpolate between 1 and 0.5
    ratio = (days - 7) / (90 - 7)
    return clamp(1.0 - 0.5 * ratio, 0.5, 1.0)


def _anonymity_factor(evidence: Evidence) -> float:
    attr_flag = getattr(evidence, "anonymity", False)
    prov_flag = evidence.provenance.get("anonymity") if isinstance(evidence.provenance, dict) else None
    if isinstance(prov_flag, bool):
        return 0.7 if prov_flag else 1.0
    return 0.7 if bool(attr_flag) else 1.0
