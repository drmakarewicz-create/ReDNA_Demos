from __future__ import annotations

RECENCY_WEIGHTS = {
    "RECENT": 1.00,
    "OLD": 0.60,
    "RETRO": 0.35
}

def confidence_to_ucn(conf: float, support_n: int, recency_weight_sum: float) -> float:
    """
    Map model confidence + evidence support to UCN (0..1000).
    Base from confidence, diminishing returns with #photos, and a recency boost.
    """
    import math
    conf = max(0.0, min(1.0, conf))
    base = conf * 900.0 + 50.0                           # 50..950
    mult = 1.0 - 0.6 * math.exp(-float(support_n) / 3.0) # more photos → higher
    recent_ratio = max(0.0, min(1.0, (recency_weight_sum / max(1, support_n))))
    recency_mult = 0.8 + 0.2 * recent_ratio              # RECENT pushes UCN up
    return max(0.0, min(1000.0, base * mult * recency_mult))