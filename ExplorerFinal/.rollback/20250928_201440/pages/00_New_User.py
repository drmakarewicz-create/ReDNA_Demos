# ExplorerFinal/pages/00_New_User.py
from __future__ import annotations

import shutil
from pathlib import Path

import streamlit as st

from ui.nav import side_nav, render_top_nav
from ui.session import (
    CORE_USERS_DIR,
    CORE_LEGACY_USERS_DIR,
    UCNRR_USERS_DIR,
    list_users,
    render_user_banner,
    set_user_id,
    get_user_id,
)


st.set_page_config(page_title="ReDNA — Delete Users", layout="wide")
side_nav(active="new_user")
render_top_nav(active="new_user")

st.title("Delete Users")
render_user_banner()

st.caption(
    "User creation now lives with the Onboarding Coach persona. Launch onboarding from the Head Coach tab to add new profiles."
)


def _delete_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


existing = list_users()
if not existing:
    st.info("No users found yet.")
else:
    targets = st.multiselect("Select users to delete", options=existing)
    confirm = st.checkbox(
        "I understand this permanently deletes the selected users from Core and UCN/RR storage.",
        value=False,
    )
    delete_clicked = st.button(
        "Delete selected users",
        type="secondary",
        use_container_width=False,
        disabled=(not targets or not confirm),
    )

    if delete_clicked and targets:
        removed: list[str] = []
        for del_user in targets:
            _delete_tree(CORE_USERS_DIR / del_user)
            _delete_tree(CORE_LEGACY_USERS_DIR / del_user)
            _delete_tree(UCNRR_USERS_DIR / del_user)
            removed.append(del_user)
            if get_user_id() == del_user:
                set_user_id("")
                st.session_state["user_id"] = ""
                st.session_state["active_user"] = ""
        if removed:
            st.success(
                "Deleted the following users from Core and UCN/RR storage: "
                + ", ".join(sorted(removed))
            )
        st.rerun()
