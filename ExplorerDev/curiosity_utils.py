"""Utilities for managing curiosity mode and source state in Dev Explorer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import streamlit as st

from ExplorerDev.schema_utils import curiosity_flag_state


@dataclass
class CuriosityModeInfo:
    flag_value: bool
    flag_source: str
    forced: bool
    session_live: bool
    effective_live: bool
    effective_source: str


def resolve_curiosity_mode(
    session_key: str,
    *,
    default_live: Optional[bool] = None,
) -> CuriosityModeInfo:
    """Resolve curiosity mode combining flag sources with session preference."""

    flag_value, flag_source = curiosity_flag_state()
    forced = flag_source == "env"

    if default_live is None:
        default_live = flag_value

    if session_key not in st.session_state:
        st.session_state[session_key] = bool(default_live)

    session_live = bool(st.session_state.get(session_key, default_live))

    if forced:
        session_live = flag_value
        st.session_state[session_key] = flag_value

    # Clamp live mode when the backing flag is disabled
    if not flag_value and not forced:
        session_live = False
        st.session_state[session_key] = False

    effective_live = flag_value if forced else (session_live if flag_value else False)

    if forced:
        effective_source = flag_source
    else:
        baseline = flag_value
        if session_live != baseline:
            effective_source = "session"
        else:
            effective_source = flag_source

    if effective_source not in {"env", "prefs", "session", "default"}:
        effective_source = "default"

    return CuriosityModeInfo(
        flag_value=flag_value,
        flag_source=flag_source,
        forced=forced,
        session_live=session_live,
        effective_live=effective_live,
        effective_source=effective_source,
    )


def curiosity_chip_label(mode_info: CuriosityModeInfo) -> str:
    mode = "live" if mode_info.effective_live else "sim"
    return f"{mode} ({mode_info.effective_source})"

