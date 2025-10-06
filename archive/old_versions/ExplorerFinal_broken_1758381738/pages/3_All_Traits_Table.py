# ExplorerFinal/pages/3_All_Traits_Table.py
from __future__ import annotations

import os, time
import requests
import pandas as pd
import streamlit as st
from ui.nav import side_nav

st.set_page_config(page_title="All Traits — ReDNA Explorer", layout="wide")

st.markdown(
    """
    <style>
      [data-testid="stSidebarNav"] { display: none; }
      section[data-testid="stSidebar"] { visibility: visible; }
    </style>
    """,
    unsafe_allow_html=True,
)

UCNRR_BASE = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")
CORE_BASE  = os.getenv("CORE_BASE",  "http://127.0.0.1:8015").rstrip("/")
ACTIVE_KEY = "active_user"

def get_active_user() -> str | None:
    return st.session_state.get(ACTIVE_KEY)

def core_resolved_flat(user_id: str) -> pd.DataFrame:
    r = requests.get(f"{CORE_BASE}/resolved/flat/{user_id}", timeout=8)
    r.raise_for_status()
    rows = (r.json() or {}).get("rows", [])
    return pd.DataFrame(rows or [])

side_nav(active="all_traits")
st.title("All Traits")

active = get_active_user()
if not active:
    st.info("Pick a user in Explorer Final to continue.")
    st.stop()

c1, c2 = st.columns([1, 6])
with c1:
    auto = st.toggle("Auto-refresh", value=True, help="Poll Core every few seconds.")

with c2:
    if st.button("Refresh from Core", use_container_width=False):
        st.experimental_rerun()

if auto:
    st.autorefresh = st.experimental_rerun  # no-op reference
    st.experimental_set_query_params(ts=str(time.time()))

try:
    df = core_resolved_flat(active)
    st.dataframe(df, use_container_width=True, height=640)
except Exception as e:
    st.warning(f"Could not load resolved flat: {e}")