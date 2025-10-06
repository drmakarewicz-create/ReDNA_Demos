from __future__ import annotations

import streamlit as st

from ui.coach_orchestrator import build_padna_body_renderer
from ui.coach_tab import render_coach_tab

st.set_page_config(page_title="PaDNA Outbound Coach", page_icon="🎨", layout="wide")

render_coach_tab(
    page_title="PaDNA Outbound Coach",
    nav_key="padna",
    page_prefix="padna",
    chat_input_label="Message the Head Coach…",
    chat_placeholder="Ask about outbound avatar options or PaDNA packaging",
    provenance_source="padna_coach_chat",
    upload_source="padna_coach_upload",
    enable_personas=False,
    extra_body_renderer=build_padna_body_renderer("padna"),
)
