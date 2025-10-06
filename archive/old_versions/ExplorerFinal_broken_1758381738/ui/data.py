# ExplorerFinal/ui/data.py
from __future__ import annotations
import os, time, requests, streamlit as st

CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8015").rstrip("/")

# A single version flag we bump whenever Core gets new writes.
_VERSION_KEY = "__core_data_version"

def _version() -> int:
    if _VERSION_KEY not in st.session_state:
        st.session_state[_VERSION_KEY] = 0
    return st.session_state[_VERSION_KEY]

def bump_version() -> None:
    st.session_state[_VERSION_KEY] = _version() + 1

# ---------- Cached fetchers keyed by (user_id, version) ----------
@st.cache_data(show_spinner=False)
def _fetch_resolved(user_id: str, version: int) -> dict:
    r = requests.get(f"{CORE_BASE}/resolved/{user_id}", timeout=10)
    r.raise_for_status()
    return r.json()

@st.cache_data(show_spinner=False)
def _fetch_resolved_flat(user_id: str, version: int) -> dict:
    r = requests.get(f"{CORE_BASE}/resolved/flat/{user_id}", timeout=10)
    r.raise_for_status()
    return r.json()

def get_resolved(user_id: str) -> dict:
    return _fetch_resolved(user_id, _version())

def get_resolved_flat(user_id: str) -> dict:
    return _fetch_resolved_flat(user_id, _version())

def soft_wait_for_core(user_id: str, tries: int = 3, delay_s: float = 0.25) -> dict:
    """
    After a write to Core, wait briefly + refetch so the UI shows the
    latest resolved snapshot without manual refresh.
    """
    last = {}
    for _ in range(tries):
        try:
            last = get_resolved(user_id)
            if isinstance(last, dict) and (last.get("resolved") or {}):
                break
        except Exception:
            pass
        time.sleep(delay_s)
    return last