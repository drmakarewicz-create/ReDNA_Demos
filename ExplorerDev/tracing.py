"""Trace helpers for the round-trip observability suite."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import os
try:
    from ExplorerDev.bootstrap import ensure_repo_root
except Exception:  # pragma: no cover - bootstrap fallback
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_repo_root  # type: ignore

from ExplorerDev.write_utils import WriteProtectContext


REPO_ROOT = ensure_repo_root()
TRACE_ROOT = REPO_ROOT / "data" / "dev_logs"

_COMPONENT_PATHS = {
    "devexp": TRACE_ROOT / "trace_devexp.jsonl",
    "ucnrr": TRACE_ROOT / "trace_ucnrr.jsonl",
    "core": TRACE_ROOT / "trace_core.jsonl",
}


def new_trace_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"rt_{timestamp}_{uuid.uuid4().hex[:4]}"


def _append(component: str, record: Dict[str, Any], *, write_protect: bool) -> None:
    if write_protect:
        return
    path = _COMPONENT_PATHS.get(component)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def start_span(
    *,
    component: str,
    trace_id: str,
    span: str,
    meta: Optional[Dict[str, Any]] = None,
    write_protect: bool,
) -> None:
    if not trace_id:
        return
    _append(
        component,
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "span": span,
            "phase": "start",
            "meta": meta or {},
        },
        write_protect=write_protect,
    )


def end_span(
    *,
    component: str,
    trace_id: str,
    span: str,
    meta: Optional[Dict[str, Any]] = None,
    write_protect: bool,
) -> None:
    if not trace_id:
        return
    _append(
        component,
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "span": span,
            "phase": "end",
            "meta": meta or {},
        },
        write_protect=write_protect,
    )


def log_event(
    *,
    component: str,
    trace_id: str,
    event: str,
    meta: Optional[Dict[str, Any]] = None,
    write_protect: bool,
) -> None:
    if not trace_id:
        return
    _append(
        component,
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "event": event,
            "meta": meta or {},
        },
        write_protect=write_protect,
    )


def trace_log_paths() -> Dict[str, Path]:
    return dict(_COMPONENT_PATHS)


__all__ = [
    "new_trace_id",
    "start_span",
    "end_span",
    "log_event",
    "trace_log_paths",
]
