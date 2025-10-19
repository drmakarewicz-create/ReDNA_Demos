"""
UCNRR Supervisor Module
========================

Ensures UCNRR is running, monitors its health, and auto-restarts with
bounded exponential backoff and restart capping.

Features:
- ensure_ucnrr(): Idempotent startup with pre-flight validation
- check_ucnrr(): Fast liveness probe with timeouts
- monitor_ucnrr(): Async monitor loop with backoff and restart cap
- Reason codes for diagnostics and recovery suggestions
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ReDNACoreDemo.core.logutil import stack_log

# Configuration
REPO_ROOT = Path(__file__).resolve().parents[3]
REDNA_HOME = Path(os.getenv("REDNA_HOME", Path.home() / ".redna")).expanduser()
REDNA_HOME.mkdir(parents=True, exist_ok=True)

UCNRR_PID_FILE = REDNA_HOME / "ucnrr.pid"
UCNRR_LOG_FILE = Path("/tmp/ucnrr.log")

DEFAULT_UCNRR_PORT = 8017
DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434"

# Health check timeouts (seconds)
UCNRR_HEALTH_CONNECT_TIMEOUT = 0.3
UCNRR_HEALTH_READ_TIMEOUT = 0.7

# Warmup configuration
UCNRR_WARMUP_ENABLED = os.getenv("UCNRR_WARMUP_ENABLED", "true").lower() in ("1", "true", "yes", "on")
OLLAMA_API = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE)
UCNRR_WARMUP_CONNECT_MS = int(os.getenv("UCNRR_WARMUP_CONNECT_MS", "500"))
UCNRR_WARMUP_READ_MS = int(os.getenv("UCNRR_WARMUP_READ_MS", "2000"))

# Backoff schedule (seconds)
BACKOFF_SCHEDULE = [2, 5, 10, 30]  # Final value is cap
BACKOFF_MAX_SEC = BACKOFF_SCHEDULE[-1]

# Restart cap: max restarts within window
RESTART_CAP_COUNT = 3
RESTART_CAP_WINDOW_SEC = 600  # 10 minutes

PYTHON_EXECUTABLE = sys.executable


@dataclass
class UCNRRState:
    """Tracks UCNRR supervisor state."""
    pid: Optional[int] = None
    last_start_ts: Optional[float] = None
    restart_timestamps: List[float] = field(default_factory=list)
    backoff_level: int = 0
    restart_capped: bool = False
    cap_expires_ts: Optional[float] = None
    last_check_ts: Optional[float] = None
    last_status: str = "unknown"
    last_reason: str = ""


# Global state (in-memory, single process)
_UCNRR_STATE = UCNRRState()


def _now_ts() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pid_alive(pid: int) -> bool:
    """Check if PID is alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_pid(pid: int, timeout: float = 5.0) -> bool:
    """Kill PID with SIGTERM, fallback to SIGKILL."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.1)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return not _pid_alive(pid)


def _read_pid_file() -> Optional[int]:
    """Read PID from file."""
    if not UCNRR_PID_FILE.exists():
        return None
    try:
        raw = UCNRR_PID_FILE.read_text(encoding="utf-8").strip()
        return int(raw)
    except (ValueError, OSError):
        return None


def _write_pid_file(pid: int) -> None:
    """Write PID to file."""
    UCNRR_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    UCNRR_PID_FILE.write_text(str(pid), encoding="utf-8")


def _clear_pid_file() -> None:
    """Remove PID file."""
    try:
        UCNRR_PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _validate_ollama(ollama_base: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Ollama is reachable.
    Returns: (ok, error_reason)
    """
    try:
        response = httpx.get(f"{ollama_base}/api/tags", timeout=2.0)
        if response.status_code == 200:
            return True, None
        return False, f"ollama_http_{response.status_code}"
    except httpx.ConnectError:
        return False, "ollama_conn_refused"
    except httpx.TimeoutException:
        return False, "ollama_timeout"
    except Exception as exc:
        return False, f"ollama_error:{type(exc).__name__}"


def _validate_port_available(port: int) -> Tuple[bool, Optional[str]]:
    """
    Check if port is available.
    Returns: (ok, error_reason)
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex(("127.0.0.1", port))
        if result == 0:
            # Port is in use
            return False, f"port_{port}_in_use"
        return True, None


def _start_ucnrr_process(port: int) -> int:
    """
    Start UCNRR service via uvicorn.
    Returns PID.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["UCNRR_PORT"] = str(port)

    cmd = [
        PYTHON_EXECUTABLE,
        "-m",
        "uvicorn",
        "UCN_RR_Demo.ucnrr_app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "info",
    ]

    UCNRR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with UCNRR_LOG_FILE.open("ab") as log_handle:
        process = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )

    pid = process.pid
    _write_pid_file(pid)
    stack_log(
        "devx",
        "INFO",
        "ucnrr_start",
        f"UCNRR started (PID {pid})",
        {"pid": pid, "port": port, "log_file": str(UCNRR_LOG_FILE)},
    )
    return pid


def _warmup_model(model: str) -> None:
    """
    Warm up the LLM model with a trivial generation request.
    Best-effort; never blocks readiness for long.
    """
    if not UCNRR_WARMUP_ENABLED or not model:
        return

    try:
        timeout = httpx.Timeout(
            connect=UCNRR_WARMUP_CONNECT_MS / 1000,
            read=UCNRR_WARMUP_READ_MS / 1000,
            write=UCNRR_WARMUP_CONNECT_MS / 1000,
            pool=UCNRR_WARMUP_CONNECT_MS / 1000,
        )
        # Trivial generate; Ollama streams, so keep prompt tiny
        httpx.post(
            f"{OLLAMA_API}/api/generate",
            json={"model": model, "prompt": "ok", "stream": False},
            timeout=timeout,
        )
        stack_log(
            "devx",
            "INFO",
            "ucnrr_warmup_ok",
            f"Warmed {model}",
            {"model": model},
        )
    except Exception as exc:
        stack_log(
            "devx",
            "WARN",
            "ucnrr_warmup_skip",
            "Warmup skipped or failed",
            {"model": model, "error": str(exc)},
        )


def check_ucnrr() -> Dict[str, Any]:
    """
    Fast liveness probe for UCNRR.
    Returns: {alive: bool, llm_configured: bool, reason: str, details: {...}}
    """
    port = int(os.getenv("UCNRR_PORT", DEFAULT_UCNRR_PORT))
    url = f"http://127.0.0.1:{port}/health"
    timeout = httpx.Timeout(
        connect=UCNRR_HEALTH_CONNECT_TIMEOUT,
        read=UCNRR_HEALTH_READ_TIMEOUT,
        write=UCNRR_HEALTH_READ_TIMEOUT,
        pool=UCNRR_HEALTH_READ_TIMEOUT,
    )

    try:
        response = httpx.get(url, timeout=timeout)
        if response.status_code == 200:
            payload = response.json()
            llm_ok = payload.get("llm_configured", False)
            return {
                "alive": True,
                "llm_configured": llm_ok,
                "reason": "ok" if llm_ok else "bad_llm",
                "details": payload,
            }
        return {
            "alive": False,
            "llm_configured": False,
            "reason": f"http_{response.status_code}",
            "details": {},
        }
    except httpx.ConnectError:
        return {
            "alive": False,
            "llm_configured": False,
            "reason": "conn_refused",
            "details": {},
        }
    except httpx.TimeoutException:
        return {
            "alive": False,
            "llm_configured": False,
            "reason": "timeout",
            "details": {},
        }
    except Exception as exc:
        return {
            "alive": False,
            "llm_configured": False,
            "reason": f"error:{type(exc).__name__}",
            "details": {},
        }


def ensure_ucnrr(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Idempotent UCNRR startup with pre-flight checks.

    Steps:
    1. Validate environment (UCNRR_LLM_PROVIDER, UCNRR_LLM_MODEL, OLLAMA_BASE_URL)
    2. Validate Ollama is reachable
    3. Validate port is available or UCNRR is already running
    4. Start UCNRR if needed

    Returns: {status: str, reason: str, pid: int, model: str, provider: str}
    """
    config = config or {}

    # Read environment
    provider = config.get("provider") or os.getenv("UCNRR_LLM_PROVIDER", "ollama")
    model = config.get("model") or os.getenv("UCNRR_LLM_MODEL", "phi3:mini")
    ollama_base = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE)
    port = int(os.getenv("UCNRR_PORT", DEFAULT_UCNRR_PORT))
    force_restart = config.get("force_restart", False)

    # 1. Validate Ollama (only if provider is ollama)
    if provider == "ollama":
        ollama_ok, ollama_reason = _validate_ollama(ollama_base)
        if not ollama_ok:
            hint = f"Start Ollama: ollama serve & && ollama list"
            stack_log(
                "devx",
                "WARN",
                "ucnrr_ensure_failed",
                f"Ollama not reachable: {ollama_reason}",
                {"reason": ollama_reason, "hint": hint},
            )
            return {
                "status": "failed",
                "reason": ollama_reason,
                "hint": hint,
                "pid": None,
                "model": model,
                "provider": provider,
            }

    # 2. Check if UCNRR is already running
    pid = _read_pid_file()
    if pid and _pid_alive(pid):
        if not force_restart:
            # Already running, check health
            health = check_ucnrr()
            if health["alive"]:
                return {
                    "status": "already_running",
                    "reason": health["reason"],
                    "pid": pid,
                    "model": model,
                    "provider": provider,
                }
        # Force restart
        stack_log("devx", "INFO", "ucnrr_force_restart", "Force restarting UCNRR", {"pid": pid})
        _kill_pid(pid)
        _clear_pid_file()

    # 3. Validate port is available
    port_ok, port_reason = _validate_port_available(port)
    if not port_ok:
        return {
            "status": "failed",
            "reason": port_reason,
            "pid": None,
            "model": model,
            "provider": provider,
        }

    # 4. Start UCNRR
    try:
        new_pid = _start_ucnrr_process(port)
        _UCNRR_STATE.pid = new_pid
        _UCNRR_STATE.last_start_ts = _now_ts()
        _UCNRR_STATE.restart_timestamps.append(_now_ts())

        # Wait briefly for startup
        time.sleep(2)
        health = check_ucnrr()

        # Warm up model if healthy and configured
        if health["alive"] and health["llm_configured"]:
            _warmup_model(model)

        return {
            "status": "started",
            "reason": health["reason"],
            "pid": new_pid,
            "model": model,
            "provider": provider,
            "alive": health["alive"],
            "llm_configured": health["llm_configured"],
        }
    except Exception as exc:
        stack_log(
            "devx",
            "ERROR",
            "ucnrr_start_failed",
            f"Failed to start UCNRR: {exc}",
            {"error": str(exc)},
        )
        return {
            "status": "failed",
            "reason": f"start_error:{type(exc).__name__}",
            "pid": None,
            "model": model,
            "provider": provider,
        }


def _record_restart() -> None:
    """Record a restart timestamp and clean old entries."""
    now = _now_ts()
    _UCNRR_STATE.restart_timestamps.append(now)
    cutoff = now - RESTART_CAP_WINDOW_SEC
    _UCNRR_STATE.restart_timestamps = [
        ts for ts in _UCNRR_STATE.restart_timestamps if ts >= cutoff
    ]


def _check_restart_cap() -> bool:
    """Check if restart cap is exceeded."""
    now = _now_ts()
    cutoff = now - RESTART_CAP_WINDOW_SEC
    recent = [ts for ts in _UCNRR_STATE.restart_timestamps if ts >= cutoff]
    return len(recent) >= RESTART_CAP_COUNT


def _get_backoff_delay() -> int:
    """Get current backoff delay in seconds."""
    level = min(_UCNRR_STATE.backoff_level, len(BACKOFF_SCHEDULE) - 1)
    return BACKOFF_SCHEDULE[level]


async def monitor_ucnrr(interval: float = 5.0) -> None:
    """
    Async monitor loop for UCNRR.

    - Checks health every `interval` seconds
    - Restarts on failure with exponential backoff
    - Caps restarts to prevent thrashing

    Emits stack_log events:
    - ucnrr_online
    - ucnrr_unhealthy
    - ucnrr_restart
    - ucnrr_backoff
    - ucnrr_cap
    """
    stack_log("devx", "INFO", "ucnrr_monitor_start", "UCNRR monitor started", {})

    while True:
        await asyncio.sleep(interval)

        # Check if restart cap needs to be cleared
        if _UCNRR_STATE.restart_capped:
            if _UCNRR_STATE.cap_expires_ts and _now_ts() >= _UCNRR_STATE.cap_expires_ts:
                _UCNRR_STATE.restart_capped = False
                _UCNRR_STATE.backoff_level = 0
                stack_log("devx", "INFO", "ucnrr_cap_cleared", "Restart cap expired", {})

        health = check_ucnrr()
        _UCNRR_STATE.last_check_ts = _now_ts()
        _UCNRR_STATE.last_status = "online" if health["alive"] else "unhealthy"
        _UCNRR_STATE.last_reason = health["reason"]

        if health["alive"] and health["llm_configured"]:
            # UCNRR is healthy, reset backoff
            if _UCNRR_STATE.backoff_level > 0:
                stack_log("devx", "INFO", "ucnrr_online", "UCNRR recovered", health)
                _UCNRR_STATE.backoff_level = 0
            continue

        # UCNRR is unhealthy
        stack_log("devx", "WARN", "ucnrr_unhealthy", f"UCNRR unhealthy: {health['reason']}", health)

        # Check restart cap
        if _check_restart_cap():
            if not _UCNRR_STATE.restart_capped:
                _UCNRR_STATE.restart_capped = True
                _UCNRR_STATE.cap_expires_ts = _now_ts() + RESTART_CAP_WINDOW_SEC
                stack_log(
                    "devx",
                    "ERROR",
                    "ucnrr_cap",
                    f"UCNRR restart capped ({RESTART_CAP_COUNT} restarts in {RESTART_CAP_WINDOW_SEC}s)",
                    {
                        "cap_count": RESTART_CAP_COUNT,
                        "window_sec": RESTART_CAP_WINDOW_SEC,
                        "expires_at": datetime.fromtimestamp(_UCNRR_STATE.cap_expires_ts, tz=timezone.utc).isoformat(),
                    },
                )
            continue

        # Apply backoff before restart
        backoff_delay = _get_backoff_delay()
        stack_log("devx", "INFO", "ucnrr_backoff", f"Waiting {backoff_delay}s before restart", {"backoff_sec": backoff_delay})
        await asyncio.sleep(backoff_delay)

        # Attempt restart
        result = ensure_ucnrr({"force_restart": True})
        _record_restart()
        _UCNRR_STATE.backoff_level = min(_UCNRR_STATE.backoff_level + 1, len(BACKOFF_SCHEDULE) - 1)

        stack_log("devx", "INFO", "ucnrr_restart", f"UCNRR restart attempt: {result['status']}", result)


def get_ucnrr_status() -> Dict[str, Any]:
    """
    Get current UCNRR status for API.

    Returns:
    {
        alive: bool,
        llm_configured: bool,
        reason: str,
        restarts_last_10m: int,
        restart_capped: bool,
        backoff_sec_remaining: int,
        last_check: str,
        pid: int,
    }
    """
    health = check_ucnrr()
    now = _now_ts()
    cutoff = now - RESTART_CAP_WINDOW_SEC
    recent_restarts = [ts for ts in _UCNRR_STATE.restart_timestamps if ts >= cutoff]

    backoff_remaining = 0
    if _UCNRR_STATE.last_check_ts and not health["alive"]:
        elapsed = now - _UCNRR_STATE.last_check_ts
        backoff_remaining = max(0, _get_backoff_delay() - int(elapsed))

    return {
        "alive": health["alive"],
        "llm_configured": health["llm_configured"],
        "reason": health["reason"],
        "restarts_last_10m": len(recent_restarts),
        "restart_capped": _UCNRR_STATE.restart_capped,
        "backoff_sec_remaining": backoff_remaining,
        "last_check": _now_iso() if _UCNRR_STATE.last_check_ts else None,
        "pid": _UCNRR_STATE.pid,
    }
