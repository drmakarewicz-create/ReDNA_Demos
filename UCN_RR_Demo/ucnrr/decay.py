# ucnrr/decay.py
from __future__ import annotations
from datetime import datetime

DEFAULT_HALF_LIFE_DAYS = 365.0

def _days_between(a: datetime, b: datetime) -> float:
    try:
        delta = (b - a)
        return abs(delta.days + delta.seconds / 86400.0)
    except Exception:
        return 0.0

def decay_weight(observed_at_iso: str | None, now: datetime, half_life_days: float = DEFAULT_HALF_LIFE_DAYS) -> float:
    """
    Standard exponential decay: weight *= 0.5 ** (days / half_life).
    If observed_at_iso is missing/invalid, returns 1.0 (no decay).
    """
    if not observed_at_iso:
        return 1.0
    try:
        t = datetime.fromisoformat(observed_at_iso)
    except Exception:
        return 1.0
    days = _days_between(t, now)
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (days / float(half_life_days))

def get_half_life_for_path(decay_map: dict[str, float], path: str, default_hl: float) -> float:
    """
    Select most-specific half-life for a dna path string like "IntDNA.RoDNA.AttachmentDNA".
    decay_map keys may be:
      - "IntDNA"
      - "IntDNA.RoDNA"
      - "IntDNA.RoDNA.AttachmentDNA"
    Most specific match wins; fallback to default_hl.
    """
    parts = path.split(".")
    best = None
    for i in range(1, len(parts) + 1):
        key = ".".join(parts[:i])
        if key in decay_map:
            best = decay_map[key]
    return float(best) if best is not None else float(default_hl)