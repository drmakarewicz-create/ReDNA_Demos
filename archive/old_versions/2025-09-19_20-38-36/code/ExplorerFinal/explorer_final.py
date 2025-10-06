# ExplorerFinal/explorer_final.py
from __future__ import annotations

import os
import time
import requests
import streamlit as st
from typing import Any, Dict, List, Optional

# Optional nav (safe if not present)
try:
    from ui.nav import top_tabs, side_nav  # type: ignore
except Exception:
    top_tabs = side_nav = lambda *a, **k: None  # no-op if nav module isn't there

# Session helpers (your working user picker)
from ui.session import user_picker, get_user_id  # type: ignore

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
CORE_BASE  = os.getenv("CORE_BASE",  "http://127.0.0.1:8015").rstrip("/")
UCNRR_BASE = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")

st.set_page_config(page_title="ReDNA Explorer — Final", layout="wide")
top_tabs(active="explorer")
side_nav(active="explorer")

st.title("ReDNA Explorer — Final")

# ---------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------
def _post_ucnrr_ingest_text(user_id: str, text: str) -> Dict[str, Any]:
    try:
        r = requests.post(
            f"{UCNRR_BASE}/ingest_text",
            json={"user_id": user_id, "text": text},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _get_core_resolved(user_id: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{CORE_BASE}/resolved/{user_id}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"user_id": user_id, "schema_version": 4, "resolved": {}, "error": str(e)}

def _get_core_resolved_flat(user_id: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{CORE_BASE}/resolved/flat/{user_id}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"rows": [], "error": str(e)}

def _rows_len(doc_flat: Optional[Dict[str, Any]]) -> int:
    try:
        return len((doc_flat or {}).get("rows") or [])
    except Exception:
        return 0

# After sending to UCN/RR, poll Core briefly so merged traits appear
def _poll_core_after_ingest(user_id: str, tries: int = 6, delay_s: float = 0.8) -> None:
    """Poll Core a few times and keep the freshest snapshot in session."""
    base_len = _rows_len(st.session_state.get("__last_resolved_flat"))
    latest_doc = _get_core_resolved(user_id)
    latest_flat = _get_core_resolved_flat(user_id)

    best_doc = latest_doc
    best_flat = latest_flat
    best_len = _rows_len(latest_flat)

    for _ in range(max(1, tries - 1)):
        time.sleep(max(0.1, delay_s))
        cur_doc = _get_core_resolved(user_id)
        cur_flat = _get_core_resolved_flat(user_id)
        cur_len = _rows_len(cur_flat)

        if cur_len >= best_len:
            best_doc, best_flat, best_len = cur_doc, cur_flat, cur_len
        # small exit optimization: if Core already added rows beyond baseline, keep them
        if cur_len > base_len:
            best_doc, best_flat = cur_doc, cur_flat
            break

    st.session_state["__last_resolved_doc"] = best_doc
    st.session_state["__last_resolved_flat"] = best_flat

# ---------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------
user_picker("Existing users")
uid = get_user_id()
if not uid:
    st.info("Pick a user to continue.")
    st.stop()

# ---------------------------------------------------------------------
# Freeform capture
# ---------------------------------------------------------------------
st.subheader("Freeform Text")
text = st.text_area(
    "What should I learn?",
    height=160,
    key="__freeform_text",  # IMPORTANT: we never mutate this key in the same run
    placeholder="Try: 'I'm around 6 feet' or 'I've been a husband for 25 years'",
)

c1, c2 = st.columns([1, 7])
with c1:
    do_process = st.button("Process", type="primary", use_container_width=True)
with c2:
    st.caption(
        "After processing, Explorer briefly polls Core so merged traits appear without manual reload."
    )

if do_process and (text or "").strip():
    with st.spinner("Sending to UCN/RR and updating Core…"):
        ures = _post_ucnrr_ingest_text(uid, text.strip())
        st.session_state["__last_ucnrr"] = ures
        # Even if UCN/RR returns note:no_actionable, Core may still hold prior truths; refresh anyway
        _poll_core_after_ingest(uid, tries=6, delay_s=0.8)
    # Do NOT mutate st.session_state['__freeform_text'] in this same run.
    st.rerun()

# Ensure something to show on first load
resolved_doc  = st.session_state.get("__last_resolved_doc")  or _get_core_resolved(uid)
resolved_flat = st.session_state.get("__last_resolved_flat") or _get_core_resolved_flat(uid)
st.session_state["__last_resolved_doc"]  = resolved_doc
st.session_state["__last_resolved_flat"] = resolved_flat

# ---------------------------------------------------------------------
# Resolved views (from Core)
# ---------------------------------------------------------------------
st.subheader("Resolved (nested)")
st.json(resolved_doc or {})

st.subheader("Resolved (flat)")
rows = (resolved_flat or {}).get("rows") or []
if rows:
    st.dataframe(
        {
            "trait_key": [r.get("trait_key") for r in rows],
            "value":     [r.get("value") for r in rows],
            "ucn":       [r.get("ucn") for r in rows],
            "notes":     [r.get("notes") for r in rows],
            "status":    [r.get("status") for r in rows],
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No resolved traits yet.")

st.divider()

# ---------------------------------------------------------------------
# Debug expander (kept minimal but handy)
# ---------------------------------------------------------------------
with st.expander("Pipeline (debug)"):
    st.markdown("**UCN/RR last response**")
    st.json(st.session_state.get("__last_ucnrr") or {"note": "No request yet."})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Core health**")
        try:
            st.json(requests.get(f"{CORE_BASE}/health", timeout=4).json())
        except Exception as e:
            st.write({"error": str(e)})
    with c2:
        st.markdown("**UCN/RR health**")
        try:
            st.json(requests.get(f"{UCNRR_BASE}/health", timeout=4).json())
        except Exception as e:
            st.write({"error": str(e)})