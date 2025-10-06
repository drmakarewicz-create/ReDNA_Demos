#!/usr/bin/env python3
# ai_control_panel_agent.py
# Agent-only AI Control Panel for ReDNA (no process management).
# Use Control Panel Plus to run Core (8015) and UCN/RR (8011).
# This panel manages LLM settings (Llama3/Ollama), probes server/model,
# generates an env script for Plus, sends text, runs harness, views traits, and can wipe test users.

from __future__ import annotations

import os, json, time, shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

# -----------------------------------------------------------------------------
# Config — adjust to your setup
# -----------------------------------------------------------------------------
ROOT            = Path(os.path.expanduser("~/Documents/ReDNA_Demos")).resolve()
CORE_DIR        = ROOT / "ReDNACoreDemo"
UCNRR_DIR       = ROOT / "UCN_RR_Demo"
CORE_PORT       = 8015
UCNRR_PORT      = 8011
PANEL_PORT      = 8020

# Optional explicit data dirs (used for Reset)
CORE_DATA_DIR   = os.getenv("CORE_DATA_DIR", str(CORE_DIR / "data"))
UCNRR_DATA_DIR  = os.getenv("UCNRR_DATA_DIR", str(UCNRR_DIR / "data"))

# LLM settings file + default values
LLM_SETTINGS_PATH = ROOT / "llm_settings.json"
DEFAULT_LLM = {
    "provider": "ollama",                          # descriptive, not sent to servers; UCN/RR/Core read env they were started with
    "model": "llama3",                             # e.g., "llama3", "llama3:8b-instruct"
    "base_url": "http://127.0.0.1:11434",          # Ollama default
    "api_key": "dummy",                            # Ollama doesn't need it, but UCN/RR/Core expect a string
    "prompts_dir": str(ROOT / "prompts"),
    "ucn_prompt_main": str(ROOT / "prompts" / "ucn_rr_ai.md"),
    "ucn_prompt_conf": str(ROOT / "prompts" / "ucn_rr_confidence.md"),
    "core_prompt_main": str(ROOT / "prompts" / "core_ai.md"),
    "core_prompt_prop": str(ROOT / "prompts" / "core_ai_propagation.md"),
}

# Golden-path tests
TESTS = [
    ("I'm around 6 feet.", "PaDNA.BodyDNA.Height"),
    ("I've been a husband for 25 years.", "SocDNA.Relationship"),
    ("My eyes are dark brown.", "Eye"),
    ("The little bit of hair I have left is red.", "Hair"),
]

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _read_llm() -> Dict[str, Any]:
    try:
        if LLM_SETTINGS_PATH.exists():
            return {**DEFAULT_LLM, **json.loads(LLM_SETTINGS_PATH.read_text())}
    except Exception:
        pass
    return DEFAULT_LLM.copy()

def _write_llm(cfg: Dict[str, Any]) -> None:
    LLM_SETTINGS_PATH.write_text(json.dumps(cfg, indent=2))

def _html_page(body: str, title: str="ReDNA AI Control Panel") -> HTMLResponse:
    html = f"""<!doctype html><html><head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
h1,h2,h3 {{ margin: 8px 0; }}
section {{ margin: 20px 0; padding: 12px; border: 1px solid #eee; border-radius: 10px; }}
label {{ display: inline-block; width: 220px; }}
input[type=text] {{ width: 380px; padding: 6px; }}
textarea {{ width: 100%; height: 110px; padding: 8px; }}
button {{ padding: 8px 14px; margin-right: 8px; }}
pre {{ background: #fafafa; padding: 12px; overflow: auto; border-radius: 8px; }}
small {{ color: #666; }}
.code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Courier New", monospace; }}
.grid {{ display: grid; grid-template-columns: 220px 1fr; gap: 8px 16px; align-items:center; }}
.badge {{ padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
.ok {{ background:#e8f7ed; color:#0a6; }}
.warn {{ background:#fff7e6; color:#a66; }}
.bad {{ background:#fdecea; color:#a00; }}
table {{ border-collapse: collapse; }}
td, th {{ border: 1px solid #eee; padding: 6px 8px; }}
</style>
</head><body>
{body}
</body></html>"""
    return HTMLResponse(html)

def _health_ok(port: int) -> Tuple[bool, Dict[str,Any]]:
    import requests
    try:
        r = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
        j = r.json() if r.headers.get("content-type","").startswith("application/json") else {"_raw": r.text}
        return (r.status_code == 200 and isinstance(j, dict) and j.get("ok") is True), j
    except Exception as e:
        return False, {"error": str(e)}

def _post_ucnrr_ingest(user_id: str, text: str) -> Tuple[int, str]:
    import requests
    payload = {
        "schema_version": "explorer.text/1.0",
        "user_id": user_id,
        "text": text,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provenance": {"actor": "user", "source": "ai-panel"}
    }
    r = requests.post(f"http://127.0.0.1:{UCNRR_PORT}/ingest_text", json=payload, timeout=10)
    return r.status_code, r.text

def _get_core_resolved(user_id: str) -> Tuple[int, Dict[str,Any]]:
    import requests
    r = requests.get(f"http://127.0.0.1:{CORE_PORT}/resolved/{user_id}", timeout=10)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text}

def _get_core_resolved_flat(user_id: str) -> Tuple[int, Dict[str,Any]]:
    import requests
    r = requests.get(f"http://127.0.0.1:{CORE_PORT}/resolved/flat/{user_id}", timeout=10)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text}

def _contains_fragment(resolved_doc: Dict[str,Any], fragment: str) -> bool:
    if not isinstance(resolved_doc, dict): return False
    resolved_map = resolved_doc.get("resolved", {})
    try:
        blob = json.dumps(resolved_map, ensure_ascii=False)
    except Exception:
        blob = str(resolved_map)
    return fragment in blob

def _reset_user(user_id: str) -> None:
    for base in (UCNRR_DATA_DIR, CORE_DATA_DIR):
        user_path = Path(base) / "users" / user_id
        try:
            if user_path.exists():
                shutil.rmtree(user_path)
        except Exception:
            pass

# ---- Ollama-specific probes ----
def _ollama_tags(base_url: str) -> Tuple[bool, Dict[str,Any]]:
    import requests
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=3)
        j = r.json()
        return (r.status_code == 200 and "models" in j), j
    except Exception as e:
        return False, {"error": str(e)}

def _ollama_has_model(tags_json: Dict[str,Any], model_name: str) -> bool:
    try:
        models = tags_json.get("models", [])
        wanted = model_name.strip().lower()
        for m in models:
            if str(m.get("name","")).lower() == wanted:
                return True
    except Exception:
        pass
    return False

def _make_env_script(cfg: Dict[str,Any]) -> Path:
    path = ROOT / "set_env_llama3.sh"
    lines = [
        "#!/usr/bin/env bash",
        "# Auto-generated by AI Control Panel (Agent)",
        f'export LLM_PROVIDER=llama',
        f'export LLM_MODEL="{cfg["model"]}"',
        f'export LLM_BASE_URL="{cfg["base_url"]}"',
        f'export LLM_API_KEY="{cfg["api_key"]}"',
        f'export PROMPTS_DIR="{cfg["prompts_dir"]}"',
        f'export UCN_PROMPT_MAIN="{cfg["ucn_prompt_main"]}"',
        f'export UCN_PROMPT_CONF="{cfg["ucn_prompt_conf"]}"',
        f'export CORE_PROMPT_MAIN="{cfg["core_prompt_main"]}"',
        f'export CORE_PROMPT_PROP="{cfg["core_prompt_prop"]}"',
        '# Optional safety while stabilizing:',
        '# export UCNRR_USE_MIN_HEURISTICS=true',
        "",
        'echo "Llama3 env exported. Start services in this shell to apply settings."'
    ]
    path.write_text("\n".join(lines) + "\n")
    try:
        os.chmod(path, 0o755)
    except Exception:
        pass
    return path

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(title="ReDNA AI Control Panel (Agent)", version="1.1.0")

@app.get("/", response_class=HTMLResponse)
def home():
    cfg = _read_llm()
    core_ok, core_health   = _health_ok(CORE_PORT)
    ucnrr_ok, ucnrr_health = _health_ok(UCNRR_PORT)

    # statuses from services (to see if they picked up env at launch)
    core_model  = (core_health or {}).get("model")
    core_prov   = (core_health or {}).get("provider")
    u_model     = (ucnrr_health or {}).get("model")
    u_prov      = (ucnrr_health or {}).get("provider")

    # health-based badges for services
    services_html = f"""
      <div class="grid">
        <label>Core (:{CORE_PORT})</label>
        <div>
          <span class="badge {'ok' if core_ok else 'bad'}">{'RUNNING' if core_ok else 'STOPPED'}</span>
          &nbsp; <a href="/health/core">View health</a>
          &nbsp; <small>provider=<b>{core_prov}</b>, model=<b>{core_model}</b></small>
        </div>
        <label>UCN/RR (:{UCNRR_PORT})</label>
        <div>
          <span class="badge {'ok' if ucnrr_ok else 'bad'}">{'RUNNING' if ucnrr_ok else 'STOPPED'}</span>
          &nbsp; <a href="/health/ucnrr">View health</a>
          &nbsp; <small>provider=<b>{u_prov}</b>, model=<b>{u_model}</b></small>
        </div>
      </div>
      <p><small>Processes are managed by Control Panel Plus. This panel does not start/stop servers.</small></p>
    """

    # LLM config form
    llm_html = f"""
      <form method="post" action="/llm/save">
        <div class="grid">
          <label>Provider (label)</label><input type="text" name="provider" value="{cfg['provider']}"/>
          <label>Model</label><input type="text" name="model" value="{cfg['model']}"/>
          <label>Base URL</label><input type="text" name="base_url" value="{cfg['base_url']}"/>
          <label>API Key</label><input type="text" name="api_key" value="{cfg['api_key']}"/>
          <label>Prompts Dir</label><input type="text" name="prompts_dir" value="{cfg['prompts_dir']}"/>
          <label>UCN Prompt (main)</label><input type="text" name="ucn_prompt_main" value="{cfg['ucn_prompt_main']}"/>
          <label>UCN Prompt (conf)</label><input type="text" name="ucn_prompt_conf" value="{cfg['ucn_prompt_conf']}"/>
          <label>Core Prompt (main)</label><input type="text" name="core_prompt_main" value="{cfg['core_prompt_main']}"/>
          <label>Core Prompt (prop)</label><input type="text" name="core_prompt_prop" value="{cfg['core_prompt_prop']}"/>
        </div>
        <p>
          <button>Save LLM Settings</button>
          <a href="/llm/probe">Probe Llama Server</a>
          <a href="/llm/make_env">Generate set_env_llama3.sh</a>
        </p>
        <small>After saving, re-launch services from Control Panel Plus with <code>source set_env_llama3.sh</code> so Core/UCN/RR inherit these env vars.</small>
      </form>
    """

    # Integration check badges: do services match saved settings?
    def badge(ok: bool) -> str:
        return f'<span class="badge {"ok" if ok else "warn"}">{"MATCH" if ok else "DIFF"}</span>'
    u_match = (u_model == cfg["model"])
    c_match = (core_model == cfg["model"])

    integration_html = f"""
      <div class="grid">
        <label>UCN/RR ⇄ LLM Settings</label>
        <div>{badge(u_match)} <small>ucnrr.model=<b>{u_model}</b> vs saved=<b>{cfg['model']}</b></small></div>
        <label>Core ⇄ LLM Settings</label>
        <div>{badge(c_match)} <small>core.model=<b>{core_model}</b> vs saved=<b>{cfg['model']}</b></small></div>
      </div>
      <small>If DIFF: re-launch services from Control Panel Plus after sourcing the generated env script.</small>
    """

    body = f"""
    <h1>🧭 ReDNA AI Control Panel (Agent-Only)</h1>

    <section>
      <h2>Services</h2>
      {services_html}
    </section>

    <section>
      <h2>LLM (Llama3 / Ollama)</h2>
      {llm_html}
      <h3>Integration Check</h3>
      {integration_html}
    </section>

    <section>
      <h2>Send Text → UCN/RR → Core</h2>
      <form method="post" action="/ingest">
        <div class="grid">
          <label>User ID</label><input type="text" name="user_id" value="harness_user"/>
          <label>Text</label><input type="text" name="text" placeholder="e.g., I have dark brown eyes"/>
        </div>
        <p><button>Send</button></p>
      </form>
      <small>Posts to <code>/ingest_text</code> on UCN/RR, then you can view Core’s resolved doc below.</small>
    </section>

    <section>
      <h2>Harness (Golden Path)</h2>
      <form method="post" action="/harness">
        <label>User ID</label> <input name="user_id" type="text" value="harness_user"/>
        <button>Run 4 Tests</button>
      </form>
      <small>Tests: ~6ft height, husband 25 years, dark brown eyes, red hair + balding cue.</small>
    </section>

    <section>
      <h2>Resolved Viewer</h2>
      <form method="get" action="/resolved/view">
        <label>User ID</label> <input name="user_id" type="text" value="harness_user"/>
        <button>View</button>
      </form>
      <p><small>Flat rows: <code>/resolved/flat?user_id=&lt;id&gt;</code></small></p>
    </section>

    <section>
      <h2>Reset (wipe test user)</h2>
      <form method="post" action="/user/reset" onsubmit="return confirm('Really wipe this user\\'s data in both services?');">
        <label>User ID</label> <input name="user_id" type="text" value="harness_user"/>
        <button>Wipe User Data</button>
      </form>
      <small>Deletes <code>{UCNRR_DATA_DIR}/users/&lt;id&gt;</code> and <code>{CORE_DATA_DIR}/users/&lt;id&gt;</code>.</small>
    </section>
    """
    return _html_page(body)

# -----------------------------------------------------------------------------
# Routes — LLM controls
# -----------------------------------------------------------------------------
@app.post("/llm/save")
def llm_save(
    provider: str = Form(...),
    model: str = Form(...),
    base_url: str = Form(...),
    api_key: str = Form(...),
    prompts_dir: str = Form(...),
    ucn_prompt_main: str = Form(...),
    ucn_prompt_conf: str = Form(...),
    core_prompt_main: str = Form(...),
    core_prompt_prop: str = Form(...)
):
    cfg = {
        "provider": provider.strip(),
        "model": model.strip(),
        "base_url": base_url.strip(),
        "api_key": api_key.strip(),
        "prompts_dir": prompts_dir.strip(),
        "ucn_prompt_main": ucn_prompt_main.strip(),
        "ucn_prompt_conf": ucn_prompt_conf.strip(),
        "core_prompt_main": core_prompt_main.strip(),
        "core_prompt_prop": core_prompt_prop.strip(),
    }
    _write_llm(cfg)
    return PlainTextResponse("Saved LLM settings. Re-launch services from Control Panel Plus after sourcing the generated env script.", status_code=200)

@app.get("/llm/probe", response_class=HTMLResponse)
def llm_probe():
    cfg = _read_llm()
    ok, info = _ollama_tags(cfg["base_url"])
    has = _ollama_has_model(info if ok else {}, cfg["model"])
    status = "OK" if ok else "ERROR"
    found = "yes" if has else "no"
    body = f"""
    <h1>Llama Server Probe</h1>
    <p>Base URL: <b>{cfg['base_url']}</b></p>
    <p>Status: <span class="badge {'ok' if ok else 'bad'}">{status}</span></p>
    <p>Model “{cfg['model']}” installed: <span class="badge {'ok' if has else 'warn'}">{found}</span></p>
    <h3>Raw Response</h3>
    <pre class="code">{json.dumps(info, indent=2, ensure_ascii=False)}</pre>
    <p><a href="/">Back</a></p>
    """
    return _html_page(body, title="Llama Probe")

@app.get("/llm/make_env", response_class=HTMLResponse)
def llm_make_env():
    cfg = _read_llm()
    path = _make_env_script(cfg)
    body = f"""
    <h1>Env Script Generated</h1>
    <p>Wrote: <b>{path}</b></p>
    <p>In Control Panel Plus, launch services with:</p>
    <pre class="code">source "{path}" && uvicorn ...</pre>
    <p><a href="/">Back</a></p>
    """
    return _html_page(body, title="Env Script")

# -----------------------------------------------------------------------------
# Routes — health, ingest, harness, resolved, reset
# -----------------------------------------------------------------------------
@app.get("/health/{svc}")
def health_view(svc: str):
    ok, j = _health_ok(CORE_PORT if svc == "core" else UCNRR_PORT if svc == "ucnrr" else -1)
    if svc not in ("core","ucnrr"):
        return PlainTextResponse("unknown service", status_code=400)
    return JSONResponse(j, status_code=200 if ok else 500)

@app.post("/ingest", response_class=HTMLResponse)
def ingest(user_id: str = Form(...), text: str = Form(...)):
    code, resp = _post_ucnrr_ingest(user_id, text)
    status, resolved = _get_core_resolved(user_id)
    pretty = json.dumps(resolved, indent=2, ensure_ascii=False)
    body = f"""
    <h1>Ingest Result</h1>
    <p><b>UCN/RR</b> status: {code}</p>
    <pre class="code">{resp}</pre>
    <h2>Core /resolved/{user_id}</h2>
    <pre class="code">{pretty}</pre>
    <p><a href="/">Back</a></p>
    """
    return _html_page(body, title="Ingest → Resolved")

@app.post("/harness", response_class=HTMLResponse)
def harness(user_id: str = Form(...)):
    import time as _t
    results = []
    for text, frag in TESTS:
        code, resp = _post_ucnrr_ingest(user_id, text)
        _t.sleep(1.5)
        status, resolved = _get_core_resolved(user_id)
        found = _contains_fragment(resolved, frag)
        results.append({"text": text, "expect": frag, "ucnrr": code, "core": status, "pass": bool(found), "resp": resp[:280]})
    rows = "".join(
        f"<tr><td>{r['text']}</td><td class='code'>{r['expect']}</td>"
        f"<td>{r['ucnrr']}</td><td>{r['core']}</td><td>{'✅' if r['pass'] else '❌'}</td>"
        f"<td class='code'>{r['resp']}</td></tr>"
        for r in results
    )
    body = f"""
    <h1>Harness Results</h1>
    <p>User: <b>{user_id}</b></p>
    <table>
      <tr><th>Text</th><th>Expect</th><th>UCN/RR</th><th>Core</th><th>Pass?</th><th>UCN/RR resp (trunc)</th></tr>
      {rows}
    </table>
    <p><a href="/">Back</a></p>
    """
    return _html_page(body, title="Harness Results")

@app.get("/resolved/view", response_class=HTMLResponse)
def resolved_view(user_id: str = "harness_user"):
    status, doc = _get_core_resolved(user_id)
    res = doc.get("resolved", {}) if isinstance(doc, dict) else {}
    rows = "".join(
        f"<tr><td class='code'>{k}</td><td class='code'>{v.get('resolved_value', v)}</td><td>{v.get('ucn','')}</td></tr>"
        for k, v in sorted(res.items())
    )
    body = f"""
    <h1>Resolved for {user_id}</h1>
    <table>
      <tr><th>Trait</th><th>Value</th><th>UCN</th></tr>
      {rows}
    </table>
    <p><a href="/">Back</a></p>
    """
    return _html_page(body, title=f"Resolved {user_id}")

@app.get("/resolved/flat")
def resolved_flat(user_id: str = "harness_user"):
    status, flat = _get_core_resolved_flat(user_id)
    return JSONResponse(flat, status_code=status)

@app.post("/user/reset")
def user_reset(user_id: str = Form(...)):
    _reset_user(user_id)
    return PlainTextResponse(f"Deleted user '{user_id}' in Core & UCN/RR data dirs.", status_code=200)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("ai_control_panel_agent:app", host="127.0.0.1", port=PANEL_PORT, reload=False)