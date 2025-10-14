"""
Core resolver implementation.

This module implements the canonical trait resolution pipeline:
1. Group evidence by trait_id
2. Select winning value per trait (latest-strongest strategy)
3. Compute UCN via RR (with fallback to priors)
4. Merge into existing resolved snapshot and persist
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from core.resolver.contracts import Evidence, Resolved, ResolvedTrait
from core.resolver.debug import log_step
from core.resolver.resolved_io import read_resolved, write_resolved
from core.traits.ontology import get_trait_spec
from core.rr.client import score_ucn


def _now() -> str:
    """Get current ISO8601 timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_roundtrip(
    user_id: str,
    evidence: List[Evidence],
    source: str,
    trace: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Resolve traits from evidence and persist to user snapshot.

    This is the canonical resolution path. All pipelines (chat, onboarding,
    goals, etc.) should flow through this function.

    Args:
        user_id: User identifier
        evidence: List of Evidence dicts (canonical schema)
        source: Source tag for this resolution pass (e.g., "chat", "onboarding")
        trace: Optional trace dict for debugging

    Returns:
        Dict with:
            - resolved: The complete resolved snapshot
            - rr_ok: True if RR scored successfully, False if fallback used
    """
    trace and log_step(trace, "evidence_in", evidence)

    # 1) Group by trait_id
    by_trait: Dict[str, List[Evidence]] = {}
    for ev in evidence:
        tid = ev.get("trait_id")
        if not tid:
            continue
        by_trait.setdefault(tid, []).append(ev)

    trace and log_step(trace, "grouped", {k: len(v) for k, v in by_trait.items()})

    # 2) Select value per trait
    # Strategy: Latest wins (last in list). Could extend with:
    # - Source priority (direct > inferred)
    # - UCN-weighted selection
    # - Conflict detection
    chosen: Dict[str, Evidence] = {}
    for tid, evs in by_trait.items():
        # Sort by timestamp if available, then take last
        sorted_evs = sorted(
            evs,
            key=lambda e: e.get("ts", "1970-01-01T00:00:00Z")
        )
        chosen[tid] = sorted_evs[-1]

    trace and log_step(trace, "chosen", chosen)

    # 3) Score UCN via RR (batched), with fallback
    rr_input = []
    for tid, ev in chosen.items():
        spec = get_trait_spec(tid)
        rr_input.append({
            "trait_id": tid,
            "value": ev.get("value", {}),
            "ucn_prior": float(ev.get("ucn_prior") or spec.get("ucn_prior", 0.2)),
            "source": ev.get("source", source)
        })

    trace and log_step(trace, "rr_input", rr_input)

    # Try RR scoring
    rr_ok = False
    try:
        rr_scores = score_ucn(user_id, rr_input)
        rr_ok = True
        trace and log_step(trace, "rr_success", rr_scores)
    except Exception as e:
        trace and log_step(trace, "rr_error", repr(e))
        # Fallback: use priors
        rr_scores = [
            {
                "trait_id": x["trait_id"],
                "ucn": x.get("ucn_prior", 0.2)
            }
            for x in rr_input
        ]

    by_tid_ucn = {x["trait_id"]: float(x["ucn"]) for x in rr_scores}
    trace and log_step(trace, "ucn_scores", by_tid_ucn)

    # 4) Merge into resolved snapshot
    resolved: Resolved = read_resolved(user_id) or {}

    for tid, ev in chosen.items():
        prev = resolved.get(tid, {})
        ucn = by_tid_ucn.get(tid, float(ev.get("ucn_prior", 0.2)))
        val = ev.get("value", {})
        ev_source = ev.get("source", source)

        # Determine status
        status = "resolved"
        provenance = ev.get("provenance", "")
        if provenance.startswith("inference:") and not prev.get("value"):
            status = "inferred"

        # Merge sources
        existing_sources = prev.get("sources", [])
        if isinstance(existing_sources, list):
            sources = list(set(existing_sources + [ev_source]))
        else:
            sources = [ev_source]

        resolved[tid] = {
            "value": val,
            "ucn": ucn,
            "sources": sources,
            "status": status,
            "last_updated": _now()
        }

    # Persist
    write_resolved(user_id, resolved)
    trace and log_step(trace, "resolved_out", {
        "trait_count": len(resolved),
        "rr_ok": rr_ok
    })

    return {
        "resolved": resolved,
        "rr_ok": rr_ok
    }


def resolve_traits(
    user_id: str,
    evidence: List[Evidence],
    source: str = "ingestion",
    trace: Optional[dict] = None
) -> Resolved:
    """
    Legacy-compatible wrapper around resolve_roundtrip.

    Args:
        user_id: User identifier
        evidence: List of Evidence dicts
        source: Source tag
        trace: Optional trace dict

    Returns:
        Resolved trait dict
    """
    result = resolve_roundtrip(user_id, evidence, source, trace)
    return result["resolved"]
