"""Control Panel Plus Plus — orchestrates Core, React, and Streamlit shells."""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
import signal
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, NamedTuple, Optional, Tuple

import requests

import streamlit as st

from cpplusplus import envstore, services, ports

# Import DevX bootstrap helpers
try:
    from ReDNACoreDemo.core.devx_bootstrap import (
        devx_backend_health,
        devx_ui_health,
        ensure_devx_requirements_commands,
        start_devx_backend,
        start_devx_ui,
        stop_devx,
        load_last_ui_port,
    )
    DEVX_BOOTSTRAP_AVAILABLE = True
except ImportError:
    DEVX_BOOTSTRAP_AVAILABLE = False
    load_last_ui_port = lambda: None  # type: ignore


def safe_rerun() -> None:
    try:
        st.rerun()
    except AttributeError:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()

ROOT = Path(__file__).parent.resolve()
SESSION_ENV_KEY = "_cpplusplus_env"
SESSION_SERVICES_KEY = "_cpplusplus_services"
SESSION_HEALTH_KEY = "_cpplusplus_health"
SESSION_LOG_PAUSE_KEY = "_cpplusplus_log_pause"
SESSION_TESTS_KEY = "_cpplusplus_tests"
SESSION_CONFLICTS_KEY = "_cpplusplus_port_conflicts"
SESSION_START_LOCK_KEY = "_cpplusplus_starting"
SESSION_ENV_DIRTY_KEY = "_cpplusplus_env_dirty"
SESSION_ACTION_RESULT_KEY = "_cpplusplus_action_result"
SESSION_PENDING_AUTO_OPEN_KEY = "_cpplusplus_pending_auto_open"
SESSION_CHAT_PROBE_KEY = "_cpplusplus_chat_probe"
SESSION_PROVIDER_VALIDATION_KEY = "_cpplusplus_provider_validation"
SESSION_PROFILES_KEY = "_cpplusplus_profiles"
SESSION_SELECTED_PROFILE_KEY = "_cpplusplus_selected_profile"
SESSION_PROFILE_NOTICE_KEY = "_cpplusplus_profile_notice"
SESSION_ACTIVE_USER_KEY = "_cpplusplus_active_user"
SESSION_ACTIVE_USER_INPUT_KEY = "_cpplusplus_active_user_input"
SESSION_DETECTED_PORTS_KEY = "_cpplusplus_detected_ports"
SESSION_HEALTH_PENDING_KILL_KEY = "_cpplusplus_pending_kill"
SESSION_HEALTH_NOTICE_KEY = "_cpplusplus_health_notice"
SESSION_FORCE_ROOT_VENV_KEY = "_cpplusplus_force_root_venv"
DEFAULT_ACTIVE_USER = "TEST"

SERVICE_CORE = "core"
SERVICE_REACT = "react"
SERVICE_STREAMLIT = "streamlit"
SERVICE_UCNRR = "ucnrr"
SERVICE_ROUTER = "router"
SERVICE_TEST_PLAYWRIGHT = "test_playwright"
SERVICE_TEST_CI = "test_ci"
SERVICE_DEV_EXPLORER = "dev_explorer"

CORE_PORT_RANGE = (8015, 8020)
REACT_PORT_RANGE = (3000, 3005)
REACT_DEFAULT_PORT = 3001
STREAMLIT_PORT_RANGE = (8501, 8515)
STREAMLIT_DEFAULT_PORT = 8510
STREAMLIT_FALLBACK_PORTS = [port for port in range(8503, 8516) if port != 8502]

SERVICE_PORT_KEYS = {
    SERVICE_CORE: "core_port",
    SERVICE_REACT: "react_port",
    SERVICE_STREAMLIT: "streamlit_port",
    SERVICE_UCNRR: "ucnrr_port",
}

FRONTEND_FLAG_KEYS = {"avatar", "avatarDebug"}

REACT_LOCAL_URL_RE = re.compile(r"Local:\s+https?://(?:localhost|127\.0\.0\.1):(\d+)")
REACT_PORT_BUMP_RE = re.compile(r"Port\s+(\d+)\s+is in use, trying\s+(\d+)\s+instead", re.IGNORECASE)
REACT_PORT_SCAN_RANGE = list(range(REACT_PORT_RANGE[0], REACT_PORT_RANGE[1] + 1))

_REACT_WATCHERS: Dict[int, threading.Thread] = {}
_REACT_WATCHERS_LOCK = threading.Lock()


def _repo_root() -> str:
    return str(ROOT)


def _discover_venvs(root: str) -> List[str]:
    candidates: List[str] = []
    for path in glob.glob(os.path.join(root, ".venv")):
        if os.path.isdir(path):
            candidates.append(os.path.abspath(path))
    for path in glob.glob(os.path.join(root, "*", ".venv")):
        if os.path.isdir(path):
            candidates.append(os.path.abspath(path))
    return sorted(set(candidates))


_ROOT_VENV_PATH = os.path.join(_repo_root(), ".venv")
_PY_EXE = os.path.join(_ROOT_VENV_PATH, "bin", "python")
ROOT_VENV_BIN = Path(_PY_EXE)
_ALL_VENVS = _discover_venvs(_repo_root())

if len(_ALL_VENVS) > 1:
    st.warning("Multiple Python venvs found. Defaulting to the **root** `.venv`.", icon="⚠️")

if not os.path.exists(_PY_EXE):
    st.error(f"Root venv python not found at: {_PY_EXE}. Run `scripts/consolidate_venv.sh`.", icon="🛑")


# ---------------------------------------------------------------------------
# Managed process persistence & probing helpers
# ---------------------------------------------------------------------------

STATE_PATH = ROOT / ".cp_state.json"


@dataclass
class ProcInfo:
    name: str
    cmd: List[str]
    pid: int
    port: Optional[int]
    started_at: float
    actual_port: Optional[int] = None


ProcState = Dict[str, ProcInfo]


def _load_state() -> ProcState:
    if not STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    state: ProcState = {}
    if not isinstance(raw, dict):
        return state
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            actual_raw = value.get("actual_port")
            state[key] = ProcInfo(
                name=str(value["name"]),
                cmd=list(value.get("cmd", [])),
                pid=int(value["pid"]),
                port=int(value["port"]) if value.get("port") is not None else None,
                started_at=float(value.get("started_at", time.time())),
                actual_port=int(actual_raw) if actual_raw is not None else None,
            )
        except Exception:
            continue
    return state


def _save_state(state: ProcState) -> None:
    serial = {key: asdict(value) for key, value in state.items()}
    try:
        STATE_PATH.write_text(json.dumps(serial, indent=2), encoding="utf-8")
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _is_port_in_use(port: int) -> bool:
    """Check if a port is in use by attempting to connect."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", port))
        return result == 0


def _pid_on_port(port: int) -> Optional[int]:
    """Get PID of process listening on a port (cross-platform)."""
    commands = [["lsof", "-nti", f":{port}"], ["fuser", "-n", "tcp", str(port)]]
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            tokens = [token.strip() for token in output.split() if token.strip()]
            for token in tokens:
                try:
                    if token.endswith("/tcp"):
                        token = token.split("/")[0]
                    return int(token)
                except ValueError:
                    continue
        except Exception:
            continue
    return None


def _describe_process(pid: int) -> str:
    """Get command line of a process by PID."""
    try:
        output = subprocess.check_output([
            "ps",
            "-o",
            "command=",
            "-p",
            str(pid),
        ], text=True, stderr=subprocess.DEVNULL)
        return output.strip()
    except Exception:
        return ""


def _listener_up(host: str, port: int, path: str = "/", timeout: float = 0.8) -> Tuple[bool, Optional[int]]:
    try:
        path = path or "/"
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"http://{host}:{port}{path}"
        response = requests.get(url, timeout=timeout)
        if 200 <= response.status_code < 400:
            return True, response.status_code
        return False, response.status_code
    except Exception:
        return False, None


def _find_first_open_port(candidates: List[int], path: str = "/") -> Optional[int]:
    for candidate in candidates:
        up, _ = _listener_up("127.0.0.1", candidate, path=path, timeout=0.5)
        if up:
            return candidate
    return None


def kill_port(port: int) -> None:
    """Best-effort kill anything bound to a port."""
    try:
        # Use lsof on macOS, fuser on Linux
        if sys.platform == "darwin":
            cmd = f"lsof -ti :{port} | xargs kill -9"
        else:
            cmd = f"fuser -k {port}/tcp"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait(timeout=3)
    except Exception:
        pass


def _my_streamlit_pid() -> int:
    return os.getpid()


def _my_streamlit_port() -> Optional[int]:
    for key in ("STREAMLIT_SERVER_PORT", "PORT"):
        value = os.getenv(key)
        if value and value.isdigit():
            try:
                return int(value)
            except ValueError:
                continue
    return None


def _ensure_state(key: str, initial: str) -> str:
    """Initialize a session state entry once without fighting widget defaults."""

    if key not in st.session_state or st.session_state.get(key) is None:
        st.session_state[key] = initial
    return st.session_state[key]


def _probe_health(url: str | None, timeout: float = 2.0) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Return (ok, payload, error). Safe on empty/malformed URLs."""
    if not url or not isinstance(url, str):
        return False, None, "no health url"

    try:
        # Normalize: if passed just a port (digits), make it a default health URL
        normalized_url = url.strip()
        if normalized_url.isdigit():
            normalized_url = f"http://127.0.0.1:{normalized_url}/health"

        # Add scheme if missing, e.g., "127.0.0.1:8015/health"
        if not normalized_url.startswith("http://") and not normalized_url.startswith("https://"):
            normalized_url = f"http://{normalized_url.lstrip('/')}"

        response = requests.get(normalized_url, timeout=timeout)
        if 200 <= response.status_code < 300:
            try:
                payload = response.json() if response.content else {}
            except ValueError:
                payload = {}
            return True, payload, None
        return False, None, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, None, str(exc)


def check_health(url: str | None, timeout: float = 2.0) -> Tuple[bool, str]:
    """
    Legacy wrapper for _probe_health(). Returns (ok, message).
    Safe on empty/malformed URLs.
    """
    ok, payload, error = _probe_health(url, timeout)
    if ok:
        msg = "OK"
        # Enrich with holistic info if available
        if payload and isinstance(payload, dict):
            hol = payload.get("holistic")
            if isinstance(hol, dict):
                msg += (
                    f" — holistic enabled={hol.get('enabled')} "
                    f"rules={hol.get('rules_loaded')} "
                    f"baselines={hol.get('baselines_loaded')}"
                )
            # Enrich with curiosity status if available (from Core features)
            features = payload.get("features")
            if isinstance(features, dict) and "curiosity_enabled" in features:
                curiosity_on = features.get("curiosity_enabled")
                msg += f" — curiosity={'🟢 ON' if curiosity_on else '🔴 OFF'}"
        return True, msg
    else:
        return False, error or "no response"


def _resolve_core_workdir(config: Dict[str, Any]) -> Path:
    raw = str(config.get("core_workdir") or ROOT)
    try:
        return Path(raw).expanduser().resolve(strict=False)
    except Exception:
        return ROOT


def _core_start_command_list(config: Dict[str, Any]) -> Optional[List[str]]:
    raw = str(config.get("core_start_command") or "").strip()
    if not raw:
        return None
    try:
        return shlex.split(raw)
    except ValueError:
        return None


def _compose_core_command(port: int, tokens: Optional[List[str]] = None) -> List[str]:
    configured = tokens if tokens else _core_start_command_list(_env())
    if configured:
        args = list(configured)
    else:
        args = ["uvicorn", "ReDNACoreDemo.core.api:build_app", "--factory"]

    interpreter_aliases = {
        sys.executable,
        os.path.basename(sys.executable),
        "python",
        "python3",
        _PY_EXE,
        os.path.basename(_PY_EXE),
    }

    while args and args[0] in interpreter_aliases:
        args.pop(0)

    if not args:
        args = ["uvicorn", "ReDNACoreDemo.core.api:build_app", "--factory"]

    if args[0] == "uvicorn":
        args = ["-m", "uvicorn", *args[1:]]
    elif args[0] != "-m":
        args = ["-m", *args]

    cleaned: List[str] = []
    skip_next = False
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token == "--port":
            skip_next = True
            continue
        cleaned.append(token)

    cleaned.extend(["--port", str(port)])

    if bool(_env().get("CORE_RELOAD")) and "--reload" not in cleaned:
        cleaned.append("--reload")

    force_root = bool(st.session_state.get(SESSION_FORCE_ROOT_VENV_KEY, False))
    python_path = ROOT_VENV_BIN if force_root and ROOT_VENV_BIN.exists() else Path(sys.executable)
    return [str(python_path), *cleaned]


def _resolve_react_workdir(config: Dict[str, Any]) -> Path:
    default = ROOT / "web"
    raw = config.get("react_workdir")
    if not raw:
        return default
    try:
        return Path(str(raw)).expanduser().resolve(strict=False)
    except Exception:
        return default


def _resolve_react_npm(config: Dict[str, Any]) -> Optional[str]:
    raw = str(config.get("react_npm_path") or "").strip()
    if raw:
        return raw
    return shutil.which("npm")


def _update_service_actual_port(name: str, port: Optional[int]) -> None:
    if port is None:
        return
    state = _load_state()
    info = state.get(name)
    if not info:
        return
    if info.actual_port == port:
        return
    info.actual_port = port
    state[name] = info
    _save_state(state)


def _update_react_actual_port(port: int) -> None:
    _update_service_actual_port(SERVICE_REACT, port)


def _parse_frontend_flag_string(raw: str) -> tuple[dict[str, bool], list[str]]:
    flags: dict[str, bool] = {}
    passthrough: list[str] = []
    if not raw:
        return flags, passthrough
    tokens = raw.split(',')
    for token in tokens:
        trimmed = token.strip()
        if not trimmed:
            continue
        if '=' in trimmed:
            key_part, value_part = trimmed.split('=', 1)
            key = key_part.strip()
            normalized_value = value_part.strip().lower()
            enabled = normalized_value in ('', '1', 'true', 'on', 'yes')
        else:
            key = trimmed
            enabled = True
        if key in FRONTEND_FLAG_KEYS:
            flags[key] = enabled
        else:
            passthrough.append(trimmed)
    return flags, passthrough


def _serialize_frontend_flags(flags: dict[str, bool], passthrough: list[str]) -> str:
    tokens: list[str] = [token for token in passthrough if token]
    for key in sorted(FRONTEND_FLAG_KEYS):
        if flags.get(key):
            tokens.append(key)
    return ','.join(tokens)


def _detect_react_port_by_pid(
    pid: int,
    scan_range: List[int],
    configured_port: Optional[int],
) -> Optional[int]:
    candidates = _unique_candidates([configured_port] + scan_range)
    try:
        output = subprocess.check_output(
            [
                "lsof",
                "-Pan",
                "-p",
                str(pid),
                "-iTCP",
                "-sTCP:LISTEN",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        for line in output.splitlines():
            match = re.search(r":(\d+)\b.*\(LISTEN\)", line)
            if match:
                port = int(match.group(1))
                if port in candidates:
                    return port
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        pass

    for candidate in candidates:
        up, _ = _listener_up("127.0.0.1", candidate, path="/")
        if up:
            return candidate
    return None


def _react_port_watcher(service: services.ServiceProcess, configured_port: Optional[int]) -> None:
    pid = service.pid()
    if not pid:
        return
    processed = 0
    port_hint: Optional[int] = None
    start = time.time()
    timeout = 60.0
    try:
        while time.time() - start < timeout:
            if not service.is_running():
                break
            logs = service.logs()
            while processed < len(logs):
                line = logs[processed]
                clean_line = re.sub(r"\x1b\[[0-9;]*m", "", line)
                processed += 1
                local_match = REACT_LOCAL_URL_RE.search(clean_line)
                if local_match:
                    detected = int(local_match.group(1))
                    _update_react_actual_port(detected)
                    return
                bump_match = REACT_PORT_BUMP_RE.search(clean_line)
                if bump_match:
                    try:
                        port_hint = int(bump_match.group(2))
                    except Exception:
                        continue
            time.sleep(0.5)

        if port_hint:
            _update_react_actual_port(port_hint)
            return

        fallback = _detect_react_port_by_pid(pid, REACT_PORT_SCAN_RANGE, configured_port)
        if fallback:
            _update_react_actual_port(fallback)
    finally:
        with _REACT_WATCHERS_LOCK:
            _REACT_WATCHERS.pop(pid, None)


def _ensure_react_port_watcher(service: services.ServiceProcess, configured_port: Optional[int]) -> None:
    pid = service.pid()
    if not pid:
        return
    with _REACT_WATCHERS_LOCK:
        if pid in _REACT_WATCHERS:
            return
        thread = threading.Thread(
            target=_react_port_watcher,
            args=(service, configured_port),
            name="react-port-watcher",
            daemon=True,
        )
        _REACT_WATCHERS[pid] = thread
        thread.start()


# ---------------------------------------------------------------------------
# Service health modelling
# ---------------------------------------------------------------------------

Status = Literal["RUNNING (managed)", "RUNNING (external)", "STOPPED"]


class ServiceHealth(NamedTuple):
    name: str
    status: Status
    pid: Optional[int]
    port: Optional[int]
    url: Optional[str]
    last_checked: float
    note: Optional[str] = None
    configured_port: Optional[int] = None
    actual_port: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None


def _unique_candidates(values: List[Optional[int]]) -> List[int]:
    ordered: List[int] = []
    for value in values:
        if value is None:
            continue
        if value not in ordered:
            ordered.append(value)
    return ordered


def _probe_first(host: str, port: int, paths: List[str]) -> Tuple[bool, Optional[str], Optional[int]]:
    for path in paths:
        up, status = _listener_up(host, port, path=path)
        if up:
            return True, path, status
    return False, None, None


def check_services(env: Optional[Dict[str, Any]] = None) -> Dict[str, ServiceHealth]:
    env_map = dict(env or _env())
    state = _load_state()
    changed = False
    now = time.time()
    results: Dict[str, ServiceHealth] = {}

    host = "127.0.0.1"

    def _cleanup(name: str) -> Optional[ProcInfo]:
        nonlocal changed
        info = state.get(name)
        if info and not _pid_alive(info.pid):
            state.pop(name, None)
            changed = True
            return None
        return info

    def _record(health: ServiceHealth) -> None:
        results[health.name] = health

    # Self (Streamlit)
    self_pid = _my_streamlit_pid()
    self_port = _my_streamlit_port()
    self_url = f"http://127.0.0.1:{self_port}" if self_port else None
    _record(
        ServiceHealth(
            name="cpplusplus",
            status="RUNNING (managed)",
            pid=self_pid,
            port=self_port,
            url=self_url,
            last_checked=now,
            note="Self-protected",
        )
    )

    def _evaluate(
        service_name: str,
        env_key: str,
        default_range: Tuple[int, int],
        probe_paths: Optional[List[str]] = None,
        health_paths: Optional[List[str]] = None,
    ) -> None:
        nonlocal changed
        managed = _cleanup(service_name)
        managed_pid = managed.pid if managed else None
        managed_port = managed.port if managed else None
        actual_port = managed.actual_port if managed else None

        env_port_value = env_map.get(env_key)
        try:
            env_port = int(env_port_value) if env_port_value is not None else None
        except Exception:
            env_port = None

        probe_paths = list(probe_paths or [])
        health_paths = list(health_paths or [])
        scan_range = list(range(default_range[0], default_range[1] + 1))

        if (
            service_name == SERVICE_REACT
            and managed
            and managed_pid
            and actual_port is None
        ):
            fallback_port = _detect_react_port_by_pid(
                managed_pid,
                scan_range,
                env_port or managed_port,
            )
            if fallback_port:
                actual_port = fallback_port
                managed.actual_port = fallback_port
                changed = True

        candidates = _unique_candidates([actual_port, managed_port, env_port] + scan_range)

        discovered_port: Optional[int] = None
        discovered_path: Optional[str] = None
        discovered_status: Optional[int] = None
        discovered_payload: Optional[Dict[str, Any]] = None
        health_error: Optional[str] = None

        for candidate in candidates:
            if health_paths:
                for rel_path in health_paths:
                    url = f"http://{host}:{candidate}{rel_path}"
                    ok, payload, err = _probe_health(url)
                    if ok:
                        discovered_port = candidate
                        discovered_payload = payload or {}
                        break
                    health_error = err
                if discovered_port is not None:
                    break
            elif probe_paths:
                ok, path, status_code = _probe_first(host, candidate, probe_paths)
                if ok:
                    discovered_port = candidate
                    discovered_path = path
                    discovered_status = status_code
                    break

        if (
            managed
            and discovered_port is not None
            and discovered_port != actual_port
        ):
            actual_port = discovered_port
            managed.actual_port = discovered_port
            changed = True
        elif discovered_port is not None and not managed:
            actual_port = discovered_port

        url: Optional[str] = None
        if discovered_port is not None:
            if discovered_path and discovered_path not in (None, "") and not health_paths:
                suffix = "" if discovered_path == "/" else discovered_path
                url = f"http://{host}:{discovered_port}{suffix}"
            else:
                url = f"http://{host}:{discovered_port}"
        elif actual_port:
            url = f"http://{host}:{actual_port}"

        status: Status
        note: Optional[str] = None
        pid: Optional[int] = None
        active_port: Optional[int] = None

        if managed and managed_pid:
            pid = managed_pid
            if discovered_port:
                status = "RUNNING (managed)"
                active_port = discovered_port
            else:
                active_port = actual_port or managed_port or env_port
                if _pid_alive(managed_pid):
                    status = "STOPPED"
                    note = "Managed process alive but listener unreachable."
                else:
                    state.pop(service_name, None)
                    changed = True
                    managed = None
                    pid = None
                    status = "STOPPED"
        elif discovered_port:
            status = "RUNNING (external)"
            active_port = discovered_port
        else:
            status = "STOPPED"
            active_port = env_port or managed_port

        if managed:
            state[service_name] = managed

        if status == "RUNNING (managed)" and env_port and active_port and env_port != active_port:
            service_label = service_name.title()
            if service_name == SERVICE_REACT:
                service_label = "React"
            elif service_name == SERVICE_CORE:
                service_label = "Core"
            elif service_name == SERVICE_STREAMLIT:
                service_label = "Streamlit"
            mismatch_note = (
                f"Detected {service_label} on port {active_port}; configured port is {env_port} (use Adopt actual to persist)."
            )
            note = f"{note} {mismatch_note}".strip() if note else mismatch_note
        elif status == "RUNNING (external)" and active_port is not None:
            if service_name == SERVICE_REACT:
                detected_label = "React"
            elif service_name == SERVICE_CORE:
                detected_label = "Core"
            elif service_name == SERVICE_UCNRR:
                detected_label = "UCN/RR"
            elif service_name == SERVICE_STREAMLIT:
                detected_label = "Streamlit"
            else:
                detected_label = service_name.title()
            if env_port and env_port != active_port:
                note = (
                    f"Detected {detected_label} on port {active_port}; configured port is {env_port}."
                )
            else:
                note = f"Detected {detected_label} on port {active_port}."

        if status.startswith("RUNNING") and discovered_status and discovered_status >= 400:
            detail_note = f"HTTP {discovered_status} on {discovered_path or '/'}"
            note = f"{note} {detail_note}".strip() if note else detail_note

        if health_paths and discovered_payload:
            version = str(discovered_payload.get("version") or "").strip()
            timestamp = str(discovered_payload.get("timestamp") or "").strip()
            pieces = [f"v{version}" for version in [version] if version]
            if timestamp:
                pieces.append(timestamp)
            if pieces:
                health_line = "Health " + " · ".join(pieces)
                note = f"{health_line}" if not note else f"{health_line} — {note}"
        elif health_paths and health_error and status != "RUNNING (managed)" and status != "RUNNING (external)":
            error_line = f"Health probe failed: {health_error}"
            note = f"{note} {error_line}".strip() if note else error_line

        actual_for_health = actual_port
        if status == "RUNNING (external)" and discovered_port:
            actual_for_health = discovered_port

        _record(
            ServiceHealth(
                name=service_name,
                status=status,
                pid=pid,
                port=active_port,
                url=url,
                last_checked=now,
                note=note,
                configured_port=env_port,
                actual_port=actual_for_health,
                payload=discovered_payload,
            )
        )

    _evaluate(SERVICE_REACT, "react_port", REACT_PORT_RANGE, ["/api/health", "/"])
    _evaluate(SERVICE_CORE, "core_port", CORE_PORT_RANGE, [], ["/health"])
    _evaluate(SERVICE_STREAMLIT, "streamlit_port", STREAMLIT_PORT_RANGE, ["/_stcore/health", "/"])
    _evaluate(SERVICE_UCNRR, "ucnrr_port", (8011, 8025), [], ["/api/health", "/health"])

    if changed:
        _save_state(state)

    return results


def _refresh_health() -> Dict[str, ServiceHealth]:
    results = check_services()
    st.session_state[SESSION_HEALTH_KEY] = results
    detected = {
        name: (health.actual_port or health.port)
        for name, health in results.items()
        if (health.actual_port or health.port) is not None
    }
    st.session_state[SESSION_DETECTED_PORTS_KEY] = detected
    return results


def _format_relative_time(timestamp: float) -> str:
    diff = max(0.0, time.time() - timestamp)
    if diff < 1:
        return "just now"
    if diff < 60:
        return f"{int(diff)}s ago"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


def _render_health_card(health: ServiceHealth, label: str) -> None:
    status_icons = {
        "RUNNING (managed)": "🟢",
        "RUNNING (external)": "🔵",
        "STOPPED": "⚪️",
    }

    with st.container(border=True):
        header_cols = st.columns([3, 1])
        with header_cols[0]:
            st.markdown(f"### {label}")
            emoji = status_icons.get(health.status, "⬜️")
            st.markdown(f"{emoji} **{health.status}**")
            if health.note:
                st.caption(health.note)
        with header_cols[1]:
            st.caption(f"Last checked { _format_relative_time(health.last_checked) }")

        info_cols = st.columns([1, 1, 1, 2])
        info_cols[0].metric("PID", str(health.pid) if health.pid else "—")
        if health.configured_port is not None:
            info_cols[1].metric("Configured", str(health.configured_port))
        else:
            info_cols[1].metric("Port", str(health.port) if health.port else "—")

        detected_label = "Detected" if health.configured_port is not None else "Port"
        if health.actual_port is not None:
            info_cols[2].metric(detected_label, str(health.actual_port))
        else:
            fallback_port = health.port if health.configured_port is not None else None
            info_cols[2].metric(detected_label, str(fallback_port) if fallback_port is not None else "—")

        with info_cols[3]:
            st.markdown("**URL**")
            st.code(health.url or "—", language="text")

        if (
            health.name in {SERVICE_REACT, SERVICE_STREAMLIT}
            and health.configured_port is not None
            and health.actual_port is not None
            and int(health.actual_port) != int(health.configured_port)
        ):
            st.caption(
                f"Detected port {health.actual_port} differs from configured {health.configured_port}."
            )

        if health.payload:
            payload_version = str(health.payload.get("version") or "").strip()
            payload_timestamp = str(health.payload.get("timestamp") or "").strip()
            payload_bits = [f"v{payload_version}" for payload_version in [payload_version] if payload_version]
            if payload_timestamp:
                payload_bits.append(payload_timestamp)
            if payload_bits:
                st.caption("Health " + " · ".join(payload_bits))

        service = _services().get(health.name)
        service_logs = service.logs() if service else []
        if health.status == "STOPPED" and service_logs:
            st.warning(service_logs[-1])

        if service_logs:
            st.markdown("**Logs**")
            preview_count = min(20, len(service_logs))
            preview = service_logs[:preview_count]
            st.code("\n".join(preview), language="text")
            if len(service_logs) > preview_count:
                with st.expander("View more…"):
                    st.code("\n".join(service_logs[-100:]), language="text")
        elif health.name in {SERVICE_CORE, SERVICE_REACT}:
            st.caption("No logs captured yet for this service.")

        action_cols = st.columns([1, 1, 1, 1])
        if health.name == SERVICE_CORE:
            base_port = health.actual_port or health.port or health.configured_port
            open_url = f"http://127.0.0.1:{base_port}/docs" if base_port else None
            open_label = "Open Core Docs"
        else:
            open_url = health.url
            open_label = "Open"
        open_disabled = not open_url or health.status == "STOPPED"
        with action_cols[0]:
            if st.button(
                open_label,
                key=f"health-open-{health.name}",
                disabled=open_disabled,
            ):
                _open_ui(open_url, label, notify=False)

        with action_cols[1]:
            if st.button("Refresh", key=f"health-refresh-{health.name}"):
                _refresh_health()
                safe_rerun()

        adopt_enabled = (
            health.name in {SERVICE_REACT, SERVICE_STREAMLIT, SERVICE_CORE, SERVICE_UCNRR}
            and health.actual_port is not None
            and health.configured_port is not None
            and health.actual_port != health.configured_port
        )
        with action_cols[2]:
            if adopt_enabled:
                if st.button("Adopt actual", key=f"health-adopt-{health.name}"):
                    target_port = int(health.actual_port)
                    state = _load_state()
                    if health.name == SERVICE_REACT:
                        info = state.get(SERVICE_REACT)
                        if info:
                            info.port = target_port
                            info.actual_port = target_port
                            state[SERVICE_REACT] = info
                            _save_state(state)
                        _env()["react_port"] = target_port
                        _save_env()
                        _set_health_notice(
                            f"React port updated to {health.actual_port}. Restart React to apply."
                        )
                    elif health.name == SERVICE_STREAMLIT:
                        info = state.get(SERVICE_STREAMLIT)
                        if info:
                            info.port = target_port
                            info.actual_port = target_port
                            state[SERVICE_STREAMLIT] = info
                            _save_state(state)
                        _apply_port_change(SERVICE_STREAMLIT, target_port)
                        _save_env()
                        _set_health_notice(
                            f"Port updated to {health.actual_port}. Restart Streamlit to apply."
                        )
                    elif health.name == SERVICE_CORE:
                        info = state.get(SERVICE_CORE)
                        if info:
                            info.port = target_port
                            info.actual_port = target_port
                            state[SERVICE_CORE] = info
                            _save_state(state)
                        _apply_port_change(SERVICE_CORE, target_port)
                        _save_env()
                        _set_health_notice(
                            f"Core port updated to {health.actual_port}. Restart Core to apply."
                        )
                    elif health.name == SERVICE_UCNRR:
                        _apply_port_change(SERVICE_UCNRR, target_port)
                        _save_env()
                        _set_health_notice(
                            f"UCN/RR port updated to {health.actual_port}. Restart service to apply."
                        )
                    _refresh_health()
                    safe_rerun()
            if health.name == SERVICE_CORE:
                base_port = health.actual_port or health.port or health.configured_port
                health_url = f"http://127.0.0.1:{base_port}/health" if base_port else None
                if st.button(
                    "Open Health",
                    key=f"health-core-health-{health.name}",
                    disabled=health_url is None,
                ):
                    _open_ui(health_url, "Core health", notify=False)
            elif not adopt_enabled:
                st.write("")

        with action_cols[3]:
            self_pid = _my_streamlit_pid()
            kill_enabled = (
                health.status == "RUNNING (managed)"
                and health.pid is not None
                and health.name != "cpplusplus"
                and health.pid != self_pid
            )
            help_text = None
            if health.name == "cpplusplus" or (health.pid and health.pid == self_pid):
                help_text = "Self-protected"
            elif health.status == "RUNNING (external)":
                help_text = "Unmanaged process"
            elif health.status == "STOPPED":
                help_text = "Process not running"

            if st.button(
                "Kill",
                key=f"health-kill-{health.name}",
                disabled=not kill_enabled,
                help=help_text,
            ):
                st.session_state[SESSION_HEALTH_PENDING_KILL_KEY] = {
                    "service": health.name,
                    "pid": health.pid,
                    "port": health.port,
                    "label": label,
                }
                safe_rerun()
# ---------------------------------------------------------------------------
# Session and persistence helpers
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    if SESSION_ENV_KEY not in st.session_state:
        st.session_state[SESSION_ENV_KEY] = envstore.load_env_config()
    if SESSION_SERVICES_KEY not in st.session_state:
        st.session_state[SESSION_SERVICES_KEY] = {}
    if SESSION_LOG_PAUSE_KEY not in st.session_state:
        st.session_state[SESSION_LOG_PAUSE_KEY] = set()
    if SESSION_HEALTH_KEY not in st.session_state:
        st.session_state[SESSION_HEALTH_KEY] = {}
    if SESSION_TESTS_KEY not in st.session_state:
        st.session_state[SESSION_TESTS_KEY] = {}
    if SESSION_CONFLICTS_KEY not in st.session_state:
        st.session_state[SESSION_CONFLICTS_KEY] = {}
    if SESSION_START_LOCK_KEY not in st.session_state:
        st.session_state[SESSION_START_LOCK_KEY] = set()
    if SESSION_ENV_DIRTY_KEY not in st.session_state:
        st.session_state[SESSION_ENV_DIRTY_KEY] = False
    if SESSION_ACTION_RESULT_KEY not in st.session_state:
        st.session_state[SESSION_ACTION_RESULT_KEY] = None
    if SESSION_PENDING_AUTO_OPEN_KEY not in st.session_state:
        st.session_state[SESSION_PENDING_AUTO_OPEN_KEY] = {}
    if SESSION_CHAT_PROBE_KEY not in st.session_state:
        st.session_state[SESSION_CHAT_PROBE_KEY] = None
    if SESSION_PROVIDER_VALIDATION_KEY not in st.session_state:
        st.session_state[SESSION_PROVIDER_VALIDATION_KEY] = None
    if SESSION_PROFILES_KEY not in st.session_state:
        st.session_state[SESSION_PROFILES_KEY] = envstore.load_profiles()
    if SESSION_SELECTED_PROFILE_KEY not in st.session_state:
        st.session_state[SESSION_SELECTED_PROFILE_KEY] = ""
    if SESSION_PROFILE_NOTICE_KEY not in st.session_state:
        st.session_state[SESSION_PROFILE_NOTICE_KEY] = None
    if SESSION_ACTIVE_USER_KEY not in st.session_state:
        st.session_state[SESSION_ACTIVE_USER_KEY] = DEFAULT_ACTIVE_USER
    if SESSION_ACTIVE_USER_INPUT_KEY not in st.session_state:
        st.session_state[SESSION_ACTIVE_USER_INPUT_KEY] = DEFAULT_ACTIVE_USER
    if SESSION_DETECTED_PORTS_KEY not in st.session_state:
        st.session_state[SESSION_DETECTED_PORTS_KEY] = {}
    if SESSION_HEALTH_PENDING_KILL_KEY not in st.session_state:
        st.session_state[SESSION_HEALTH_PENDING_KILL_KEY] = None
    if SESSION_HEALTH_NOTICE_KEY not in st.session_state:
        st.session_state[SESSION_HEALTH_NOTICE_KEY] = None
    if SESSION_FORCE_ROOT_VENV_KEY not in st.session_state:
        st.session_state[SESSION_FORCE_ROOT_VENV_KEY] = False


def _env() -> Dict[str, Any]:
    return st.session_state[SESSION_ENV_KEY]


def _save_env() -> None:
    envstore.save_env_config(_env())
    _set_env_dirty(False)


def _services() -> Dict[str, services.ServiceProcess]:
    return st.session_state[SESSION_SERVICES_KEY]


def _tests() -> Dict[str, services.ServiceProcess]:
    return st.session_state[SESSION_TESTS_KEY]


def _conflicts() -> Dict[str, Any]:
    return st.session_state[SESSION_CONFLICTS_KEY]


def _start_locks() -> set:
    return st.session_state[SESSION_START_LOCK_KEY]


def _set_start_lock(name: str, locked: bool) -> None:
    locks = _start_locks()
    if locked:
        locks.add(name)
    else:
        locks.discard(name)


def _is_start_locked(name: str) -> bool:
    return name in _start_locks()


def _set_action_result(summary: Optional[Dict[str, Any]]) -> None:
    st.session_state[SESSION_ACTION_RESULT_KEY] = summary


def _set_health_notice(message: Optional[str]) -> None:
    st.session_state[SESSION_HEALTH_NOTICE_KEY] = message


def _consume_action_result() -> Optional[Dict[str, Any]]:
    summary = st.session_state.get(SESSION_ACTION_RESULT_KEY)
    st.session_state[SESSION_ACTION_RESULT_KEY] = None
    return summary


def _set_env_dirty(value: bool) -> None:
    st.session_state[SESSION_ENV_DIRTY_KEY] = bool(value)


def _is_env_dirty() -> bool:
    return bool(st.session_state.get(SESSION_ENV_DIRTY_KEY))


def _pending_auto_open() -> Dict[str, str]:
    return st.session_state[SESSION_PENDING_AUTO_OPEN_KEY]


def _set_pending_auto_open(mapping: Dict[str, str]) -> None:
    st.session_state[SESSION_PENDING_AUTO_OPEN_KEY] = dict(mapping)


def _set_chat_probe_result(result: Optional[Dict[str, Any]]) -> None:
    st.session_state[SESSION_CHAT_PROBE_KEY] = result


def _get_chat_probe_result() -> Optional[Dict[str, Any]]:
    return st.session_state.get(SESSION_CHAT_PROBE_KEY)


def _set_provider_validation(result: Optional[Dict[str, Any]]) -> None:
    st.session_state[SESSION_PROVIDER_VALIDATION_KEY] = result


def _get_provider_validation() -> Optional[Dict[str, Any]]:
    return st.session_state.get(SESSION_PROVIDER_VALIDATION_KEY)


def _profiles() -> Dict[str, Dict[str, Any]]:
    return st.session_state[SESSION_PROFILES_KEY]


def _set_profiles(profiles: Dict[str, Dict[str, Any]]) -> None:
    st.session_state[SESSION_PROFILES_KEY] = profiles


def _selected_profile() -> str:
    return st.session_state.get(SESSION_SELECTED_PROFILE_KEY, "")


def _set_selected_profile(name: str) -> None:
    st.session_state[SESSION_SELECTED_PROFILE_KEY] = name


def _set_profile_notice(message: Optional[str]) -> None:
    st.session_state[SESSION_PROFILE_NOTICE_KEY] = message


def _active_user() -> str:
    value = str(st.session_state.get(SESSION_ACTIVE_USER_KEY, DEFAULT_ACTIVE_USER) or "").strip()
    if not value:
        value = DEFAULT_ACTIVE_USER
        st.session_state[SESSION_ACTIVE_USER_KEY] = value
    return value


def _set_active_user(value: str) -> None:
    sanitized = value.strip() or DEFAULT_ACTIVE_USER
    st.session_state[SESSION_ACTIVE_USER_KEY] = sanitized


# ---------------------------------------------------------------------------
# Command builders
# ---------------------------------------------------------------------------

def _bool_env(value: Any) -> str:
    return "1" if bool(value) else "0"


def _core_env(config: Dict[str, Any]) -> Dict[str, str]:
    env_vars: Dict[str, str] = {
        "HC_CHAT_ENABLED": _bool_env(config.get("HC_CHAT_ENABLED", True)),
        "HC_CHAT_STREAM_ENABLED": _bool_env(config.get("HC_CHAT_STREAM_ENABLED", True)),
        "HC_ASK_ACTIONS_ENABLED": _bool_env(config.get("HC_ASK_ACTIONS_ENABLED", True)),
        "HC_CHAT_PROVIDER": str(config.get("HC_CHAT_PROVIDER", "stub") or "stub"),
        "CORE_CURIOSITY_ENABLED": _bool_env(config.get("CORE_CURIOSITY_ENABLED", True)),
    }
    optional = {
        "OPENAI_API_KEY": config.get("OPENAI_API_KEY"),
        "OPENAI_MODEL": config.get("OPENAI_MODEL"),
        "OLLAMA_BASE": config.get("OLLAMA_BASE"),
        "OLLAMA_MODEL": config.get("OLLAMA_MODEL"),
        "ANTHROPIC_API_KEY": config.get("ANTHROPIC_API_KEY"),
        "ANTHROPIC_MODEL": config.get("ANTHROPIC_MODEL"),
        "UCNRR_BASE_URL": config.get("UCNRR_BASE_URL"),
    }
    for key, value in optional.items():
        if value:
            env_vars[key] = str(value)

    workspace_root_raw = str(config.get("WORKSPACE_ROOT") or "").strip()
    core_data_dir_raw = str(config.get("CORE_DATA_DIR") or "").strip()
    try:
        if workspace_root_raw:
            workspace_path = Path(workspace_root_raw).expanduser()
            env_vars["WORKSPACE_ROOT"] = str(workspace_path.resolve(strict=False))
            if not core_data_dir_raw:
                env_vars["CORE_DATA_DIR"] = str((workspace_path / "data").resolve(strict=False))
    except Exception:
        env_vars["WORKSPACE_ROOT"] = workspace_root_raw

    if core_data_dir_raw:
        try:
            env_vars["CORE_DATA_DIR"] = str(Path(core_data_dir_raw).expanduser().resolve(strict=False))
        except Exception:
            env_vars["CORE_DATA_DIR"] = core_data_dir_raw

    workspace_label = str(config.get("WORKSPACE_LABEL") or "").strip()
    if workspace_label:
        env_vars["WORKSPACE_LABEL"] = workspace_label
    return env_vars


def _react_command(npm_cmd: Optional[str] = None) -> List[str]:
    executable = npm_cmd or "npm"
    return [executable, "run", "dev"]


def _react_env(config: Dict[str, Any]) -> Dict[str, str]:
    env_vars: Dict[str, str] = {
        "NEXT_PUBLIC_CORE_API_BASE": str(config.get("NEXT_PUBLIC_CORE_API_BASE", "")),
    }
    workspace_label = str(config.get("WORKSPACE_LABEL") or "").strip()
    if workspace_label:
        env_vars["NEXT_PUBLIC_WORKSPACE_LABEL"] = workspace_label
    workspace_root = str(config.get("WORKSPACE_ROOT") or "").strip()
    if workspace_root:
        env_vars["NEXT_PUBLIC_WORKSPACE_ROOT"] = workspace_root
    streamlit_port = int(config.get("streamlit_port", STREAMLIT_DEFAULT_PORT))
    env_vars["NEXT_PUBLIC_CP_PROFILES_URL"] = f"http://127.0.0.1:{streamlit_port}?tab=profiles"
    return env_vars


def _ucnrr_command(config: Dict[str, Any], port: int) -> List[str]:
    """Build UCNRR command from config, substituting {port} placeholder."""
    cmd_template = str(config.get("ucnrr_start_command") or envstore.DEFAULT_ENV.get("ucnrr_start_command", ""))
    if not cmd_template:
        # Fallback if no command configured
        venv_python = ROOT / ".venv" / "bin" / "python"
        return [str(venv_python), "-m", "uvicorn", "ucnrr_app:app", "--host", "0.0.0.0", "--port", str(port), "--reload"]
    cmd_str = cmd_template.format(port=port)
    try:
        return shlex.split(cmd_str)
    except ValueError:
        return cmd_str.split()


def _ucnrr_env(config: Dict[str, Any]) -> Dict[str, str]:
    """Build environment variables for UCNRR service."""
    env_vars: Dict[str, str] = {}
    ucnrr_base = str(config.get("UCNRR_BASE_URL") or "")
    if ucnrr_base:
        env_vars["UCNRR_BASE_URL"] = ucnrr_base
    return env_vars


def _streamlit_command(port: int) -> List[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "ExplorerFinal/pages/HC_v2.py",
        "--server.port",
        str(port),
        "--server.address",
        "0.0.0.0",
    ]


def _streamlit_find_fallback_port(configured_port: Optional[int]) -> Optional[int]:
    cp_port = _my_streamlit_port()
    for candidate in STREAMLIT_FALLBACK_PORTS:
        if configured_port is not None and candidate == int(configured_port):
            continue
        if cp_port is not None and candidate == int(cp_port):
            continue
        free = ports.find_free_port(candidate, candidate)
        if free == candidate:
            return candidate
    return None


def _router_command(shell: str) -> List[str]:
    env = os.environ.copy()
    env["HC_SHELL_V2"] = shell
    cmd = [sys.executable, "ExplorerDev/hc_shell_router.py"]
    return cmd


def _test_command_playwright() -> List[str]:
    return ["bash", "-lc", "cd web && npm install && npx playwright install && npm run test:e2e"]


def _test_command_ci() -> List[str]:
    return ["bash", "-lc", "bash ExplorerDev/scripts/run_ci_smoke.sh"]


# ---------------------------------------------------------------------------
# Service management helpers
# ---------------------------------------------------------------------------

def _start_service(
    name: str,
    command: List[str],
    cwd: Optional[Path],
    env: Dict[str, str],
    port: Optional[int] = None,
    actual_port: Optional[int] = None,
) -> bool:
    svc_map = _services()
    if name in svc_map and svc_map[name].is_running():
        st.warning(f"{name} already running (pid={svc_map[name].pid()}).")
        return False
    try:
        service = services.start_service(name=name, command=command, cwd=cwd, env=env)
        svc_map[name] = service
        pid = service.pid()
        if pid:
            state = _load_state()
            state[name] = ProcInfo(
                name=name,
                cmd=list(command),
                pid=int(pid),
                port=int(port) if port is not None else None,
                started_at=time.time(),
                actual_port=int(actual_port) if actual_port is not None else None,
            )
            _save_state(state)
        st.success(f"Started {name} (pid={service.pid()}).")
        return True
    except FileNotFoundError as exc:
        st.error(f"Failed to start {name}: {exc}")
    except Exception as exc:
        st.error(f"Failed to start {name}: {exc}")
    return False


def _stop_service(name: str, *, rerun: bool = True) -> None:
    svc_map = _services()
    service = svc_map.get(name)
    if not service:
        st.info(f"{name} is not running.")
        return
    summary = services.stop_service(service)
    svc_map.pop(name, None)
    state = _load_state()
    if state.pop(name, None) is not None:
        _save_state(state)
    _set_action_result(summary)
    _refresh_port_scans()
    st.info(f"Stopped {name}.")
    if rerun:
        safe_rerun()


def _kill_managed_service(name: str) -> Optional[Dict[str, Any]]:
    if name == "cpplusplus":
        st.info("CP++ is self-protected.")
        return None

    state = _load_state()
    info = state.get(name)
    if not info:
        st.info("No managed process record for this service.")
        return None

    if info.pid == _my_streamlit_pid():
        st.info("CP++ is self-protected.")
        return None

    svc_map = _services()
    service = svc_map.get(name)
    summary: Optional[Dict[str, Any]]

    if service and service.is_running():
        summary = services.stop_service(service)
        svc_map.pop(name, None)
    else:
        summary = ports.kill_pids([info.pid])

    state.pop(name, None)
    _save_state(state)
    _refresh_port_scans()
    return summary


def _merge_summary(total: Dict[str, Any], summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(summary, dict):
        return total
    total.setdefault("terminated", set()).update(summary.get("terminated", []))
    total.setdefault("already_dead", set()).update(summary.get("already_dead", []))
    errors = summary.get("errors", {})
    if errors:
        target_errors = total.setdefault("errors", {})
        for pid, err in errors.items():
            target_errors[pid] = err
    return total


def _stop_all_services() -> None:
    svc_map = _services()
    names = list(svc_map.keys())
    if not names:
        st.info("No services running.")
        return
    aggregate: Dict[str, Any] = {}
    for name in names:
        service = svc_map.pop(name, None)
        if not service:
            continue
        summary = services.stop_service(service)
        _merge_summary(aggregate, summary)
    if "terminated" in aggregate:
        aggregate["terminated"] = sorted(aggregate["terminated"])
    if "already_dead" in aggregate:
        aggregate["already_dead"] = sorted(aggregate["already_dead"])
    _set_action_result(aggregate)
    _refresh_port_scans()
    st.info("Stopped all services.")
    safe_rerun()


def _wait_for_core_health(port: int, timeout: float = 25.0) -> tuple[bool, Optional[str]]:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/health"
    last_detail: Optional[str] = None

    while time.time() < deadline:
        service = _services().get(SERVICE_CORE)
        if service and not service.is_running():
            exit_code = services.poll_service(service)
            if exit_code is not None:
                last_detail = f"Core exited with code {exit_code} before health succeeded."
            break
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                try:
                    payload = response.json()
                except Exception:
                    payload = {}
                if isinstance(payload, dict) and payload.get("ok") is True:
                    return True, None
                if payload:
                    last_detail = f"Health response: {payload}"
                else:
                    last_detail = "Health endpoint returned 200 without ok:true."
            else:
                last_detail = f"HTTP {response.status_code}"
        except Exception as exc:
            last_detail = str(exc)
        time.sleep(0.5)

    return False, last_detail


def _wait_for_react_health(port: int, timeout: float = 35.0) -> tuple[bool, Optional[str]]:
    deadline = time.time() + timeout
    last_note: Optional[str] = None

    while time.time() < deadline:
        service = _services().get(SERVICE_REACT)
        if service and not service.is_running():
            exit_code = services.poll_service(service)
            if exit_code is not None:
                last_note = f"React exited with code {exit_code} before health succeeded."
            break
        if service is None:
            time.sleep(0.5)
            continue

        results = check_services(_env())
        health = results.get(SERVICE_REACT)
        if health:
            if health.status == "RUNNING (managed)":
                return True, None
            if health.note:
                last_note = health.note
        time.sleep(0.5)

    return False, last_note


def _handle_core_start(
    name: str,
    label: str,
    start_cmd: List[str],
    cwd: Optional[Path],
    env_extra: Dict[str, str],
    port: Optional[int],
    port_range: Optional[Tuple[int, int]],
    expected_core: bool = False,
) -> None:
    _conflicts().pop(name, None)

    if _is_env_dirty():
        st.warning("Save Environment changes before launching services.")
        return

    env_config = _env()
    port_key = SERVICE_PORT_KEYS.get(name)
    configured_port = int(port or env_config.get(port_key, 8015))
    health_url = f"http://127.0.0.1:{configured_port}/health"

    port_in_use = _is_port_in_use(configured_port)
    adopted = False

    if port_in_use:
        pid = _pid_on_port(configured_port)
        cmd = _describe_process(pid) if pid else ""
        health_ok, _ = check_health(health_url, timeout=1.5)
        cmd_lower = cmd.lower()

        if (
            pid
            and health_ok
            and "uvicorn" in cmd_lower
            and "rednacoredemo.core.api" in cmd_lower
        ):
            st.info(f"Reusing existing Core on port {configured_port} (PID {pid})")
            state = _load_state()
            state[name] = ProcInfo(
                name=name,
                cmd=list(start_cmd) if start_cmd else [],
                pid=int(pid),
                port=int(configured_port),
                started_at=time.time(),
                actual_port=int(configured_port),
            )
            _save_state(state)
            _post_launch_health(name)
            adopted = True
        else:
            with st.container(border=True):
                st.warning(
                    f"Port {configured_port} is occupied by: {cmd or 'unknown process'}"
                )
                suggested = _next_free_port(configured_port + 1, forbidden={configured_port})
                col_use, col_kill = st.columns(2)
                with col_use:
                    if st.button(
                        f"Use different port ({suggested})",
                        key=f"core-change-port-{configured_port}",
                    ):
                        if port_key:
                            env_config[port_key] = int(suggested)
                            _save_env()
                            st.success(f"Updated {port_key} to {suggested}. Restart action to launch Core.")
                        safe_rerun()
                        return
                with col_kill:
                    if st.button(
                        f"Kill port {configured_port}",
                        key=f"core-kill-port-{configured_port}",
                    ):
                        kill_port(configured_port)
                        port_in_use = _is_port_in_use(configured_port)
                        if port_in_use:
                            st.error(f"Unable to free port {configured_port}.")
                            return
                        st.success(f"Cleared port {configured_port}. Launching Core…")
                    else:
                        return

    if adopted:
        return

    if _is_start_locked(name):
        st.info(f"{label} launch already in progress.")
        return

    workdir = Path(cwd) if cwd else _resolve_core_workdir(env_config)
    if not workdir.exists():
        st.error(f"Core working dir '{workdir}' does not exist.")
        return

    force_root = bool(st.session_state.get(SESSION_FORCE_ROOT_VENV_KEY, False))
    if force_root and not ROOT_VENV_BIN.exists():
        st.error(f"Root venv python not found at {ROOT_VENV_BIN}. Run `scripts/consolidate_venv.sh` to restore.")
        return

    command = _compose_core_command(configured_port, start_cmd)

    env_vars = dict(env_extra)
    prev_cwd = os.getcwd()
    _set_start_lock(name, True)
    success = False
    try:
        os.chdir(str(workdir))
        success = _start_service(
            name,
            command,
            workdir,
            env_vars,
            configured_port,
            configured_port,
        )
    finally:
        os.chdir(prev_cwd)
        _set_start_lock(name, False)

    if success:
        healthy, detail = _wait_for_core_health(configured_port)
        if not healthy and detail:
            _set_health_notice(f"Core health check failed: {detail}")
        _post_launch_health(name)
    else:
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)


def _handle_ucnrr_start(
    name: str,
    label: str,
    start_cmd: List[str],
    cwd: Optional[Path],
    env_extra: Dict[str, str],
    port: Optional[int],
    port_range: Optional[Tuple[int, int]],
) -> None:
    if _is_env_dirty():
        st.warning("Save Environment changes before launching services.")
        return

    env_config = _env()
    port_key = SERVICE_PORT_KEYS.get(name)
    configured_port = int(port or env_config.get(port_key, 8011))
    health_url = f"http://127.0.0.1:{configured_port}/health"

    port_in_use = _is_port_in_use(configured_port)
    if port_in_use:
        pid = _pid_on_port(configured_port)
        cmd = _describe_process(pid) if pid else ""
        health_ok, _ = check_health(health_url, timeout=1.5)
        cmd_lower = cmd.lower()

        if pid and health_ok and "uvicorn" in cmd_lower and "ucnrr_app" in cmd_lower:
            st.info(f"Reusing existing UCN/RR on port {configured_port} (PID {pid})")
            state = _load_state()
            state[name] = ProcInfo(
                name=name,
                cmd=list(start_cmd) if start_cmd else [],
                pid=int(pid),
                port=int(configured_port),
                started_at=time.time(),
                actual_port=int(configured_port),
            )
            _save_state(state)
            _post_launch_health(name)
            return

        with st.container(border=True):
            st.warning(
                f"Port {configured_port} is occupied by: {cmd or 'unknown process'}"
            )
            suggested = _next_free_port(configured_port + 1, forbidden={configured_port})
            col_use, col_kill = st.columns(2)
            with col_use:
                if st.button(
                    f"Use different port ({suggested})",
                    key=f"ucnrr-change-port-{configured_port}",
                ):
                    if port_key:
                        env_config[port_key] = int(suggested)
                        _save_env()
                        st.success(f"Updated {port_key} to {suggested}. Restart action to launch UCN/RR.")
                    safe_rerun()
                    return
            with col_kill:
                if st.button(
                    f"Kill port {configured_port}",
                    key=f"ucnrr-kill-port-{configured_port}",
                ):
                    kill_port(configured_port)
                    port_in_use = _is_port_in_use(configured_port)
                    if port_in_use:
                        st.error(f"Unable to free port {configured_port}.")
                        return
                    st.success(f"Cleared port {configured_port}. Launching UCN/RR…")
                else:
                    return

    if _is_start_locked(name):
        st.info(f"{label} launch already in progress.")
        return

    workdir = Path(cwd) if cwd else ROOT
    if not workdir.exists():
        st.error(f"UCN/RR working dir '{workdir}' does not exist.")
        return

    env_vars = dict(env_extra)
    prev_cwd = os.getcwd()
    _set_start_lock(name, True)
    success = False
    try:
        os.chdir(str(workdir))
        success = _start_service(
            name,
            start_cmd,
            workdir,
            env_vars,
            configured_port,
            configured_port,
        )
    finally:
        os.chdir(prev_cwd)
        _set_start_lock(name, False)

    if success:
        _post_launch_health(name)
    else:
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)
def _handle_react_start(
    name: str,
    label: str,
    start_cmd: List[str],
    cwd: Optional[Path],
    env_extra: Dict[str, str],
    port: Optional[int],
    port_range: Optional[Tuple[int, int]],
) -> None:
    _conflicts().pop(name, None)

    if _is_env_dirty():
        st.warning("Save Environment changes before launching services.")
        return

    configured_port = int(port or _env().get("react_port", REACT_DEFAULT_PORT))
    listeners = ports.who_listens(configured_port) if configured_port else []
    if listeners:
        st.info(
            f"React configured port {configured_port} is occupied; Next.js will request a new port if available."
        )
        for row in listeners:
            pid = row.get("pid")
            cmd = row.get("cmd") or "(unknown command)"
            st.code(f"{pid}: {cmd}", language="text")

    workdir = Path(cwd) if cwd else _resolve_react_workdir(_env())
    if not workdir.exists():
        st.error(f"React working dir '{workdir}' does not exist.")
        return

    npm_cmd = _resolve_react_npm(_env())
    if not npm_cmd:
        message = "Unable to locate npm. Set the React npm path in Environment & Ports."
        st.error(message)
        _set_health_notice(message)
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)
        return

    env_vars = dict(env_extra)
    env_vars["PORT"] = str(configured_port)

    if _is_start_locked(name):
        st.info(f"{label} launch already in progress.")
        return

    prev_cwd = os.getcwd()
    _set_start_lock(name, True)
    success = False
    try:
        os.chdir(str(workdir))
        success = _start_service(
            name,
            [npm_cmd, "run", "dev"],
            workdir,
            env_vars,
            configured_port,
            None,
        )
    finally:
        os.chdir(prev_cwd)
        _set_start_lock(name, False)

    if not success:
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)
        return

    _conflicts().pop(name, None)
    service = _services().get(name)
    if service:
        _ensure_react_port_watcher(service, configured_port)

    healthy, detail = _wait_for_react_health(configured_port)
    if not healthy and detail:
        _set_health_notice(detail)

    _post_launch_health(name)


def _handle_streamlit_start(
    name: str,
    label: str,
    start_cmd: List[str],
    cwd: Optional[Path],
    env_extra: Dict[str, str],
    port: Optional[int],
    port_range: Optional[Tuple[int, int]],
) -> None:
    if _is_env_dirty():
        st.warning("Save Environment changes before launching services.")
        return

    _ = start_cmd  # Command rebuilt with the selected port.

    configured_port: Optional[int]
    try:
        configured_port = int(port) if port is not None else STREAMLIT_DEFAULT_PORT
    except Exception:
        configured_port = STREAMLIT_DEFAULT_PORT

    listeners = ports.who_listens(int(configured_port)) if configured_port else []
    conflict_payload: Optional[Dict[str, Any]] = None
    if configured_port and listeners:
        conflict_payload = {
            "port": int(configured_port),
            "rows": listeners,
            "expected_ok": False,
            "range": port_range,
            "label": label,
            "auto_scanned": True,
        }
        _conflicts()[name] = conflict_payload
    else:
        _conflicts().pop(name, None)

    if _is_start_locked(name):
        st.info(f"{label} launch already in progress.")
        return

    _set_start_lock(name, True)
    env_vars = dict(env_extra)
    actual_port: Optional[int] = configured_port
    success = False
    try:
        if listeners:
            fallback = _streamlit_find_fallback_port(configured_port)
            if fallback is None:
                st.error(
                    "Configured Streamlit port is busy and no fallback ports (8503-8515) are free."
                )
                _set_health_notice(
                    "Streamlit launch blocked: configured port busy and fallback range exhausted."
                )
                return
            actual_port = fallback

        if actual_port is None:
            actual_port = STREAMLIT_DEFAULT_PORT

        env_vars["STREAMLIT_SERVER_PORT"] = str(actual_port)
        command = _streamlit_command(actual_port)
        success = _start_service(
            name,
            command,
            cwd,
            env_vars,
            configured_port,
            actual_port,
        )
    finally:
        _set_start_lock(name, False)

    if success:
        if conflict_payload:
            conflict_payload["auto_port"] = actual_port
            _conflicts()[name] = conflict_payload
        else:
            _conflicts().pop(name, None)

        if configured_port and actual_port and configured_port != actual_port:
            _set_health_notice(
                f"Streamlit launched on port {actual_port}; configured port {configured_port} remains reserved."
            )

        _post_launch_health(name)
    else:
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)


def _handle_start_request(
    name: str,
    label: str,
    start_cmd: List[str],
    cwd: Optional[Path],
    env_extra: Dict[str, str],
    port: Optional[int],
    port_range: Optional[Tuple[int, int]],
    expected_core: bool = False,
) -> None:
    if name == SERVICE_CORE:
        _handle_core_start(name, label, start_cmd, cwd, env_extra, port, port_range, expected_core)
        return
    if name == SERVICE_REACT:
        _handle_react_start(name, label, start_cmd, cwd, env_extra, port, port_range)
        return
    if name == SERVICE_UCNRR:
        _handle_ucnrr_start(name, label, start_cmd, cwd, env_extra, port, port_range)
        return
    if name == SERVICE_STREAMLIT:
        _handle_streamlit_start(name, label, start_cmd, cwd, env_extra, port, port_range)
        return

    _conflicts().pop(name, None)

    if _is_env_dirty():
        st.warning("Save Environment changes before launching services.")
        return

    listeners: List[Dict[str, Any]] = []
    if port:
        listeners = ports.who_listens(int(port))

    if port and listeners:
        expected_ok = expected_core and ports.is_expected_core_owner(listeners)
        _conflicts()[name] = {
            "port": int(port),
            "rows": listeners,
            "expected_ok": expected_ok,
            "range": port_range,
            "label": label,
        }
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)
        return

    if _is_start_locked(name):
        st.info(f"{label} launch already in progress.")
        return

    _set_start_lock(name, True)
    success = False
    try:
        success = _start_service(name, start_cmd, cwd, env_extra, port)
    finally:
        _set_start_lock(name, False)

    if success:
        if name == SERVICE_REACT:
            react_service = _services().get(name)
            if react_service:
                _ensure_react_port_watcher(react_service, port)
        _conflicts().pop(name, None)
        _post_launch_health(name)
    else:
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)


def _post_launch_health(name: str) -> None:
    labels = {
        SERVICE_CORE: "Core",
        SERVICE_REACT: "React",
        SERVICE_STREAMLIT: "Streamlit",
        SERVICE_UCNRR: "UCN/RR",
    }
    results = _refresh_health()
    service_health = results.get(name)
    if not service_health:
        return
    _render_post_launch_result(labels.get(name, name.title()), service_health)
    _maybe_auto_open(name, service_health)
    # Trigger UI refresh to show updated service status immediately
    safe_rerun()


def _render_post_launch_result(label: str, result: ServiceHealth) -> None:
    message = f"{label} status: {result.status}"
    if result.note:
        message = f"{message} — {result.note}"
    if result.status == "RUNNING (managed)":
        st.success(message)
    elif result.status == "RUNNING (external)":
        st.info(message)
    else:
        st.warning(message)


def _render_conflict_panel(name: str, conflict: Dict[str, Any]) -> None:
    port = conflict.get("port")
    rows: List[Dict[str, Any]] = conflict.get("rows", [])
    expected_ok = conflict.get("expected_ok", False)
    label = conflict.get("label", name)
    auto_scanned = bool(conflict.get("auto_scanned"))
    auto_port = conflict.get("auto_port")
    header = f"Port {port} is occupied by:" if not expected_ok else f"Port {port} already runs an expected {label} instance."

    alert = st.error if not expected_ok else st.warning
    alert(header)
    for row in rows:
        pid = row.get("pid")
        cmd = row.get("cmd") or "(unknown command)"
        st.code(f"{pid}: {cmd}", language="text")

    if auto_scanned and auto_port:
        st.info(
            f"{label} launched on port {auto_port} while port {port} remains busy."
        )

    cols = st.columns(2)
    with cols[0]:
        if st.button("Kill listeners", key=f"conflict-kill-{name}-{port}"):
            pids = [row.get("pid") for row in rows if row.get("pid")]
            summary = ports.kill_pids(pids)
            _set_action_result(summary)
            _conflicts().pop(name, None)
            _refresh_port_scans()
            safe_rerun()
    with cols[1]:
        if st.button("Use different port", key=f"conflict-move-{name}-{port}"):
            port_range = conflict.get("range")
            start = port_range[0] if port_range else int(port)
            end = port_range[1] if port_range else int(port)
            suggestion = ports.find_free_port(start, end)
            if suggestion is None:
                st.warning("No free port available in the suggested range.")
            else:
                _apply_port_change(name, suggestion)
                _conflicts().pop(name, None)
                st.info(f"Updated to port {suggestion}. Save changes in Environment & Flags before launching.")


def _service_log_lines(name: str, limit: int = 100) -> List[str]:
    svc = _services().get(name) or _tests().get(name)
    if not svc:
        return []
    logs = svc.logs()
    if limit:
        logs = logs[-limit:]
    return logs


def _update_next_public_base() -> None:
    env = _env()
    core_port = int(env.get("core_port", 8015))
    env.setdefault("NEXT_PUBLIC_CORE_API_BASE", f"http://127.0.0.1:{core_port}")


def _refresh_port_scans() -> None:
    ports.scan_ports("react", range(REACT_PORT_RANGE[0], REACT_PORT_RANGE[1] + 1))
    ports.scan_ports("streamlit", range(STREAMLIT_PORT_RANGE[0], STREAMLIT_PORT_RANGE[1] + 1))


def _env_port_key(service_name: str) -> Optional[str]:
    mapping = {
        SERVICE_CORE: "core_port",
        SERVICE_REACT: "react_port",
        SERVICE_STREAMLIT: "streamlit_port",
        SERVICE_UCNRR: "ucnrr_port",
    }
    return mapping.get(service_name)


def _apply_port_change(service_name: str, new_port: int) -> None:
    env = _env()
    key = _env_port_key(service_name)
    if not key:
        return
    env[key] = int(new_port)
    if service_name == SERVICE_CORE:
        expected = f"http://127.0.0.1:{new_port}"
        current = str(env.get("NEXT_PUBLIC_CORE_API_BASE", ""))
        if not current or current.startswith("http://127.0.0.1:"):
            env["NEXT_PUBLIC_CORE_API_BASE"] = expected
    _set_env_dirty(True)


def _render_action_summary(summary: Optional[Dict[str, Any]]) -> None:
    if not summary:
        return
    terminated = summary.get("terminated", []) if isinstance(summary, dict) else []
    already = summary.get("already_dead", []) if isinstance(summary, dict) else []
    errors = summary.get("errors", {}) if isinstance(summary, dict) else {}
    msg = f"Terminated: {len(terminated)}, Already gone: {len(already)}, Errors: {len(errors)}."
    if errors:
        st.warning(msg)
        if isinstance(errors, dict) and errors:
            error_lines = "\n".join(f"PID {pid}: {err}" for pid, err in errors.items())
            if error_lines:
                st.code(error_lines, language="text")
    elif terminated:
        st.success(msg)
    else:
        st.info(msg)


def _append_ui_debug(url: str, enabled: bool) -> str:
    if not enabled:
        return url
    if "?" in url:
        separator = "&" if not url.endswith("?") and not url.endswith("&") else ""
    else:
        separator = "?"
    suffix = "ui_debug=1"
    if separator == "" and not url.endswith("?") and not url.endswith("&"):
        separator = "&"
    return f"{url}{separator}{suffix}"


def _build_service_url(service: str, force_debug: Optional[bool] = None) -> Optional[str]:
    env = _env()
    debug = force_debug if force_debug is not None else bool(env.get("APPEND_UI_DEBUG_PARAM", False))

    health_map = st.session_state.get(SESSION_HEALTH_KEY, {})
    health_entry = health_map.get(service)
    preferred_port: Optional[int] = None
    if isinstance(health_entry, ServiceHealth):
        for candidate in (health_entry.actual_port, health_entry.port, health_entry.configured_port):
            if candidate:
                try:
                    preferred_port = int(candidate)
                    break
                except Exception:
                    continue

    if service == SERVICE_REACT:
        port = preferred_port or env.get("react_port")
        if not port:
            return None
        base = f"http://127.0.0.1:{int(port)}/"
    elif service == SERVICE_CORE:
        port = preferred_port or env.get("core_port")
        if not port:
            return None
        base = f"http://127.0.0.1:{int(port)}/"
    elif service == SERVICE_STREAMLIT:
        port = preferred_port or env.get("streamlit_port")
        if not port:
            return None
        base = f"http://127.0.0.1:{int(port)}/"
    elif service == SERVICE_UCNRR:
        port = preferred_port or env.get("ucnrr_port")
        if not port:
            return None
        base = f"http://127.0.0.1:{int(port)}/"
    elif service == SERVICE_DEV_EXPLORER:
        port = env.get("dev_explorer_port")
        if not port:
            return None
        base = f"http://127.0.0.1:{int(port)}/"
    else:
        return None

    return _append_ui_debug(base, debug)


def _open_ui(url: Optional[str], label: str, notify: bool = True) -> None:
    if not url:
        st.info(f"{label} URL is not configured.")
        return

    status: Optional[int] = None
    error: Optional[str] = None

    if notify:
        try:
            response = requests.head(url, timeout=1.5, allow_redirects=True)
            status = response.status_code
            if status == 405:
                response = requests.get(url, timeout=1.5, allow_redirects=True)
                status = response.status_code
        except requests.RequestException as exc:
            error = str(exc)

    webbrowser.open_new_tab(url)

    if notify:
        if error:
            st.info(f"Opened {label}, but the endpoint may be offline ({error}).")
        elif status is not None and not (200 <= status < 400):
            st.info(f"Opened {label}; received HTTP {status}.")


def _setup_auto_open_targets() -> None:
    env = _env()
    debug = bool(env.get("APPEND_UI_DEBUG_PARAM", False))
    pending: Dict[str, str] = {}
    if env.get("AUTO_OPEN_REACT_AFTER_LAUNCH"):
        url = _build_service_url(SERVICE_REACT, debug)
        if url:
            pending[SERVICE_REACT] = url
    if env.get("AUTO_OPEN_STREAMLIT_AFTER_LAUNCH"):
        url = _build_service_url(SERVICE_STREAMLIT, debug)
        if url:
            pending[SERVICE_STREAMLIT] = url
    _set_pending_auto_open(pending)


def _maybe_auto_open(name: str, result: ServiceHealth) -> None:
    pending = dict(_pending_auto_open())
    url = pending.get(name)
    if not url:
        return
    target_url = result.url or url
    if result.status == "RUNNING (managed)" and target_url:
        _open_ui(target_url, f"{name} UI", notify=False)
    pending.pop(name, None)
    _set_pending_auto_open(pending)


def _render_open_button(service: str, label: str) -> None:
    url = _build_service_url(service)
    cols = st.columns([1, 3])
    disabled = url is None
    with cols[0]:
        if st.button(label, key=f"open-{service}", disabled=disabled):
            _open_ui(url, label)
    with cols[1]:
        st.code(url or "(not configured)", language="text")
# ---------------------------------------------------------------------------
# UI Building blocks
# ---------------------------------------------------------------------------

def _render_service_row(
    name: str,
    label: str,
    start_cmd: List[str],
    cwd: Optional[Path],
    env_extra: Dict[str, str],
    port: Optional[int],
    port_range: Optional[Tuple[int, int]],
    expected_core: bool = False,
) -> None:
    svc = _services().get(name)
    conflict = _conflicts().get(name)
    start_locked = _is_start_locked(name)

    state_info = _load_state().get(name)
    svc_running = bool(svc and svc.is_running())
    svc_pid = svc.pid() if svc else None
    stored_pid = state_info.pid if state_info else None
    pid = svc_pid or stored_pid

    health_url: Optional[str] = None
    if port is not None:
        if name == SERVICE_CORE:
            health_url = f"http://127.0.0.1:{int(port)}/health"
        elif name == SERVICE_UCNRR:
            health_url = f"http://127.0.0.1:{int(port)}/health"
        elif name == SERVICE_REACT:
            health_url = f"http://127.0.0.1:{int(port)}/api/health"
        elif name == SERVICE_STREAMLIT:
            health_url = f"http://127.0.0.1:{int(port)}/_stcore/health"

    health_ok = False
    health_msg = ""
    if health_url:
        health_ok, health_msg = check_health(health_url)

    health_status = "🔴 down"
    if health_ok:
        health_status = "🟢 OK"
    elif health_url:
        health_status = "🟡 not ready"

    external_running = bool(health_ok and not svc_running and not pid)
    running = bool(pid) or svc_running or external_running

    start_disabled = start_locked or _is_env_dirty() or conflict is not None or running or external_running
    stop_disabled = not running and not external_running

    cols = st.columns([1.4, 2, 2])
    with cols[0]:
        st.metric(label, "Running" if running or health_ok else "Stopped", delta=None)
        st.markdown(f"**PID:** {pid if pid else '—'}{(' (external)') if external_running else ''}")
        if port is not None:
            st.markdown(f"**Port:** {port}")
        if health_url:
            health_line = f"Health: {health_status} — {health_url}"
        else:
            health_line = "Health: (not configured)"
        if external_running:
            health_line += " (external process)"
        st.caption(health_line)
        if health_msg:
            st.caption(health_msg)

    with cols[1]:
        start_clicked = st.button(
            f"Start {label}",
            key=f"start-{name}",
            disabled=start_disabled,
        )
        stop_clicked = st.button(
            f"Stop {label}",
            key=f"stop-{name}",
            disabled=stop_disabled,
        )

        if start_clicked:
            _handle_start_request(name, label, start_cmd, cwd, env_extra, port, port_range, expected_core)

        if stop_clicked:
            if svc_running:
                _stop_service(name)
            elif pid:
                summary = _kill_managed_service(name)
                if summary:
                    _set_action_result(summary)
                if port is not None:
                    kill_port(int(port))
                _refresh_health()
                safe_rerun()
            elif port is not None:
                kill_port(int(port))
                st.success(f"Cleared port {port}.")
                _refresh_health()
                safe_rerun()

        if start_locked:
            st.caption("Launch in progress…")
        if _is_env_dirty():
            st.caption("Save Environment & Flags before launching.")

        if external_running and health_url and port is not None and name in {SERVICE_CORE, SERVICE_UCNRR}:
            if st.button(f"Adopt {label}", key=f"adopt-{name}"):
                adopt_pid = _pid_on_port(int(port))
                if adopt_pid:
                    state_snapshot = _load_state()
                    state_snapshot[name] = ProcInfo(
                        name=name,
                        cmd=list(start_cmd) if start_cmd else [],
                        pid=int(adopt_pid),
                        port=int(port),
                        started_at=time.time(),
                        actual_port=int(port),
                    )
                    _save_state(state_snapshot)
                    st.success(f"Adopted PID {adopt_pid}")
                    _refresh_health()
                    safe_rerun()
                else:
                    st.warning("Unable to detect a PID on the configured port to adopt.")

    with cols[2]:
        paused = name in st.session_state[SESSION_LOG_PAUSE_KEY]
        if st.checkbox("Pause log", value=paused, key=f"pause-{name}"):
            st.session_state[SESSION_LOG_PAUSE_KEY].add(name)
        else:
            st.session_state[SESSION_LOG_PAUSE_KEY].discard(name)
        log_limit = st.slider("Lines", min_value=20, max_value=400, value=100, key=f"log-limit-{name}")
        if not paused:
            logs = _service_log_lines(name, limit=log_limit)
        else:
            logs = st.session_state.get(f"log-cache-{name}", _service_log_lines(name, limit=log_limit))
        st.session_state[f"log-cache-{name}"] = logs
        st.code("\n".join(logs) if logs else "(no output yet)", language="text")

    if conflict:
        _render_conflict_panel(name, conflict)


def _render_launch_tab() -> None:
    env = _env()
    core_port = int(env.get("core_port", 8015))
    react_port = int(env.get("react_port", REACT_DEFAULT_PORT))
    streamlit_port = int(env.get("streamlit_port", STREAMLIT_DEFAULT_PORT))
    ucnrr_port = int(env.get("ucnrr_port", 8011))
    core_workdir_path = _resolve_core_workdir(env)
    react_workdir_path = _resolve_react_workdir(env)
    ucnrr_workdir_path = Path(str(env.get("ucnrr_workdir") or ROOT)).expanduser().resolve(strict=False)
    react_npm_cmd = _resolve_react_npm(env)
    core_command_list = _core_start_command_list(env)

    st.subheader("One-click Demo Launcher")
    workspace_label = str(env.get("WORKSPACE_LABEL") or "Workspace")
    workspace_root = str(env.get("WORKSPACE_ROOT") or "")
    workspace_caption = workspace_root if workspace_root else "(path not set)"
    st.caption(f"Workspace: {workspace_label} · {workspace_caption}")
    action_summary = _consume_action_result()
    if action_summary:
        _render_action_summary(action_summary)

    active_user_key = SESSION_ACTIVE_USER_INPUT_KEY
    default_active_user = _active_user()
    _ensure_state(active_user_key, default_active_user)

    def _on_active_user_change() -> None:
        raw_value = str(st.session_state.get(active_user_key, "") or "")
        sanitized_value = raw_value.strip()
        if sanitized_value:
            if sanitized_value != _active_user():
                _set_active_user(sanitized_value)
            if sanitized_value != raw_value:
                st.session_state[active_user_key] = sanitized_value
        else:
            fallback_value = _active_user()
            if fallback_value != raw_value:
                st.session_state[active_user_key] = fallback_value

    user_input_col, open_folder_col = st.columns([4, 1])
    with user_input_col:
        st.text_input(
            "Active user ID",
            key=active_user_key,
            help="Used by demo utilities (seeding asks/nudges, probes).",
            on_change=_on_active_user_change,
        )

    raw_active_user = str(st.session_state.get(active_user_key, "") or "")
    sanitized_active_user = raw_active_user.strip()
    if sanitized_active_user:
        if sanitized_active_user != _active_user():
            _set_active_user(sanitized_active_user)
        active_user = sanitized_active_user
    else:
        active_user = _active_user()

    with open_folder_col:
        st.write("")  # Spacing
        st.write("")  # Spacing to align button
        if st.button("📁 Open Folder", key="open-user-folder", help="Open user's data folder in Finder/Explorer"):
            workspace_root = str(env.get("WORKSPACE_ROOT") or ROOT)
            user_folder = Path(workspace_root) / "data" / "users" / active_user

            if user_folder.exists():
                try:
                    if sys.platform == "darwin":  # macOS
                        subprocess.run(["open", str(user_folder)], check=True)
                    elif sys.platform == "win32":  # Windows
                        subprocess.run(["explorer", str(user_folder)], check=True)
                    else:  # Linux
                        subprocess.run(["xdg-open", str(user_folder)], check=True)
                    st.success(f"Opened folder for user: {active_user}")
                except Exception as exc:
                    st.error(f"Failed to open folder: {exc}")
            else:
                st.warning(f"User folder not found: {user_folder}")

    seed_feedback = st.empty()

    def _trigger_seed(kind: str, label: str) -> None:
        endpoint = f"http://127.0.0.1:{core_port}/ui/{kind}/seed"
        try:
            response = requests.post(endpoint, params={"user_id": active_user}, timeout=10)
        except requests.RequestException as exc:
            seed_feedback.error(f"Failed to seed {label.lower()}: {exc}")
            return

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {}
            message = ""
            if isinstance(detail, dict):
                message = str(detail.get("message") or detail.get("detail") or "").strip()
            if not message:
                message = response.text.strip() or f"HTTP {response.status_code}"
            seed_feedback.error(f"{label} seed failed: {message}")
            return

        try:
            payload = response.json()
        except Exception:
            payload = {}

        count: Optional[int]
        created: Optional[bool]
        if isinstance(payload, dict):
            count = payload.get("count") if isinstance(payload.get("count"), int) else None
            created = payload.get("created") if isinstance(payload.get("created"), bool) else None
        else:
            count = None
            created = None

        if created:
            base_msg = f"Seeded {label.lower()} for {active_user}"
        else:
            base_msg = f"{label} already present for {active_user}"
        if count is not None:
            base_msg = f"{base_msg} ({count} items)"
        seed_feedback.success(base_msg)

    seed_cols = st.columns(2)
    with seed_cols[0]:
        if st.button("Seed Asks for active user", key="seed-asks"):
            _trigger_seed("asks", "Asks")
    with seed_cols[1]:
        if st.button("Seed Nudges for active user", key="seed-nudges"):
            _trigger_seed("nudges", "Nudges")

    # Holistic Review section
    st.markdown("---")
    holistic_feedback = st.empty()
    holistic_result_container = st.container()

    if st.button("🔄 Run Holistic Review", key="holistic-review", help="Recalculate RR and Curiosity for all traits of active user"):
        endpoint = f"http://127.0.0.1:{core_port}/ui/holistic/review"
        try:
            response = requests.post(endpoint, json={"user_id": active_user}, timeout=30)
        except requests.RequestException as exc:
            holistic_feedback.error(f"Failed to trigger holistic review: {exc}")
        else:
            if response.status_code >= 400:
                try:
                    detail = response.json()
                except Exception:
                    detail = {}
                message = ""
                if isinstance(detail, dict):
                    message = str(detail.get("message") or detail.get("detail") or "").strip()
                if not message:
                    message = response.text.strip() or f"HTTP {response.status_code}"
                holistic_feedback.error(f"Holistic review failed: {message}")
            else:
                try:
                    result = response.json()
                except Exception:
                    result = {}

                if result.get("ok"):
                    traits_updated = result.get("traits_updated", 0)
                    global_curiosity = result.get("global_curiosity", 0.0)
                    holistic_feedback.success(
                        f"✅ Holistic Review completed for {active_user}: "
                        f"{traits_updated} traits updated, "
                        f"global curiosity: {global_curiosity:.2%}"
                    )

                    # Display summary in expander
                    with holistic_result_container:
                        with st.expander("📊 Review Details", expanded=True):
                            st.json(result)
                else:
                    error_msg = result.get("message") or result.get("error") or "Unknown error"
                    holistic_feedback.error(f"Holistic review failed: {error_msg}")

    st.markdown("---")
    col_launch, col_open, col_stop, col_reset = st.columns(4)
    launch_disabled = _is_env_dirty() or bool(_start_locks())
    with col_launch:
        if st.button(
            "Launch All",
            help="Start UCN/RR, Core, and React using current environment",
            disabled=launch_disabled,
        ):
            _update_next_public_base()
            _setup_auto_open_targets()
            # Start UCNRR first (Core depends on it)
            _handle_start_request(
                SERVICE_UCNRR,
                "UCN/RR",
                _ucnrr_command(env, ucnrr_port),
                ucnrr_workdir_path,
                _ucnrr_env(env),
                ucnrr_port,
                (8011, 8025),
            )
            _handle_start_request(
                SERVICE_CORE,
                "Core (uvicorn)",
                list(core_command_list or []),
                core_workdir_path,
                _core_env(env),
                core_port,
                CORE_PORT_RANGE,
                expected_core=True,
            )
            _handle_start_request(
                SERVICE_REACT,
                "React (Next.js)",
                _react_command(react_npm_cmd),
                react_workdir_path,
                _react_env(env),
                react_port,
                REACT_PORT_RANGE,
            )
            if env.get("AUTO_OPEN_DEVEXPLORER_AFTER_LAUNCH"):
                # Open DevX (new React frontend) instead of old Dev Explorer
                devx_url = "http://localhost:3100"
                _open_ui(devx_url, "DevX", notify=False)
    with col_open:
        st.caption("Open UIs")
        _render_open_button(SERVICE_REACT, "Open React")
        # Open DevX (new React frontend on port 3100) instead of old Dev Explorer
        devx_url = "http://localhost:3100"
        if st.button("Open DevX", key="open-devx-ui"):
            _open_ui(devx_url, "DevX", notify=False)
        core_base_url = _build_service_url(SERVICE_CORE)
        docs_url = f"{core_base_url}docs" if core_base_url else None
        if st.button("Open Core Docs", key="open-core-docs", disabled=docs_url is None):
            _open_ui(docs_url, "Core Docs", notify=False)
        ucnrr_url = _build_service_url(SERVICE_UCNRR)
        if st.button("Open UCN/RR", key="open-ucnrr-base", disabled=ucnrr_url is None):
            _open_ui(ucnrr_url, "UCN/RR base")
    with col_stop:
        if st.button("Stop All"):
            _stop_all_services()
    with col_reset:
        if st.button(
            "🔄 RESET ALL",
            help="Stop all services, wait, then restart in correct order: Core → UCN/RR → React",
            type="primary",
        ):
            # Perform the exact sequence: Stop Core, Stop UCN/RR, Stop React, then restart in order
            st.info("Stopping Core...")
            _stop_service(SERVICE_CORE, rerun=False)
            time.sleep(1)

            st.info("Stopping UCN/RR...")
            _stop_service(SERVICE_UCNRR, rerun=False)
            time.sleep(1)

            st.info("Stopping React...")
            _stop_service(SERVICE_REACT, rerun=False)
            time.sleep(2)

            st.info("Starting Core (waiting for it to load)...")
            _handle_start_request(
                SERVICE_CORE,
                "Core (uvicorn)",
                list(core_command_list or []),
                core_workdir_path,
                _core_env(env),
                core_port,
                CORE_PORT_RANGE,
                expected_core=True,
            )
            time.sleep(3)  # Give Core time to start

            st.info("Starting UCN/RR...")
            _handle_start_request(
                SERVICE_UCNRR,
                "UCN/RR",
                _ucnrr_command(env, ucnrr_port),
                ucnrr_workdir_path,
                _ucnrr_env(env),
                ucnrr_port,
                (8011, 8025),
            )
            time.sleep(2)

            st.info("Starting React...")
            _handle_start_request(
                SERVICE_REACT,
                "React (Next.js)",
                _react_command(react_npm_cmd),
                react_workdir_path,
                _react_env(env),
                react_port,
                REACT_PORT_RANGE,
            )

            st.success("✅ All services reset and restarted!")
            time.sleep(1)
            safe_rerun()

    st.markdown("---")
    st.subheader("Service Controls")
    st.caption("Recommended start order: UCN/RR → Core → React")

    _render_service_row(
        SERVICE_UCNRR,
        "UCN/RR",
        _ucnrr_command(env, ucnrr_port),
        ucnrr_workdir_path,
        _ucnrr_env(env),
        ucnrr_port,
        (8011, 8025),
    )
    _render_service_row(
        SERVICE_CORE,
        "Core (uvicorn)",
        list(core_command_list or []),
        core_workdir_path,
        _core_env(env),
        core_port,
        CORE_PORT_RANGE,
        expected_core=True,
    )
    _render_service_row(
        SERVICE_REACT,
        "React (Next.js)",
        _react_command(react_npm_cmd),
        react_workdir_path,
        _react_env(env),
        react_port,
        REACT_PORT_RANGE,
    )
    # Streamlit HC v2 hidden - not in use


def _validate_provider() -> Dict[str, Any]:
    env = _env()
    provider = str(env.get("HC_CHAT_PROVIDER", "stub") or "stub").strip().lower()
    if provider in {"", "stub"}:
        return {"status": "PASS", "message": "Stub provider active (no external call required)."}

    if provider == "openai":
        api_key = (env.get("OPENAI_API_KEY") or "").strip()
        model = (env.get("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
        if not api_key:
            return {"status": "FAIL", "message": "OPENAI_API_KEY is missing."}
        try:
            response = requests.get(
                f"https://api.openai.com/v1/models/{model}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                owned = data.get("owned_by")
                msg = f"OpenAI model '{model}' reachable."
                if owned:
                    msg += f" Owner: {owned}."
                return {"status": "PASS", "message": msg}
            detail = response.text[:200]
            return {
                "status": "FAIL",
                "message": f"OpenAI returned HTTP {response.status_code}.",
                "detail": detail,
            }
        except requests.exceptions.Timeout:
            return {"status": "FAIL", "message": "OpenAI request timed out."}
        except Exception as exc:
            return {"status": "FAIL", "message": str(exc)}

    if provider == "ollama":
        base = (env.get("OLLAMA_BASE") or "http://127.0.0.1:11434").strip().rstrip("/")
        model = (env.get("OLLAMA_MODEL") or "llama3.1:8b").strip()
        if not base:
            return {"status": "FAIL", "message": "OLLAMA_BASE is missing."}

        # Check if Ollama is reachable
        try:
            response = requests.get(f"{base}/api/version", timeout=5)
            if response.status_code != 200:
                detail = response.text[:200]
                return {
                    "status": "FAIL",
                    "message": f"Ollama returned HTTP {response.status_code}.",
                    "detail": detail,
                }
            version = None
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    version = response.json().get("version")
                except Exception:
                    version = None
        except requests.exceptions.Timeout:
            return {"status": "FAIL", "message": "Ollama request timed out. Is 'ollama serve' running?"}
        except requests.exceptions.ConnectionError:
            return {
                "status": "FAIL",
                "message": "Cannot connect to Ollama. Install: 'brew install ollama' and run 'ollama serve'."
            }
        except Exception as exc:
            return {"status": "FAIL", "message": str(exc)}

        # Check if model is available
        try:
            response = requests.get(f"{base}/api/tags", timeout=5)
            if response.status_code == 200 and response.headers.get("content-type", "").startswith("application/json"):
                tags_data = response.json()
                models = tags_data.get("models", [])
                model_names = [m.get("name") for m in models if isinstance(m, dict)]
                if model not in model_names:
                    return {
                        "status": "MODEL_MISSING",
                        "message": f"Model '{model}' not found. Use 'Pull Model' button below.",
                        "model": model,
                        "available_models": model_names,
                    }
        except Exception:
            pass

        msg = "Ollama reachable."
        if version:
            msg = f"Ollama reachable (version {version})."
        if model:
            msg += f" Model: {model}"
        return {"status": "PASS", "message": msg}

    if provider == "anthropic":
        api_key = (env.get("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            return {"status": "WARN", "message": "ANTHROPIC_API_KEY is missing (stub provider will be used)."}
        return {"status": "PASS", "message": "Anthropic provider configured (stub only for now)."}

    return {"status": "FAIL", "message": f"Unknown provider '{provider}'."}


def _run_provider_check_cli() -> int:
    result = _validate_provider()
    print(json.dumps(result, indent=2))
    status = str(result.get("status", "")).strip().upper()
    return 0 if status == "PASS" else 1


def _render_env_tab() -> None:
    env = _env()
    detected_ports = st.session_state.get(SESSION_DETECTED_PORTS_KEY, {})
    react_detected = detected_ports.get(SERVICE_REACT)
    core_detected = detected_ports.get(SERVICE_CORE)
    ucnrr_detected = detected_ports.get(SERVICE_UCNRR)
    raw_frontend_flags = str(env.get("NEXT_PUBLIC_FLAGS", "") or "")
    frontend_flag_values, frontend_passthrough = _parse_frontend_flag_string(raw_frontend_flags)
    st.subheader("Environment & Flags")
    if _is_env_dirty():
        st.warning("Environment changes pending Save.")
    with st.form("env-form"):
        st.markdown("### Core (uvicorn)")
        core_workdir_input = st.text_input(
            "Core working dir",
            value=str(env.get("core_workdir") or ROOT),
            help="Directory where the Core process should start.",
        )
        core_start_command_input = st.text_input(
            "Core start command",
            value=str(
                env.get("core_start_command")
                or envstore.DEFAULT_ENV.get("core_start_command", "uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8015")
            ),
            help="Full command executed for Core (uvicorn).",
        )
        st.caption("Ensure the command's --port matches the Core port configured below.")
        saved_core_port = int(env.get("core_port", 8015))
        core_port = st.number_input("Core port", value=saved_core_port, min_value=1000, max_value=65000)
        if isinstance(core_detected, int) and core_detected != saved_core_port:
            st.caption(f"Detected Core listener on port {core_detected} during health scan.")

        st.markdown("### React (Next.js)")
        saved_react_port = int(env.get("react_port", REACT_DEFAULT_PORT))
        react_port = st.number_input("React (Next.js) port", value=saved_react_port, min_value=1000, max_value=65000)
        if isinstance(react_detected, int) and react_detected != saved_react_port:
            st.caption(
                f"Detected React on port {react_detected}; your saved config is {saved_react_port}."
            )
        streamlit_port = st.number_input(
            "Streamlit port",
            value=int(env.get("streamlit_port", STREAMLIT_DEFAULT_PORT)),
            min_value=1000,
            max_value=65000,
        )
        streamlit_photo_port = st.number_input(
            "Streamlit (Photo coach) port",
            value=int(env.get("streamlit_photo_port", STREAMLIT_DEFAULT_PORT)),
            min_value=1000,
            max_value=65000,
        )
        streamlit_padna_port = st.number_input(
            "Streamlit (PaDNA coach) port",
            value=int(env.get("streamlit_padna_port", STREAMLIT_DEFAULT_PORT + 1)),
            min_value=1000,
            max_value=65000,
        )
        st.markdown("### UCN/RR")
        ucnrr_workdir_input = st.text_input(
            "UCN/RR working dir",
            value=str(env.get("ucnrr_workdir") or ROOT),
            help="Directory where the UCN/RR process should start (usually repo root).",
        )
        ucnrr_start_command_input = st.text_input(
            "UCN/RR start command",
            value=str(
                env.get("ucnrr_start_command")
                or envstore.DEFAULT_ENV.get("ucnrr_start_command", f"{ROOT / '.venv' / 'bin' / 'python'} -m uvicorn ucnrr_app:app --host 0.0.0.0 --port {{port}} --reload")
            ),
            help="Full command executed for UCN/RR (use {port} placeholder).",
        )
        st.caption("Ensure the command's --port uses {port} placeholder to match configured port.")
        ucnrr_port = st.number_input(
            "UCN/RR port",
            value=int(env.get("ucnrr_port", 8011)),
            min_value=1000,
            max_value=65000,
        )
        ucnrr_port_value = int(ucnrr_port)
        if isinstance(ucnrr_detected, int) and ucnrr_detected != ucnrr_port_value:
            st.caption(
                f"Detected UCN/RR listener on port {ucnrr_detected}; your saved config is {ucnrr_port_value}."
            )

        st.markdown("### React (Next.js)")
        react_workdir_input = st.text_input(
            "React working dir",
            value=str(env.get("react_workdir") or (ROOT / "web")),
            help="Directory for Next.js dev server (usually repo/web).",
        )
        react_npm_path_input = st.text_input(
            "React npm path (optional)",
            value=str(env.get("react_npm_path") or ""),
            help="Provide an absolute npm path if not on PATH.",
        )

        default_workspace_root = str(env.get("WORKSPACE_ROOT") or envstore.DEFAULT_ENV.get("WORKSPACE_ROOT") or ROOT)
        workspace_root_input = st.text_input("WORKSPACE_ROOT", value=default_workspace_root)
        workspace_label_input = st.text_input(
            "Workspace label",
            value=str(env.get("WORKSPACE_LABEL") or envstore.DEFAULT_ENV.get("WORKSPACE_LABEL") or "Workspace"),
        )

        hc_chat = st.toggle("HC_CHAT_ENABLED", value=bool(env.get("HC_CHAT_ENABLED", True)))
        hc_stream = st.toggle("HC_CHAT_STREAM_ENABLED", value=bool(env.get("HC_CHAT_STREAM_ENABLED", True)))
        ask_actions = st.toggle("HC_ASK_ACTIONS_ENABLED", value=bool(env.get("HC_ASK_ACTIONS_ENABLED", True)))
        curiosity_enabled = st.toggle("Enable Curiosity System", value=bool(env.get("CORE_CURIOSITY_ENABLED", True)))

        next_public = st.text_input(
            "NEXT_PUBLIC_CORE_API_BASE",
            value=str(env.get("NEXT_PUBLIC_CORE_API_BASE", f"http://127.0.0.1:{core_port}")),
        )
        if isinstance(core_detected, int):
            detected_base = f"http://127.0.0.1:{core_detected}"
            if next_public.strip() != detected_base:
                st.caption(
                    f"Core health detected at {detected_base}; update this value if you want React to target it."
                )
            else:
                st.caption("NEXT_PUBLIC_CORE_API_BASE matches the detected Core listener.")

        provider_options = ["ollama", "openai", "anthropic", "stub"]
        current_provider = str(env.get("HC_CHAT_PROVIDER", "ollama") or "ollama")
        provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
        chat_provider = st.selectbox("HC_CHAT_PROVIDER", options=provider_options, index=provider_index)

        st.markdown("#### Ollama (local LLM)")
        ollama_base_input = st.text_input(
            "OLLAMA_BASE",
            value=str(env.get("OLLAMA_BASE") or "http://127.0.0.1:11434"),
        )
        ollama_model_input = st.text_input(
            "OLLAMA_MODEL",
            value=str(env.get("OLLAMA_MODEL") or "llama3.1:8b"),
        )

        st.markdown("#### OpenAI (paid)")
        openai_key_input = st.text_input(
            "OPENAI_API_KEY",
            value=str(env.get("OPENAI_API_KEY") or ""),
            type="password",
        )
        openai_model_input = st.text_input(
            "OPENAI_MODEL",
            value=str(env.get("OPENAI_MODEL") or "gpt-4o-mini"),
        )

        st.markdown("#### Anthropic (paid, stub only)")
        anthropic_key_input = st.text_input(
            "ANTHROPIC_API_KEY",
            value=str(env.get("ANTHROPIC_API_KEY") or ""),
            type="password",
        )
        anthropic_model_input = st.text_input(
            "ANTHROPIC_MODEL",
            value=str(env.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest"),
        )

        current_ucnrr = env.get("UCNRR_BASE_URL")
        default_ucnrr = current_ucnrr if isinstance(current_ucnrr, str) and current_ucnrr else "http://127.0.0.1:8011"
        ucnrr_base_input = st.text_input("UCNRR_BASE_URL", value=default_ucnrr)

        auto_open_react = st.toggle(
            "Auto-open React after Launch All",
            value=bool(env.get("AUTO_OPEN_REACT_AFTER_LAUNCH", False)),
        )
        auto_open_streamlit = st.toggle(
            "Auto-open Streamlit after Launch All",
            value=bool(env.get("AUTO_OPEN_STREAMLIT_AFTER_LAUNCH", False)),
        )
        auto_open_dev = st.toggle(
            "Auto-open Dev Explorer after Launch All",
            value=bool(env.get("AUTO_OPEN_DEVEXPLORER_AFTER_LAUNCH", False)),
        )
        append_debug = st.toggle(
            "Append ?ui_debug=1 when opening UIs",
            value=bool(env.get("APPEND_UI_DEBUG_PARAM", False)),
        )
        dev_port_input = st.text_input(
            "Dev Explorer port (optional)",
            value=str(env.get("dev_explorer_port") or ""),
        )

        st.markdown("#### Frontend feature flags")
        st.caption("Controls experimental UI behavior in the React app.")
        avatar_flag_checkbox = st.checkbox(
            "Animated coach avatar",
            value=frontend_flag_values.get("avatar", False),
            key="env-flag-avatar",
        )
        avatar_debug_checkbox = st.checkbox(
            "Avatar debug labels",
            value=frontend_flag_values.get("avatarDebug", False),
            key="env-flag-avatar-debug",
        )

        submitted = st.form_submit_button("Save")
        if submitted:
            dev_port_value = None
            dev_port_raw = dev_port_input.strip()
            if dev_port_raw:
                try:
                    dev_port_value = int(dev_port_raw)
                except ValueError:
                    st.error("Dev Explorer port must be an integer.")
                    return
            openai_key_value = openai_key_input.strip() or None
            openai_model_value = openai_model_input.strip() or None
            ollama_base_value = ollama_base_input.strip() or None
            ollama_model_value = ollama_model_input.strip() or None
            anthropic_key_value = anthropic_key_input.strip() or None
            anthropic_model_value = anthropic_model_input.strip() or None
            ucnrr_base_value = ucnrr_base_input.strip() or None
            core_workdir_value = core_workdir_input.strip() or str(ROOT)
            core_start_command_value = core_start_command_input.strip()
            ucnrr_workdir_value = ucnrr_workdir_input.strip() or str(ROOT)
            ucnrr_start_command_value = ucnrr_start_command_input.strip()
            react_workdir_value = react_workdir_input.strip() or str(ROOT / "web")
            react_npm_value = react_npm_path_input.strip()
            env.update(
                {
                    "core_port": int(core_port),
                    "react_port": int(react_port),
                    "streamlit_port": int(streamlit_port),
                    "streamlit_photo_port": int(streamlit_photo_port),
                    "streamlit_padna_port": int(streamlit_padna_port),
                    "ucnrr_port": ucnrr_port_value,
                    "core_workdir": core_workdir_value,
                    "core_start_command": core_start_command_value,
                    "ucnrr_workdir": ucnrr_workdir_value,
                    "ucnrr_start_command": ucnrr_start_command_value,
                    "react_workdir": react_workdir_value,
                    "react_npm_path": react_npm_value,
                    "HC_CHAT_ENABLED": bool(hc_chat),
                    "HC_CHAT_STREAM_ENABLED": bool(hc_stream),
                    "HC_ASK_ACTIONS_ENABLED": bool(ask_actions),
                    "CORE_CURIOSITY_ENABLED": bool(curiosity_enabled),
                    "NEXT_PUBLIC_CORE_API_BASE": next_public.strip() or f"http://127.0.0.1:{int(core_port)}",
                    "HC_CHAT_PROVIDER": chat_provider,
                    "OPENAI_API_KEY": openai_key_value,
                    "OPENAI_MODEL": openai_model_value,
                    "OLLAMA_BASE": ollama_base_value,
                    "OLLAMA_MODEL": ollama_model_value,
                    "ANTHROPIC_API_KEY": anthropic_key_value,
                    "ANTHROPIC_MODEL": anthropic_model_value,
                    "UCNRR_BASE_URL": ucnrr_base_value,
                    "AUTO_OPEN_REACT_AFTER_LAUNCH": bool(auto_open_react),
                    "AUTO_OPEN_STREAMLIT_AFTER_LAUNCH": bool(auto_open_streamlit),
                    "AUTO_OPEN_DEVEXPLORER_AFTER_LAUNCH": bool(auto_open_dev),
                    "APPEND_UI_DEBUG_PARAM": bool(append_debug),
                    "dev_explorer_port": dev_port_value,
                    "WORKSPACE_ROOT": workspace_root_input.strip() or default_workspace_root,
                    "WORKSPACE_LABEL": workspace_label_input.strip() or envstore.DEFAULT_ENV.get("WORKSPACE_LABEL", "Workspace"),
                    "NEXT_PUBLIC_FLAGS": _serialize_frontend_flags(
                        {
                            **frontend_flag_values,
                            "avatar": bool(avatar_flag_checkbox),
                            "avatarDebug": bool(avatar_debug_checkbox),
                        },
                        frontend_passthrough,
                    ),
                }
            )
            _save_env()
            st.success("Environment saved.")

    validation_cols = st.columns([1, 3])
    with validation_cols[0]:
        if st.button("Validate provider", key="validate-provider"):
            with st.spinner("Checking provider configuration…"):
                result = _validate_provider()
            _set_provider_validation(result)
    with validation_cols[1]:
        validation = _get_provider_validation()
        if validation:
            status = validation.get("status")
            message = validation.get("message", "")
            detail = validation.get("detail")
            if status == "PASS":
                st.success(message)
            elif status == "MODEL_MISSING":
                st.warning(message)
                model = validation.get("model")
                if model and st.button(f"Pull Model: {model}", key="pull-ollama-model"):
                    with st.spinner(f"Pulling {model}... This may take several minutes."):
                        try:
                            result = subprocess.run(
                                ["ollama", "pull", model],
                                capture_output=True,
                                text=True,
                                timeout=600,
                            )
                            if result.returncode == 0:
                                st.success(f"Successfully pulled {model}")
                                # Re-validate
                                new_result = _validate_provider()
                                _set_provider_validation(new_result)
                                safe_rerun()
                            else:
                                st.error(f"Failed to pull model: {result.stderr}")
                        except subprocess.TimeoutExpired:
                            st.error("Model pull timed out after 10 minutes.")
                        except FileNotFoundError:
                            st.error("'ollama' command not found. Install: brew install ollama")
                        except Exception as exc:
                            st.error(f"Error: {exc}")
                if detail:
                    st.caption(detail)
            elif status == "WARN":
                st.warning(message)
                if detail:
                    st.caption(detail)
            else:
                st.error(message)
                if detail:
                    st.caption(detail)
        else:
            st.caption("Validate provider credentials to ensure streaming works before demos.")

    st.caption("Settings are stored in .cpplusplus_env.json at the repository root.")


def _render_profiles_tab() -> None:
    profiles_state = dict(_profiles())
    pending_notice = st.session_state.get(SESSION_PROFILE_NOTICE_KEY)
    if pending_notice:
        st.success(pending_notice)
        _set_profile_notice(None)
    profile_names = sorted(profiles_state.keys())
    placeholder = "(select profile)"
    options = [placeholder] + profile_names

    current_selected = _selected_profile()
    try:
        default_index = options.index(current_selected) if current_selected else 0
    except ValueError:
        default_index = 0

    selection = st.selectbox(
        "Saved profiles",
        options=options,
        index=default_index,
        key="profiles_select",
    )
    selected_name = "" if selection == placeholder else selection
    _set_selected_profile(selected_name)

    st.caption(f"Profiles stored at `{envstore.PROFILES_PATH}`")

    name_key = "profiles_name_input"
    if name_key not in st.session_state:
        st.session_state[name_key] = ""
    st.text_input("Profile name", key=name_key, placeholder="e.g. Demo setup")

    col_save, col_apply, col_delete = st.columns([1, 1, 1])

    if col_save.button("Save / Update", key="profiles_save_btn"):
        profile_name = st.session_state.get(name_key, "").strip()
        if not profile_name:
            st.error("Enter a profile name to save.")
        else:
            new_profiles = dict(_profiles())
            new_profiles[profile_name] = dict(_env())
            envstore.save_profiles(new_profiles)
            _set_profiles(new_profiles)
            _set_selected_profile(profile_name)
            st.session_state[name_key] = profile_name
            _set_profile_notice(f"Saved profile '{profile_name}'.")
            safe_rerun()

    if col_apply.button("Apply to Environment", key="profiles_apply_btn", disabled=not selected_name):
        profile_env = profiles_state.get(selected_name)
        if profile_env is None:
            st.error("Selected profile not found.")
        else:
            merged = envstore.DEFAULT_ENV.copy()
            merged.update(profile_env)
            env = _env()
            env.clear()
            env.update(merged)
            _set_env_dirty(True)
            _set_profile_notice(f"Profile '{selected_name}' applied. Save Environment to persist.")
            safe_rerun()

    if col_delete.button("Delete", key="profiles_delete_btn", disabled=not selected_name):
        new_profiles = dict(_profiles())
        if selected_name in new_profiles:
            new_profiles.pop(selected_name, None)
            envstore.save_profiles(new_profiles)
            _set_profiles(new_profiles)
            _set_selected_profile("")
            _set_profile_notice(f"Deleted profile '{selected_name}'.")
            safe_rerun()

    if selected_name:
        st.markdown("#### Preview")
        st.json(profiles_state.get(selected_name, {}), expanded=False)
    elif profiles_state:
        st.caption("Select a profile to preview or apply.")
    else:
        st.caption("No profiles saved yet. Configure the Environment tab, then save it here.")


def _render_health_tab() -> None:
    env = _env()

    st.subheader("Health Checks")
    notice = st.session_state.get(SESSION_HEALTH_NOTICE_KEY)
    if notice:
        st.success(notice)
        _set_health_notice(None)
    if st.button("Refresh health", key="refresh-health"):
        _refresh_health()

    raw_results = st.session_state.get(SESSION_HEALTH_KEY, {})
    if not isinstance(raw_results, dict) or not all(isinstance(v, ServiceHealth) for v in raw_results.values()):
        results = _refresh_health()
    else:
        results = raw_results

    st.caption("Legend: 🟢 managed · 🔵 external · ⚪️ stopped")

    pending_kill = st.session_state.get(SESSION_HEALTH_PENDING_KILL_KEY)
    if isinstance(pending_kill, dict) and pending_kill.get("service"):
        label = pending_kill.get("label") or pending_kill["service"]
        pid = pending_kill.get("pid")
        port = pending_kill.get("port")
        warning_msg = f"Kill '{label}' (PID {pid or '—'} on port {port or '—'})? This was started by CP++."
        st.warning(warning_msg)
        confirm_cols = st.columns([1, 1])
        with confirm_cols[0]:
            if st.button("Confirm kill", key="confirm-kill"):
                summary = _kill_managed_service(pending_kill["service"])
                st.session_state[SESSION_HEALTH_PENDING_KILL_KEY] = None
                if summary:
                    _set_action_result(summary)
                _refresh_health()
                safe_rerun()
        with confirm_cols[1]:
            if st.button("Cancel", key="cancel-kill"):
                st.session_state[SESSION_HEALTH_PENDING_KILL_KEY] = None
                safe_rerun()

    core_health = results.get(SERVICE_CORE)
    env_base = str(env.get("NEXT_PUBLIC_CORE_API_BASE", "")).strip()
    if env_base:
        st.caption(f"NEXT_PUBLIC_CORE_API_BASE = `{env_base}`")
    if core_health and core_health.port:
        expected_base = f"http://127.0.0.1:{core_health.port}"
        if env_base and env_base != expected_base:
            st.warning(
                f"Core health running at {expected_base}; update NEXT_PUBLIC_CORE_API_BASE to match."
            )

    labels = {
        "cpplusplus": "CP++ (self)",
        SERVICE_CORE: "Core (uvicorn)",
        SERVICE_REACT: "React (Next.js)",
        SERVICE_STREAMLIT: "Streamlit HC v2",
        SERVICE_UCNRR: "UCN/RR",
    }
    order = ["cpplusplus", SERVICE_CORE, SERVICE_REACT, SERVICE_STREAMLIT, SERVICE_UCNRR]

    for name in order:
        health = results.get(name)
        if not health:
            continue
        _render_health_card(health, labels.get(name, name.title()))


def _render_ports_tab() -> None:
    st.subheader("Port Scanner & Cleanup")
    react_range = list(range(3000, 3006))
    streamlit_range = list(range(STREAMLIT_PORT_RANGE[0], STREAMLIT_PORT_RANGE[1] + 1))
    label_ranges = {"react": react_range, "streamlit": streamlit_range}
    with st.spinner("Scanning ports..."):
        react_entries, react_errors = ports.scan_ports("react", react_range)
        streamlit_entries, streamlit_errors = ports.scan_ports("streamlit", streamlit_range)

    def _record_result(label: str, summary: Dict[str, Any]) -> None:
        st.session_state["_port_cleanup_result"] = summary
        # Refresh cached state so a rerun immediately reflects the latest view.
        for lbl, rng in label_ranges.items():
            ports.scan_ports(lbl, rng)
        safe_rerun()

    def render_table(
        title: str,
        label: str,
        entries: List[ports.PortProcess],
        errors: List[str],
    ) -> None:
        header_cols = st.columns([6, 1])
        header_cols[0].write(f"### {title}")
        if errors:
            summary_html = "<br/>".join(html.escape(err) for err in errors)
            tooltip = (
                "<details><summary>⚠️</summary><small>"
                f"{summary_html}" "</small></details>"
            )
            header_cols[1].markdown(tooltip, unsafe_allow_html=True)
        else:
            header_cols[1].write("")

        if not entries:
            if any("Port scan requires" in err for err in errors):
                st.info("Port scan requires lsof or psutil capabilities on this platform.")
            else:
                st.info("No listeners detected in the monitored range.")
            return

        header_cols = st.columns([1, 1, 5, 1])
        header_cols[0].markdown("**Port**")
        header_cols[1].markdown("**PID**")
        header_cols[2].markdown("**Command**")
        header_cols[3].markdown("**Kill**")

        for entry in entries:
            row_cols = st.columns([1, 1, 5, 1])
            row_cols[0].write(entry.port)
            row_cols[1].write(entry.pid)
            row_cols[2].code(entry.cmdline or entry.name, language="text")
            with row_cols[3]:
                if st.button("🗑", key=f"kill-{label}-{entry.pid}", help="Terminate this process"):
                    result = ports.kill_single(label, entry.pid)
                    _record_result(label, result)

    render_table("React (3000-3005)", "react", react_entries, react_errors)
    render_table(
        f"Streamlit ({STREAMLIT_PORT_RANGE[0]}-{STREAMLIT_PORT_RANGE[1]})",
        "streamlit",
        streamlit_entries,
        streamlit_errors,
    )

    cols = st.columns(2)
    with cols[0]:
        if st.button("Kill all React dev servers"):
            result = ports.kill_cached("react")
            _record_result("react", result)
    with cols[1]:
        if st.button("Kill all Streamlit servers"):
            result = ports.kill_cached("streamlit")
            _record_result("streamlit", result)

    if "_port_cleanup_result" in st.session_state:
        summary = st.session_state.pop("_port_cleanup_result")
        status = summary.get("status")
        if status == "empty":
            st.info("Nothing to kill (rescan first).")
        else:
            terminated = summary.get("terminated", [])
            already = summary.get("already_dead", [])
            errors: Dict[int, str] = summary.get("errors", {})  # type: ignore[arg-type]
            msg = f"Terminated: {len(terminated)}, Already gone: {len(already)}, Errors: {len(errors)}."
            if errors:
                st.warning(msg)
                error_lines = "\n".join(f"PID {pid}: {err}" for pid, err in errors.items())
                if error_lines:
                    st.code(error_lines, language="text")
            elif terminated:
                st.success(msg)
            else:
                st.info(msg)


def _run_test(name: str, command: List[str], cwd: Optional[Path]) -> None:
    proc_map = _tests()
    if name in proc_map and proc_map[name].is_running():
        st.warning(f"{name} already running (pid={proc_map[name].pid()}).")
        return
    try:
        proc_map[name] = services.start_service(name, command, cwd=cwd, env={}, capture_output=True)
        st.success(f"Started {name} (pid={proc_map[name].pid()}).")
    except FileNotFoundError:
        st.error(f"Missing executable required for {name}.")
    except Exception as exc:
        st.error(f"Failed to start {name}: {exc}")


def _run_chat_probe() -> None:
    env = _env()
    core_port = int(env.get("core_port", 8015))
    url = f"http://127.0.0.1:{core_port}/ui/chat/send?stream=1"
    payload = {
        "user_id": "TEST",
        "persona": "head coach",
        "text": "Hello from CP++ health probe.",
        "client_ts": int(time.time() * 1000),
    }
    try:
        with requests.post(url, json=payload, stream=True, timeout=20) as response:
            if response.status_code >= 400:
                try:
                    data = response.json()
                except Exception:
                    data = {"detail": response.text[:200]}
                error_code = data.get("error")
                detail = data.get("detail") or data.get("message", "")
                if error_code and detail:
                    message = f"{error_code}: {detail}"
                elif error_code:
                    message = error_code
                else:
                    message = f"HTTP {response.status_code}: {detail}"
                _set_chat_probe_result(
                    {
                        "status": "error",
                        "message": message,
                        "payload": data,
                    }
                )
                return

            deltas: List[str] = []
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue
                content = line[len("data: "):]
                if content.strip() == "[DONE]":
                    break
                try:
                    packet = json.loads(content)
                except Exception:
                    continue
                if packet.get("error"):
                    message = packet.get("error")
                    detail = packet.get("detail")
                    if detail:
                        message = f"{message}: {detail}"
                    _set_chat_probe_result(
                        {
                            "status": "error",
                            "message": message,
                            "payload": packet,
                        }
                    )
                    return
                delta = packet.get("delta")
                if isinstance(delta, str):
                    deltas.append(delta)
                    if len(deltas) >= 3:
                        break
                if packet.get("done"):
                    break
            _set_chat_probe_result({"status": "ok", "deltas": deltas, "url": url})
    except Exception as exc:
        _set_chat_probe_result({"status": "error", "message": str(exc), "url": url})


def _render_test_tab() -> None:
    st.subheader("Automated Checks")

    probe_cols = st.columns([1, 2])
    with probe_cols[0]:
        if st.button("Probe Core chat"):
            with st.spinner("Streaming sample chat…"):
                _run_chat_probe()
    with probe_cols[1]:
        result = _get_chat_probe_result()
        if result is None:
            st.caption("Run the probe to verify chat streaming.")
        elif result.get("status") == "ok":
            deltas = result.get("deltas", [])
            display = "".join(deltas) or "(no deltas received)"
            st.success(f"Received {len(deltas)} delta(s):")
            st.code(display, language="text")
        else:
            message = result.get("message", "Unknown error")
            st.warning(f"Chat probe failed: {message}")
            if result.get("payload"):
                st.json(result["payload"])

    st.markdown("---")

    npm_missing = shutil.which("npm") is None
    playwright_cols = st.columns([1, 2])
    with playwright_cols[0]:
        disabled = npm_missing
        if st.button("Run Playwright e2e", disabled=disabled):
            if npm_missing:
                st.warning("npm is not installed; skipping Playwright tests.")
            else:
                _run_test(SERVICE_TEST_PLAYWRIGHT, _test_command_playwright(), ROOT)
    with playwright_cols[1]:
        logs = _service_log_lines(SERVICE_TEST_PLAYWRIGHT, limit=200)
        st.code("\n".join(logs) if logs else "No output yet.")

    st.markdown("---")
    ci_cols = st.columns([1, 2])
    with ci_cols[0]:
        if st.button("Run CI smoke script"):
            _run_test(SERVICE_TEST_CI, _test_command_ci(), ROOT)
    with ci_cols[1]:
        logs = _service_log_lines(SERVICE_TEST_CI, limit=200)
        st.code("\n".join(logs) if logs else "No output yet.")


def _render_router_tab() -> None:
    st.subheader("HC Shell Router")
    shell_choice = st.radio("Target shell", options=["react", "streamlit"], index=0, horizontal=True)
    current_url = _build_service_url(SERVICE_REACT if shell_choice == "react" else SERVICE_STREAMLIT)
    cols = st.columns([1, 3])
    with cols[0]:
        if st.button("Open selected shell", key="open-router-shell", disabled=current_url is None):
            _open_ui(current_url, f"{shell_choice.title()} shell")
    with cols[1]:
        st.code(current_url or "(not configured)", language="text")
    if st.button("Launch via Router"):
        env = _env().copy()
        env["HC_SHELL_V2"] = shell_choice
        _start_service(
            SERVICE_ROUTER,
            _router_command(shell_choice),
            ROOT,
            env,
            None,
        )
    if st.button("Stop router"):
        _stop_service(SERVICE_ROUTER)

    logs = _service_log_lines(SERVICE_ROUTER, limit=200)
    st.code("\n".join(logs) if logs else "No router logs yet.")


def main() -> None:
    st.set_page_config(page_title="Control Panel Plus Plus", layout="wide")
    _init_session_state()
    st.sidebar.title("Control Panel Plus Plus")
    st.sidebar.caption("Service orchestrator for Core, UCN/RR, and React.")

    # Quick launch Developer Tools
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🛠️ Quick Launch**")
    st.sidebar.markdown("**Developer Explorer (DevX)**")

    if DEVX_BOOTSTRAP_AVAILABLE:
        # Use new DevX bootstrap system
        backend_port = int(os.environ.get("DEVX_BACKEND_PORT", "8100") or "8100")
        ui_port = int(os.environ.get("DEVX_UI_PORT", "3100") or "3100")

        # Try to load persisted UI port
        persisted_ui_port = load_last_ui_port()
        display_ui_port = ui_port

        # Check health status
        backend_healthy = devx_backend_health(backend_port)
        ui_healthy = devx_ui_health(ui_port)

        # If persisted port is different and healthy, prefer it
        if persisted_ui_port and persisted_ui_port != ui_port:
            if devx_ui_health(persisted_ui_port):
                display_ui_port = persisted_ui_port
                ui_healthy = True

        # Display status indicators
        st.sidebar.write(f"Backend: {'🟢' if backend_healthy else '🔴'} port {backend_port}")
        if persisted_ui_port and persisted_ui_port != ui_port and ui_healthy:
            st.sidebar.write(f"UI: {'🟢' if ui_healthy else '🔴'} port {display_ui_port} (last: {persisted_ui_port})")
        else:
            st.sidebar.write(f"UI: {'🟢' if ui_healthy else '🔴'} port {display_ui_port}")

        # Verbose logging toggle
        verbose_logging = st.sidebar.checkbox(
            "Write DevX logs to ~/.redna (verbose)",
            value=os.environ.get("DEVX_VERBOSE_LOGS", "").lower() == "true",
            key="_devx_verbose_logging",
            help="Enable detailed logging of DevX processes to ~/.redna/devx_*.log"
        )
        if verbose_logging:
            os.environ["DEVX_VERBOSE_LOGS"] = "true"
        else:
            os.environ.pop("DEVX_VERBOSE_LOGS", None)

        # Control buttons
        col1, col2, col3 = st.sidebar.columns([1, 1, 1])

        if col1.button("▶️ Start", key="devx_start", help="Start DevX backend and UI"):
            with st.spinner("Starting DevX services..."):
                # Check if dependencies are needed
                cmds = ensure_devx_requirements_commands()
                if cmds:
                    st.sidebar.info("💡 Ensure dependencies are installed:")
                    for cmd in cmds:
                        st.sidebar.code(cmd, language="bash")

                # Start backend
                ok_backend, msg_backend, actual_backend_port = start_devx_backend()
                if ok_backend:
                    st.sidebar.success(msg_backend)
                else:
                    st.sidebar.error(msg_backend)

                # Start UI
                ok_ui, msg_ui, actual_ui_port = start_devx_ui()
                if ok_ui:
                    if actual_ui_port != ui_port:
                        st.sidebar.warning(msg_ui)
                    else:
                        st.sidebar.success(msg_ui)

                    # Store the actual port for the Open button
                    st.session_state["_devx_ui_actual_port"] = actual_ui_port
                else:
                    st.sidebar.error(msg_ui)

                time.sleep(0.5)
                safe_rerun()

        if col2.button("⏹️ Stop", key="devx_stop", help="Stop DevX backend and UI"):
            with st.spinner("Stopping DevX services..."):
                backend_pid, ui_pid = stop_devx()
                pids_msg = []
                if backend_pid:
                    pids_msg.append(f"backend (PID {backend_pid})")
                if ui_pid:
                    pids_msg.append(f"UI (PID {ui_pid})")

                if pids_msg:
                    st.sidebar.success(f"Stopped DevX: {', '.join(pids_msg)}")
                else:
                    st.sidebar.info("No DevX processes were running")

                if "_devx_ui_actual_port" in st.session_state:
                    del st.session_state["_devx_ui_actual_port"]
                time.sleep(0.5)
                safe_rerun()

        if col3.button("🚀 Open", key="devx_open", help="Open Developer Explorer in browser"):
            # Priority: 1) session port 2) persisted port 3) default port
            target_port = st.session_state.get("_devx_ui_actual_port")
            if not target_port:
                target_port = persisted_ui_port if persisted_ui_port else ui_port

            # Verify the target port is healthy
            if devx_ui_health(target_port):
                dev_explorer_url = f"http://localhost:{target_port}"
                webbrowser.open_new_tab(dev_explorer_url)
                st.sidebar.success(f"Opened Developer Explorer at port {target_port}")
            else:
                st.sidebar.warning(f"DevX UI not running on port {target_port}. Click 'Start' first.")

    else:
        # Fallback to legacy behavior if devx_bootstrap not available
        env = _env()
        dev_explorer_port = env.get("dev_explorer_port") or 8550
        dev_explorer_url = f"http://localhost:{dev_explorer_port}"

        # Check if Dev Explorer service URL is available
        service_url = _build_service_url(SERVICE_DEV_EXPLORER)
        if service_url:
            dev_explorer_url = service_url

        # Check if Dev Explorer is running
        dev_explorer_running = False
        try:
            response = requests.head(dev_explorer_url, timeout=0.5, allow_redirects=True)
            dev_explorer_running = response.status_code < 500
        except requests.RequestException:
            pass

        # Display button with status indicator
        button_col, status_col = st.sidebar.columns([3, 1])
        with button_col:
            if st.button("🚀 Open Developer Explorer", use_container_width=True):
                webbrowser.open_new_tab(dev_explorer_url)
                st.sidebar.success(f"Opened in new tab!")
        with status_col:
            if dev_explorer_running:
                st.markdown("🟢")  # Green dot for running
            else:
                st.markdown("⚪")  # White dot for not running

        if dev_explorer_running:
            st.sidebar.caption(f"✅ Running on port {dev_explorer_port}")
        else:
            st.sidebar.caption(f"⚠️ Not detected (port {dev_explorer_port})")

    st.sidebar.markdown("---")

    st.sidebar.checkbox(
        "Force root .venv Python",
        value=bool(st.session_state.get(SESSION_FORCE_ROOT_VENV_KEY, False)),
        key=SESSION_FORCE_ROOT_VENV_KEY,
        help="Launch Core using the repository's .venv interpreter when starting via CP++.",
    )

    tabs = st.tabs([
        "Launch",
        "Profiles",
        "Environment & Ports",
        "Health",
        "Ports & Cleanup",
        "Tests",
        "Router",
    ])

    with tabs[0]:
        _render_launch_tab()
    with tabs[1]:
        _render_profiles_tab()
    with tabs[2]:
        _render_env_tab()
    with tabs[3]:
        _render_health_tab()
    with tabs[4]:
        _render_ports_tab()
    with tabs[5]:
        _render_test_tab()
    with tabs[6]:
        _render_router_tab()

    st.sidebar.markdown("---")
    st.sidebar.caption("Processes started by CP++ appear in this session only. Stop them here before closing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control Panel Plus Plus helper CLI")
    parser.add_argument(
        "--provider-check",
        action="store_true",
        help="Run the provider validator without starting Streamlit",
    )
    parsed = parser.parse_args()
    if parsed.provider_check:
        sys.exit(_run_provider_check_cli())
    main()
