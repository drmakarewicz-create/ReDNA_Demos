"""HTTP health probes for Control Panel Plus Plus."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class HealthResult:
    status: str  # PASS | WARN | FAIL
    elapsed_ms: float
    detail: str
    url: str
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


REQUEST_TIMEOUT = 5.0
POLL_INTERVAL = 0.3


def probe_core(base_url: str, attempts: int = 1, poll_interval: float = POLL_INTERVAL) -> HealthResult:
    url = base_url.rstrip("/") + "/ui/personas"
    total_started = time.perf_counter()
    last_error = "No response"
    payload: Optional[Dict[str, Any]] = None

    for attempt in range(max(1, attempts)):
        started = time.perf_counter()
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            elapsed = (time.perf_counter() - started) * 1000
            if response.status_code == 200:
                payload = response.json()
                personas = payload.get("personas") if isinstance(payload, dict) else None
                count = len(personas) if isinstance(personas, list) else 0
                return HealthResult(
                    status="PASS",
                    elapsed_ms=elapsed,
                    detail=f"Roster: {count} persona(s)",
                    payload=payload,
                    url=url,
                )
            last_error = f"HTTP {response.status_code}"
        except requests.Timeout:
            last_error = "Timeout"
        except Exception as exc:
            last_error = str(exc)
        if attempt < attempts - 1:
            time.sleep(poll_interval)

    # Secondary probe for debugging
    openapi_url = base_url.rstrip("/") + "/openapi.json"
    try:
        doc_response = requests.get(openapi_url, timeout=REQUEST_TIMEOUT)
        if doc_response.status_code == 200:
            detail = f"OpenAPI reachable, /ui/personas failed ({last_error})"
            return HealthResult(
                status="WARN",
                elapsed_ms=(time.perf_counter() - total_started) * 1000,
                detail=detail,
                payload=None,
                url=url,
                error=last_error,
            )
    except Exception:
        pass

    return HealthResult(
        status="FAIL",
        elapsed_ms=(time.perf_counter() - total_started) * 1000,
        detail=last_error,
        payload=payload,
        url=url,
        error=last_error,
    )


def probe_react(base_url: str, attempts: int = 1, poll_interval: float = POLL_INTERVAL) -> HealthResult:
    base = base_url.rstrip("/")
    url = f"{base}/?ui_debug=1"
    total_started = time.perf_counter()
    last_error = "No response"

    for attempt in range(max(1, attempts)):
        started = time.perf_counter()
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            elapsed = (time.perf_counter() - started) * 1000
            if response.status_code == 200:
                detail = "reachable"
                payload = None
                try:
                    debug_response = requests.get(f"{base}/api/debug", timeout=REQUEST_TIMEOUT)
                    if debug_response.status_code == 200:
                        payload = debug_response.json()
                        composer = payload.get("composer_ready")
                        persona = payload.get("active_persona", {}).get("label") or payload.get("active_persona")
                        detail = f"composer={'✓' if composer else '✗'}, persona={persona}"
                        return HealthResult(
                            status="PASS",
                            elapsed_ms=elapsed,
                            detail=detail,
                            payload=payload,
                            url=url,
                        )
                except Exception:
                    detail = "debug endpoint unavailable"
                return HealthResult(
                    status="WARN",
                    elapsed_ms=elapsed,
                    detail=detail,
                    url=url,
                    error=None,
                )
            last_error = f"HTTP {response.status_code}"
        except requests.Timeout:
            last_error = "Timeout"
        except Exception as exc:
            last_error = str(exc)
        if attempt < attempts - 1:
            time.sleep(poll_interval)

    return HealthResult(
        status="FAIL",
        elapsed_ms=(time.perf_counter() - total_started) * 1000,
        detail=last_error,
        url=url,
        error=last_error,
    )


def probe_streamlit(base_url: str, attempts: int = 1, poll_interval: float = POLL_INTERVAL) -> HealthResult:
    base = base_url.rstrip("/")
    url = f"{base}/?ui_debug=1&format=json"
    total_started = time.perf_counter()
    last_error = "No response"

    for attempt in range(max(1, attempts)):
        started = time.perf_counter()
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            elapsed = (time.perf_counter() - started) * 1000
            if response.status_code == 200:
                try:
                    payload = response.json()
                    composer_ready = payload.get("composer_rendered")
                    persona = payload.get("active_persona", {}).get("label")
                    overlay = payload.get("overlay_ok")
                    detail = f"composer={'✓' if composer_ready else '✗'}, persona={persona}, overlay={'✓' if overlay else '✗'}"
                    return HealthResult(
                        status="PASS",
                        elapsed_ms=elapsed,
                        detail=detail,
                        payload=payload,
                        url=url,
                    )
                except ValueError:
                    return HealthResult(
                        status="WARN",
                        elapsed_ms=elapsed,
                        detail="HTML response (no debug JSON)",
                        url=url,
                        error="No debug JSON",
                    )
            last_error = f"HTTP {response.status_code}"
        except requests.Timeout:
            last_error = "Timeout"
        except Exception as exc:
            last_error = str(exc)
        if attempt < attempts - 1:
            time.sleep(poll_interval)

    return HealthResult(
        status="FAIL",
        elapsed_ms=(time.perf_counter() - total_started) * 1000,
        detail=last_error,
        url=url,
        error=last_error,
    )

