from ui.nav import side_nav, hide_default_sidebar
hide_default_sidebar()
side_nav(active="photo")          # or "padna" / "head_coach" / "onboarding"

# ExplorerFinal/pages/08_PaDNA_Outbound_Avatar.py
from __future__ import annotations
import os, requests, pandas as pd
import streamlit as st
from ui.nav import side_nav

side_nav(active="padna")
st.set_page_config(page_title="PaDNA Outbound Avatar", page_icon="📦", layout="wide")
st.title("PaDNA Outbound Avatar")

CORE_BASE  = os.getenv("CORE_BASE", "http://127.0.0.1:8015").rstrip("/")
ACTIVE_KEY = "active_user"

def core_get_resolved_flat(user_id: str) -> pd.DataFrame:
    try:
        r = requests.get(f"{CORE_BASE}/resolved/flat/{user_id}", timeout=10)
        r.raise_for_status()
        return pd.DataFrame((r.json() or {}).get("rows", []))
    except Exception:
        return pd.DataFrame()

active = st.session_state.get(ACTIVE_KEY)
st.caption("Active user is shared across pages.")
if not active:
    st.info("Pick a user in Explorer Final or Head Coach.")
    st.stop()

st.info("For demo: this page will later read PaDNA traits and render a face. For now it previews the PaDNA rows.")

df = core_get_resolved_flat(active)
st.dataframe(df[df["trait_key"].str.startswith("PaDNA")], use_container_width=True) if not df.empty else st.info("No PaDNA rows yet.")