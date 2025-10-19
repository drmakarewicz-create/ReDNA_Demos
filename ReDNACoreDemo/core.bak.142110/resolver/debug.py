"""
Debug and tracing utilities for the resolver.

This module provides per-request trace logging to disk,
enabling full traceability of resolver decisions.
"""
from __future__ import annotations
from pathlib import Path
import json
import time
from typing import Dict, Any


def new_trace(req_id: str) -> Dict[str, Any]:
    """
    Create a new trace object for a resolver request.

    Args:
        req_id: Unique request identifier

    Returns:
        Trace dictionary with steps array
    """
    return {
        "req_id": req_id,
        "steps": [],
        "ts": time.time()
    }


def log_step(trace: Dict[str, Any], name: str, payload: Any) -> None:
    """
    Log a step in the resolver trace.

    Args:
        trace: Trace dictionary
        name: Step name (e.g., "evidence_in", "rr_output")
        payload: Step data (will be JSON-serialized)
    """
    trace["steps"].append({
        "name": name,
        "payload": payload,
        "ts": time.time()
    })


def write_trace(trace_dir: Path, trace: Dict[str, Any]) -> str:
    """
    Write a trace to disk.

    Args:
        trace_dir: Directory to write trace to
        trace: Trace dictionary

    Returns:
        Path to written trace file
    """
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{trace['req_id']}.json"
    path.write_text(json.dumps(trace, indent=2, default=str))
    return str(path)
