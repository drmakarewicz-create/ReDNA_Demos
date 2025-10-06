# control_panel_plus.py
# ReDNA Control Panel+  — drop-in
# - Safe defaults (no KeyError on first run)
# - Core / UCN-RR / Explorer start-stop
# - Ports & working dirs editable
# - Health checks
# - PID persistence in cp_state.json
# - Settings in cp_settings.json
# Tested with Streamlit 1.37+

from __future__ import annotations

import os
import sys
import json
import time
import shlex
import signal
import pathlib
import platform
import subprocess
import socket
import webbrowser
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, Mapping, Optional, Set, List
from urllib.parse import urlencode

try:  # optional dependency; fall back silently if missing
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None

import streamlit as st
import requests

from ExplorerDev.scheduler_utils import load_scheduler_prefs, save_scheduler_prefs
from ExplorerDev.write_utils import write_guard


ROOT = pathlib.Path(__file__).parent.resolve()
SETTINGS_PATH = ROOT / "cp_settings.json"
STATE_PATH = ROOT / "cp_state.json"
ENV_FILE_PATH = ROOT / ".env"

if load_dotenv and ENV_FILE_PATH.exists():
    load_dotenv(ENV_FILE_PATH)

PY = shlex.quote(sys.executable)  # current venv python

DEFAULTS = {
    "core_port": 8015,
    "ucnrr_port": 8020,
    "explorer_port": 8502,

    # Working directories (relative to repo root or absolute ok)
    "core_workdir": str((ROOT / "ReDNACoreDemo").resolve()),
    "ucnrr_workdir": str(ROOT.resolve()),  # ucnrr_app.py at repo root per your note
    "explorer_workdir": str((ROOT / "ExplorerFinal").resolve()),

    # Start commands; {port} and {host} are replaced; cwd uses workdir fields above
    "core_start_cmd": f"{PY} -m uvicorn ReDNACoreDemo.core.api:build_app --factory --host 0.0.0.0 --port {{port}} --reload",
    "ucnrr_start_cmd": f"{PY} -m uvicorn ucnrr_app:app --host 0.0.0.0 --port {{port}} --reload",
    "explorer_start_cmd": f"{PY} -m streamlit run explorer_final.py --server.port {{port}} --server.address 0.0.0.0",

    # Health URLs (used for “Ping” and auto-status)
    "core_health_url": "http://127.0.0.1:{core_port}/health",
    "ucnrr_health_url": "http://127.0.0.1:{ucnrr_port}/health",

    # ENV to pass into Core / UCN/RR processes
    # Explorer and Core read UCNRR_BASE for round-trip calls
    "UCNRR_BASE": "http://127.0.0.1:{ucnrr_port}",
    # Optional: where the Core should look for Explorer secrets or other config
    "EXPLORER_BASE": "http://127.0.0.1:{explorer_port}",
    "CORE_USE_LLM": False,
    "CORE_LLM_PROVIDER": "",
    "CORE_LLM_MODEL": "",
    "CORE_LLM_BASE_URL": "",
    "CORE_LLM_API_KEY": "",
    "CORE_HOLISTIC_ON_INGEST": False,
    "CORE_HOLISTIC_MAX_MS": 300,

    # Dev Explorer launcher
    "devexp_port": 8520,
    "devexp_workdir": str((ROOT / "ExplorerDev").resolve()),
    "devexp_start_cmd": f"{PY} -m streamlit run ExplorerDev/explorer_dev.py --server.port {{port}} --server.address 0.0.0.0",
}


TRUTHY = {"1", "true", "yes", "on"}
ENV_FLAG_DEFAULTS: Dict[str, Any] = {
    "WRITE_PROTECT": True,
    "DEV_EXPLORER_ENABLED": True,
    "CORE_CURIOSITY_ENABLED": False,
    "DEMO_BASELINES_ENABLED": False,
    "HC_SEND_ENABLED": False,
    "HC_OPS_ENABLED": False,
    "NUDGE_INBOX_ENABLED": False,
    "FEEDBACK_ENABLED": True,
    "AUDIT_VIEWER_ENABLED": True,
    "DEV_LOOPTEST_USER_ID": "devexp_test",
    "DEV_HTTP_TIMEOUT_SECONDS": 12.0,
}
ENV_BOOL_KEYS = {
    "WRITE_PROTECT",
    "DEV_EXPLORER_ENABLED",
    "CORE_CURIOSITY_ENABLED",
    "DEMO_BASELINES_ENABLED",
    "HC_SEND_ENABLED",
    "HC_OPS_ENABLED",
    "NUDGE_INBOX_ENABLED",
    "FEEDBACK_ENABLED",
    "AUDIT_VIEWER_ENABLED",
}
ENV_STRING_KEYS = {"DEV_LOOPTEST_USER_ID"}
ENV_FLOAT_KEYS = {"DEV_HTTP_TIMEOUT_SECONDS"}
ENV_FLAGS_SESSION_KEY = "_cp_env_flags"
ENV_FLAGS_PERSISTED_KEY = "_cp_env_flags_persisted"
ENV_PROFILE_KEY = "_env_flag_profile"
ENV_PROFILE_APPLIED_KEY = "_env_profile_applied"

PROFILE_PRESETS = {
    "Demo Mode": {
        "WRITE_PROTECT": True,
        "CORE_CURIOSITY_ENABLED": False,
        "DEMO_BASELINES_ENABLED": True,
    },
    "Live Curiosity": {
        "WRITE_PROTECT": False,
        "CORE_CURIOSITY_ENABLED": True,
        "DEMO_BASELINES_ENABLED": False,
    },
}

CURRENT_ENV_FLAGS: Dict[str, Any] = {}


@dataclass
class CPWriteContext:
    write_protect: bool


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    if text in TRUTHY:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _bool_to_str(value: bool) -> str:
    return "true" if value else "false"


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _load_env_flags() -> Dict[str, Any]:
    flags = dict(ENV_FLAG_DEFAULTS)
    prefs = load_scheduler_prefs()
    stored = prefs.get("env_flags") if isinstance(prefs, dict) else {}
    stored = stored if isinstance(stored, Mapping) else {}

    for key in ENV_BOOL_KEYS:
        if key in os.environ:
            flags[key] = _parse_bool(os.environ.get(key), flags[key])
        elif key in stored:
            flags[key] = _parse_bool(stored.get(key), flags[key])

    for key in ENV_STRING_KEYS:
        if key in os.environ:
            flags[key] = str(os.environ.get(key, flags[key]) or flags[key])
        elif isinstance(stored.get(key), str):
            flags[key] = stored.get(key) or flags[key]

    for key in ENV_FLOAT_KEYS:
        raw = None
        if key in os.environ:
            raw = os.environ.get(key)
        elif key in stored:
            raw = stored.get(key)
        if raw is not None:
            try:
                flags[key] = float(raw)
            except (TypeError, ValueError):
                flags[key] = ENV_FLAG_DEFAULTS[key]

    return flags


def _apply_env_flags(flags: Mapping[str, Any]) -> None:
    global CURRENT_ENV_FLAGS
    CURRENT_ENV_FLAGS = dict(flags)

    for key in ENV_BOOL_KEYS:
        val = bool(flags.get(key, ENV_FLAG_DEFAULTS[key]))
        os.environ[key] = _bool_to_str(val)

    for key in ENV_STRING_KEYS:
        os.environ[key] = str(flags.get(key, ENV_FLAG_DEFAULTS[key]) or "")

    for key in ENV_FLOAT_KEYS:
        value = flags.get(key, ENV_FLAG_DEFAULTS[key])
        try:
            os.environ[key] = str(float(value))
        except (TypeError, ValueError):
            os.environ[key] = str(ENV_FLAG_DEFAULTS[key])


def _update_env_file(path: pathlib.Path, updates: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines: list[str]
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()
    else:
        existing_lines = []

    seen: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key, _ = stripped.split("=", 1)
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _persist_env_flags(flags: Mapping[str, Any], *, write_protect: bool) -> None:
    context = CPWriteContext(write_protect=write_protect)
    write_guard(context, action="update environment flags")

    env_updates = {}
    prefs_payload: Dict[str, Any] = {}

    for key in ENV_BOOL_KEYS:
        value = bool(flags.get(key, ENV_FLAG_DEFAULTS[key]))
        env_updates[key] = _bool_to_str(value)
        prefs_payload[key] = value

    for key in ENV_STRING_KEYS:
        value = str(flags.get(key, ENV_FLAG_DEFAULTS[key]) or "")
        env_updates[key] = value
        prefs_payload[key] = value

    for key in ENV_FLOAT_KEYS:
        try:
            value = float(flags.get(key, ENV_FLAG_DEFAULTS[key]))
        except (TypeError, ValueError):
            value = float(ENV_FLAG_DEFAULTS[key])
        env_updates[key] = str(value)
        prefs_payload[key] = value

    _update_env_file(ENV_FILE_PATH, env_updates)

    prefs = load_scheduler_prefs()
    if not isinstance(prefs, dict):
        prefs = {}
    prefs["env_flags"] = prefs_payload
    save_scheduler_prefs(prefs, context)


def _chip(label: str, *, color: str) -> str:
    style = (
        "display:inline-block;padding:0.2rem 0.65rem;margin-right:0.35rem;"
        "border-radius:999px;font-size:0.8rem;font-weight:600;color:#fff;"
        f"background:{color};"
    )
    return f"<span style=\"{style}\">{label}</span>"


def _render_env_flag_chips(flags: Mapping[str, Any]) -> None:
    chips: list[str] = []

    wp = bool(flags.get("WRITE_PROTECT", True))
    chips.append(_chip(f"WP:{'on' if wp else 'off'}", color="#d32f2f" if wp else "#388e3c"))

    dev_enabled = bool(flags.get("DEV_EXPLORER_ENABLED", True))
    chips.append(_chip(f"DevExp:{'on' if dev_enabled else 'off'}", color="#1976d2" if dev_enabled else "#6c757d"))

    curiosity = bool(flags.get("CORE_CURIOSITY_ENABLED", False))
    chips.append(_chip(f"Curiosity:{'live' if curiosity else 'sim'}", color="#6f42c1" if curiosity else "#6c757d"))

    baselines = bool(flags.get("DEMO_BASELINES_ENABLED", False))
    chips.append(_chip(f"Baselines:{'demo' if baselines else 'live'}", color="#fb8c00" if baselines else "#607d8b"))

    timeout = flags.get("DEV_HTTP_TIMEOUT_SECONDS")
    try:
        timeout_val = float(timeout)
    except (TypeError, ValueError):
        timeout_val = None
    if timeout_val is not None:
        chips.append(_chip(f"Timeout:{timeout_val:.1f}s", color="#0277bd"))

    loop_user = str(flags.get("DEV_LOOPTEST_USER_ID") or "").strip()
    if loop_user:
        chips.append(_chip(f"Loop:{loop_user}", color="#455a64"))

    if chips:
        st.markdown(
            "<div style=\"margin:0.4rem 0 1rem 0;\">" + "".join(chips) + "</div>",
            unsafe_allow_html=True,
        )


def _normalize_env_flags(raw: Mapping[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}

    for key in ENV_BOOL_KEYS:
        normalized[key] = _parse_bool(raw.get(key), ENV_FLAG_DEFAULTS[key])

    for key in ENV_STRING_KEYS:
        normalized[key] = str(raw.get(key, ENV_FLAG_DEFAULTS[key]) or "")

    for key in ENV_FLOAT_KEYS:
        try:
            normalized[key] = float(raw.get(key, ENV_FLAG_DEFAULTS[key]))
        except (TypeError, ValueError):
            normalized[key] = float(ENV_FLAG_DEFAULTS[key])

    return normalized


def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        result = sock.connect_ex(("127.0.0.1", port))
        return result == 0


def _pid_on_port(port: int) -> Optional[int]:
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


def _next_free_port(start: int, *, forbidden: Optional[Set[int]] = None, limit: int = 100) -> int:
    port = max(1, start)
    forbidden = forbidden or set()
    for _ in range(limit):
        if port in forbidden:
            port += 1
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                port += 1
                continue
            return port
    return port


def _classify_process(command: str) -> str:
    text = command.lower()
    if "explorerdev" in text or "explorer_dev.py" in text:
        return "dev"
    if "explorerfinal" in text or "explorer_final.py" in text or "explorer_final" in text:
        return "main"
    return "other"


def _resolve_cp_port() -> Optional[int]:
    for key in ("STREAMLIT_SERVER_PORT", "SERVER_PORT", "REDNA_CP_PORT"):
        value = os.environ.get(key)
        if value:
            try:
                return int(value)
            except ValueError:
                continue
    return None


def _build_devexp_cmd(template: str, port: int, *, workdir: Optional[str] = None) -> str:
    cmd = template.format(port=port, host="0.0.0.0", PY=PY)
    workdir_path = pathlib.Path(workdir) if workdir else None
    if "ExplorerDev/explorer_dev.py" in cmd:
        replacements = []
        if workdir_path is not None:
            candidate = workdir_path / "ExplorerDev" / "explorer_dev.py"
            if candidate.exists():
                replacements.append(candidate)
            candidate = workdir_path / "explorer_dev.py"
            if candidate.exists():
                replacements.append(candidate)
        replacements.append(ROOT / "ExplorerDev" / "explorer_dev.py")
        for candidate in replacements:
            try:
                resolved = candidate.resolve(strict=True)
            except FileNotFoundError:
                continue
            cmd = cmd.replace("ExplorerDev/explorer_dev.py", str(resolved))
            break
    if "--server.port" not in cmd:
        cmd += f" --server.port {port}"
    if "--server.address" not in cmd:
        cmd += " --server.address 0.0.0.0"
    if "--server.headless" not in cmd:
        cmd += " --server.headless true"
    return cmd


def _wait_for_devexp_ready(port: int, timeout: float = 8.0) -> tuple[bool, str]:
    deadline = time.time() + timeout
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    alt_url = f"http://127.0.0.1:{port}/"
    last_error = ""
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=0.25)
            if resp.status_code < 400:
                return True, ""
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        try:
            resp = requests.get(alt_url, timeout=0.25)
            if resp.status_code < 400:
                return True, ""
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(0.25)
    return False, last_error


def _safe_rerun() -> None:
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def _mark_deferred_rerun() -> None:
    st.session_state["_deferred_rerun"] = True


def _build_devexp_env(
    flags: Mapping[str, Any],
    service_settings: Mapping[str, Any],
) -> Dict[str, str]:
    env = os.environ.copy()

    def _set_bool(key: str, value: bool) -> None:
        env[key] = _bool_from_flag(value)

    _set_bool("DEV_EXPLORER_ENABLED", True)
    _set_bool("WRITE_PROTECT", bool(flags.get("WRITE_PROTECT", True)))
    _set_bool("CORE_CURIOSITY_ENABLED", bool(flags.get("CORE_CURIOSITY_ENABLED", False)))
    _set_bool("DEMO_BASELINES_ENABLED", bool(flags.get("DEMO_BASELINES_ENABLED", False)))
    _set_bool("HC_SEND_ENABLED", bool(flags.get("HC_SEND_ENABLED", False)))
    _set_bool("HC_OPS_ENABLED", bool(flags.get("HC_OPS_ENABLED", False)))
    _set_bool("NUDGE_INBOX_ENABLED", bool(flags.get("NUDGE_INBOX_ENABLED", False)))
    _set_bool("FEEDBACK_ENABLED", bool(flags.get("FEEDBACK_ENABLED", True)))
    _set_bool("AUDIT_VIEWER_ENABLED", bool(flags.get("AUDIT_VIEWER_ENABLED", True)))

    loop_user = str(flags.get("DEV_LOOPTEST_USER_ID", "devexp_test") or "devexp_test").strip()
    env["DEV_LOOPTEST_USER_ID"] = loop_user or "devexp_test"

    try:
        timeout_value = float(flags.get("DEV_HTTP_TIMEOUT_SECONDS", 6.0))
    except (TypeError, ValueError):
        timeout_value = 6.0
    env["DEV_HTTP_TIMEOUT_SECONDS"] = str(timeout_value)

    core_base = service_settings.get("core_base") or env.get("CORE_BASE_URL")
    ucnrr_base = service_settings.get("ucnrr_base") or env.get("UCNRR_BASE_URL")
    llm_base = service_settings.get("llm_base") or env.get("LLM_BASE_URL")

    if core_base:
        env["CORE_BASE_URL"] = str(core_base).rstrip("/")
    if ucnrr_base:
        env["UCNRR_BASE_URL"] = str(ucnrr_base).rstrip("/")
    if llm_base:
        env["LLM_BASE_URL"] = str(llm_base).rstrip("/")

    return env


def _env_summary(flags: Mapping[str, Any]) -> str:
    wp = "on" if bool(flags.get("WRITE_PROTECT")) else "off"
    curiosity = "live" if bool(flags.get("CORE_CURIOSITY_ENABLED")) else "sim"
    baselines = "demo" if bool(flags.get("DEMO_BASELINES_ENABLED")) else "live"
    ops = "on" if bool(flags.get("HC_OPS_ENABLED")) else "off"
    feedback = "on" if bool(flags.get("FEEDBACK_ENABLED", True)) else "off"
    try:
        timeout = float(flags.get("DEV_HTTP_TIMEOUT_SECONDS", 6.0))
    except (TypeError, ValueError):
        timeout = 6.0
    loop_user = str(flags.get("DEV_LOOPTEST_USER_ID", "devexp_test") or "devexp_test").strip()
    return (
        "WP:{wp} • Curiosity:{curiosity} • Baselines:{baselines} "
        "• Ops:{ops} • Feedback:{feedback} "
        "• Timeout:{timeout:.1f}s • Loop:{loop}"
    ).format(
        wp=wp,
        curiosity=curiosity,
        baselines=baselines,
        ops=ops,
        feedback=feedback,
        timeout=timeout,
        loop=loop_user or "devexp_test",
    )

# ---- helpers -----------------------------------------------------------------

def _read_json(path: pathlib.Path, default: dict) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return dict(default)

def _write_json(path: pathlib.Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _bool_from_flag(value: bool) -> str:
    return "true" if value else "false"


def load_settings() -> dict:
    stored = _read_json(SETTINGS_PATH, DEFAULTS)
    # merge defaults (in case new keys were added)
    merged = {**DEFAULTS, **stored}
    # normalize types
    for k in ("core_port", "ucnrr_port", "explorer_port"):
        try:
            merged[k] = int(merged.get(k, DEFAULTS[k]))
        except Exception:
            merged[k] = DEFAULTS[k]
    merged["CORE_USE_LLM"] = str(merged.get("CORE_USE_LLM", "false")).lower() in ("1", "true", "yes", "on")
    merged["CORE_HOLISTIC_ON_INGEST"] = str(merged.get("CORE_HOLISTIC_ON_INGEST", "false")).lower() in ("1", "true", "yes", "on")
    try:
        merged["CORE_HOLISTIC_MAX_MS"] = int(merged.get("CORE_HOLISTIC_MAX_MS", DEFAULTS["CORE_HOLISTIC_MAX_MS"]))
    except Exception:
        merged["CORE_HOLISTIC_MAX_MS"] = DEFAULTS["CORE_HOLISTIC_MAX_MS"]
    try:
        merged["devexp_port"] = int(merged.get("devexp_port", DEFAULTS["devexp_port"]))
    except Exception:
        merged["devexp_port"] = DEFAULTS["devexp_port"]
    merged["devexp_workdir"] = str(merged.get("devexp_workdir", DEFAULTS["devexp_workdir"]))
    merged["devexp_start_cmd"] = str(merged.get("devexp_start_cmd", DEFAULTS["devexp_start_cmd"]))
    return merged

def save_settings(s: dict) -> None:
    _write_json(SETTINGS_PATH, s)

def load_state() -> dict:
    return _read_json(STATE_PATH, {"pids": {}})

def save_state(s: dict) -> None:
    _write_json(STATE_PATH, s)

def format_url(template: str, settings: dict) -> str:
    return template.format(**settings)

def _platform_is_mac() -> bool:
    return platform.system().lower() == "darwin"

def kill_port(port: int) -> None:
    """Best-effort kill anything bound to a port."""
    try:
        if _platform_is_mac():
            cmd = f"lsof -ti :{port} | xargs -r kill -9"
        else:
            # linux
            cmd = f"fuser -k {port}/tcp"
        subprocess.Popen(cmd, shell=True).wait(timeout=3)
    except Exception:
        pass

@dataclass
class ProcSpec:
    name: str
    port: int
    workdir: str
    start_cmd: str
    env: Dict[str, str]
    health_url: Optional[str] = None  # explorer has no health

def _expand_env(settings: dict) -> Dict[str, str]:
    env = os.environ.copy()

    def _put(key: str, value: str) -> None:
        if value not in (None, ""):
            env[key] = str(value)

    _put("UCNRR_BASE", format_url(settings["UCNRR_BASE"], settings))
    _put("CORE_BASE", f"http://127.0.0.1:{settings['core_port']}")
    _put("EXPLORER_BASE", format_url(settings["EXPLORER_BASE"], settings))

    env["UCNRR_URL"] = env.get("UCNRR_BASE", env.get("UCNRR_URL", ""))
    env["CORE_URL"] = env.get("CORE_BASE", env.get("CORE_URL", ""))

    for key in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY"):
        if key in settings:
            _put(key, settings.get(key))

    _put("CORE_USE_LLM", "1" if settings.get("CORE_USE_LLM") else "0")
    for key in ("CORE_LLM_PROVIDER", "CORE_LLM_MODEL", "CORE_LLM_BASE_URL", "CORE_LLM_API_KEY"):
        if key in settings and settings.get(key):
            _put(key, settings.get(key))

    _put("CORE_HOLISTIC_ON_INGEST", "1" if settings.get("CORE_HOLISTIC_ON_INGEST") else "0")
    if settings.get("CORE_HOLISTIC_MAX_MS"):
        _put("CORE_HOLISTIC_MAX_MS", settings.get("CORE_HOLISTIC_MAX_MS"))

    for key in ENV_BOOL_KEYS:
        flag = bool(CURRENT_ENV_FLAGS.get(key, ENV_FLAG_DEFAULTS[key]))
        _put(key, _bool_to_str(flag))

    for key in ENV_STRING_KEYS:
        _put(key, CURRENT_ENV_FLAGS.get(key, ENV_FLAG_DEFAULTS[key]) or "")

    for key in ENV_FLOAT_KEYS:
        try:
            value = float(CURRENT_ENV_FLAGS.get(key, ENV_FLAG_DEFAULTS[key]))
        except (TypeError, ValueError):
            value = float(ENV_FLAG_DEFAULTS[key])
        _put(key, str(value))

    env["REDNA_CORE_PORT"] = str(settings["core_port"])
    env["REDNA_UCNRR_PORT"] = str(settings["ucnrr_port"])
    env["REDNA_EXPLORER_PORT"] = str(settings["explorer_port"])

    return env


def _log_core_launch_env(env: Mapping[str, Any]) -> None:
    snapshot = {
        "CORE_CURIOSITY_ENABLED": env.get("CORE_CURIOSITY_ENABLED"),
        "WRITE_PROTECT": env.get("WRITE_PROTECT"),
        "DEMO_BASELINES_ENABLED": env.get("DEMO_BASELINES_ENABLED"),
        "DEV_LOOPTEST_USER_ID": env.get("DEV_LOOPTEST_USER_ID"),
        "DEV_HTTP_TIMEOUT_SECONDS": env.get("DEV_HTTP_TIMEOUT_SECONDS"),
    }
    st.caption("Core env overrides")
    st.json(snapshot)


CORE_ENV_DISPLAY_KEYS = (
    "CORE_CURIOSITY_ENABLED",
    "WRITE_PROTECT",
    "DEMO_BASELINES_ENABLED",
    "HC_SEND_ENABLED",
    "HC_OPS_ENABLED",
    "NUDGE_INBOX_ENABLED",
    "FEEDBACK_ENABLED",
    "AUDIT_VIEWER_ENABLED",
    "DEV_LOOPTEST_USER_ID",
    "DEV_HTTP_TIMEOUT_SECONDS",
)


def _shell_env_fragment(env: Mapping[str, Any], keys: Iterable[str]) -> str:
    parts: List[str] = []
    for key in keys:
        value = env.get(key)
        if value in (None, ""):
            continue
        parts.append(f"{key}={value}")
    return " ".join(parts)

def make_specs(settings: dict) -> Dict[str, ProcSpec]:
    base_env = _expand_env(settings)

    curiosity_flag = bool(
        CURRENT_ENV_FLAGS.get("CORE_CURIOSITY_ENABLED", ENV_FLAG_DEFAULTS["CORE_CURIOSITY_ENABLED"])
    )
    core_env = dict(base_env)
    core_env["CORE_CURIOSITY_ENABLED"] = _bool_to_str(curiosity_flag)

    ucnrr_env = dict(base_env)
    explorer_env = dict(base_env)

    return {
        "core": ProcSpec(
            name="core",
            port=settings["core_port"],
            workdir=settings["core_workdir"],
            start_cmd=settings["core_start_cmd"].format(port=settings["core_port"], host="0.0.0.0", PY=PY),
            env=core_env,
            health_url=format_url(settings["core_health_url"], settings),
        ),
        "ucnrr": ProcSpec(
            name="ucnrr",
            port=settings["ucnrr_port"],
            workdir=settings["ucnrr_workdir"],
            start_cmd=settings["ucnrr_start_cmd"].format(port=settings["ucnrr_port"], host="0.0.0.0", PY=PY),
            env=ucnrr_env,
            health_url=format_url(settings["ucnrr_health_url"], settings),
        ),
        "explorer": ProcSpec(
            name="explorer",
            port=settings["explorer_port"],
            workdir=settings["explorer_workdir"],
            start_cmd=settings["explorer_start_cmd"].format(port=settings["explorer_port"], host="0.0.0.0", PY=PY),
            env=explorer_env,
            health_url=None,
        ),
    }

def start_proc(spec: ProcSpec) -> Optional[int]:
    """Start a service; return PID or None."""
    try:
        # pre-emptively free the port
        kill_port(spec.port)

        env_fragment = ""
        if spec.name == "core":
            env_fragment = _shell_env_fragment(spec.env, CORE_ENV_DISPLAY_KEYS)
        command_preview = f"{env_fragment} {spec.start_cmd}".strip()
        st.info(f"Starting {spec.name} with: `{command_preview}` (cwd={spec.workdir})")
        proc = subprocess.Popen(
            spec.start_cmd,
            cwd=spec.workdir,
            shell=True,  # we want the command string as-is (placeholders already formatted)
            env=spec.env,
            stdout=None,
            stderr=None,
            text=True,
        )

        if spec.health_url:
            deadline = time.time() + 20.0
            last_error = "no response"
            ready = False
            while time.time() < deadline:
                ok, message = check_health(spec.health_url, timeout=2.0)
                if ok:
                    st.success(f"{spec.name} ready → {spec.health_url}")
                    ready = True
                    break
                last_error = message
                time.sleep(2.0)
            if not ready:
                st.warning(
                    f"{spec.name} did not become ready within 20s. Last response from {spec.health_url}: {last_error}"
                )

        return proc.pid
    except Exception as e:
        st.error(f"Failed to start {spec.name}: {e}")
        return None

def stop_proc(pid: int, name: str) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
        # give it a moment, then SIGKILL if needed
        for _ in range(10):
            time.sleep(0.2)
            try:
                os.kill(pid, 0)
            except OSError:
                return
        os.kill(pid, signal.SIGKILL)
    except Exception:
        pass

def check_health(url: str, timeout=1.2) -> tuple[bool, str]:
    try:
        r = requests.get(url, timeout=timeout)
        ok = r.ok
        message = f"{r.status_code} {r.reason}"
        try:
            payload = r.json()
        except Exception:
            payload = None
        if ok and isinstance(payload, dict):
            holistic = payload.get("holistic") if isinstance(payload.get("holistic"), dict) else None
            if holistic:
                message += (
                    " — holistic enabled="
                    f"{holistic.get('enabled')} rules={holistic.get('rules_loaded')} "
                    f"baselines={holistic.get('baselines_loaded')}"
                )
        return ok, message
    except Exception as e:
        return False, str(e)


def _summarize_holistic(report: dict) -> dict:
    return {
        "ucn_rr_updates": len(report.get("ucn_rr_updates") or []),
        "implied_additions": len(report.get("implied_additions") or []),
        "contradictions": len(report.get("contradictions") or []),
        "async": bool(report.get("async_")),
    }

# ---- UI ----------------------------------------------------------------------

st.set_page_config(page_title="ReDNA Control Panel+", page_icon="🧬", layout="wide")
st.title("🧬 ReDNA Control Panel+")

settings = load_settings()
state = load_state()

loaded_env_flags = _load_env_flags()
if ENV_FLAGS_PERSISTED_KEY not in st.session_state:
    st.session_state[ENV_FLAGS_PERSISTED_KEY] = dict(loaded_env_flags)
if ENV_FLAGS_SESSION_KEY not in st.session_state:
    st.session_state[ENV_FLAGS_SESSION_KEY] = dict(loaded_env_flags)

env_flags = st.session_state[ENV_FLAGS_SESSION_KEY]
persisted_flags = st.session_state[ENV_FLAGS_PERSISTED_KEY]

_apply_env_flags(env_flags)
_render_env_flag_chips(env_flags)

service_state = st.session_state.get("_service_console_state")
if not isinstance(service_state, dict):
    service_state = {}

session_main_port = st.session_state.get("_main_explorer_port")
if session_main_port is not None:
    settings["explorer_port"] = _coerce_int(session_main_port, settings["explorer_port"])
session_dev_port = st.session_state.get("_dev_explorer_port")
if session_dev_port is not None:
    settings["devexp_port"] = _coerce_int(session_dev_port, settings["devexp_port"])

with st.sidebar:
    st.header("Ports & Options")

    colA, colB = st.columns(2)
    with colA:
        settings["core_port"] = st.number_input("Core port", 1, 65535, value=int(settings["core_port"]))
        settings["ucnrr_port"] = st.number_input("UCN/RR port", 1, 65535, value=int(settings["ucnrr_port"]))
        settings["explorer_port"] = st.number_input("Explorer port", 1, 65535, value=int(settings["explorer_port"]))
        settings["devexp_port"] = st.number_input(
            "Dev Explorer port",
            1,
            65535,
            value=int(settings["devexp_port"]),
            help="Port dedicated to Dev Explorer; must differ from CP+ and Main Explorer.",
        )
        st.session_state["_main_explorer_port"] = int(settings["explorer_port"])
        st.session_state["_dev_explorer_port"] = int(settings["devexp_port"])
    with colB:
        st.markdown("**Host:** `127.0.0.1`")
        st.markdown("Logs are written to your terminal(s).")

    st.divider()
    st.caption("Working directories")
    settings["core_workdir"] = st.text_input("Core workdir", value=settings["core_workdir"])
    settings["ucnrr_workdir"] = st.text_input("UCN/RR workdir", value=settings["ucnrr_workdir"])
    settings["explorer_workdir"] = st.text_input("Explorer workdir", value=settings["explorer_workdir"])

    st.divider()
    st.caption("Start commands")
    settings["core_start_cmd"] = st.text_input("Core start command", value=settings["core_start_cmd"])
    settings["ucnrr_start_cmd"] = st.text_input("UCN/RR start command", value=settings["ucnrr_start_cmd"])
    settings["explorer_start_cmd"] = st.text_input("Explorer start command", value=settings["explorer_start_cmd"])

    st.divider()
    st.caption("Service environment (templated)")
    settings["UCNRR_BASE"] = st.text_input("UCNRR_BASE", value=settings["UCNRR_BASE"])
    settings["EXPLORER_BASE"] = st.text_input("EXPLORER_BASE", value=settings["EXPLORER_BASE"])

    st.divider()
    st.caption("Core AI settings (optional)")
    settings["CORE_USE_LLM"] = st.checkbox(
        "CORE_USE_LLM",
        value=bool(settings.get("CORE_USE_LLM")),
        help="Enable Core-side LLM inferences when available.",
    )
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        settings["CORE_LLM_PROVIDER"] = st.text_input(
            "CORE_LLM_PROVIDER", value=settings.get("CORE_LLM_PROVIDER", "")
        )
        settings["CORE_LLM_MODEL"] = st.text_input(
            "CORE_LLM_MODEL", value=settings.get("CORE_LLM_MODEL", "")
        )
    with col_c2:
        settings["CORE_LLM_BASE_URL"] = st.text_input(
            "CORE_LLM_BASE_URL", value=settings.get("CORE_LLM_BASE_URL", "")
        )
        settings["CORE_LLM_API_KEY"] = st.text_input(
            "CORE_LLM_API_KEY", value=settings.get("CORE_LLM_API_KEY", ""), type="password"
        )

    st.divider()
    st.caption("Holistic review settings")
    settings["CORE_HOLISTIC_ON_INGEST"] = st.checkbox(
        "CORE_HOLISTIC_ON_INGEST",
        value=bool(settings.get("CORE_HOLISTIC_ON_INGEST")),
        help="Run Core's holistic review automatically after ingest/import when enabled.",
    )
    settings["CORE_HOLISTIC_MAX_MS"] = int(
        st.number_input(
            "CORE_HOLISTIC_MAX_MS",
            min_value=50,
            max_value=5000,
            step=50,
            value=int(settings.get("CORE_HOLISTIC_MAX_MS", 300)),
            help="Time budget (ms) before Core marks the pass as async.",
        )
    )

    if st.button("💾 Save settings", use_container_width=True):
        save_settings(settings)
        st.success("Settings saved.")

st.markdown("### Environment Flags")
with st.container(border=True):
    st.caption(
        "Toggle shared guardrails for Dev Explorer and demos. Changes persist only when write-protect is OFF."
    )

    profile_options = ["Custom"] + list(PROFILE_PRESETS.keys())
    st.session_state.setdefault("_launch_profile", "Custom")

    def _on_profile_change() -> None:
        selection = st.session_state.get("_launch_profile", "Custom")
        if selection == "Custom":
            st.session_state[ENV_PROFILE_APPLIED_KEY] = "Custom"
            return
        _apply_profile(selection)

    st.selectbox(
        "Launch profile",
        profile_options,
        index=profile_options.index(st.session_state.get("_launch_profile", "Custom")),
        key="_launch_profile",
        help="Apply preset Dev Explorer guardrails. Profiles modify the toggles below without saving to disk.",
        on_change=_on_profile_change,
    )

    left_col, right_col = st.columns(2)
    with left_col:
        env_flags["WRITE_PROTECT"] = st.toggle(
            "WRITE_PROTECT",
            value=bool(env_flags.get("WRITE_PROTECT", True)),
            help="Blocks disk writes when true. Required for safe demos.",
            key="env_flag_write_protect",
        )
        env_flags["DEV_EXPLORER_ENABLED"] = st.toggle(
            "DEV_EXPLORER_ENABLED",
            value=bool(env_flags.get("DEV_EXPLORER_ENABLED", True)),
            help="Global kill-switch for ExplorerDev tooling.",
            key="env_flag_dev_explorer",
        )
        env_flags["CORE_CURIOSITY_ENABLED"] = st.toggle(
            "CORE_CURIOSITY_ENABLED",
            value=bool(env_flags.get("CORE_CURIOSITY_ENABLED", False)),
            help="When on, Core seeds and serves live curiosity snapshots.",
            key="env_flag_curiosity",
        )
        env_flags["DEMO_BASELINES_ENABLED"] = st.toggle(
            "DEMO_BASELINES_ENABLED",
            value=bool(env_flags.get("DEMO_BASELINES_ENABLED", False)),
            help="Allow RR Baselines Lab overrides to drive demo calculations.",
            key="env_flag_demo_baselines",
        )

    with right_col:
        env_flags["DEV_LOOPTEST_USER_ID"] = st.text_input(
            "DEV_LOOPTEST_USER_ID",
            value=str(env_flags.get("DEV_LOOPTEST_USER_ID", "devexp_test") or ""),
            help="Default user id for diagnostics deep-link replay.",
            key="env_flag_loop_user",
        )
        env_flags["DEV_HTTP_TIMEOUT_SECONDS"] = st.number_input(
            "DEV_HTTP_TIMEOUT_SECONDS",
            min_value=0.5,
            max_value=120.0,
            step=0.5,
            value=float(env_flags.get("DEV_HTTP_TIMEOUT_SECONDS", 6.0)),
            help="HTTP timeout for Dev Explorer probes (seconds).",
            key="env_flag_timeout",
        )

    toggle_col1, toggle_col2 = st.columns(2)
    with toggle_col1:
        env_flags["HC_SEND_ENABLED"] = st.toggle(
            "HC_SEND_ENABLED",
            value=bool(env_flags.get("HC_SEND_ENABLED", False)),
            help="Allow Head Coach preview panes to enqueue motivators via Dev Explorer.",
            key="env_flag_hc_send",
        )
        env_flags["HC_OPS_ENABLED"] = st.toggle(
            "HC_OPS_ENABLED",
            value=bool(env_flags.get("HC_OPS_ENABLED", False)),
            help="Expose Head Coach Ops analytics panel in Dev Explorer.",
            key="env_flag_hc_ops",
        )

    with toggle_col2:
        env_flags["NUDGE_INBOX_ENABLED"] = st.toggle(
            "NUDGE_INBOX_ENABLED",
            value=bool(env_flags.get("NUDGE_INBOX_ENABLED", False)),
            help="Enable Main Explorer inbox actions and tabs.",
            key="env_flag_inbox",
        )
        env_flags["FEEDBACK_ENABLED"] = st.toggle(
            "FEEDBACK_ENABLED",
            value=bool(env_flags.get("FEEDBACK_ENABLED", True)),
            help="Show feedback capture buttons and dashboard in Explorer.",
            key="env_flag_feedback",
        )
        env_flags["AUDIT_VIEWER_ENABLED"] = st.toggle(
            "AUDIT_VIEWER_ENABLED",
            value=bool(env_flags.get("AUDIT_VIEWER_ENABLED", True)),
            help="Expose Dev Explorer audit viewer and rollback tools.",
            key="env_flag_audit_viewer",
        )

    st.session_state.setdefault("_flags_dirty", False)
    normalized_session = _normalize_env_flags(env_flags)
    normalized_persisted = _normalize_env_flags(persisted_flags)
    changed_keys = sorted(
        {
            *[key for key in normalized_session.keys() if normalized_session.get(key) != normalized_persisted.get(key)],
            *[key for key in normalized_persisted.keys() if normalized_session.get(key) != normalized_persisted.get(key)],
        }
    )
    pending_changes = bool(changed_keys)
    st.session_state["_flags_dirty"] = pending_changes
    write_protect_active = bool(normalized_session.get("WRITE_PROTECT", True))

    col_save, col_status = st.columns([1, 1])
    with col_save:
        save_enabled = (not write_protect_active) and pending_changes
        if save_enabled:
            save_disabled = False
            save_message = ""
            save_tooltip = "Persist current environment flags to .env and Dev prefs."
        else:
            save_disabled = True
            if write_protect_active:
                save_message = "Write-protect ON — session only."
                save_tooltip = "Disable WRITE_PROTECT to persist changes."
            else:
                save_message = "No changes to save."
                save_tooltip = "Adjust a flag to enable saving."
        if st.button(
            "Save env flags",
            use_container_width=True,
            disabled=save_disabled,
            help=save_tooltip,
            key="save_env_flags_button",
        ):
            try:
                _persist_env_flags(normalized_session, write_protect=write_protect_active)
            except PermissionError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - defensive guard for file IO
                st.error(f"Unable to persist env flags: {exc}")
            else:
                st.session_state[ENV_FLAGS_PERSISTED_KEY] = dict(normalized_session)
                persisted_flags = st.session_state[ENV_FLAGS_PERSISTED_KEY]
                st.success("Environment flags saved.")
                pending_changes = False
                st.session_state["_flags_dirty"] = False
                changed_keys = []
        if save_message:
            st.caption(save_message)
        if changed_keys:
            st.caption("Changed: " + ", ".join(changed_keys))
        else:
            st.caption("Changed: none")

    with col_status:
        if bool(persisted_flags.get("WRITE_PROTECT", True)):
            st.info("Write-protect ON — edits stay in session only.")
        elif not pending_changes:
            st.success("Flags match persisted values.")
        else:
            st.warning("Unsaved changes — hit Save when ready.")

_apply_env_flags(env_flags)

effective_service_settings = {
    "ucnrr_base": service_state.get("ucnrr_base") or format_url(settings["UCNRR_BASE"], settings),
    "core_base": service_state.get("core_base") or f"http://127.0.0.1:{settings['core_port']}",
    "llm_base": service_state.get("llm_base") or os.getenv("LLM_BASE_URL") or "",
    "timeout": float(service_state.get("timeout", normalized_session.get("DEV_HTTP_TIMEOUT_SECONDS", 6.0))),
    "llm_timeout": float(service_state.get("llm_timeout", normalized_session.get("DEV_HTTP_TIMEOUT_SECONDS", 6.0))),
}

st.markdown("### Dev Explorer Launcher")
with st.container(border=True):
    curiosity_options = ["live", "sim"]
    default_mode = "live" if bool(normalized_session.get("CORE_CURIOSITY_ENABLED", False)) else "sim"
    st.session_state.setdefault("_devexp_curiosity_mode", default_mode)
    try:
        default_index = curiosity_options.index(st.session_state.get("_devexp_curiosity_mode", default_mode))
    except ValueError:
        default_index = curiosity_options.index(default_mode)
        st.session_state["_devexp_curiosity_mode"] = default_mode

    curiosity_mode = st.radio(
        "Curiosity mode",
        curiosity_options,
        index=default_index,
        horizontal=True,
        key="_devexp_curiosity_mode",
    )

    summary_flags = dict(normalized_session)
    summary_flags["CORE_CURIOSITY_ENABLED"] = curiosity_mode == "live"
    summary_text = _env_summary(summary_flags)
    st.caption(summary_text)
    st.caption(f"Curiosity: {curiosity_mode}")

    col_snapshot, col_persona = st.columns(2)
    snapshot_id = col_snapshot.text_input(
        "Diagnostics snapshot id",
        key="devexp_snapshot_id",
        help="Optional. Adds ?snapshot=<id> when opening Diagnostics.",
    )
    persona_id = col_persona.text_input(
        "Coach persona id",
        key="devexp_persona_id",
        help="Optional. Preselects a persona in Coach Workshop (requires Dev Explorer support).",
    )

    col_container, col_trait = st.columns(2)
    container_id = col_container.text_input(
        "Container id",
        key="devexp_container_id",
        help="Optional. Focuses this container in Container Studio.",
    )
    trait_id = col_trait.text_input(
        "Trait id",
        key="devexp_trait_id",
        help="Optional. Focuses this trait alongside the container.",
    )

    anchor_cols = st.columns(2)
    coach_anchor = anchor_cols[0].text_input(
        "Coach anchor",
        value="sandbox",
        key="devexp_coach_anchor",
        help="Optional fragment (without #) appended for Coach Workshop.",
    )
    container_anchor = anchor_cols[1].text_input(
        "Container anchor",
        value="container-studio-editor",
        key="devexp_container_anchor",
        help="Optional fragment (without #) appended for Container Studio.",
    )

    dev_port = _coerce_int(st.session_state.get("_dev_explorer_port"), settings["devexp_port"])
    main_port = _coerce_int(st.session_state.get("_main_explorer_port"), settings["explorer_port"])
    devexp_workdir = settings.get("devexp_workdir", str((ROOT / "ExplorerDev").resolve()))
    devexp_cmd_template = settings.get("devexp_start_cmd", DEFAULTS["devexp_start_cmd"])

    def _compose_devexp_url(port: int, request: Mapping[str, str]) -> str:
        target = (request.get("target") or "Diagnostics").strip() or "Diagnostics"
        query: Dict[str, str] = {"nav": target}
        fragment = ""

        if target == "Diagnostics":
            snapshot = (request.get("snapshot_id") or "").strip()
            if snapshot:
                query["snapshot"] = snapshot
        if target == "Coach Workshop":
            persona = (request.get("persona_id") or "").strip()
            if persona:
                query["persona"] = persona
            anchor = (request.get("coach_anchor") or "").strip("# ")
            if anchor:
                fragment = anchor
        if target == "Container Studio":
            container_value = (request.get("container_id") or "").strip()
            trait_value = (request.get("trait_id") or "").strip()
            if container_value:
                query["container"] = container_value
            if trait_value:
                query["trait"] = trait_value
            anchor = (request.get("container_anchor") or "").strip("# ")
            if anchor:
                fragment = anchor

        query_string = urlencode({k: v for k, v in query.items() if v})
        url = f"http://127.0.0.1:{port}/"
        if query_string:
            url = f"{url}?{query_string}"
        if fragment:
            url = f"{url}#{fragment}"
        return url

    def _queue_devexp_launch(target: str) -> None:
        def _clean(value: Any) -> str:
            return str(value).strip() if isinstance(value, str) else ""

        st.session_state["_devexp_launch_request"] = {
            "target": target,
            "snapshot_id": _clean(snapshot_id),
            "persona_id": _clean(persona_id),
            "container_id": _clean(container_id),
            "trait_id": _clean(trait_id),
            "coach_anchor": _clean(coach_anchor),
            "container_anchor": _clean(container_anchor),
        }
        _mark_deferred_rerun()

    def _execute_devexp_launch(request: Dict[str, Any]) -> None:
        st.session_state.pop("_devexp_launch_request", None)

        current_dev_port = _coerce_int(st.session_state.get("_dev_explorer_port"), dev_port)
        current_main_port = _coerce_int(st.session_state.get("_main_explorer_port"), main_port)
        cp_value = _resolve_cp_port()

        if current_dev_port == current_main_port:
            st.error("Dev Explorer port conflicts with Main Explorer. Choose a different port.")
            return
        if cp_value and current_dev_port == cp_value:
            st.error("Dev Explorer port conflicts with Control Panel+. Choose a different port.")
            return

        env = _build_devexp_env(normalized_session, effective_service_settings)
        curiosity_mode = st.session_state.get("_devexp_curiosity_mode", "live")
        env["CORE_CURIOSITY_ENABLED"] = "true" if curiosity_mode == "live" else "false"
        cmd = _build_devexp_cmd(devexp_cmd_template, current_dev_port, workdir=devexp_workdir)

        if _is_port_in_use(current_dev_port):
            pid = _pid_on_port(current_dev_port)
            descriptor = _describe_process(pid) if pid else ""
            role = _classify_process(descriptor)

            if role == "dev":
                ready, last_error = _wait_for_devexp_ready(current_dev_port)
                url = _compose_devexp_url(current_dev_port, request)
                if pid:
                    pids = state.get("pids", {})
                    pids["devexp"] = pid
                    state["pids"] = pids
                    save_state(state)
                if ready:
                    webbrowser.open(url)
                    st.success(f"Reusing Dev Explorer → {url}")
                else:
                    st.error(
                        "Existing Dev Explorer did not respond within 8s. Last response: "
                        + (last_error or "no response")
                    )
                return

            forbidden = {current_main_port}
            if cp_value:
                forbidden.add(cp_value)
            candidate = _next_free_port(current_dev_port + 1, forbidden=forbidden)
            if candidate == current_dev_port:
                candidate += 1
            st.session_state["_devexp_conflict_offer"] = {
                "port": current_dev_port,
                "occupied_by": "Main Explorer" if role == "main" else "another process",
                "pid": pid,
                "command": descriptor,
                "suggested_port": candidate,
                "request": dict(request),
            }
            return

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=devexp_workdir,
                shell=True,
                env=env,
            )
        except Exception as exc:
            st.error(f"Unable to launch Dev Explorer: {exc}")
            return

        pids = state.get("pids", {})
        pids["devexp"] = proc.pid
        state["pids"] = pids
        save_state(state)

        ready, last_error = _wait_for_devexp_ready(current_dev_port)
        url = _compose_devexp_url(current_dev_port, request)

        if ready:
            webbrowser.open(url)
            st.success(f"Launching Dev Explorer → {url}")
        else:
            exit_code = proc.poll()
            if exit_code is not None:
                pids.pop("devexp", None)
                state["pids"] = pids
                save_state(state)
                st.error(
                    f"Dev Explorer exited immediately (code {exit_code}). See launch command below for context."
                )
            else:
                st.error(
                    "Dev Explorer did not become ready within 8s. Last response: "
                    + (last_error or "no response")
                )
                st.info("Use Kill DevExp port and try again if needed.")

        important_env = {
            key: env.get(key)
            for key in [
                "WRITE_PROTECT",
                "CORE_CURIOSITY_ENABLED",
                "DEMO_BASELINES_ENABLED",
                "DEV_LOOPTEST_USER_ID",
                "DEV_HTTP_TIMEOUT_SECONDS",
                "CORE_BASE_URL",
                "UCNRR_BASE_URL",
                "LLM_BASE_URL",
            ]
            if key in env
        }
        st.caption("Launch env overrides")
        st.json(important_env)
        st.caption("Launch command")
        st.code(cmd, language="bash")

    pending_request = st.session_state.get("_devexp_launch_request")
    if pending_request:
        _execute_devexp_launch(dict(pending_request))

    conflict = st.session_state.get("_devexp_conflict_offer")
    if conflict:
        conflict_port = conflict.get("port")
        occupied = conflict.get("occupied_by", "another process")
        pid_value = conflict.get("pid")
        suggested_port = _coerce_int(conflict.get("suggested_port"), dev_port)
        with st.container(border=True):
            message = f"Port {conflict_port} is busy ({occupied})."
            if pid_value:
                message += f" PID {pid_value}."
            st.error(message)
            command_hint = conflict.get("command")
            if command_hint:
                st.code(command_hint, language="bash")
            st.caption(f"Suggested port: {suggested_port}")
            accept_col, cancel_col = st.columns([2, 1])
            if accept_col.button(
                f"Use port {suggested_port}",
                key="devexp_conflict_accept",
            ):
                new_port = suggested_port
                st.session_state["_dev_explorer_port"] = new_port
                settings["devexp_port"] = new_port
                st.session_state.pop("_devexp_conflict_offer", None)
                request_payload = conflict.get("request")
                if isinstance(request_payload, Mapping):
                    st.session_state["_devexp_launch_request"] = dict(request_payload)
                    _mark_deferred_rerun()
                else:
                    st.session_state.pop("_devexp_launch_request", None)
            if cancel_col.button("Cancel", key="devexp_conflict_cancel"):
                st.session_state.pop("_devexp_conflict_offer", None)

launcher_cols = st.columns(3)
if launcher_cols[0].button("Open Coach Workshop", use_container_width=True):
    _queue_devexp_launch("Coach Workshop")
if launcher_cols[1].button("Open Container Studio", use_container_width=True):
    _queue_devexp_launch("Container Studio")
if launcher_cols[2].button("Open Diagnostics", use_container_width=True):
    _queue_devexp_launch("Diagnostics")

if st.button("Kill DevExp port", key="kill_devexp_port"):
    target_port = _coerce_int(st.session_state.get("_dev_explorer_port"), dev_port)
    kill_port(target_port)
    st.success(f"Sent kill signal to port {target_port}.")

specs = make_specs(settings)

st.markdown("### Controls")

c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("🚀 Start All", use_container_width=True):
        save_settings(settings)
        specs = make_specs(settings)
        pids = state.get("pids", {})
        for name in ("ucnrr", "core", "explorer"):  # order matters (Core after UCN/RR)
            pid = start_proc(specs[name])
            if pid:
                pids[name] = pid
        state["pids"] = pids
        save_state(state)
with c2:
    if st.button("🛑 Stop All", use_container_width=True):
        pids = state.get("pids", {})
        for name, pid in list(pids.items()):
            stop_proc(pid, name)
            pids.pop(name, None)
        state["pids"] = pids
        save_state(state)
with c3:
    if st.button("🔪 Kill ports", use_container_width=True):
        for p in (settings["ucnrr_port"], settings["core_port"], settings["explorer_port"]):
            kill_port(int(p))
        st.success("Ports killed.")
with c4:
    st.button("🔁 Refresh", use_container_width=True)

st.markdown("### Services")

def service_card(tag: str, spec: ProcSpec):
    pids = state.get("pids", {})
    pid = pids.get(tag)

    with st.container(border=True):
        st.subheader(tag.upper())
        command_preview = spec.start_cmd
        if tag == "core":
            curiosity_env = str(spec.env.get("CORE_CURIOSITY_ENABLED", "false")).lower()
            curiosity_live = "on" if curiosity_env in TRUTHY else "off"
            st.caption(f"Curiosity (Core flag): {curiosity_live}")
            env_fragment = _shell_env_fragment(spec.env, CORE_ENV_DISPLAY_KEYS)
            if env_fragment:
                command_preview = f"{env_fragment} {spec.start_cmd}"
            st.code(command_preview, language="bash")
            _log_core_launch_env(spec.env)
        else:
            st.code(command_preview, language="bash")

        col1, col2, col3, col4 = st.columns([1.3, 1, 1, 2])
        with col1:
            st.markdown("&nbsp;", unsafe_allow_html=True)
        with col2:
            if st.button(f"Start {tag}", key=f"start_{tag}", use_container_width=True):
                new_pid = start_proc(spec)
                if new_pid:
                    pids[tag] = new_pid
                    state["pids"] = pids
                    save_state(state)
        with col3:
            if st.button(f"Stop {tag}", key=f"stop_{tag}", type="secondary", use_container_width=True):
                if pid:
                    stop_proc(pid, tag)
                    pids.pop(tag, None)
                    state["pids"] = pids
                    save_state(state)
        with col4:
            st.write(f"**PID:** {pid or '—'}")
            st.write(f"**Port:** {spec.port}")
            st.write(f"**CWD:** `{spec.workdir}`")

        if spec.health_url:
            ok, msg = check_health(spec.health_url)
            st.write(f"Health: {'🟢 OK' if ok else '🟡 not ready / 🔴 down'} — {spec.health_url}")
            st.caption(msg)
        else:
            # Explorer (no health endpoint). Offer open link.
            url = f"http://127.0.0.1:{spec.port}"
            st.write(f"Open: {url}")

service_card("ucnrr", specs["ucnrr"])
service_card("core", specs["core"])
service_card("explorer", specs["explorer"])

st.caption("Tip: Start UCN/RR → start Core → then start Explorer. Core receives UCNRR_BASE via env automatically.")

st.markdown("### Holistic Controls")
hol_cols = st.columns([3, 1])
with hol_cols[0]:
    holistic_user = st.text_input(
        "User id for holistic run",
        value="",
        placeholder="e.g., TEST123",
    )
with hol_cols[1]:
    if st.button("Run Holistic", use_container_width=True):
        uid = holistic_user.strip()
        if not uid:
            st.warning("Enter a user id before running holistic review.")
        else:
            core_url = f"http://127.0.0.1:{settings['core_port']}"
            try:
                with st.spinner("Triggering Core holistic review…"):
                    resp = requests.post(f"{core_url}/holistic/{uid}", timeout=20)
                payload: Dict[str, Any]
                if resp.headers.get("content-type", "").startswith("application/json"):
                    payload = resp.json()
                else:
                    payload = {}
                if resp.ok:
                    summary = _summarize_holistic(payload)
                    st.success(
                        f"Holistic review completed — {summary['ucn_rr_updates']} adjusted, "
                        f"{summary['implied_additions']} implied, {summary['contradictions']} contradictions."
                    )
                    if payload:
                        st.json(payload, expanded=False)
                else:
                    st.error(f"Holistic review failed ({resp.status_code}): {resp.text[:200]}")
            except Exception as exc:
                st.error(f"Holistic request error: {exc}")
def _apply_profile(name: str) -> None:
    profile = PROFILE_PRESETS.get(name)
    if not profile:
        return
    flags = st.session_state.get(ENV_FLAGS_SESSION_KEY, {})
    if not isinstance(flags, dict):
        flags = {}
    flags.update(profile)
    st.session_state[ENV_FLAGS_SESSION_KEY] = flags
    st.session_state[ENV_PROFILE_APPLIED_KEY] = name
    st.session_state["_flags_dirty"] = True
    _mark_deferred_rerun()


if st.session_state.get("_deferred_rerun"):
    st.session_state["_deferred_rerun"] = False
    _safe_rerun()
