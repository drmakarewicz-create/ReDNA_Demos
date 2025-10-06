# ReDNACoreDemo/ai/arbitrator_adapter.py
# Lightweight arbitrator:
# - Translates legacy keys -> canonical trait IDs
# - Merges direct evidence with linked-trait priors
# - Produces resolved_value, UCN, flags, reasons per trait

from __future__ import annotations
from typing import Dict, Any, List, Tuple, DefaultDict
from collections import defaultdict

# ---------------- Canonical trait IDs ----------------
IRIS = "PaDNA.LooksDNA.EyeDNA.IrisColor"
HAIR = "PaDNA.LooksDNA.HairDNA.NaturalColor"
FRECKLES = "PaDNA.SkinDNA.Freckles"

# ---------------- Legacy -> Canonical translations ----------------
LEGACY_MAP = {
    "Eye Color": IRIS,
    "EyeColour": IRIS,
    "Iris": IRIS,

    "Hair Color": HAIR,
    "HairColour": HAIR,
    "Natural Hair Color": HAIR,
    "Natural Hair Colour": HAIR,

    "Freckles": FRECKLES,
}

# For enum sanity checks (optional – used for filtering weird values)
ENUMS = {
    IRIS:      ["Blue","Green","Hazel","Brown","Gray","Amber","Heterochromia"],
    HAIR:      ["Black","Brown","Blonde","Red","Gray","White","Mixed"],
    FRECKLES:  ["None","Light","Moderate","Heavy"],
}

# ---------------- Linked-trait priors (illustrative; low weights) ----------------
# These are *priors*, not facts. They nudge the arbitrator but won’t overwhelm direct evidence.
PRIORS_FROM_IRIS = {
    # IrisColor -> list of (target_trait, candidate_value, weight, reason_tag)
    "Blue": [
        (HAIR, "Blonde",   0.08, "prior_from_iris"),
        (HAIR, "Red",      0.04, "prior_from_iris"),
        (FRECKLES, "Light", 0.05, "prior_from_iris"),
    ],
    "Green": [
        (HAIR, "Brown",    0.05, "prior_from_iris"),
        (FRECKLES, "Light", 0.03, "prior_from_iris"),
    ],
    "Hazel": [
        (HAIR, "Brown",    0.05, "prior_from_iris"),
    ],
    "Brown": [
        (HAIR, "Brown",    0.08, "prior_from_iris"),
    ],
    "Gray": [
        (HAIR, "Blonde",   0.05, "prior_from_iris"),
        (FRECKLES, "Light", 0.03, "prior_from_iris"),
    ],
    "Amber": [
        (HAIR, "Brown",    0.05, "prior_from_iris"),
    ],
}

# Cap for UCN scaling (just to keep numbers in a nice range like your screenshots)
UCN_SCALE = 200.0

def _is_enum_ok(trait_id: str, val: Any) -> bool:
    if trait_id not in ENUMS:
        return True
    return str(val) in ENUMS[trait_id]

def _add_evidence(beliefs: Dict[str, Dict[str, float]],
                  reasons: Dict[str, List[str]],
                  flags: Dict[str, List[str]],
                  trait_id: str, value: str, weight: float, tag: str):
    if not value:
        return
    if not _is_enum_ok(trait_id, value):
        reasons.setdefault(trait_id, []).append(f"drop:{value}@{weight:.2f} (enum_mismatch)")
        return
    beliefs.setdefault(trait_id, {})
    beliefs[trait_id][value] = beliefs[trait_id].get(value, 0.0) + float(weight)
    reasons.setdefault(trait_id, []).append(f"{tag}:{value}@{weight:.2f}")

def _translate_observation(obs: Dict[str, Any]) -> Tuple[str, str, float, str]:
    """Return (canonical_trait_id, value, weight, tag)."""
    tid = str(obs.get("trait_id","")).strip()
    val = obs.get("value")
    if tid in LEGACY_MAP:
        canonical = LEGACY_MAP[tid]
        tag = "translated"
    else:
        canonical = tid
        tag = "direct"

    # numeric/confidence weighting → scale into ~[0.05, 1.0] (bounded)
    cw = float(obs.get("confidence_weight", 0.6))
    cw = max(0.05, min(cw, 1.0))

    # minor recency bump (optional)
    if obs.get("schema_version", 4) >= 4:
        cw *= 1.0
    else:
        cw *= 0.75  # slightly discount old schemas

    return canonical, str(val), cw, tag

def _apply_linked_priors(beliefs: Dict[str, Dict[str, float]],
                         reasons: Dict[str, List[str]],
                         flags: Dict[str, List[str]]):
    """Inject low-weight priors based on already-accumulated strong beliefs (e.g., from IrisColor)."""
    # If IrisColor already has a clear leader, add priors to linked traits
    iris_scores = beliefs.get(IRIS, {})
    if not iris_scores:
        return
    leader_val, leader_w = max(iris_scores.items(), key=lambda kv: kv[1])
    # Only apply priors when there is *some* evidence for iris
    if leader_w <= 0:
        return
    for (target_trait, candidate_value, w, tag) in PRIORS_FROM_IRIS.get(leader_val, []):
        # weight scaled softly by iris weight but capped low (so it never dominates direct evidence)
        scaled = min(0.12, 0.5 * w)  # soft coupling to iris evidence
        _add_evidence(beliefs, reasons, flags, target_trait, candidate_value, scaled, tag)
        flags.setdefault(target_trait, []).append("inferred_low_conf")

def translate_and_resolve(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    observations: list of { trait_id, value, confidence_weight, schema_version, provenance, ... }
    returns: { trait_id: { resolved_value, ucn, flags:[], reasons:[] } }
    """
    beliefs: Dict[str, Dict[str, float]] = {}
    reasons: Dict[str, List[str]] = {}
    flags: Dict[str, List[str]] = {}

    # 1) Translate & add direct evidence
    for obs in observations:
        t, v, w, tag = _translate_observation(obs)
        if not t: 
            continue
        # keep a small floor so things register
        w = max(w, 0.05)
        _add_evidence(beliefs, reasons, flags, t, v, w, tag)
        if tag == "translated":
            flags.setdefault(t, []).append("translated")

    # 2) Linked-trait priors (e.g., from IrisColor -> Hair/Freckles)
    _apply_linked_priors(beliefs, reasons, flags)

    # 3) Decide winners & form response
    out: Dict[str, Any] = {}
    for trait_id, score_map in beliefs.items():
        if not score_map:
            continue
        # Argmax
        winner_val, winner_w = max(score_map.items(), key=lambda kv: kv[1])
        total_w = sum(score_map.values())
        # crude UCN scaling just to match the “feel” of your previous numbers
        ucn = min(UCN_SCALE, max(1.0, total_w * 150.0))
        out[trait_id] = {
            "resolved_value": winner_val,
            "ucn": float(round(ucn, 6)),
            "flags": sorted(list(set(flags.get(trait_id, [])))),
            "reasons": reasons.get(trait_id, []),
        }

    return out