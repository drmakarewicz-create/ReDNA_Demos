"""Read-only Draft Chat viewer for accepted nudges."""

from __future__ import annotations

import os
from typing import Dict, List

import json

import streamlit as st

from ExplorerFinal.core import nudge_store
from ExplorerFinal.ui.components import compact_mode_enabled, render_css_once

_DEV_TRUE = {"1", "true", "yes", "on"}
WRITE_PROTECT = os.getenv("WRITE_PROTECT", "true").strip().lower() in _DEV_TRUE


def _sorted_entries(entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(entries, key=lambda row: row.get("ts", ""), reverse=True)


def render_draft_chat(*, default_user: str, active_user: str | None = None) -> None:
    compact_mode, _ = compact_mode_enabled()
    render_css_once(compact=compact_mode)

    st.markdown("<div id='draft-chat'></div>", unsafe_allow_html=True)
    st.markdown("### Draft Chat")
    st.caption("Messages generated from accepted nudges (read-only preview).")

    user_default = active_user or default_user
    user_id = st.text_input(
        "Chat user id",
        value=user_default,
        key="draft_chat_user",
        help="Select which user's draft chat to inspect.",
    ).strip()

    if not user_id:
        st.info("Enter a user id to view Draft Chat entries.")
        return

    entries = nudge_store.get_draft_chat(user_id, write_protect=WRITE_PROTECT)
    if not entries:
        st.info("No draft chat entries yet — accept nudges with delivery enabled to populate this list.")
        return

    mailbox_root = getattr(nudge_store, "MAILBOX_ROOT", None)
    if mailbox_root is not None:
        st.caption(f"draft_chat.json → {(mailbox_root / user_id / 'draft_chat.json').as_posix()}")

    st.markdown(
        "<a href='#explorer-chat'><button>Open in Chat</button></a>",
        unsafe_allow_html=True,
    )
    switch_page = getattr(st, "switch_page", None)
    if switch_page:
        if st.button("Open full Head Coach app", key="draft_chat_open"):
            switch_page("pages/05_Head_Coach.py")

    for entry in _sorted_entries(entries):
        with st.container(border=True):
            ts = entry.get("ts") or "—"
            sender = entry.get("from") or "head_coach"
            nudge_id = entry.get("nudge_id") or "—"
            cols = st.columns([0.75, 0.25]) if not compact_mode else st.columns([0.7, 0.3])
            with cols[0]:
                st.markdown(
                    f"<small><strong>{sender}</strong> · {ts} · nudge {nudge_id}</small>",
                    unsafe_allow_html=True,
                )
            with cols[1]:
                payload = entry.get("text") or ""
                payload_json = json.dumps(payload)
                button_html = (
                    "<button type='button' style='width:100%;' "
                    f"onclick=\"navigator.clipboard.writeText({payload_json})\">Copy</button>"
                )
                st.markdown(button_html, unsafe_allow_html=True)
            st.write(entry.get("text") or "(empty)")


__all__ = ["render_draft_chat"]
