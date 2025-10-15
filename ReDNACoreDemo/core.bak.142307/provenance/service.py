"""
Provenance service for trait explainability.

Assembles complete provenance information for a trait including:
- Current resolved value and UCN
- Evidence timeline (all observations)
- Inference items (rule-based derivations)
- Resolver trace references
- RR scoring status
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.storage import USERS_DIR, CORE_DATA_ROOT


def _user_dir(user_id: str) -> Path:
    """Get user data directory."""
    return USERS_DIR / user_id


def _load_json(p: Path) -> Any:
    """Load JSON file safely."""
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _iter_evidence_files(user_id: str) -> List[Path]:
    """Iterate evidence files for user (newest first)."""
    evdir = _user_dir(user_id)

    # Check multiple possible evidence locations
    evidence_files = []

    # Single evidence file
    ev_file = evdir / "evidence.json"
    if ev_file.exists():
        evidence_files.append(ev_file)

    # Evidence directory
    ev_dir = evdir / "evidence"
    if ev_dir.exists() and ev_dir.is_dir():
        evidence_files.extend(sorted(ev_dir.glob("*.json"), reverse=True))

    return evidence_files


def _iter_trace_files(user_id: str) -> List[Path]:
    """Iterate resolver trace files for user (newest first)."""
    tdir = _user_dir(user_id) / "resolver_traces"
    if not tdir.exists():
        return []
    return sorted(tdir.glob("*.json"), reverse=True)


def build_provenance(user_id: str, trait_id: str, max_traces: int = 10) -> Dict[str, Any]:
    """
    Assemble complete provenance for one trait.

    Args:
        user_id: User identifier
        trait_id: Canonical trait ID (e.g., "PaDNA.EyeDNA.IrisColor")
        max_traces: Maximum number of trace files to scan

    Returns:
        Provenance dict with resolved state, evidence, inferences, traces, and RR status
    """
    udir = _user_dir(user_id)

    # Load resolved state
    resolved = _load_json(udir / "resolved.json") or {}
    r_entry = resolved.get(trait_id) or {}

    # Gather evidence across all files
    evidence: List[Dict[str, Any]] = []

    for f in _iter_evidence_files(user_id):
        data = _load_json(f)
        if not data:
            continue

        # Handle different evidence file formats
        records = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # Could be {"items": [...]} or single evidence object
            items = data.get("items", [])
            if items:
                records = items
            elif "trait_id" in data:
                records = [data]

        # Extract evidence for this trait
        for ev in records:
            if not isinstance(ev, dict):
                continue

            if ev.get("trait_id") == trait_id:
                # Normalize value format
                value = ev.get("value")
                if not value:
                    # Handle legacy fact_value
                    fact_val = ev.get("fact_value")
                    if fact_val is not None:
                        # Try to infer type
                        if isinstance(fact_val, (int, float)):
                            value = {"number": fact_val}
                        else:
                            value = {"text": str(fact_val)}

                evidence.append({
                    "source": ev.get("source", "unknown"),
                    "ts": ev.get("ts"),
                    "value": value,
                    "ucn_prior": ev.get("ucn_prior"),
                    "provenance": ev.get("provenance"),
                    "req_id": ev.get("request_id") or ev.get("req_id")
                })

    # Scan resolver traces
    traces: List[Dict[str, Any]] = []

    for f in _iter_trace_files(user_id)[:max_traces]:
        data = _load_json(f)
        if not data:
            continue

        req_id = data.get("req_id")
        touched = False
        rr_ok = True

        steps = data.get("steps") or []
        for s in steps:
            name = s.get("name")
            payload = s.get("payload")

            # Check if this step touched our trait
            if name == "chosen":
                # chosen is {trait_id: Evidence}
                if isinstance(payload, dict) and trait_id in payload:
                    touched = True

            elif name == "rr_input":
                # list of items with trait_id
                if isinstance(payload, list):
                    if any(x.get("trait_id") == trait_id for x in payload):
                        touched = True

            elif name == "resolved_out":
                # Check if trait is in resolved output
                if isinstance(payload, dict):
                    if trait_id in payload or (
                        "trait_count" in payload and touched
                    ):
                        touched = True

            # Check for RR errors
            if name == "rr_error":
                rr_ok = False

        if touched:
            traces.append({
                "req_id": req_id,
                "file": f.name,  # Just filename, not full path
                "rr_ok": rr_ok
            })

    # Separate direct evidence from inferences
    inference_items = [
        ev for ev in evidence
        if (ev.get("provenance") or "").startswith("inference:")
    ]

    direct_evidence = [
        ev for ev in evidence
        if not (ev.get("provenance") or "").startswith("inference:")
    ]

    # Determine RR status from most recent trace
    rr_status = "unknown"
    if traces:
        rr_status = "ok" if traces[0].get("rr_ok", True) else "offline"

    return {
        "trait_id": trait_id,
        "resolved": {
            "value": r_entry.get("value"),
            "ucn": r_entry.get("ucn", 0.0),
            "status": r_entry.get("status"),
            "last_updated": r_entry.get("last_updated"),
            "sources": r_entry.get("sources", [])
        },
        "direct_evidence": direct_evidence,
        "inferences": inference_items,
        "traces": traces,
        "rr_status": rr_status
    }
