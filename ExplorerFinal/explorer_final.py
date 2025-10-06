#!/usr/bin/env python3
# Explorer Final — self-contained Streamlit app
# - Works with ReDNACoreDemo (port 8015 by default) and UCN_RR_Demo (8011)
# - Initializes session_state keys BEFORE rendering widgets (fixes StreamlitAPIException)
# - Lets you: pick a user, send freeform text to UCN/RR, nudge Core, view Core resolved
# - Honors environment overrides: UCNRR_BASE, CORE_BASE

from __future__ import annotations

try:
    from . import _prelude  # noqa: F401
    from . import _bootstrap  # noqa: F401
except Exception:  # pragma: no cover - fallback for script execution
    import pathlib
    import sys

    _f = pathlib.Path(__file__).resolve()
    sys.path.insert(0, str(_f.parent))
    sys.path.insert(0, str(_f.parent.parent))
    import ExplorerFinal._prelude  # noqa: F401
    import ExplorerFinal._bootstrap  # noqa: F401

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

from ui.nav import render_top_nav
from ui.components import render_quick_link_chips
from ui.session import (
    get_user_id,
    switch_active_user,
    consume_user_loaded_toast,
    safe_rerun,
)
from ui.nudge_inbox import render_nudge_inbox
from ui.draft_chat import render_draft_chat
from ui.components import (
    ChipSpec,
    compact_mode_enabled,
    render_sticky_header,
    write_protect_enabled,
)
from ui.feedback_dashboard import render_feedback_dashboard
from ui.hotreload import PrefsWatcher

try:
    from ExplorerDev.curiosity_utils import resolve_curiosity_mode
except Exception:  # pragma: no cover - optional import when Dev helpers unavailable
    resolve_curiosity_mode = None  # type: ignore

try:  # Flag helpers respect system prefs when ExplorerDev is available
    from ExplorerDev.schema_utils import get_flag_bool, SYSTEM_PREFS_PATH
except Exception:  # pragma: no cover - fallback when running standalone
    SYSTEM_PREFS_PATH = Path(__file__).resolve().parents[1] / "data" / "dev_system_prefs.json"

    def get_flag_bool(name: str, default: bool = False):
        env_val = os.getenv(name)
        if env_val is not None:
            token = env_val.strip().lower()
            if token in {"1", "true", "yes", "on"}:
                return True, "env"
            if token in {"0", "false", "no", "off"}:
                return False, "env"
        return default, "default"


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
UCNRR_BASE = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")
CORE_BASE  = os.getenv("CORE_BASE",  "http://127.0.0.1:8015").rstrip("/")

_DEV_TRUE = {"1", "true", "yes", "on"}
NUDGE_INBOX_ENABLED = os.getenv("NUDGE_INBOX_ENABLED", "false").strip().lower() in _DEV_TRUE
NUDGE_DELIVER_TO_CHAT = os.getenv("NUDGE_DELIVER_TO_CHAT", "false").strip().lower() in _DEV_TRUE
DEV_LOOPTEST_USER = os.getenv("DEV_LOOPTEST_USER_ID", "devexp_test")

TIMEOUT_S = 30


# -----------------------------------------------------------------------------
# Safe requests
# -----------------------------------------------------------------------------
def _jget(url: str, **kw) -> Tuple[int, Any]:
    try:
        r = requests.get(url, timeout=kw.pop("timeout", TIMEOUT_S), **kw)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    except Exception as e:
        return 0, {"error": str(e)}

def _jpost(url: str, json_body: dict, **kw) -> Tuple[int, Any]:
    try:
        r = requests.post(url, json=json_body, timeout=kw.pop("timeout", TIMEOUT_S), **kw)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    except Exception as e:
        return 0, {"error": str(e)}


# -----------------------------------------------------------------------------
# API wrappers
# -----------------------------------------------------------------------------
def ucnrr_health() -> Tuple[int, Any]:
    return _jget(f"{UCNRR_BASE}/health")

def ucnrr_users() -> List[str]:
    code, j = _jget(f"{UCNRR_BASE}/users/list")
    if code == 200 and isinstance(j, dict):
        return j.get("users", [])
    return []

def ucnrr_init_user(username: str) -> Tuple[int, Any]:
    body = {"username": username}
    return _jpost(f"{UCNRR_BASE}/users/init", body)

def ucnrr_ingest_text(user_id: str, text: str, lines: Optional[List[str]] = None) -> Tuple[int, Any]:
    payload = {
        "user_id": user_id,
        "text": text,
        "lines": lines or [],
        "provenance": {
            "actor": "user",
            "source": "explorer",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    }
    return _jpost(f"{UCNRR_BASE}/ingest_text", payload)

def core_health() -> Tuple[int, Any]:
    return _jget(f"{CORE_BASE}/health")

def core_ingest_from_ucnrr(user_id: str) -> Tuple[int, Any]:
    body = {"user_id": user_id}
    return _jpost(f"{CORE_BASE}/ingest_from_ucnrr", body)

def core_resolved(user_id: str) -> Tuple[int, Any]:
    return _jget(f"{CORE_BASE}/resolved/{user_id}")

def core_resolved_flat(user_id: str) -> Tuple[int, Any]:
    return _jget(f"{CORE_BASE}/resolved/flat/{user_id}")


def ucnrr_holistic(user_id: str) -> Tuple[int, Any]:
    return _jpost(f"{UCNRR_BASE}/holistic/{user_id}", {})


def core_recompute(user_id: str) -> Tuple[int, Any]:
    return _jpost(f"{CORE_BASE}/recompute/{user_id}", {})


# -----------------------------------------------------------------------------
# Streamlit App
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Explorer Final", page_icon="🧬", layout="wide")

# Initialize session_state keys *before* widgets are created
ss = st.session_state
_defaults = {
    "user_id": get_user_id(),
    "freeform_text": "",
    "last_ucnrr": None,
    "last_core": None,
    "last_resolved": None,
    "last_resolved_flat": None,
    "_clear_text_flag": False,  # used by the Clear button callback
    "_clear_inputs_next": False,
    "canonical_lines": "",
    "_show_canonical_input": False,
    "last_ucnrr_llm_used": None,
    "last_core_ai_paths": [],
    "last_holistic": None,
    "last_core_recompute": None,
}
for k, v in _defaults.items():
    if k not in ss:
        ss[k] = v


def _apply_prefs_update(update) -> bool:
    """Apply watcher results into session state.

    Returns True when a meaningful update occurred.
    """

    if update is None:
        return False

    if getattr(update, "error", None):
        ss["_prefs_last_error"] = update.error
        return False

    if getattr(update, "updated", False):
        ss["_prefs_last_update_ts"] = getattr(update, "timestamp", time.time())
        diff_summary = update.diff.summary() if getattr(update, "diff", None) else []
        ss["_prefs_diff_preview"] = diff_summary
        ss["_prefs_last_error"] = None
        if ss.get("_prefs_initialized"):
            if diff_summary:
                ss["_prefs_show_toast"] = True
        else:
            ss["_prefs_initialized"] = True
        return True

    return False

# Honor one-shot clear requests before widgets render
if ss.get("_clear_text_flag"):
    ss["freeform_text"] = ""
    ss["_clear_text_flag"] = False

if ss.get("_clear_inputs_next"):
    ss["freeform_text"] = ""
    ss["canonical_lines"] = ""
    ss["_clear_inputs_next"] = False

def _request_clear_text():
    # This sets a flag that the top-of-file block will honor on the next run
    st.session_state["_clear_text_flag"] = True
    st.session_state["canonical_lines"] = ""

st.title("🧬 Explorer Final")
render_top_nav(active="explorer")

active_user = get_user_id()
pending_user_toast = consume_user_loaded_toast()
if pending_user_toast:
    st.success(f"Loaded user: {pending_user_toast}")
render_quick_link_chips()

if "_prefs_watcher" not in ss:
    ss["_prefs_watcher"] = PrefsWatcher(SYSTEM_PREFS_PATH)
if "_prefs_auto_refresh" not in ss:
    ss["_prefs_auto_refresh"] = True
if "_prefs_initialized" not in ss:
    ss["_prefs_initialized"] = False
if "_prefs_diff_preview" not in ss:
    ss["_prefs_diff_preview"] = []
if "_prefs_last_update_ts" not in ss:
    ss["_prefs_last_update_ts"] = None
if "_prefs_last_error" not in ss:
    ss["_prefs_last_error"] = None

prefs_watcher: PrefsWatcher = ss["_prefs_watcher"]
auto_refresh_state = bool(ss.get("_prefs_auto_refresh", True))
prefs_update = prefs_watcher.poll() if auto_refresh_state else None
_apply_prefs_update(prefs_update)

compact_mode_value, compact_mode_source = compact_mode_enabled()
write_protect_state = write_protect_enabled()

feedback_enabled, feedback_source = get_flag_bool("FEEDBACK_ENABLED", True)
audit_enabled, audit_source = get_flag_bool("AUDIT_VIEWER_ENABLED", True)
ops_enabled, ops_source = get_flag_bool("HC_OPS_ENABLED", False)

extra_chips: List[ChipSpec] = [
    ChipSpec(
        label="Feedback",
        value="on" if feedback_enabled else "off",
        color="#9c6fce" if feedback_enabled else "#a0a0a0",
        source=feedback_source,
    ),
    ChipSpec(
        label="Audit",
        value="on" if audit_enabled else "off",
        color="#d4a017" if audit_enabled else "#a0a0a0",
        source=audit_source,
    ),
    ChipSpec(
        label="Ops",
        value="on" if ops_enabled else "off",
        color="#137b80" if ops_enabled else "#a0a0a0",
        source=ops_source,
    ),
]

quick_links = [
    ("Head Coach", "#head-coach", "HC", "Head Coach"),
    ("Unabridged", "#unabridged", "UA", "Unabridged Traits"),
    ("Draft Chat", "#draft-chat", "DC", "Draft Chat"),
    ("Snapshots", "#snapshots", "SS", "Snapshots"),
]
if feedback_enabled:
    quick_links.append(("Feedback", "#feedback-dashboard", "FB", "Feedback Dashboard"))

curiosity_mode_label = "sim"
curiosity_mode_source = "default"
if resolve_curiosity_mode is not None:
    mode_info = resolve_curiosity_mode("_explorer_curiosity_mode")
    curiosity_mode_label = "live" if mode_info.effective_live else "sim"
    curiosity_mode_source = mode_info.effective_source
else:  # pragma: no cover - fallback when curiosity helpers unavailable
    env_mode = os.getenv("EXPLORER_CURIOSITY_MODE")
    if env_mode is not None:
        curiosity_mode_label = "live" if env_mode.strip().lower() == "live" else "sim"
        curiosity_mode_source = "env"

uc_users = ucnrr_users()
if DEV_LOOPTEST_USER not in uc_users:
    uc_users = [DEV_LOOPTEST_USER] + [user for user in uc_users if user != DEV_LOOPTEST_USER]
if active_user and active_user not in uc_users:
    uc_users = [active_user] + [user for user in uc_users if user != active_user]
if not uc_users:
    uc_users = [active_user or DEV_LOOPTEST_USER]

uc_health_code, uc_health_body = ucnrr_health()
core_health_code, core_health_body = core_health()

core_curiosity_value = "unknown"
if isinstance(core_health_body, dict):
    for key in ("curiosity", "curiosity_enabled", "live_curiosity"):
        if key in core_health_body:
            value = core_health_body.get(key)
            if isinstance(value, bool):
                core_curiosity_value = "on" if value else "off"
            else:
                core_curiosity_value = str(value)
            break
core_curiosity_state = (core_curiosity_value, "health")


def _on_user_change(new_user: str) -> None:
    if switch_active_user(new_user, trigger_toast=True):
        safe_rerun()


header_state = render_sticky_header(
    user_options=uc_users,
    active_user=active_user or uc_users[0],
    on_user_change=_on_user_change,
    curiosity_mode=(curiosity_mode_label, curiosity_mode_source),
    core_curiosity=core_curiosity_state,
    write_protect=write_protect_state,
    compact=compact_mode_value,
    extra_chips=extra_chips,
    quick_links=quick_links,
    auto_refresh_enabled=auto_refresh_state,
    auto_refresh_interval=getattr(prefs_watcher, "interval", 7.0),
    last_update_ts=ss.get("_prefs_last_update_ts"),
    prefs_error=ss.get("_prefs_last_error"),
    diff_preview=(ss.get("_prefs_diff_preview") or [])[:6],
)

new_auto_refresh = header_state.get("auto_refresh", auto_refresh_state)
if new_auto_refresh != auto_refresh_state:
    ss["_prefs_auto_refresh"] = bool(new_auto_refresh)
    if new_auto_refresh:
        manual_update = prefs_watcher.force_refresh()
        _apply_prefs_update(manual_update)
    st.experimental_rerun()

if header_state.get("refresh_now"):
    manual_update = prefs_watcher.force_refresh()
    _apply_prefs_update(manual_update)
    st.experimental_rerun()

if ss.pop("_prefs_show_toast", False):
    diff_preview = ss.get("_prefs_diff_preview") or []
    if diff_preview:
        keys_preview = ", ".join(diff_preview[:6])
        if len(diff_preview) > 6:
            keys_preview += ", …"
        st.toast(f"Settings updated (prefs): {keys_preview}", icon="✅")
    else:
        st.toast("Settings updated (prefs)", icon="✅")

st.markdown("<div id='head-coach'></div>", unsafe_allow_html=True)
st.subheader("Head Coach")
st.caption("Open the Head Coach experience to collaborate with specialist personas via chips.")
page_link = getattr(st, "page_link", None)
if callable(page_link):
    page_link("pages/05_Head_Coach.py", label="Open Head Coach", icon="🧠")
else:
    st.markdown("[Open Head Coach](?page=Head%20Coach)")

st.markdown("<div id='unabridged'></div>", unsafe_allow_html=True)
st.subheader("Unabridged Traits")
st.caption("Review the full trait table with governance context.")
if callable(page_link):
    page_link("pages/4_Unabridged_Traits_Table.py", label="Open Unabridged", icon="📚")
else:
    st.markdown("[Open Unabridged](?page=Unabridged%20Traits)")

st.divider()

if NUDGE_INBOX_ENABLED:
    st.markdown("<div id='nudge-inbox'></div>", unsafe_allow_html=True)
    mailbox_user = (active_user or DEV_LOOPTEST_USER).strip() or DEV_LOOPTEST_USER
    mailbox_path = Path("data") / "dev_mailbox" / mailbox_user / "inbox.json"
    st.markdown(f"### Nudge Inbox · `{mailbox_path.as_posix()}`")
    st.caption("If empty, send motivators via Dev Explorer ▸ Coach Workshop ▸ Head Coach Preview.")
    render_nudge_inbox(default_user=DEV_LOOPTEST_USER, active_user=active_user)
    if NUDGE_DELIVER_TO_CHAT:
        render_draft_chat(default_user=DEV_LOOPTEST_USER, active_user=active_user)
    st.divider()

if feedback_enabled:
    st.markdown("<div id='feedback-dashboard'></div>", unsafe_allow_html=True)
    render_feedback_dashboard(default_user=DEV_LOOPTEST_USER, active_user=active_user)
    st.divider()

st.markdown("<div id='snapshots'></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Connections")
    st.caption("These can be overridden via env vars `UCNRR_BASE` and `CORE_BASE`.")
    st.write(f"**UCN/RR:** `{UCNRR_BASE}`")
    st.write(f"**Core:** `{CORE_BASE}`")

    colh1, colh2 = st.columns(2)
    with colh1:
        st.metric("UCN/RR", "OK" if uc_health_code == 200 else "DOWN")
        if uc_health_code == 200 and isinstance(uc_health_body, dict):
            st.caption(f"provider={uc_health_body.get('provider')}, model={uc_health_body.get('model')}")
    with colh2:
        st.metric("Core", "OK" if core_health_code == 200 else "DOWN")
        if core_health_code == 200 and isinstance(core_health_body, dict):
            st.caption(f"data_dir={core_health_body.get('data_dir')}")

    st.divider()

    st.subheader("User")
    users = uc_users
    sel = st.selectbox("Known users (UCN/RR)", options=[""] + users, index=0, key="known_users_select")
    if sel and switch_active_user(sel, trigger_toast=True):
        safe_rerun()

    st.info(
        "Use the Onboarding Coach persona to create new users. Once onboarding completes, the new profile will appear in this list."
    )

    current_user = get_user_id()
    st.text_input("Active user_id", value=current_user, key="user_id_input", disabled=True)

st.markdown("<div id='explorer-chat'></div>", unsafe_allow_html=True)
st.write("### Freeform → Traits")
st.caption("Type something like: *I have dark brown eyes and I’m six feet tall.*")

# Input form -------------------------------------------------------------
# Input areas (no Streamlit form so button state updates live)
free_text_value = st.text_area(
    "Free text",
    key="freeform_text",
    height=140,
    placeholder="Type freeform text here…",
)
show_canonical = st.checkbox(
    "Show canonical lines override",
    value=ss.get("_show_canonical_input", False),
    help="Enable if you need to paste explicit Trait.Path=Value overrides.",
)
ss["_show_canonical_input"] = show_canonical
if show_canonical:
    canonical_value = st.text_area(
        "Canonical lines",
        key="canonical_lines",
        height=110,
        placeholder="Trait.Path=Value",
    )
else:
    ss["canonical_lines"] = ""
    canonical_value = ""

c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    send_disabled = not (active_user or "").strip()
    send_ok = st.button(
        "Send to UCN/RR + Core",
        type="primary",
        use_container_width=True,
        disabled=send_disabled,
    )
with c2:
    clear_clicked = st.button("Clear text", on_click=_request_clear_text, use_container_width=True)
with c3:
    nudge_ok = st.button(
        "Nudge Core (pull latest from UCN/RR)",
        use_container_width=True,
        disabled=(not (active_user or "").strip()),
    )
with c4:
    holistic_ok = st.button(
        "Holistic AI Review",
        use_container_width=True,
        disabled=(not (active_user or "").strip()),
    )

if send_ok:
    uid = get_user_id()
    txt = (free_text_value or "").strip()
    lines = [ln.strip() for ln in (canonical_value or "").splitlines() if ln.strip()]
    if not txt and not lines:
        st.warning("Enter some free text or at least one canonical line before sending.")
        st.stop()
    with st.spinner("Extracting traits…"):
        code, j = ucnrr_ingest_text(uid, txt, lines)
    ss["last_ucnrr"] = {"status": code, "resp": j}
    used_llm = False
    if code == 200 and isinstance(j, dict) and j.get("ok"):
        keys = j.get("changed_keys") or j.get("resolved_keys", [])
        st.success(f"UCN/RR ok. Keys: {', '.join(keys) or '—'}")
        used_llm = bool(txt) and not lines and bool(keys)
    else:
        st.error(f"UCN/RR error: {code} {j}")

    core_resp = j.get("core_response") if isinstance(j, dict) else None
    if isinstance(core_resp, dict):
        ss["last_core"] = {
            "status": core_resp.get("status_code", 200 if core_resp.get("ok") else 500),
            "resp": core_resp,
        }

    ss["_clear_inputs_next"] = True
    ss["last_ucnrr_llm_used"] = used_llm

    rc, rj = core_resolved(uid)
    ss["last_resolved"] = {"status": rc, "doc": rj}
    rfc, rfj = core_resolved_flat(uid)
    ss["last_resolved_flat"] = {"status": rfc, "rows": rfj}

    core_body = None
    if isinstance(ss.get("last_core"), dict):
        core_payload = ss["last_core"].get("resp")
        if isinstance(core_payload, dict):
            core_body = core_payload.get("body") if isinstance(core_payload.get("body"), dict) else core_payload
    if isinstance(core_body, dict):
        ss["last_core_ai_paths"] = core_body.get("added_by_core_ai") or []
    else:
        ss["last_core_ai_paths"] = []

    st.rerun()

if nudge_ok:
    uid = get_user_id()
    with st.spinner("Core ingest_from_ucnrr…"):
        code, j = core_ingest_from_ucnrr(uid)
    ss["last_core"] = {"status": code, "resp": j}
    if code == 200 and isinstance(j, dict) and j.get("ok"):
        st.success(f"Core ingest ok. Changed: {', '.join(j.get('changed', [])) or '—'}")
    else:
        st.error(f"Core ingest error: {code} {j}")

    rc, rj = core_resolved(uid)
    ss["last_resolved"] = {"status": rc, "doc": rj}
    rfc, rfj = core_resolved_flat(uid)
    ss["last_resolved_flat"] = {"status": rfc, "rows": rfj}

    if isinstance(j, dict):
        core_body = j.get("body") if isinstance(j.get("body"), dict) else j
    else:
        core_body = None
    if isinstance(core_body, dict):
        ss["last_core_ai_paths"] = core_body.get("added_by_core_ai") or []
    else:
        ss["last_core_ai_paths"] = []

if holistic_ok:
    uid = get_user_id()
    with st.spinner("Running holistic AI review…"):
        h_code, h_resp = ucnrr_holistic(uid)
    ss["last_holistic"] = {"status": h_code, "resp": h_resp}

    if isinstance(h_resp, dict):
        core_resp = h_resp.get("core_response")
        if isinstance(core_resp, dict):
            ss["last_core"] = {
                "status": core_resp.get("status_code", 200 if core_resp.get("ok") else 500),
                "resp": core_resp,
            }
    with st.spinner("Core recompute in progress…"):
        rc_code, rc_resp = core_recompute(uid)
    ss["last_core_recompute"] = {"status": rc_code, "resp": rc_resp}

    rc, rj = core_resolved(uid)
    ss["last_resolved"] = {"status": rc, "doc": rj}
    rfc, rfj = core_resolved_flat(uid)
    ss["last_resolved_flat"] = {"status": rfc, "rows": rfj}

    ss["last_core_ai_paths"] = []

    st.rerun()

st.markdown("#### Latest contributions")
col_contrib = st.columns(3)
last_ucnrr = ss.get("last_ucnrr")
ucnrr_badge = "—"
if isinstance(last_ucnrr, dict):
    resp_body = last_ucnrr.get("resp") if isinstance(last_ucnrr.get("resp"), dict) else {}
    changed = resp_body.get("changed_keys") or resp_body.get("resolved_keys") or []
    llm_used = ss.get("last_ucnrr_llm_used")
    if llm_used:
        ucnrr_badge = f"AI extracted {len(changed)} traits"
    elif changed:
        ucnrr_badge = f"Manual input {len(changed)} traits"
    else:
        reason = resp_body.get("message") or resp_body.get("reason") or "No changes"
        ucnrr_badge = str(reason)

core_badge = "—"
core_ai_badge = "—"
last_core = ss.get("last_core")
core_body = None
if isinstance(last_core, dict):
    payload = last_core.get("resp")
    if isinstance(payload, dict):
        core_body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
if isinstance(core_body, dict):
    caller = core_body.get("changed_from_caller") or []
    added_ai = core_body.get("added_by_core_ai") or []
    core_badge = f"Updated {len(caller)} traits" if caller else "No caller changes"
    core_ai_badge = f"AI added {len(added_ai)} traits" if added_ai else "No AI additions"

with col_contrib[0]:
    st.metric("UCN/RR", ucnrr_badge)
with col_contrib[1]:
    st.metric("Core (caller)", core_badge)
with col_contrib[2]:
    st.metric("Core AI", core_ai_badge)

st.divider()

colA, colB = st.columns(2)

with colA:
    st.subheader("UCN/RR • last call")
    if ss["last_ucnrr"] is None:
        st.info("No UCN/RR calls yet.")
    else:
        st.code(json.dumps(ss["last_ucnrr"], indent=2, ensure_ascii=False), language="json")

    st.subheader("Core ingest • last call")
    if ss["last_core"] is None:
        st.caption("Click *Nudge Core* to pull again, if needed.")
    else:
        st.code(json.dumps(ss["last_core"], indent=2, ensure_ascii=False), language="json")

with colB:
    st.subheader("Core • resolved")
    if ss["last_resolved"] is None:
        st.caption("Send text or Nudge Core to refresh resolved.")
    else:
        st.code(json.dumps(ss["last_resolved"], indent=2, ensure_ascii=False), language="json")

    st.subheader("Core • resolved (flat rows)")
    if ss["last_resolved_flat"] is None:
        st.caption("—")
    else:
        st.code(json.dumps(ss["last_resolved_flat"], indent=2, ensure_ascii=False), language="json")

st.subheader("AI review results")
colH1, colH2 = st.columns(2)
with colH1:
    st.caption("UCN/RR Holistic Review")
    if ss.get("last_holistic"):
        st.code(json.dumps(ss["last_holistic"], indent=2, ensure_ascii=False), language="json")
    else:
        st.caption("No holistic run yet.")
with colH2:
    st.caption("Core /recompute")
    if ss.get("last_core_recompute"):
        st.code(json.dumps(ss["last_core_recompute"], indent=2, ensure_ascii=False), language="json")
    else:
        st.caption("No recompute run yet.")

st.divider()
st.caption(
    "Tip: If you ever see the Streamlit key error again, it means a session_state key was changed *after* its widget was created. This app avoids that by initializing all keys up-front and using a pre-widget flag for clearing."
)
