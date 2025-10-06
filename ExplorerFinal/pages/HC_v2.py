"""Head Coach v2 — hardened Streamlit shell.

Run with `streamlit run ExplorerFinal/pages/HC_v2.py` to open the demo UI.
The composer stays anchored, persona chips remain visible, and uploads use a
modal so layout never shifts during interaction.
"""

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

from ui.hc_v2 import render_hc_v2_page

st.set_page_config(page_title="Head Coach v2", layout="wide")

render_hc_v2_page()
