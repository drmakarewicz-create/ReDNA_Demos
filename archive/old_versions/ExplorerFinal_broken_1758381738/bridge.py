# ExplorerFinal/bridge.py
"""
Thin bridge for ExplorerFinal → UCN/RR + Core AI helpers.
- Respects REDNA_AI_ENABLED; if off, returns safe baselines.
- Imports root helpers: ucn_rr_ai.py and core_ai_propagation.py (in project root).
"""

from __future__ import annotations
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent  # project root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AI_ENABLED = os.getenv("REDNA_AI_ENABLED", "false").lower() == "true"

# Lazy import root helpers so this file works even if AI files are absent temporarily.
try:
    from ucn_rr_ai import score_confidence as _ai_score
except Exception:
    _ai_score = None

try:
    from core_ai_propagation import propose_propagation as _ai_propose
except Exception:
    _ai_propose = None


@dataclass
class NodeSpec:
    path: str
    prior_ucn: float = 400.0
    prior_rr: float = 0.5
    last_update_ts: Any = None
    preset: str = "Normal"


@dataclass
class EvidenceSpec:
    confirmations: int = 0
    neutrals: int = 0
    contradictions: int = 0
    half_life_days: int = 90


def ai_score_node(node: NodeSpec, evidence: EvidenceSpec) -> Dict[str, Any]:
    """Return {ucn, rr, curiosity, why} with safe fallbacks."""
    base = {
        "ucn": float(node.prior_ucn),
        "rr": float(node.prior_rr),
        "curiosity": 1000.0 - float(node.prior_ucn),
        "why": "baseline",
    }
    if not (AI_ENABLED and _ai_score):
        return base
    try:
        return _ai_score(asdict(node), asdict(evidence))
    except Exception:
        return base


def ai_core_propagation(change_event: Dict[str, Any], neighborhood: Dict[str, Any]) -> Dict[str, Any]:
    """Return Core propagation plan with safe fallback."""
    fallback = {
        "propagation_plan": [{
            "path": str(change_event.get("path", "")).split(".")[0] if change_event else "PaDNA",
            "action": "recompute_rollup",
            "reason": "direct change"
        }],
        "contradictions": [],
        "checks": [{"prompt": f"Confirm {change_event.get('path','<path>')} change is persistent and not a typo."}],
    }
    if not (AI_ENABLED and _ai_propose):
        return fallback
    try:
        return _ai_propose(change_event, neighborhood)
    except Exception:
        return fallback