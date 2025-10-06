from __future__ import annotations

import streamlit as st

from ui.coach_orchestrator import build_photo_body_renderer
from ui.coach_tab import render_coach_tab

st.set_page_config(page_title="Photo Coach", page_icon="📸", layout="wide")

render_coach_tab(
    page_title="Photo Refinement Coach",
    nav_key="photo",
    page_prefix="photo",
    chat_input_label="Message the Head Coach…",
    chat_placeholder="Upload photos or ask for visual refinements",
    provenance_source="photo_coach_chat",
    upload_source="photo_coach_upload",
    enable_personas=False,
    extra_body_renderer=build_photo_body_renderer("photo"),
)
