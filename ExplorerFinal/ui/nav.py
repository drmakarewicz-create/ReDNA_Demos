# ExplorerFinal/ui/nav.py
from __future__ import annotations

import os

import streamlit as st
from typing import Literal, Optional

# Map the *actual* page files that exist in ExplorerFinal/pages/
# (no leading zeros, matching your repo names)
PAGES = {
    "explorer":   ("explorer_final.py", "🧭 Explorer"),  # legacy entrypoint (hidden)
    "head":       ("pages/05_Head_Coach.py", "🧠 Head Coach"),
    "unabridged": ("pages/4_Unabridged_Traits_Table.py", "📚 Unabridged Traits"),
    "onboarding": ("pages/06_Onboarding.py", "🗂️ Onboarding"),  # accessible via direct link/persona
    "photo":      ("pages/06_Photo_Coach.py", "🖼️ Photo Coach"),  # hidden from nav
    "padna":      ("pages/07_PaDNA_Coach.py", "📦 PaDNA Outbound"),  # hidden from nav
    "relationship": ("pages/RC_Coach.py", "💞 Relationship Coach"),  # hidden from nav
}

PERSONA_DEV_TABS = os.getenv("PERSONA_DEV_TABS", "false").strip().lower() in {"1", "true", "yes", "on"}
USER_EXPLORER_RSC_ENABLED = os.getenv("USER_EXPLORER_RSC_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
USER_EXPLORER_RCDEV_ENABLED = os.getenv("USER_EXPLORER_RCDEV_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
DEV_NAV_ITEMS = []

if PERSONA_DEV_TABS:
    pages_update = {}
    if USER_EXPLORER_RCDEV_ENABLED:
        DEV_NAV_ITEMS.append(("rc_dev", "RC Dev", "🧪"))
        pages_update["rc_dev"] = ("pages/RC_Dev.py", "🧪 RC Dev")
    if USER_EXPLORER_RSC_ENABLED:
        DEV_NAV_ITEMS.append(("rsc_dev", "RSC Dev", "🤝"))
        pages_update["rsc_dev"] = ("pages/RSC_Dev.py", "🤝 RSC Dev")
    PAGES.update(pages_update)


PRIMARY_NAV_ITEMS = [
    ("head", "Head Coach", "🧠"),
]


def render_rsc_disabled_banner() -> bool:
    if USER_EXPLORER_RSC_ENABLED:
        return False
    st.info("This feature now lives in Dev Explorer ▸ Collaboration Demos.")
    return True

def page_link(page_path: str, label: str, icon: Optional[str] = None, *, width: int = 180):
    """
    Safe wrapper: only add a link if the file really exists, otherwise do nothing.
    """
    try:
        st.sidebar.page_link(page_path, label=label, icon=icon or " ")
    except Exception:
        # Missing pages shouldn't crash the app; we just skip the link.
        pass

def render_top_nav(active: Optional[str] = None) -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Arrange buttons in two rows if we have more than 4 entries
    items_per_row = 4
    try:
        from .session import get_user_id, list_users
        from .onboarding_state import (
            should_show_onboarding_tab,
            onboarding_active,
            mark_completed,
        )

        user_id = get_user_id()
        if user_id and user_id in list_users() and not onboarding_active(user_id):
            mark_completed(user_id)
        show_onboarding = should_show_onboarding_tab(user_id)
    except Exception:
        # Fallback when imported outside Streamlit runtime
        user_id = None
        show_onboarding = True

    filtered_items = list(PRIMARY_NAV_ITEMS)

    rows = [filtered_items[i:i + items_per_row] for i in range(0, len(filtered_items), items_per_row)]
    if DEV_NAV_ITEMS:
        rows.append(DEV_NAV_ITEMS)
    switch_page = getattr(st, "switch_page", None)

    for row in rows:
        cols = st.columns(len(row))
        for col, (key, label, icon) in zip(cols, row):
            with col:
                page_path, _ = PAGES[key]
                is_active = active == key
                button_label = f"{icon} {label}" if icon else label

                if switch_page:
                    if st.button(
                        button_label,
                        key=f"nav_{key}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                        disabled=is_active,
                    ) and not is_active:
                        switch_page(page_path)
                else:
                    try:
                        st.page_link(
                            page_path,
                            label=label,
                            icon=icon,
                            help=None if is_active else "",
                        )
                    except Exception:
                        if key == "explorer":
                            try:
                                st.link_button(
                                    button_label,
                                    url="?page=Explorer%20Final",
                                )
                            except Exception:
                                pass

def side_nav(active: Literal["head", "unabridged"] = "head"):
    st.sidebar.markdown("### Explorer")

    nav_items = list(PRIMARY_NAV_ITEMS)

    for key, _label, _icon in nav_items:
        page_path, page_title = PAGES[key]
        # Streamlit handles active styling internally when using page_link
        page_link(page_path, page_title)
