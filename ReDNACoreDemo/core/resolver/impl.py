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
import os

from .contracts import Evidence, Resolved, ResolvedTrait
from .debug import log_step
from .resolved_io import read_resolved, write_resolved
from ReDNACoreDemo.core.traits.ontology import get_trait_spec
from ReDNACoreDemo.core.rr.client import score_ucn
from ReDNACoreDemo.core.ingest.policy import apply_supersession
from ReDNACoreDemo.core.logutil import stack_log, supersession_log
from ReDNACoreDemo.core.metrics import METRICS, MetricNames


class UCNRRRequiredError(Exception):
    """
    Exception raised when UCNRR is required but unavailable.

    This signals that the system should return 503 to the client
    rather than silently falling back to prior UCN values.
    """
    def __init__(self, message: str, rr_error: Optional[Exception] = None):
        self.message = message
        self.rr_error = rr_error
        super().__init__(message)


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
    ucnrr_required = os.getenv("UCNRR_REQUIRED", "false").lower() in ("1", "true", "yes")

    try:
        rr_scores = score_ucn(user_id, rr_input)
        rr_ok = True
        trace and log_step(trace, "rr_success", rr_scores)
    except Exception as e:
        trace and log_step(trace, "rr_error", repr(e))

        # In UCNRR_REQUIRED mode, raise error instead of falling back
        if ucnrr_required:
            raise UCNRRRequiredError(
                message="UCNRR service required but unavailable. Resolution blocked in strict mode.",
                rr_error=e
            )

        # Fallback: use priors (permissive mode)
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
    previous_snapshot: Dict[str, Dict[str, Any]] = {}
    if isinstance(resolved, dict):
        for tid, payload in resolved.items():
            if isinstance(payload, dict):
                previous_snapshot[tid] = dict(payload)
    else:
        resolved = {}

    for tid, ev in chosen.items():
        prev = previous_snapshot.get(tid) or {}
        ucn = by_tid_ucn.get(tid, float(ev.get("ucn_prior", 0.2)))
        val = ev.get("value", {})
        ev_source = ev.get("source", source)

        decision = apply_supersession(
            tid,
            prev if prev else None,
            {
                "value": val,
                "source": ev_source,
                "ts": ev.get("ts", _now()),
                "ucn": ucn,
                "policy": ev.get("policy", {}),
                "_reliability": ev.get("_reliability"),
            },
        )

        ucn = max(0.0, min(1.0, ucn * max(decision.ucn_multiplier, 0.0)))
        last_confirmed_at = decision.last_confirmed_at
        if last_confirmed_at is None:
            last_confirmed_at = prev.get("last_confirmed_at")
            if last_confirmed_at is None and decision.new_status == "stable":
                last_confirmed_at = _now()

        history: List[Dict[str, Any]] = []
        prev_history = prev.get("history") if isinstance(prev, dict) else None
        if isinstance(prev_history, list):
            history = [dict(entry) for entry in prev_history]
        if decision.history_entry:
            history.append(decision.history_entry)

        if isinstance(prev, dict):
            existing_sources = prev.get("sources", [])
        else:
            existing_sources = []

        # Determine status
        status = decision.new_status or "stable"
        provenance = ev.get("provenance", "")
        if provenance.startswith("inference:") and not prev.get("value") and status == "stable":
            status = "warming"

        # Merge sources
        if isinstance(existing_sources, list):
            sources = list(set(existing_sources + [ev_source]))
        else:
            sources = [ev_source]

        entry = {
            "value": val,
            "ucn": ucn,
            "sources": sources,
            "status": status,
            "last_updated": _now(),
            "last_confirmed_at": last_confirmed_at,
            "history": history,
            "policy": ev.get("policy", {}),
        }

        resolved[tid] = entry

        if decision.action in {"superseded", "contradiction", "reinforced"}:
            log_payload = {
                "ts": entry["last_updated"],
                "user_id": user_id,
                "trait_id": tid,
                "action": decision.action,
                "new_status": decision.new_status,
                "old_status": decision.old_status,
                "ucn_multiplier": decision.ucn_multiplier,
                "old_value": prev.get("value") if isinstance(prev, dict) else None,
                "new_value": val,
                "context": decision.context,
            }
            supersession_log(log_payload)
            level = "WARN" if decision.action == "contradiction" else "INFO"
            stack_log("core", level, "supersession_event", f"{tid} {decision.action}", log_payload)
            if decision.action == "superseded":
                METRICS.increment(MetricNames.POLICY_SUPERSESSIONS)
            elif decision.action == "contradiction":
                METRICS.increment(MetricNames.POLICY_CONTRADICTIONS)

    # Persist
    write_resolved(user_id, resolved)
    trace and log_step(trace, "resolved_out", {
        "trait_count": len(resolved),
        "rr_ok": rr_ok
    })

    # Phase 8 Stage 3: Update belief graph for each promoted trait
    try:
        from ..graph.belief import on_trait_promotion

        for tid, ev in chosen.items():
            # Get the resolved entry (with UCN scores)
            resolved_entry = resolved.get(tid, {})
            ucn_score = resolved_entry.get("ucn", 0.5)

            # Convert UCN float to dict format (u=ucn, c and n estimated)
            ucn_dict = {
                "u": ucn_score,
                "c": ucn_score * 0.8,  # Estimate curiosity from uncertainty
                "n": 0.5  # Default necessity
            }

            # Calculate rr_score (0-1000 legacy scale) from UCN
            # Phase 9: This is stored as rr_score and normalized at egress to rr (0-100)
            rr_score = (1.0 - ucn_score) * 1000.0

            # Get observation text from evidence
            observation_text = ev.get("text", "") or str(ev.get("value", ""))
            observation_source = ev.get("source", source)

            # Call graph update hook
            on_trait_promotion(
                user_id=user_id,
                trait_id=tid,
                value=ev.get("value"),
                rr_score=rr_score,
                ucn=ucn_dict,
                observation_text=observation_text,
                observation_source=observation_source,
                observation_ts=None,  # Will default to now
                why_card_text=None,  # Stage 4: generate Why-Cards
                metadata={"resolution_source": source}
            )
    except ImportError as e:
        logger.warning(f"Graph module not available, skipping belief graph update: {e}")
    except Exception as e:
        logger.error(f"Failed to update belief graph for {user_id}: {e}", exc_info=True)
        # Re-raise in development to catch issues early
        if os.getenv("GRAPH_DEBUG", "").lower() in ("1", "true", "yes"):
            raise

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
