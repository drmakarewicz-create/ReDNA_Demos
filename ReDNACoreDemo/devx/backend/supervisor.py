"""
DevX Supervisor
===============

Lightweight process supervision for Core and UCNRR services.
Controls restarts, tracks rate limits, and records restart history.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, List, Optional, Tuple

from ReDNACoreDemo.core.logutil import stack_log

ServiceName = Literal["core", "ucnrr"]

REPO_ROOT = Path(__file__).resolve().parents[3]
REDNA_ROOT = Path(os.getenv("REDNA_HOME", Path.home() / ".redna")).expanduser()
SUPERVISOR_DIR = Path(os.getenv("REDNA_SUPERVISOR_DIR", str(REDNA_ROOT / "devx_supervisor"))).expanduser()
STATE_PATH = SUPERVISOR_DIR / "state.json"
LOG_DIR = SUPERVISOR_DIR / "logs"

SUPERVISOR_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_EXECUTABLE = sys.executable

DEFAULT_CONFIG = {
    "core": {
        "env_var": "CORE_PORT",
        "default_port": 8001,
        "module": "ReDNACoreDemo.core.api:app",
        "cwd": str(REPO_ROOT),
    },
    "ucnrr": {
        "env_var": "UCNRR_PORT",
        "default_port": 8011,
        "module": "UCN_RR_Demo.ucnrr_app:app",
        "cwd": str(REPO_ROOT),
    },
}

STATE_LOCK = threading.Lock()


def _now_ts() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_py_path(existing: Optional[str]) -> str:
    repo_path = str(REPO_ROOT)
    if not existing:
        return repo_path
    paths = existing.split(os.pathsep)
    if repo_path in paths:
        return existing
    return os.pathsep.join([repo_path, existing])


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def restart_grace_seconds() -> int:
    return max(1, _int_env("DEVX_RESTART_GRACE_SEC", 60))


def max_restarts_per_hour() -> int:
    return max(1, _int_env("DEVX_MAX_RESTARTS_PER_HOUR", 6))


def _service_log_path(service: ServiceName) -> Path:
    return LOG_DIR / f"{service}.stdout.log"


def _service_port(service: ServiceName) -> int:
    config = DEFAULT_CONFIG[service]
    return _int_env(config["env_var"], config["default_port"])


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _kill_pid(pid: int, timeout: float = 5.0) -> bool:
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


def _load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        try:
            with STATE_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    services = data.get("services", {})
    for name in ("core", "ucnrr"):
        services.setdefault(name, {})
        services[name].setdefault("pid", None)
        services[name].setdefault("last_restart", None)
        services[name].setdefault("restart_timestamps", [])
    data["services"] = services
    data.setdefault("history", [])
    return data


def _save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def _history_entry(service: ServiceName, status: str, reason: str, force: bool, pid: Optional[int]) -> Dict[str, Any]:
    return {
        "ts": _now_iso(),
        "service": service,
        "status": status,
        "reason": reason,
        "force": force,
        "pid": pid,
    }


def _append_history(state: Dict[str, Any], entry: Dict[str, Any], limit: int = 200) -> None:
    history: List[Dict[str, Any]] = state.setdefault("history", [])
    history.append(entry)
    if len(history) > limit:
        del history[: len(history) - limit]


def _record_restart_timestamp(metadata: Dict[str, Any], ts: float) -> None:
    timestamps: List[float] = metadata.setdefault("restart_timestamps", [])
    timestamps.append(ts)
    cutoff = ts - 3600.0
    metadata["restart_timestamps"] = [value for value in timestamps if value >= cutoff]


def _rate_limited(metadata: Dict[str, Any]) -> bool:
    now = _now_ts()
    timestamps = metadata.get("restart_timestamps", [])
    metadata["restart_timestamps"] = [value for value in timestamps if value >= now - 3600.0]
    return len(metadata["restart_timestamps"]) >= max_restarts_per_hour()


def _start_service_locked(service: ServiceName, state: Dict[str, Any], reason: str) -> int:
    config = DEFAULT_CONFIG[service]
    port = _service_port(service)

    env = os.environ.copy()
    env[config["env_var"]] = str(port)
    env["PYTHONPATH"] = _default_py_path(env.get("PYTHONPATH"))
    if service == "core":
        env.setdefault("UCNRR_BASE", f"http://127.0.0.1:{_service_port('ucnrr')}")

    cmd = [
        PYTHON_EXECUTABLE,
        "-m",
        "uvicorn",
        config["module"],
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--reload",
    ]

    log_path = _service_log_path(service)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    process = subprocess.Popen(
        cmd,
        cwd=config["cwd"],
        env=env,
        stdout=log_path.open("ab"),
        stderr=subprocess.STDOUT,
    )

    metadata = state["services"][service]
    metadata["pid"] = int(process.pid)
    metadata["last_restart"] = _now_iso()
    _record_restart_timestamp(metadata, _now_ts())

    entry = _history_entry(service, "restarted", reason, False, int(process.pid))
    _append_history(state, entry)

    stack_log(
        "devx",
        "INFO",
        "restart_event",
        f"{service} started",
        {"service": service, "reason": reason, "pid": process.pid, "port": port},
    )
    return int(process.pid)


def ensure_process(service: ServiceName) -> Optional[int]:
    with STATE_LOCK:
        state = _load_state()
        metadata = state["services"][service]
        pid = metadata.get("pid")
        if pid and _pid_alive(pid):
            return int(pid)
        pid = _start_service_locked(service, state, reason="ensure_process")
        _save_state(state)
        return pid


def _stop_service_locked(service: ServiceName, state: Dict[str, Any]) -> None:
    metadata = state["services"][service]
    pid = metadata.get("pid")
    if pid and _pid_alive(pid):
        if _kill_pid(int(pid)):
            stack_log(
                "devx",
                "INFO",
                "restart_event",
                f"{service} stopped",
                {"service": service, "pid": pid},
            )
    metadata["pid"] = None


def _restart_service_locked(
    service: ServiceName,
    state: Dict[str, Any],
    reason: str,
    force: bool,
) -> Tuple[str, Optional[int]]:
    metadata = state["services"][service]
    now = _now_ts()
    if not force and _rate_limited(metadata):
        entry = _history_entry(service, "rate_limited", reason, force, metadata.get("pid"))
        _append_history(state, entry)
        stack_log(
            "devx",
            "WARN",
            "restart_event",
            f"{service} restart skipped (rate limited)",
            {"service": service, "reason": reason, "force": force},
        )
        return "rate_limited", metadata.get("pid")

    _stop_service_locked(service, state)
    pid = _start_service_locked(service, state, reason=reason)
    return "restarted", pid


def restart_services(
    services: Iterable[ServiceName],
    reason: str,
    force: bool,
    *,
    eligible_services: Iterable[ServiceName],
) -> Dict[str, Any]:
    with STATE_LOCK:
        state = _load_state()
        restarted: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        rate_limited: List[Dict[str, Any]] = []

        eligible_set = set(eligible_services)

        for service in services:
            if service not in DEFAULT_CONFIG:
                skipped.append({"service": service, "status": "unknown_service"})
                continue

            if not force and service not in eligible_set:
                skipped.append({"service": service, "status": "not_eligible"})
                continue

            status, pid = _restart_service_locked(service, state, reason, force)
            record = {"service": service, "status": status, "pid": pid}
            if status == "restarted":
                restarted.append(record)
            elif status == "rate_limited":
                rate_limited.append(record)
            else:
                skipped.append(record)

        _save_state(state)

        history = list(reversed(state.get("history", [])))[:50]

    return {
        "force": force,
        "reason": reason,
        "grace_seconds": restart_grace_seconds(),
        "restarted": restarted,
        "skipped": skipped,
        "rate_limited": rate_limited,
        "history": history,
    }


def get_restart_history(limit: int = 50) -> List[Dict[str, Any]]:
    with STATE_LOCK:
        state = _load_state()
        history = list(reversed(state.get("history", [])))
    return history[:limit]


def get_rate_limit_status() -> Dict[str, Dict[str, Any]]:
    with STATE_LOCK:
        state = _load_state()
        status: Dict[str, Dict[str, Any]] = {}
        for service, meta in state["services"].items():
            timestamps = meta.get("restart_timestamps", [])
            now = _now_ts()
            recent = [value for value in timestamps if value >= now - 3600.0]
            remaining = max(0, max_restarts_per_hour() - len(recent))
            status[service] = {
                "rate_limited": len(recent) >= max_restarts_per_hour(),
                "recent_restarts": len(recent),
                "remaining": remaining,
            }
    return status
