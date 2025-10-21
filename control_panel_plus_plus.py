"""Control Panel Plus Plus — orchestrates Core, React, and Streamlit shells."""

from __future__ import annotations

import argparse
import glob
import html
import io
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import time
import webbrowser
import signal
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import Any, Callable, Dict, List, Literal, NamedTuple, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests

import streamlit as st
import streamlit.components.v1 as components

try:  # pragma: no cover - optional autorefresh utility
    from streamlit_autorefresh import st_autorefresh  # type: ignore
except Exception:  # pragma: no cover
    st_autorefresh = None  # type: ignore

from cpplusplus import envstore, services, ports
from ReDNACoreDemo.devx import manifest_parser

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
    if st.session_state.get(SESSION_SUPPRESS_RERUN_KEY):
        return
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
SESSION_ACTIVE_VENV_KEY = "_cpplusplus_active_venv"
SESSION_SUPPRESS_RERUN_KEY = "_cpplusplus_suppress_rerun"
SESSION_UCNRR_LAST_ACTION_KEY = "_cpplusplus_ucnrr_last_action"
SESSION_UCNRR_LAST_MESSAGE_KEY = "_cpplusplus_ucnrr_last_message"
SESSION_LLM_BOOTSTRAP_KEY = "_cpplusplus_llm_bootstrapped"
SESSION_LLM_BOOTSTRAP_LOG_KEY = "_cpplusplus_llm_bootstrap_log"
SESSION_MANIFEST_OPEN_STATE_KEY = "_cpplusplus_manifest_open"
SESSION_SYSTEM_HEALTH_KEY = "_cpplusplus_system_health"
SESSION_CONSENT_HEALTH_DETAIL_KEY = "_cpplusplus_consent_health_detail"
SESSION_RR_REFERENCE_DETAIL_KEY = "_cpplusplus_rr_reference_detail"
DEFAULT_ACTIVE_USER = "TEST"

ENV_FILE_PATH = ROOT / ".env"
WEB_ENV_LOCAL_PATH = ROOT / "web" / ".env.local"
NUCLEAR_LOG_PATH = Path.home() / ".redna" / "nuclear_reset.log"
PORT_SERVICE_LABELS = {
    "core": "Core API",
    "ucnrr": "UCN/RR",
    "react": "React Dev Server",
    "streamlit": "Streamlit UI",
    "devx_backend": "DevX Backend",
}
NUCLEAR_BUNDLE_DIR = Path.home() / ".redna" / "nuclear" / "bundles"
NUCLEAR_MAX_BUNDLES = 5
NUCLEAR_LOG_FILES = [
    Path.home() / ".redna" / "devx_backend.log",
    Path.home() / ".redna" / "devx_ui.log",
    Path.home() / ".redna" / "logs" / "stack.log",
]
NUCLEAR_SANITY_USER_ID = "NUCLEAR_SANITY"

SERVICE_CORE = "core"
SERVICE_REACT = "react"
SERVICE_STREAMLIT = "streamlit"
SERVICE_UCNRR = "ucnrr"
SERVICE_ROUTER = "router"
SERVICE_TEST_PLAYWRIGHT = "test_playwright"
SERVICE_TEST_CI = "test_ci"
# SERVICE_DEV_EXPLORER = "dev_explorer"  # RETIRED: Use DevX (port 3100) instead

CORE_DEFAULT_PORT = 8004
CORE_PORT_RANGE = (8004, 8012)
UCNRR_DEFAULT_PORT = 8017
UCNRR_PORT_RANGE = (8017, 8030)
REACT_PORT_RANGE = (3000, 3005)
REACT_DEFAULT_PORT = 3000
STREAMLIT_PORT_RANGE = (8501, 8515)
STREAMLIT_DEFAULT_PORT = 8510
STREAMLIT_FALLBACK_PORTS = [port for port in range(8503, 8516) if port != 8502]
DEVX_BACKEND_DEFAULT_PORT = 8100
CORE_BASE_DEFAULT = os.getenv("CORE_BASE", f"http://127.0.0.1:{CORE_DEFAULT_PORT}")
HEAD_COACH_URL_SUFFIX = "/?user=TEST&persona=head_coach&center=coach"
LLM_BENCHMARKS_URL_SUFFIX = "/tools/llm-benchmarks?tab=ai-readiness"

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


def _load_repo_dotenv() -> None:
    """Load repository .env values into os.environ without overriding existing entries."""
    try:
        from dotenv import load_dotenv  # type: ignore

        env_path = (ENV_FILE_PATH if ENV_FILE_PATH.is_absolute() else Path(".env")).resolve()
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            print(f"[CP++] Loaded .env from {env_path}")
    except ImportError:
        print("[CP++] .env load skipped: python-dotenv not available")
    except Exception as exc:  # noqa: BLE001
        print(f"[CP++] .env load skipped: {exc}")


_load_repo_dotenv()


def _repo_root() -> str:
    return str(ROOT)


def _merge_env(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Return a merged environment dict with overrides applied (string coercion)."""
    merged: Dict[str, str] = {str(k): str(v) for k, v in os.environ.items()}
    if overrides:
        for key, value in overrides.items():
            if value is None:
                continue
            merged[str(key)] = str(value)
    return merged


def _format_core_launch_log(env_map: Dict[str, str]) -> str:
    secret_status = "present" if env_map.get("CONSENT_JWT_SECRET") else "missing"
    ttl_value = env_map.get("CONSENT_JWT_TTL_MINUTES") or "none"
    return f"[CP++] Launch Core with CONSENT_JWT_SECRET={secret_status}, TTL={ttl_value}"


def _discover_venvs(root: str) -> List[Path]:
    candidates: List[Path] = []
    for path in glob.glob(os.path.join(root, ".venv")):
        if os.path.isdir(path):
            candidates.append(Path(path).resolve())
    for path in glob.glob(os.path.join(root, "*", ".venv")):
        if os.path.isdir(path):
            candidates.append(Path(path).resolve())
    unique: List[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return sorted(unique)


_ROOT_VENV_PATH = Path(_repo_root()) / ".venv"


def _python_executable_for_venv(venv_path: Path) -> Path:
    if sys.platform == "win32":
        return (venv_path / "Scripts" / "python.exe").resolve()
    return (venv_path / "bin" / "python").resolve()


def _python_candidates() -> List[Path]:
    candidates: List[Path] = []
    root_py = _python_executable_for_venv(_ROOT_VENV_PATH)
    candidates.append(root_py)
    for venv_path in _discover_venvs(_repo_root()):
        candidates.append(_python_executable_for_venv(venv_path))
    candidates.append(Path(sys.executable).resolve())
    unique: List[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            continue
        key = str(resolved)
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


def _active_python_path() -> Path:
    root_python = _python_executable_for_venv(_ROOT_VENV_PATH)
    if root_python.exists():
        resolved = root_python.resolve()
        st.session_state[SESSION_ACTIVE_VENV_KEY] = str(resolved)
        return resolved
    fallback = Path(sys.executable).resolve()
    st.session_state[SESSION_ACTIVE_VENV_KEY] = str(fallback)
    return fallback


def _python_choice_label(path: Path) -> str:
    try:
        if path.exists() and path.samefile(ROOT_VENV_BIN):
            return f"{path} (repo .venv)"
    except Exception:
        pass
    parent = path.parent
    if parent.name in {"bin", "Scripts"}:
        venv_dir = parent.parent
        return f"{path} ({venv_dir.name})"
    return str(path)


def _python_choices() -> List[Tuple[str, Path]]:
    return [( _python_choice_label(candidate), candidate) for candidate in _python_candidates()]


ROOT_VENV_BIN = _python_executable_for_venv(_ROOT_VENV_PATH)
_ALL_VENVS = _discover_venvs(_repo_root())

if len(_ALL_VENVS) > 1:
    st.warning("Multiple Python venvs found. Defaulting to the **root** `.venv`.", icon="⚠️")

if not ROOT_VENV_BIN.exists():
    st.error(f"Root venv python not found at: {ROOT_VENV_BIN}. Run `scripts/consolidate_venv.sh`.", icon="🛑")


def _render_copy_path(path_str: str, element_id: Optional[str] = None) -> None:
    """Display a copy-to-clipboard widget for a filesystem path."""
    escaped = html.escape(path_str)
    input_id = element_id or f"copy-path-{uuid4().hex}"
    components.html(
        f"""
        <div style="display:flex; gap:0.5rem; align-items:center; width:100%;">
            <input id="{input_id}" style="flex:1; padding:0.45rem; border-radius:0.5rem; border:1px solid #3c3f44; background-color:#0f1116; color:#f0f2f6;" value="{escaped}" readonly />
            <button style="padding:0.45rem 0.9rem; border-radius:0.5rem; background-color:#1f6feb; color:white; border:none; cursor:pointer;"
                onclick="navigator.clipboard.writeText(document.getElementById('{input_id}').value); this.innerText='Copied!'; setTimeout(() => this.innerText='Copy Path', 1500);">
                Copy Path
            </button>
        </div>
        """,
        height=70,
    )


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

    python_path = _active_python_path()
    interpreter_aliases = {
        sys.executable,
        os.path.basename(sys.executable),
        "python",
        "python3",
        str(python_path),
        os.path.basename(str(python_path)),
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
    local_npm = (ROOT / "web" / "node_modules" / ".bin" / "npm").resolve(strict=False)
    if local_npm.exists():
        return str(local_npm)
    detected = shutil.which("npm")
    if detected:
        return detected
    return None


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
    _evaluate(SERVICE_UCNRR, "ucnrr_port", UCNRR_PORT_RANGE, [], ["/api/health", "/health"])

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
    if SESSION_ACTIVE_VENV_KEY not in st.session_state:
        st.session_state[SESSION_ACTIVE_VENV_KEY] = str(_active_python_path())
    if SESSION_SUPPRESS_RERUN_KEY not in st.session_state:
        st.session_state[SESSION_SUPPRESS_RERUN_KEY] = False
    if SESSION_UCNRR_LAST_ACTION_KEY not in st.session_state:
        st.session_state[SESSION_UCNRR_LAST_ACTION_KEY] = None
    if SESSION_UCNRR_LAST_MESSAGE_KEY not in st.session_state:
        st.session_state[SESSION_UCNRR_LAST_MESSAGE_KEY] = None


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
# Port drift detection and repair
# ---------------------------------------------------------------------------

def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if not text:
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def _load_env_file_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    data: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _extract_port(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    candidate = text
    if "://" not in candidate:
        candidate = f"http://{candidate.lstrip('/')}"
    parsed = urlparse(candidate)
    port_val = parsed.port
    if port_val:
        return port_val
    match = re.search(r":(\d+)", text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _first_non_none(values: Sequence[Optional[int]], default: int) -> int:
    for value in values:
        if value is not None:
            return int(value)
    return int(default)


def _build_port_analysis(health: Dict[str, ServiceHealth]) -> Dict[str, Any]:
    root_env = _load_env_file_map(ENV_FILE_PATH)
    web_env = _load_env_file_map(WEB_ENV_LOCAL_PATH)
    cp_env = dict(_env())
    actual_map: Dict[str, Optional[int]] = {}
    for service_name in (SERVICE_CORE, SERVICE_REACT, SERVICE_STREAMLIT, SERVICE_UCNRR):
        service_health = health.get(service_name)
        port_value = None
        if service_health:
            port_value = _safe_int(service_health.actual_port)
            if port_value is None:
                port_value = _safe_int(service_health.port)
        actual_map[service_name] = port_value

    context = {
        "root": root_env,
        "web": web_env,
        "cp": cp_env,
        "actual": actual_map,
    }

    specs: Dict[str, List[Tuple[str, Callable[[Dict[str, Any]], Optional[int]]]]] = {
        "core": [
            ("env:CORE_PORT", lambda ctx: _safe_int(ctx["root"].get("CORE_PORT"))),
            ("cp:core_port", lambda ctx: _safe_int(ctx["cp"].get("core_port"))),
            ("cp:NEXT_PUBLIC_CORE_API_BASE", lambda ctx: _extract_port(ctx["cp"].get("NEXT_PUBLIC_CORE_API_BASE"))),
            ("cp:CORE_BASE", lambda ctx: _extract_port(ctx["cp"].get("CORE_BASE"))),
            ("web:NEXT_PUBLIC_CORE_API_BASE", lambda ctx: _extract_port(ctx["web"].get("NEXT_PUBLIC_CORE_API_BASE"))),
            ("web:CORE_API_URL", lambda ctx: _extract_port(ctx["web"].get("CORE_API_URL"))),
            ("actual", lambda ctx: ctx["actual"].get(SERVICE_CORE)),
        ],
        "react": [
            ("env:REACT_PORT", lambda ctx: _safe_int(ctx["root"].get("REACT_PORT"))),
            ("cp:react_port", lambda ctx: _safe_int(ctx["cp"].get("react_port"))),
            ("actual", lambda ctx: ctx["actual"].get(SERVICE_REACT)),
        ],
        "ucnrr": [
            ("env:UCNRR_PORT", lambda ctx: _safe_int(ctx["root"].get("UCNRR_PORT"))),
            ("cp:ucnrr_port", lambda ctx: _safe_int(ctx["cp"].get("ucnrr_port"))),
            ("cp:UCNRR_BASE", lambda ctx: _extract_port(ctx["cp"].get("UCNRR_BASE"))),
            ("cp:UCNRR_BASE_URL", lambda ctx: _extract_port(ctx["cp"].get("UCNRR_BASE_URL"))),
            ("actual", lambda ctx: ctx["actual"].get(SERVICE_UCNRR)),
        ],
        "streamlit": [
            ("env:STREAMLIT_PHOTO_PORT", lambda ctx: _safe_int(ctx["root"].get("STREAMLIT_PHOTO_PORT"))),
            ("cp:streamlit_port", lambda ctx: _safe_int(ctx["cp"].get("streamlit_port"))),
            ("actual", lambda ctx: ctx["actual"].get(SERVICE_STREAMLIT)),
        ],
        "devx_backend": [
            ("env:DEVX_BACKEND_PORT", lambda ctx: _safe_int(ctx["root"].get("DEVX_BACKEND_PORT"))),
            ("cp:DEVX_BACKEND_PORT", lambda ctx: _safe_int(ctx["cp"].get("DEVX_BACKEND_PORT"))),
            ("cp:NEXT_PUBLIC_DEVX_API_BASE", lambda ctx: _extract_port(ctx["cp"].get("NEXT_PUBLIC_DEVX_API_BASE"))),
            ("web:NEXT_PUBLIC_DEVX_API_BASE", lambda ctx: _extract_port(ctx["web"].get("NEXT_PUBLIC_DEVX_API_BASE"))),
        ],
    }

    analysis: Dict[str, Dict[str, Any]] = {}
    for service, entries in specs.items():
        sources: Dict[str, Optional[int]] = {}
        for label, getter in entries:
            try:
                sources[label] = getter(context)
            except Exception:
                sources[label] = None
        unique = sorted({value for value in sources.values() if value is not None})
        analysis[service] = {"sources": sources, "unique": unique, "has_drift": len(unique) > 1}

    canonical_ports = {
        "core": _first_non_none(
            [
                _safe_int(root_env.get("CORE_PORT")),
                _safe_int(cp_env.get("core_port")),
                _extract_port(cp_env.get("NEXT_PUBLIC_CORE_API_BASE")),
                actual_map.get(SERVICE_CORE),
            ],
            CORE_DEFAULT_PORT,
        ),
        "react": _first_non_none(
            [
                _safe_int(root_env.get("REACT_PORT")),
                _safe_int(cp_env.get("react_port")),
                actual_map.get(SERVICE_REACT),
            ],
            REACT_DEFAULT_PORT,
        ),
        "ucnrr": _first_non_none(
            [
                _safe_int(root_env.get("UCNRR_PORT")),
                _safe_int(cp_env.get("ucnrr_port")),
                _extract_port(cp_env.get("UCNRR_BASE")),
                actual_map.get(SERVICE_UCNRR),
            ],
            UCNRR_DEFAULT_PORT,
        ),
        "streamlit": _first_non_none(
            [
                _safe_int(root_env.get("STREAMLIT_PHOTO_PORT")),
                _safe_int(cp_env.get("streamlit_port")),
                actual_map.get(SERVICE_STREAMLIT),
            ],
            STREAMLIT_DEFAULT_PORT,
        ),
        "devx_backend": _first_non_none(
            [
                _safe_int(root_env.get("DEVX_BACKEND_PORT")),
                _safe_int(cp_env.get("DEVX_BACKEND_PORT")),
                _extract_port(cp_env.get("NEXT_PUBLIC_DEVX_API_BASE")),
            ],
            DEVX_BACKEND_DEFAULT_PORT,
        ),
    }

    return {
        "analysis": analysis,
        "canonical": canonical_ports,
        "root_env": root_env,
        "web_env": web_env,
    }


def _regenerate_env_config(canonical_ports: Dict[str, int]) -> Dict[str, Any]:
    config = envstore.DEFAULT_ENV.copy()
    config.update(dict(_env()))

    core_port = int(canonical_ports.get("core", CORE_DEFAULT_PORT))
    react_port = int(canonical_ports.get("react", REACT_DEFAULT_PORT))
    streamlit_port = int(canonical_ports.get("streamlit", STREAMLIT_DEFAULT_PORT))
    ucnrr_port = int(canonical_ports.get("ucnrr", UCNRR_DEFAULT_PORT))
    devx_port = int(canonical_ports.get("devx_backend", DEVX_BACKEND_DEFAULT_PORT))

    config["core_port"] = core_port
    config["react_port"] = react_port
    config["streamlit_port"] = streamlit_port
    config["ucnrr_port"] = ucnrr_port
    config["DEVX_BACKEND_PORT"] = devx_port

    core_base = f"http://127.0.0.1:{core_port}"
    config["NEXT_PUBLIC_CORE_API_BASE"] = core_base
    config["CORE_BASE"] = core_base
    config["CORE_API_URL"] = core_base
    config["core_start_command"] = f"uvicorn ReDNACoreDemo.core.api:build_app --factory --port {core_port}"

    react_origin = f"http://127.0.0.1:{react_port}"
    config["CORS_ALLOWED_ORIGINS"] = react_origin

    ucnrr_base = f"http://127.0.0.1:{ucnrr_port}"
    config["UCNRR_BASE"] = ucnrr_base
    config["UCNRR_BASE_URL"] = ucnrr_base
    config["NEXT_PUBLIC_UCNRR_API_BASE"] = ucnrr_base

    devx_base = f"http://127.0.0.1:{devx_port}"
    config["NEXT_PUBLIC_DEVX_API_BASE"] = devx_base
    config["DEVX_BASE"] = devx_base

    return config


def _rewrite_env_file(path: Path, updates: Dict[str, str], append_missing: bool = True) -> bool:
    if not updates:
        return False

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if not append_missing:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(f"{key}={value}" for key, value in updates.items()) + "\n"
        path.write_text(payload, encoding="utf-8")
        return True
    except Exception:
        return False

    lines = text.splitlines()
    seen: set[str] = set()
    changed = False
    new_lines: List[str] = []

    for line in lines:
        replacement = line
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            key_clean = key.strip()
            seen.add(key_clean)
            if key_clean in updates:
                new_value = updates[key_clean]
                if value.strip() != new_value:
                    changed = True
                replacement = f"{key_clean}={new_value}"
        new_lines.append(replacement)

    if append_missing:
        for key, value in updates.items():
            if key not in seen:
                new_lines.append(f"{key}={value}")
                changed = True

    if not changed:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    joined = "\n".join(new_lines) + "\n"
    path.write_text(joined, encoding="utf-8")
    return True


def _append_nuclear_log(event: str, payload: Dict[str, Any]) -> None:
    try:
        NUCLEAR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.utcnow().isoformat() + "Z", "event": event}
        entry.update(payload)
        with NUCLEAR_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True))
            handle.write("\n")
    except Exception:
        pass


def _restart_stack_after_port_fix(config: Dict[str, Any]) -> None:
    summary = _stop_all_services(request_rerun=False)
    if summary:
        _set_action_result(summary)

    core_port = int(config.get("core_port", CORE_DEFAULT_PORT))
    react_port = int(config.get("react_port", REACT_DEFAULT_PORT))
    ucnrr_port = int(config.get("ucnrr_port", UCNRR_DEFAULT_PORT))

    core_workdir = _resolve_core_workdir(config)
    react_workdir = _resolve_react_workdir(config)
    try:
        raw_ucnrr_workdir = config.get("ucnrr_workdir")
        ucnrr_workdir = Path(str(raw_ucnrr_workdir) if raw_ucnrr_workdir else str(ROOT)).expanduser().resolve(strict=False)
    except Exception:
        ucnrr_workdir = ROOT

    core_command = _core_start_command_list(config)
    react_npm = _resolve_react_npm(config)

    _launch_stack(
        config,
        core_port,
        react_port,
        ucnrr_port,
        core_workdir,
        react_workdir,
        ucnrr_workdir,
        core_command,
        react_npm,
        open_ui=False,
    )

    if DEVX_BOOTSTRAP_AVAILABLE:
        _apply_devx_env(config)
        ok_backend, msg_backend, backend_port = start_devx_backend()
        if ok_backend:
            st.info(f"DevX backend running on port {backend_port}. {msg_backend}")
        else:
            st.warning(f"DevX backend restart failed: {msg_backend}")
        ok_ui, msg_ui, ui_port = start_devx_ui()
        if ok_ui:
            st.info(f"DevX UI running on port {ui_port}. {msg_ui}")
        else:
            st.warning(f"DevX UI restart failed: {msg_ui}")


def _execute_port_repair(canonical_ports: Dict[str, int], rewrite_files: bool, port_state: Dict[str, Any]) -> None:
    with st.spinner("Realigning ports and restarting services…"):
        new_env = _regenerate_env_config(canonical_ports)
        envstore.save_env_config(new_env)
        st.session_state[SESSION_ENV_KEY] = dict(new_env)
        _set_env_dirty(False)

        updated_files: List[str] = []
        if rewrite_files:
            root_updates = {
                "CORE_PORT": str(new_env["core_port"]),
                "UCNRR_PORT": str(new_env["ucnrr_port"]),
                "REACT_PORT": str(new_env["react_port"]),
                "STREAMLIT_PHOTO_PORT": str(new_env["streamlit_port"]),
                "DEVX_BACKEND_PORT": str(new_env["DEVX_BACKEND_PORT"]),
                "CORE_BASE": f"http://127.0.0.1:{new_env['core_port']}",
                "UCNRR_BASE": f"http://127.0.0.1:{new_env['ucnrr_port']}",
                "UCNRR_BASE_URL": f"http://127.0.0.1:{new_env['ucnrr_port']}",
            }
            if _rewrite_env_file(ENV_FILE_PATH, root_updates, append_missing=True):
                try:
                    updated_files.append(str(ENV_FILE_PATH.relative_to(ROOT)))
                except ValueError:
                    updated_files.append(str(ENV_FILE_PATH))

            web_updates = {
                "NEXT_PUBLIC_CORE_API_BASE": f"http://127.0.0.1:{new_env['core_port']}",
                "CORE_API_URL": f"http://127.0.0.1:{new_env['core_port']}",
                "NEXT_PUBLIC_DEVX_API_BASE": f"http://127.0.0.1:{new_env['DEVX_BACKEND_PORT']}",
            }
            if _rewrite_env_file(WEB_ENV_LOCAL_PATH, web_updates, append_missing=False):
                try:
                    updated_files.append(str(WEB_ENV_LOCAL_PATH.relative_to(ROOT)))
                except ValueError:
                    updated_files.append(str(WEB_ENV_LOCAL_PATH))

        drift_snapshot = {
            service: {label: value for label, value in info["sources"].items() if value is not None}
            for service, info in port_state["analysis"].items()
            if info["has_drift"]
        }

        log_payload: Dict[str, Any] = {
            "canonical_ports": {name: int(value) for name, value in canonical_ports.items()},
            "rewrite_env_files": rewrite_files,
        }
        if drift_snapshot:
            log_payload["drift_snapshot"] = drift_snapshot
        if updated_files:
            log_payload["updated_files"] = updated_files

        _append_nuclear_log("port_repair", log_payload)
        _restart_stack_after_port_fix(new_env)

    st.success("Ports aligned and services restarted.")
    _refresh_health()
    safe_rerun()


def _render_port_drift_banner(port_state: Dict[str, Any]) -> None:
    analysis = port_state["analysis"]
    canonical_ports = port_state["canonical"]
    drift_entries = [(service, data) for service, data in analysis.items() if data["has_drift"]]
    if not drift_entries:
        return

    with st.container(border=True):
        st.warning("⚠️ Port drift detected between running services and environment files.")
        for service, data in drift_entries:
            label = PORT_SERVICE_LABELS.get(service, service.title())
            canonical = canonical_ports.get(service)
            parts: List[str] = []
            for source_label, value in data["sources"].items():
                if value is None:
                    continue
                label_fragment = source_label.split(":", 1)[-1]
                parts.append(f"{label_fragment}={value}")
            summary = ", ".join(parts) if parts else "n/a"
            if canonical is not None:
                st.markdown(f"- **{label}** · target {canonical} → {summary}")
            else:
                st.markdown(f"- **{label}** → {summary}")

        with st.form("port_repair_form"):
            rewrite_files = st.checkbox("Rewrite .env and web/.env.local to canonical ports", value=False)
            submitted = st.form_submit_button("Fix Ports", use_container_width=True)
            if submitted:
                _execute_port_repair(canonical_ports, rewrite_files, port_state)


# ---------------------------------------------------------------------------
# Nuclear diagnostics helpers
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(authorization:\s*Bearer\s+)([A-Za-z0-9\-\._~+/=]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key[:=]\s*)([^\s\"']+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(secret[:=]\s*)([^\s\"']+)"), r"\1[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "sk-[REDACTED]"),
    (re.compile(r"eyJ[0-9A-Za-z_\-]+?\.[0-9A-Za-z_\-]+?\.[0-9A-Za-z_\-]+"), "[JWT-REDACTED]"),
]


def _redact_sensitive_tokens(text: str) -> str:
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_log_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    return _redact_sensitive_tokens(content)


def _snapshot_nuclear_logs(prefix: str) -> Dict[str, str]:
    snapshots: Dict[str, str] = {}
    for path in NUCLEAR_LOG_FILES:
        sanitized = _sanitize_log_file(path)
        if sanitized:
            snapshots[f"{prefix}/{path.name}"] = sanitized
    return snapshots


def _truncate_nuclear_logs() -> None:
    for path in NUCLEAR_LOG_FILES:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        except Exception:
            continue


def _enforce_nuclear_bundle_retention(max_bundles: int = NUCLEAR_MAX_BUNDLES) -> None:
    if max_bundles <= 0 or not NUCLEAR_BUNDLE_DIR.exists():
        return
    bundles = sorted(
        NUCLEAR_BUNDLE_DIR.glob("*.tgz"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for old in bundles[max_bundles:]:
        try:
            old.unlink()
        except Exception:
            continue


def _write_nuclear_bundle(name: str, log_contents: Dict[str, str], metadata: Dict[str, Any]) -> Optional[Path]:
    try:
        NUCLEAR_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
        bundle_path = NUCLEAR_BUNDLE_DIR / f"{name}.tgz"
        with tarfile.open(bundle_path, "w:gz") as tar:
            for relative_name, content in log_contents.items():
                data = content.encode("utf-8")
                info = tarfile.TarInfo(name=relative_name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            meta_bytes = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8")
            info = tarfile.TarInfo(name="metadata.json")
            info.size = len(meta_bytes)
            tar.addfile(info, io.BytesIO(meta_bytes))
        return bundle_path
    except Exception:
        return None


def _summarize_kill_results(results: Dict[str, Any]) -> Dict[str, Any]:
    killed = results.get("killed_pids") or []
    errors = results.get("errors") or []
    return {
        "timestamp": results.get("timestamp"),
        "killed_count": len(killed),
        "errors": errors[:5],
        "ports_cleared": sorted(results.get("ports_cleared", []))[:10],
    }


def _summarize_rebuild_results(results: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"timestamp": results.get("timestamp"), "services": {}}
    for service, payload in results.items():
        if service in {"diagnostic_log", "timestamp"}:
            continue
        if not isinstance(payload, dict):
            continue
        summary["services"][service] = {
            "started": bool(payload.get("started")),
            "port": payload.get("port"),
            "error": payload.get("error"),
        }
    return summary


def _build_nuclear_bundle(
    kill_results: Dict[str, Any],
    rebuild_results: Dict[str, Any],
    sanity_report: Dict[str, Any],
    pre_logs: Dict[str, str],
    post_logs: Dict[str, str],
) -> Optional[Path]:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    bundle_name = f"nuclear_{timestamp}"
    log_contents = {}
    log_contents.update(pre_logs)
    log_contents.update(post_logs)
    metadata = {
        "kill": _summarize_kill_results(kill_results),
        "rebuild": _summarize_rebuild_results(rebuild_results),
        "sanity": sanity_report,
    }
    bundle_path = _write_nuclear_bundle(bundle_name, log_contents, metadata)
    if bundle_path:
        _enforce_nuclear_bundle_retention()
    return bundle_path


def _run_nuclear_sanity_checks(user_id: str = NUCLEAR_SANITY_USER_ID) -> Dict[str, Any]:
    report: Dict[str, Any] = {"timestamp": datetime.utcnow().isoformat() + "Z"}

    core_base = _build_service_url(SERVICE_CORE)
    devx_base = str(
        _env().get("NEXT_PUBLIC_DEVX_API_BASE")
        or f"http://127.0.0.1:{_devx_backend_port(_env())}"
    ).rstrip("/")

    # Chronotype ingest probe
    chronotype_payload = {
        "user_id": user_id,
        "text": "I hop out of bed at 5:30 AM every day and feel my best early in the morning.",
        "source": "nuclear_sanity",
    }
    if core_base:
        try:
            ingest_url = core_base.rstrip("/") + "/core/api/ingest_text"
            response = requests.post(ingest_url, json=chronotype_payload, timeout=10)
            body: Any
            try:
                body = response.json()
            except Exception:
                body = response.text[:200]
            report["chronotype_ingest"] = {
                "status": response.status_code,
                "ok": response.ok,
                "body": body,
            }
        except Exception as exc:
            report["chronotype_ingest"] = {"error": str(exc)}
    else:
        report["chronotype_ingest"] = {"error": "Core URL unavailable"}

    # Why-Card fetch
    if core_base:
        try:
            why_url = core_base.rstrip("/") + "/core/api/traits/BehaviorDNA.Sleep.Chronotype/why"
            response = requests.get(
                why_url,
                params={"user_id": user_id, "limit": 1},
                timeout=5,
            )
            if response.ok:
                report["why_card"] = {"status": response.status_code, "body": response.json()}
            else:
                report["why_card"] = {
                    "status": response.status_code,
                    "body": response.text[:200],
                }
        except Exception as exc:
            report["why_card"] = {"error": str(exc)}
    else:
        report["why_card"] = {"error": "Core URL unavailable"}

    # AI readiness probe
    try:
        readiness_url = f"{devx_base}/devx/api/ingestion/ai_ready"
        response = requests.get(readiness_url, timeout=5)
        body = response.json() if response.ok else response.text[:200]
        report["ai_readiness"] = {
            "status": response.status_code,
            "ok": response.ok,
            "body": body,
        }
    except Exception as exc:
        report["ai_readiness"] = {"error": str(exc)}

    if core_base:
        try:
            ontology_url = core_base.rstrip("/") + "/core/graph/ontology"
            ontology_resp = requests.get(ontology_url, timeout=5)
            if ontology_resp.ok:
                ontology_payload = ontology_resp.json()
                report["graph_ontology"] = {
                    "status": "ok",
                    "nodes": len(ontology_payload.get("nodes", [])),
                    "edges": len(ontology_payload.get("edges", [])),
                    "version": ontology_payload.get("version"),
                }
            else:
                report["graph_ontology"] = {
                    "status": f"HTTP {ontology_resp.status_code}",
                    "body": ontology_resp.text[:200],
                }
        except Exception as exc:
            report["graph_ontology"] = {"error": str(exc)}

        try:
            graph_stats_url = core_base.rstrip("/") + f"/core/graph/user/{user_id}/stats"
            stats_resp = requests.get(graph_stats_url, timeout=5)
            if stats_resp.ok:
                stats_payload = stats_resp.json()
                report["graph_user"] = {
                    "status": "ok",
                    "total_nodes": stats_payload.get("total_nodes"),
                    "total_edges": stats_payload.get("total_edges"),
                    "trait_nodes": stats_payload.get("trait_nodes"),
                    "observation_nodes": stats_payload.get("observation_nodes"),
                }
            else:
                report["graph_user"] = {
                    "status": f"HTTP {stats_resp.status_code}",
                    "body": stats_resp.text[:200],
                }
        except Exception as exc:
            report["graph_user"] = {"error": str(exc)}
    else:
        report["graph_ontology"] = {"error": "Core URL unavailable"}
        report["graph_user"] = {"error": "Core URL unavailable"}

    return report


# ---------------------------------------------------------------------------
# Command builders
# ---------------------------------------------------------------------------

def _bool_env(value: Any) -> str:
    return "1" if bool(value) else "0"


def _set_ucnrr_action(action: Optional[str], message: Optional[str]) -> None:
    st.session_state[SESSION_UCNRR_LAST_ACTION_KEY] = action
    st.session_state[SESSION_UCNRR_LAST_MESSAGE_KEY] = message


def _devx_backend_port(config: Dict[str, Any]) -> int:
    try:
        return int(config.get("DEVX_BACKEND_PORT", DEVX_BACKEND_DEFAULT_PORT))
    except Exception:
        return DEVX_BACKEND_DEFAULT_PORT


def _devx_ui_url(path: str = "") -> Optional[str]:
    port_value: Optional[str] = os.environ.get("DEVX_UI_PORT")
    if not port_value and DEVX_BOOTSTRAP_AVAILABLE:
        persisted = load_last_ui_port()
        if persisted:
            port_value = str(persisted)
    if not port_value:
        port_value = "3100"
    try:
        port_int = int(port_value)
    except Exception:
        port_int = 3100
    base = f"http://localhost:{port_int}"
    if path:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"
    return base


def _apply_devx_env(config: Dict[str, Any]) -> None:
    port = _devx_backend_port(config)
    base_raw = str(config.get("DEVX_BASE") or f"http://127.0.0.1:{port}").strip()
    base = base_raw.rstrip("/") if base_raw else f"http://127.0.0.1:{port}"
    os.environ["DEVX_BACKEND_PORT"] = str(port)
    os.environ["DEVX_BASE"] = base
    os.environ["AI_READY_DEVX_HEALTH_URL"] = f"{base}/health"
    os.environ["NEXT_PUBLIC_DEVX_API_BASE"] = base


def _core_base_url() -> str:
    env = _env()
    candidates = [
        env.get("CORE_BASE_URL"),
        env.get("NEXT_PUBLIC_CORE_API_BASE"),
    ]
    for raw in candidates:
        if not raw:
            continue
        candidate = str(raw).strip()
        if candidate:
            return candidate.rstrip("/")

    port_raw = env.get("core_port")
    try:
        port_val = int(port_raw)
        if port_val > 0:
            return f"http://127.0.0.1:{port_val}"
    except (TypeError, ValueError):
        pass

    return CORE_BASE_DEFAULT.rstrip("/")


def _core_build_url(path: str) -> str:
    base = _core_base_url()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _run_make_command(target: str) -> Dict[str, Any]:
    """Execute `make <target>` inside the repo root and capture output."""
    try:
        completed = subprocess.run(
            ["make", target],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "`make` command not found"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    return {
        "ok": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "returncode": completed.returncode,
    }


def _format_request_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        if response is not None:
            status = response.status_code
            reason = response.reason or ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = payload.get("message") or payload.get("detail") or payload.get("error")
                    if detail:
                        return f"{status} {reason}: {detail}"
            except Exception:
                body = response.text
                if body:
                    return f"{status} {reason}: {body}"
            return f"{status} {reason}"
    if isinstance(exc, requests.ConnectionError):
        return "Connection failed"
    if isinstance(exc, requests.Timeout):
        return "Request timed out"
    return str(exc)


def _health_user() -> str:
    return manifest_parser.preferred_health_user()


def _fetch_json_get(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"error": _format_request_error(exc)}
    try:
        return response.json()
    except ValueError:
        return {"error": "Invalid JSON response"}


def _post_json(url: str, timeout: float = 5.0, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"error": _format_request_error(exc)}
    try:
        return response.json()
    except ValueError:
        return {"ok": True}


def _fetch_rr_audit_data(base_url: Optional[str] = None) -> Dict[str, Any]:
    base = (base_url or _core_base_url()).rstrip("/")
    url = f"{base}/core/debug/rr_audit/{_health_user()}"
    return _fetch_json_get(url, timeout=2)


def _fetch_propagation_audit_data(base_url: Optional[str] = None) -> Dict[str, Any]:
    base = (base_url or _core_base_url()).rstrip("/")
    url = f"{base}/core/debug/ucn_propagation/{_health_user()}"
    return _fetch_json_get(url, timeout=2)


def _fetch_rr_reference_status(base_url: Optional[str] = None) -> Dict[str, Any]:
    base = (base_url or _core_base_url()).rstrip("/")
    cache_buster = int(time.time())
    url = f"{base}/core/rr/reference/status?ts={cache_buster}"
    return _fetch_json_get(url, timeout=2)


def _fetch_ontology_data(base_url: Optional[str] = None) -> Dict[str, Any]:
    base = (base_url or _core_base_url()).rstrip("/")
    url = f"{base}/core/graph/ontology"
    return _fetch_json_get(url, timeout=2)


def _fetch_consent_health(base_url: Optional[str] = None) -> Dict[str, Any]:
    base = (base_url or _core_base_url()).rstrip("/")
    url = f"{base}/core/consent/health"
    return _fetch_json_get(url, timeout=2.5)


def _force_reload_ontology() -> Dict[str, Any]:
    url = _core_build_url("/core/graph/ontology/load?force=true")
    return _post_json(url, timeout=6)


def _count_items(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _format_health_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return (f"{value:.2f}").rstrip("0").rstrip(".")
    return str(value)


def _issues_badge(value: Any) -> str:
    try:
        issues = int(value)
    except (TypeError, ValueError):
        return "⚪"
    return "✅" if issues == 0 else "🟡"


def _refresh_system_health_state() -> Dict[str, Any]:
    base = _core_base_url()
    state = {
        "rr": _fetch_rr_audit_data(base),
        "propagation": _fetch_propagation_audit_data(base),
        "ontology": _fetch_ontology_data(base),
        "consent": _fetch_consent_health(base),
        "reference": _fetch_rr_reference_status(base),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state[SESSION_SYSTEM_HEALTH_KEY] = state
    return state


def _render_system_health_panel(env: Dict[str, Any]) -> None:
    health_state = st.session_state.get(SESSION_SYSTEM_HEALTH_KEY)
    if health_state is None:
        health_state = _refresh_system_health_state()

    button_cols = st.columns(2)
    if button_cols[0].button("Refresh Health", key="system-health-refresh"):
        with st.spinner("Refreshing system health…"):
            health_state = _refresh_system_health_state()

    if button_cols[1].button("Reload Phase 10 Ontology (force)", key="system-health-reload"):
        with st.spinner("Reloading ontology…"):
            reload_result = _force_reload_ontology()
        if reload_result.get("error"):
            st.error(f"Reload failed: {reload_result['error']}")
        else:
            message = reload_result.get("message") or "Ontology reload complete."
            seed = reload_result.get("seed_version") or reload_result.get("seed") or reload_result.get("version")
            node_count = _count_items(reload_result.get("nodes"))
            edge_count = _count_items(reload_result.get("edges"))
            details: List[str] = []
            if seed:
                details.append(f"seed={seed}")
            if node_count is not None:
                details.append(f"nodes={node_count}")
            if edge_count is not None:
                details.append(f"edges={edge_count}")
            if details:
                message = f"{message} ({', '.join(details)})"
            st.success(message)
            health_state = _refresh_system_health_state()

    st.caption(f"Canary user: `{_health_user()}`")
    timestamp = health_state.get("updated_at")
    if timestamp:
        st.caption(f"Last updated: {timestamp} UTC")

    consent_data = health_state.get("consent", {}) or {}
    st.markdown("##### Consent (JWT)")
    consent_summary_text: Optional[str] = None
    consent_status_line: Optional[str] = None
    if consent_data.get("error"):
        st.error(consent_data["error"])
    else:
        status = str(consent_data.get("status") or "unknown").lower()
        status_icon = {
            "healthy": "🟢",
            "degraded": "🟡",
            "error": "🔴",
        }.get(status, "⚪")
        tooltip_parts: List[str] = []
        warning = consent_data.get("warning")
        if warning:
            tooltip_parts.append(str(warning))
        error_reason = consent_data.get("error_reason")
        if error_reason:
            tooltip_parts.append(str(error_reason))
        tooltip_attr = ""
        if tooltip_parts:
            tooltip_attr = f' title="{html.escape(" | ".join(tooltip_parts))}"'
        consent_header_html = (
            f"<strong>{status_icon} Consent</strong>"
            + (f'<span style="margin-left:0.35rem;"{tooltip_attr}>ℹ️</span>' if tooltip_attr else "")
        )
        st.markdown(consent_header_html, unsafe_allow_html=True)

        config = consent_data.get("config") or {}
        ttl_display = consent_data.get("ttl_minutes")
        ttl_str = "—" if ttl_display is None else str(ttl_display)
        summary_line = " | ".join(
            [
                f"ALG={config.get('algorithm', 'unknown')}",
                f"ENC={config.get('secret_encoding', 'unknown')}",
                f"TTL={ttl_str}",
                f"LEEWAY={config.get('leeway_seconds', '—')}",
            ]
        )
        status_line = " ".join(
            [
                "Roundtrip:",
                "✅" if consent_data.get("roundtrip_ok") else "❌",
                "| Secret:",
                "✅" if consent_data.get("has_secret") else "⚠️",
            ]
        )
        consent_summary_text = summary_line
        consent_status_line = status_line

    if consent_summary_text:
        st.caption(consent_summary_text)
    if consent_status_line:
        st.caption(consent_status_line)

    action_cols = st.columns(3)
    env_path_str = str((ENV_FILE_PATH if ENV_FILE_PATH.is_absolute() else Path(".env")).resolve())
    with action_cols[0]:
        st.caption(".env path")
        _render_copy_path(env_path_str, element_id="consent-env-path")
    with action_cols[1]:
        if st.button("Rotate Secret (Make)", key="consent-rotate-secret"):
            with st.spinner("Running `make consent-secret`…"):
                result = _run_make_command("consent-secret")
            if result.get("ok"):
                st.success("Secret rotation command completed. Restart Core via Nuclear to apply.")
            else:
                st.error(result.get("error") or f"make consent-secret failed (exit {result.get('returncode')})")
            if result.get("stdout"):
                st.code(result["stdout"], language="bash")
            if result.get("stderr"):
                st.caption("stderr:")
                st.code(result["stderr"], language="bash")
    with action_cols[2]:
        if st.button("Consent Health JSON", key="consent-health-json"):
            detail_payload = _fetch_consent_health()
            st.session_state[SESSION_CONSENT_HEALTH_DETAIL_KEY] = detail_payload
            if detail_payload.get("error"):
                st.error(detail_payload["error"])
            else:
                st.success("Fetched latest consent health.")

    consent_detail = st.session_state.get(SESSION_CONSENT_HEALTH_DETAIL_KEY)
    if consent_detail and not consent_detail.get("error"):
        with st.expander("Consent Health Detail", expanded=False):
            st.code(json.dumps(consent_detail, indent=2), language="json")
    elif consent_detail and consent_detail.get("error"):
        with st.expander("Consent Health Detail", expanded=False):
            st.error(consent_detail["error"])

    reference_data = health_state.get("reference") or {}
    st.markdown("##### RR Reference")
    if reference_data.get("error"):
        st.error(reference_data["error"])
    else:
        config_raw = reference_data.get("config") if isinstance(reference_data.get("config"), dict) else {}
        config: Dict[str, Any] = dict(config_raw) if isinstance(config_raw, dict) else {}
        source_raw = config.get("source") or reference_data.get("source")
        source = (str(source_raw).upper() if source_raw else "UNKNOWN") or "UNKNOWN"
        universe = config.get("universe") or reference_data.get("universe")
        cohort_keys = config.get("cohort_keys") or reference_data.get("cohort_keys") or []
        if isinstance(cohort_keys, str):
            cohort_keys = [cohort_keys]
        if not isinstance(cohort_keys, (list, tuple, set)):
            cohort_list: List[str] = []
        else:
            cohort_list = [str(item).strip() for item in cohort_keys if str(item).strip()]
        fallback_reason = (
            reference_data.get("fallback_reason")
            or config.get("fallback_reason")
            or (reference_data.get("core") or {}).get("fallback_reason")
        )

        if source == "ACTUAL":
            if cohort_list:
                detail_display = ", ".join(cohort_list[:3])
                if len(cohort_list) > 3:
                    detail_display += f" +{len(cohort_list) - 3}"
            else:
                detail_display = "default cohort"
        else:
            detail_display = str(universe or "default")

        badge_state = "green"
        if reference_data.get("error"):
            badge_state = "red"
        elif fallback_reason:
            badge_state = "yellow"

        badge_palette = {
            "green": ("#0f5132", "#d1fae5", "#0f5132"),
            "yellow": ("#8a6d1a", "#fef3c7", "#8a6d1a"),
            "red": ("#842029", "#f8d7da", "#842029"),
        }
        fg_color, bg_color, border_color = badge_palette.get(badge_state, badge_palette["yellow"])
        badge_icon = "🟢" if badge_state == "green" else "🟡" if badge_state == "yellow" else "🔴"
        badge_html = f"""
        <div style="
            display:flex;
            align-items:center;
            gap:0.75rem;
            padding:0.75rem 1rem;
            border-radius:0.75rem;
            border:1px solid {border_color};
            background:{bg_color};
            color:{fg_color};
            font-weight:600;
        ">
            <span style="font-size:1.25rem;">{badge_icon}</span>
            <div>
                <div>RR Reference: <code>{html.escape(source)}</code></div>
                <div style="font-size:0.85rem; font-weight:500;">{html.escape(detail_display)}</div>
            </div>
        </div>
        """
        st.markdown(badge_html, unsafe_allow_html=True)

        if fallback_reason:
            st.caption(f"Fallback: {fallback_reason}")

        button_cols = st.columns([1, 1, 2])
        with button_cols[0]:
            if st.button("View Details", key="rr-reference-view-details"):
                st.session_state[SESSION_RR_REFERENCE_DETAIL_KEY] = reference_data
        with button_cols[1]:
            devx_rr_url = _devx_ui_url("/rr-reference")
            if st.button(
                "Open DevX RR Reference Panel",
                key="rr-reference-open-devx",
                disabled=devx_rr_url is None,
            ):
                _open_ui(devx_rr_url, "DevX RR Reference", notify=False)
        with button_cols[2]:
            st.caption("Adjust settings in DevX and restart Core via Nuclear to apply.")

    rr_reference_detail = st.session_state.get(SESSION_RR_REFERENCE_DETAIL_KEY)
    if rr_reference_detail:
        try:
            detail_json = json.dumps(rr_reference_detail, indent=2)
        except TypeError:
            detail_json = json.dumps(rr_reference_detail, indent=2, default=str)
        with st.modal("RR Reference Status", key="rr-reference-modal"):
            st.code(detail_json, language="json")
            if st.button("Close", key="rr-reference-modal-close"):
                st.session_state.pop(SESSION_RR_REFERENCE_DETAIL_KEY, None)

    rr_data = health_state.get("rr", {})
    st.markdown("##### RR Audit")
    if rr_data.get("error"):
        st.error(rr_data["error"])
    else:
        rr_summary = rr_data.get("summary") or {}
        issues_value = rr_summary.get("issues")
        st.markdown(f"{_issues_badge(issues_value)} Issues: **{_format_health_value(issues_value)}**")
        rr_lines: List[str] = []
        for key, label in (("normalized", "Normalized"), ("corrected", "Corrected")):
            value = rr_summary.get(key)
            if value is not None:
                rr_lines.append(f"- **{label}**: {_format_health_value(value)}")
        if rr_lines:
            st.markdown("\n".join(rr_lines))
        else:
            st.caption("No RR normalization data available.")

    propagation_data = health_state.get("propagation", {})
    st.markdown("##### UCN Propagation")
    if propagation_data.get("error"):
        st.error(propagation_data["error"])
    else:
        propagation_summary = propagation_data.get("summary") or {}
        issues_value = propagation_summary.get("issues")
        st.markdown(f"{_issues_badge(issues_value)} Issues: **{_format_health_value(issues_value)}**")
        propagation_lines: List[str] = []
        for key, label in (("corrected", "Corrected"), ("processed", "Processed")):
            value = propagation_summary.get(key)
            if value is not None:
                propagation_lines.append(f"- **{label}**: {_format_health_value(value)}")
        if propagation_lines:
            st.markdown("\n".join(propagation_lines))
        else:
            st.caption("No propagation metrics available.")

    ontology_data = health_state.get("ontology", {})
    st.markdown("##### Ontology")
    if ontology_data.get("error"):
        st.error(ontology_data["error"])
    else:
        summary = ontology_data.get("summary") if isinstance(ontology_data.get("summary"), dict) else None
        nodes_count = _count_items(summary.get("nodes")) if summary else None
        edges_count = _count_items(summary.get("edges")) if summary else None
        if nodes_count is None:
            nodes_count = _count_items(ontology_data.get("nodes"))
        if edges_count is None:
            edges_count = _count_items(ontology_data.get("edges"))
        seed_version = (
            (summary or {}).get("seed_version")
            or ontology_data.get("seed_version")
            or (ontology_data.get("loader") or {}).get("seed_version")
        )
        st.markdown(
            "\n".join(
                [
                    f"- **Nodes**: {_format_health_value(nodes_count)}",
                    f"- **Edges**: {_format_health_value(edges_count)}",
                    f"- **Seed Version**: {_format_health_value(seed_version)}",
                ]
            )
        )

    st.markdown("##### Runtime Flags")
    flags = [
        {"Flag": "RR_ADAPTER_ENABLED", "Value": _format_health_value(env.get("RR_ADAPTER_ENABLED"))},
        {"Flag": "REFERENCE_POP_ENABLED", "Value": _format_health_value(env.get("REFERENCE_POP_ENABLED"))},
        {"Flag": "REFERENCE_POP_SOURCE", "Value": _format_health_value(env.get("REFERENCE_POP_SOURCE"))},
    ]
    st.table(flags)
    st.caption("Values read from the current Control Panel++ environment.")


INTEL_FILES = [
    ("Services & Ports JSON", "docs/Intel/ServicesAndPorts.json"),
    ("Endpoints Index", "docs/Intel/EndpointsIndex.json"),
    ("Flags & Defaults", "docs/Intel/FlagsAndDefaults.json"),
    ("Ontology Status", "docs/Intel/OntologyStatus.md"),
    ("Propagation Policy", "docs/Intel/PropagationPolicy.md"),
    ("Debug Surface", "docs/Intel/DebugSurface.md"),
]

DEV_KEYWORDS = ("dev", "test", "demo", "sample", "placeholder", "secret")


def _is_dev_default(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(keyword in lowered for keyword in DEV_KEYWORDS)


def _load_intel_flags(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"error": f"Flags file not found at {path}"}
    except OSError as exc:
        return {"error": str(exc)}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        return {"error": f"Failed to parse JSON: {exc}"}


def _render_flags_table(flags_payload: Dict[str, Any]) -> None:
    categories = flags_payload.get("categories")
    if not isinstance(categories, list):
        st.caption("No flag categories available.")
        return

    note_shown = False
    for entry in categories:
        category_name = entry.get("category") or "Uncategorized"
        category_desc = entry.get("description")
        flags = entry.get("flags") or []
        if not flags:
            continue
        st.markdown(f"**{html.escape(category_name)}**")
        if category_desc:
            st.caption(category_desc)

        header_html = "<tr><th align='left'>Flag</th><th align='left'>Current</th><th align='left'>Default</th><th align='left'>Description</th></tr>"
        rows_html: List[str] = []
        for flag in flags:
            name = html.escape(str(flag.get("name", "")))
            current = html.escape(_format_health_value(flag.get("current")))
            default = html.escape(_format_health_value(flag.get("default")))
            description = html.escape(str(flag.get("description") or ""))
            highlight = False
            if flag.get("current") == flag.get("default") and _is_dev_default(str(flag.get("default", ""))):
                highlight = True
                note_shown = True
            style = "background-color: rgba(250, 204, 21, 0.25);" if highlight else ""
            rows_html.append(
                f"<tr style='{style}'><td>{name}</td><td>{current}</td><td>{default}</td><td>{description}</td></tr>"
            )

        table_html = f"<table style='width:100%; border-collapse:collapse;'>" \
            f"{header_html}{''.join(rows_html)}</table>"
        st.markdown(table_html, unsafe_allow_html=True)
        st.markdown("<hr style='border:none; border-top:1px solid rgba(148,163,184,0.2);' />", unsafe_allow_html=True)

    if note_shown:
        st.caption("Rows highlighted in yellow indicate dev-aligned defaults currently in effect.")


def _render_intel_drawer() -> None:
    st.markdown("#### Intel Files")
    for label, relative_path in INTEL_FILES:
        path = (ROOT / relative_path).resolve()
        cols = st.columns([3, 2])
        with cols[0]:
            if path.exists():
                try:
                    uri = path.as_uri()
                    st.markdown(f"- [{html.escape(label)}]({uri})")
                except ValueError:
                    st.markdown(f"- `{html.escape(relative_path)}`")
            else:
                st.markdown(f"- ~~{html.escape(relative_path)}~~ (missing)")
        with cols[1]:
            _render_copy_path(str(path), element_id=f"intel-{uuid4().hex}")

    flags_path = (ROOT / "docs/Intel/FlagsAndDefaults.json").resolve()
    st.markdown("#### Flags & Defaults")
    flags_payload = _load_intel_flags(flags_path)
    if flags_payload.get("error"):
        st.error(flags_payload["error"])
    else:
        _render_flags_table(flags_payload)
def _core_get_policies() -> Dict[str, Any]:
    response = requests.get(_core_build_url("/core/api/policies"), timeout=3)
    response.raise_for_status()
    return response.json()


def _core_get_learned_policies() -> Dict[str, Any]:
    response = requests.get(_core_build_url("/core/api/policies/learned"), timeout=3)
    response.raise_for_status()
    return response.json()


def _core_set_learned_rr(trait_id: str, learned_rr: Optional[float]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"trait_id": trait_id, "learned_rr": learned_rr}
    response = requests.post(_core_build_url("/core/api/policies/learned"), json=payload, timeout=4)
    response.raise_for_status()
    return response.json()


def _core_clear_learned_rr(trait_id: Optional[str] = None) -> Dict[str, Any]:
    url = _core_build_url("/core/api/policies/learned")
    if trait_id:
        url = f"{url}?trait_id={trait_id}"
    response = requests.delete(url, timeout=4)
    response.raise_for_status()
    return response.json()


def _resolve_llm_provider(config: Dict[str, Any]) -> str:
    provider = str(
        config.get("LLM_PROVIDER")
        or config.get("HC_CHAT_PROVIDER")
        or config.get("llm_provider")
        or ""
    ).strip()
    return provider.lower()


def _is_local_ollama(provider: str) -> bool:
    normalized = provider.replace("-", "").replace("_", "")
    return normalized in {"ollama", "llama", "llama3"} or normalized.startswith("ollama")


def _resolve_ollama_base(config: Dict[str, Any]) -> str:
    base = str(
        config.get("OLLAMA_BASE_URL")
        or config.get("OLLAMA_BASE")
        or config.get("LLM_BASE_URL")
        or "http://127.0.0.1:11434"
    ).strip()
    if not base:
        base = "http://127.0.0.1:11434"
    return base.rstrip("/")


def _ollama_ready(base: str, timeout: float = 2.0) -> bool:
    url = f"{base}/api/version"
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False


def _llm_command_tokens(config: Dict[str, Any]) -> Optional[List[str]]:
    raw = str(config.get("llm_start_command") or config.get("LLM_START_COMMAND") or "").strip()
    if not raw:
        script = ROOT / "start_llm.sh"
        if script.exists():
            raw = f"bash {script.resolve()}"
    if not raw:
        return None
    try:
        return shlex.split(raw)
    except ValueError:
        return raw.split()


def _tail_lines(text: str, limit: int = 40) -> str:
    if not text:
        return ""
    lines = [line.rstrip("\n") for line in text.splitlines()]
    if len(lines) <= limit:
        return "\n".join(lines)
    return "\n".join(lines[-limit:])


def _ensure_llm_runtime(config: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[str]]:
    provider = _resolve_llm_provider(config)
    if not provider:
        provider = "ollama"
    if not _is_local_ollama(provider):
        st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = True
        return True, None, None

    base = _resolve_ollama_base(config)
    if _ollama_ready(base):
        st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = True
        st.session_state[SESSION_LLM_BOOTSTRAP_LOG_KEY] = None
        return True, None, None

    command = _llm_command_tokens(config)
    if not command:
        message = (
            f"Ollama not reachable at {base}. Configure 'LLM start command' under Environment & Ports or"
            " start the runtime manually."
        )
        st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = False
        return False, message, None

    env_copy = os.environ.copy()
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env_copy,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError as exc:
        message = f"LLM start command failed: {exc}"
        st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = False
        st.session_state[SESSION_LLM_BOOTSTRAP_LOG_KEY] = None
        return False, message, None
    except subprocess.TimeoutExpired:
        message = "LLM start command timed out after 10 minutes."
        st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = False
        st.session_state[SESSION_LLM_BOOTSTRAP_LOG_KEY] = None
        return False, message, None

    combined = ""
    if isinstance(result.stdout, str) and result.stdout.strip():
        combined += result.stdout.strip()
    if isinstance(result.stderr, str) and result.stderr.strip():
        combined = f"{combined}\n{result.stderr.strip()}" if combined else result.stderr.strip()
    snippet = _tail_lines(combined, limit=40) if combined else None

    if result.returncode != 0:
        message = f"LLM start command exited with code {result.returncode}."
        st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = False
        st.session_state[SESSION_LLM_BOOTSTRAP_LOG_KEY] = snippet
        return False, message, snippet

    for _ in range(12):
        if _ollama_ready(base):
            message = f"Ollama ready at {base}"
            st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = True
            st.session_state[SESSION_LLM_BOOTSTRAP_LOG_KEY] = snippet
            return True, message, snippet
        time.sleep(1.0)

    message = f"Ollama still unavailable at {base} after running bootstrap command."
    st.session_state[SESSION_LLM_BOOTSTRAP_KEY] = False
    st.session_state[SESSION_LLM_BOOTSTRAP_LOG_KEY] = snippet
    return False, message, snippet


def _core_set_learner(enabled: bool, window: Optional[int] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"enabled": bool(enabled)}
    if window is not None:
        payload["window"] = int(window)
    response = requests.post(_core_build_url("/core/api/policies/learner"), json=payload, timeout=3)
    response.raise_for_status()
    return response.json()


def _core_get_promotion_state() -> Dict[str, Any]:
    response = requests.get(_core_build_url("/core/api/debug/promotion_state"), timeout=3)
    response.raise_for_status()
    return response.json()


def _ai_env(config: Dict[str, Any]) -> Dict[str, str]:
    provider = str(config.get("LLM_PROVIDER") or config.get("HC_CHAT_PROVIDER") or "ollama").strip() or "ollama"
    model = (
        str(
            config.get("LLM_MODEL")
            or config.get("UCNRR_LLM_MODEL")
            or config.get("OLLAMA_MODEL")
            or "phi3:mini"
        ).strip()
        or "phi3:mini"
    )
    base_url_raw = str(config.get("OLLAMA_BASE_URL") or config.get("OLLAMA_BASE") or "http://127.0.0.1:11434").strip()
    base_url = base_url_raw.rstrip("/") if base_url_raw else "http://127.0.0.1:11434"

    env_vars: Dict[str, str] = {
        "LLM_PROVIDER": provider,
        "LLM_MODEL": model,
        "LLM_BASE_URL": base_url,
        "OLLAMA_BASE_URL": base_url,
        "OLLAMA_BASE": base_url,
        "UCNRR_LLM_MODEL": str(config.get("UCNRR_LLM_MODEL") or model),
    }
    env_vars["OLLAMA_MODEL"] = str(config.get("OLLAMA_MODEL") or model)
    if config.get("LLM_TIMEOUT"):
        env_vars["LLM_TIMEOUT"] = str(config.get("LLM_TIMEOUT"))
    return env_vars


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
        "ANTHROPIC_API_KEY": config.get("ANTHROPIC_API_KEY"),
        "ANTHROPIC_MODEL": config.get("ANTHROPIC_MODEL"),
    }
    for key, value in optional.items():
        if value:
            env_vars[key] = str(value)

    env_vars.update(_ai_env(config))
    ucnrr_base = str(
        config.get("UCNRR_BASE_URL")
        or config.get("UCNRR_BASE")
        or f"http://127.0.0.1:{int(config.get('ucnrr_port', UCNRR_DEFAULT_PORT))}"
    ).strip()
    if ucnrr_base:
        env_vars["UCNRR_BASE_URL"] = ucnrr_base
        env_vars["UCNRR_BASE"] = ucnrr_base
    env_vars["UCNRR_SCORE_PATH"] = str(config.get("UCNRR_SCORE_PATH") or "/api/rescore")

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
    env_vars["CORS_ALLOWED_ORIGINS"] = str(config.get("CORS_ALLOWED_ORIGINS") or "http://127.0.0.1:3000")
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
    env_vars["NEXT_PUBLIC_DEVX_API_BASE"] = str(config.get("NEXT_PUBLIC_DEVX_API_BASE") or "http://127.0.0.1:8100")
    ucnrr_base = str(
        config.get("NEXT_PUBLIC_UCNRR_API_BASE")
        or config.get("UCNRR_BASE_URL")
        or config.get("UCNRR_BASE")
        or f"http://127.0.0.1:{int(config.get('ucnrr_port', UCNRR_DEFAULT_PORT))}"
    ).strip()
    env_vars["NEXT_PUBLIC_UCNRR_API_BASE"] = ucnrr_base
    local_bin = (ROOT / "web" / "node_modules" / ".bin").resolve(strict=False)
    if local_bin.exists():
        current_path = os.environ.get("PATH", "")
        prefix = str(local_bin)
        env_vars["PATH"] = f"{prefix}{os.pathsep}{current_path}" if current_path else prefix
    return env_vars


def _ucnrr_command(config: Dict[str, Any], port: int) -> List[str]:
    """Build UCNRR command from config, substituting {port} placeholder."""
    cmd_template = str(config.get("ucnrr_start_command") or envstore.DEFAULT_ENV.get("ucnrr_start_command", ""))
    if not cmd_template:
        # Fallback if no command configured
        python_path = _active_python_path()
        return [str(python_path), "-m", "uvicorn", "ucnrr_app:app", "--host", "0.0.0.0", "--port", str(port), "--reload"]
    cmd_str = cmd_template.format(port=port)
    try:
        tokens = shlex.split(cmd_str)
    except ValueError:
        tokens = cmd_str.split()

    if tokens:
        python_path = _active_python_path()
        alias_candidates = {
            "python",
            "python3",
            os.path.basename(sys.executable),
            os.path.basename(str(python_path)),
            str(python_path),
        }
        first_token = tokens[0]
        first_name = os.path.basename(first_token)
        if first_token in alias_candidates or first_name in alias_candidates:
            tokens[0] = str(python_path)

    return tokens


def _ucnrr_env(config: Dict[str, Any]) -> Dict[str, str]:
    """Build environment variables for UCNRR service."""
    env_vars: Dict[str, str] = _ai_env(config)
    ucnrr_base = str(
        config.get("UCNRR_BASE_URL")
        or config.get("UCNRR_BASE")
        or f"http://127.0.0.1:{int(config.get('ucnrr_port', UCNRR_DEFAULT_PORT))}"
    ).strip()
    if ucnrr_base:
        env_vars["UCNRR_BASE_URL"] = ucnrr_base
        env_vars["UCNRR_BASE"] = ucnrr_base
    env_vars["UCNRR_SCORE_PATH"] = str(config.get("UCNRR_SCORE_PATH") or "/api/rescore")
    env_vars["CORS_ALLOWED_ORIGINS"] = str(config.get("CORS_ALLOWED_ORIGINS") or "http://127.0.0.1:3000")
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
    env: Dict[str, Any],
    port: Optional[int] = None,
    actual_port: Optional[int] = None,
) -> bool:
    env_strings: Dict[str, str] = {str(k): str(v) for k, v in env.items() if v is not None}
    svc_map = _services()
    if name in svc_map and svc_map[name].is_running():
        st.warning(f"{name} already running (pid={svc_map[name].pid()}).")
        return False
    try:
        if name == SERVICE_CORE:
            launch_env = _merge_env(env_strings)
            log_line = _format_core_launch_log(launch_env)
            print(log_line)
        service = services.start_service(name=name, command=command, cwd=cwd, env=env_strings)
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


def _force_kill_ports(port_values: Sequence[int]) -> Dict[int, Dict[str, Any]]:
    killed: Dict[int, Dict[str, Any]] = {}
    for port in port_values:
        if not port:
            continue
        listeners = ports.who_listens(int(port))
        pids = [row.get("pid") for row in listeners if row.get("pid")]
        if not pids:
            continue
        summary = ports.kill_pids(pids)
        killed[int(port)] = summary
    return killed


def _kill_existing_next_servers(preferred_port: int) -> None:
    candidate_ports = {
        int(preferred_port),
        int(REACT_DEFAULT_PORT),
        int(REACT_DEFAULT_PORT + 1),
    }
    candidate_ports.update(range(REACT_PORT_RANGE[0], REACT_PORT_RANGE[1] + 1))
    pids: List[int] = []
    for port in candidate_ports:
        for row in ports.who_listens(int(port)):
            pid = row.get("pid")
            cmd = (row.get("cmd") or "").lower()
            if not pid:
                continue
            if any(token in cmd for token in ("next", "node", "react-scripts")):
                pids.append(int(pid))
    if pids:
        ports.kill_pids(pids)


def _stop_all_services(request_rerun: bool = True, hard_kill: bool = True) -> Dict[str, Any]:
    svc_map = _services()
    names = list(svc_map.keys())
    if not names:
        if request_rerun:
            st.info("No services running.")
        return {}
    aggregate: Dict[str, Any] = {}
    for name in names:
        service = svc_map.pop(name, None)
        if not service:
            continue
        summary = services.stop_service(service)
        _merge_summary(aggregate, summary)

    env = _env()
    if hard_kill:
        forced = _force_kill_ports(
            [
                int(env.get("ucnrr_port", UCNRR_DEFAULT_PORT)),
                int(env.get("core_port", CORE_DEFAULT_PORT)),
                int(env.get("react_port", REACT_DEFAULT_PORT)),
            ]
        )
        if forced:
            aggregate["forced_ports"] = {port: summary for port, summary in forced.items()}

    if "terminated" in aggregate:
        aggregate["terminated"] = sorted(aggregate["terminated"])
    if "already_dead" in aggregate:
        aggregate["already_dead"] = sorted(aggregate["already_dead"])

    if request_rerun:
        _set_action_result(aggregate)
    _refresh_port_scans()
    if request_rerun:
        st.info("Stopped all services.")
        safe_rerun()
    return aggregate


def _wait_for_ucnrr_health(
    port: int,
    *,
    restart_callback: Optional[Callable[[], bool]] = None,
    status_callback: Optional[Callable[[Optional[str]], None]] = None,
    attempts: int = 10,
    interval: float = 3.0,
) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    url = f"http://127.0.0.1:{port}/health"
    last_detail: Optional[str] = None
    last_payload: Optional[Dict[str, Any]] = None
    llm_flag: Optional[bool] = None

    def _notify(message: Optional[str]) -> None:
        if message:
            composed = f"UCN/RR — {message}"
            _set_health_notice(composed)
        else:
            _set_health_notice(None)
        if status_callback:
            status_callback(message)

    for attempt in range(1, attempts + 1):
        service = _services().get(SERVICE_UCNRR)
        if service and not service.is_running():
            exit_code = services.poll_service(service)
            if exit_code is not None:
                detail = f"UCN/RR exited with code {exit_code} before llm_configured=true."
                _notify(detail)
                return False, detail, last_payload
            break

        ok, payload, error = _probe_health(url, timeout=2.5)
        if ok and isinstance(payload, dict):
            last_payload = payload
            llm_flag = bool(payload.get("llm_configured")) if "llm_configured" in payload else None
            if llm_flag:
                _notify(None)
                return True, None, payload
            last_detail = "llm_configured=false"
            _notify("waiting for LLM model (llm_configured=false)…")
        else:
            last_detail = error
            if error:
                _notify(f"waiting for LLM model ({error})…")
            else:
                _notify("waiting for LLM model (health unavailable)…")

        if attempt < attempts:
            time.sleep(interval)

    if llm_flag is False and restart_callback:
        _notify("failed to load model, retrying with clean env…")
        restarted = restart_callback()
        if restarted:
            time.sleep(1.0)
            return _wait_for_ucnrr_health(
                port,
                restart_callback=None,
                status_callback=status_callback,
                attempts=attempts,
                interval=interval,
            )
        detail = "UCN/RR restart failed with clean env."
        _notify(detail)
        return False, detail, last_payload

    return False, last_detail, last_payload


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


def _wait_for_react_health(port: int, timeout: float = 45.0) -> tuple[bool, Optional[str], Optional[str]]:
    deadline = time.time() + timeout
    last_note: Optional[str] = None
    current_port = port

    def _chunk_url(for_port: int) -> str:
        return f"http://127.0.0.1:{for_port}/_next/static/chunks/webpack.js"

    def _head_coach_url(for_port: int) -> str:
        return f"http://127.0.0.1:{for_port}{HEAD_COACH_URL_SUFFIX}"

    def _benchmarks_url(for_port: int) -> str:
        return f"http://127.0.0.1:{for_port}{LLM_BENCHMARKS_URL_SUFFIX}"

    chunk_url = _chunk_url(current_port)
    head_coach_url = _head_coach_url(current_port)
    benchmarks_url = _benchmarks_url(current_port)

    while time.time() < deadline:
        service = _services().get(SERVICE_REACT)
        if service and not service.is_running():
            exit_code = services.poll_service(service)
            if exit_code is not None:
                last_note = f"React exited with code {exit_code} before readiness checks completed."
            break
        if service is None:
            time.sleep(0.5)
            continue

        state_info = _load_state().get(SERVICE_REACT)
        if state_info:
            candidate = state_info.actual_port or state_info.port
            if candidate and int(candidate) != current_port:
                current_port = int(candidate)
                chunk_url = _chunk_url(current_port)
                head_coach_url = _head_coach_url(current_port)
                benchmarks_url = _benchmarks_url(current_port)

        target_url = head_coach_url

        chunk_ok = False
        try:
            chunk_response = requests.get(chunk_url, timeout=1.8, allow_redirects=True)
            chunk_ok = chunk_response.status_code == 200
            if chunk_ok:
                try:
                    home_response = requests.get(head_coach_url, timeout=2.0, allow_redirects=True)
                    if home_response.status_code == 200:
                        return True, None, target_url
                    last_note = f"{head_coach_url} → HTTP {home_response.status_code}"
                except Exception as exc:
                    last_note = f"{head_coach_url} → {exc}"
                if head_coach_url != benchmarks_url:
                    try:
                        bench_response = requests.get(benchmarks_url, timeout=2.0, allow_redirects=True)
                        if bench_response.status_code == 200:
                            return True, None, target_url
                        last_note = f"{benchmarks_url} → HTTP {bench_response.status_code}"
                    except Exception as exc:
                        last_note = f"{benchmarks_url} → {exc}"
            last_note = f"{chunk_url} → HTTP {chunk_response.status_code}"
        except Exception as exc:
            last_note = f"{chunk_url} → {exc}"

        time.sleep(0.75)

    return False, last_note, None


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
                range_start = configured_port + 1
                range_end = port_range[1] if port_range else configured_port + 100
                suggested = ports.find_free_port(range_start, range_end)
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

    command = _compose_core_command(configured_port, start_cmd)

    env_vars = dict(env_extra)
    last_launch_env: Dict[str, str] = dict(env_vars)
    last_launch_env = dict(env_vars)

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
    _set_ucnrr_action(None, None)
    port_key = SERVICE_PORT_KEYS.get(name)
    configured_port = int(port or env_config.get(port_key, UCNRR_DEFAULT_PORT))
    health_url = f"http://127.0.0.1:{configured_port}/health"

    with st.spinner("Ensuring LLM runtime is ready…"):
        llm_ready, llm_message, llm_log = _ensure_llm_runtime(env_config)
    if not llm_ready:
        failure_message = llm_message or "Unable to reach local LLM runtime."
        st.error(failure_message)
        _set_ucnrr_action("llm_failed", failure_message)
        if llm_log:
            st.code(llm_log, language="text")
        return
    if llm_message:
        st.info(llm_message)
        if llm_log:
            with st.expander("LLM bootstrap output (tail)", expanded=False):
                st.code(llm_log, language="text")

    port_in_use = _is_port_in_use(configured_port)
    if port_in_use:
        pid = _pid_on_port(configured_port)
        cmd = _describe_process(pid) if pid else ""
        cmd_lower = cmd.lower()
        health_payload: Optional[Dict[str, Any]] = None
        llm_configured: Optional[bool] = None

        try:
            response = requests.get(health_url, timeout=1.5, allow_redirects=True)
            if response.status_code == 200:
                health_payload = response.json()
                if isinstance(health_payload, dict):
                    llm_configured = bool(health_payload.get("llm_configured"))
        except Exception:
            health_payload = None
            llm_configured = None

        expected_process = bool(
            pid and "uvicorn" in cmd_lower and "ucnrr_app" in cmd_lower
        )

        if expected_process and llm_configured is True:
            message = f"Reusing UCN/RR on port {configured_port} (PID {pid})"
            st.info(message)
            _set_ucnrr_action("reused", message)
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

        if expected_process and llm_configured is False:
            message = f"Restarting UCN/RR with LLM env (llm_configured=false on port {configured_port})."
            st.warning(message)
            _set_ucnrr_action("restarting", message)
            if _services().get(name):
                _stop_service(name, rerun=False)
            else:
                ports.kill_pids([pid])
            time.sleep(0.5)
            port_in_use = _is_port_in_use(configured_port)

        elif expected_process:
            message = f"Restarting UCN/RR with LLM env on port {configured_port}."
            st.info(message)
            _set_ucnrr_action("restarting", message)
            if _services().get(name):
                _stop_service(name, rerun=False)
            else:
                ports.kill_pids([pid])
            time.sleep(0.5)
            port_in_use = _is_port_in_use(configured_port)

        if port_in_use:
            with st.container(border=True):
                st.warning(
                    f"Port {configured_port} is occupied by: {cmd or 'unknown process'}"
                )
                range_start = configured_port + 1
                range_end = port_range[1] if port_range else configured_port + 100
                suggested = ports.find_free_port(range_start, range_end)
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
    last_launch_env: Dict[str, str] = dict(env_vars)
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
        def _resolve_model(source_env: Dict[str, str]) -> str:
            for key in ("LLM_MODEL", "HC_CHAT_MODEL"):
                candidate = source_env.get(key) or env_config.get(key)
                if candidate:
                    return str(candidate)
            return "phi3:mini"

        def _restart_ucnrr_clean_env() -> bool:
            message = f"Retrying UCN/RR with clean LLM env on port {configured_port}."
            st.warning(message)
            _set_ucnrr_action("retrying", message)
            if _services().get(name):
                _stop_service(name, rerun=False)
            else:
                pid = _pid_on_port(configured_port)
                if pid:
                    ports.kill_pids([pid])
            time.sleep(0.5)
            clean_env = dict(env_vars)
            clean_env["LLM_PROVIDER"] = "ollama"
            clean_env["LLM_MODEL"] = _resolve_model(clean_env)
            clean_env.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            prev_retry_cwd = os.getcwd()
            _set_start_lock(name, True)
            try:
                os.chdir(str(workdir))
                restarted = _start_service(
                    name,
                    start_cmd,
                    workdir,
                    clean_env,
                    configured_port,
                    configured_port,
                )
            finally:
                os.chdir(prev_retry_cwd)
                _set_start_lock(name, False)
            if restarted:
                last_launch_env.clear()
                last_launch_env.update(clean_env)
            return restarted

        healthy, detail, payload = _wait_for_ucnrr_health(
            configured_port,
            restart_callback=_restart_ucnrr_clean_env,
        )

        provider = ""
        model = ""
        if isinstance(payload, dict):
            provider = str(payload.get("llm_provider") or "")
            model = str(payload.get("llm_model") or "")
        if not provider:
            provider = str(last_launch_env.get("LLM_PROVIDER") or "")
        if not model:
            model = str(last_launch_env.get("LLM_MODEL") or _resolve_model(last_launch_env))

        if healthy:
            summary = f"UCN/RR ready on port {configured_port}"
            if provider:
                summary = f"{summary} · {provider}"
            if model:
                summary = f"{summary} · {model}"
            summary = f"{summary} · llm_configured ✅"
            _set_ucnrr_action("ready", summary)
            _set_health_notice(None)
        else:
            failure_msg = detail or "Timed out waiting for llm_configured=true"
            _set_health_notice(f"UCN/RR health check failed: {failure_msg}")
            st.warning(f"UCN/RR health check failed: {failure_msg}")
            _set_ucnrr_action("failed", failure_msg)
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

    env_config = _env()
    configured_port = int(port or env_config.get("react_port", REACT_DEFAULT_PORT))
    listeners = ports.who_listens(configured_port) if configured_port else []
    if listeners:
        st.info(
            f"React configured port {configured_port} is occupied; Next.js will request a new port if available."
        )
        for row in listeners:
            pid = row.get("pid")
            cmd = row.get("cmd") or "(unknown command)"
            st.code(f"{pid}: {cmd}", language="text")

    workdir = Path(cwd) if cwd else _resolve_react_workdir(env_config)
    if not workdir.exists():
        st.error(f"React working dir '{workdir}' does not exist.")
        return

    npm_cmd = _resolve_react_npm(env_config)
    if not npm_cmd:
        message = "Unable to locate npm. Run `npm install` in the web/ directory or set the npm path in Environment & Ports."
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

    _kill_existing_next_servers(configured_port)

    prev_cwd = os.getcwd()
    _set_start_lock(name, True)
    success = False
    try:
        os.chdir(str(workdir))
        success = _start_service(
            name,
            _react_command(npm_cmd),
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

    healthy, detail, ready_url = _wait_for_react_health(configured_port)
    if not healthy and detail:
        _set_health_notice(detail)
    elif ready_url:
        pending = dict(_pending_auto_open())
        if pending.pop(name, None) is not None:
            _set_pending_auto_open(pending)
        st.info("Opening Head Coach (Northstar)…")
        _open_ui(ready_url, "Head Coach", notify=False)
        if bool(env_config.get("AUTO_OPEN_BENCHMARKS_AFTER_LAUNCH", False)):
            base_for_bench = ready_url.split('?')[0].rstrip('/')
            bench_url = f"{base_for_bench}{LLM_BENCHMARKS_URL_SUFFIX}"
            st.info("Opening LLM Benchmarks (AI Readiness)…")
            _open_ui(bench_url, "LLM Benchmarks", notify=False)

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
    core_port = int(env.get("core_port", CORE_DEFAULT_PORT))
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
    # SERVICE_DEV_EXPLORER removed - retired in favor of DevX (port 3100)
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


def _schedule_ai_autorefresh(interval_ms: int = 10_000) -> None:
    if st_autorefresh:
        st_autorefresh(interval=interval_ms, key="ai-readiness-autorefresh")  # type: ignore[misc]
    else:  # pragma: no cover - fallback best effort
        components.html(
            f"""
            <script>
            const frame = window.frameElement;
            if (frame && window.parent) {{
                setTimeout(() => {{
                    window.parent.postMessage({{type: "streamlit:rerun"}}, "*");
                }}, {interval_ms});
            }}
            </script>
            """,
            height=0,
            width=0,
        )


def _fetch_ai_readiness() -> Dict[str, Any]:
    env_config = _env()
    _apply_devx_env(env_config)
    backend_port = _devx_backend_port(env_config)
    devx_base = str(env_config.get("DEVX_BASE") or f"http://127.0.0.1:{backend_port}")
    url = f"{devx_base.rstrip('/')}/devx/api/ingestion/ai_ready"

    try:
        response = requests.get(url, timeout=3)
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "DevX backend unreachable"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    if response.status_code == 404:
        return {"status": "error", "message": "DevX: 404", "code": 404}
    if not response.ok:
        snippet = response.text[:120].strip()
        return {"status": "error", "message": f"HTTP {response.status_code} {snippet}"}
    try:
        data = response.json()
    except ValueError:
        return {"status": "error", "message": "Invalid JSON from DevX probe"}
    return {"status": "ok", "data": data}


def _format_layer_tooltip(name: str, light: Optional[Dict[str, Any]], success: Callable[[Dict[str, Any]], str]) -> str:
    if not isinstance(light, dict):
        return f"🔴 {name}: unavailable"
    status = light.get("status")
    icon = "🟢" if status == "green" else "🔴"
    if status == "green":
        try:
            message = success(light)
        except Exception:
            message = "ready"
    else:
        message = str(light.get("reason") or "needs attention")
    if not message:
        message = "ready" if status == "green" else "needs attention"
    return f"{icon} {name}: {message}"


def _render_ai_readiness_sidebar() -> None:
    env = _env()
    _schedule_ai_autorefresh()
    readiness = _fetch_ai_readiness()

    react_port = int(env.get("react_port", REACT_DEFAULT_PORT))
    target_port = react_port
    health_map = st.session_state.get(SESSION_HEALTH_KEY, {})
    health_entry = health_map.get(SERVICE_REACT)
    if isinstance(health_entry, ServiceHealth):
        for candidate in (health_entry.actual_port, health_entry.port, health_entry.configured_port):
            if candidate:
                try:
                    target_port = int(candidate)
                    break
                except Exception:
                    continue
    target_url = f"http://127.0.0.1:{target_port}/tools/llm-benchmarks?tab=ai-readiness"

    tooltip = "Unable to fetch readiness status."
    caption_hint: Optional[str] = None
    label = "AI Readiness: ❌ NEEDS-FIX"

    if readiness.get("status") == "ok":
        data = readiness.get("data", {})
        hc_light = data.get("hc_devx", {})
        ucnrr_light = data.get("ucnrr", {})
        core_light = data.get("core", {})
        e2e_light = {}
        if isinstance(core_light, dict):
            details = core_light.get("details") or {}
            if isinstance(details, dict):
                e2e_light = details.get("e2e", {}) or {}

        tooltip_lines = [
            _format_layer_tooltip("HC/DevX", hc_light, lambda _: "online"),
            _format_layer_tooltip(
                "UCNRR",
                ucnrr_light,
                lambda light: " · ".join(
                    filter(
                        None,
                        [
                            str(light.get("details", {}).get("llm_provider", "")),
                            str(light.get("details", {}).get("llm_model", "")),
                        ],
                    )
                )
                or "configured",
            ),
            _format_layer_tooltip(
                "Core",
                core_light,
                lambda light: f"rr_mode {light.get('details', {}).get('rr_mode', 'unknown')} · "
                f"ucnrr {'on' if light.get('details', {}).get('ucnrr_enabled') else 'off'}",
            ),
            _format_layer_tooltip(
                "E2E",
                e2e_light if isinstance(e2e_light, dict) else {},
                lambda light: str(light.get("reason") or "Why-Card ready"),
            ),
        ]
        tooltip = "\n".join(tooltip_lines)
        overall = str(data.get("result") or "").upper()
        label = "AI Readiness: ✅ ALL-GOOD" if overall == "ALL-GOOD" else "AI Readiness: ❌ NEEDS-FIX"
    else:
        message = readiness.get("message", "unknown error")
        tooltip = f"DevX probe failed: {message}"
        if readiness.get("code") == 404:
            caption_hint = "Hint: start DevX backend (Quick Launch → Developer Explorer)."

    if st.sidebar.button(label, key="ai-readiness-pill", help=tooltip):
        _open_ui(target_url, "LLM Benchmarks", notify=False)
    if st.sidebar.button("Refresh", key="ai-readiness-refresh"):
        safe_rerun()
    if caption_hint:
        st.sidebar.caption(caption_hint)


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


def _launch_stack(
    env: Dict[str, Any],
    core_port: int,
    react_port: int,
    ucnrr_port: int,
    core_workdir_path: Path,
    react_workdir_path: Path,
    ucnrr_workdir_path: Path,
    core_command_list: Optional[List[str]],
    react_npm_cmd: Optional[str],
    open_ui: bool = True,
    sidebar_logger: Optional[Callable[[str], None]] = None,
) -> None:
    status_placeholder = st.empty()
    status_lines: List[str] = []

    def _update_status(service: str, icon: str, message: str) -> None:
        entry = f"- {icon} **{service}** — {message}"
        status_lines.append(entry)
        status_placeholder.markdown("\n".join(status_lines))
        if sidebar_logger:
            sidebar_logger(f"{icon} {service}: {message}")

    runtime_npm_cmd = react_npm_cmd or _resolve_react_npm(env)
    if runtime_npm_cmd is None:
        message = "Unable to locate npm. Run `npm install` in web/ or configure the npm path under Environment & Ports."
        _update_status("React", "❌", message)
        st.error(message)
        return

    st.session_state[SESSION_SUPPRESS_RERUN_KEY] = True
    try:
        # UCN/RR
        _update_status("UCN/RR", "⏳", "Starting…")
        with st.spinner("Starting UCN/RR…"):
            _handle_start_request(
                SERVICE_UCNRR,
                "UCN/RR",
                _ucnrr_command(env, ucnrr_port),
                ucnrr_workdir_path,
                _ucnrr_env(env),
                ucnrr_port,
                UCNRR_PORT_RANGE,
            )
        _update_status("UCN/RR", "⏳", "Waiting for LLM model (llm_configured=false)…")
        healthy_ucnrr, detail_ucnrr, payload_ucnrr = _wait_for_ucnrr_health(ucnrr_port)
        if not healthy_ucnrr:
            failure_msg = detail_ucnrr or "Timed out waiting for llm_configured=true"
            _update_status("UCN/RR", "❌", failure_msg)
            _set_health_notice(f"UCN/RR launch failed: {failure_msg}")
            return
        action = st.session_state.get(SESSION_UCNRR_LAST_ACTION_KEY)
        action_message = st.session_state.get(SESSION_UCNRR_LAST_MESSAGE_KEY)
        if action_message:
            _update_status("UCN/RR", "ℹ️", action_message)
        provider = ""
        model = ""
        if isinstance(payload_ucnrr, dict):
            provider = str(payload_ucnrr.get("llm_provider") or "")
            model = str(payload_ucnrr.get("llm_model") or "")
        action_phrase = "Restarted UCN/RR"
        if action == "reused":
            action_phrase = "Reusing UCN/RR"
        summary_parts = [action_phrase]
        if provider:
            summary_parts.append(provider)
        if model:
            summary_parts.append(model)
        summary_parts.append("llm_configured ✅")
        summary_ucnrr = " · ".join(part for part in summary_parts if part)
        _set_ucnrr_action(None, None)
        _update_status("UCN/RR", "✅", summary_ucnrr)

        # Core
        _update_status("Core", "⏳", "Starting…")
        with st.spinner("Starting Core…"):
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
        _update_status("Core", "⏳", "Waiting for rr_mode=online…")
        healthy_core, detail_core = _wait_for_core_health(core_port)
        if not healthy_core:
            failure_msg = detail_core or "Timed out waiting for rr_mode=online"
            _update_status("Core", "❌", failure_msg)
            _set_health_notice(f"Core launch failed: {failure_msg}")
            return
        _update_status("Core", "✅", "rr_mode online")

        # React
        _update_status("React", "⏳", "Starting…")
        with st.spinner("Starting React…"):
            _handle_start_request(
                SERVICE_REACT,
                "React (Next.js)",
                _react_command(runtime_npm_cmd),
                react_workdir_path,
                _react_env(env),
                react_port,
                REACT_PORT_RANGE,
            )
        _update_status("React", "⏳", "Waiting for Next.js readiness…")
        healthy_react, detail_react, ready_url = _wait_for_react_health(react_port)
        if not healthy_react:
            failure_msg = detail_react or "Timed out waiting for Next.js"
            _update_status("React", "❌", failure_msg)
            _set_health_notice(f"React launch failed: {failure_msg}")
            return
        _refresh_health()
        base_url = _build_service_url(SERVICE_REACT)
        if base_url:
            try:
                actual_port = int(base_url.split(":")[2].split("/")[0])
            except Exception:
                actual_port = react_port
        else:
            actual_port = react_port
        _update_status("React", "✅", f"port {actual_port}")

        _set_health_notice(None)

        if open_ui:
            target_url = ready_url
            if not target_url and base_url:
                target_url = base_url.rstrip('/') + HEAD_COACH_URL_SUFFIX
            if target_url:
                pending = dict(_pending_auto_open())
                if pending.pop(SERVICE_REACT, None) is not None:
                    _set_pending_auto_open(pending)
                st.info("Opening Head Coach (Northstar)…")
                _open_ui(target_url, "Head Coach", notify=False)
                if bool(env.get("AUTO_OPEN_BENCHMARKS_AFTER_LAUNCH", False)):
                    base_for_bench = target_url.split('?')[0].rstrip('/')
                    bench_url = f"{base_for_bench}{LLM_BENCHMARKS_URL_SUFFIX}"
                    st.info("Opening LLM Benchmarks (AI Readiness)…")
                    _open_ui(bench_url, "LLM Benchmarks", notify=False)
    finally:
        st.session_state[SESSION_SUPPRESS_RERUN_KEY] = False
        _refresh_health()


def _render_launch_tab() -> None:
    env = _env()
    core_port = int(env.get("core_port", CORE_DEFAULT_PORT))
    react_port = int(env.get("react_port", REACT_DEFAULT_PORT))
    streamlit_port = int(env.get("streamlit_port", STREAMLIT_DEFAULT_PORT))
    ucnrr_port = int(env.get("ucnrr_port", UCNRR_DEFAULT_PORT))
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
    col_launch, col_open, col_stop, col_restart = st.columns(4)
    launch_disabled = _is_env_dirty() or bool(_start_locks())
    if react_npm_cmd is None:
        launch_disabled = True
    with col_launch:
        if st.button(
            "Launch All (open UI)",
            help="Start UCN/RR → Core → React with AI env and open the AI Readiness tab",
            disabled=launch_disabled,
        ):
            _update_next_public_base()
            _launch_stack(
                env,
                core_port,
                react_port,
                ucnrr_port,
                core_workdir_path,
                react_workdir_path,
                ucnrr_workdir_path,
                core_command_list,
                react_npm_cmd,
                open_ui=True,
            )
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
            with st.spinner("Stopping all managed services…"):
                summary = _stop_all_services(request_rerun=False)
            if summary:
                _set_action_result(summary)
            st.success("All services stopped and ports cleared.")
            _refresh_health()
            safe_rerun()
    with col_restart:
        if st.button(
            "Restart All",
            help="Stop everything, then relaunch the stack with AI env and open the AI Readiness tab",
            disabled=launch_disabled,
        ):
            sidebar_status = st.sidebar.empty()
            sidebar_lines: List[str] = []

            def _sidebar_log(message: str) -> None:
                sidebar_lines.append(f"- {message}")
                sidebar_status.markdown("\n".join(sidebar_lines))

            with st.spinner("Restarting stack…"):
                _sidebar_log("⏹️ Stopping existing services…")
                _stop_all_services(request_rerun=False)
                _sidebar_log("✅ Previous services stopped.")
                _launch_stack(
                    env,
                    core_port,
                    react_port,
                    ucnrr_port,
                    core_workdir_path,
                    react_workdir_path,
                    ucnrr_workdir_path,
                    core_command_list,
                    react_npm_cmd,
                    open_ui=True,
                    sidebar_logger=_sidebar_log,
                )

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
        UCNRR_PORT_RANGE,
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
        base = (
            env.get("OLLAMA_BASE_URL")
            or env.get("OLLAMA_BASE")
            or env.get("LLM_BASE_URL")
            or "http://127.0.0.1:11434"
        )
        base = str(base).strip().rstrip("/")
        model = (env.get("OLLAMA_MODEL") or env.get("LLM_MODEL") or "phi3:mini").strip()
        if not base:
            return {"status": "FAIL", "message": "OLLAMA_BASE_URL is missing."}

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


def _render_policy_tab() -> None:
    st.subheader("Policy Learner & Thresholds")
    core_base = _core_base_url()
    try:
        policies_payload = _core_get_policies()
    except requests.ConnectionError:
        st.info(f"Core not reachable at {core_base}. Start Core to manage policies.")
        return
    except requests.Timeout:
        st.warning(f"Core request timed out at {core_base}.")
        return
    except Exception as exc:
        st.error(f"Unable to load policies: {_format_request_error(exc)}")
        return

    try:
        learned_payload = _core_get_learned_policies()
    except Exception as exc:
        learned_payload = {}
        st.warning(f"Unable to load learned thresholds: {_format_request_error(exc)}")

    try:
        promotion_state = _core_get_promotion_state()
    except Exception as exc:
        promotion_state = {}
        st.warning(f"Unable to load enabled policy map: {_format_request_error(exc)}")

    policies_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(policies_payload, dict):
        policies_map = policies_payload.get("policies") or {}
        if not isinstance(policies_map, dict):
            policies_map = {}

    learned_map: Dict[str, Any] = {}
    if isinstance(learned_payload, dict):
        learned_map = learned_payload.get("learned_thresholds") or {}
        if not isinstance(learned_map, dict):
            learned_map = {}

    learner_enabled = bool(policies_payload.get("learner_enabled")) if isinstance(policies_payload, dict) else False
    learner_window_raw = policies_payload.get("window") if isinstance(policies_payload, dict) else None
    try:
        learner_window_default = int(learner_window_raw) if learner_window_raw is not None else 25
    except (TypeError, ValueError):
        learner_window_default = 25

    learner_cols = st.columns([1.2, 1.2, 0.8])
    with learner_cols[0]:
        learner_enabled_state = st.checkbox(
            "Learner enabled",
            value=learner_enabled,
            key="policy_learner_enabled_toggle",
        )
    with learner_cols[1]:
        learner_window_state = st.number_input(
            "Window",
            value=int(max(1, learner_window_default)),
            min_value=1,
            max_value=1000,
            step=1,
            key="policy_learner_window_input",
        )
    with learner_cols[2]:
        if st.button("Save", key="policy_learner_save"):
            try:
                _core_set_learner(bool(learner_enabled_state), int(learner_window_state))
                st.success("Updated learner configuration.")
                safe_rerun()
            except Exception as exc:
                st.error(f"Failed to update learner: {_format_request_error(exc)}")

    st.markdown("### Learned Thresholds")
    filter_value = st.text_input(
        "Filter traits",
        value="",
        key="policy_filter_input",
        placeholder="Type to filter trait id…",
    ).strip().lower()

    def _as_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_rr(value: Optional[float]) -> str:
        if value is None:
            return "—"
        if abs(value) >= 100:
            return f"{value:.0f}"
        return f"{value:.1f}"

    def _format_int(value: Any) -> str:
        if value in (None, "", 0):
            return "—"
        try:
            return f"{int(value)}"
        except (TypeError, ValueError):
            return "—"

    def _render_numeric(column: "st.delta_generator.DeltaGenerator", label: str) -> None:
        column.markdown(
            f"<div style='text-align:right; font-family:var(--font-mono, monospace);'>{label}</div>",
            unsafe_allow_html=True,
        )

    learned_rows: List[Dict[str, Any]] = []
    for trait_id, entry in policies_map.items():
        if not isinstance(entry, dict):
            continue
        base_rr = _as_float(entry.get("base_rr"))
        learned_rr = _as_float(entry.get("learned_rr"))
        fallback = learned_map.get(trait_id) if isinstance(learned_map, dict) else {}
        if not isinstance(fallback, dict):
            fallback = {}
        samples = entry.get("sample_size") if entry.get("sample_size") not in (None, "") else fallback.get("sample_size")
        last_update = entry.get("last_update") or fallback.get("last_update")
        if learned_rr is not None and base_rr is not None:
            effective_rr = max(base_rr, learned_rr)
        elif learned_rr is not None:
            effective_rr = learned_rr
        else:
            effective_rr = base_rr
        learned_rows.append(
            {
                "trait": trait_id,
                "base": base_rr,
                "learned": learned_rr,
                "effective": effective_rr,
                "samples": samples,
                "last_update": last_update,
            }
        )

    if filter_value:
        learned_rows = [row for row in learned_rows if filter_value in row["trait"].lower()]

    learned_rows.sort(
        key=lambda row: (
            row["effective"] is not None,
            row["effective"] if row["effective"] is not None else -1,
        ),
        reverse=True,
    )

    header_cols = st.columns([3.2, 1.2, 1.2, 1.2, 0.9, 1.6, 2.5])
    header_cols[0].markdown("**Trait**")
    header_cols[1].markdown("**Base RR**")
    header_cols[2].markdown("**Learned RR**")
    header_cols[3].markdown("**Effective RR**")
    header_cols[4].markdown("**Samples**")
    header_cols[5].markdown("**Last Update**")
    header_cols[6].markdown("**Actions**")

    for row in learned_rows:
        trait_id = row["trait"]
        base_rr = row["base"]
        learned_rr = row["learned"]
        effective_rr = row["effective"]
        samples = row["samples"]
        last_update = row["last_update"] or "—"
        badge = "🟠" if learned_rr is not None else "🟢"
        key_safe = trait_id.replace(".", "_").replace("/", "_").replace(" ", "_")

        body_cols = st.columns([3.2, 1.2, 1.2, 1.2, 0.9, 1.6, 2.5])
        body_cols[0].markdown(f"{badge} `{trait_id}`")
        _render_numeric(body_cols[1], _format_rr(base_rr))
        _render_numeric(body_cols[2], _format_rr(learned_rr))
        _render_numeric(body_cols[3], _format_rr(effective_rr))
        _render_numeric(body_cols[4], _format_int(samples))
        body_cols[5].markdown(f"<div style='font-family:var(--font-mono, monospace); font-size:0.85rem;'>{last_update}</div>", unsafe_allow_html=True)

        action_input_col, action_save_col, action_clear_col = body_cols[6].columns([1.4, 0.8, 0.8])
        default_value = learned_rr if learned_rr is not None else (base_rr if base_rr is not None else 0.0)
        new_value = action_input_col.number_input(
            "Learned RR",
            value=float(default_value if default_value is not None else 0.0),
            min_value=0.0,
            max_value=1000.0,
            step=1.0,
            key=f"policy_input_{key_safe}",
            label_visibility="collapsed",
        )
        if action_save_col.button("Save", key=f"policy_save_{key_safe}"):
            try:
                _core_set_learned_rr(trait_id, float(new_value))
                st.success(f"Updated learned RR for {trait_id} → {new_value:.1f}")
                safe_rerun()
            except Exception as exc:
                st.error(f"Failed to update {trait_id}: {_format_request_error(exc)}")
        if action_clear_col.button("Clear", key=f"policy_clear_{key_safe}"):
            try:
                _core_clear_learned_rr(trait_id)
                st.success(f"Cleared learned RR for {trait_id}")
                safe_rerun()
            except Exception as exc:
                st.error(f"Failed to clear {trait_id}: {_format_request_error(exc)}")

    st.markdown("### Diagnostics")
    diag_cols = st.columns(2)
    enabled_payload = promotion_state if isinstance(promotion_state, dict) else {}
    policy_payload_json = json.dumps(policies_payload, indent=2, sort_keys=True) if isinstance(policies_payload, dict) else "{}"
    enabled_payload_json = json.dumps(enabled_payload, indent=2, sort_keys=True)

    with diag_cols[0]:
        st.markdown("#### Enabled Policies")
        st.code(enabled_payload_json, language="json")
        st.download_button(
            "Copy JSON",
            data=enabled_payload_json,
            file_name="enabled_policies.json",
            mime="application/json",
            key="download_enabled_policies",
        )

    with diag_cols[1]:
        st.markdown("#### Policy Map")
        st.code(policy_payload_json, language="json")
        st.download_button(
            "Copy JSON",
            data=policy_payload_json,
            file_name="policy_map.json",
            mime="application/json",
            key="download_policy_map",
        )


def _render_env_tab() -> None:
    config_tab, policy_tab = st.tabs(["Configuration", "Policy"])
    with config_tab:
        env = _env()
        detected_ports = st.session_state.get(SESSION_DETECTED_PORTS_KEY, {})
        react_detected = detected_ports.get(SERVICE_REACT)
        core_detected = detected_ports.get(SERVICE_CORE)
        ucnrr_detected = detected_ports.get(SERVICE_UCNRR)
        raw_frontend_flags = str(env.get("NEXT_PUBLIC_FLAGS", "") or "")
        frontend_flag_values, frontend_passthrough = _parse_frontend_flag_string(raw_frontend_flags)
        manifest_path = Path("docs/ReDNA_Workspace_Manifest.md")

        st.markdown("### Workspace Manifest")
        manifest_cols = st.columns([1, 3])
        with manifest_cols[0]:
            if st.button("Open Workspace Manifest", key="manifest-open-button"):
                resolved = manifest_path.resolve()
                success = False
                error: Optional[str] = None
                if manifest_path.exists():
                    try:
                        success = bool(webbrowser.open(f"file://{resolved}"))
                    except Exception as exc:
                        error = str(exc)
                        success = False
                else:
                    error = f"Manifest not found at {resolved}"
                print(f"[Manifest] Open requested → {resolved}")
                st.session_state[SESSION_MANIFEST_OPEN_STATE_KEY] = {
                    "path": str(resolved),
                    "success": success,
                    "error": error,
                }
        with manifest_cols[1]:
            manifest_state = st.session_state.get(SESSION_MANIFEST_OPEN_STATE_KEY, {})
            manifest_path_str = str(manifest_state.get("path") or manifest_path.resolve())
            if manifest_state.get("success"):
                st.success(f"Opened manifest at {manifest_path_str}")
            else:
                if manifest_state:
                    st.info("Manifest available locally. Use the path below if the viewer did not open.")
                    _render_copy_path(manifest_path_str, element_id="manifest-path-input")
                    if manifest_state.get("error"):
                        st.caption(f"Open attempt reported: {manifest_state['error']}")
                elif not manifest_path.exists():
                    st.error(f"Manifest not found at {manifest_path.resolve()}")

        st.markdown("#### Services & Ports")
        manifest_result = manifest_parser.read_manifest(manifest_path)
        if "error" in manifest_result:
            st.warning(
                f"{manifest_result['error']}. Use the Open Workspace Manifest button to review the latest document."
            )
            if manifest_path.exists():
                _render_copy_path(str(manifest_path.resolve()))
        else:
            parsed_table = manifest_parser.extract_services_table(str(manifest_result["text"]))
            if "error" in parsed_table:
                st.warning(f"{parsed_table['error']}. Open the manifest to verify the Services & Ports section.")
            else:
                headers = parsed_table.get("headers", [])
                rows = parsed_table.get("rows", [])
                ordered_rows = [
                    {header: row.get(header, "") for header in headers}
                    for row in rows
                ]
                if ordered_rows:
                    st.dataframe(ordered_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("Services & Ports table is currently empty in the manifest.")
                st.caption("Source: docs/ReDNA_Workspace_Manifest.md → ## 2. Services & Ports")

        with st.expander("System Health", expanded=False):
            _render_system_health_panel(env)

        with st.expander("Intel", expanded=False):
            _render_intel_drawer()

        st.subheader("Environment & Flags")
        if _is_env_dirty():
            st.warning("Environment changes pending Save.")
        submitted = False
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
                st.caption(f"Detected React on port {react_detected}; your saved config is {saved_react_port}.")
            devx_backend_port_input = st.number_input(
                "DevX backend port",
                value=int(env.get("DEVX_BACKEND_PORT", DEVX_BACKEND_DEFAULT_PORT)),
                min_value=1000,
                max_value=65000,
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
                    or envstore.DEFAULT_ENV.get(
                        "ucnrr_start_command",
                        f"{ROOT / '.venv' / 'bin' / 'python'} -m uvicorn ucnrr_app:app --host 0.0.0.0 --port {{port}} --reload",
                    )
                ),
                help="Full command executed for UCN/RR (use {port} placeholder).",
            )
            st.caption("Ensure the command's --port uses {port} placeholder to match configured port.")
            ucnrr_port = st.number_input(
                "UCN/RR port",
                value=int(env.get("ucnrr_port", UCNRR_DEFAULT_PORT)),
                min_value=1000,
                max_value=65000,
            )
            ucnrr_port_value = int(ucnrr_port)
            if isinstance(ucnrr_detected, int) and ucnrr_detected != ucnrr_port_value:
                st.caption(f"Detected UCN/RR listener on port {ucnrr_detected}; your saved config is {ucnrr_port_value}.")

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
                    st.caption(f"Core health detected at {detected_base}; update this value if you want React to target it.")
                else:
                    st.caption("NEXT_PUBLIC_CORE_API_BASE matches the detected Core listener.")

            provider_options = ["ollama", "openai", "anthropic", "stub"]
            current_provider = str(env.get("HC_CHAT_PROVIDER", "ollama") or "ollama")
            provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
            chat_provider = st.selectbox("HC_CHAT_PROVIDER", options=provider_options, index=provider_index)

            st.markdown("### AI Environment")
            default_llm_start = str(
                env.get("llm_start_command")
                or (
                    f"bash {(ROOT / 'start_llm.sh').resolve()}"
                    if (ROOT / "start_llm.sh").exists()
                    else ""
                )
            )
            llm_start_command_input = st.text_input(
                "llm_start_command",
                value=default_llm_start,
                help="Optional command executed before launching UCN/RR to ensure the local LLM runtime is running (e.g., bash start_llm.sh).",
            )
            llm_provider_input = st.text_input(
                "LLM_PROVIDER",
                value=str(env.get("LLM_PROVIDER") or "ollama"),
                help="Primary LLM provider for Core and UCNRR services.",
            )
            llm_model_input = st.text_input(
                "LLM_MODEL",
                value=str(env.get("LLM_MODEL") or env.get("OLLAMA_MODEL") or "phi3:mini"),
                help="Model identifier applied to Core, UCNRR, and DevX probes.",
            )
            ollama_base_input = st.text_input(
                "OLLAMA_BASE_URL",
                value=str(env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_BASE") or "http://127.0.0.1:11434"),
                help="Base URL for the local Ollama runtime.",
            )
            ollama_model_input = st.text_input(
                "OLLAMA_MODEL",
                value=str(env.get("OLLAMA_MODEL") or env.get("LLM_MODEL") or "phi3:mini"),
                help="Optional override for Ollama-specific model selection.",
            )

            st.markdown("### OpenAI (paid)")
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

            current_ucnrr = env.get("UCNRR_BASE_URL") or env.get("UCNRR_BASE")
            default_ucnrr = current_ucnrr if isinstance(current_ucnrr, str) and current_ucnrr else f"http://127.0.0.1:{UCNRR_DEFAULT_PORT}"
            ucnrr_base_input = st.text_input("UCNRR_BASE_URL", value=default_ucnrr)
            ucnrr_score_path_input = st.text_input(
                "UCNRR_SCORE_PATH",
                value=str(env.get("UCNRR_SCORE_PATH") or "/api/rescore"),
            )

            auto_open_react = st.toggle(
                "Auto-open React after Launch All",
                value=bool(env.get("AUTO_OPEN_REACT_AFTER_LAUNCH", False)),
            )
            auto_open_benchmarks = st.toggle(
                "Open Benchmarks tab after start",
                value=bool(env.get("AUTO_OPEN_BENCHMARKS_AFTER_LAUNCH", False)),
            )
            auto_open_streamlit = st.toggle(
                "Auto-open Streamlit after Launch All",
                value=bool(env.get("AUTO_OPEN_STREAMLIT_AFTER_LAUNCH", False)),
            )
            append_debug = st.toggle(
                "Append ?ui_debug=1 when opening UIs",
                value=bool(env.get("APPEND_UI_DEBUG_PARAM", False)),
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
        openai_key_value = openai_key_input.strip() or None
        openai_model_value = openai_model_input.strip() or None
        llm_provider_value = (llm_provider_input or "ollama").strip() or "ollama"
        llm_model_value = (llm_model_input or "phi3:mini").strip() or "phi3:mini"
        ollama_base_value = (ollama_base_input or "http://127.0.0.1:11434").strip().rstrip("/") or "http://127.0.0.1:11434"
        ollama_model_value = (ollama_model_input or llm_model_value).strip() or llm_model_value
        llm_start_command_value = llm_start_command_input.strip()
        anthropic_key_value = anthropic_key_input.strip() or None
        anthropic_model_value = anthropic_model_input.strip() or None
        ucnrr_base_value = (ucnrr_base_input or f"http://127.0.0.1:{UCNRR_DEFAULT_PORT}").strip()
        ucnrr_score_path_value = (ucnrr_score_path_input or "/api/rescore").strip() or "/api/rescore"
        devx_base_value = f"http://127.0.0.1:{int(devx_backend_port_input)}"
        cors_origins_value = str(env.get("CORS_ALLOWED_ORIGINS") or "http://127.0.0.1:3000").strip() or "http://127.0.0.1:3000"
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
                "DEVX_BACKEND_PORT": int(devx_backend_port_input),
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
                "LLM_PROVIDER": llm_provider_value,
                "LLM_MODEL": llm_model_value,
                "LLM_BASE_URL": ollama_base_value,
                "llm_start_command": llm_start_command_value,
                "OPENAI_API_KEY": openai_key_value,
                "OPENAI_MODEL": openai_model_value,
                "OLLAMA_BASE": ollama_base_value,
                "OLLAMA_BASE_URL": ollama_base_value,
                "OLLAMA_MODEL": ollama_model_value,
                "ANTHROPIC_API_KEY": anthropic_key_value,
                "ANTHROPIC_MODEL": anthropic_model_value,
                "UCNRR_BASE_URL": ucnrr_base_value,
                "UCNRR_BASE": ucnrr_base_value,
                "UCNRR_SCORE_PATH": ucnrr_score_path_value,
                "DEVX_BASE": devx_base_value,
                "NEXT_PUBLIC_DEVX_API_BASE": devx_base_value or "http://127.0.0.1:8100",
                "NEXT_PUBLIC_UCNRR_API_BASE": ucnrr_base_value,
                "CORS_ALLOWED_ORIGINS": cors_origins_value,
                "AUTO_OPEN_REACT_AFTER_LAUNCH": bool(auto_open_react),
                "AUTO_OPEN_BENCHMARKS_AFTER_LAUNCH": bool(auto_open_benchmarks),
                "AUTO_OPEN_STREAMLIT_AFTER_LAUNCH": bool(auto_open_streamlit),
                # Removed: AUTO_OPEN_DEVEXPLORER (retired)
                "APPEND_UI_DEBUG_PARAM": bool(append_debug),
                # Removed: dev_explorer_port (retired - DevX uses 3100)
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
        _apply_devx_env(env)
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
    
        st.markdown("### AI Config (read-only)")
        ai_config = {
            "LLM_PROVIDER": str(env.get("LLM_PROVIDER") or "ollama"),
            "LLM_MODEL": str(env.get("LLM_MODEL") or env.get("OLLAMA_MODEL") or "phi3:mini"),
            "OLLAMA_BASE_URL": str(env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_BASE") or "http://127.0.0.1:11434"),
            "UCNRR_BASE": str(env.get("UCNRR_BASE") or env.get("UCNRR_BASE_URL") or f"http://127.0.0.1:{ucnrr_port}"),
            "UCNRR_SCORE_PATH": str(env.get("UCNRR_SCORE_PATH") or "/api/rescore"),
        }
        ai_cols = st.columns(2)
        with ai_cols[0]:
            st.text_input("LLM_PROVIDER", value=ai_config["LLM_PROVIDER"], disabled=True)
            st.text_input("LLM_MODEL", value=ai_config["LLM_MODEL"], disabled=True)
            st.text_input("OLLAMA_BASE_URL", value=ai_config["OLLAMA_BASE_URL"], disabled=True)
        with ai_cols[1]:
            st.text_input("UCNRR_BASE", value=ai_config["UCNRR_BASE"], disabled=True)
            st.text_input("UCNRR_SCORE_PATH", value=ai_config["UCNRR_SCORE_PATH"], disabled=True)
    
        apply_cols = st.columns([1, 3])
        with apply_cols[0]:
            if st.button("Apply & Restart", key="ai-config-apply"):
                if _is_env_dirty():
                    st.warning("Save environment changes before applying the AI config.")
                elif react_npm_cmd is None:
                    st.warning("Configure npm path before restarting the stack.")
                else:
                    with st.spinner("Restarting services with current AI configuration…"):
                        _stop_all_services(request_rerun=False)
                        _update_next_public_base()
                        _launch_stack(
                            env,
                            core_port,
                            react_port,
                            ucnrr_port,
                            core_workdir_path,
                            react_workdir_path,
                            ucnrr_workdir_path,
                            core_command_list,
                            react_npm_cmd,
                            open_ui=True,
                        )
        with apply_cols[1]:
            st.caption("Restarts UCNRR → Core → React using the values above to keep AI readiness in sync.")
    with policy_tab:
        _render_policy_tab()

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

    st.markdown("---")
    st.markdown("### 🧪 Post-Merge QA")
    st.caption("Runs: Mapper audit + Golden fixtures + Live smoke test")
    qa_cols = st.columns([1, 2])
    with qa_cols[0]:
        if st.button("Run Post-Merge QA"):
            # Run the QA harness
            qa_script = ROOT / "scripts" / "post_merge_qa.sh"
            if not qa_script.exists():
                st.error(f"QA script not found: {qa_script}")
            else:
                with st.spinner("Running post-merge QA harness..."):
                    env = os.environ.copy()
                    env.setdefault("QA_USER", "TEST_QA_USER")
                    env.setdefault("QA_ENDPOINT", "http://127.0.0.1:8015/ui/chat/send")
                    env.setdefault("DATA_ROOT", str(ROOT / "data"))

                    try:
                        proc = subprocess.run(
                            [str(qa_script)],
                            env=env,
                            cwd=ROOT,
                            text=True,
                            capture_output=True,
                            timeout=120  # 2 minute timeout
                        )

                        # Store result in session state
                        st.session_state["qa_result"] = {
                            "returncode": proc.returncode,
                            "stdout": proc.stdout,
                            "stderr": proc.stderr,
                        }
                    except subprocess.TimeoutExpired:
                        st.session_state["qa_result"] = {
                            "returncode": 1,
                            "stdout": "",
                            "stderr": "QA harness timed out after 120 seconds",
                        }
                    except Exception as e:
                        st.session_state["qa_result"] = {
                            "returncode": 1,
                            "stdout": "",
                            "stderr": f"Error running QA harness: {e}",
                        }

                safe_rerun()

    with qa_cols[1]:
        if "qa_result" in st.session_state:
            result = st.session_state["qa_result"]

            if result["returncode"] == 0:
                st.success("✅ QA PASSED — Ready for merge!")
            else:
                st.error("❌ QA FAILED — See output below")

            if result["stdout"]:
                st.code(result["stdout"], language="text")

            if result["stderr"]:
                st.error("Errors:")
                st.code(result["stderr"], language="text")
        else:
            st.caption("Click 'Run Post-Merge QA' to validate the resolver pipeline")


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


def _nuclear_reset_all_services() -> Dict[str, Any]:
    """
    Nuclear option: Kill ALL services on all known ports except CP++.
    Returns a dictionary with kill results for each service.
    """
    import subprocess
    from datetime import datetime

    results = {
        "killed_pids": [],
        "errors": [],
        "ports_cleared": [],
        "ports_scanned": [],
        "ports_empty": [],
        "diagnostic_log": [],
        "cp_port": None,
        "timestamp": datetime.now().isoformat(),
    }

    def log(msg: str):
        results["diagnostic_log"].append(msg)

    log("=== NUCLEAR RESET DIAGNOSTICS ===")

    # Get CP++ port to avoid killing ourselves
    cp_port = None
    for key in ("STREAMLIT_SERVER_PORT", "PORT"):
        val = os.environ.get(key)
        log(f"Checking env var {key}: {val}")
        if val and val.isdigit():
            cp_port = int(val)
            break

    results["cp_port"] = cp_port
    log(f"CP++ port identified as: {cp_port}")

    # All known service ports
    # Expand ranges to catch all possible ports services might be running on
    all_ports = {
        "Core": list(range(8000, 8020)),  # Expanded to catch 8015 and others
        "UCNRR": list(range(UCNRR_PORT_RANGE[0], UCNRR_PORT_RANGE[1] + 1)),
        "React/Next.js": list(range(3000, 3010)),  # Expanded to catch 3001, 3002, etc.
        "DevX Backend": [8100, 8101, 8102],
        "DevX UI": [3100, 3101, 3102],
        "Streamlit (others)": [p for p in STREAMLIT_FALLBACK_PORTS if p != cp_port],
    }

    log(f"Port ranges to scan: {sum(len(ports) for ports in all_ports.values())} total ports")

    for service_name, ports in all_ports.items():
        log(f"\n--- Scanning {service_name} ---")
        for port in ports:
            results["ports_scanned"].append(port)

            if port == cp_port:
                log(f"Port {port}: SKIPPED (CP++ itself)")
                continue

            try:
                # Use lsof to find process on port
                log(f"Port {port}: Running lsof...")
                result = subprocess.run(
                    ["lsof", "-i", f":{port}", "-t"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                if result.returncode == 0 and result.stdout.strip():
                    pid_str = result.stdout.strip().split()[0]
                    pid = int(pid_str)

                    # Get process details before killing
                    try:
                        ps_result = subprocess.run(
                            ["ps", "-p", str(pid), "-o", "comm="],
                            capture_output=True,
                            text=True,
                            timeout=1
                        )
                        process_name = ps_result.stdout.strip() if ps_result.returncode == 0 else "unknown"
                    except Exception:
                        process_name = "unknown"

                    log(f"Port {port}: Found PID {pid} ({process_name})")

                    # Kill the process
                    try:
                        os.kill(pid, signal.SIGTERM)
                        log(f"Port {port}: Sent SIGTERM to PID {pid}")
                        time.sleep(0.1)

                        # Check if still alive
                        try:
                            os.kill(pid, 0)  # Test if process exists
                            log(f"Port {port}: PID {pid} still alive, sending SIGKILL")
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            log(f"Port {port}: PID {pid} terminated successfully")
                    except ProcessLookupError:
                        log(f"Port {port}: PID {pid} already dead")
                    except Exception as kill_err:
                        log(f"Port {port}: Failed to kill PID {pid}: {kill_err}")

                    results["killed_pids"].append({
                        "service": service_name,
                        "port": port,
                        "pid": pid,
                        "process_name": process_name
                    })
                    results["ports_cleared"].append(port)
                else:
                    log(f"Port {port}: Empty (returncode={result.returncode})")
                    results["ports_empty"].append(port)

            except subprocess.TimeoutExpired:
                error_msg = f"{service_name} port {port}: lsof timed out"
                log(f"Port {port}: ERROR - {error_msg}")
                results["errors"].append(error_msg)
            except Exception as e:
                error_msg = f"{service_name} port {port}: {str(e)}"
                log(f"Port {port}: ERROR - {error_msg}")
                results["errors"].append(error_msg)

    # Also clean up PID files
    log("\n--- Cleaning up PID files ---")
    pid_files = [
        Path.home() / ".redna" / "core.pid",
        Path.home() / ".redna" / "ucnrr.pid",
        Path.home() / ".redna" / "devx_backend.pid",
        Path.home() / ".redna" / "devx_ui.pid",
    ]
    for pid_file in pid_files:
        if pid_file.exists():
            log(f"Removing PID file: {pid_file}")
            pid_file.unlink(missing_ok=True)
        else:
            log(f"PID file not found: {pid_file}")

    log(f"\n=== SUMMARY ===")
    log(f"Ports scanned: {len(results['ports_scanned'])}")
    log(f"Ports killed: {len(results['ports_cleared'])}")
    log(f"Ports empty: {len(results['ports_empty'])}")
    log(f"Errors: {len(results['errors'])}")

    return results


def _rebuild_stack_properly() -> Dict[str, Any]:
    """
    Rebuild the entire stack in the proper order with health checks.
    Order: Core → UCNRR → DevX Backend → React → DevX UI
    """
    import subprocess
    from datetime import datetime

    results = {
        "core": {"started": False, "port": None, "error": None, "log": []},
        "ucnrr": {"started": False, "port": None, "error": None, "log": []},
        "devx_backend": {"started": False, "port": None, "error": None, "log": []},
        "react": {"started": False, "port": None, "error": None, "log": []},
        "devx_ui": {"started": False, "port": None, "error": None, "log": []},
        "diagnostic_log": [],
        "timestamp": datetime.now().isoformat(),
    }

    def log(msg: str):
        results["diagnostic_log"].append(msg)

    log("=== STACK REBUILD DIAGNOSTICS ===")

    _load_repo_dotenv()

    env = _env()
    # Convert all env values to strings (subprocess.Popen requires string values)
    env_str = {k: str(v) for k, v in env.items()}
    base_env = _merge_env(env_str)
    venv_python = str(_active_python_path())  # Convert Path to string
    log(f"Python venv: {venv_python}")
    log(f"Working directory: {ROOT}")
    log(f"Environment variables: {len(env_str)} custom vars")

    # 1. Start Core
    log("\n--- Starting Core API ---")
    try:
        results["core"]["log"].append("Starting Core API initialization")
        log("Core: Building command")

        core_port = CORE_DEFAULT_PORT
        results["core"]["log"].append(f"Core port: {core_port}")

        core_cmd = [
            venv_python, "-m", "uvicorn",
            "ReDNACoreDemo.core.api:build_app",
            "--factory",
            "--host", "127.0.0.1",
            "--port", str(core_port),
        ]
        results["core"]["log"].append("Command list built")

        results["core"]["log"].append(f"Command: {' '.join(core_cmd)}")
        log(f"Core command: {' '.join(core_cmd)}")

        results["core"]["log"].append(f"Working directory: {ROOT} (type: {type(ROOT).__name__})")
        results["core"]["log"].append(f"Command list items: {[f'{item} ({type(item).__name__})' for item in core_cmd]}")

        core_env = base_env.copy()
        core_launch_line = _format_core_launch_log(core_env)
        results["core"]["log"].append(core_launch_line)
        print(core_launch_line)

        try:
            proc = subprocess.Popen(
                core_cmd,
                cwd=str(ROOT),
                env=core_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            results["core"]["log"].append(f"Popen succeeded")
        except Exception as popen_err:
            results["core"]["log"].append(f"Popen failed: {type(popen_err).__name__}: {popen_err}")
            import traceback
            results["core"]["log"].append(f"Traceback: {traceback.format_exc()}")
            raise

        results["core"]["log"].append(f"Process started with PID {proc.pid}")
        log(f"Core process started with PID {proc.pid}")

        # Wait for Core to be healthy
        for attempt in range(30):  # 15 seconds max
            time.sleep(0.5)
            try:
                import requests
                resp = requests.get(f"http://127.0.0.1:{core_port}/health", timeout=1)
                results["core"]["log"].append(f"Health check attempt {attempt+1}: status={resp.status_code}")
                if resp.ok:
                    results["core"]["started"] = True
                    results["core"]["port"] = core_port
                    log(f"Core is healthy on port {core_port} after {attempt+1} attempts")
                    break
            except Exception as health_err:
                if attempt % 5 == 0:  # Log every 5th attempt
                    results["core"]["log"].append(f"Attempt {attempt+1}: {str(health_err)}")
                continue

        if not results["core"]["started"]:
            error_msg = "Core failed to become healthy within 15 seconds"
            results["core"]["error"] = error_msg
            results["core"]["log"].append(error_msg)
            log(f"Core ERROR: {error_msg}")

    except Exception as e:
        error_msg = str(e)
        results["core"]["error"] = error_msg
        results["core"]["log"].append(f"Exception: {error_msg}")
        log(f"Core EXCEPTION: {error_msg}")

    # 2. Start UCNRR
    if results["core"]["started"]:
        log("\n--- Starting UCNRR ---")
        try:
            ucnrr_port = UCNRR_DEFAULT_PORT
            ucnrr_cmd = [
                venv_python, "-m", "uvicorn",
                "UCN_RR_Demo.ucnrr_app:app",
                "--host", "127.0.0.1",
                "--port", str(ucnrr_port),
            ]

            results["ucnrr"]["log"].append(f"Command: {' '.join(ucnrr_cmd)}")
            log(f"UCNRR command: {' '.join(ucnrr_cmd)}")

            ucnrr_env = base_env.copy()
            proc = subprocess.Popen(
                ucnrr_cmd,
                cwd=str(ROOT),
                env=ucnrr_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            results["ucnrr"]["log"].append(f"Process started with PID {proc.pid}")
            log(f"UCNRR process started with PID {proc.pid}")

            # Wait for UCNRR
            for attempt in range(20):
                time.sleep(0.5)
                try:
                    import requests
                    resp = requests.get(f"http://127.0.0.1:{ucnrr_port}/health", timeout=1)
                    results["ucnrr"]["log"].append(f"Health check attempt {attempt+1}: status={resp.status_code}")
                    if resp.ok:
                        results["ucnrr"]["started"] = True
                        results["ucnrr"]["port"] = ucnrr_port
                        log(f"UCNRR is healthy on port {ucnrr_port} after {attempt+1} attempts")
                        break
                except Exception as health_err:
                    if attempt % 5 == 0:
                        results["ucnrr"]["log"].append(f"Attempt {attempt+1}: {str(health_err)}")
                    continue

            if not results["ucnrr"]["started"]:
                error_msg = "UCNRR failed to become healthy within 10 seconds"
                results["ucnrr"]["error"] = error_msg
                results["ucnrr"]["log"].append(error_msg)
                log(f"UCNRR WARNING: {error_msg}")

        except Exception as e:
            error_msg = str(e)
            results["ucnrr"]["error"] = error_msg
            results["ucnrr"]["log"].append(f"Exception: {error_msg}")
            log(f"UCNRR EXCEPTION: {error_msg}")
    else:
        log("\n--- Skipping UCNRR (Core not started) ---")

    # 3. Start DevX Backend (if available)
    if DEVX_BOOTSTRAP_AVAILABLE and results["core"]["started"]:
        log("\n--- Starting DevX Backend ---")
        try:
            _apply_devx_env(env_str)
            results["devx_backend"]["log"].append("Calling start_devx_backend()")
            ok, msg, port = start_devx_backend()
            results["devx_backend"]["started"] = ok
            results["devx_backend"]["port"] = port
            results["devx_backend"]["log"].append(f"Result: ok={ok}, msg={msg}, port={port}")
            log(f"DevX Backend: {msg}")
            if not ok:
                results["devx_backend"]["error"] = msg
        except Exception as e:
            error_msg = str(e)
            results["devx_backend"]["error"] = error_msg
            results["devx_backend"]["log"].append(f"Exception: {error_msg}")
            log(f"DevX Backend EXCEPTION: {error_msg}")
    else:
        if not DEVX_BOOTSTRAP_AVAILABLE:
            log("\n--- Skipping DevX Backend (bootstrap not available) ---")
        else:
            log("\n--- Skipping DevX Backend (Core not started) ---")

    # 4. Start React/Next.js
    if results["core"]["started"]:
        log("\n--- Starting React/Next.js ---")
        try:
            react_port = REACT_DEFAULT_PORT
            react_env = {
                **os.environ,
                **env_str,
                "NEXT_PUBLIC_CORE_API_BASE": f"http://127.0.0.1:{results['core']['port']}",
                "CORE_API_URL": f"http://127.0.0.1:{results['core']['port']}",
                "NEXT_PUBLIC_DEVX_API_BASE": f"http://127.0.0.1:{DEVX_BACKEND_DEFAULT_PORT}",
            }

            results["react"]["log"].append(f"Core API URL: http://127.0.0.1:{results['core']['port']}")

            # Create .env.local for Next.js
            env_local_path = ROOT / "web" / ".env.local"
            env_content = f"NEXT_PUBLIC_CORE_API_BASE=http://127.0.0.1:{results['core']['port']}\n"
            env_content += f"CORE_API_URL=http://127.0.0.1:{results['core']['port']}\n"
            env_content += f"NEXT_PUBLIC_DEVX_API_BASE=http://127.0.0.1:{DEVX_BACKEND_DEFAULT_PORT}\n"

            with open(env_local_path, "w") as f:
                f.write(env_content)

            results["react"]["log"].append(f"Created {env_local_path}")
            log(f"Created Next.js .env.local with Core API at port {results['core']['port']}")

            react_cmd = ["npm", "run", "dev", "--", "--port", str(react_port)]
            results["react"]["log"].append(f"Command: {' '.join(react_cmd)}")
            log(f"React command: {' '.join(react_cmd)}")

            react_env = base_env.copy()
            react_env.update({
                "NEXT_PUBLIC_CORE_API_BASE": f"http://127.0.0.1:{results['core']['port']}",
                "CORE_API_URL": f"http://127.0.0.1:{results['core']['port']}",
                "NEXT_PUBLIC_DEVX_API_BASE": f"http://127.0.0.1:{DEVX_BACKEND_DEFAULT_PORT}",
            })

            proc = subprocess.Popen(
                react_cmd,
                cwd=str(ROOT / "web"),
                env=react_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            results["react"]["log"].append(f"Process started with PID {proc.pid}")
            log(f"React process started with PID {proc.pid}")

            # Wait for React
            for attempt in range(40):  # 20 seconds max
                time.sleep(0.5)
                try:
                    import requests
                    resp = requests.get(f"http://127.0.0.1:{react_port}/", timeout=1)
                    if attempt % 10 == 0:
                        results["react"]["log"].append(f"Health check attempt {attempt+1}: status={resp.status_code}")
                    if resp.ok:
                        results["react"]["started"] = True
                        results["react"]["port"] = react_port
                        log(f"React is healthy on port {react_port} after {attempt+1} attempts")
                        break
                except Exception as health_err:
                    if attempt % 10 == 0:
                        results["react"]["log"].append(f"Attempt {attempt+1}: {str(health_err)}")
                    continue

            if not results["react"]["started"]:
                error_msg = "React failed to become healthy within 20 seconds"
                results["react"]["error"] = error_msg
                results["react"]["log"].append(error_msg)
                log(f"React ERROR: {error_msg}")

        except Exception as e:
            error_msg = str(e)
            results["react"]["error"] = error_msg
            results["react"]["log"].append(f"Exception: {error_msg}")
            log(f"React EXCEPTION: {error_msg}")
    else:
        log("\n--- Skipping React (Core not started) ---")

    # 5. Start DevX UI (if available)
    if DEVX_BOOTSTRAP_AVAILABLE and results["devx_backend"]["started"]:
        log("\n--- Starting DevX UI ---")
        try:
            results["devx_ui"]["log"].append("Calling start_devx_ui()")
            ok, msg, port = start_devx_ui()
            results["devx_ui"]["started"] = ok
            results["devx_ui"]["port"] = port
            results["devx_ui"]["log"].append(f"Result: ok={ok}, msg={msg}, port={port}")
            log(f"DevX UI: {msg}")
            if not ok:
                results["devx_ui"]["error"] = msg
        except Exception as e:
            error_msg = str(e)
            results["devx_ui"]["error"] = error_msg
            results["devx_ui"]["log"].append(f"Exception: {error_msg}")
            log(f"DevX UI EXCEPTION: {error_msg}")
    else:
        if not DEVX_BOOTSTRAP_AVAILABLE:
            log("\n--- Skipping DevX UI (bootstrap not available) ---")
        else:
            log("\n--- Skipping DevX UI (DevX Backend not started) ---")

    log("\n=== REBUILD COMPLETE ===")
    return results


def main() -> None:
    st.set_page_config(page_title="Control Panel Plus Plus", layout="wide")
    _init_session_state()
    _apply_devx_env(_env())
    health_snapshot = _refresh_health()
    port_state = _build_port_analysis(health_snapshot)
    _render_port_drift_banner(port_state)

    # NUCLEAR RESET BUTTON - Giant button at the top
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(
            "🔥 NUCLEAR RESET & REBUILD ENTIRE STACK 🔥",
            key="nuclear_reset",
            help="Kill ALL services on all ports (except CP++) and rebuild the entire stack properly",
            use_container_width=True,
            type="primary"
        ):
            pre_logs: Dict[str, str] = {}
            post_logs: Dict[str, str] = {}
            sanity_report: Dict[str, Any] = {}
            bundle_path: Optional[Path] = None
            with st.spinner("💥 KILLING ALL SERVICES..."):
                kill_results = _nuclear_reset_all_services()
                pre_logs = _snapshot_nuclear_logs("pre")
                _append_nuclear_log("nuclear_reset", _summarize_kill_results(kill_results))
                _truncate_nuclear_logs()

                st.markdown("### 💀 Cleanup Results")

                # Summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Ports Scanned", len(kill_results.get("ports_scanned", [])))
                with col2:
                    st.metric("Processes Killed", len(kill_results.get("killed_pids", [])))
                with col3:
                    st.metric("Errors", len(kill_results.get("errors", [])))

                if kill_results["killed_pids"]:
                    with st.expander("✅ Killed Processes", expanded=True):
                        for item in kill_results["killed_pids"]:
                            st.write(f"• **{item['service']}** - Port {item['port']} - PID {item['pid']} ({item.get('process_name', 'unknown')})")

                if kill_results["errors"]:
                    with st.expander("⚠️ Errors During Cleanup", expanded=True):
                        for err in kill_results["errors"]:
                            st.write(f"• {err}")

                # Full diagnostic log
                with st.expander("🔍 Full Cleanup Diagnostic Log"):
                    st.code("\n".join(kill_results.get("diagnostic_log", [])), language="text")

                # Save to file
                log_file = NUCLEAR_LOG_PATH
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(f"=== NUCLEAR RESET - {kill_results.get('timestamp', 'unknown')} ===\n\n")
                    f.write("\n".join(kill_results.get("diagnostic_log", [])))
                st.caption(f"📝 Full log saved to: {log_file}")

                time.sleep(2)  # Give ports time to free up

            with st.spinner("🏗️ REBUILDING STACK (Core → UCNRR → DevX Backend → React → DevX UI)..."):
                rebuild_results = _rebuild_stack_properly()
                _append_nuclear_log("nuclear_rebuild", _summarize_rebuild_results(rebuild_results))

                st.markdown("### 🚀 Stack Rebuild Results")

                # Summary metrics
                services = ["core", "ucnrr", "devx_backend", "react", "devx_ui"]
                started_count = sum(1 for s in services if rebuild_results.get(s, {}).get("started"))
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Services Started", f"{started_count}/{len(services)}")
                with col2:
                    if started_count == len(services):
                        st.success("🎉 All services running!")
                    elif started_count >= 3:
                        st.warning("⚠️ Some services failed")
                    else:
                        st.error("❌ Critical failures")

                # Core
                if rebuild_results["core"]["started"]:
                    st.success(f"✅ **Core API** running on port {rebuild_results['core']['port']}")
                else:
                    st.error(f"❌ **Core API** failed: {rebuild_results['core']['error']}")

                with st.expander("Core Diagnostic Log"):
                    st.code("\n".join(rebuild_results["core"].get("log", [])), language="text")

                # UCNRR
                if rebuild_results["ucnrr"]["started"]:
                    st.success(f"✅ **UCNRR** running on port {rebuild_results['ucnrr']['port']}")
                else:
                    st.warning(f"⚠️ **UCNRR** failed: {rebuild_results['ucnrr']['error']}")

                with st.expander("UCNRR Diagnostic Log"):
                    st.code("\n".join(rebuild_results["ucnrr"].get("log", [])), language="text")

                # DevX Backend
                if rebuild_results["devx_backend"]["started"]:
                    st.success(f"✅ **DevX Backend** running on port {rebuild_results['devx_backend']['port']}")
                elif rebuild_results["devx_backend"]["error"]:
                    st.warning(f"⚠️ **DevX Backend**: {rebuild_results['devx_backend']['error']}")

                with st.expander("DevX Backend Diagnostic Log"):
                    st.code("\n".join(rebuild_results["devx_backend"].get("log", [])), language="text")

                # React
                if rebuild_results["react"]["started"]:
                    st.success(f"✅ **React/Next.js** running on port {rebuild_results['react']['port']}")
                    st.info(f"🌐 Open: http://127.0.0.1:{rebuild_results['react']['port']}{HEAD_COACH_URL_SUFFIX}")
                else:
                    st.error(f"❌ **React/Next.js** failed: {rebuild_results['react']['error']}")

                with st.expander("React Diagnostic Log"):
                    st.code("\n".join(rebuild_results["react"].get("log", [])), language="text")

                # DevX UI
                if rebuild_results["devx_ui"]["started"]:
                    st.success(f"✅ **DevX UI** running on port {rebuild_results['devx_ui']['port']}")
                elif rebuild_results["devx_ui"]["error"]:
                    st.warning(f"⚠️ **DevX UI**: {rebuild_results['devx_ui']['error']}")

                with st.expander("DevX UI Diagnostic Log"):
                    st.code("\n".join(rebuild_results["devx_ui"].get("log", [])), language="text")

                # Full rebuild diagnostic log
                with st.expander("🔍 Full Rebuild Diagnostic Log"):
                    st.code("\n".join(rebuild_results.get("diagnostic_log", [])), language="text")

                # Save rebuild log to file with all service details
                rebuild_log_file = Path.home() / ".redna" / "stack_rebuild.log"
                with open(rebuild_log_file, "w") as f:
                    f.write(f"=== STACK REBUILD - {rebuild_results.get('timestamp', 'unknown')} ===\n\n")
                    f.write("\n".join(rebuild_results.get("diagnostic_log", [])))
                    f.write("\n\n=== PER-SERVICE LOGS ===\n")
                    for svc in ["core", "ucnrr", "devx_backend", "react", "devx_ui"]:
                        if svc in rebuild_results and rebuild_results[svc].get("log"):
                            f.write(f"\n--- {svc.upper()} ---\n")
                            f.write("\n".join(rebuild_results[svc]["log"]))
                            f.write("\n")
                st.caption(f"📝 Full rebuild log saved to: {rebuild_log_file}")

                sanity_report = _run_nuclear_sanity_checks()
                _append_nuclear_log("nuclear_sanity", sanity_report)
                post_logs = _snapshot_nuclear_logs("post")
                bundle_path = _build_nuclear_bundle(
                    kill_results,
                    rebuild_results,
                    sanity_report,
                    pre_logs,
                    post_logs,
                )
                if bundle_path:
                    st.caption(f"📦 Nuclear bundle saved to: {bundle_path}")
                    _append_nuclear_log("nuclear_bundle", {"path": str(bundle_path)})
                else:
                    st.caption("⚠️ Failed to create nuclear diagnostic bundle.")
                    _append_nuclear_log("nuclear_bundle", {"error": "bundle_creation_failed"})
                with st.expander("🔬 Post-Nuclear Sanity Checks", expanded=False):
                    st.json(sanity_report)
                _truncate_nuclear_logs()

                time.sleep(2)
                safe_rerun()

    st.markdown("---")
    st.sidebar.title("Control Panel Plus Plus")
    st.sidebar.caption("Service orchestrator for Core, UCN/RR, and React.")

    active_python = _active_python_path()
    label = _python_choice_label(active_python)
    st.sidebar.caption(f"Using venv: {label}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🤖 AI Readiness")
    _render_ai_readiness_sidebar()

    # Quick launch Developer Tools
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🛠️ Quick Launch**")
    st.sidebar.markdown("**Developer Explorer (DevX)**")

    if DEVX_BOOTSTRAP_AVAILABLE:
        # Use new DevX bootstrap system
        devx_env = _env()
        _apply_devx_env(devx_env)
        backend_port = _devx_backend_port(devx_env)
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

                _apply_devx_env(_env())

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
