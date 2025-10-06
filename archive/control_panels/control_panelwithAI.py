# control_panelwithAI.py
# ReDNA Control Panel (UCN/RR-aware)
#
# Features
# - Start/Stop Core (uvicorn) with CORE_USE_UCNRR and UCNRR_URL env set
# - Start/Stop UCN/RR (your ucnrr_app.py or any command)
# - Start/Stop Explorer (Streamlit)
# - Ping /health
# - Write Explorer secrets.toml pointing to Core and UCN/RR flags
# - Kill anything on a port
#
# Assumptions
# - This file sits at the repo root that contains:
#     ReDNACoreDemo/            (FastAPI app with app.py)
#     ExplorerFinal/            (Streamlit app)
#     UCN/RR script: ucnrr_app.py (or whatever you use)
# - Python venv already active where streamlit/uvicorn/psutil/requests are installed
#
# If your paths differ, adjust the UI fields under “Paths & Commands”.

import os
import sys
import time
import json
import signal
import socket
import shutil
import psutil
import requests
import subprocess
from pathlib import Path

import streamlit as st

# --------------------------
# Defaults (edit if needed)
# --------------------------
REPO_ROOT = Path(__file__).resolve().parent

DEFAULT_CORE_PORT = 8015
DEFAULT_UCNRR_PORT = 8020
DEFAULT_EXPLORER_PORT = 8502

DEFAULT_CORE_DIR = REPO_ROOT / "ReDNACoreDemo"
DEFAULT_EXPLORER_DIR = REPO_ROOT / "ExplorerFinal"
DEFAULT_UCNRR_CMD = "python ucnrr_app.py --port {port}"  # can be any shell cmd

DEFAULT_HEALTH_PATH = "/health"

# --------------------------
# Helpers
# --------------------------
def is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        return s.connect_ex(("127.0.0.1", port)) == 0

def kill_port(port: int) -> str:
    killed = []
    for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            cons = p.connections(kind="inet")
        except Exception:
            continue
        for c in cons:
            if c.laddr.port == port:
                try:
                    p.terminate()
                    try:
                        p.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        p.kill()
                    killed.append(p.pid)
                except Exception:
                    pass
                break
    return f"Killed {len(killed)} process(es) on {port}: {killed}"

def run_bg(cmd, cwd=None, env=None, name=None):
    # Launch a detached subprocess
    kwargs = dict(
        cwd=str(cwd) if cwd else None,
        env=env if env else os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    proc = subprocess.Popen(cmd, **kwargs)

    # Track in session for Stop buttons
    if name:
        st.session_state.setdefault("procs", {})
        st.session_state["procs"][name] = proc.pid
    return proc

def stop_named(name: str):
    pid = st.session_state.get("procs", {}).get(name)
    if not pid:
        return "Nothing to stop."
    try:
        p = psutil.Process(pid)
        p.terminate()
        try:
            p.wait(2)
        except psutil.TimeoutExpired:
            p.kill()
        return f"Stopped {name} (pid {pid})."
    except psutil.NoSuchProcess:
        return f"{name} already stopped."
    finally:
        st.session_state["procs"].pop(name, None)

def ping_health(base_url: str, path=DEFAULT_HEALTH_PATH, timeout=2.0):
    url = base_url.rstrip("/") + path
    try:
        r = requests.get(url, timeout=timeout)
        ok = r.status_code == 200
        return ok, r.status_code, (r.json() if "application/json" in r.headers.get("content-type","") else r.text)
    except Exception as e:
        return False, None, str(e)

def write_explorer_secrets(explorer_dir: Path, core_url: str, use_ucnrr: bool, ucnrr_url: str):
    target = explorer_dir / ".streamlit" / "secrets.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = [
        f'core_url = "{core_url}"',
        f'use_ucnrr = {"true" if use_ucnrr else "false"}',
        f'ucnrr_url = "{ucnrr_url}"'
    ]
    target.write_text("\n".join(content) + "\n", encoding="utf-8")
    return str(target)

def ensure_packages_msg():
    return (
        "If you see import errors from this panel, install deps in your venv:\n\n"
        "```bash\n"
        "pip install streamlit uvicorn fastapi psutil requests\n"
        "```\n"
    )

# --------------------------
# UI
# --------------------------
st.set_page_config(page_title="ReDNA Control Panel", layout="wide")
st.title("🧬 ReDNA Control Panel")

with st.sidebar:
    st.header("Ports & Options")
    core_port = st.number_input("Core port", 1, 65535, value=DEFAULT_CORE_PORT, step=1)
    ucnrr_port = st.number_input("UCN/RR port", 1, 65535, value=DEFAULT_UCNRR_PORT, step=1)
    explorer_port = st.number_input("Explorer port", 1, 65535, value=DEFAULT_EXPLORER_PORT, step=1)

    use_ucnrr = st.toggle("Use UCN/RR for reconcile", value=True, help="Pass CORE_USE_UCNRR=1 to Core and wire Explorer through UCN/RR.")
    ucnrr_url = st.text_input("UCNRR_URL", value=f"http://127.0.0.1:{ucnrr_port}")

    st.markdown("---")
    st.header("Paths & Commands")
    core_dir = Path(st.text_input("Core working directory", value=str(DEFAULT_CORE_DIR)))
    explorer_dir = Path(st.text_input("Explorer working directory", value=str(DEFAULT_EXPLORER_DIR)))
    ucnrr_cmd_template = st.text_input(
        "UCN/RR start command",
        value=DEFAULT_UCNRR_CMD,
        help="You can change to any script/command. {port} will be replaced with the selected UCN/RR port."
    )

    st.markdown("---")
    st.header("Utilities")
    kill_on = st.number_input("Kill anything on port…", 1, 65535, value=core_port, step=1)
    if st.button("Kill port"):
        st.info(kill_port(int(kill_on)))
    if st.button("Stop ALL"):
        msgs = []
        for key in list(st.session_state.get("procs", {}).keys()):
            msgs.append(stop_named(key))
        st.write("\n".join(msgs) or "No tracked processes.")

st.subheader("Core")

core_url = f"http://127.0.0.1:{core_port}"
cols = st.columns([1, 1, 1, 2])

with cols[0]:
    if st.button("Start Core"):
        # make sure port free
        if is_port_listening(core_port):
            st.warning(f"Port {core_port} is already in use. Try Kill port.")
        else:
            env = os.environ.copy()
            # Wire UCN/RR flag + URL
            env["CORE_USE_UCNRR"] = "1" if use_ucnrr else "0"
            env["UCNRR_URL"] = ucnrr_url
            # Many users had missing httpx/uvicorn; hint in UI if that happens
            try:
                cmd = [
                    sys.executable, "-m", "uvicorn", "app:app",
                    "--host", "127.0.0.1",
                    "--port", str(core_port),
                    "--reload"
                ]
                run_bg(cmd, cwd=core_dir, env=env, name="core")
                time.sleep(0.8)
                ok, code, body = ping_health(core_url)
                if ok:
                    st.success(f"Core up at {core_url}{DEFAULT_HEALTH_PATH} ✓")
                else:
                    st.warning(f"Core started, but health ping failed. Status={code}, body={body}\n\n{ensure_packages_msg()}")
            except Exception as e:
                st.error(f"Failed to start Core: {e}\n\n{ensure_packages_msg()}")

with cols[1]:
    if st.button("Stop Core"):
        st.info(stop_named("core"))

with cols[2]:
    if st.button("Ping /health"):
        ok, code, body = ping_health(core_url)
        if ok:
            st.success(f"OK {code}")
            st.code(json.dumps(body, indent=2) if isinstance(body, dict) else str(body))
        else:
            st.error(f"No response: {body}")

with cols[3]:
    ok, code, body = ping_health(core_url)
    if ok:
        st.markdown(f"**Health:** 🟢 OK — [{core_url}{DEFAULT_HEALTH_PATH}]({core_url}{DEFAULT_HEALTH_PATH})")
    else:
        st.markdown(f"**Health:** 🔴 Not reachable — {body}")

st.markdown("---")

st.subheader("UCN/RR")
ucnrr_cols = st.columns([1, 1, 2])

with ucnrr_cols[0]:
    if st.button("Start UCN/RR"):
        if is_port_listening(ucnrr_port):
            st.warning(f"Port {ucnrr_port} is already in use.")
        else:
            try:
                cmd = ucnrr_cmd_template.format(port=ucnrr_port)
                run_bg(cmd if os.name == "nt" else ["bash", "-lc", cmd], cwd=REPO_ROOT, name="ucnrr")
                time.sleep(0.6)
                # Best-effort check (assume health also on /health)
                ok, code, body = ping_health(f"http://127.0.0.1:{ucnrr_port}")
                if ok:
                    st.success(f"UCN/RR running on 127.0.0.1:{ucnrr_port} ✓")
                else:
                    st.info("UCN/RR started; if no /health endpoint, this ping may show an error which is okay.")
            except Exception as e:
                st.error(f"Failed to start UCN/RR: {e}")

with ucnrr_cols[1]:
    if st.button("Stop UCN/RR"):
        st.info(stop_named("ucnrr"))

with ucnrr_cols[2]:
    st.write(f"Command: `{ucnrr_cmd_template.format(port=ucnrr_port)}`")

st.markdown("---")

st.subheader("Explorer")
expl_cols = st.columns([1, 1, 2, 2])

def write_secrets_and_show():
    p = write_explorer_secrets(explorer_dir, core_url, use_ucnrr, ucnrr_url)
    st.success(f"Wrote Explorer secrets → {p}")
    st.code(Path(p).read_text())

with expl_cols[0]:
    if st.button("Start Explorer"):
        if is_port_listening(explorer_port):
            st.warning(f"Port {explorer_port} is already in use.")
        else:
            # Always (re)write secrets before launching
            write_secrets_and_show()
            try:
                cmd = [
                    "streamlit", "run", "ExplorerFinal.py",
                    "--server.port", str(explorer_port),
                    "--server.headless", "true",
                ]
                run_bg(cmd, cwd=explorer_dir, name="explorer")
                time.sleep(1.0)
                st.success(f"Explorer starting on http://127.0.0.1:{explorer_port}")
            except Exception as e:
                st.error(f"Failed to start Explorer: {e}\n\n{ensure_packages_msg()}")

with expl_cols[1]:
    if st.button("Stop Explorer"):
        st.info(stop_named("explorer"))

with expl_cols[2]:
    st.link_button(f"Open Explorer (:{explorer_port})", f"http://127.0.0.1:{explorer_port}", disabled=not is_port_listening(explorer_port))

with expl_cols[3]:
    if st.button("Write Explorer secrets.toml"):
        write_secrets_and_show()

st.markdown("> Tip: **Start Core → (optional) Start UCN/RR → Start Explorer.** If you enable the UCN/RR toggle, both Core and Explorer are automatically configured for you.")