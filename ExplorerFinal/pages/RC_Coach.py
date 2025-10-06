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

st.set_page_config(page_title="Relationship Coach", layout="wide")

st.title("💞 Relationship Coach")
st.info(
    "Relationship Coach now lives inside Head Coach. Use the persona chips on Head Coach to switch into RC mode."
)
page_link = getattr(st, "page_link", None)
if callable(page_link):
    page_link("pages/05_Head_Coach.py", label="Open Head Coach", icon="🧠")
else:
    st.markdown("[Open Head Coach](?page=Head%20Coach)")

st.stop()
