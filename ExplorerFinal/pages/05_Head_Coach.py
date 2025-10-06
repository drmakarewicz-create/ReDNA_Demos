from __future__ import annotations

try:
    from .. import _prelude  # noqa: F401
    from .. import _bootstrap  # noqa: F401
except Exception:  # pragma: no cover - fallback when executed as script
    import pathlib
    import sys

    _f = pathlib.Path(__file__).resolve()
    sys.path.insert(0, str(_f.parent))
    sys.path.insert(0, str(_f.parent.parent))
    import ExplorerFinal._prelude  # noqa: F401
    import ExplorerFinal._bootstrap  # noqa: F401

import streamlit as st

from ui.coach_tab import render_coach_tab

st.set_page_config(page_title="Head Coach", layout="wide")

render_coach_tab(
    page_title="Head Coach",
    nav_key="head",
    page_prefix="hc",
    chat_input_label="Message the Head Coach…",
    chat_placeholder="Share updates or questions for the Head Coach",
    provenance_source="head_coach_chat",
    upload_source="head_coach_upload",
    enable_personas=True,
)
