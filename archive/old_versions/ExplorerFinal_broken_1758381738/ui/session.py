# ExplorerFinal/ui/session.py
from __future__ import annotations

import os, json, requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st

# ---- Config ----
UCNRR_BASE = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")
CORE_BASE  = os.getenv("CORE_BASE",  "http://127.0.0.1:8015").rstrip("/")
CORE_DATA_DIR = Path(os.getenv("CORE_DATA_DIR", (Path(__file__).resolve().parents[1] / "../ReDNACoreDemo/data").as_posix())).resolve()

SESSION_USER_KEY = "active_user_id"

# ---- Session helpers ----
def get_user_id() -> str:
    return st.session_state.get(SESSION_USER_KEY, "").strip()

def set_user_id(uid: str) -> None:
    st.session_state[SESSION_USER_KEY] = (uid or "").strip()

def ensure_state() -> None:
    st.session_state.setdefault(SESSION_USER_KEY, "")

# ---- Data access ----
def list_users(max_items: int = 500) -> List[str]:
    users_root = CORE_DATA_DIR / "users"
    if not users_root.exists():
        return []
    out: List[str] = []
    for p in sorted(users_root.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            out.append(p.name)
            if len(out) >= max_items:
                break
    return out

def core_get_resolved(user_id: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{CORE_BASE}/resolved/{user_id}", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"user_id": user_id, "schema_version": 4, "resolved": {}}

def core_get_resolved_flat(user_id: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{CORE_BASE}/resolved/flat/{user_id}", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"rows": []}

def ucnrr_ingest_text(user_id: str, text: str) -> Dict[str, Any]:
    try:
        payload = {"user_id": user_id, "text": text}
        r = requests.post(f"{UCNRR_BASE}/ingest_text", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"ok": False, "reason": f"ucnrr_error:{e}"}

# ---- UI widgets ----
def user_picker(label_left: str = "Existing users", label_right: str = "Active user") -> Tuple[str, str]:
    """Dropdown + input, returns (chosen_from_list, active_input)."""
    ensure_state()
    users = list_users()
    dd = st.selectbox(label_left, ["—"] + users, index=0, key="existing_users_dd")
    active_val = st.text_input(label_right, value=get_user_id() or "", placeholder="e.g., 918NIGHT", key="active_user_input")
    cols = st.columns([1,1,8])
    with cols[0]:
        if st.button("Use", type="primary"):
            use_id = active_val.strip() or (dd if dd != "—" else "")
            set_user_id(use_id)
            st.rerun()
    with cols[1]:
        if st.button("Reload"):
            st.rerun()
    return dd, active_val

def freeform_block(title: str = "Freeform Text") -> None:
    """Shared ‘free text → UCN/RR → Core’ block."""
    uid = get_user_id()
    st.subheader(title)
    with st.expander("What should I learn?", expanded=True):
        text = st.text_area("", height=180, placeholder="Try: “I'm around 6 feet” or “I've been a husband for 25 years”")
        if st.button("Process", type="primary", use_container_width=False):
            if not uid:
                st.warning("Pick an active user (top of page) before processing.")
            elif not text.strip():
                st.info("Type something for me to learn.")
            else:
                res = ucnrr_ingest_text(uid, text.strip())
                st.json(res, expanded=False)
                # force a refresh so tables show latest Core view
                st.rerun()

def resolved_flat_table() -> None:
    uid = get_user_id()
    st.subheader("Resolved (flat)")
    if not uid:
        st.info("Pick an active user to view resolved traits.")
        return
    flat = core_get_resolved_flat(uid)
    rows = flat.get("rows", [])
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No resolved traits yet.")