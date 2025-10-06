#!/usr/bin/env python3
# ai_control_panel.py
# A tiny web control panel to manage ReDNA Core + UCN/RR with Llama3 (Ollama).
# Run:  python ai_control_panel.py   -> open http://127.0.0.1:8020

from __future__ import annotations

import os, sys, json, time, signal, subprocess, threading, shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# -------------------------
# Editable defaults (paths)
# -------------------------
ROOT           = Path(os.path.expanduser("~/Documents/ReDNA_Demos")).resolve()
CORE_DIR       = ROOT / "ReDNACoreDemo"
UCNRR_DIR      = ROOT / "UCN_RR_Demo"
VENV_BIN       = ROOT / ".venv" / "bin"         # adjust if your venv differs
UVICORN_BIN    = VENV_BIN / "uvicorn"

# Service config
CORE_HOST, CORE_PORT   = "0.0.0.0", 8015
UCNRR_HOST, UCNRR_PORT = "0.0.0.0", 8011

# Control Panel port
PANEL_PORT     = 8020

# Logs
LOGS_DIR       = ROOT / "control_panel_logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
CORE_LOG       = LOGS_DIR / "core.log"
UCNRR_LOG      = LOGS_DIR / "ucnrr.log"
PANEL_LOG      = LOGS_DIR / "panel.log"

# PID tracking (so we can stop cleanly)
PIDS_FILE      = LOGS_DIR / "pids.json"

# Llama3 (Ollama) defaults
DEFAULT_ENV = {
    "LLM_PROVIDER": "llama",
    "LLM_MODEL": "llama3",
    "LLM_BASE_URL": "http://127.0.0.1:11434",
    "LLM_API_KEY": "dummy-key",

    # Prompts dir (edit if your prompts live elsewhere)
    "PROMPTS_DIR": str((ROOT / "prompts")),

    # UCN/RR prompt files
    "UCN_PROMPT_MAIN": str((ROOT / "prompts" / "ucn_rr_ai.md")),
    "UCN_PROMPT_CONF": str((ROOT / "prompts" / "ucn_rr_confidence.md")),

    # Core prompt files
    "CORE_PROMPT_MAIN": str((ROOT / "prompts" / "core_ai.md")),
    "CORE_PROMPT_PROP": str((ROOT / "prompts" / "core_ai_propagation.md")),

    # Heuristic backstop (you can flip this in UI)
    "UCNRR_USE_MIN_HEURISTICS": "false",

    # Explicit data dirs (optional; Core already defaults to ./data)
    "CORE_DATA_DIR": str(CORE_DIR / "data"),
    "UCNRR_DATA_DIR": str(UCNRR_DIR / "data"),
    "CORE_BASE": f"http://127.0.0.1:{CORE_PORT}",
}

# -------------------------
# Process helpers
# -------------------------
def _load_pids() -> Dict[str, int]:
    if PIDS_FILE.exists():
        try:
            return json.loads(PIDS_FILE.read_text())
        except Exception:
            pass
    return {}

def _save_pids(pids: Dict[str, int]) -> None:
    PIDS_FILE.write_text(json.dumps(pids, indent=2))

def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def _kill_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass

def _merge_env(extra: Dict[str,str]) -> Dict[str,str]:
    env = os.environ.copy()
    for k, v in DEFAULT_ENV.items():
        env.setdefault(k, v)
    for k, v in (extra or {}).items():
        env[k] = v
    return env

def _launch_service(name: str, cwd: Path, module: str, app_ref: str,
                    host: str, port: int, log_file: Path,
                    overrides: Optional[Dict[str,str]] = None) -> Tuple[bool, str]:
    """
    Launch a uvicorn service in the background, isolated from the panel's process group.
    """
    pids = _load_pids()
    if name in pids and _is_running(pids[name]):
        return False, f"{name} already running (pid {pids[name]})."

    log_file.parent.mkdir(parents=True, exist_ok=True)
    fout = open(log_file, "a", buffering=1)

    cmd = [
        str(UVICORN_BIN),
        f"{app_ref}",
        "--host", host,
        "--port", str(port),
        # Uncomment next line if you want extra logging while debugging exits:
        # "--log-level", "debug",
        # No --reload to avoid cross-service restarts
        # Explicit app-dir to limit import scanning to each service folder
        "--app-dir", str(cwd),
        # If you ever re-enable reload, also add:
        # "--reload-dir", str(cwd),
        # "--reload-exclude", str(LOGS_DIR),
    ]

    env = _merge_env(overrides or {})
    # Hard-disable any watchfiles side-effects and keep logs unbuffered
    env["WATCHFILES_DISABLE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    # Launch detached so signals to the panel don't hit the services
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=fout,
        stderr=fout,
        start_new_session=True,   # 👈 important
        close_fds=True,           # extra isolation on macOS
    )

    pids[name] = proc.pid
    _save_pids(pids)
    return True, f"{name} started (pid {proc.pid})."

def _stop_service(name: str) -> Tuple[bool, str]:
    pids = _load_pids()
    pid = pids.get(name)
    if not pid:
        return False, f"{name} not running."
    if _is_running(pid):
        _kill_pid(pid)
        time.sleep(0.5)
        if _is_running(pid):
            os.kill(pid, signal.SIGKILL)
    pids.pop(name, None)
    _save_pids(pids)
    return True, f"{name} stopped."

def _tail(path: Path, n: int=200) -> str:
    if not path.exists():
        return "(no log yet)"
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception as e:
        return f"(error reading log: {e})"

# -------------------------
# HTTP helpers
# -------------------------
def _html_page(body: str, title: str="ReDNA Control Panel") -> HTMLResponse:
    html = f"""<!doctype html><html><head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
h1,h2,h3 {{ margin: 8px 0; }}
section {{ margin: 20px 0; padding: 12px; border: 1px solid #eee; border-radius: 10px; }}
label {{ display: inline-block; width: 220px; }}
input[type=text], input[type=number] {{ width: 340px; padding: 6px; }}
button {{ padding: 8px 14px; margin-right: 8px; }}
pre {{ background: #fafafa; padding: 12px; overflow: auto; border-radius: 8px; }}
small {{ color: #666; }}
.code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Courier New", monospace; }}
.ok {{ color: #0a0; }}
.bad {{ color: #a00; }}
.kv {{ margin: 2px 0; }}
.grid {{ display: grid; grid-template-columns: 220px 1fr; gap: 8px 16px; align-items:center; }}
hr {{ border: none; border-top: 1px solid #eee; margin: 16px 0; }}
</style>
</head><body>
{body}
</body></html>"""
    return HTMLResponse(html)

def _row(k, v): return f'<div class="kv"><label class="code">{k}</label><span class="code">{v}</span></div>'

# -------------------------
# App + routes
# -------------------------
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    pids = _load_pids()
    core_running   = "core"  in pids and _is_running(pids["core"])
    ucnrr_running  = "ucnrr" in pids and _is_running(pids["ucnrr"])

    body = f"""
    <h1>🧭 ReDNA AI Control Panel</h1>

    <section>
      <h2>Quick Actions</h2>
      <form method="post" action="/env/llama3_default"><button>Set Llama3 (Ollama) Env</button></form>
      <form method="post" action="/heuristics/toggle?value=true"><button>Enable Heuristics</button></form>
      <form method="post" action="/heuristics/toggle?value=false"><button>Disable Heuristics</button></form>
    </section>

    <section>
      <h2>Services</h2>
      <div class="grid">
        <label>Core ({CORE_HOST}:{CORE_PORT})</label>
        <div>
          <form style="display:inline" method="post" action="/service/start/core"><button>Start Core</button></form>
          <form style="display:inline" method="post" action="/service/stop/core"><button>Stop Core</button></form>
          <a href="/health/core">Check Health</a>
          <span class="{ 'ok' if core_running else 'bad' }">[{ 'RUNNING' if core_running else 'STOPPED' }]</span>
        </div>

        <label>UCN/RR ({UCNRR_HOST}:{UCNRR_PORT})</label>
        <div>
          <form style="display:inline" method="post" action="/service/start/ucnrr"><button>Start UCN/RR</button></form>
          <form style="display:inline" method="post" action="/service/stop/ucnrr"><button>Stop UCN/RR</button></form>
          <a href="/health/ucnrr">Check Health</a>
          <span class="{ 'ok' if ucnrr_running else 'bad' }">[{ 'RUNNING' if ucnrr_running else 'STOPPED' }]</span>
        </div>
      </div>
      <p><small>Logs: <a href="/logs/core">Core log</a> · <a href="/logs/ucnrr">UCN/RR log</a> · <a href="/logs/panel">Panel log</a></small></p>
    </section>

    <section>
      <h2>Harness (Golden Path)</h2>
      <form method="post" action="/harness/run">
        <label>User ID</label><input name="user_id" type="text" value="harness_user"/><br/><br/>
        <button>Run 4 Tests</button>
      </form>
      <div><small>Runs: height ~6ft, husband 25 years, dark brown eyes, red hair+balder cue.</small></div>
    </section>

    <section>
      <h2>Resolved Viewer</h2>
      <form method="get" action="/resolved/view">
        <label>User ID</label><input name="user_id" type="text" value="harness_user"/>
        <button>View</button>
      </form>
      <form method="post" action="/user/reset" onsubmit="return confirm('Really wipe this user in both services?');">
        <label>User ID</label><input name="user_id" type="text" value="harness_user"/>
        <button>Reset (wipe data)</button>
      </form>
      <div><small>Flat rows endpoint also available: <code>/resolved/flat?user_id=&lt;id&gt;</code></small></div>
    </section>

    <section>
      <h2>Current Defaults</h2>
      {_row("ROOT", ROOT)}
      {_row("CORE_DIR", CORE_DIR)}
      {_row("UCNRR_DIR", UCNRR_DIR)}
      {_row("VENV_BIN", VENV_BIN)}
      {_row("UCNRR_USE_MIN_HEURISTICS", DEFAULT_ENV.get("UCNRR_USE_MIN_HEURISTICS"))}
      {_row("LLM_PROVIDER", DEFAULT_ENV.get("LLM_PROVIDER"))}
      {_row("LLM_MODEL", DEFAULT_ENV.get("LLM_MODEL"))}
      {_row("LLM_BASE_URL", DEFAULT_ENV.get("LLM_BASE_URL"))}
      {_row("PROMPTS_DIR", DEFAULT_ENV.get("PROMPTS_DIR"))}
    </section>
    """
    return _html_page(body)

@app.post("/env/llama3_default")
def env_llama3_default():
    # this just ensures our DEFAULT_ENV is used on next launch; nothing to do here since we merge on spawn
    return RedirectResponse("/", status_code=302)

@app.post("/heuristics/toggle")
def heuristics_toggle(value: str = "true"):
    DEFAULT_ENV["UCNRR_USE_MIN_HEURISTICS"] = "true" if value.lower() in ("1","true","yes","on") else "false"
    return RedirectResponse("/", status_code=302)

@app.post("/service/start/{svc}")
def start_service(svc: str):
    if svc == "core":
        ok, msg = _launch_service(
            name="core",
            cwd=CORE_DIR,
            module="app",
            app_ref="app:app",
            host=CORE_HOST, port=CORE_PORT,
            log_file=CORE_LOG,
            overrides={}  # inherit DEFAULT_ENV
        )
    elif svc == "ucnrr":
        ok, msg = _launch_service(
            name="ucnrr",
            cwd=UCNRR_DIR,
            module="ucnrr_app",
            app_ref="ucnrr_app:app",
            host=UCNRR_HOST, port=UCNRR_PORT,
            log_file=UCNRR_LOG,
            overrides={}  # inherit DEFAULT_ENV incl heuristics toggle
        )
    else:
        return PlainTextResponse("unknown service", status_code=400)
    return RedirectResponse("/", status_code=302)

@app.post("/service/stop/{svc}")
def stop_service(svc: str):
    if svc not in ("core","ucnrr"):
        return PlainTextResponse("unknown service", status_code=400)
    ok, msg = _stop_service(svc)
    return RedirectResponse("/", status_code=302)

@app.get("/health/{svc}")
def health_proxy(svc: str):
    import requests
    if svc == "core":
        url = f"http://127.0.0.1:{CORE_PORT}/health"
    elif svc == "ucnrr":
        url = f"http://127.0.0.1:{UCNRR_PORT}/health"
    else:
        return PlainTextResponse("unknown service", status_code=400)
    try:
        r = requests.get(url, timeout=5)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as e:
        return PlainTextResponse(f"health error: {e}", status_code=500)

@app.get("/logs/{svc}")
def logs_view(svc: str):
    if svc == "core":   text = _tail(CORE_LOG)
    elif svc == "ucnrr": text = _tail(UCNRR_LOG)
    elif svc == "panel": text = _tail(PANEL_LOG)
    else: return PlainTextResponse("unknown log", status_code=400)
    return PlainTextResponse(text, status_code=200)

# -------------------------
# Harness runner
# -------------------------
TESTS = [
    ("I'm around 6 feet.", "PaDNA.BodyDNA.Height"),
    ("I've been a husband for 25 years.", "SocDNA.Relationship"),
    ("My eyes are dark brown.", "Eye"),
    ("The little bit of hair I have left is red.", "Hair"),
]

def run_harness_once(user_id: str) -> Dict[str, Any]:
    import requests, json, time as _t

    results = []
    for text, frag in TESTS:
        payload = {
            "schema_version": "explorer.text/1.0",
            "user_id": user_id,
            "text": text,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provenance": {"actor":"user","source":"panel"}
        }
        r = requests.post(f"http://127.0.0.1:{UCNRR_PORT}/ingest_text", json=payload, timeout=10)
        ucnrr_resp = (r.status_code, r.text)
        _t.sleep(1.5)
        r2 = requests.get(f"http://127.0.0.1:{8015}/resolved/{user_id}", timeout=10)
        resolved = r2.json() if r2.status_code == 200 else {}
        found = frag in json.dumps(resolved.get("resolved", {}))
        results.append({
            "text": text, "expected_fragment": frag,
            "ucnrr_status": r.status_code, "ucnrr_resp": r.text[:300],
            "core_status": r2.status_code, "pass": bool(found)
        })
    return {"user_id": user_id, "results": results}

@app.post("/harness/run", response_class=HTMLResponse)
def harness_run(user_id: str = Form(...)):
    res = run_harness_once(user_id)
    rows = ""
    for r in res["results"]:
        rows += f"<tr><td>{r['text']}</td><td class='code'>{r['expected_fragment']}</td><td>{r['ucnrr_status']}</td><td class='code'>{r['ucnrr_resp']}</td><td>{r['core_status']}</td><td>{'✅' if r['pass'] else '❌'}</td></tr>"
    body = f"""
    <h1>Harness Results</h1>
    <p>User: <b>{res['user_id']}</b></p>
    <table border="1" cellspacing="0" cellpadding="6">
      <tr><th>Text</th><th>Expect</th><th>UCNRR</th><th>UCNRR resp (trunc)</th><th>Core</th><th>Pass?</th></tr>
      {rows}
    </table>
    <p><a href="/">Back</a></p>
    """
    return _html_page(body, title="Harness Results")

# -------------------------
# Resolved viewer + flat
# -------------------------
@app.get("/resolved/view", response_class=HTMLResponse)
def resolved_view(user_id: str = "harness_user"):
    import requests
    url = f"http://127.0.0.1:{CORE_PORT}/resolved/{user_id}"
    try:
        r = requests.get(url, timeout=6)
        doc = r.json() if r.status_code == 200 else {}
        resolved = doc.get("resolved", {})
        items = "".join([f"<tr><td class='code'>{k}</td><td class='code'>{v.get('resolved_value', v)}</td><td>{v.get('ucn','')}</td></tr>" for k, v in sorted(resolved.items())])
        table = f"<table border='1' cellspacing='0' cellpadding='6'><tr><th>Trait</th><th>Value</th><th>UCN</th></tr>{items}</table>"
        body = f"<h1>Resolved for {user_id}</h1>{table}<p><a href='/'>Back</a></p>"
        return _html_page(body, title=f"Resolved: {user_id}")
    except Exception as e:
        return _html_page(f"<h1>Error</h1><pre>{e}</pre><p><a href='/'>Back</a></p>")

@app.get("/resolved/flat")
def resolved_flat(user_id: str = "harness_user"):
    import requests
    url = f"http://127.0.0.1:{CORE_PORT}/resolved/flat/{user_id}"
    try:
        r = requests.get(url, timeout=6)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)

# -------------------------
# Reset (wipe) a user
# -------------------------
@app.post("/user/reset")
def user_reset(user_id: str = Form(...)):
    # Delete user folders from both services
    core_user  = Path(DEFAULT_ENV["CORE_DATA_DIR"])   / "users" / user_id
    ucnrr_user = Path(DEFAULT_ENV["UCNRR_DATA_DIR"]) / "users" / user_id
    for p in (core_user, ucnrr_user):
        try:
            if p.exists():
                shutil.rmtree(p)
        except Exception:
            pass
    return RedirectResponse("/", status_code=302)

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    # simple self-log
    with open(PANEL_LOG, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Control panel started on {PANEL_PORT}\n")
    uvicorn.run("ai_control_panel:app", host="127.0.0.1", port=PANEL_PORT, reload=False)