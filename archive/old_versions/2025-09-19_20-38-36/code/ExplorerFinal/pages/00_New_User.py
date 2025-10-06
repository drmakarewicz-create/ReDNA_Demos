# ExplorerFinal/pages/00_New_User.py
from __future__ import annotations
import os, json
from pathlib import Path
import streamlit as st

from ui.nav import side_nav, top_tabs
from ui.session import set_user_id, get_user_id, CORE_DATA_DIR

st.set_page_config(page_title="ReDNA — New User", layout="wide")
side_nav(active="new")
st.title("Create New User")
top_tabs("new")

uid = st.text_input("User ID (letters/numbers/underscores only)", placeholder="e.g., 918NIGHT").strip()
root = CORE_DATA_DIR / "users" / uid if uid else None

if st.button("Create", type="primary") and uid:
    root.mkdir(parents=True, exist_ok=True)
    # create minimal scaffold files if missing
    (root / "resolved.json").write_text(json.dumps({"user_id": uid, "schema_version": 4, "resolved": {}}, indent=2))
    (root / "resolved.flat.json").write_text(json.dumps({"rows": []}, indent=2))
    (root / "observations.json").write_text(json.dumps({}, indent=2))
    (root / "evidence.json").write_text(json.dumps([], indent=2))
    set_user_id(uid)
    st.success(f"User '{uid}' created.")
    st.rerun()