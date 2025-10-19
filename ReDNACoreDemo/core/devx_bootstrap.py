# ReDNACoreDemo/core/devx_bootstrap.py
"""DevX Bootstrap Helper — Start/stop DevX backend and UI with health checks."""

from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import socket
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore

HOME = Path.home()
STATE_DIR = HOME / ".redna"
STATE_DIR.mkdir(parents=True, exist_ok=True)

DEVX_BACKEND_PID = STATE_DIR / "devx_backend.pid"
DEVX_UI_PID = STATE_DIR / "devx_ui.pid"
STATE_JSON = STATE_DIR / "devx_state.json"


def env_get(k: str, default: Optional[str] = None) -> str:
    """Get environment variable with fallback to default."""
    val = os.environ.get(k, default)
    if val in ("", None):
        return default or ""
    return val


def load_last_ui_port() -> Optional[int]:
    """Load the last known UI port from state file."""
    try:
        if STATE_JSON.exists():
            data = json.loads(STATE_JSON.read_text())
            p = int(data.get("ui_port", 0))
            return p if p > 0 else None
    except Exception:
        return None
    return None


def save_last_ui_port(port: int) -> None:
    """Save the current UI port to state file."""
    try:
        STATE_JSON.write_text(json.dumps({
            "ui_port": int(port),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }))
    except Exception:
        pass


def is_port_open(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_free_port(start: int, limit: int = 20) -> Optional[int]:
    """Find the next available port starting from 'start'."""
    for p in range(start, start + limit):
        if not is_port_open(p):
            return p
    return None


def _wait_until(predicate, timeout_s: float, base: float = 0.2, cap: float = 1.6) -> bool:
    """
    Wait until predicate returns True, using exponential backoff.
    Returns True if predicate became true within timeout, False otherwise.
    """
    slept = 0.0
    step = base
    while slept < timeout_s:
        if predicate():
            return True
        time.sleep(step)
        slept += step
        step = min(cap, step * 2.0)
    return predicate()


def _is_process_alive(pid: int) -> bool:
    """Check if a process is alive (cross-platform)."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we can't send signals
        return True
    except Exception:
        return False


def _write_pidfile(path: Path, pid: int) -> None:
    """Write PID to file for later cleanup."""
    path.write_text(str(pid))


def _read_pidfile(path: Path) -> Optional[int]:
    """Read PID from file, with stale PID detection."""
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().strip())
        # Check if process is still alive
        if not _is_process_alive(pid):
            # Stale PID file, clean it up
            path.unlink(missing_ok=True)
            return None
        return pid
    except Exception:
        # Invalid PID file, clean it up
        path.unlink(missing_ok=True)
        return None


def _log_handles(prefix: str):
    """Get log file handles for subprocess output based on verbose setting."""
    if os.environ.get("DEVX_VERBOSE_LOGS", "").lower() == "true":
        log_file = STATE_DIR / f"{prefix}.log"
        f = open(log_file, "a", buffering=1)
        return f, f
    return subprocess.DEVNULL, subprocess.STDOUT


def _terminate_pid(pid: int) -> None:
    """Gracefully terminate a process (SIGTERM then SIGKILL fallback)."""
    if not _is_process_alive(pid):
        return

    try:
        # Try graceful termination first
        if os.name == "nt":
            # Windows: try CTRL_BREAK_EVENT first, then SIGTERM
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                time.sleep(0.4)
            except Exception:
                pass
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        else:
            # Unix: SIGTERM
            os.kill(pid, signal.SIGTERM)

        # Wait up to 2 seconds for graceful shutdown
        for _ in range(8):
            time.sleep(0.25)
            if not _is_process_alive(pid):
                return

        # Still alive, use SIGKILL
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        # Can't kill, nothing we can do
        return
    except Exception:
        # Best effort
        return


def _kill_pidfile(path: Path) -> Optional[int]:
    """Kill process by PID file and remove the file. Returns PID if killed."""
    pid = _read_pidfile(path)
    if pid:
        _terminate_pid(pid)
        path.unlink(missing_ok=True)
        return pid
    path.unlink(missing_ok=True)
    return None


def _find_pid_on_port(port: int) -> Optional[int]:
    """Find PID of process listening on given port using lsof."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split()[0])
    except Exception:
        pass
    return None


def _kill_port(port: int) -> Optional[int]:
    """Kill process listening on given port. Returns PID if killed."""
    pid = _find_pid_on_port(port)
    if pid:
        _terminate_pid(pid)
        return pid
    return None


def devx_backend_health(port: int) -> bool:
    """Check if DevX backend is healthy via /health endpoint."""
    if requests is None:
        return False
    try:
        r = requests.get(f"http://127.0.0.1:{port}/health", timeout=0.6)
        return r.ok
    except Exception:
        return False


def devx_ui_health(port: int) -> bool:
    """Check if DevX UI (React/Vite) is healthy."""
    if requests is None:
        return False
    # Vite dev server serves at root
    try:
        r = requests.get(f"http://127.0.0.1:{port}/", timeout=0.6)
        return r.ok
    except Exception:
        return False


def ensure_devx_requirements_commands() -> list[str]:
    """
    Return command(s) to install missing deps.
    Present to the user; do not auto-run silently.
    """
    py = env_get("DEVX_PY", sys.executable) or sys.executable
    frontend_dir = env_get("DEVX_UI_DIR", "ReDNACoreDemo/devx/frontend")

    cmds = []
    # Backend: Python dependencies
    cmds.append(f"{py} -m pip install fastapi uvicorn requests")

    # Frontend: npm dependencies
    if Path(frontend_dir).exists():
        cmds.append(f"cd {frontend_dir} && npm install")
    else:
        cmds.append("# DevX frontend: npm install (directory not found)")

    return cmds


def start_devx_backend() -> Tuple[bool, str, int]:
    """
    Start DevX backend (FastAPI/uvicorn).
    Returns: (success, message, port)
    """
    py = env_get("DEVX_PY", sys.executable) or sys.executable
    port = int(env_get("DEVX_BACKEND_PORT", "8100") or "8100")

    # Check if already running
    if devx_backend_health(port):
        return True, f"DevX backend already healthy on {port}", port

    # Try module-based uvicorn first (devx.api:app)
    cmd = [
        py, "-m", "uvicorn",
        "ReDNACoreDemo.devx.backend.api:app",
        "--port", str(port),
        "--host", "127.0.0.1",
        "--reload"
    ]

    # Fallback to script entry if DEVX_BACKEND_ENTRY is set
    entry = env_get("DEVX_BACKEND_ENTRY", "")
    if entry and Path(entry).exists():
        cmd = [py, entry, "--port", str(port)]

    try:
        # Get log handles based on verbose setting
        out, err = _log_handles("devx_backend")

        proc = subprocess.Popen(
            cmd,
            stdout=out,
            stderr=err,
            cwd=str(Path.cwd())
        )
        _write_pidfile(DEVX_BACKEND_PID, proc.pid)

        # Wait for health check with bounded backoff
        ok = _wait_until(lambda: devx_backend_health(port), timeout_s=10.0)

        if ok:
            return True, f"DevX backend started on {port} (pid {proc.pid})", port
        return False, f"DevX backend started but failed health check on {port}", port
    except Exception as e:
        return False, f"Failed to start DevX backend: {e}", port


def start_devx_ui() -> Tuple[bool, str, int]:
    """
    Start DevX UI (React/Vite frontend).
    Returns: (success, message, actual_port)
    Auto-selects next free port if desired port is busy.
    """
    desired_port = int(env_get("DEVX_UI_PORT", "3100") or "3100")
    port = desired_port

    # Find free port if desired port is busy
    if is_port_open(port):
        free = find_free_port(port + 1)
        if free is None:
            return False, f"Port {port} busy and no free port found nearby", port
        port = free

    # DevX frontend is a React/Vite app, use npm run dev
    frontend_dir = env_get("DEVX_UI_DIR", "ReDNACoreDemo/devx/frontend")
    cmd = [
        "npm", "run", "dev",
        "--", "--port", str(port), "--host", "127.0.0.1"
    ]

    try:
        # Get log handles based on verbose setting
        out, err = _log_handles("devx_ui")

        # Change to frontend directory for npm
        frontend_path = Path(frontend_dir)
        if not frontend_path.exists():
            return False, f"DevX frontend directory not found: {frontend_dir}", port

        proc = subprocess.Popen(
            cmd,
            stdout=out,
            stderr=err,
            cwd=str(frontend_path)
        )
        _write_pidfile(DEVX_UI_PID, proc.pid)

        # Wait for health check with bounded backoff (Vite dev server startup)
        ok = _wait_until(lambda: devx_ui_health(port), timeout_s=20.0)

        if ok:
            # Save the UI port to state file for persistence
            save_last_ui_port(port)

            msg = f"DevX UI (React) started on {port} (pid {proc.pid})"
            if port != desired_port:
                msg = f"⚠️ Port {desired_port} busy, started on {port} (pid {proc.pid})"
            return True, msg, port

        return False, f"DevX UI started but failed health check on {port}", port
    except Exception as e:
        return False, f"Failed to start DevX UI: {e}", port


def stop_devx() -> Tuple[Optional[int], Optional[int]]:
    """
    Stop both DevX backend and UI by killing their PIDs.
    Falls back to port-based killing if PID file doesn't exist.
    Returns: (backend_pid, ui_pid) if processes were terminated.
    """
    # Try PID file first
    backend_pid = _kill_pidfile(DEVX_BACKEND_PID)
    ui_pid = _kill_pidfile(DEVX_UI_PID)

    # Fallback: kill by port if PID file didn't work
    if not backend_pid:
        backend_port = int(env_get("DEVX_BACKEND_PORT", "8100") or "8100")
        backend_pid = _kill_port(backend_port)

    if not ui_pid:
        ui_port = int(env_get("DEVX_UI_PORT", "3100") or "3100")
        # Also check persisted port from state file
        persisted_port = load_last_ui_port()
        if persisted_port and persisted_port != ui_port:
            # Try persisted port first
            ui_pid = _kill_port(persisted_port)
        if not ui_pid:
            ui_pid = _kill_port(ui_port)

    return backend_pid, ui_pid
