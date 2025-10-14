from __future__ import annotations
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Import canonical trait ID mapper and inference engine
from ..traits.trait_id_mapper import normalize_evidence as id_normalize
from ..traits.inference_engine import run_inference
from .evidence_schema import validate_batch


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ingest_evidence_roundtrip(
    user_id: str,
    source: str,
    evidence: List[Dict[str, Any]],
    req_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified evidence ingestion pipeline used by all entry points.

    This is the SINGLE SOURCE OF TRUTH for evidence processing.
    Both /core/api/ingest_text and /ui/chat/send call this function.

    Pipeline steps:
    1. Canonicalize trait IDs (attributes.* → PaDNA.*, BasicDNA.*)
    2. Validate and normalize evidence schema
    3. Stamp source/timestamp
    4. Store evidence (persisted for provenance)
    5. First resolve pass (direct evidence → traits)
    6. Inference pass (declarative rules)
    7. Merge inferred traits (only if existing UCN < 0.3)
    8. Second resolve pass (incorporate inferences)
    9. Build snapshot for UI

    Args:
        user_id: User identifier
        source: Evidence source ("chat", "onboarding", "goal", etc.)
        evidence: List of evidence records
        req_id: Optional request ID for tracing (generated if not provided)

    Returns:
        Result dict with ok, req_id, snapshot, ingested count, inferred count
    """
    rid = req_id or str(uuid4())[:8]  # Short ID for logs

    logger.info(f"ingest_start{{req_id={rid}, user={user_id}, source={source}, items_in={len(evidence)}}}")

    try:
        # STEP 1: Canonicalize trait IDs
        # Maps attributes.physical.eye_color → PaDNA.EyeDNA.IrisColor
        ev1 = id_normalize(evidence)
        logger.info(f"  → Canonicalized {len(ev1)} trait IDs")

        # STEP 2: Enforce evidence schema
        # Converts fact_value → value, normalizes value shape
        ev2 = validate_batch(ev1)
        logger.info(f"  → Validated schema for {len(ev2)} evidence records")

        # STEP 3: Stamp source/timestamp if missing
        ts = now_iso()
        for e in ev2:
            e.setdefault("source", source)
            e.setdefault("ts", ts)

        # STEP 4: Store evidence (for provenance)
        # This writes to evidence.json
        _store_evidence(user_id, ev2, req_id=rid)
        logger.info(f"  → Stored {len(ev2)} evidence records")

        # STEP 5: First resolve pass (direct evidence → traits with RR/UCN)
        direct_resolved = _resolve_direct(user_id, ev2, req_id=rid)
        logger.info(f"  → Resolved {direct_resolved} direct traits")

        # STEP 6: Inference pass
        # Run declarative rules on canonical evidence
        ev_inf_raw = run_inference(ev2)

        inferred_count = 0
        if ev_inf_raw:
            logger.info(f"  → Inference generated {len(ev_inf_raw)} proposals")

            # Convert inference output to canonical evidence format
            ev_inf = []
            for inf in ev_inf_raw:
                ev_inf.append({
                    "trait_id": inf["trait_id"],
                    "fact_value": inf.get("fact_value") or inf.get("value"),
                    "ucn_prior": inf.get("ucn_prior", 0.2),
                    "provenance": inf.get("provenance", "inference:unknown"),
                    "display_hint": inf.get("display_hint", "needs_confirmation"),
                    "ui_hidden": inf.get("ui_hidden", False)
                })

            # Validate and normalize inferred evidence
            ev_inf_canonical = id_normalize(ev_inf)
            ev_inf_validated = validate_batch(ev_inf_canonical)

            # Stamp as inference source
            for e in ev_inf_validated:
                e.setdefault("source", f"{source}:inference")
                e.setdefault("ts", ts)

            # STEP 7: Merge inferred traits (only if existing UCN < 0.3)
            ev_merge = _filter_inferences_by_ucn_threshold(user_id, ev_inf_validated, threshold=0.3)

            if ev_merge:
                logger.info(f"  → Accepting {len(ev_merge)} inferred traits (UCN < 0.3)")
                _store_evidence(user_id, ev_merge, req_id=rid, tag="inference")

                # STEP 8: Second resolve pass (incorporate inferences)
                inferred_count = _resolve_inferred(user_id, ev_merge, req_id=rid)
                logger.info(f"  → Re-resolved with {inferred_count} inferred traits")
            else:
                logger.info(f"  → No inferences accepted (all traits have UCN >= 0.3)")

        # STEP 9: Build snapshot for UI
        snap = _build_snapshot(user_id)
        logger.info(f"ingest_done{{req_id={rid}, snapshot_traits={len(snap.get('traits', []))}, wrote_resolved=true}}")

        return {
            "ok": True,
            "req_id": rid,
            "snapshot": snap,
            "ingested": len(ev2),
            "inferred": inferred_count
        }

    except Exception as e:
        logger.error(f"ingest_error{{req_id={rid}, error={str(e)}}}", exc_info=True)
        raise


def _store_evidence(user_id: str, evidence: List[Dict[str, Any]], req_id: str, tag: Optional[str] = None) -> None:
    """
    Store evidence to evidence.json (for provenance).

    Args:
        user_id: User identifier
        evidence: List of canonical evidence records
        req_id: Request ID for tracing
        tag: Optional tag (e.g., "inference")
    """
    from ..storage import read_user_state, write_user_state

    # Read current state
    resolved, evidence_doc, observations = read_user_state(user_id)

    # Append new evidence items
    if not isinstance(evidence_doc, dict):
        evidence_doc = {"items": []}
    if "items" not in evidence_doc:
        evidence_doc["items"] = []

    evidence_doc["items"].extend(evidence)

    # Write back (only evidence is updated)
    write_user_state(user_id, resolved, evidence_doc, observations, enforce_governance=False)

    # Log evidence storage with file path for traceability
    logger.info(f"chat_store{{req_id={req_id}, path=\"users/{user_id}/evidence.json\", count={len(evidence)}}}")
    logger.info(f"stored_observations{{req_id={req_id}, count={len(evidence)}, tag={tag or 'direct'}}}")


def _resolve_direct(user_id: str, evidence: List[Dict[str, Any]], req_id: str) -> int:
    """
    First resolve pass: direct evidence → traits with RR/UCN scores.

    Args:
        user_id: User identifier
        evidence: List of canonical evidence records
        req_id: Request ID for tracing

    Returns:
        Number of traits resolved
    """
    from ..resolver.impl import resolve_roundtrip
    from ..resolver.debug import new_trace, write_trace
    from ..resolver.resolved_io import get_resolver_trace_dir

    try:
        # Create trace for debugging
        trace = new_trace(req_id)

        # Convert evidence to canonical Evidence schema
        # Evidence should already have: trait_id, value, source, ts
        canonical_evidence = []
        for e in evidence:
            canonical_evidence.append({
                "trait_id": e.get("trait_id"),
                "value": e.get("value", {}),
                "source": e.get("source", "ingestion"),
                "ts": e.get("ts", now_iso()),
                "ucn_prior": float(e.get("ucn_prior", 0.2)),
                "provenance": e.get("provenance", "direct")
            })

        # Run resolver
        result = resolve_roundtrip(user_id, canonical_evidence, source="ingestion", trace=trace)

        # Write trace for debugging
        trace_dir = get_resolver_trace_dir(user_id)
        write_trace(trace_dir, trace)

        resolved = result["resolved"]
        rr_ok = result["rr_ok"]

        logger.info(f"ingest_resolve{{req_id={req_id}, direct_items={len(evidence)}, resolved={len(resolved)}, rr_ok={rr_ok}}}")

        return len(resolved)

    except Exception as e:
        logger.error(f"resolve_direct_error{{req_id={req_id}, error={str(e)}}}", exc_info=True)
        return 0


def _resolve_inferred(user_id: str, evidence: List[Dict[str, Any]], req_id: str) -> int:
    """
    Second resolve pass: inferred evidence → update traits with inferred priors.

    Args:
        user_id: User identifier
        evidence: List of inferred evidence records
        req_id: Request ID for tracing

    Returns:
        Number of inferred traits resolved
    """
    from ..resolver.impl import resolve_roundtrip
    from ..resolver.debug import new_trace, write_trace
    from ..resolver.resolved_io import get_resolver_trace_dir

    try:
        # Create trace for debugging
        trace = new_trace(f"{req_id}-inferred")

        # Convert evidence to canonical Evidence schema
        canonical_evidence = []
        for e in evidence:
            canonical_evidence.append({
                "trait_id": e.get("trait_id"),
                "value": e.get("value", {}),
                "source": e.get("source", "ingestion:inference"),
                "ts": e.get("ts", now_iso()),
                "ucn_prior": float(e.get("ucn_prior", 0.15)),  # Lower prior for inferences
                "provenance": e.get("provenance", "inference:unknown")
            })

        # Run resolver
        result = resolve_roundtrip(user_id, canonical_evidence, source="inference", trace=trace)

        # Write trace for debugging
        trace_dir = get_resolver_trace_dir(user_id)
        write_trace(trace_dir, trace)

        resolved = result["resolved"]
        rr_ok = result["rr_ok"]

        logger.info(f"ingest_resolve{{req_id={req_id}, inferred_items={len(evidence)}, resolved={len(resolved)}, rr_ok={rr_ok}}}")

        return len(evidence)

    except Exception as e:
        logger.error(f"resolve_inferred_error{{req_id={req_id}, error={str(e)}}}", exc_info=True)
        return 0


def _filter_inferences_by_ucn_threshold(user_id: str, ev: List[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    """
    Filter inferred traits to only include those where existing UCN < threshold.

    Never overwrites confirmed traits with inferences.

    Args:
        user_id: User identifier
        ev: List of inferred evidence records
        threshold: UCN threshold (default 0.3)

    Returns:
        Filtered list of inferences to accept
    """
    from ..storage import read_user_state

    try:
        resolved, _, _ = read_user_state(user_id)
        allow: List[Dict[str, Any]] = []

        for e in ev:
            tid = e.get("trait_id")
            if not tid:
                continue

            existing = resolved.get(tid, {})
            ucn = float(existing.get("ucn", 0)) if isinstance(existing, dict) else 0

            if ucn < threshold:
                allow.append(e)
                logger.info(f"  → Accepting inference: {tid} (existing UCN={ucn:.2f})")
            else:
                logger.info(f"  → Skipping inference: {tid} (existing UCN={ucn:.2f} >= {threshold})")

        return allow

    except Exception as e:
        logger.error(f"filter_inferences_error: {e}", exc_info=True)
        return []


def _build_snapshot(user_id: str) -> Dict[str, Any]:
    """
    Build UI snapshot with current trait state.

    Args:
        user_id: User identifier

    Returns:
        Snapshot dict with traits array
    """
    try:
        from .. import ui_readonly
        return ui_readonly.unabridged_snapshot(user_id)
    except Exception as e:
        logger.error(f"build_snapshot_error: {e}", exc_info=True)
        return {"traits": []}
