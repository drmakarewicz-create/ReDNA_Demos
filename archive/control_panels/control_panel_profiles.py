# control_panel_profiles.py
# One-click runner for Core + (optional) UCN/RR + Explorer, with env injection.
# Keep this side-by-side with your existing control_panel.py until you're happy.

import os, sys, json, time, signal, subprocess, pathlib, textwrap
from typing import Optional
import requests
import streamlit as st

HERE = pathlib.Path(__file__).resolve().parent

# --- Configuration defaults (edit if your repo folders differ) ---
CORE_DIR       = (HERE / "ReDNACoreDemo").resolve()        # folder with app.py
EXPLORER_DIR   = (HERE / "ExplorerFinal").resolve()        # folder with explorer_final.py
EXPLORER_FILE  = "explorer_final.py"                       # Streamlit entrypoint
UCNRR_START_CMD= "python ucnrr_app.py --port {port}"       # If you have a runner; else leave blank

# --- Helpers ------------------------------------------------------
def kill_port(port: int):
    try:
        if sys.platform == "darwin" or sys.platform.startswith("linux"):
            # lsof + kill
            out = subprocess.run(["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True)
            pids = [p.strip() for p in out.stdout.splitlines() if p.strip()]
            for pid in pids:
                try: os.kill(int(pid), signal.SIGKILL)
                except Exception: pass
        else:
            # Windows (best-effort)
            subprocess.run(["powershell", "-c", f"Get-NetTCPConnection -LocalPort {port} | ForEach-Object {{$_.OwningProcess}} | Get-Process | Stop-Process -Force"], check=False)
    except Exception as e:
        st.toast(f"Kill port {port}: {e}")

def ping_health(base_url: str, timeout=2.0) -> tuple[bool,str]:
    try:
        r = requests.get(base_url.rstrip("/") + "/health", timeout=timeout)
        r.raise_for_status()
        return True, r.text
    except Exception as e:
        return False, str(e)

def start_core(core_port: int, use_ucnrr: bool, ucnrr_url: str, reload: bool=True, extra_env: Optional[dict]=None):
    env = os.environ.copy()
    env["CORE_USE_UCNRR"] = "1" if use_ucnrr else "0"
    if use_ucnrr:
        env["UCNRR_URL"] = ucnrr_url
    if extra_env:
        env.update(extra_env)

    args = ["python", "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(core_port)]
    if reload: args.append("--reload")

    return subprocess.Popen(args, cwd=str(CORE_DIR), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def start_ucnrr(ucnrr_port: int, cmd_template: str):
    if not cmd_template.strip():
        return None
    cmd = cmd_template.format(port=ucnrr_port)
    # Start via shell to allow arbitrary command strings
    return subprocess.Popen(cmd, cwd=str(HERE), env=os.environ.copy(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

def start_explorer(explorer_port: int, core_url: str):
    # Pass CORE_URL to Streamlit so Explorer picks it up immediately
    env = os.environ.copy()
    env["CORE_URL"] = core_url
    return subprocess.Popen(
        ["streamlit", "run", EXPLORER_FILE, "--server.port", str(explorer_port), "--server.headless", "true"],
        cwd=str(EXPLORER_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )

def write_explorer_secrets(core_url: str, password: str=""):
    secrets_dir = EXPLORER_DIR / ".streamlit"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    secrets = textwrap.dedent(f"""
        CORE_URL = "{core_url}"
        CORE_PASSWORD = "{password}"
    """).strip() + "\n"
    (secrets_dir / "secrets.toml").write_text(secrets, encoding="utf-8")
    return str(secrets_dir / "secrets.toml")

def tail(proc: subprocess.Popen, n=20) -> str:
    if not proc or not proc.stdout: return ""
    try:
        out = proc.stdout.readlines()[-n:]
        return "".join(l.decode("utf-8", errors="ignore") for l in out)
    except Exception:
        return ""

# --- UI -----------------------------------------------------------
st.set_page_config(page_title="ReDNA Control Panel (Profiles)", layout="wide")
st.title("🧬 ReDNA Control Panel")

with st.sidebar:
    st.caption("Ports & Options")
    core_port = st.number_input("Core port", 1, 65535, 8015, step=1)
    ucn_port  = st.number_input("UCN/RR port", 1, 65535, 8020, step=1)
    exp_port  = st.number_input("Explorer port", 1, 65535, 8502, step=1)

    use_ucnrr = st.toggle("Use UCN/RR for reconcile", value=False, help="If ON, Control Panel starts Core with CORE_USE_UCNRR=1 and UCNRR_URL set.")
    ucnrr_url = st.text_input("UCNRR_URL", value=f"http://127.0.0.1:{ucn_port}")
    ucnrr_cmd = st.text_input("UCN/RR start command", value=UCNRR_START_CMD, help="Leave blank if you start UCN/RR yourself.")

    st.divider()
    st.caption("Explorer")
    exp_pw = st.text_input("Explorer password (if any)", value="", type="password")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔧 Kill ports", help="Kills Core/UCN-RR/Explorer ports"):
        for p in (core_port, ucn_port, exp_port):
            kill_port(int(p))
        st.success("Kill requested for Core/UCN-RR/Explorer ports.")

with col2:
    if st.button("🟢 Start All"):
        # Ensure clean start
        for p in (core_port, ucn_port, exp_port):
            kill_port(int(p))

        # UCN/RR first (if used)
        ucn_proc = None
        if use_ucnrr:
            ucn_proc = start_ucnrr(int(ucn_port), ucnrr_cmd)
            time.sleep(0.8)

        core_proc = start_core(int(core_port), use_ucnrr, ucnrr_url, reload=True)
        time.sleep(1.0)

        core_ok, msg = ping_health(f"http://127.0.0.1:{core_port}")
        if not core_ok:
            st.error(f"Core /health not responding: {msg}")
        else:
            st.success("Core is up ✅")

        # Write Explorer secrets + start Explorer
        secrets_path = write_explorer_secrets(f"http://127.0.0.1:{core_port}", password=exp_pw)
        st.info(f"Explorer secrets written → {secrets_path}")
        exp_proc = start_explorer(int(exp_port), f"http://127.0.0.1:{core_port}")
        st.success("Explorer starting ✅ (open its tab from your other panel, or http://127.0.0.1:{exp_port})")

with col3:
    if st.button("🛑 Stop All"):
        for p in (core_port, ucn_port, exp_port):
            kill_port(int(p))
        st.success("Stop requested.")

st.divider()
st.subheader("Core")
core_url = f"http://127.0.0.1:{core_port}"
ok, detail = ping_health(core_url)
st.write(f"Health: {'🟢 OK' if ok else '🔴 down'} — {core_url}/health")
if not ok:
    st.code(detail, language="text")

colh1, colh2 = st.columns(2)
with colh1:
    if st.button("Ping /health"):
        ok, detail = ping_health(core_url)
        if ok: st.success(f"/health OK: {detail[:200]}")
        else:  st.error(detail)

with colh2:
    if st.button("Write Explorer secrets.toml"):
        p = write_explorer_secrets(core_url, password=exp_pw)
        st.success(f"Wrote {p}")

st.caption("Tip: Start All → then open Explorer. If you toggle 'Use UCN/RR', Start All will pass the env flags to Core automatically.")