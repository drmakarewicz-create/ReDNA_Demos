"""
Stack lifecycle management endpoints for CP++ DevX Bootstrap.

This module orchestrates health aggregation, diagnostics, restarts,
port reassignment, self-tests, and log access across the Core, UCNRR,
and DevX backend services. The implementation keeps side effects
thread-safe by delegating blocking operations to background threads.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

try:
    from cpplusplus.ports import find_free_port, who_listens
except Exception:  # pragma: no cover - fallback for environments without cpplusplus
    find_free_port = None

    def who_listens(_: int) -> List[Dict[str, Any]]:
        return []


# Paths
BACKEND_ROOT = Path(__file__).resolve().parent
DEVX_ROOT = BACKEND_ROOT.parent
PROJECT_ROOT = DEVX_ROOT.parent
REPO_ROOT = PROJECT_ROOT.parent
RUN_DIR = (REPO_ROOT / ".run").resolve()
LOG_DIR = (RUN_DIR / "logs").resolve()
ENV_FILE = (REPO_ROOT / ".env").resolve()

RUN_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_py_path(existing: Optional[str]) -> str:
    repo_path = str(REPO_ROOT)
    if not existing:
        return repo_path
    paths = existing.split(os.pathsep)
    if repo_path in paths:
        return existing
    return os.pathsep.join([repo_path, existing])


def _tail_lines(path: Path, limit: int) -> List[str]:
    if not path.exists():
        return []
    lines: deque[str] = deque(maxlen=limit)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            lines.append(line.rstrip("\n"))
    return list(lines)


def _tail_json(path: Path, limit: int) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for raw in _tail_lines(path, limit):
        text = raw.strip()
        if not text:
            continue
        try:
            entry = json.loads(text)
            if isinstance(entry, dict):
                entries.append(entry)
                continue
        except json.JSONDecodeError:
            pass
        entries.append({"raw": text})
    return entries


def _update_env_var(key: str, value: str) -> None:
    """Update or append *key* in the root .env file."""
    lines: List[str] = []
    found = False
    if ENV_FILE.exists():
        with ENV_FILE.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")
    with ENV_FILE.open("w", encoding="utf-8") as handle:
        handle.writelines(lines)


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
    except PermissionError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

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


def _current_port(env_key: str, fallback: int) -> int:
    raw = os.getenv(env_key)
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return fallback


def _compose_health_url(port: int, path: str) -> str:
    base = f"http://127.0.0.1:{port}"
    return base + (path if path.startswith("/") else f"/{path}")


def _fallback_find_port(start: int, end: int) -> Optional[int]:
    if start > end:
        start, end = end, start
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    return None


@dataclass(slots=True)
class ServiceDefinition:
    key: Literal["core", "ucnrr", "devx"]
    display_name: str
    env_var: str
    default_port: int
    uvicorn_app: str
    health_path: str = "/health"
    factory: bool = False
    cwd: Path = field(default=REPO_ROOT)
    restart_label: str = field(default="")
    extra_args: Sequence[str] = field(default_factory=tuple)
    python_path: str = field(default_factory=lambda: sys.executable)

    pid_file: Path = field(init=False)
    log_file: Path = field(init=False)
    legacy_log_file: Path = field(init=False)

    def __post_init__(self) -> None:
        self.pid_file = RUN_DIR / f"{self.key}.pid"
        self.log_file = LOG_DIR / f"{self.key}.jsonl"
        self.legacy_log_file = RUN_DIR / f"{self.key}.log"
        if not self.restart_label:
            self.restart_label = self.key
        self.python_path = sys.executable

    @property
    def port(self) -> int:
        return _current_port(self.env_var, self.default_port)

    def build_command(self, port: int) -> List[str]:
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            self.uvicorn_app,
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ]
        if self.factory:
            cmd.append("--factory")
        cmd.extend(self.extra_args)
        return cmd

    def resolve_log_path(self) -> Path:
        if self.log_file.exists():
            return self.log_file
        if self.legacy_log_file.exists():
            return self.legacy_log_file
        return self.log_file


SERVICES: Dict[str, ServiceDefinition] = {
    "core": ServiceDefinition(
        key="core",
        display_name="Core API",
        env_var="CORE_PORT",
        default_port=8000,
        uvicorn_app="ReDNACoreDemo.core.api:build_app",
        factory=True,
        extra_args=("--log-level", "info"),
    ),
    "ucnrr": ServiceDefinition(
        key="ucnrr",
        display_name="UCNRR Engine",
        env_var="UCNRR_PORT",
        default_port=8011,
        uvicorn_app="UCN_RR_Demo.ucnrr_app:app",
        cwd=REPO_ROOT / "UCN_RR_Demo",
    ),
    "devx": ServiceDefinition(
        key="devx",
        display_name="DevX Backend",
        env_var="DEVX_BACKEND_PORT",
        default_port=8100,
        uvicorn_app="ReDNACoreDemo.devx.backend.api:app",
        extra_args=("--log-level", "info"),
    ),
}


class ServiceStatus(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    status: Literal["healthy", "degraded", "down"]
    port: int
    health: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    last_check: str
    version: Optional[str] = None
    python: Optional[str] = None


class StackStatusResponse(BaseModel):
    services: List[ServiceStatus]
    timestamp: str


class DiagnoseRequest(BaseModel):
    service: Literal["core", "ucnrr", "devx"]


class ListenerInfo(BaseModel):
    pid: int
    cmd: str


class DiagnoseResponse(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    port: int
    port_available: bool
    listeners: List[ListenerInfo]
    process_running: bool
    pid: Optional[int]
    log_file_exists: bool
    last_log_entry: Optional[Dict[str, Any]] = None


class RestartRequest(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    port: int = Field(..., ge=1, le=65535)


class RestartResponse(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    status: Literal["started", "failed"]
    port: int
    pid: Optional[int]
    health_check: Literal["passed", "failed"]
    startup_logs: List[Dict[str, Any]]
    last_health: Optional[Dict[str, Any]] = None


class ChangePortRequest(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    new_port: Optional[int] = Field(None, ge=1, le=65535)

    @field_validator("new_port")
    def _validate_port(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not (1 <= value <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return value


class ChangePortResponse(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    old_port: int
    new_port: int
    status: Literal["restarted", "error"]
    config_updated: bool


class LogEntry(BaseModel):
    ts: Optional[str] = None
    level: Optional[str] = None
    event: Optional[str] = None
    message: Optional[str] = None
    raw: Optional[str] = None
    rest: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "LogEntry":
        known = {key: payload.get(key) for key in ("ts", "timestamp", "time")}
        ts = next((value for value in known.values() if isinstance(value, str)), None)
        level = payload.get("level") or payload.get("levelname")
        event = payload.get("event") or payload.get("msg") or payload.get("message")
        message = payload.get("message") or payload.get("detail")
        rest = {k: v for k, v in payload.items() if k not in {"ts", "timestamp", "time", "level", "levelname", "event", "msg", "message", "detail"}}
        return cls(ts=ts, level=level, event=event, message=message, rest=rest)


class LogsResponse(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    log_file: str
    total_lines: int
    lines: List[LogEntry]


class SelfTestResult(BaseModel):
    service: Literal["core", "ucnrr", "devx"]
    passed: bool
    details: Dict[str, Any]
    test: str


router = APIRouter(prefix="/stack", tags=["stack"])


async def _probe_service(service: ServiceDefinition) -> ServiceStatus:
    port = service.port
    url = _compose_health_url(port, service.health_path)
    timestamp = _now_iso()
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            response = await client.get(url)
            payload = response.json()
            reported_status = str(payload.get("status", "")).lower()
            service_state: Literal["healthy", "degraded", "down"]
            if response.status_code != 200:
                service_state = "down"
            else:
                service_state = "healthy" if reported_status in {"healthy", "ok", "green"} else "degraded"
                if service.key == "core" and payload.get("rr_mode") == "fallback":
                    service_state = "degraded"
            return ServiceStatus(
                service=service.key,
                status=service_state,
                port=port,
                health=payload,
                last_check=timestamp,
                version=str(payload.get("version")) if payload.get("version") is not None else None,
                python=str(payload.get("python") or service.python_path),
            )
        except Exception as exc:
            return ServiceStatus(
                service=service.key,
                status="down",
                port=port,
                error=str(exc),
                last_check=timestamp,
                python=service.python_path,
            )


@router.get("/status", response_model=StackStatusResponse)
async def get_stack_status() -> StackStatusResponse:
    snapshots = await asyncio.gather(*[_probe_service(service) for service in SERVICES.values()])
    return StackStatusResponse(services=list(snapshots), timestamp=_now_iso())


def _listeners_for(service: ServiceDefinition, port: int) -> List[ListenerInfo]:
    raw_entries = who_listens(port) if callable(who_listens) else []
    seen: Dict[int, ListenerInfo] = {}
    for entry in raw_entries:
        pid = int(entry.get("pid", 0))
        if pid <= 0:
            continue
        cmd = str(entry.get("cmd", "")).strip() or service.display_name
        seen[pid] = ListenerInfo(pid=pid, cmd=cmd)
    return list(seen.values())


def _read_pid(service: ServiceDefinition) -> Optional[int]:
    if not service.pid_file.exists():
        return None
    try:
        raw = service.pid_file.read_text(encoding="utf-8").strip()
        return int(raw)
    except (ValueError, OSError):
        return None


def _last_log_entry(service: ServiceDefinition) -> Optional[Dict[str, Any]]:
    entries = _tail_json(service.resolve_log_path(), 1)
    return entries[0] if entries else None


@router.post("/diagnose", response_model=DiagnoseResponse)
async def post_diagnose(request: DiagnoseRequest) -> DiagnoseResponse:
    service = SERVICES[request.service]
    port = service.port
    listeners = await asyncio.to_thread(_listeners_for, service, port)
    port_available = len(listeners) == 0
    pid = await asyncio.to_thread(_read_pid, service)
    running = pid is not None and _pid_alive(pid)
    log_exists = service.resolve_log_path().exists()
    last_log = await asyncio.to_thread(_last_log_entry, service)
    return DiagnoseResponse(
        service=service.key,
        port=port,
        port_available=port_available,
        listeners=listeners,
        process_running=running,
        pid=pid if running else None,
        log_file_exists=log_exists,
        last_log_entry=last_log,
    )


async def _kill_service(service: ServiceDefinition) -> Optional[int]:
    pid = await asyncio.to_thread(_read_pid, service)
    if pid and _pid_alive(pid):
        success = await asyncio.to_thread(_kill_pid, pid)
        if success:
            try:
                service.pid_file.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            return pid
    return None


def _start_service_sync(service: ServiceDefinition, port: int) -> int:
    service.pid_file.parent.mkdir(parents=True, exist_ok=True)
    log_path = service.resolve_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env[service.env_var] = str(port)
    env["PYTHONPATH"] = _default_py_path(env.get("PYTHONPATH"))

    # Set UCNRR_BASE for Core service so it can check UCNRR health
    if service.key == "core":
        ucnrr_port = SERVICES["ucnrr"].port
        env["UCNRR_BASE"] = f"http://127.0.0.1:{ucnrr_port}"

    cmd = service.build_command(port)

    service.python_path = cmd[0]

    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            cmd,
            cwd=service.cwd,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )

    service.pid_file.write_text(str(process.pid), encoding="utf-8")
    return process.pid


async def _start_service(service: ServiceDefinition, port: int) -> int:
    return await asyncio.to_thread(_start_service_sync, service, port)


async def _wait_for_health(service: ServiceDefinition, port: int, attempts: int = 10, delay: float = 1.0) -> Dict[str, Any]:
    url = _compose_health_url(port, service.health_path)
    async with httpx.AsyncClient(timeout=2.0) as client:
        last_payload: Dict[str, Any] = {}
        for _ in range(attempts):
            try:
                response = await client.get(url)
                last_payload = response.json()
                if response.status_code == 200:
                    return last_payload
            except Exception:
                pass
            await asyncio.sleep(delay)
        return last_payload


@router.post("/restart", response_model=RestartResponse)
async def post_restart(request: RestartRequest) -> RestartResponse:
    service = SERVICES[request.service]
    port = request.port

    await _kill_service(service)
    pid = await _start_service(service, port)
    health_payload = await _wait_for_health(service, port)
    health_check = "passed" if health_payload.get("status") in {"healthy", "ok", "green"} else "failed"
    startup_logs = await asyncio.to_thread(_tail_json, service.resolve_log_path(), 20)
    return RestartResponse(
        service=service.key,
        status="started" if pid else "failed",
        port=port,
        pid=pid,
        health_check=health_check,
        startup_logs=startup_logs,
        last_health=health_payload or None,
    )


@router.post("/change_port", response_model=ChangePortResponse)
async def post_change_port(request: ChangePortRequest) -> ChangePortResponse:
    service = SERVICES[request.service]
    old_port = service.port
    port = request.new_port

    if port is None:
        if find_free_port:
            port = find_free_port(8000, 8099) if service.key == "core" else find_free_port(8010, 8199)
        else:
            port = _fallback_find_port(8000, 8099) if service.key == "core" else _fallback_find_port(8010, 8199)
    if port is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No free port found in expected range.")

    _update_env_var(service.env_var, str(port))
    os.environ[service.env_var] = str(port)

    restart_result = await post_restart(RestartRequest(service=service.key, port=port))
    status_flag: Literal["restarted", "error"] = "restarted" if restart_result.status == "started" else "error"
    return ChangePortResponse(
        service=service.key,
        old_port=old_port,
        new_port=port,
        status=status_flag,
        config_updated=True,
    )


async def _selftest_core(service: ServiceDefinition) -> SelfTestResult:
    port = service.port
    base = f"http://127.0.0.1:{port}"
    payload = {
        "user_id": "SELFTEST_USER",
        "persona": "head_coach",
        "text": "I have blue eyes",
        "client_ts": int(time.time() * 1000),
    }
    async with httpx.AsyncClient(timeout=6.0) as client:
        response = await client.post(f"{base}/ui/chat/send", json=payload)
        data = response.json()
    evidence = json.dumps(data, default=str)
    passed = "PaDNA.EyeDNA.IrisColor" in evidence
    return SelfTestResult(service="core", passed=passed, details=data, test="blue_eyes_chat")


async def _selftest_ucnrr(service: ServiceDefinition) -> SelfTestResult:
    port = service.port
    async with httpx.AsyncClient(timeout=4.0) as client:
        response = await client.get(f"http://127.0.0.1:{port}/ucnrr/selftest")
        data = response.json()
    passed = bool(data.get("ok")) and float(data.get("ucn", 0)) > 0.5
    return SelfTestResult(service="ucnrr", passed=passed, details=data, test="selftest_endpoint")


async def _selftest_devx(service: ServiceDefinition) -> SelfTestResult:
    port = service.port
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.get(_compose_health_url(port, service.health_path))
        data = response.json()
    passed = response.status_code == 200 and data.get("status") == "healthy"
    return SelfTestResult(service="devx", passed=passed, details=data, test="health_check")


SELFTEST_HANDLERS = {
    "core": _selftest_core,
    "ucnrr": _selftest_ucnrr,
    "devx": _selftest_devx,
}


@router.get("/selftest/{service}", response_model=SelfTestResult)
async def get_selftest(service: Literal["core", "ucnrr", "devx"]) -> SelfTestResult:
    handler = SELFTEST_HANDLERS[service]
    target = SERVICES[service]
    try:
        return await handler(target)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


def _filter_log_entries(entries: Iterable[Dict[str, Any]], level: Optional[str]) -> List[LogEntry]:
    filtered: List[LogEntry] = []
    level_upper = level.upper() if level else None
    for entry in entries:
        if isinstance(entry, dict):
            model = LogEntry.from_payload(entry)
        else:
            model = LogEntry(raw=str(entry))
        if level_upper and model.level and model.level.upper() != level_upper:
            continue
        filtered.append(model)
    return filtered


@router.get("/logs/{service}", response_model=LogsResponse)
async def get_logs(
    service: Literal["core", "ucnrr", "devx"],
    lines: int = Query(100, ge=1, le=500),
    level: Optional[str] = Query(None),
) -> LogsResponse:
    target = SERVICES[service]
    log_path = target.resolve_log_path()
    entries = await asyncio.to_thread(_tail_json, log_path, lines)
    filtered = _filter_log_entries(entries, level)
    return LogsResponse(
        service=service,
        log_file=str(log_path),
        total_lines=len(filtered),
        lines=filtered,
    )
