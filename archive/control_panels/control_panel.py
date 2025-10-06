# control_panel.py
# ReDNA Control Panel — Start/Stop Core, UCN/RR, Explorer; set ports; write Explorer secrets
# Includes self-healing for missing Python deps and safeguards against killing itself.

# ---------------- Bootstrap: auto-install missing deps ----------------
import sys, subprocess

def _need(mod):
    try:
        __import__(mod)
        return False
    except Exception:
        return True

_missing = []
for m, pkg in [
    ("psutil", "psutil"),
    ("requests", "requests"),
    ("uvicorn", "uvicorn"),
    ("fastapi", "fastapi"),
    ("apscheduler", "apscheduler"),
    ("streamlit", "streamlit"),
]:
    if _need(m):
        _missing.append(pkg)

if _missing:
    subprocess.run([sys.executable, "-m", "pip", "install", *sorted(set(_missing))], check=False)

# ---------------- Imports (safe after bootstrap) ----------------
import os, time, socket, shutil, json
from pathlib import Path
from typing import Optional, Dict, List
import subprocess
import psutil
import requests
import streamlit as st

# ---------------- Paths / Defaults ----------------
REPO = Path(__file__).resolve().parent

CORE_DIR  = REPO / "ReDNACoreDemo"
UCNRR_DIR = REPO / "UCN_RR_Demo"
EXPL_DIR  = REPO / "ExplorerFinal"

EXPL_SECRET = EXPL_DIR / ".streamlit" / "secrets.toml"
RUN_DIR     = REPO / ".run"
RUN_DIR.mkdir(exist_ok=True)

DEFAULT_CORE_PORT  = 8010
DEFAULT_UCNRR_PORT = 8020
DEFAULT_EXPL_PORT  = 8502  # keep this different from Streamlit's default (8501)

# Detect the control panel's own port so we don't kill ourselves accidentally
# Streamlit sets STREAMLIT_SERVER_PORT for the running app.
PANEL_PORT = int(os.environ.get("STREAMLIT_SERVER_PORT", "0") or 0)

# ---------------- Utilities ----------------
def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0

def pidfile(service: str) -> Path:
    return RUN_DIR / f"{service}.pid"

def read_pid(service: str) -> Optional[int]:
    p = pidfile(service)
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except Exception:
        return None

def write_pid(service: str, pid: int) -> None:
    pidfile(service).write_text(str(pid))

def clear_pid(service: str) -> None:
    p = pidfile(service)
    if p.exists():
        p.unlink()

def kill_pid(pid: int) -> None:
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()
    except psutil.NoSuchProcess:
        pass

def kill_by_port(port: int) -> int:
    """Kill any process listening on a given TCP port."""
    killed = 0
    for proc in psutil.process_iter(attrs=["pid","name","cmdline"]):
        try:
            conns = proc.connections(kind="inet")
        except Exception:
            continue
        for c in conns:
            if c.laddr and c.laddr.port == port:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                killed += 1
                break
    return killed

def start_process(cmd: List[str], cwd: Path, env: Dict[str, str], service: str) -> int:
    """Launch a detached process for a service and record its PID."""
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    write_pid(service, p.pid)
    return p.pid

def get_health(url: str, timeout=1.0) -> Optional[dict]:
    try:
        r = requests.get(url, timeout=timeout)
        if r.ok:
            return r.json()
    except Exception:
        return None
    return None

def write_explorer_secret(core_url: str):
    EXPL_SECRET.parent.mkdir(parents=True, exist_ok=True)
    EXPL_SECRET.write_text(f'core_url = "{core_url}"\n', encoding="utf-8")

# ---------------- UI ----------------
st.set_page_config(page_title="ReDNA Control Panel", page_icon="🧬", layout="wide")
st.title("🧬 ReDNA Control Panel")

with st.sidebar:
    st.markdown("### Ports & Options")
    core_port  = st.number_input("Core port", 1, 65535, value=DEFAULT_CORE_PORT, step=1, key="core_port")
    ucn_port   = st.number_input("UCN/RR port", 1, 65535, value=DEFAULT_UCNRR_PORT, step=1, key="ucnrr_port")
    expl_port  = st.number_input("Explorer port (Streamlit)", 1, 65535, value=DEFAULT_EXPL_PORT, step=1, key="expl_port")
    ai_off     = st.checkbox("Run Core with AI disabled  (CORE_AI_OFF=1)", value=True)
    st.markdown("---")
    if st.button("Write Explorer secrets.toml", use_container_width=True):
        write_explorer_secret(f"http://127.0.0.1:{core_port}")
        st.success(f"Wrote {EXPL_SECRET} → core_url=http://127.0.0.1:{core_port}")

col1, col2, col3, col4 = st.columns(4)

# ---------------- CORE ----------------
with col1:
    st.subheader("Core")
    core_url = f"http://127.0.0.1:{core_port}"
    ok = is_port_open(core_port)
    st.write(("🟢" if ok else "🔴") + f" {core_url}")

    if st.button("Start Core", type="primary"):
        # stop any stale PID
        pid = read_pid("core")
        if pid: kill_pid(pid); clear_pid("core")
        # free the port
        if not (PANEL_PORT and core_port == PANEL_PORT):
            kill_by_port(core_port)
        else:
            st.warning(f"Core port equals the control panel port ({PANEL_PORT}); not killing it.")

        env = os.environ.copy()
        if ai_off:
            env["CORE_AI_OFF"] = "1"

        # Run from repo root with module path to avoid cwd confusion.
        cmd = ["uvicorn", "ReDNACoreDemo.app:app", "--host", "127.0.0.1", "--port", str(core_port), "--reload"]
        pid = start_process(cmd, REPO, env, "core")
        time.sleep(1.2)
        st.toast(f"Core starting (pid {pid})")

    if st.button("Stop Core"):
        pid = read_pid("core")
        if pid:
            kill_pid(pid); clear_pid("core")
        if not (PANEL_PORT and core_port == PANEL_PORT):
            kill_by_port(core_port)
        st.toast("Core stopped")

    if st.button("Ping /health"):
        h = get_health(core_url + "/health", timeout=1.2)
        if h:
            st.success(h)
        else:
            st.error("No response")

# ---------------- UCN/RR ----------------
with col2:
    st.subheader("UCN/RR")
    ucn_url = f"http://127.0.0.1:{ucn_port}"
    ok = is_port_open(ucn_port)
    st.write(("🟢" if ok else "🔴") + f" {ucn_url}")

    if st.button("Start UCN/RR", type="primary"):
        pid = read_pid("ucnrr")
        if pid: kill_pid(pid); clear_pid("ucnrr")
        if not (PANEL_PORT and ucn_port == PANEL_PORT):
            kill_by_port(ucn_port)

        # Adjust module path if your app file/module differs
        cmd = ["uvicorn", "UCN_RR_Demo.app:app", "--host", "127.0.0.1", "--port", str(ucn_port), "--reload"]
        pid = start_process(cmd, REPO, os.environ.copy(), "ucnrr")
        time.sleep(1.2)
        st.toast(f"UCN/RR starting (pid {pid})")

    if st.button("Stop UCN/RR"):
        pid = read_pid("ucnrr")
        if pid:
            kill_pid(pid); clear_pid("ucnrr")
        if not (PANEL_PORT and ucn_port == PANEL_PORT):
            kill_by_port(ucn_port)
        st.toast("UCN/RR stopped")

    if st.button("Open Docs (if any)"):
        st.write(f"Open {ucn_url}/docs")

# ---------------- EXPLORER ----------------
with col3:
    st.subheader("Explorer")
    ok = is_port_open(expl_port)
    st.write(("🟢" if ok else "🔴") + f" http://127.0.0.1:{expl_port}")

    if st.button("Start Explorer", type="primary"):
        pid = read_pid("explorer")
        if pid: kill_pid(pid); clear_pid("explorer")

        # Never collide with the control panel itself
        if PANEL_PORT and expl_port == PANEL_PORT:
            st.warning(f"Explorer port equals the control panel port ({PANEL_PORT}). "
                       f"Bumping Explorer to {PANEL_PORT + 1}.")
            expl_port = PANEL_PORT + 1

        if not (PANEL_PORT and expl_port == PANEL_PORT):
            kill_by_port(expl_port)

        # Ensure Explorer points to the current Core
        write_explorer_secret(f"http://127.0.0.1:{core_port}")

        env = os.environ.copy()
        env["CORE_URL"] = f"http://127.0.0.1:{core_port}"

        cmd = ["streamlit", "run", "ExplorerFinal/explorer_final.py", "--server.port", str(expl_port)]
        pid = start_process(cmd, REPO, env, "explorer")
        time.sleep(1.5)
        st.toast(f"Explorer starting (pid {pid})")

    if st.button("Stop Explorer"):
        pid = read_pid("explorer")
        if pid:
            kill_pid(pid); clear_pid("explorer")
        if not (PANEL_PORT and expl_port == PANEL_PORT):
            kill_by_port(expl_port)
        st.toast("Explorer stopped")

    if st.button("Open Explorer"):
        st.write(f"Open http://127.0.0.1:{expl_port}")

# ---------------- Utilities ----------------
with col4:
    st.subheader("Utilities")
    target_port = st.number_input("Kill anything on port …", 1, 65535, value=8010)

    if st.button("Kill Port"):
        if PANEL_PORT and int(target_port) == PANEL_PORT:
            st.error(f"Refusing to kill the control panel's own port ({PANEL_PORT}). "
                     f"Change the Explorer port or kill a different port.")
        else:
            n = kill_by_port(int(target_port))
            st.toast(f"Killed {n} process(es) on port {int(target_port)}")

    st.markdown("---")
    if st.button("Stop ALL"):
        # Stop services by PID first
        for svc, port in [("core", core_port), ("ucnrr", ucn_port), ("explorer", expl_port)]:
            pid = read_pid(svc)
            if pid:
                kill_pid(pid); clear_pid(svc)
        # Then clear ports, but never kill the control panel port
        for port in [core_port, ucn_port, expl_port]:
            if PANEL_PORT and port == PANEL_PORT:
                continue
            kill_by_port(port)
        st.toast("Stopped Core, UCN/RR, Explorer (panel kept alive)")

st.info("Tip: Start Core → UCN/RR → Explorer. Use **Ping /health** to verify Core before opening Explorer.")