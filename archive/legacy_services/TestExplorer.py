# TestExplorer.py (v4.3 — stable pins + NL→trait auto-bridge for eyes/hair)
# Run: streamlit run TestExplorer.py

import os, json, time, pathlib, re
from typing import Any, Dict, Optional, List
import requests
import streamlit as st

st.set_page_config(page_title="ReDNA TestExplorer (v4.3)", page_icon="🧬", layout="wide")

# -------- Defaults (your OpenAPI) --------
DEFAULT_CORE_URL  = os.getenv("CORE_URL",  "http://127.0.0.1:8015").rstrip("/")
DEFAULT_UCNRR_URL = os.getenv("UCNRR_URL", "http://127.0.0.1:8011").rstrip("/")

DEFAULT_PINS = {
    "core_health":        "/health",
    "core_nudge":         "/ingest_from_ucnrr",
    "core_resolved":      "/resolved/{uid}",
    "core_resolved_flat": "/resolved/flat/{uid}",
    "ucnrr_health":       "/health",
    "ucnrr_ingest_text":  "/ingest_text",
}

ROUTE_MAP_PATH = pathlib.Path("ExplorerFinal/ui/.route_map.json")
SETTINGS_PATH  = pathlib.Path("ExplorerFinal/ui/.explorer_settings.json")

# -------- Session state --------
def ensure_state():
    ss = st.session_state
    # URLs
    if SETTINGS_PATH.exists():
        try:
            s = json.loads(SETTINGS_PATH.read_text())
            ss.setdefault("CORE_URL",  s.get("CORE_URL",  DEFAULT_CORE_URL))
            ss.setdefault("UCNRR_URL", s.get("UCNRR_URL", DEFAULT_UCNRR_URL))
        except Exception:
            ss.setdefault("CORE_URL",  DEFAULT_CORE_URL)
            ss.setdefault("UCNRR_URL", DEFAULT_UCNRR_URL)
    else:
        ss.setdefault("CORE_URL",  DEFAULT_CORE_URL)
        ss.setdefault("UCNRR_URL", DEFAULT_UCNRR_URL)

    # Pins (editable; persisted)
    pins = DEFAULT_PINS.copy()
    if ROUTE_MAP_PATH.exists():
        try:
            data = json.loads(ROUTE_MAP_PATH.read_text())
            for k in pins.keys():
                if k in data and data[k]:
                    pins[k] = data[k]
        except Exception:
            pass
    ss.setdefault("pins", pins)

    ss.setdefault("users", [])
    ss.setdefault("selected_user_id", None)
    ss.setdefault("messages", [])
    ss.setdefault("resolved_traits", {})
    ss.setdefault("resolved_flat", {"rows":[]})
    ss.setdefault("service_health", {"core": None, "ucnrr": None})
    ss.setdefault("last_http", [])
    ss.setdefault("last_diag", None)
    ss.setdefault("auto_nudge", True)
    ss.setdefault("auto_bridge", True)  # NEW: map simple NL to canonical trait lines

ensure_state()

def save_pins():
    ROUTE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROUTE_MAP_PATH.write_text(json.dumps(st.session_state["pins"], indent=2))

def save_urls():
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps({
        "CORE_URL": st.session_state["CORE_URL"],
        "UCNRR_URL": st.session_state["UCNRR_URL"],
    }, indent=2))

# -------- HTTP helpers --------
def log_http(direction, method, url, req, resp):
    entry = {"ts": time.strftime("%H:%M:%S"), "dir": direction, "method": method,
             "url": url, "status": getattr(resp, "status_code", None),
             "ok": getattr(resp, "ok", None), "req": req, "resp": None}
    if isinstance(resp, requests.Response):
        try: entry["resp"] = resp.json()
        except Exception: entry["resp"] = getattr(resp, "text", None)
    st.session_state["last_http"] = (st.session_state["last_http"] + [entry])[-150:]

def _get(url, timeout=8, **kw):
    try: return requests.get(url, timeout=timeout, **kw)
    except Exception: return None

def _post(url, json=None, timeout=12, **kw):
    try: return requests.post(url, json=json, timeout=timeout, **kw)
    except Exception: return None

def GET(base: str, path: str):
    url = base.rstrip("/") + path
    log_http("→","GET",url,None,None)
    r = _get(url)
    log_http("←","GET",url,None,r)
    return r

def POST(base: str, path: str, payload: Any):
    url = base.rstrip("/") + path
    log_http("→","POST",url,payload,None)
    r = _post(url, json=payload)
    log_http("←","POST",url,payload,r)
    return r

def pin(key: str) -> str:
    return st.session_state["pins"][key]

def path_for(key: str, uid: Optional[str] = None) -> str:
    p = pin(key)
    return p.replace("{uid}", uid) if (uid is not None) else p

# -------- Health --------
def check_health():
    core = GET(st.session_state["CORE_URL"], pin("core_health"))
    ucn  = GET(st.session_state["UCNRR_URL"], pin("ucnrr_health"))
    st.session_state["service_health"]["core"]  = bool(core and core.ok)
    st.session_state["service_health"]["ucnrr"] = bool(ucn and ucn.ok)

check_health()

# -------- Core ops --------
def core_nudge(user_id: str) -> Dict[str, Any]:
    r = POST(st.session_state["CORE_URL"], pin("core_nudge"), {"user_id": user_id})
    try: return r.json() if (r and r.ok) else {"error": True, "status": getattr(r,"status_code",None)}
    except Exception: return {"error": True, "status": getattr(r,"status_code",None), "text": getattr(r,"text",None)}

def core_get_resolved(user_id: str) -> Dict[str, Any]:
    r = GET(st.session_state["CORE_URL"], path_for("core_resolved", user_id))
    try: return r.json() if (r and r.ok) else {}
    except Exception: return {}

def core_get_resolved_flat(user_id: str) -> Dict[str, Any]:
    r = GET(st.session_state["CORE_URL"], path_for("core_resolved_flat", user_id))
    try: return r.json() if (r and r.ok) else {"rows":[]}
    except Exception: return {"rows":[]}

# -------- UCN/RR ops --------
def ucnrr_ingest_text(user_id: str, text: str) -> Dict[str, Any]:
    payload = {"user_id": user_id, "text": text}
    r = POST(st.session_state["UCNRR_URL"], pin("ucnrr_ingest_text"), payload)
    try: return r.json() if (r and r.ok) else {"error": True, "status": getattr(r,"status_code",None)}
    except Exception: return {"error": True, "status": getattr(r,"status_code",None), "text": getattr(r,"text",None)}

# -------- NL → Trait Auto-Bridge (very small, conservative) --------
EYE_COLOR_MAP = {
    r"\bblue\b": "Blue",
    r"\bbrown\b": "Brown",
    r"\bgreen\b": "Green",
    r"\bhazel\b": "Hazel",
    r"\bgrey\b|\bgray\b": "Gray",
}
HAIR_COLOR_MAP = {
    r"\bblond(e)?\b": "Blonde",
    r"\bbrown\b": "Brown",
    r"\bblack\b": "Black",
    r"\bred\b": "Red",
    r"\bauburn\b": "Auburn",
    r"\bgray\b|\bgrey\b": "Gray",
}

def auto_bridge_lines(nl: str) -> List[str]:
    """Map simple NL to canonical equal-form lines the backend already accepts."""
    lines = []
    low = nl.lower()
    # eyes
    if re.search(r"\b(eye|eyes|iris)\b", low):
        for patt, canon in EYE_COLOR_MAP.items():
            if re.search(patt, low):
                lines.append(f"EyeDNA.IrisColor={canon}")
                break
    # hair
    if re.search(r"\bhair\b", low):
        for patt, canon in HAIR_COLOR_MAP.items():
            if re.search(patt, low):
                lines.append(f"HairDNA.Color={canon}")
                break
    return lines

def build_payload_text(nl: str, enable_bridge: bool) -> str:
    """Return text to send to /ingest_text. If bridging is enabled and we detect
       known phrases, we append canonical lines to help the parser."""
    if not enable_bridge:
        return nl
    bridges = auto_bridge_lines(nl)
    if not bridges:
        return nl
    # Append canonical hints under a clear separator (the service only sees text).
    suffix = "\n\n# Canonical hints\n" + "\n".join(bridges)
    return nl.strip() + suffix

# -------- UI Header --------
h1, h2, h3 = st.columns([0.45,0.35,0.20])
with h1: st.markdown("## 🧬 ReDNA TestExplorer (v4.3)")
with h2:
    core_ok = "✅" if st.session_state["service_health"]["core"] else "❌"
    ucn_ok  = "✅" if st.session_state["service_health"]["ucnrr"] else "❌"
    st.markdown(f"**Core** {core_ok} &nbsp;&nbsp; **UCN/RR** {ucn_ok}")
with h3:
    if st.button("🔄 Recheck Health", use_container_width=True):
        check_health(); st.rerun()
st.divider()

# -------- Users (local only) --------
u1, u2 = st.columns([0.70,0.30])
with u1:
    users = st.session_state["users"]
    if users and st.session_state["selected_user_id"] not in users:
        st.session_state["selected_user_id"] = users[0]
    st.session_state["selected_user_id"] = st.selectbox(
        "Select User (local)", options=users,
        index=users.index(st.session_state["selected_user_id"]) if users and st.session_state["selected_user_id"] in users else 0 if users else None,
        placeholder="Create a user…", key="user_select",
    )
with u2:
    with st.popover("➕ New User"):
        with st.form("create_user_form", clear_on_submit=False):
            new_name = st.text_input("Username")
            submitted = st.form_submit_button("Create", use_container_width=True, type="primary")
        if submitted:
            name = (new_name or "").strip()
            if not name:
                st.toast("Enter a username")
            else:
                if name not in st.session_state["users"]:
                    st.session_state["users"].append(name)
                st.session_state["selected_user_id"] = name
                st.toast(f"User ready: {name}")
                st.session_state["resolved_traits"] = core_get_resolved(name)
                st.session_state["resolved_flat"]   = core_get_resolved_flat(name)
                st.rerun()
if not st.session_state["users"]:
    st.info("No local users yet. Create one with ➕.")

# -------- Nav --------
TABS = ["🏠 Home", "🧬 Traits", "⚙️ Settings", "🛠️ Dev"]
st.radio("Navigation", options=TABS, horizontal=True, key="nav")
active = st.session_state["nav"]
st.write("")

# -------- HOME --------
if active == "🏠 Home":
    st.subheader("Head Coach Chat")
    topA, topB = st.columns([0.5,0.5])
    topA.toggle("Auto-nudge Core after ingest", key="auto_nudge")
    topB.toggle("Auto-bridge simple NL (eyes/hair)", key="auto_bridge")

    chat_box = st.container(height=440, border=True)
    with chat_box:
        for msg in st.session_state["messages"]:
            with st.chat_message(msg.get("role","user")):
                st.markdown(msg.get("content",""))

    # Bridges quick buttons (unchanged behavior that worked for you)
    with st.expander("Bridges: quick sample inputs"):
        cA, cB = st.columns(2)
        if cA.button("Send `EyeDNA.IrisColor=Blue`", use_container_width=True):
            uid = st.session_state.get("selected_user_id")
            txt = "EyeDNA.IrisColor=Blue"
            st.session_state["messages"].append({"role":"user","content":txt})
            resp = ucnrr_ingest_text(uid, txt)
            st.session_state["messages"].append({"role":"assistant","content":"Sent to UCN/RR. " + ("(ok)" if resp.get("ok") else "(not ok)") + (f" — note: {resp.get('note')}" if resp.get("note") else "")})
            if st.session_state["auto_nudge"] and uid:
                _ = core_nudge(uid)
            st.session_state["resolved_traits"] = core_get_resolved(uid)
            st.session_state["resolved_flat"]   = core_get_resolved_flat(uid)
            st.session_state["last_diag"] = {"bridge":"equals_form","ucnrr":resp,"resolved":st.session_state["resolved_traits"]}
            st.rerun()
        if cB.button("Send YAML block", use_container_width=True):
            uid = st.session_state.get("selected_user_id")
            txt = "traits:\n  EyeDNA.IrisColor: Blue"
            st.session_state["messages"].append({"role":"user","content":txt})
            resp = ucnrr_ingest_text(uid, txt)
            st.session_state["messages"].append({"role":"assistant","content":"Sent to UCN/RR. " + ("(ok)" if resp.get("ok") else "(not ok)") + (f" — note: {resp.get('note')}" if resp.get("note") else "")})
            if st.session_state["auto_nudge"] and uid:
                _ = core_nudge(uid)
            st.session_state["resolved_traits"] = core_get_resolved(uid)
            st.session_state["resolved_flat"]   = core_get_resolved_flat(uid)
            st.session_state["last_diag"] = {"bridge":"yaml_form","ucnrr":resp,"resolved":st.session_state["resolved_traits"]}
            st.rerun()

    # Chat input — ALWAYS echo first
    st.session_state.pop("chat_input_home", None)
    prompt = st.chat_input("Type a message to your Head Coach…", key="chat_input_home")
    if prompt:
        uid = st.session_state.get("selected_user_id")
        st.session_state["messages"].append({"role":"user","content":prompt})

        text_to_send = build_payload_text(prompt, st.session_state["auto_bridge"])
        resp = ucnrr_ingest_text(uid, text_to_send)

        if resp.get("ok"):
            st.toast("📨 UCN/RR accepted text")
        else:
            st.toast("⚠️ UCN/RR did not accept text — see Dev logs")
        if resp.get("note"):
            st.toast(f"UCN/RR note: {resp['note']}")

        if st.session_state["auto_nudge"] and uid:
            core_resp = core_nudge(uid)
            if core_resp.get("ok"): st.toast("🧲 Core ingested from UCN/RR")
            else: st.toast("ℹ️ Core nudge returned no changes")

        st.session_state["resolved_traits"] = core_get_resolved(uid)
        st.session_state["resolved_flat"]   = core_get_resolved_flat(uid)

        # Assistant summary
        bridges = auto_bridge_lines(prompt) if st.session_state["auto_bridge"] else []
        note = "Logged and synchronized with Core."
        if bridges: note += " (auto-bridge: " + ", ".join(bridges) + ")"
        if resp.get("note"): note += f" UCN/RR note: {resp['note']}"
        st.session_state["messages"].append({"role":"assistant","content":note})

        st.session_state["last_diag"] = {
            "sent_text": text_to_send,
            "ucnrr_response": resp,
            "resolved_after": st.session_state["resolved_traits"],
        }
        st.rerun()

    with st.expander("Quick Glance: Resolved (Core)"):
        st.json(st.session_state.get("resolved_traits") or {"info":"No resolved traits yet."})

# -------- TRAITS --------
elif active == "🧬 Traits":
    st.subheader("Resolved Traits (Core)")
    uid = st.session_state.get("selected_user_id")
    a,b,c,d = st.columns([0.22,0.24,0.24,0.30])
    with a:
        if st.button("↻ Refresh", use_container_width=True):
            st.session_state["resolved_traits"] = core_get_resolved(uid) if uid else {}
            st.session_state["resolved_flat"]   = core_get_resolved_flat(uid) if uid else {"rows":[]}
            st.rerun()
    with b:
        if st.button("🧲 Nudge Core", use_container_width=True):
            if uid: _ = core_nudge(uid)
            st.session_state["resolved_traits"] = core_get_resolved(uid) if uid else {}
            st.session_state["resolved_flat"]   = core_get_resolved_flat(uid) if uid else {"rows":[]}
            st.rerun()
    with c:
        st.caption("Core is the arbiter; this mirrors Core.")
    with d:
        st.caption("If empty: UCN/RR returned no actionable traits.")

    st.markdown("**Hierarchical**"); st.json(st.session_state.get("resolved_traits") or {})
    st.markdown("**Flat**");         st.json(st.session_state.get("resolved_flat") or {"rows":[]})

# -------- SETTINGS --------
elif active == "⚙️ Settings":
    st.subheader("Connections (Base URLs)")
    colA, colB = st.columns(2)
    st.session_state["CORE_URL"]  = colA.text_input("CORE_URL",  value=st.session_state["CORE_URL"])
    st.session_state["UCNRR_URL"] = colB.text_input("UCNRR_URL", value=st.session_state["UCNRR_URL"])
    s1, s2 = st.columns([0.25,0.75])
    if s1.button("Save URLs"): save_urls(); st.toast("URLs saved.")
    if s2.button("Recheck Health"): check_health(); st.rerun()

    st.markdown("---")
    st.subheader("Manual Route Pins")
    st.caption("Edit and Save. Use {uid} in user-scoped paths; replaced at runtime.")
    edits = {}
    for k in ["core_health","core_nudge","core_resolved","core_resolved_flat","ucnrr_health","ucnrr_ingest_text"]:
        edits[k] = st.text_input(k, value=st.session_state["pins"].get(k,""))
    p1, p2 = st.columns([0.25,0.75])
    if p1.button("Save Pins"):
        st.session_state["pins"].update(edits); save_pins(); st.toast("Pins saved.")
    if p2.button("Reset to Defaults"):
        st.session_state["pins"] = DEFAULT_PINS.copy(); save_pins(); st.toast("Pins reset to defaults.")

# -------- DEV --------
elif active == "🛠️ Dev":
    st.subheader("Live Wire — HTTP Logs")
    logs = st.session_state.get("last_http", [])
    if not logs:
        st.info("No HTTP logs yet.")
    else:
        for e in logs:
            status, ok = e["status"], e["ok"]
            marker = "🟢" if ok else ("🔴" if status else "⚫")
            header = f"{marker} [{e['ts']}] {e['method']} {e['url']} → status={status} ok={ok}"
            with st.expander(header):
                st.markdown("**Request**"); st.json(e["req"])
                st.markdown("**Response**"); st.json(e["resp"])

    st.markdown("---")
    st.subheader("Last Diagnostic")
    if st.session_state.get("last_diag"):
        st.code(json.dumps(st.session_state["last_diag"], indent=2), language="json")
    else:
        st.info("No diagnostic yet — send a message on Home.")

    st.markdown("---")
    st.subheader("Service Health")
    st.json(st.session_state["service_health"])