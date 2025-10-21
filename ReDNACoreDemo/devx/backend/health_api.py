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
from typing import Any, Deque, Dict, List, Optional

import httpx
from fastapi import APIRouter, Query, Response

from .config import DEVX_CORE_BASE
from .privacy_dashboard_api import DATA_ROOT

router = APIRouter()

# Health check URLs - defaults updated to match current port allocation (Phase 10)
CORE_HEALTH_URL = os.getenv("REDNA_CORE_HEALTH", f"{DEVX_CORE_BASE.rstrip('/')}/health")
CONSENT_HEALTH_URL = os.getenv(
    "REDNA_CONSENT_HEALTH", f"{DEVX_CORE_BASE.rstrip('/')}/core/consent/health"
)
DEVX_HEALTH_URL = os.getenv("REDNA_DEVX_HEALTH", "http://127.0.0.1:8100/health")

HISTORY_ROOT = DATA_ROOT / "system_logs" / "health"
HISTORY_FILE = HISTORY_ROOT / "health_history.jsonl"
HISTORY_ROOT.mkdir(parents=True, exist_ok=True)

HISTORY_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=100)
PROBE_TIMEOUT = httpx.Timeout(read=2.0, write=2.0, connect=2.0, pool=2.0)


def _bool_query(value: Optional[str]) -> bool:
    if value is None:
        return False
    lowered = value.strip().lower()
    return lowered in {"1", "true", "yes", "force"}


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


async def _probe(url: str, *, force: bool = False) -> Dict[str, Any]:
    start = perf_counter()
    params = {"force": "1"} if force else None
    headers = {"Cache-Control": "no-cache"}
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
            response = await client.get(url, params=params, headers=headers)
        latency_ms = (perf_counter() - start) * 1000
        try:
            payload = response.json()
            raw_body: Any = payload
        except ValueError:
            raw_body = response.text[:200]
            payload = None

        reported = ""
        warning_text = None
        detail_text = None
        if isinstance(payload, dict):
            reported = str(payload.get("status", "")).lower()
            warning_text = payload.get("warning")
            detail_text = warning_text or payload.get("detail")
            if detail_text is None:
                detail_text = payload.get("summary")
        elif isinstance(raw_body, str):
            detail_text = raw_body

        success = response.status_code == 200
        status = "green" if success else "red"
        ok = False

        result_error = None

        if success:
            if reported == "healthy":
                status = "green"
                ok = True
                detail_text = detail_text or "Healthy"
            elif reported == "degraded":
                status = "yellow"
                ok = False
                detail_text = detail_text or "Degraded"
            elif reported == "error":
                status = "red"
                ok = False
                detail_text = detail_text or "Error reported"
                result_error = detail_text
            elif reported in {"green", "yellow", "amber"}:
                status = "yellow" if reported != "green" else "green"
                ok = status == "green"
            elif reported:
                status = "yellow"
                detail_text = detail_text or f"Status: {reported}"
            else:
                status = "yellow"
                detail_text = detail_text or "Unknown status payload"
        else:
            detail_text = detail_text or f"HTTP {response.status_code}"

        if status == "yellow" and warning_text:
            detail_text = warning_text

        if status == "red" and not ok:
            result_error = result_error or detail_text

        result: Dict[str, Any] = {
            "status": status,
            "ok": ok,
            "ms": round(latency_ms, 2),
            "detail": detail_text or raw_body,
            "reported_status": reported or None,
        }
        if warning_text:
            result["warning"] = warning_text
        if force:
            result["force"] = True
        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
        elif result_error:
            result["error"] = result_error
        if payload is not None:
            result["payload"] = payload
        return result
    except Exception as exc:  # noqa: BLE001
        # Include URL in error detail for debugging
        error_detail = f"{url}: {type(exc).__name__}: {exc}"
        result = {"status": "red", "ok": False, "ms": None, "detail": error_detail, "error": "exception"}
        if force:
            result["force"] = True
        return result


@router.get("/health/status")
async def health_status(
    response: Response,
    force: Optional[str] = Query(None, description="Bypass caches for downstream health probes"),
) -> Dict[str, Dict[str, Any]]:
    """Return live status and append to history."""

    response.headers["Cache-Control"] = "no-cache"
    force_flag = _bool_query(force)
    consent_url = CONSENT_HEALTH_URL
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Debug: print URLs being checked
    print(f"[Health Check] DevX: {DEVX_HEALTH_URL}")
    print(f"[Health Check] Consent: {consent_url}")
    print(f"[Health Check] Core: {CORE_HEALTH_URL}")

    devx_info = await _probe(DEVX_HEALTH_URL, force=force_flag)
    consent_info = await _probe(consent_url, force=force_flag)
    core_info = await _probe(CORE_HEALTH_URL, force=force_flag)

    print(f"[Health Check] Core result: {core_info}")

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
