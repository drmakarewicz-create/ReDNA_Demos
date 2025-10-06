"""Holistic scheduler utilities for Dev Explorer."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

try:
    from .bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - script execution path
    import sys

    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from bootstrap import ensure_repo_root  # type: ignore

try:
    from .write_utils import WriteProtectContext, write_guard
except ImportError:  # pragma: no cover - script execution path
    import sys

    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from write_utils import WriteProtectContext, write_guard  # type: ignore

from .schema_utils import core_base_url, get_flag_float, ucnrr_base_url


REPO_ROOT = ensure_repo_root()
SYSTEM_PREFS_PATH = REPO_ROOT / "data/dev_system_prefs.json"
SCHEDULER_LOG_PATH = REPO_ROOT / "data/dev_logs/scheduler.log"
_MAX_RING_SIZE = 500


def load_scheduler_prefs() -> Dict[str, Any]:
    if not SYSTEM_PREFS_PATH.exists():
        return {}
    try:
        return json.loads(SYSTEM_PREFS_PATH.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - prefs are advisory only
        return {}


def save_scheduler_prefs(prefs: Dict[str, Any], write_context: WriteProtectContext) -> None:
    if getattr(write_context, "write_protect", False):
        raise PermissionError("Write-protect ON — unable to update scheduler prefs.")
    write_guard(write_context, action="update system preferences")
    SYSTEM_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYSTEM_PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def _ring_buffer(write_context: WriteProtectContext) -> List[Dict[str, Any]]:
    return st.session_state.setdefault("_sched_ring", [])  # type: ignore[return-value]


def append_run_history(
    entry: Dict[str, Any],
    write_context: WriteProtectContext,
    snapshot: Optional[Dict[str, Any]] = None,
) -> None:
    entry = dict(entry)
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    entry.setdefault("trigger", "manual")
    entry.setdefault("result", "ok")

    if snapshot and snapshot.get("ok"):
        entry.setdefault("snapshot_id", snapshot.get("snapshot_id"))
        entry.setdefault("snapshot_path", snapshot.get("path"))
        entry.setdefault("snapshot_note", snapshot.get("note"))
        entry.setdefault("snapshot_size", snapshot.get("size"))

        storage = "memory" if snapshot.get("path") is None else "disk"
        entry.setdefault("snapshot_storage", storage)

    if getattr(write_context, "write_protect", False):
        ring = _ring_buffer(write_context)
        ring.append(entry)
        if len(ring) > _MAX_RING_SIZE:
            del ring[: len(ring) - _MAX_RING_SIZE]
        return

    write_guard(write_context, action="append scheduler log entry")
    SCHEDULER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SCHEDULER_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def load_run_history(write_context: WriteProtectContext, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if SCHEDULER_LOG_PATH.exists():
        try:
            for raw in SCHEDULER_LOG_PATH.read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
        except Exception:  # pragma: no cover - log is advisory only
            pass

    ring = _ring_buffer(write_context)
    if isinstance(ring, list):
        entries.extend(ring)

    entries.sort(key=lambda item: item.get("ts", ""), reverse=True)
    if limit is not None:
        return entries[:limit]
    return entries


def _timeout_seconds() -> float:
    value, _ = get_flag_float("DEV_HTTP_TIMEOUT_SECONDS", 6.0)
    return float(value)


def run_now_probe() -> Tuple[str, int, str]:
    """Run a lightweight endpoint probe for scheduler diagnostics."""

    uc_base = ucnrr_base_url().rstrip("/")
    core_base = core_base_url().rstrip("/")
    timeout = _timeout_seconds()

    endpoints = [
        ("ucnrr", f"{uc_base}/health"),
        ("core", f"{core_base}/health"),
    ]

    statuses: List[str] = []
    ok = True
    started = time.time()

    for name, url in endpoints:
        try:
            response = requests.get(url, timeout=timeout)
            statuses.append(f"{name}={response.status_code}")
            if response.status_code >= 400:
                ok = False
        except requests.RequestException:
            statuses.append(f"{name}=ERR")
            ok = False

    duration_ms = int((time.time() - started) * 1000)
    notes = " ".join(statuses) if statuses else "no probe"
    return ("ok" if ok else "fail", duration_ms, notes)
