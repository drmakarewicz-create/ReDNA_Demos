# ReDNACoreDemo/core/redna_core.py
from __future__ import annotations
from typing import Any, Dict, List
from .schemas import EvidenceItem, ObservationItem, ResolveOut
from . import hierarchy
from .arbitration import choose_best

def build_observations(bundle_items: List[EvidenceItem]) -> List[ObservationItem]:
    obs: List[ObservationItem] = []
    for ev in bundle_items:
        # only accept traits the Core knows about (or umbrella placeholders)
        t = ev.get("trait")
        if not t:
            continue
        if t not in hierarchy.all_trait_keys() and not any(t.startswith(fam + ".") for fam in hierarchy.REGISTRY):
            continue
        obs.append({
            "trait": t,
            "value": ev.get("value"),
            "ucn": float(ev.get("ucn", 0.0)),
            "provenance": ev,
        })
    return obs

def resolve_traits(
    prior_resolved: Dict[str, Any],
    prior_evidence: Dict[str, Any],
    prior_obs: Dict[str, Any],
    new_obs: List[ObservationItem],
) -> ResolveOut:
    # merge new evidence/observations
    evidence_items = list(prior_evidence.get("items", [])) + [o["provenance"] for o in new_obs]
    obs_items = list(prior_obs.get("items", [])) + new_obs

    # group observations by trait
    by_trait: Dict[str, List[ObservationItem]] = {}
    for o in obs_items:
        by_trait.setdefault(o["trait"], []).append(o)

    # arbitrate each trait
    resolved: Dict[str, Any] = {}
    priorities: Dict[str, float] = {}
    for trait, group in by_trait.items():
        val, ucn, reasons = choose_best([g["provenance"] for g in group])
        if val is None:
            continue
        resolved[trait] = {
            "resolved_value": val if isinstance(val, (str, int, float, bool)) else val,
            "ucn": ucn,
            "reasons": reasons,
        }
        # curiosity/system-need heuristic: lower UCN ⇒ higher priority
        priorities[trait] = max(0.0, min(1.0, 1.0 - (ucn / 100.0)))

    # make sure every known trait appears at least with null (for “wide table”)
    for key in hierarchy.all_trait_keys():
        resolved.setdefault(key, {"resolved_value": None, "ucn": 0, "reasons": ["unknown"]})
        priorities.setdefault(key, 0.0)

    return {
        "resolved": resolved,
        "priorities": priorities,
    }, {"items": evidence_items}, {"items": obs_items}