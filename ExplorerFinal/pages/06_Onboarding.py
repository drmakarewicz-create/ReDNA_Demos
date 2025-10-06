from __future__ import annotations

import streamlit as st

from ui.coach_tab import render_coach_tab
from ui.onboarding import render_onboarding_panel, render_sidebar_controls

st.set_page_config(page_title="Onboarding", layout="wide")

render_coach_tab(
    page_title="Onboarding Coach",
    nav_key="onboarding",
    page_prefix="onb",
    chat_input_label="Message the Onboarding Coach…",
    chat_placeholder="Kick off onboarding questions or share user context",
    provenance_source="onboarding_coach_chat",
    upload_source="onboarding_coach_upload",
    enable_personas=False,
    sidebar_renderer=render_sidebar_controls,
    extra_body_renderer=render_onboarding_panel,
)
