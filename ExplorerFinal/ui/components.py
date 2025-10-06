"""Shared UI helpers for Explorer streamlit pages."""

from __future__ import annotations

import os
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st

try:
    from ExplorerDev.schema_utils import get_flag_bool, get_flag_str
except Exception:  # pragma: no cover - Dev package optional in runtime
    def get_flag_bool(name: str, default: bool = False) -> Tuple[bool, str]:
        env_val = os.getenv(name)
        if env_val is not None:
            token = env_val.strip().lower()
            return token in {"1", "true", "yes", "on"}, "env"
        return bool(default), "default"

    def get_flag_str(name: str, default: str = "") -> Tuple[str, str]:
        env_val = os.getenv(name)
        if env_val is not None:
            return env_val.strip(), "env"
        return default, "default"


_DEV_TRUE = {"1", "true", "yes", "on"}


@dataclass
class ChipSpec:
    label: str
    value: str
    color: str = "#1f77b4"
    tooltip: Optional[str] = None
    source: Optional[str] = None


def compact_mode_enabled() -> Tuple[bool, str]:
    return get_flag_bool("EXPLORER_UI_COMPACT", False)


def reduced_motion_enabled() -> Tuple[bool, str]:
    return get_flag_bool("EXPLORER_UI_REDUCED_MOTION", False)


def write_protect_enabled() -> Tuple[bool, str]:
    return get_flag_bool("WRITE_PROTECT", True)


def render_css_once(*, compact: bool) -> None:
    key = "_explorer_base_css"
    if st.session_state.get(key):
        return
    spacing = "0.55rem" if compact else "0.9rem"
    card_gap = "0.6rem" if compact else "1.0rem"
    badge_padding = "0.1rem 0.45rem" if compact else "0.15rem 0.55rem"
    st.markdown(
        f"""
        <style>
        .explorer-sticky-header {{
            position: sticky;
            top: 3.25rem;
            z-index: 60;
            background: var(--background-color, #fff);
            padding: {spacing};
            border-bottom: 1px solid rgba(0,0,0,0.08);
            box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(6px);
        }}
        .explorer-header-grid {{
            display: grid;
            gap: {spacing};
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            align-items: center;
        }}
        .explorer-chip {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border-radius: 999px;
            padding: {badge_padding};
            font-size: 0.75rem;
            font-weight: 600;
            color: #fff;
            margin-right: 0.4rem;
            margin-bottom: 0.25rem;
        }}
        .explorer-chip-source {{
            text-transform: uppercase;
            font-size: 0.62rem;
            letter-spacing: 0.04em;
            opacity: 0.85;
        }}
        .explorer-card-grid {{
            display: grid;
            gap: {card_gap};
        }}
        .explorer-card {{
            border-radius: 0.75rem;
            padding: {spacing};
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: rgba(255,255,255,0.85);
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
            transition: transform 120ms ease, box-shadow 120ms ease;
        }}
        .explorer-card:hover {{
            transform: translate3d(0,-2px,0);
            box-shadow: 0 12px 24px rgba(15, 23, 42, 0.12);
        }}
        .explorer-link-btn button {{
            width: 100%;
        }}
        .fade-enter {{
            animation: fadeIn 160ms ease;
        }}
        section.main > div.block-container {{
            padding-top: 0.75rem;
        }}
        section.main {{
            background-color: transparent;
        }}
        section.main > div.block-container::before {{
            content: "";
            display: block;
            height: 0;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translate3d(0, 6px, 0); }}
            to {{ opacity: 1; transform: translate3d(0, 0, 0); }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[key] = True


def chip_html(spec: ChipSpec) -> str:
    tooltip_attr = f" title='{spec.tooltip}'" if spec.tooltip else ""
    source = f"<span class='explorer-chip-source'>{spec.source}</span>" if spec.source else ""
    return (
        f"<span class='explorer-chip' style='background:{spec.color};' {tooltip_attr}>"
        f"<span>{spec.label}</span><span>{spec.value}</span>{source}</span>"
    )


def render_chips(chips: Iterable[ChipSpec]) -> None:
    html = "".join(chip_html(spec) for spec in chips)
    if html:
        st.markdown(f"<div class='explorer-chips fade-enter'>{html}</div>", unsafe_allow_html=True)


def render_shortcut_listener() -> None:
    if st.session_state.get("_explorer_shortcuts_bound"):
        return
    st.session_state["_explorer_shortcuts_bound"] = True
    st.components.v1.html(
        """
        <script>
        (function() {
            const nav = {
                'hc': '#head-coach',
                'ua': '#unabridged',
                'dc': '#draft-chat',
                'ss': '#snapshots',
                'ni': '#nudge-inbox',
                'ec': '#explorer-chat'
            };
            let buffer = '';
            document.addEventListener('keydown', function(ev) {
                if (['INPUT', 'TEXTAREA'].includes(ev.target.tagName)) { return; }
                buffer += ev.key.toLowerCase();
                if (buffer.length > 2) { buffer = buffer.slice(-2); }
                const anchor = nav[buffer];
                if (anchor) {
                    buffer = '';
                    const el = document.querySelector(anchor);
                    if (el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }
                }
            }, {passive: true});
        })();
        </script>
        """,
        height=0,
    )


def render_quick_link_chips() -> None:
    st.markdown(
        """
        <style>
        .chipbar { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin:.25rem 0 .5rem 0 }
        .chipbar a { display:inline-block; text-decoration:none; border-radius:10px; padding:.28rem .65rem;
                     background:rgba(255,255,255,.07); line-height:1.1; white-space:nowrap }
        .chipbar .lbl-wide { display:inline; }
        .chipbar .lbl-abbr { display:none; }
        @media (max-width: 980px){
          .chipbar .lbl-wide { display:none; }
          .chipbar .lbl-abbr { display:inline; }
        }
        </style>
        <div class="chipbar">
          <a href="#head-coach"><span class="lbl-wide">Head Coach</span><span class="lbl-abbr" title="Head Coach">HC</span></a>
          <a href="#unabridged"><span class="lbl-wide">Unabridged</span><span class="lbl-abbr" title="Unabridged">UA</span></a>
          <a href="#draft-chat"><span class="lbl-wide">Draft Chat</span><span class="lbl-abbr" title="Draft Chat">DC</span></a>
          <a href="#snapshots"><span class="lbl-wide">Snapshots</span><span class="lbl-abbr" title="Snapshots">SS</span></a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sticky_header(
    *,
    user_options: List[str],
    active_user: str,
    on_user_change,
    curiosity_mode: Tuple[str, str],
    core_curiosity: Tuple[str, str],
    write_protect: Tuple[bool, str],
    compact: bool,
    extra_chips: Optional[List[ChipSpec]] = None,
    quick_links: Optional[List[Tuple[str, str, str, Optional[str]]]] = None,
    auto_refresh_enabled: bool = True,
    auto_refresh_interval: float = 7.0,
    last_update_ts: Optional[float] = None,
    prefs_error: Optional[str] = None,
    diff_preview: Optional[List[str]] = None,
) -> Dict[str, Any]:
    render_css_once(compact=compact)
    render_shortcut_listener()
    with st.container():
        st.markdown("<div class='explorer-sticky-header'>", unsafe_allow_html=True)
        with st.container():
            cols = st.columns([2, 1, 1, 1])
            with cols[0]:
                selection = st.selectbox(
                    "Active user",
                    options=user_options,
                    index=user_options.index(active_user) if active_user in user_options else 0,
                    key="explorer_header_user_select",
                )
                if selection != active_user:
                    on_user_change(selection)
            with cols[1]:
                st.markdown("**Deep links**")
                render_quick_link_chips()
            with cols[2]:
                st.markdown("**Status**")
                chips = [
                    ChipSpec(
                        label="Curiosity",
                        value=curiosity_mode[0],
                        color="#4e79a7",
                        source=curiosity_mode[1],
                    ),
                    ChipSpec(
                        label="Core curiosity",
                        value=core_curiosity[0],
                        color="#59a14f",
                        source=core_curiosity[1],
                    ),
                    ChipSpec(
                        label="Write-protect",
                        value="on" if write_protect[0] else "off",
                        color="#f28e2b" if write_protect[0] else "#d37295",
                        source=write_protect[1],
                    ),
                ]
                if extra_chips:
                    chips.extend(extra_chips)
                render_chips(chips)
                if prefs_error:
                    st.error(prefs_error)
            with cols[3]:
                st.markdown("**Settings**")
                popover = getattr(st, "popover", None)
                container_ctx = (
                    popover("⚙️ Settings") if callable(popover) else st.expander("⚙️ Settings", expanded=False)
                )
                refresh_clicked = False
                auto_refresh_value = auto_refresh_enabled
                with container_ctx:
                    auto_refresh_value = st.checkbox(
                        f"Auto refresh ({int(auto_refresh_interval)}s)",
                        value=auto_refresh_enabled,
                        key="prefs_auto_refresh_toggle",
                    )
                    refresh_clicked = st.button("Refresh now", key="prefs_refresh_now")
                    if last_update_ts:
                        formatted = datetime.utcfromtimestamp(last_update_ts).strftime("%Y-%m-%d %H:%M:%S")
                        st.caption(f"Last update: {formatted} UTC")
                    if diff_preview:
                        st.caption("Updated keys: " + ", ".join(diff_preview))
        st.markdown("</div>", unsafe_allow_html=True)

    return {
        "auto_refresh": auto_refresh_value,
        "refresh_now": refresh_clicked,
    }


__all__ = [
    "ChipSpec",
    "compact_mode_enabled",
    "reduced_motion_enabled",
    "write_protect_enabled",
    "render_sticky_header",
    "render_css_once",
    "render_chips",
    "chip_html",
    "render_quick_link_chips",
    "inject_hc_chat_css",
    "inject_hc_footer_css",
    "render_hc_footer",
    "inject_hc_flex_css",
]


def inject_hc_chat_css() -> None:
    """Inject base styling for the Head Coach transcript."""

    if st.session_state.get("_hc_chat_css_injected"):
        return

    st.markdown(
        """
        <style>
          section.main > div.block-container {
            padding-bottom: 7.25rem;
          }

          .hc-wrap {
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            min-height: min(82vh, calc(100vh - 5.5rem));
          }

          @supports (height: 100dvh) {
            .hc-wrap {
              min-height: min(82dvh, calc(100dvh - 5.5rem));
            }
          }

          .hc-scroll {
            flex: 1 1 auto;
            overflow-y: auto;
            border: 1px solid rgba(148, 163, 184, 0.32);
            border-radius: 14px;
            padding: 0.85rem 1rem 1.25rem;
            background: rgba(15, 23, 42, 0.12);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
          }

          .hc-scroll::-webkit-scrollbar {
            width: 8px;
          }

          .hc-scroll::-webkit-scrollbar-thumb {
            background: rgba(148, 163, 184, 0.45);
            border-radius: 8px;
          }

          .hc-attachments {
            background: rgba(15, 23, 42, 0.18);
            border: 1px dashed rgba(148, 163, 184, 0.45);
            border-radius: 12px;
            padding: 0.75rem;
          }

          .hc-composer {
            position: fixed;
            left: 50%;
            transform: translateX(-50%);
            bottom: 1.5rem;
            width: min(880px, calc(100% - 2.5rem));
            padding: 0.8rem 1rem;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.38);
            background: rgba(15, 23, 42, 0.92);
            box-shadow: 0 18px 38px rgba(15, 23, 42, 0.48);
            backdrop-filter: blur(6px);
            z-index: 610;
          }

          @media (max-width: 680px){
            .hc-composer {
              width: calc(100% - 1.5rem);
              bottom: 0.75rem;
              padding: 0.75rem;
              border-radius: 14px;
            }
          }

          .hc-composer .hc-row {
            display: flex;
            align-items: center;
            gap: 0.6rem;
          }

          .hc-composer .hc-row .grow {
            flex: 1 1 auto;
          }

          .hc-composer .hc-row .grow input[type="text"] {
            width: 100%;
            border-radius: 999px;
            padding: 0.65rem 1.05rem;
          }

          .hc-composer .stButton button {
            border-radius: 10px;
            padding: 0.55rem 0.85rem;
          }

          .hc-wrap {
            padding-bottom: 7rem;
          }

          @media (max-width: 680px){
            .hc-wrap {
              padding-bottom: 6rem;
            }
          }

          @media (max-width: 900px){
            .hc-wrap {
              min-height: calc(100vh - 6rem);
            }
            @supports (height: 100dvh) {
              .hc-wrap {
                min-height: calc(100dvh - 6rem);
              }
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_hc_chat_css_injected"] = True


def inject_hc_footer_css() -> None:
    """Inject CSS for the pinned Head Coach chat footer."""

    if st.session_state.get("_hc_footer_css_injected"):
        return

    st.markdown(
        """
        <style>
          section.main > div.block-container { padding-bottom: 7.5rem; }
          @media (max-width: 980px){
            section.main > div.block-container { padding-bottom: 8.5rem; }
          }

          .hc-footer {
            position: fixed; left: 0; right: 0; bottom: 0;
            z-index: 999;
            padding: .5rem 1rem;
            border-top: 1px solid rgba(255,255,255,.10);
            background: rgba(10,10,10,.85);
            backdrop-filter: blur(6px);
          }

          .hc-footer .row { display:flex; gap:.5rem; align-items:center; }
          .hc-footer .grow { flex: 1 1 auto; }
          .hc-footer .btn { min-width: 2.4rem; height: 2.4rem; display:flex; align-items:center; justify-content:center;
                            border-radius: 8px; background:rgba(255,255,255,.08); }

          .hc-footer input[type="text"] {
            width: 100%;
            padding: .6rem .75rem;
            border-radius: 8px;
          }

          .hc-chat-scroll {
            height: calc(100vh - 320px - 6.5rem);
            overflow-y: auto;
            padding-right: .25rem;
            margin-bottom: .25rem;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,.08);
          }

          @media (max-width: 980px){
            .hc-chat-scroll {
              height: calc(100vh - 360px - 7.5rem);
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_hc_footer_css_injected"] = True


def render_hc_footer() -> None:
    """Render the fixed Head Coach footer with input, attach, and send controls."""

    ss = st.session_state
    ss.setdefault("hc_footer_text", "")
    ss.setdefault("_hc_footer_submit", False)
    ss.setdefault("_hc_show_uploader", False)

    def _submit_on_enter() -> None:
        ss["_hc_footer_submit"] = True

    st.markdown('<div class="hc-footer"><div class="row">', unsafe_allow_html=True)
    cols = st.columns([12, 1, 1])
    with cols[0]:
        st.text_input(
            "Message the Head Coach…",
            value=ss.get("hc_footer_text", ""),
            key="hc_footer_text",
            label_visibility="collapsed",
            on_change=_submit_on_enter,
        )
    with cols[1]:
        if st.button("📎", help="Attach a file or photo", key="hc_attach_btn_footer"):
            ss["_hc_show_uploader"] = not ss["_hc_show_uploader"]
    with cols[2]:
        if st.button("➤", help="Send", key="hc_send_btn_footer"):
            ss["_hc_footer_submit"] = True
    st.markdown('</div></div>', unsafe_allow_html=True)


def inject_hc_flex_css() -> None:
    """Inject flex layout styles for the Head Coach chat."""

    if st.session_state.get("_hc_flex_css_injected"):
        return

    st.markdown(
        """
        <style>
          section.main > div.block-container {
            padding-bottom: 7.25rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_hc_flex_css_injected"] = True
