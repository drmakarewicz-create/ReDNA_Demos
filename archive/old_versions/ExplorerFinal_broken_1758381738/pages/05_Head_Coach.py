# ExplorerFinal/pages/05_Head_Coach.py
from __future__ import annotations

import streamlit as st
from ui.nav import side_nav, top_tabs

st.set_page_config(page_title="Head Coach", layout="wide")
side_nav(active="explorer")   # keep left icon list consistent
top_tabs(active="head")       # top tabs highlight

st.title("Head Coach")

# Mirror the Explorer's freeform box (baseline)
free_text = st.text_area("What should I learn?", height=140)
if st.button("Process", type="primary"):
    st.info("Baseline: processing is disabled here until the main Explorer is stabilized; will wire this to the same UCN/RR → Core pipeline next.")