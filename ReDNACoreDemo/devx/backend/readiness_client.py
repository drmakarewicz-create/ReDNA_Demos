"""
Utilities for polling DevX stack readiness with optional warmup seeding.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import httpx


Callback = Callable[[], None]
SleepFn = Callable[[float], None]

READINESS_RETRY_BACKOFF = 0.2


@dataclass
class ReadinessResult:
    ready: bool
    resilience_used: bool
    seeded: bool
    last_payload: Optional[Dict[str, Any]]
    last_error: Optional[str]


def poll_stack_readiness(
    *,
    devx_base: str,
    core_base: str,
    timeout: float = 90.0,
    poll_interval: float = 3.0,
    seed_after: float = 30.0,
    restart_after: float = 60.0,
    session: Optional[httpx.Client] = None,
    seed_func: Optional[Callback] = None,
    restart_func: Optional[Callback] = None,
    sleep_func: Optional[SleepFn] = None,
) -> ReadinessResult:
    """
    Poll DevX readiness endpoint until the stack reports ready or timeout occurs.

    Args:
        devx_base: Base URL for the DevX backend (without trailing slash).
        core_base: Base URL for Core API (unused directly, but captured for telemetry symmetry).
        timeout: Max seconds to wait before giving up.
        poll_interval: Seconds between readiness checks.
        seed_after: Seconds before triggering warmup seeding callback.
        restart_after: Seconds before invoking resilience callback.
        session: Optional requests session to reuse TCP connections.
        seed_func: Optional callback invoked once to seed Core traffic.
        restart_func: Optional callback invoked once to trigger resilience restart.
        sleep_func: Optional sleep implementation (used in tests).

    Returns:
        ReadinessResult summarising operations performed.
    """

    del core_base  # Reserved for future telemetry symmetry

    sleeper: SleepFn = sleep_func or time.sleep

    ready_endpoint = f"{devx_base.rstrip('/')}/devx/api/stack/ready"

    start_time = time.time()
    deadline = start_time + timeout
    seed_deadline = start_time + seed_after
    restart_deadline = start_time + restart_after

    seeded = False
    resilience_used = False
    last_payload: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None

    def should_seed(payload: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(payload, dict):
            return False
        fail_conditions = payload.get("fail_conditions") or []
        return "metrics_warming" in fail_conditions

    own_client: Optional[httpx.Client] = None
    if session is None:
        own_client = httpx.Client(timeout=httpx.Timeout(connect=1.0, read=2.5, write=2.5, pool=2.5))
    client = session or own_client

    try:
        while time.time() < deadline:
            try_again = False
            try:
                response = client.get(ready_endpoint)
                response.raise_for_status()
                payload = response.json()
                last_payload = payload if isinstance(payload, dict) else None
            except httpx.ReadTimeout as exc:  # pragma: no cover - network dependent
                if last_payload is None and (time.time() + READINESS_RETRY_BACKOFF) < deadline:
                    sleeper(READINESS_RETRY_BACKOFF)
                    try_again = True
                else:
                    last_error = f"ready_timeout:{exc}"
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = f"ready_error:{exc}"
            if try_again:
                continue

            if isinstance(last_payload, dict) and last_payload.get("ready"):
                return ReadinessResult(
                    ready=True,
                    resilience_used=resilience_used,
                    seeded=seeded,
                    last_payload=last_payload,
                    last_error=None,
                )

            status = (last_payload or {}).get("status")
            now = time.time()

            if not seeded and status == "warming" and now >= seed_deadline and seed_func and should_seed(last_payload):
                try:
                    seed_func()
                except Exception as exc:  # pragma: no cover - defensive
                    last_error = f"seed_error:{exc}"
                seeded = True

            if not resilience_used and now >= restart_deadline and restart_func:
                try:
                    restart_func()
                    resilience_used = True
                except Exception as exc:  # pragma: no cover - defensive
                    last_error = f"restart_error:{exc}"

            sleeper(poll_interval)
    finally:
        if own_client is not None:
            own_client.close()

    return ReadinessResult(
        ready=False,
        resilience_used=resilience_used,
        seeded=seeded,
        last_payload=last_payload,
        last_error=last_error or "timeout",
    )


__all__ = ["ReadinessResult", "poll_stack_readiness"]
