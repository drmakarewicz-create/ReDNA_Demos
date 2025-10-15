# ReDNACoreDemo/core/arbitration.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple
from .schemas import EvidenceItem

def _ucn(v: EvidenceItem) -> float:
    try:
        return float(v.get("ucn", 0.0))
    except Exception:
        return 0.0

def _normalize_value(val: Any) -> Any:
    # You can make this stricter per-trait; keeping permissive for now.
    return val

def choose_best(values: List[EvidenceItem]) -> Tuple[Any, float, List[str]]:
    """
    Very simple arbitration:
      • pick the highest-UCN value
      • if tie on value but conflict on literal values, mark conflict
    """
    if not values:
        return None, 0.0, []

    # group by value literal
    buckets: Dict[str, List[EvidenceItem]] = {}
    for ev in values:
        val = str(_normalize_value(ev.get("value")))
        buckets.setdefault(val, []).append(ev)

    # pick the bucket whose best UCN is max; prefer larger bucket if tie
    best_val, best_ucn, reasons = None, -1.0, []
    for val, group in buckets.items():
        top = max(group, key=_ucn)
        top_ucn = _ucn(top)
        if top_ucn > best_ucn or (top_ucn == best_ucn and len(group) > len(buckets.get(str(best_val), []))):
            best_val, best_ucn = val, top_ucn
            reasons = [f"{g.get('source','?')}@{_ucn(g):.0f}" for g in sorted(group, key=_ucn, reverse=True)[:3]]

    # conflict flag if more than one bucket exists and the winner is not unanimous
    if len(buckets) > 1:
        reasons.insert(0, "conflict_detected")

    return best_val, best_ucn, reasons