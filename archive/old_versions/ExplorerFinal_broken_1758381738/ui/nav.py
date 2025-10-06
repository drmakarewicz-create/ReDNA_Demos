# ExplorerFinal/ui/nav.py
from __future__ import annotations

import streamlit as st
from typing import Literal, Optional

# Map the *actual* page files that exist in ExplorerFinal/pages/
# (no leading zeros, matching your repo names)
PAGES = {
    "explorer":      ("Explorer Final", None),  # main entrypoint (not under /pages)
    "all_traits":    ("pages/3_All_Traits_Table.py", "🧬 All Traits"),
    "unabridged":    ("pages/4_Unabridged_Traits_Table.py", "📚 Unabridged Traits"),
    "head":          ("pages/05_Head_Coach.py", "🧠 Head Coach"),
    "onboarding":    ("pages/06_Onboarding.py", "🗂️ Onboarding"),
    "photo":         ("pages/07_Photo_Refinement.py", "🖼️ Photo Refinement"),
    "padna":         ("pages/08_PaDNA_Outbound_Avatar.py", "📦 PaDNA Outbound Avatar"),
    "new_user":      ("pages/00_New_User.py", "➕ New User"),
}

def page_link(page_path: str, label: str, icon: Optional[str] = None, *, width: int = 180):
    """
    Safe wrapper: only add a link if the file really exists, otherwise do nothing.
    """
    try:
        st.sidebar.page_link(page_path, label=label, icon=icon or " ")
    except Exception:
        # Missing pages shouldn't crash the app; we just skip the link.
        pass

def top_tabs(active: Literal["explorer","head","onboarding","new_user"]="explorer"):
    col1, col2, col3, col4 = st.columns([1,1,1,1])
    with col1:
        page_link(PAGES["explorer"][0], label="🔎 Explore")
    with col2:
        page_link(*PAGES["head"])
    with col3:
        page_link(*PAGES["onboarding"])
    with col4:
        page_link(*PAGES["new_user"])

def side_nav(active: Literal["explorer","all_traits","unabridged","photo","padna"]="explorer"):
    st.sidebar.markdown("### Explorer")
    page_link(PAGES["explorer"][0], label="🧭 Explorer Final")
    page_link(*PAGES["all_traits"])
    page_link(*PAGES["unabridged"])
    page_link(*PAGES["photo"])
    page_link(*PAGES["padna"])