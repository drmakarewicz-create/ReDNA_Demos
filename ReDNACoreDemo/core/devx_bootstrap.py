# ReDNACoreDemo/core/devx_bootstrap.py
"""DevX Bootstrap Helper — Start/stop DevX backend and UI with health checks."""

from __future__ import annotations
import os
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


def env_get(k: str, default: Optional[str] = None) -> str:
    """Get environment variable with fallback to default."""
    val = os.environ.get(k, default)
    if val in ("", None):
        return default or ""
    return val


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


def _write_pidfile(path: Path, pid: int) -> None:
    """Write PID to file for later cleanup."""
    path.write_text(str(pid))


def _read_pidfile(path: Path) -> Optional[int]:
    """Read PID from file."""
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def _kill_pidfile(path: Path) -> None:
    """Kill process by PID file and remove the file."""
    pid = _read_pidfile(path)
    if pid:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
        path.unlink(missing_ok=True)


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
    """Check if DevX UI (Streamlit) is healthy."""
    if requests is None:
        return False
    # Streamlit exposes /healthz; fallback to root
    for path in ("/healthz", "/"):
        try:
            r = requests.get(f"http://127.0.0.1:{port}{path}", timeout=0.6)
            if r.ok:
                return True
        except Exception:
            continue
    return False


def ensure_devx_requirements_commands() -> list[str]:
    """
    Return pip command(s) to install missing deps.
    Present to the user; do not auto-run silently.
    """
    req = env_get("DEVX_REQUIREMENTS", "ExplorerDev/requirements.txt")
    py = env_get("DEVX_PY", sys.executable) or sys.executable
    if Path(req).exists():
        return [f"{py} -m pip install -r {req}"]
    return [f"{py} -m pip install streamlit fastapi uvicorn requests"]


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
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd())
        )
        _write_pidfile(DEVX_BACKEND_PID, proc.pid)

        # Wait for health check
        for _ in range(40):
            time.sleep(0.25)
            if devx_backend_health(port):
                return True, f"DevX backend started on {port} (pid {proc.pid})", port

        return False, f"DevX backend started but failed health check on {port}", port
    except Exception as e:
        return False, f"Failed to start DevX backend: {e}", port


def start_devx_ui() -> Tuple[bool, str, int]:
    """
    Start DevX UI (Streamlit).
    Returns: (success, message, actual_port)
    Auto-selects next free port if desired port is busy.
    """
    py = env_get("DEVX_PY", sys.executable) or sys.executable
    entry = env_get("DEVX_UI_ENTRY", "ExplorerDev/explorer_dev.py")
    desired_port = int(env_get("DEVX_UI_PORT", "8550") or "8550")
    port = desired_port

    # Find free port if desired port is busy
    if is_port_open(port):
        free = find_free_port(port + 1)
        if free is None:
            return False, f"Port {port} busy and no free port found nearby", port
        port = free

    cmd = [
        py, "-m", "streamlit", "run",
        entry,
        "--server.port", str(port),
        "--server.headless", "true"
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd())
        )
        _write_pidfile(DEVX_UI_PID, proc.pid)

        # Wait for health check (Streamlit takes longer to start)
        for _ in range(60):
            time.sleep(0.25)
            if devx_ui_health(port):
                msg = f"DevX UI started on {port} (pid {proc.pid})"
                if port != desired_port:
                    msg = f"⚠️ Port {desired_port} busy, started on {port} (pid {proc.pid})"
                return True, msg, port

        return False, f"DevX UI started but failed health check on {port}", port
    except Exception as e:
        return False, f"Failed to start DevX UI: {e}", port


def stop_devx() -> None:
    """Stop both DevX backend and UI by killing their PIDs."""
    _kill_pidfile(DEVX_BACKEND_PID)
    _kill_pidfile(DEVX_UI_PID)
