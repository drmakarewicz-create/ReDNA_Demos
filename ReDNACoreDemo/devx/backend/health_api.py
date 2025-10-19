"""
DevX Health API
===============

Provides live status for DevX, Consent, and Core services and records a rolling
history for the System Monitor dashboard.
"""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Deque, Dict, List

import httpx
from fastapi import APIRouter, Query

from .privacy_dashboard_api import get_consent_service_url, DATA_ROOT

router = APIRouter()

CORE_HEALTH_URL = os.getenv("REDNA_CORE_HEALTH", "http://127.0.0.1:8015/health")
DEVX_HEALTH_URL = os.getenv("REDNA_DEVX_HEALTH", "http://127.0.0.1:8100/health")

HISTORY_ROOT = DATA_ROOT / "system_logs" / "health"
HISTORY_FILE = HISTORY_ROOT / "health_history.jsonl"
HISTORY_ROOT.mkdir(parents=True, exist_ok=True)

HISTORY_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=100)


def _load_history_from_disk() -> None:
    if not HISTORY_FILE.exists():
        return
    try:
        lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for line in lines[-HISTORY_BUFFER.maxlen :]:
        try:
            HISTORY_BUFFER.append(json.loads(line))
        except json.JSONDecodeError:
            continue


def _append_history(entry: Dict[str, Any]) -> None:
    HISTORY_BUFFER.append(entry)
    try:
        with HISTORY_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: BLE001
        pass


async def _probe(url: str) -> Dict[str, Any]:
    start = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
        latency_ms = (perf_counter() - start) * 1000
        detail = response.text[:200]
        ok = response.status_code == 200
        status = "green" if ok else "red"
        if ok:
            try:
                payload = response.json()
                reported = str(payload.get("status", "")).lower()
            except ValueError:
                reported = ""
            if reported and reported not in {"healthy", "ok", "green"}:
                status = "amber"
        return {
            "status": status,
            "ok": status == "green",
            "ms": round(latency_ms, 2),
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "red", "ok": False, "ms": None, "detail": str(exc)}


@router.get("/health/status")
async def health_status() -> Dict[str, Dict[str, Any]]:
    """Return live status and append to history."""

    consent_url = f"{get_consent_service_url().rstrip('/')}/health"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    devx_info = await _probe(DEVX_HEALTH_URL)
    consent_info = await _probe(consent_url)
    core_info = await _probe(CORE_HEALTH_URL)

    entry = {
        "ts": timestamp,
        "devx": {"ok": devx_info["ok"], "ms": devx_info["ms"]},
        "consent": {"ok": consent_info["ok"], "ms": consent_info["ms"]},
        "core": {"ok": core_info["ok"], "ms": core_info["ms"]},
    }
    _append_history(entry)

    devx_info["checked_at"] = timestamp
    consent_info["checked_at"] = timestamp
    core_info["checked_at"] = timestamp

    return {
        "devx": devx_info,
        "consent": consent_info,
        "core": core_info,
    }


@router.get("/health/history")
async def health_history(limit: int = Query(100, ge=1, le=100)) -> Dict[str, List[Dict[str, Any]]]:
    """Return the most recent health entries (newest first)."""
    items = list(HISTORY_BUFFER)[-limit:]
    return {"entries": list(reversed(items))}


_load_history_from_disk()
