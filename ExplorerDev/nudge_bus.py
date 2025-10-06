"""Wrapper utilities bridging Dev Explorer UI with the shared nudge store."""

from __future__ import annotations

try:
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path
except Exception:  # pragma: no cover
    import os
    import sys

    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from ExplorerDev.bootstrap import ensure_explorerdev_on_path  # type: ignore

ensure_explorerdev_on_path()

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - allow import without Streamlit runtime
    st = None  # type: ignore

from ExplorerDev.write_utils import WriteProtectContext
from ExplorerFinal.core import nudge_store


def compute_hash(payload: Dict[str, Any]) -> str:
    """Expose the shared hash function for dedupe checks."""

    return nudge_store.compute_bundle_hash(payload)


def enqueue(
    *,
    user_id: str,
    persona_id: str,
    mode: str,
    items: List[Dict[str, Any]],
    tone_meta: Optional[str],
    snapshot_id: Optional[str],
    provenance: Dict[str, Any],
    context: WriteProtectContext,
) -> Dict[str, Any]:
    """Send a bundle into the shared nudge store.

    Returns the store response containing `duplicate` and the persisted `bundle`.
    """

    payload = {
        "persona_id": persona_id,
        "mode": mode,
        "items": items,
        "tone_meta": tone_meta,
        "snapshot_id": snapshot_id,
        "provenance": provenance,
    }
    return nudge_store.add_bundle(user_id, payload, write_protect=context.write_protect)


def list_for_user(
    user_id: str,
    *,
    status_filter: str = "inbox",
    limit: int = 100,
    context: Optional[WriteProtectContext] = None,
) -> List[Dict[str, Any]]:
    write_protect = context.write_protect if context is not None else False
    return nudge_store.list_inbox(
        user_id,
        status_filter=status_filter,
        limit=limit,
        write_protect=write_protect,
    )


def tail_log(*, max_lines: int = 200) -> List[Dict[str, Any]]:
    path = nudge_store.get_enqueue_log_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()[-max_lines:]
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))  # type: ignore[name-defined]
        except Exception:
            continue
    return out


def log_path() -> Path:
    return nudge_store.get_enqueue_log_path()
