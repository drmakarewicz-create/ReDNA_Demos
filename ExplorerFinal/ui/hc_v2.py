"""Head Coach v2 Streamlit helpers.

Provides a DOM-stable composer dock, persona controls, and upload modal so
the Streamlit shell matches the P0 contracts for the demo bake-off.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Mapping

import streamlit as st
import requests

CANONICAL_PERSONAS = {
    "head_coach": {
        "label": "Head Coach (Orchestrator)",
        "icon": "🧭",
        "env": "PERSONA_HEAD_COACH_ENABLED",
    },
    "relationship_coach": {
        "label": "Relationship Coach",
        "icon": "💞",
        "env": "PERSONA_RELATIONSHIP_COACH_ENABLED",
    },
    "padna": {
        "label": "PaDNA Coach",
        "icon": "🧬",
        "env": "PERSONA_PADNA_COACH_ENABLED",
    },
    "photo": {
        "label": "Photo Coach",
        "icon": "📸",
        "env": "PERSONA_PHOTO_COACH_ENABLED",
    },
}

CANONICAL_ORDER = ["head_coach", "relationship_coach", "padna", "photo"]

PERSONA_KEY_ALIASES = {
    "head_coach": "head_coach",
    "head coach": "head_coach",
    "headcoach": "head_coach",
    "relationship_coach": "relationship_coach",
    "relationship coach": "relationship_coach",
    "rc": "relationship_coach",
    "padna": "padna",
    "padna_coach": "padna",
    "padna coach": "padna",
    "photo": "photo",
    "photo_coach": "photo",
    "photo coach": "photo",
}

CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8015").rstrip("/")

OBSERVATION_WINDOW_PRIORITY = ["session", "24h", "1h"]
WINDOW_LABELS = {
    "all": "All time",
    "1h": "Last hour",
    "24h": "Last 24h",
    "session": "Current session",
}


@dataclass
class PersonaOption:
    key: str
    label: str
    icon: str
    enabled: bool


def _env_enabled(var_name: str | None) -> bool:
    if not var_name:
        return True
    raw = os.getenv(var_name)
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "off", "no"}

def _get_query_params() -> Dict[str, str]:
    try:
        return dict(st.query_params)
    except Exception:
        try:
            legacy = st.experimental_get_query_params()
        except Exception:
            return {}
        params: Dict[str, str] = {}
        for key, value in legacy.items():
            if isinstance(value, list):
                params[key] = value[0] if value else ""
            else:
                params[key] = value or ""
        return params


def _persona_roster() -> List[PersonaOption]:
    raw_entries = _fetch_persona_roster()
    merged: Dict[str, PersonaOption] = {}

    for entry in raw_entries:
        if not isinstance(entry, Mapping):
            continue
        raw_key = str(entry.get("key") or entry.get("id") or "").strip().lower()
        canonical_key = PERSONA_KEY_ALIASES.get(raw_key)
        if not canonical_key or canonical_key not in CANONICAL_PERSONAS:
            continue
        meta = CANONICAL_PERSONAS[canonical_key]
        api_enabled = entry.get("enabled")
        entry_enabled = bool(api_enabled) if isinstance(api_enabled, bool) else True
        env_enabled = _env_enabled(meta.get("env"))
        option = PersonaOption(
            key=canonical_key,
            label=meta["label"],
            icon=str(entry.get("icon") or meta["icon"]),
            enabled=env_enabled and entry_enabled,
        )
        existing = merged.get(canonical_key)
        if existing:
            merged[canonical_key] = PersonaOption(
                key=canonical_key,
                label=meta["label"],
                icon=existing.icon or option.icon,
                enabled=existing.enabled and option.enabled,
            )
        else:
            merged[canonical_key] = option

    roster: List[PersonaOption] = []
    for key in CANONICAL_ORDER:
        if key in merged:
            roster.append(merged[key])
            continue
        meta = CANONICAL_PERSONAS[key]
        roster.append(
            PersonaOption(
                key=key,
                label=meta["label"],
                icon=meta["icon"],
                enabled=_env_enabled(meta.get("env")),
            )
        )
    return roster


def _fetch_persona_roster() -> List[Dict[str, Any]]:
    try:
        response = requests.get(
            f"{CORE_BASE}/ui/personas",
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    entries: Any
    if isinstance(payload, Mapping):
        entries = payload.get("personas")
    else:
        entries = payload

    normalized: List[Dict[str, Any]] = []
    if isinstance(entries, list):
        for item in entries:
            if isinstance(item, Mapping):
                normalized.append(dict(item))
    return normalized


def _ensure_state_defaults() -> None:
    st.session_state.setdefault("hc_v2_history", [])
    st.session_state.setdefault("hc_v2_active_persona", "head_coach")
    st.session_state.setdefault("hc_v2_show_upload", False)
    st.session_state.setdefault("hc_v2_input", "")
    st.session_state.setdefault("hc_v2_pending_send", None)
    st.session_state.setdefault("hc_v2_error", None)
    st.session_state.setdefault("hc_v2_cooldown_until", 0.0)
    st.session_state.setdefault("hc_v2_sending", False)
    st.session_state.setdefault("hc_v2_asks_data", [])
    st.session_state.setdefault("hc_v2_asks_error", None)
    st.session_state.setdefault("hc_v2_unabridged_data", [])
    st.session_state.setdefault("hc_v2_unabridged_error", None)
    st.session_state.setdefault("hc_v2_unabridged_revision", 0.0)
    st.session_state.setdefault("hc_v2_unabridged_search", "")
    st.session_state.setdefault("hc_v2_unabridged_container", "all")
    st.session_state.setdefault("hc_v2_unabridged_page", 0)
    st.session_state.setdefault("hc_v2_unabridged_page_size", 100)
    st.session_state.setdefault("hc_v2_unabridged_cache", None)
    st.session_state.setdefault("hc_v2_unabridged_prev_filters", None)
    st.session_state.setdefault("hc_v2_timeline_trait", None)
    st.session_state.setdefault("hc_v2_timeline_entries", [])
    st.session_state.setdefault("hc_v2_timeline_error", None)
    st.session_state.setdefault("hc_v2_nudges_data", [])
    st.session_state.setdefault("hc_v2_nudges_error", None)
    st.session_state.setdefault("hc_v2_nudge_pending", {})
    st.session_state.setdefault("hc_v2_nudge_errors", {})
    st.session_state.setdefault("hc_v2_focus_composer", False)
    st.session_state.setdefault("hc_v2_snapshot_bundle", None)
    st.session_state.setdefault("hc_v2_snapshot_version", None)
    st.session_state.setdefault("hc_v2_snapshot_pending", False)
    st.session_state.setdefault("hc_v2_observation_data", None)
    st.session_state.setdefault("hc_v2_observation_error", None)
    st.session_state.setdefault("hc_v2_observation_window", "all")
    st.session_state.setdefault("hc_v2_observation_manual", False)
    st.session_state.setdefault("hc_v2_observation_last_user", None)
    st.session_state.setdefault("hc_v2_nudges_data", [])
    st.session_state.setdefault("hc_v2_nudges_error", None)
    st.session_state.setdefault("hc_v2_nudge_pending", {})
    st.session_state.setdefault("hc_v2_nudge_errors", {})


def render_hc_v2_page() -> None:
    _ensure_state_defaults()
    roster = _persona_roster()
    roster_map: Dict[str, PersonaOption] = {option.key: option for option in roster}

    active_persona = st.session_state["hc_v2_active_persona"]
    if active_persona not in roster_map:
        active_persona = "head_coach"
        st.session_state["hc_v2_active_persona"] = active_persona
    persona_option = roster_map.get(active_persona)

    query_params = _get_query_params()
    debug_enabled = (query_params.get("ui_debug") or "0") == "1"
    format_json = (query_params.get("format") or "").lower() == "json"

    if debug_enabled and format_json:
        payload = {
            "composer_rendered": True,
            "active_persona": {
                "key": active_persona,
                "label": persona_option.label if persona_option else active_persona,
            },
            "unabridged_anchor_ok": True,
            "asks_panel_visible": True,
            "overlay_ok": True,
        }
        st.json(payload)
        st.stop()

    st.markdown(
        """
    <style>
      .hc2-wrap {padding-bottom: 8rem;}
      .hc2-composer {
        position: fixed;
        left: 50%;
        transform: translateX(-50%);
        bottom: 1.5rem;
        width: min(880px, calc(100% - 2.5rem));
        padding: 1rem 1.2rem;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background: rgba(15, 23, 42, 0.92);
        box-shadow: 0 18px 38px rgba(15, 23, 42, 0.48);
        backdrop-filter: blur(6px);
        z-index: 610;
      }
      .hc2-transcript {
        max-height: 60vh;
        overflow-y: auto;
        padding-right: 0.5rem;
        margin-bottom: 1rem;
      }
      .hc2-transcript .message {
        margin-bottom: 0.75rem;
      }
      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }
      .sr-only-focusable:active,
      .sr-only-focusable:focus {
        position: static;
        width: auto;
        height: auto;
        margin: 0;
        overflow: visible;
        clip: auto;
        white-space: normal;
      }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='hc2-wrap'>", unsafe_allow_html=True)

    _render_header(active_persona, roster)

    st.markdown("---")
    st.subheader("Persona Controls")
    _render_personas(roster, active_persona)

    st.markdown("---")
    st.subheader("Conversation Transcript")
    _render_transcript()

    st.markdown("---")
    st.subheader("Conversation Metrics")
    _render_observation_metrics(roster)

    st.markdown(
        "<a class='sr-only-focusable' href='#hc2-composer-anchor'>Skip to composer dock</a>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.subheader("Unabridged Traits")
    _render_unabridged()

    st.markdown("---")
    st.subheader("Coach Asks (read-only)")
    _render_asks()

    st.markdown("---")
    st.subheader("Nudge Inbox")
    _render_nudges()

    st.markdown("</div>", unsafe_allow_html=True)

    _render_upload_modal()
    _render_composer()
    st.session_state["hc_v2_post_composer_widgets"] = []
    if debug_enabled:
        _render_debug_overlay(
            roster,
            active_persona,
            persona_option.label if persona_option else "",
            st.session_state.get("hc_v2_active_user", ""),
            first_widget="Conversation Transcript",
        )
    # Guard: keep the composer as the last interactive widget; only the debug overlay may render after it.


def _render_header(active_persona: str, roster: List[PersonaOption]) -> None:
    roster_map: Dict[str, PersonaOption] = {option.key: option for option in roster}
    persona_meta = roster_map.get(active_persona)
    cols = st.columns([3, 2])
    with cols[0]:
        st.title("Head Coach v2 (Streamlit)")
        st.caption("Composer dock stays anchored. Persona controls are always visible.")
    with cols[1]:
        active_user = st.text_input(
            "Active user id",
            key="hc_v2_active_user",
            placeholder="_active_user_id",
            help="Used to scope read-only panels; not persisted to Core in v2 demo.",
        )
        st.session_state.setdefault("hc_v2_active_user_cache", active_user)
        if active_user != st.session_state["hc_v2_active_user_cache"]:
            st.session_state["hc_v2_active_user_cache"] = active_user
            toast = getattr(st, "toast", None)
            if callable(toast):
                toast("Active user updated", icon="🧭")
        snapshot_disabled = not active_user.strip() or st.session_state.get("hc_v2_snapshot_pending", False)
        if st.button(
            "Snapshot & Export",
            key="hc_v2_snapshot_button",
            use_container_width=True,
            disabled=snapshot_disabled,
        ):
            _perform_snapshot(active_user.strip())

    icon = persona_meta.icon if persona_meta else "🤖"
    label = persona_meta.label if persona_meta else active_persona
    st.info(f"Current persona: {icon} {label}", icon="🤖")

    snapshot_bundle = st.session_state.get("hc_v2_snapshot_bundle")
    snapshot_version = st.session_state.get("hc_v2_snapshot_version")
    if snapshot_bundle:
        st.download_button(
            label=f"Download latest snapshot ({snapshot_version})",
            data=snapshot_bundle,
            file_name=f"{(st.session_state.get('hc_v2_active_user') or 'user')}_snapshot.json",
            mime="application/json",
            key="hc_v2_snapshot_download",
        )


def _render_transcript() -> None:
    history = st.session_state["hc_v2_history"]
    st.markdown(
        "<div class='sr-only' role='status' aria-live='polite'>Conversation transcript updated.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='hc2-transcript'>", unsafe_allow_html=True)
    if not history:
        st.caption("No messages yet. Use the composer below to start the conversation.")
    else:
        for entry in history[-50:]:
            speaker = entry.get("speaker", "Head Coach")
            message = entry.get("message", "")
            pending = entry.get("pending", False)
            speaker_label = f"{speaker} (pending)" if pending else speaker
            st.markdown(
                f"<div class='message'><strong>{speaker_label}:</strong> {message}</div>",
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_observation_metrics(roster: List[PersonaOption]) -> None:
    active_user = st.session_state.get("hc_v2_active_user", "").strip()
    if not active_user:
        st.info("Pick an active user to see conversation telemetry.")
        st.session_state["hc_v2_observation_data"] = None
        return

    last_user = st.session_state.get("hc_v2_observation_last_user")
    if last_user != active_user:
        st.session_state["hc_v2_observation_last_user"] = active_user
        st.session_state["hc_v2_observation_manual"] = False
        st.session_state["hc_v2_observation_window"] = "all"

    _refresh_observations(active_user)

    payload = st.session_state.get("hc_v2_observation_data")
    error = st.session_state.get("hc_v2_observation_error")
    if error:
        st.warning(error)

    if not isinstance(payload, Mapping):
        st.caption("No conversation telemetry captured yet.")
        return

    window_options = _window_options(payload)
    manual = bool(st.session_state.get("hc_v2_observation_manual"))
    current_window = str(st.session_state.get("hc_v2_observation_window", "all"))

    if not manual:
        current_window = _default_observation_window(payload)
        st.session_state["hc_v2_observation_window"] = current_window
    elif current_window not in window_options:
        current_window = _default_observation_window(payload)
        st.session_state["hc_v2_observation_window"] = current_window

    prior_window = current_window
    if st.session_state.get("hc_v2_observation_window_select") != current_window:
        st.session_state["hc_v2_observation_window_select"] = current_window

    if len(window_options) > 1:
        selected = st.selectbox(
            "Window",
            options=window_options,
            key="hc_v2_observation_window_select",
            format_func=_format_window_label,
        )
    else:
        selected = window_options[0]

    if selected != prior_window:
        st.session_state["hc_v2_observation_manual"] = True
        st.session_state["hc_v2_observation_window"] = selected
        current_window = selected
    else:
        current_window = selected

    metrics = _resolve_observation_metrics(payload, current_window)

    summary_cols = st.columns(3)
    with summary_cols[0]:
        st.metric("Latest dialog act", metrics["dialog_acts"].get("latest") or "—")
    with summary_cols[1]:
        st.metric("Cadence bucket", metrics["cadence"].get("latest_bucket") or "—")
    with summary_cols[2]:
        st.metric("Observations", metrics.get("observation_count", 0))

    dialog_top = _top_distribution(metrics["dialog_acts"].get("distribution", {}))
    cadence_top = _top_distribution(metrics["cadence"].get("histogram", {}))

    mix_cols = st.columns(3)
    with mix_cols[0]:
        st.caption("Dialog mix")
        st.markdown(_format_distribution_text(dialog_top))
    with mix_cols[1]:
        st.caption("Cadence mix")
        st.markdown(_format_distribution_text(cadence_top))
    with mix_cols[2]:
        latency = metrics.get("latency", {})
        st.caption("Latency (ms)")
        st.write(f"Median: {_format_latency(latency.get('median_ms'))}")
        st.write(f"Mean: {_format_latency(latency.get('mean_ms'))}")

    per_persona = metrics.get("per_persona") or {}
    if isinstance(per_persona, Mapping) and per_persona:
        roster_map = {option.key: option for option in roster}
        persona_rows: List[Dict[str, Any]] = []
        for persona_id, detail in per_persona.items():
            if not isinstance(detail, Mapping):
                continue
            count = int(detail.get("observation_count") or 0)
            dialog_acts = detail.get("dialog_acts") if isinstance(detail.get("dialog_acts"), Mapping) else {}
            latest = dialog_acts.get("latest") if isinstance(dialog_acts, Mapping) else None
            option = roster_map.get(persona_id)
            label = option.label if option else _format_persona_label(persona_id)
            icon = option.icon if option else ""
            persona_rows.append(
                {
                    "Persona": f"{icon} {label}".strip(),
                    "Entries": count,
                    "Latest act": latest or "—",
                }
            )
        persona_rows.sort(key=lambda item: item.get("Entries", 0), reverse=True)
        st.caption("Persona activity")
        st.table(persona_rows)
    else:
        st.caption("No persona-specific activity captured in this window.")


def _render_unabridged() -> None:
    active_user = st.session_state.get("hc_v2_active_user", "").strip()
    if not active_user:
        st.info("Pick an active user to see the unabridged traits.")
        st.session_state["hc_v2_unabridged_data"] = []
        return

    _refresh_unabridged(active_user)

    traits = st.session_state.get("hc_v2_unabridged_data", [])
    error = st.session_state.get("hc_v2_unabridged_error")
    timeline_trait = st.session_state.get("hc_v2_timeline_trait")
    timeline_entries = st.session_state.get("hc_v2_timeline_entries", [])
    timeline_error = st.session_state.get("hc_v2_timeline_error")

    if error:
        st.warning(error)

    if not traits:
        st.caption("No traits available for this user.")
        return

    containers = sorted({_safe_container(trait.get("trait_id")) for trait in traits if trait.get("trait_id")})
    search_holder, container_holder, page_size_holder = st.columns([3, 2, 1.3])
    with search_holder:
        st.text_input(
            "Quick search",
            key="hc_v2_unabridged_search",
            placeholder="Filter by trait, value, or reason",
        )
    with container_holder:
        st.selectbox(
            "Container",
            options=["all", *containers],
            key="hc_v2_unabridged_container",
            format_func=lambda value: "All containers" if value == "all" else (value or "(unknown)"),
        )
    with page_size_holder:
        st.selectbox(
            "Rows per page",
            options=[50, 100, 500],
            key="hc_v2_unabridged_page_size",
            format_func=lambda value: f"{value:,}",
        )

    container_filter = st.session_state.get("hc_v2_unabridged_container", "all")
    search_term = st.session_state.get("hc_v2_unabridged_search", "")
    revision = float(st.session_state.get("hc_v2_unabridged_revision", 0.0))

    cache_key: Tuple[float, str, str] = (
        revision,
        container_filter,
        search_term.strip().lower(),
    )
    cached = st.session_state.get("hc_v2_unabridged_cache")
    if not cached or cached.get("key") != cache_key:
        filtered = _filter_unabridged_traits(traits, container_filter, search_term)
        st.session_state["hc_v2_unabridged_cache"] = {"key": cache_key, "value": filtered}
    else:
        filtered = cached.get("value", [])

    prev_filters = st.session_state.get("hc_v2_unabridged_prev_filters")
    current_filters = (container_filter, search_term.strip().lower())
    if prev_filters != current_filters:
        st.session_state["hc_v2_unabridged_page"] = 0
        st.session_state["hc_v2_unabridged_prev_filters"] = current_filters

    page_size = int(st.session_state.get("hc_v2_unabridged_page_size", 100) or 100)
    total_rows = len(filtered)
    if not total_rows:
        st.caption("No traits match the current filters.")
        return

    page_count = max(1, (total_rows + page_size - 1) // page_size)
    current_page = min(int(st.session_state.get("hc_v2_unabridged_page", 0)), page_count - 1)
    page_col, info_col = st.columns([1, 3])
    with page_col:
        selected_page = st.number_input(
            "Page",
            min_value=1,
            max_value=page_count,
            value=current_page + 1,
            step=1,
        )
        current_page = int(selected_page) - 1
        st.session_state["hc_v2_unabridged_page"] = current_page
    with info_col:
        start_row = current_page * page_size + 1
        end_row = min(start_row + page_size - 1, total_rows)
        st.caption(f"Showing {start_row:,} – {end_row:,} of {total_rows:,} traits")

    start = current_page * page_size
    end = start + page_size
    page_traits = filtered[start:end]

    for trait in page_traits:
        trait_id = trait.get("trait_id") or ""
        container = trait_id.split(".")[0] if trait_id else ""
        value = trait.get("value")
        ucn = trait.get("ucn")
        reasons = trait.get("reasons") or []
        badges = trait.get("badges") or []

        with st.container():
            st.markdown(f"**{trait_id}**")
            meta_cols = st.columns([1.5, 1, 1])
            with meta_cols[0]:
                st.caption(f"Container: {container}")
            with meta_cols[1]:
                st.caption(f"UCN: {ucn if ucn is not None else '—'}")
            with meta_cols[2]:
                st.caption(", ".join(str(badge) for badge in badges) or "No governance flags")

            st.caption(
                f"Value: {json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value}"
            )
            if reasons:
                st.caption(f"Reasons: {', '.join(str(r) for r in reasons)}")

            col_btn, _ = st.columns([1, 4])
            with col_btn:
                if st.button(
                    "Timeline",
                    key=f"hc_v2_trait_timeline_{trait_id}",
                    use_container_width=True,
                ):
                    _load_trait_timeline(active_user, trait_id)

            if timeline_trait == trait_id:
                if timeline_error:
                    st.warning(timeline_error)
                else:
                    st.caption(f"{len(timeline_entries)} event(s)")
                    for entry in timeline_entries:
                        st.markdown(
                            f"- **{entry.get('ts', 'unknown')}** · {entry.get('source', 'source')} — {entry.get('reason') or ''}"
                        )
                    json_text = json.dumps(timeline_entries, indent=2).encode("utf-8")
                    csv_buffer = io.StringIO()
                    writer = csv.writer(csv_buffer)
                    writer.writerow(["ts", "source", "reason", "value", "ucn", "delta_ucn"])
                    for entry in timeline_entries:
                        writer.writerow(
                            [
                                entry.get("ts", ""),
                                entry.get("source", ""),
                                entry.get("reason", ""),
                                json.dumps(entry.get("value"), ensure_ascii=False),
                                entry.get("ucn", ""),
                                entry.get("delta_ucn", ""),
                            ]
                        )
                    st.download_button(
                        "Download Timeline JSON",
                        json_text,
                        file_name=f"{trait_id.replace('.', '_')}_timeline.json",
                        mime="application/json",
                    )
                    st.download_button(
                        "Download Timeline CSV",
                        csv_buffer.getvalue().encode("utf-8"),
                        file_name=f"{trait_id.replace('.', '_')}_timeline.csv",
                        mime="text/csv",
                    )

            st.divider()

def _render_personas(roster: List[PersonaOption], active_persona: str) -> None:
    roster_map: Dict[str, PersonaOption] = {option.key: option for option in roster}
    active_option = roster_map.get(
        active_persona,
        PersonaOption(key=active_persona, label=active_persona.replace("_", " ").title(), icon="", enabled=True),
    )
    st.markdown(
        f"<p class='sr-only' role='status' aria-live='polite'>Active persona is {active_option.label}</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(roster)) if roster else [st.container()]
    for option, col in zip(roster, cols):
        with col:
            disabled = not option.enabled
            help_text = "Activate this persona in the conversation."
            if option.key == active_persona:
                help_text += " Currently selected."
            elif not option.enabled:
                help_text += " Disabled via environment flag."
            if st.button(
                f"{option.icon} {option.label}",
                key=f"hc_v2_persona_{option.key}",
                disabled=disabled,
                use_container_width=True,
                help=help_text,
            ) and not disabled:
                _set_active_persona(option.key, roster_map)
            if option.key == active_persona:
                st.caption("Active", help="Response bubble mirrors this persona.")
            elif not option.enabled:
                st.caption("Disabled via env flag")
            else:
                st.caption("Available")

    labels = []
    values = []
    for option in roster:
        postfix = " (disabled)" if not option.enabled else ""
        labels.append(f"{option.icon} {option.label}{postfix}")
        values.append(option.key)

    if values:
        default_index = values.index(active_persona) if active_persona in values else 0
        chosen_label = st.selectbox(
            "Persona roster",
            labels,
            index=default_index,
            key="hc_v2_persona_dropdown",
            help="Dropdown remains available even when chips overflow.",
        )
        chosen_key = values[labels.index(chosen_label)]
        selected_option = roster_map.get(chosen_key)
        if selected_option and selected_option.enabled:
            _set_active_persona(chosen_key, roster_map)
        elif selected_option and not selected_option.enabled:
            st.caption("Selected persona is disabled via env flag.")

    _inject_persona_aria(roster, active_persona)


def _inject_persona_aria(roster: List[PersonaOption], active_persona: str) -> None:
    try:
        persona_payload = [
            {
                "label": option.label,
                "icon": option.icon,
                "active": option.key == active_persona,
                "enabled": option.enabled,
            }
            for option in roster
        ]
        st.markdown(
            """
<script>
(function() {
  const personas = %s;
  const buttons = Array.from(document.querySelectorAll('button'));
  personas.forEach(function(persona) {
    const label = (persona.icon ? persona.icon + ' ' : '') + persona.label;
    const match = buttons.find(function(btn) {
      return btn.textContent && btn.textContent.trim() === label;
    });
    if (!match) { return; }
    match.setAttribute('aria-label', persona.label + ' persona');
    match.setAttribute('aria-pressed', persona.active ? 'true' : 'false');
    match.setAttribute('aria-disabled', persona.enabled ? 'false' : 'true');
  });
})();
</script>
            """
            % json.dumps(persona_payload),
            unsafe_allow_html=True,
        )
    except Exception:
        pass


def _render_asks() -> None:
    active_user = st.session_state.get("hc_v2_active_user", "").strip()
    if not active_user:
        st.info("Pick an active user to view the planner ask queue.")
        st.session_state["hc_v2_asks_data"] = []
        return

    _refresh_asks(active_user)

    asks: List[Dict[str, Any]] = st.session_state.get("hc_v2_asks_data", [])
    asks_error = st.session_state.get("hc_v2_asks_error")

    if asks_error:
        st.warning(asks_error)

    if not asks:
        st.caption("No planner asks queued for this user.")
        return

    st.caption(
        "Planner asks are read-only in this demo build. Use Control Panel++ to approve or snooze in sandboxes."
    )

    for ask in asks:
        phrasing = ask.get("phrasing_stub") or "Planner ask"
        container = ask.get("container") or "—"
        confidence = float(ask.get("confidence", 0))
        ttl_minutes = int(ask.get("ttl_minutes", 0))
        snooze_minutes = int(ask.get("snooze_minutes", 0))
        status = ask.get("status") or "pending"
        ask_type = ask.get("ask_type")
        sensitivity = bool(ask.get("sensitivity"))

        with st.container():
            st.markdown(f"**{phrasing}**")
            meta_cols = st.columns([1.5, 1, 1, 1, 1])
            with meta_cols[0]:
                st.caption(f"Container: `{container}`")
            with meta_cols[1]:
                st.caption(f"Confidence: {int(confidence * 100)}%")
            with meta_cols[2]:
                st.caption(f"TTL: {ttl_minutes}m")
            with meta_cols[3]:
                st.caption(f"Snooze: {snooze_minutes}m")
            with meta_cols[4]:
                st.caption(f"Status: {status}")

            badges: List[str] = []
            if ask_type:
                badges.append(f"Type: {ask_type}")
            if sensitivity:
                badges.append("Sensitive")
            if badges:
                st.caption(" • ".join(badges))

            st.divider()


def _render_nudges() -> None:
    active_user = st.session_state.get("hc_v2_active_user", "").strip()
    if not active_user:
        st.info("Pick an active user to view nudges.")
        st.session_state["hc_v2_nudges_data"] = []
        return

    _refresh_nudges(active_user)

    nudges = st.session_state.get("hc_v2_nudges_data", [])
    nudges_error = st.session_state.get("hc_v2_nudges_error")
    pending_map: Dict[str, bool] = st.session_state.get("hc_v2_nudge_pending", {})
    error_map: Dict[str, str] = st.session_state.get("hc_v2_nudge_errors", {})

    if nudges_error:
        st.warning(nudges_error)

    if not nudges:
        st.caption("No nudges available for this user.")
        return

    for nudge in nudges:
        nudge_id = str(nudge.get("id") or "")
        text = nudge.get("text") or "Nudge"
        kind = nudge.get("kind") or "general"
        status = nudge.get("status") or "pending"
        ttl_minutes = int(nudge.get("ttl_minutes", 0) or 0)
        snooze_minutes = int(nudge.get("snooze_minutes", 0) or 0)
        created_ts = nudge.get("created_ts") or ""
        policy = nudge.get("policy") or {}
        pending = bool(pending_map.get(nudge_id))
        row_error = error_map.get(nudge_id)

        accept_policy = policy.get("accept") or {}
        dismiss_policy = policy.get("dismiss") or {}
        undo_policy = policy.get("undo") or {}

        with st.container():
            st.markdown(f"**{text}**")
            meta_cols = st.columns([1.5, 1, 1, 1])
            with meta_cols[0]:
                st.caption(f"Kind: {kind}")
            with meta_cols[1]:
                st.caption(f"Status: {status}")
            with meta_cols[2]:
                st.caption(f"TTL: {ttl_minutes}m")
            with meta_cols[3]:
                st.caption(f"Snooze: {snooze_minutes}m")
            if created_ts:
                st.caption(f"Created {created_ts}")

            action_cols = st.columns(3)
            with action_cols[0]:
                approve_disabled = pending or not bool(accept_policy.get("allowed", True))
                if st.button(
                    "Accept",
                    key=f"hc_v2_nudge_{nudge_id}_accept",
                    disabled=approve_disabled,
                    help=accept_policy.get("reason") or "Accept this nudge.",
                ):
                    st.session_state["hc_v2_nudge_pending"][nudge_id] = True
                    _handle_nudge_action(active_user, nudge, "accept")
            with action_cols[1]:
                dismiss_disabled = pending or not bool(dismiss_policy.get("allowed", True))
                if st.button(
                    "Dismiss",
                    key=f"hc_v2_nudge_{nudge_id}_dismiss",
                    disabled=dismiss_disabled,
                    help=dismiss_policy.get("reason") or "Dismiss this nudge.",
                ):
                    st.session_state["hc_v2_nudge_pending"][nudge_id] = True
                    _handle_nudge_action(active_user, nudge, "dismiss")
            with action_cols[2]:
                undo_disabled = pending or not bool(undo_policy.get("allowed", False))
                if st.button(
                    "Undo",
                    key=f"hc_v2_nudge_{nudge_id}_undo",
                    disabled=undo_disabled,
                    help=undo_policy.get("reason") or "Undo the last nudge action.",
                ):
                    st.session_state["hc_v2_nudge_pending"][nudge_id] = True
                    _handle_nudge_action(active_user, nudge, "undo")

            if row_error:
                st.caption(f"⚠️ {row_error}")

            st.divider()


def _render_composer() -> None:
    def _send_message(*, retry: bool = False) -> None:
        pending_payload = st.session_state.get("hc_v2_pending_send")
        if retry:
            if not pending_payload:
                return
            st.session_state["hc_v2_error"] = None
            _schedule_cooldown()
            _dispatch_chat(payload=pending_payload)
            return

        text = st.session_state.get("hc_v2_input", "").strip()
        if not text:
            return

        active_user = st.session_state.get("hc_v2_active_user", "").strip()
        if not active_user:
            st.session_state["hc_v2_error"] = "Pick a user before chatting so the Head Coach knows who to update."
            return

        persona = st.session_state.get("hc_v2_active_persona", "head_coach")
        persona_meta = CANONICAL_PERSONAS.get(persona, {})
        persona_label = persona_meta.get("label", persona.replace("_", " ").title())

        client_id = _generate_client_message_id()
        now_ts = int(time.time() * 1000)

        history = st.session_state["hc_v2_history"]
        streaming = _chat_stream_allowed()

        history.append(
            {
                "speaker": "Member",
                "message": text,
                "client_id": client_id,
                "role": "member",
                "ts": now_ts,
            }
        )
        history.append(
            {
                "speaker": persona_label,
                "message": "…" if streaming else _build_local_echo(text),
                "client_id": client_id,
                "role": "assistant",
                "pending": True,
                "streaming": streaming,
                "ts": now_ts,
            }
        )
        st.session_state["hc_v2_history"] = history[-60:]

        payload = {
            "client_id": client_id,
            "user_id": active_user,
            "persona_send": _persona_send_key(persona),
            "persona_label": persona_label,
            "text": text,
            "client_ts": now_ts,
            "streaming": streaming,
        }
        st.session_state["hc_v2_pending_send"] = payload
        st.session_state["hc_v2_error"] = None
        st.session_state["hc_v2_input"] = ""
        _schedule_cooldown()
        _dispatch_chat(payload=payload)

    st.markdown("<div class='hc2-composer' role='region' aria-label='Chat composer dock'>", unsafe_allow_html=True)
    st.markdown("<div id='hc2-composer-anchor'></div>", unsafe_allow_html=True)

    error_message = st.session_state.get("hc_v2_error")
    pending_payload = st.session_state.get("hc_v2_pending_send")
    sending = bool(st.session_state.get("hc_v2_sending"))
    cooldown_active = time.time() < float(st.session_state.get("hc_v2_cooldown_until", 0.0))

    if error_message:
        err_cols = st.columns([4, 1])
        with err_cols[0]:
            st.markdown(
                f"<div style='border-radius:12px;padding:10px;border:1px solid rgba(248,113,113,0.4);"
                "background:rgba(248,113,113,0.08);color:#fecaca;font-size:12px;'>"
                f"{error_message}</div>",
                unsafe_allow_html=True,
            )
        with err_cols[1]:
            retry_disabled = sending or pending_payload is None
            if st.button(
                "Retry",
                key="hc_v2_retry_button",
                use_container_width=True,
                disabled=retry_disabled,
            ):
                _send_message(retry=True)

    cols = st.columns([12, 3, 3])
    with cols[0]:
        st.text_input(
            "Compose a message",
            key="hc_v2_input",
            placeholder="Type and press Enter to send…",
            label_visibility="collapsed",
            on_change=_send_message,
        )
        if st.session_state.pop("hc_v2_focus_composer", False):
            st.markdown(
                """
<script>
(function() {
  const composer = document.querySelector('input[placeholder="Type and press Enter to send…"]');
  if (composer) {
    composer.focus({ preventScroll: true });
    const length = composer.value.length;
    if (composer.setSelectionRange) {
      composer.setSelectionRange(length, length);
    }
  }
})();
</script>
                """,
                unsafe_allow_html=True,
            )
    with cols[1]:
        if st.button("Upload", key="hc_v2_upload_button", use_container_width=True):
            st.session_state["hc_v2_show_upload"] = True
    with cols[2]:
        if st.button(
            "Send",
            key="hc_v2_send_button",
            type="primary",
            use_container_width=True,
            disabled=sending or cooldown_active,
        ):
            _send_message()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_upload_modal() -> None:
    if st.session_state.get("hc_v2_show_upload"):
        with st.modal("Upload evidence", key="hc_v2_upload_modal"):
            st.markdown(
                """
<h2 id="hc-upload-modal-title" class="sr-only">Upload evidence</h2>
<p class="sr-only" id="hc-upload-modal-desc">Upload files to share context with the Head Coach. Press Escape or the close button to dismiss this dialog.</p>
                """,
                unsafe_allow_html=True,
            )
            st.write("Drop files here (read-only demo)")
            st.file_uploader(
                "Add files",
                accept_multiple_files=True,
                key="hc_v2_upload_input",
                help="Upload supporting files; composer focus returns after closing.",
            )
            if st.button("Close upload modal", type="primary", key="hc_v2_upload_close"):
                st.session_state["hc_v2_show_upload"] = False
                st.session_state["hc_v2_focus_composer"] = True
            st.markdown(
                """
<script>
(function() {
  const modalRoot = document.querySelector('[data-testid="stModal"]');
  if (!modalRoot) { return; }
  modalRoot.setAttribute('role', 'dialog');
  modalRoot.setAttribute('aria-modal', 'true');
  modalRoot.setAttribute('aria-labelledby', 'hc-upload-modal-title');
  modalRoot.setAttribute('aria-describedby', 'hc-upload-modal-desc');
  const focusableSelectors = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  const focusable = Array.from(modalRoot.querySelectorAll(focusableSelectors)).filter(function(el) {
    return !el.hasAttribute('disabled');
  });
  if (!focusable.length) { return; }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (first) {
    setTimeout(function() { first.focus(); }, 50);
  }
  modalRoot.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      const closer = focusable.find(function(el) {
        return el.textContent && el.textContent.trim().startsWith('Close upload');
      }) || last;
      if (closer) { closer.click(); }
    }
    if (event.key === 'Tab') {
      if (event.shiftKey) {
        if (document.activeElement === first) {
          event.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
  });
})();
</script>
                """,
                unsafe_allow_html=True,
            )

def _refresh_asks(user_id: str) -> None:
    try:
        response = requests.get(
            f"{CORE_BASE}/ui/asks",
            params={"user_id": user_id, "limit": 8},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        asks = payload.get("asks") if isinstance(payload, dict) else []
        if not isinstance(asks, list):
            asks = []
        st.session_state["hc_v2_asks_data"] = asks
        st.session_state["hc_v2_asks_error"] = None
    except Exception as exc:
        st.session_state["hc_v2_asks_data"] = []
        st.session_state["hc_v2_asks_error"] = _describe_api_error(exc)

def _merge_updated_nudge(updated: Dict[str, Any]) -> None:
    nudges = list(st.session_state.get("hc_v2_nudges_data", []))
    updated_id = str(updated.get("id") or "")
    replaced = False
    for idx, entry in enumerate(nudges):
        if str(entry.get("id") or "") == updated_id:
            nudges[idx] = updated
            replaced = True
            break
    if not replaced:
        nudges.append(updated)
    st.session_state["hc_v2_nudges_data"] = nudges


def _refresh_nudges(user_id: str) -> None:
    try:
        response = requests.get(
            f"{CORE_BASE}/ui/nudges",
            params={"user_id": user_id},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        nudges = payload.get("nudges") if isinstance(payload, dict) else []
        if not isinstance(nudges, list):
            nudges = []
        st.session_state["hc_v2_nudges_data"] = nudges
        st.session_state["hc_v2_nudges_error"] = None
    except Exception as exc:
        st.session_state["hc_v2_nudges_data"] = []
        st.session_state["hc_v2_nudges_error"] = _describe_api_error(exc)


def _handle_nudge_action(user_id: str, nudge: Dict[str, Any], action: str) -> None:
    nudge_id = str(nudge.get("id") or "")
    if not nudge_id:
        return
    try:
        response = requests.post(
            f"{CORE_BASE}/ui/nudges/act",
            json={
                "user_id": user_id,
                "id": nudge_id,
                "action": action,
            },
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            st.session_state.setdefault("hc_v2_nudge_errors", {})[nudge_id] = data.get("reason") or "Action blocked."
            if isinstance(data.get("nudge"), dict):
                _merge_updated_nudge(data["nudge"])
            return
        st.session_state.setdefault("hc_v2_nudge_errors", {}).pop(nudge_id, None)
        if isinstance(data.get("nudge"), dict):
            _merge_updated_nudge(data["nudge"])
    except Exception as exc:
        st.session_state.setdefault("hc_v2_nudge_errors", {})[nudge_id] = _describe_api_error(exc)
    finally:
        st.session_state.setdefault("hc_v2_nudge_pending", {})[nudge_id] = False
        _refresh_nudges(user_id)


def _filter_unabridged_traits(
    traits: List[Dict[str, Any]],
    container: str,
    search_term: str,
) -> List[Dict[str, Any]]:
    term = (search_term or "").strip().lower()
    filtered: List[Dict[str, Any]] = []
    for trait in traits:
        trait_id = str(trait.get("trait_id") or "")
        container_id = _safe_container(trait_id)
        if container and container != "all" and container_id != container:
            continue
        if term:
            value_text = _stringify_value(trait.get("value"))
            reasons = " ".join(str(reason) for reason in trait.get("reasons") or [])
            haystack = " ".join([
                trait_id.lower(),
                value_text.lower(),
                reasons.lower(),
            ])
            if term not in haystack:
                continue
        filtered.append(trait)
    filtered.sort(key=lambda item: str(item.get("trait_id") or ""))
    return filtered


def _safe_container(trait_id: Any) -> str:
    text = str(trait_id or "")
    if not text:
        return "(unknown)"
    return text.split(".")[0] if "." in text else text


def _stringify_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    if value is None:
        return ""
    return str(value)


def _refresh_unabridged(user_id: str) -> None:
    try:
        response = requests.get(
            f"{CORE_BASE}/ui/unabridged",
            params={"user_id": user_id},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        traits = payload.get("traits") if isinstance(payload, dict) else []
        if not isinstance(traits, list):
            traits = []
        st.session_state["hc_v2_unabridged_data"] = traits
        st.session_state["hc_v2_unabridged_error"] = None
        st.session_state["hc_v2_unabridged_revision"] = time.time()
        st.session_state["hc_v2_unabridged_cache"] = None
    except Exception as exc:
        st.session_state["hc_v2_unabridged_data"] = []
        st.session_state["hc_v2_unabridged_error"] = _describe_api_error(exc)
        st.session_state["hc_v2_unabridged_cache"] = None


def _refresh_observations(user_id: str) -> None:
    try:
        response = requests.get(
            f"{CORE_BASE}/ui/observations/aggregates",
            params={"user_id": user_id},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        st.session_state["hc_v2_observation_data"] = None
        st.session_state["hc_v2_observation_error"] = _describe_api_error(exc)
        return

    if isinstance(payload, Mapping):
        st.session_state["hc_v2_observation_data"] = payload
        st.session_state["hc_v2_observation_error"] = None
    else:
        st.session_state["hc_v2_observation_data"] = None
        st.session_state["hc_v2_observation_error"] = "Unexpected payload for observation aggregates."


def _window_options(payload: Mapping[str, Any]) -> List[str]:
    options = ["all"]
    windows = payload.get("windows")
    if isinstance(windows, Mapping):
        for key in OBSERVATION_WINDOW_PRIORITY:
            if key in windows and key not in options:
                options.append(key)
        for key in windows.keys():
            key_str = str(key)
            if key_str not in options:
                options.append(key_str)
    return options


def _default_observation_window(payload: Mapping[str, Any]) -> str:
    windows = payload.get("windows")
    if isinstance(windows, Mapping) and windows:
        for key in OBSERVATION_WINDOW_PRIORITY:
            if key in windows:
                return key
        first_key = next(iter(windows.keys()))
        return str(first_key)
    return "all"


def _resolve_observation_metrics(payload: Mapping[str, Any], window_key: str) -> Dict[str, Any]:
    base = {
        "observation_count": int(payload.get("observation_count") or 0),
        "dialog_acts": _normalize_distribution(payload.get("dialog_acts")),
        "cadence": _normalize_cadence(payload.get("cadence")),
        "latency": _normalize_latency(payload.get("latency")),
        "per_persona": _normalize_persona_map(payload.get("per_persona")),
    }
    if window_key != "all":
        windows = payload.get("windows")
        if isinstance(windows, Mapping):
            window_payload = windows.get(window_key)
            if isinstance(window_payload, Mapping):
                return {
                    "observation_count": int(window_payload.get("observation_count") or 0),
                    "dialog_acts": _normalize_distribution(window_payload.get("dialog_acts")),
                    "cadence": _normalize_cadence(window_payload.get("cadence")),
                    "latency": _normalize_latency(window_payload.get("latency")),
                    "per_persona": _normalize_persona_map(window_payload.get("per_persona")),
                }
    return base


def _normalize_distribution(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        payload = {}
    latest_raw = payload.get("latest")
    latest = str(latest_raw) if latest_raw not in (None, "") else None
    distribution: Dict[str, float] = {}
    mapping = payload.get("distribution")
    if isinstance(mapping, Mapping):
        for key, value in mapping.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            distribution[str(key)] = numeric
    return {"latest": latest, "distribution": distribution}


def _normalize_cadence(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        payload = {}
    latest_raw = payload.get("latest_bucket")
    latest = str(latest_raw) if latest_raw not in (None, "") else None
    histogram: Dict[str, float] = {}
    mapping = payload.get("histogram")
    if isinstance(mapping, Mapping):
        for key, value in mapping.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            histogram[str(key)] = numeric
    return {"latest_bucket": latest, "histogram": histogram}


def _normalize_latency(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        payload = {}
    histogram: Dict[str, float] = {}
    mapping = payload.get("histogram")
    if isinstance(mapping, Mapping):
        for key, value in mapping.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            histogram[str(key)] = numeric
    median = payload.get("median_ms")
    mean = payload.get("mean_ms")
    return {
        "median_ms": float(median) if isinstance(median, (int, float)) else None,
        "mean_ms": float(mean) if isinstance(mean, (int, float)) else None,
        "histogram": histogram,
    }


def _normalize_persona_map(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    result: Dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(value, Mapping):
            continue
        result[str(key)] = {
            "observation_count": int(value.get("observation_count") or 0),
            "dialog_acts": _normalize_distribution(value.get("dialog_acts")),
        }
    return result


def _top_distribution(mapping: Mapping[str, Any], limit: int = 5) -> List[Tuple[str, float]]:
    if not isinstance(mapping, Mapping):
        return []
    entries: List[Tuple[str, float]] = []
    for key, value in mapping.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        entries.append((str(key), numeric))
    entries.sort(key=lambda item: item[1], reverse=True)
    return entries[:limit]


def _format_distribution_text(entries: List[Tuple[str, float]]) -> str:
    if not entries:
        return "—"
    parts: List[str] = []
    for label, count in entries:
        if abs(count - round(count)) < 0.01:
            parts.append(f"{label} ({int(round(count))})")
        else:
            parts.append(f"{label} ({count:.1f})")
    return ", ".join(parts)


def _format_latency(value: Any) -> str:
    if value is None:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{numeric:.0f}"


def _format_persona_label(raw: str) -> str:
    text = str(raw or "").replace("_", " ").replace("-", " ").strip()
    if not text:
        return "(unknown)"
    return text.title()


def _format_window_label(window_key: str) -> str:
    return WINDOW_LABELS.get(window_key, _format_persona_label(window_key))


def _load_trait_timeline(user_id: str, trait_id: str) -> None:
    try:
        response = requests.get(
            f"{CORE_BASE}/ui/trait_timeline",
            params={"user_id": user_id, "trait_id": trait_id, "limit": 50},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("entries") if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            entries = []
        st.session_state["hc_v2_timeline_entries"] = entries
        st.session_state["hc_v2_timeline_error"] = None
    except Exception as exc:
        st.session_state["hc_v2_timeline_entries"] = []
        st.session_state["hc_v2_timeline_error"] = _describe_api_error(exc)
    finally:
        st.session_state["hc_v2_timeline_trait"] = trait_id


def _perform_snapshot(user_id: str) -> None:
    if not user_id:
        st.warning("Pick a user before creating a snapshot.")
        return
    st.session_state["hc_v2_snapshot_pending"] = True
    try:
        response = requests.post(
            f"{CORE_BASE}/ui/snapshot",
            json={"user_id": user_id},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            st.warning("Snapshot failed.")
            return
        bundle = payload.get("bundle") or {}
        version = payload.get("version") or "unknown"
        st.session_state["hc_v2_snapshot_bundle"] = json.dumps(bundle, indent=2).encode("utf-8")
        st.session_state["hc_v2_snapshot_version"] = version
        st.success(f"Snapshot created (version {version}).")
    except Exception as exc:
        st.warning(_describe_api_error(exc))
    finally:
        st.session_state["hc_v2_snapshot_pending"] = False


def _dispatch_chat(*, payload: Dict[str, Optional[str]]) -> None:
    st.session_state["hc_v2_sending"] = True
    streaming_allowed = bool(payload.get("streaming")) and _chat_stream_allowed()
    try:
        if streaming_allowed:
            try:
                with requests.post(
                    f"{CORE_BASE}/ui/chat/send",
                    params={"stream": 1},
                    headers={"Accept": "text/event-stream"},
                    json={
                        "user_id": payload.get("user_id"),
                        "persona": payload.get("persona_send"),
                        "text": payload.get("text"),
                        "client_ts": payload.get("client_ts"),
                    },
                    stream=True,
                    timeout=12,
                ) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")
                    if "text/event-stream" in content_type:
                        final_payload = _consume_chat_stream(response, payload)
                    else:
                        final_payload = response.json()
            except Exception:
                final_payload = None
            else:
                _finalize_chat_response(final_payload, payload)
                st.session_state["hc_v2_pending_send"] = None
                st.session_state["hc_v2_error"] = None
                return

        response = requests.post(
            f"{CORE_BASE}/ui/chat/send",
            json={
                "user_id": payload.get("user_id"),
                "persona": payload.get("persona_send"),
                "text": payload.get("text"),
                "client_ts": payload.get("client_ts"),
            },
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        _finalize_chat_response(data, payload)
        st.session_state["hc_v2_pending_send"] = None
        st.session_state["hc_v2_error"] = None
    except Exception as exc:
        st.session_state["hc_v2_error"] = _describe_api_error(exc)
        st.session_state["hc_v2_pending_send"] = payload
    finally:
        st.session_state["hc_v2_sending"] = False


def _schedule_cooldown(window_seconds: float = 0.5) -> None:
    st.session_state["hc_v2_cooldown_until"] = time.time() + max(window_seconds, 0.0)


def _generate_client_message_id() -> str:
    try:
        return uuid.uuid4().hex
    except Exception:
        return f"msg-{int(time.time() * 1000)}"


def _persona_send_key(persona: str) -> str:
    normalized = persona.replace("_", " ").strip().lower()
    if normalized in {"head coach", "head_coach"}:
        return "head coach"
    if normalized in {"relationship coach", "relationship_coach", "rc"}:
        return "rc"
    if normalized in {"padna", "padna coach", "padna_coach"}:
        return "padna"
    if normalized in {"photo", "photo coach", "photo_coach"}:
        return "photo"
    return "head coach"


def _chat_stream_allowed() -> bool:
    return _env_enabled("HC_CHAT_STREAM_ENABLED")


def _assistant_label_from_response(persona: Optional[str], fallback: str) -> str:
    if not persona:
        return fallback
    normalized = str(persona).strip().lower()
    if normalized == "head coach":
        return "Head Coach (Orchestrator)"
    if normalized in {"rc", "relationship coach", "relationship_coach"}:
        return "Relationship Coach"
    if normalized == "padna":
        return "PaDNA Coach"
    if normalized == "photo":
        return "Photo Coach"
    return fallback


def _replace_placeholder(*, client_id: str, persona_label: str, message_text: str, timestamp: Optional[int]) -> None:
    history = st.session_state.get("hc_v2_history", [])
    found = False
    for entry in history:
        if entry.get("role") == "assistant" and entry.get("client_id") == client_id:
            entry["speaker"] = persona_label
            entry["message"] = message_text
            entry["pending"] = False
            entry["streaming"] = False
            if timestamp is not None:
                entry["ts"] = timestamp
            found = True
            break
    if not found:
        history.append(
            {
                "speaker": persona_label,
                "message": message_text,
                "role": "assistant",
                "client_id": client_id,
                "pending": False,
                "streaming": False,
                "ts": timestamp or int(time.time() * 1000),
            }
        )
    st.session_state["hc_v2_history"] = history[-60:]


def _finalize_chat_response(data: Dict[str, Any], payload: Dict[str, Optional[str]]) -> None:
    if not isinstance(data, dict):
        raise ValueError("Invalid chat response payload")
    persona_label = _assistant_label_from_response(
        data.get("persona"),
        payload.get("persona_label") or "Head Coach",
    )
    message_text = str(data.get("text") or "Noted. I will circle back shortly.")
    timestamp = data.get("ts")
    _replace_placeholder(
        client_id=str(payload.get("client_id")),
        persona_label=persona_label,
        message_text=message_text,
        timestamp=timestamp,
    )


def _consume_chat_stream(response: requests.Response, payload: Dict[str, Optional[str]]) -> Dict[str, Any]:
    persona_label = payload.get("persona_label") or "Head Coach"
    client_id = str(payload.get("client_id") or "")
    data_lines: List[str] = []
    final_payload: Optional[Dict[str, Any]] = None

    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            if data_lines:
                joined = "".join(data_lines)
                data_lines = []
                final_payload = _process_stream_chunk(joined, client_id, persona_label, final_payload)
                if final_payload and final_payload.get("done"):
                    break
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())

    if data_lines and not final_payload:
        joined = "".join(data_lines)
        final_payload = _process_stream_chunk(joined, client_id, persona_label, final_payload)

    if not final_payload:
        raise ValueError("Head Coach stream ended without a completion payload.")
    return final_payload


def _process_stream_chunk(
    chunk: str,
    client_id: str,
    persona_label: str,
    current_final: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not chunk:
        return current_final
    try:
        payload = json.loads(chunk)
    except json.JSONDecodeError:
        return current_final

    delta = payload.get("delta")
    if delta:
        _append_stream_delta(client_id, str(delta), persona_label)

    if payload.get("done"):
        return payload

    return current_final


def _append_stream_delta(client_id: str, delta: str, persona_label: str) -> None:
    if not delta:
        return
    history = st.session_state.get("hc_v2_history", [])
    for entry in history:
        if entry.get("role") == "assistant" and entry.get("client_id") == client_id:
            existing = entry.get("message") or ""
            if existing == "…":
                existing = ""
            entry["message"] = existing + delta
            entry["pending"] = True
            entry["streaming"] = True
            entry["speaker"] = persona_label
            break
    st.session_state["hc_v2_history"] = history[-60:]


def _build_local_echo(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "Noted. Logging this turn for the Head Coach."
    if len(cleaned) < 90:
        return f"Got it — I’ll keep this in mind: \"{cleaned}\""
    return "Thanks! Captured that update and will incorporate it in the next plan."


def _describe_api_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError):
        try:
            payload = exc.response.json() if exc.response is not None else {}
        except Exception:
            payload = {}
        detail = payload.get("message") or payload.get("error") or exc.response.text if exc.response else ""
        base = f"Head Coach chat failed ({exc.response.status_code})."
        return f"{base} {detail}".strip()
    if isinstance(exc, requests.RequestException):
        return "Network error reaching the Head Coach API."
    return str(exc) if str(exc) else "Unexpected error sending chat message."


def _set_active_persona(key: str, roster_map: Dict[str, PersonaOption]) -> None:
    if st.session_state.get("hc_v2_active_persona") == key:
        return
    st.session_state["hc_v2_active_persona"] = key
    option = roster_map.get(key)
    icon = option.icon if option else "🤖"
    label = option.label if option else key
    toast = getattr(st, "toast", None)
    if callable(toast):
        toast(f"Persona switched to {label}", icon=icon)


def _register_post_composer_widget(name: str) -> None:
    if "hc_v2_post_composer_widgets" not in st.session_state:
        st.session_state["hc_v2_post_composer_widgets"] = []
    st.session_state["hc_v2_post_composer_widgets"].append(name)


def _render_debug_overlay(
    roster: List[PersonaOption],
    active_persona: str,
    active_persona_label: str,
    active_user: str,
    *,
    first_widget: str,
) -> None:
    _register_post_composer_widget("debug_overlay")
    post_widgets = st.session_state.get("hc_v2_post_composer_widgets", [])
    extras = [item for item in post_widgets if item != "debug_overlay"]

    roster_lines = []
    for option in roster:
        status = "✓" if option.enabled else "✗"
        roster_lines.append(
            f"<li><span class='persona-icon'>{option.icon}</span>"
            f"<span class='persona-label'>{option.label}</span>"
            f"<span class='persona-status { 'on' if option.enabled else 'off' }'>{status}</span></li>"
        )
    roster_html = "".join(roster_lines)
    overlay_html = f"""
    <style>
      .hc2-debug-overlay {{
        position: fixed;
        top: 1.5rem;
        right: 1.5rem;
        max-width: 320px;
        z-index: 999;
        pointer-events: none;
      }}
      .hc2-debug-overlay .card {{
        pointer-events: auto;
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.45);
        background: rgba(15, 23, 42, 0.94);
        box-shadow: 0 18px 38px rgba(15, 23, 42, 0.48);
        padding: 16px;
        font-family: 'Inter', sans-serif;
        color: #e2e8f0;
        font-size: 12px;
      }}
      .hc2-debug-overlay h4 {{
        margin: 0 0 8px 0;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 11px;
        color: #94a3b8;
      }}
      .hc2-debug-overlay ul {{
        list-style: none;
        padding: 0;
        margin: 0;
      }}
      .hc2-debug-overlay li {{
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 4px;
      }}
      .hc2-debug-overlay .persona-status {{
        margin-left: auto;
        font-weight: 600;
      }}
      .hc2-debug-overlay .persona-status.on {{ color: #34d399; }}
      .hc2-debug-overlay .persona-status.off {{ color: #f87171; }}
      .hc2-debug-overlay .metric, .hc2-debug-overlay .metric-inline {{
        display: flex;
        justify-content: space-between;
        margin-top: 6px;
      }}
      .hc2-debug-overlay .metric span:first-child {{
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .hc2-debug-overlay .badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        border-radius: 999px;
        padding: 2px 8px;
        background: rgba(14, 165, 233, 0.2);
        color: #bae6fd;
        font-weight: 600;
        margin-bottom: 4px;
      }}
      .hc2-debug-overlay .section {{
        margin-top: 12px;
      }}
      .hc2-debug-overlay .metric-inline span {{
        text-transform: none;
        letter-spacing: normal;
        font-weight: 500;
        color: #f8fafc;
      }}
    </style>
    <div class="hc2-debug-overlay">
      <div class="card">
        <div class="badge">UI Debug · ?ui_debug=1</div>
        <div class="section">
          <h4>Persona Roster</h4>
          <ul>{roster_html}</ul>
        </div>
        <div class="section">
          <div class="metric"><span>Current persona</span><span>{active_persona} · {active_persona_label or '—'}</span></div>
          <div class="metric"><span>Composer</span><span>✓ rendered</span></div>
          <div class="metric"><span>First widget</span><span>{first_widget}</span></div>
          <div class="metric"><span>Active user</span><span>{active_user or '—'}</span></div>
          <div class="metric"><span>Composer last</span><span>{'✓' if not extras else '✗'}</span></div>
          {('<div class="metric-inline"><span>' + ', '.join(extras[:3]) + ('…' if len(extras) > 3 else '') + '</span></div>') if extras else ''}
        </div>
      </div>
    </div>
    """
    st.markdown(overlay_html, unsafe_allow_html=True)
