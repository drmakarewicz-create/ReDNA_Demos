from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

_UI_DEBUG_TRUE = {"1", "true", "yes", "on"}
_DEBUG_CSS_KEY = "_hc_debug_overlay_css"


def _ui_debug_enabled() -> bool:
    """Return True when ?ui_debug=1 style flags appear in the query params."""

    try:
        params = st.query_params  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - legacy Streamlit fallback
        params = st.experimental_get_query_params()  # type: ignore[attr-defined]

    value = params.get("ui_debug") if isinstance(params, dict) else None
    if value is None:
        return False
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    token = str(value or "").strip().lower()
    return token in _UI_DEBUG_TRUE


def _render_debug_overlay(payload: Dict[str, str], placeholder: Optional[Any] = None) -> None:
    """Render a small pinned diagnostic overlay showing persona/chat metadata."""

    if not payload:
        return

    if not st.session_state.get(_DEBUG_CSS_KEY):
        st.markdown(
            """
            <style>
              .hc-debug-overlay {
                position: fixed;
                top: 4.5rem;
                right: 1.5rem;
                background: rgba(15, 23, 42, 0.92);
                color: #f8fafc;
                padding: 0.6rem 0.9rem;
                border-radius: 0.75rem;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.35);
                font-size: 0.75rem;
                line-height: 1.4;
                z-index: 980;
              }
              .hc-debug-overlay strong {
                display: inline-block;
                min-width: 7.5rem;
                font-weight: 600;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.session_state[_DEBUG_CSS_KEY] = True

    body = "".join(
        f"<div><strong>{escape(key.title())}</strong> {escape(value)}</div>"
        for key, value in payload.items()
    )
    target = placeholder.markdown if placeholder is not None else st.markdown
    target(f"<div class='hc-debug-overlay'>{body}</div>", unsafe_allow_html=True)

from ExplorerFinal.core.head_coach_runtime import (
    capture_turn_observation,
    last_assistant_timestamp,
)

from ui import personas as _registered_personas  # noqa: F401
from ExplorerFinal.ui.components import (
    compact_mode_enabled,
    inject_hc_chat_css,
    inject_hc_flex_css,
    render_css_once,
    render_quick_link_chips,
)
from ExplorerFinal.ui.nav import render_top_nav, side_nav
from ExplorerFinal.ui.persona_bus import (
    PersonaDescriptor,
    get_active_descriptor as persona_get_active_descriptor,
    get_active_id as persona_get_active_id,
    get_persona as persona_lookup,
    public_roster as persona_public_roster,
    register_persona as persona_register,
    set_active as persona_set_active,
)
from ExplorerFinal.ui.persona_router import route_intent
from ExplorerFinal.ui.session import (
    consume_persona_toast,
    consume_user_loaded_toast,
    current_persona_for,
    get_persona_descriptor,
    get_persona_for_user,
    get_user_id,
    list_users,
    normalize_persona_key,
    persona_choices,
    persona_status,
    safe_rerun,
    set_persona_for_user,
    switch_active_user,
)
from ExplorerFinal.ui.onboarding_state import onboarding_active, onboarding_completed

try:  # pragma: no cover - optional tone helpers
    from ExplorerFinal.ui.tone.rc_filters import scrub as rc_scrub  # type: ignore
except Exception:  # pragma: no cover - fallback when tone package not wired
    def rc_scrub(text: str) -> str:
        return text

try:  # pragma: no cover - optional fallback if helpers missing during wiring
    from ExplorerFinal.ui.coach_api import (
        apply_canonical_lines,
        coach_ingest_text,
        coach_upload_files,
        generate_game_plan,
        run_holistic_review,
        CORE_HOLISTIC_USE_LLM,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback
    def coach_ingest_text(
        user_id: str,
        text: str,
        dev_mode: bool,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        provenance_source: str = "head_coach_chat",
        observations: Optional[List[Dict[str, Any]]] = None,
        background_capture: bool = True,
    ) -> Dict[str, Any]:
        return {
            "assistant_text": "Coach services are not ready yet.",
            "ucnrr_reply": {"ok": False, "reason": "coach_api_missing"},
            "core_resolved": {},
            "added_by_core_ai": [],
            "error": "coach_api_missing",
            "observation_reply": {"ok": False, "reason": "coach_api_missing"},
        }

    def coach_upload_files(
        user_id: str,
        files: List[Any],
        *,
        provenance_source: str = "head_coach_upload",
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for file in files:
            out.append(
                {
                    "ok": False,
                    "reason": "coach_api_missing",
                    "filename": getattr(file, "name", "file"),
                }
            )
        return out

    def generate_game_plan(user_id: str) -> Dict[str, Any]:
        return {"ok": False, "reason": "coach_api_missing"}

    def run_holistic_review(user_id: str) -> Dict[str, Any]:
        return {"ok": False, "reason": "coach_api_missing"}

    def apply_canonical_lines(user_id: str, lines: List[str], *, persona_id: str = "head_coach") -> Dict[str, Any]:
        return {"ok": False, "reason": "coach_api_missing"}

    CORE_HOLISTIC_USE_LLM = False


HOLISTIC_LLM_ENABLED = CORE_HOLISTIC_USE_LLM

_PERSONA_FALLBACK: Dict[str, Dict[str, str]] = {
    "head_coach": {
        "title": "Head Coach",
        "icon": "🧠",
        "color": "#1F2933",
        "description": "Primary orchestrator and default persona.",
    },
    "relationship_coach": {
        "title": "Relationship Coach",
        "icon": "💞",
        "color": "#8FBFE0",
        "description": "Guides relationship reflection and micro-actions.",
    },
    "padna_coach": {
        "title": "PaDNA Coach",
        "icon": "🧬",
        "color": "#7C3AED",
        "description": "Packages confirmed PaDNA traits into outbound-ready avatars.",
    },
    "photo_coach": {
        "title": "Photo Coach",
        "icon": "📷",
        "color": "#F59E0B",
        "description": "Analyzes photos to map traits and suggest refinements.",
    },
}

_CANONICAL_TO_BUS: Dict[str, str] = {
    "head coach": "head_coach",
    "rc": "relationship_coach",
    "padna": "padna_coach",
    "photo": "photo_coach",
}

_BUS_TO_CANONICAL: Dict[str, str] = {
    "head_coach": "head coach",
    "relationship_coach": "rc",
    "padna_coach": "padna",
    "photo_coach": "photo",
}


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

def _safe_persona_lookup(persona_id: str):
    try:
        return persona_lookup(persona_id)
    except (RuntimeError, KeyError):
        return None


def _safe_active_descriptor(default_id: str = "head_coach"):
    try:
        return persona_get_active_descriptor(default_id)
    except RuntimeError:
        return None


def _ensure_fallback_persona(bus_id: str) -> None:
    if _safe_persona_lookup(bus_id) is not None:
        return
    fallback = _PERSONA_FALLBACK.get(bus_id)
    if not fallback:
        return
    try:
        persona_register(
            PersonaDescriptor(
                id=bus_id,
                title=fallback.get("title", bus_id.replace("_", " ").title()),
                icon=fallback.get("icon", ""),
                color=fallback.get("color", "#1F2933"),
                description=fallback.get("description", ""),
            ),
            overwrite=False,
        )
    except Exception:
        pass

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trigger_rerun() -> None:
    st.session_state["_deferred_rerun"] = True


def _status_pill(text: str, tone: str = "error") -> None:
    colors = {
        "error": "#d73a49",
        "success": "#1b7f3c",
        "info": "#5865f2",
        "warn": "#b08800",
    }
    color = colors.get(tone, "#5865f2")
    safe_text = escape(text or "")
    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:0.25rem 0.7rem;
            border-radius:999px;
            background:{color};
            color:#fff;
            font-size:0.75rem;
            margin-right:0.5rem;
            margin-top:0.25rem;">
            {safe_text}
        </span>
        """,
        unsafe_allow_html=True,
    )


def _persona_greeting(persona_id: str) -> str:
    canonical = normalize_persona_key(persona_id)
    bus_id = persona_id
    if bus_id not in _PERSONA_FALLBACK:
        bus_id = _CANONICAL_TO_BUS.get(canonical, persona_id)

    descriptor = _safe_persona_lookup(bus_id)
    if descriptor is not None:
        title = descriptor.title
    else:
        fallback = _PERSONA_FALLBACK.get(bus_id)
        if fallback:
            title = fallback.get("title", canonical.replace("_", " ").title())
        else:
            fallback_descriptor = get_persona_descriptor(canonical)
            title = fallback_descriptor.label
    greetings = {
        "relationship_coach": (
            f"{title} here — ready to co-create one small relational win together. What’s on your mind?"
        ),
        "photo": (
            f"{title} here. Share a photo or describe the look and I’ll map traits for you."
        ),
        "padna": (
            f"{title} here. Point me toward the bundle or story you want to package next."
        ),
        "onboarding": (
            f"{title} checking in. Ready to capture a quick snapshot of where you’re starting?"
        ),
    }
    return greetings.get(
        persona_id,
        f"{title} here. Tell me what you’d like to focus on next."
    )


def _safe_active_persona_id(default: Optional[str] = None) -> Optional[str]:
    try:
        value = persona_get_active_id()
    except RuntimeError:
        return default
    return value or default


def _format_holistic_summary(summary: Dict[str, Any]) -> str:
    if summary.get("llm_considered") or summary.get("llm_updates"):
        return (
            "Holistic (LLM): "
            f"considered {summary.get('llm_considered', 0)}, "
            f"updated {summary.get('llm_updates', 0)}, "
            f"implied {summary.get('implied_additions', 0)}, "
            f"contradictions {summary.get('contradictions', 0)}"
        )
    return (
        "Holistic: "
        f"{summary.get('ucn_rr_updates', 0)} adjusted, "
        f"{summary.get('implied_additions', 0)} implied, "
        f"{summary.get('contradictions', 0)} contradictions"
    )


def _render_assistant_message(
    message: Dict[str, Any],
    dev_mode: bool,
    header_label: Optional[str] = None,
) -> None:
    meta = message.get("meta", {}) or {}
    content = message.get("content", "")
    if header_label:
        st.markdown(f"**{header_label}**")
    st.markdown(content)
    badge_details = meta.get("badge_details") or []
    if badge_details:
        for badge in badge_details:
            _status_pill(badge.get("text", ""), tone=badge.get("tone", "info"))
    else:
        badges = meta.get("badges") or []
        for badge in badges:
            _status_pill(badge, tone="info")
    if dev_mode and meta.get("canonical_suggestions"):
        st.caption("Suggested test inputs")
        st.code("\n".join(meta["canonical_suggestions"]), language="text")


def _render_user_loader(page_prefix: str, active_user: str) -> None:
    users = list_users()
    options = ["—"] + users
    default_index = 0
    if active_user and active_user in users:
        default_index = options.index(active_user)

    selection = st.selectbox(
        "Existing users",
        options=options,
        index=default_index,
        key=f"{page_prefix}_user_picker_select",
    )

    st.text_input(
        "User id",
        value=active_user or "",
        key=f"{page_prefix}_user_picker_display",
        disabled=True,
    )

    load_label = "Load user"
    cols = st.columns([1, 1])
    with cols[0]:
        if st.button(load_label, key=f"{page_prefix}_user_picker_load", use_container_width=True):
            new_id = selection if selection != "—" else ""
            if new_id and switch_active_user(new_id, trigger_toast=True):
                safe_rerun()
    with cols[1]:
        disabled = not active_user
        if st.button(
            "Clear active",
            key=f"{page_prefix}_user_picker_clear",
            use_container_width=True,
            disabled=disabled,
        ):
            if switch_active_user("", trigger_toast=False):
                safe_rerun()


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def render_coach_tab(
    *,
    page_title: str,
    nav_key: str,
    page_prefix: str,
    chat_input_label: str,
    chat_placeholder: Optional[str],
    provenance_source: str,
    upload_source: str,
    plan_button_label: str = "Generate Game Plan",
    plan_expander_label: str = "Game plan",
    plan_empty_caption: str = "Click the plan button to draft a personalized plan.",
    holistic_button_label: str = "Run Holistic Review",
    holistic_expander_label: str = "Holistic AI review",
    enable_personas: bool = False,
    lock_persona: bool = False,
    persona_id: Optional[str] = None,
    locked_persona_id: Optional[str] = None,
    sidebar_renderer: Optional[Any] = None,
    extra_body_renderer: Optional[Any] = None,
    header_badges: Optional[List[str]] = None,
) -> None:
    """Render a coach tab that shares the Head Coach interaction surface."""

    side_nav(active="explorer")
    render_top_nav(active=nav_key)
    debug_enabled = _ui_debug_enabled()
    debug_overlay: Dict[str, str] = {
        "persona roster": "pending",
        "active persona": "pending",
        "chat section rendered": "✗",
        "first widget": "st.title",
    }
    overlay_placeholder = st.empty() if debug_enabled else None

    compact_mode_value, _compact_source = compact_mode_enabled()
    render_css_once(compact=compact_mode_value)
    inject_hc_chat_css()
    inject_hc_flex_css()

    if st.session_state.pop("_deferred_rerun", False):
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()
        return

    active_user = get_user_id()
    pending_user_toast = consume_user_loaded_toast()
    if pending_user_toast:
        st.success(f"Loaded user: {pending_user_toast}")

    persona_toast = consume_persona_toast()
    if persona_toast:
        st.success(persona_toast)

    toast_map = (
        ("_toast_persona_err", st.error),
        ("_toast_persona_info", st.info),
        ("_toast_persona_switched", st.success),
    )
    for key, emitter in toast_map:
        message = st.session_state.pop(key, None)
        if message:
            emitter(message)

    # ---- State scaffold ----
    msgs_key = f"{page_prefix}_msgs"
    files_key = f"{page_prefix}_file_status"
    plan_key = f"{page_prefix}_plan"
    plan_status_key = f"{page_prefix}_plan_status"
    dev_key = f"{page_prefix}_dev"
    badges_key = f"{page_prefix}_recent_badges"
    holistic_key = f"{page_prefix}_holistic"
    context_key = f"{page_prefix}_context"
    last_user_key = f"{page_prefix}_last_user"
    processed_uploads_key = f"{page_prefix}_processed_uploads"
    persona_mode_key = f"{page_prefix}_persona_mode"
    persona_mode_force_key = f"_persona_force_manual_{page_prefix}"
    persona_manual_key = f"{page_prefix}_persona_manual"
    persona_current_key = f"{page_prefix}_persona_current"
    suggestion_status_key = f"{page_prefix}_suggestion_status"
    user_picker_flag_key = f"{page_prefix}_user_picker_open"
    observations_key = f"{page_prefix}_observations_buffer"
    runtime_state_key = f"{page_prefix}_observation_state"
    metrics_key = f"{page_prefix}_turn_metrics"
    uploader_toggle_key = f"{page_prefix}_show_uploader"

    st.session_state.setdefault(msgs_key, {})
    st.session_state.setdefault(files_key, {})
    st.session_state.setdefault(plan_key, {})
    st.session_state.setdefault(plan_status_key, {})
    st.session_state.setdefault(dev_key, False)
    st.session_state.setdefault(badges_key, {})
    st.session_state.setdefault(holistic_key, {})
    st.session_state.setdefault(context_key, {})
    st.session_state.setdefault(last_user_key, None)
    st.session_state.setdefault(processed_uploads_key, [])
    st.session_state.setdefault(suggestion_status_key, {})
    st.session_state.setdefault(user_picker_flag_key, not bool(active_user))
    st.session_state.setdefault(observations_key, {})
    st.session_state.setdefault(runtime_state_key, {})
    st.session_state.setdefault(metrics_key, {})
    st.session_state.setdefault(uploader_toggle_key, False)
    st.session_state.setdefault("hc_text_input", "")
    if st.session_state.pop("_hc_clear_text_input", False):
        st.session_state["hc_text_input"] = ""
    st.session_state.setdefault(persona_mode_key, "Manual")

    if lock_persona:
        st.session_state[persona_mode_key] = "Manual"

    if st.session_state.pop(persona_mode_force_key, False):
        st.session_state[persona_mode_key] = "Manual"
    if st.session_state.pop("_persona_force_manual", False):
        st.session_state[persona_mode_key] = "Manual"

    if lock_persona and persona_id:
        locked_persona_id = persona_id
        if not enable_personas:
            enable_personas = True

    if locked_persona_id and active_user:
        st.session_state.setdefault("_persona_ctx_by_user", {})[active_user] = locked_persona_id

    persona_error_message: Optional[str] = None
    if locked_persona_id and enable_personas:
        try:
            persona_set_active(
                locked_persona_id,
                trigger="locked_tab",
                metadata={"source": page_prefix, "user_id": active_user},
            )
        except (KeyError, RuntimeError):
            enable_personas = False
            persona_error_message = "Personas are not registered; falling back to Head Coach."

    seed_persona = persona_id or locked_persona_id or _safe_active_persona_id("head_coach") or "head_coach"
    active_persona_default = (
        get_persona_for_user(active_user, seed_persona) if active_user else seed_persona
    )

    persona_roster: List[Dict[str, Any]] = []
    descriptor_for_sidebar = None
    if enable_personas:
        for bus_id in _PERSONA_FALLBACK.keys():
            canonical = _BUS_TO_CANONICAL.get(bus_id, normalize_persona_key(bus_id))
            status_state, _ = persona_status(canonical)
            # Seed minimal descriptors for enabled personas so the bus never 404s.
            if status_state != "off":
                _ensure_fallback_persona(bus_id)

        try:
            bus_roster = persona_public_roster()
        except RuntimeError:
            bus_roster = []

        source_iterable: List[Dict[str, Any]]
        if bus_roster:
            source_iterable = bus_roster
        else:
            # Bus did not return anything; synthesise entries from fallbacks so UI stays usable.
            source_iterable = [
                {
                    "id": bus_id,
                    "title": payload.get("title"),
                    "icon": payload.get("icon"),
                    "color": payload.get("color"),
                    "description": payload.get("description"),
                }
                for bus_id, payload in _PERSONA_FALLBACK.items()
            ]

        for raw_entry in source_iterable:
            bus_id = str(raw_entry.get("id") or "").strip()
            if not bus_id:
                continue
            canonical = _BUS_TO_CANONICAL.get(bus_id, normalize_persona_key(bus_id))
            fallback = _PERSONA_FALLBACK.get(bus_id, {})
            status_state, status_note = persona_status(canonical)
            persona_roster.append(
                {
                    "id": bus_id,
                    "canonical": canonical,
                    "title": raw_entry.get("title") or fallback.get("title") or bus_id.replace("_", " ").title(),
                    "icon": raw_entry.get("icon") or fallback.get("icon", ""),
                    "color": raw_entry.get("color") or fallback.get("color", "#1F2933"),
                    "description": raw_entry.get("description") or fallback.get("description", ""),
                    "enabled": status_state != "off",
                    "status_note": status_note,
                }
            )

        st.session_state.setdefault(persona_manual_key, active_persona_default)
        st.session_state.setdefault(persona_current_key, active_persona_default)
        if lock_persona and locked_persona_id:
            for roster_entry in persona_roster:
                if roster_entry["id"] != locked_persona_id:
                    roster_entry["enabled"] = False

    valid_persona_ids = {entry["id"] for entry in persona_roster if entry.get("enabled")}
    enabled_names = [entry["title"] for entry in persona_roster if entry.get("enabled")]
    disabled_names = [entry["title"] for entry in persona_roster if not entry.get("enabled")]
    if enable_personas and persona_roster:
        parts: List[str] = [f"enabled: {', '.join(enabled_names) or 'none'}"]
        if disabled_names:
            parts.append(f"disabled: {', '.join(disabled_names)}")
        debug_overlay["persona roster"] = f"{len(persona_roster)} total ({'; '.join(parts)})"
    elif enable_personas:
        debug_overlay["persona roster"] = "0 total"
    else:
        debug_overlay["persona roster"] = "disabled"

    def _history_for(user_id: str) -> List[Dict[str, Any]]:
        history_store = st.session_state[msgs_key]
        return history_store.setdefault(user_id, [])

    def _file_status_for(user_id: str) -> List[Dict[str, Any]]:
        status_store = st.session_state[files_key]
        return status_store.setdefault(user_id, [])

    def _set_file_status(user_id: str, payloads: List[Dict[str, Any]]) -> None:
        _file_status_for(user_id).extend(payloads)

    # Reset session stores when the active user changes
    last_user = st.session_state[last_user_key]
    if last_user != active_user:
        st.session_state[last_user_key] = active_user
        if active_user:
            _history_for(active_user)
            _file_status_for(active_user)
            st.session_state[observations_key].setdefault(active_user, [])
            st.session_state[runtime_state_key].setdefault(active_user, {})
            st.session_state[metrics_key].setdefault(active_user, [])
        st.session_state[suggestion_status_key] = {}

    # ---- Header ----
    title_col, persona_col, toggle_col = st.columns([3, 3, 2])
    title_area = title_col.container()
    with title_area:
        st.title(page_title)
        debug_overlay["first widget"] = page_title
        st.markdown("<div id='head-coach'></div>", unsafe_allow_html=True)
        if header_badges:
            badge_html = ''.join(
                f"<span style='display:inline-block;margin-right:0.4rem;margin-bottom:0.25rem;padding:0.25rem 0.6rem;border-radius:999px;background:#0f172a;color:#fff;font-size:0.75rem;'>"
                f"{badge}</span>"
                for badge in header_badges
            )
            st.markdown(badge_html, unsafe_allow_html=True)
        st.markdown(f"## User: {active_user or '—'}")

    persona_meta: Optional[Dict[str, Any]] = None
    active_persona_id = _safe_active_persona_id(active_persona_default) or active_persona_default
    st.session_state[persona_current_key] = active_persona_id

    if enable_personas and persona_roster:
        with persona_col:
            chip_cols = st.columns(len(persona_roster))
            for roster_entry, col in zip(persona_roster, chip_cols):
                pid = roster_entry["id"]
                is_active = pid == active_persona_id
                locked_out = bool(locked_persona_id and pid != locked_persona_id)
                disabled = (not roster_entry["enabled"]) or (not bool(active_user)) or locked_out
                label = f"{roster_entry['icon']} {roster_entry['title']}".strip()
                help_text = None
                if not roster_entry["enabled"] and roster_entry.get("status_note"):
                    help_text = f"{roster_entry['title']} disabled ({roster_entry['status_note']})."
                with col:
                    if st.button(
                        label,
                        key=f"{page_prefix}_persona_chip_{pid}",
                        use_container_width=True,
                        disabled=disabled,
                        help=help_text,
                    ):
                        if active_user:
                            set_persona_for_user(
                                active_user,
                                pid,
                                reason="persona_chip",
                                metadata={"source": page_prefix},
                            )
                            st.session_state[persona_manual_key] = pid
                        else:
                            st.session_state["_toast_persona_err"] = "Load a user before switching personas."

            dropdown_options = [entry["id"] for entry in persona_roster]
            dropdown_index = dropdown_options.index(active_persona_id) if active_persona_id in dropdown_options else 0

            def _persona_option_label(pid: str) -> str:
                entry_lookup = next((entry for entry in persona_roster if entry["id"] == pid), None)
                if not entry_lookup:
                    fallback = _PERSONA_FALLBACK.get(pid, {})
                    return f"{fallback.get('icon', '')} {fallback.get('title', pid.replace('_', ' ').title())}".strip()
                prefix = entry_lookup["icon"] or ""
                return f"{prefix} {entry_lookup['title']}".strip()

            dropdown_disabled = not active_user or bool(locked_persona_id)

            selected_persona = st.selectbox(
                "Persona",
                dropdown_options,
                index=dropdown_index,
                key=f"{page_prefix}_persona_select",
                format_func=_persona_option_label,
                disabled=dropdown_disabled,
            )
            if (
                selected_persona
                and selected_persona != active_persona_id
                and active_user
                and not dropdown_disabled
            ):
                selected_entry = next(
                    (entry for entry in persona_roster if entry["id"] == selected_persona),
                    None,
                )
                if selected_entry and not selected_entry.get("enabled", True):
                    note = selected_entry.get("status_note") or "env flag"
                    st.session_state["_toast_persona_err"] = (
                        f"{selected_entry['title']} is disabled ({note})."
                    )
                else:
                    set_persona_for_user(
                        active_user,
                        selected_persona,
                        reason="dropdown",
                        metadata={"source": page_prefix},
                    )
                    st.session_state[persona_manual_key] = selected_persona

            descriptor = _safe_persona_lookup(active_persona_id) or _safe_active_descriptor()
            fallback = _PERSONA_FALLBACK.get(active_persona_id, {})
            persona_meta = {
                "title": getattr(descriptor, "title", fallback.get("title", "Head Coach")),
                "description": getattr(descriptor, "description", fallback.get("description", "")),
                "icon": getattr(descriptor, "icon", fallback.get("icon", "")),
                "color": getattr(descriptor, "color", fallback.get("color", "#1F2933")),
            }
            badge_text = f"{persona_meta.get('icon', '')} {persona_meta.get('title', active_persona_id)}".strip()
            st.markdown(
                f"<div style='display:inline-block;margin-top:0.5rem;padding:0.4rem 0.75rem;border-radius:999px;"
                f"background:{persona_meta.get('color', '#1F2933')};color:#fff;font-weight:600;font-size:0.85rem;'>"
                f"{badge_text}</div>",
                unsafe_allow_html=True,
            )
            description = persona_meta.get("description")
            if description:
                st.caption(f"ℹ️ {description}")
            descriptor_for_sidebar = _safe_persona_lookup(active_persona_id)
    else:
        with persona_col:
            if persona_error_message:
                st.info(persona_error_message)
            elif enable_personas and not active_user:
                st.caption("Load a user to manage personas.")
            else:
                st.caption("Personas unavailable; using Head Coach defaults.")

    if persona_meta is None:
        descriptor = (
            _safe_persona_lookup(active_persona_id)
            or _safe_active_descriptor()
            or get_persona_descriptor(active_persona_id)
        )
        persona_meta = {
            "title": getattr(descriptor, "title", "Head Coach"),
            "description": getattr(descriptor, "description", ""),
            "icon": getattr(descriptor, "icon", ""),
            "color": getattr(descriptor, "color", "#1F2933"),
        }
    capture_key = f"{page_prefix}_background_capture"
    capture_default = st.session_state.get(capture_key, True)

    with toggle_col:
        dev_mode = st.toggle(
            "Developer Mode",
            value=st.session_state.get(dev_key, False),
            key=f"{page_prefix}_dev_toggle",
        )
        capture_enabled = capture_default
        if active_persona_id == "relationship_coach":
            capture_enabled = st.toggle(
                "Background capture",
                value=capture_default,
                key=f"{page_prefix}_capture_toggle",
            )
    st.session_state[dev_key] = dev_mode
    st.session_state[capture_key] = capture_enabled

    if enable_personas and persona_roster:
        active_persona_id = _safe_active_persona_id(active_persona_default) or active_persona_default
        descriptor = _safe_active_descriptor() or _safe_persona_lookup(active_persona_id) or get_persona_descriptor(active_persona_id)
        persona_meta = persona_meta or {
            "title": getattr(descriptor, "title", "Head Coach"),
            "icon": getattr(descriptor, "icon", "🧠"),
            "color": getattr(descriptor, "color", "#1F2933"),
            "description": getattr(descriptor, "description", "Primary orchestrator and default persona."),
        }
        st.session_state[persona_current_key] = active_persona_id
    else:
        active_persona_id = persona_id or "head_coach"
        persona_meta = persona_meta or {
            "title": "Head Coach" if active_persona_id == "head_coach" else active_persona_id.replace("_", " ").title(),
            "icon": "🧠" if active_persona_id == "head_coach" else "",
            "color": "#1F2933",
            "description": "Primary orchestrator and default persona." if active_persona_id == "head_coach" else "",
        }

    if enable_personas and persona_roster:
        descriptor_for_sidebar = _safe_persona_lookup(active_persona_id)

    if callable(sidebar_renderer):
        sidebar_renderer(active_user)

    if descriptor_for_sidebar and descriptor_for_sidebar.render_sidebar:
        descriptor_for_sidebar.render_sidebar(active_user)

    user_picker_open = st.session_state.get(user_picker_flag_key, False)
    if active_user:
        toggle_cols = st.columns([1, 6])
        with toggle_cols[0]:
            if st.button(
                "Change user",
                key=f"{page_prefix}_toggle_user_picker",
                use_container_width=True,
            ):
                st.session_state[user_picker_flag_key] = not user_picker_open
                _trigger_rerun()
        user_picker_open = st.session_state.get(user_picker_flag_key, False)
        if user_picker_open:
            with st.expander("Change / load user", expanded=True):
                _render_user_loader(page_prefix, active_user)
    else:
        st.warning("No active user selected. Load an existing profile to continue.")
        _render_user_loader(page_prefix, active_user)
        st.session_state[user_picker_flag_key] = True
        st.stop()

    # ---- Plan + Holistic controls ----
    action_cols = st.columns([1, 3])
    with action_cols[0]:
        if st.button(plan_button_label, type="primary", use_container_width=True):
            with st.spinner("Drafting personalized plan…"):
                plan = generate_game_plan(active_user)
            st.session_state[plan_key][active_user] = plan
            storage = plan.get("storage") if isinstance(plan, dict) else None
            storage_ok = not (isinstance(storage, dict) and storage.get("ok") is False)
            if isinstance(plan, dict) and (plan.get("ok") is False or not storage_ok):
                reason = plan.get("reason")
                if not reason and isinstance(storage, dict):
                    reason = storage.get("reason") or storage.get("data")
                st.session_state[plan_status_key][active_user] = {
                    "tone": "error",
                    "text": reason or "Plan generation failed",
                }
            else:
                st.session_state[plan_status_key][active_user] = {
                    "tone": "success",
                    "text": "Plan updated",
                }

    with action_cols[1]:
        plan_state = st.session_state[plan_key].get(active_user)
        plan_status = st.session_state[plan_status_key].get(active_user)
        with st.expander(plan_expander_label, expanded=bool(plan_state)):
            if plan_status:
                _status_pill(plan_status.get("text", ""), tone=plan_status.get("tone", "info"))
            if plan_state:
                st.json(plan_state)
            else:
                st.caption(plan_empty_caption)

    holistic_cols = st.columns([1, 3])
    with holistic_cols[0]:
        if st.button(holistic_button_label, type="secondary", use_container_width=True):
            spinner_label = "Running holistic AI review…"
            if HOLISTIC_LLM_ENABLED:
                spinner_label = "Running holistic AI review… 🏊🚴🏃"
            with st.spinner(spinner_label):
                hol = run_holistic_review(active_user)
            st.session_state[holistic_key][active_user] = hol
            if hol.get("top_curiosity"):
                context_store = st.session_state[context_key]
                entry = context_store.setdefault(active_user, {})
                entry["top_curiosity"] = hol.get("top_curiosity")
                entry["recent_changes"] = hol.get("recent_changes") or entry.get("recent_changes")
                summary = hol.get("summary") or {}
                if summary.get("ran"):
                    entry["holistic"] = summary
                    holistic_badge = (
                        f"Holistic: {summary.get('ucn_rr_updates', 0)} adjusted, "
                        f"{summary.get('implied_additions', 0)} implied, "
                        f"{summary.get('contradictions', 0)} contradictions"
                    )
                    st.toast(holistic_badge)
                    st.session_state[badges_key].setdefault(active_user, {})[
                        "holistic"
                    ] = summary

    with holistic_cols[1]:
        hol_state = st.session_state[holistic_key].get(active_user)
        with st.expander(holistic_expander_label, expanded=bool(hol_state)):
            if hol_state:
                if hol_state.get("status") and hol_state.get("status") >= 400:
                    _status_pill(
                        f"HTTP {hol_state.get('status')}: {hol_state.get('reason', 'error')}",
                        tone="error",
                    )
                elif hol_state.get("ok"):
                    overview = hol_state.get("data") or {}
                    _status_pill("Holistic review completed", tone="success")
                    changes = overview.get("changes") or overview.get("core_response", {}).get("changed", [])
                    if changes:
                        st.markdown("**Suggested updates**")
                        st.write(", ".join(changes))
                    if hol_state.get("core_resolved"):
                        st.caption("Latest resolved snapshot")
                        st.json(hol_state["core_resolved"], expanded=False)
                    if hol_state.get("top_curiosity"):
                        st.markdown("**Top curiosity focus**")
                        st.dataframe(hol_state["top_curiosity"], use_container_width=True)
                else:
                    _status_pill(hol_state.get("reason", "Holistic review unavailable"), tone="error")
            else:
                st.caption("Run a holistic review to see cross-trait insights.")

    # ---- Chat history & composer ----
    history = _history_for(active_user)
    file_status = _file_status_for(active_user)

    display_persona_key = current_persona_for(active_user) if active_user else "head coach"
    display_descriptor = get_persona_descriptor(display_persona_key)
    debug_overlay["active persona"] = f"{display_persona_key} / {display_descriptor.label}"

    assistant_title = display_descriptor.label
    if display_persona_key == "head coach":
        assistant_title = f"{assistant_title} (Orchestrator)"
    assistant_icon = (display_descriptor.icon or "").strip()
    assistant_label = assistant_title if not assistant_icon else f"{assistant_title} {assistant_icon}"

    st.caption(f"Currently speaking as: **{display_descriptor.label}** {display_descriptor.icon}")

    context_state = st.session_state[context_key].get(active_user)
    if context_state:
        with st.expander("AI signals", expanded=False):
            recent = context_state.get("recent_changes") or {}
            if recent:
                st.markdown("**Recent changes**")
                st.json(recent, expanded=False)
            top_rows = context_state.get("top_curiosity") or []
            if top_rows:
                st.markdown("**Top curiosity traits**")
                st.dataframe(top_rows, use_container_width=True)
            holistic_state = context_state.get("holistic")
            if holistic_state and holistic_state.get("ran"):
                st.markdown("**Holistic summary**")
                st.write(
                    f"Adjusted: {holistic_state.get('ucn_rr_updates', 0)} • "
                    f"Implied: {holistic_state.get('implied_additions', 0)} • "
                    f"Contradictions: {holistic_state.get('contradictions', 0)}"
                )

    recent_badges = st.session_state[badges_key].get(active_user, {})
    if recent_badges:
        badge_updated = recent_badges.get("updated") or []
        badge_core = recent_badges.get("core_ai") or []
        badge_proposed = recent_badges.get("proposed") or []
        badge_holistic = recent_badges.get("holistic") or {}
        if badge_updated or badge_core or badge_proposed:
            st.caption("Latest pipeline activity")
        if badge_updated:
            label = ", ".join(badge_updated[:3]) + ("…" if len(badge_updated) > 3 else "")
            _status_pill(
                f"Updated ({len(badge_updated)}): {label}" if label else f"Updated ({len(badge_updated)})",
                tone="info",
            )
        if badge_core:
            label = ", ".join(badge_core[:3]) + ("…" if len(badge_core) > 3 else "")
            _status_pill(
                f"Core-AI ({len(badge_core)}): {label}" if label else f"Core-AI ({len(badge_core)})",
                tone="info",
            )
        if badge_proposed:
            label = ", ".join(badge_proposed[:3]) + ("…" if len(badge_proposed) > 3 else "")
            _status_pill(
                f"Proposed ({len(badge_proposed)}): {label}" if label else f"Proposed ({len(badge_proposed)})",
                tone="info",
            )
        if badge_holistic and badge_holistic.get("ran"):
            _status_pill(
                f"Holistic: {badge_holistic.get('ucn_rr_updates', 0)} adjusted, "
                f"{badge_holistic.get('implied_additions', 0)} implied, "
                f"{badge_holistic.get('contradictions', 0)} contradictions",
                tone="info",
            )

    suggestion_status = st.session_state[suggestion_status_key]
    ss = st.session_state
    ss[uploader_toggle_key] = False
    uploaded_files = None

    st.markdown("<div class='hc-wrap'>", unsafe_allow_html=True)

    log_container = st.container()
    with log_container:
        st.markdown("<div class='hc-scroll'>", unsafe_allow_html=True)
        for idx, message in enumerate(history):
            role = message.get("role", "assistant")
            if role == "assistant":
                with st.chat_message("assistant", avatar=assistant_icon or None):
                    _render_assistant_message(
                        message,
                        dev_mode=dev_mode,
                        header_label=assistant_label,
                    )
                    meta = message.get("meta") or {}
                    suggestions = meta.get("canonical_suggestions") or []
                    if suggestions:
                        apply_key = f"{page_prefix}_apply_{idx}"
                        if st.button(
                            "Apply suggestions",
                            key=apply_key,
                            use_container_width=False,
                        ):
                            persona_for_apply = meta.get("persona_id") or active_persona_id
                            result = apply_canonical_lines(
                                active_user,
                                suggestions,
                                persona_id=persona_for_apply,
                            )
                            suggestion_status[idx] = result
                            st.session_state[suggestion_status_key] = suggestion_status
                            _trigger_rerun()
                        status = suggestion_status.get(idx)
                        if status:
                            if status.get("ok"):
                                _status_pill("Applied to UCN/RR", tone="success")
                            else:
                                reason = status.get("reason") or status.get("message") or "apply_failed"
                                _status_pill(f"Apply failed: {reason}", tone="error")
            else:
                with st.chat_message(role):
                    st.markdown(message.get("content", ""))

        if file_status:
            st.markdown("---")
            st.caption("Recent uploads")
            for entry in file_status[-5:]:
                tone = "success" if entry.get("ok") else "error"
                label = entry.get("filename") or entry.get("id") or "file"
                reason = (
                    entry.get("reason")
                    or entry.get("detail")
                    or entry.get("note")
                    or "Processed"
                )
                _status_pill(f"{label}: {reason}", tone=tone)
        st.markdown("</div>", unsafe_allow_html=True)

    debug_overlay["chat section rendered"] = "✓"

    st.markdown("<div class='hc-composer'>", unsafe_allow_html=True)
    composer_container = st.container()
    with composer_container:
        st.markdown("<div class='hc-row'>", unsafe_allow_html=True)
        composer_cols = st.columns([12, 1], gap="small")

        def _submit_text_input() -> None:
            ss["_hc_footer_submit"] = True

        with composer_cols[0]:
            st.text_input(
                "Message the Head Coach…",
                key="hc_text_input",
                label_visibility="collapsed",
                on_change=_submit_text_input,
                placeholder=chat_placeholder or chat_input_label,
            )
        with composer_cols[1]:
            if st.button("➤", help="Send", key=f"{page_prefix}_send_btn"):
                ss["_hc_footer_submit"] = True

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if debug_enabled:
        _render_debug_overlay(debug_overlay, overlay_placeholder)


    processed_keys: List[str] = st.session_state.get(processed_uploads_key, [])
    new_statuses: List[Dict[str, Any]] = []
    if uploaded_files and active_user:
        st.session_state[processed_uploads_key] = processed_keys
    footer_submitted = ss.pop("_hc_footer_submit", False)
    prompt = (ss.get("hc_text_input") or "").strip()
    pending_command: Optional[str] = None
    pending_prompt: Optional[str] = None
    should_rerun = False
    if footer_submitted:
        if prompt:
            command_target = _match_persona_command(prompt)
            if command_target and active_user:
                pending_command = command_target
            else:
                pending_prompt = prompt
        else:
            ss["_hc_clear_text_input"] = True

    if pending_prompt:
        turn_ts = _iso_now()

        turn_observations: List[Dict[str, Any]] = []

        if active_user:
            observation_state = st.session_state[runtime_state_key].get(active_user, {})
            observation_buffer = st.session_state[observations_key].setdefault(active_user, [])
            metrics_buffer = st.session_state[metrics_key].setdefault(active_user, [])

            observation_result = capture_turn_observation(
                user_id=active_user,
                user_text=pending_prompt,
                user_ts=turn_ts,
                last_assistant_ts=last_assistant_timestamp(history),
                state=observation_state,
            )
            st.session_state[runtime_state_key][active_user] = dict(observation_result.state)
            turn_observations = list(observation_result.observations)
            if turn_observations:
                observation_buffer.extend(turn_observations)
                st.session_state[observations_key][active_user] = observation_buffer
            metrics_entry = {"ts": turn_ts, **observation_result.metrics}
            metrics_buffer.append(metrics_entry)
            st.session_state[metrics_key][active_user] = metrics_buffer

        user_entry = {
            "role": "user",
            "content": pending_prompt,
            "meta": {
                "ts": turn_ts,
            },
        }
        history.append(user_entry)

        persona_for_turn = persona_id if (lock_persona and persona_id) else active_persona_id
        descriptor_for_turn = None
        if lock_persona and persona_id:
            descriptor_for_turn = _safe_persona_lookup(persona_for_turn)
            st.session_state[persona_current_key] = persona_for_turn
        elif enable_personas and persona_roster:
            mode = st.session_state.get(persona_mode_key, "Manual")
            if mode == "Manual":
                persona_for_turn = _safe_active_persona_id(persona_for_turn) or persona_for_turn
            else:
                routed = route_intent(pending_prompt, dev_mode)
                if routed in valid_persona_ids:
                    persona_for_turn = routed
                    persona_set_active(
                        persona_for_turn,
                        trigger="auto_route",
                        metadata={
                            "source": page_prefix,
                            "message_preview": pending_prompt[:120],
                        },
                    )
                    if active_user:
                        st.session_state.setdefault("_persona_ctx_by_user", {})[active_user] = (
                            persona_for_turn
                        )
                else:
                    persona_for_turn = _safe_active_persona_id(persona_for_turn) or persona_for_turn
            st.session_state[persona_current_key] = persona_for_turn
            if persona_for_turn in valid_persona_ids:
                descriptor_for_turn = _safe_persona_lookup(persona_for_turn)
            if descriptor_for_turn:
                persona_meta = {
                    "title": descriptor_for_turn.title,
                    "icon": descriptor_for_turn.icon,
                    "color": descriptor_for_turn.color,
                    "description": descriptor_for_turn.description,
                }
            active_persona_id = _safe_active_persona_id(persona_for_turn) or persona_for_turn

        try:
            reply = coach_ingest_text(
                active_user,
                pending_prompt,
                dev_mode,
                history=history,
                persona_id=persona_for_turn,
                provenance_source=provenance_source,
                background_capture=st.session_state.get(capture_key, True),
                observations=turn_observations,
            )
        except Exception as exc:  # pragma: no cover - defensive UI
            reply = {
                "assistant_text": "I hit a snag while reaching the pipeline.",
                "error": f"coach_ingest_error:{exc}",
                "ucnrr_reply": {"ok": False, "reason": str(exc)},
            }

        switch_notice: Optional[str] = None
        switch_success = False
        switch_to = reply.get("next_persona")
        switch_title = reply.get("next_persona_title") or (
            switch_to.replace("_", " ").title() if isinstance(switch_to, str) else None
        )
        if switch_to:
            if enable_personas and persona_roster and switch_to in valid_persona_ids:
                try:
                    persona_set_active(
                        switch_to,
                        trigger="chat_switch",
                        metadata={
                            "source": page_prefix,
                            "message_preview": pending_prompt[:120],
                        },
                    )
                except KeyError:
                    switch_notice = f"{switch_title or switch_to} isn’t available right now."
                else:
                    st.session_state[persona_mode_force_key] = True
                    st.session_state[persona_manual_key] = switch_to
                    st.session_state[persona_current_key] = switch_to
                    active_persona_id = switch_to
                    if active_user:
                        st.session_state.setdefault("_persona_ctx_by_user", {})[active_user] = switch_to
                    switch_notice = f"Switched to {switch_title or switch_to}."
                    switch_success = True
            else:
                switch_notice = f"{switch_title or switch_to} isn’t available in this view."

        assistant_text = reply.get("assistant_text") or "I’m still thinking about that."
        if persona_for_turn == "relationship_coach":
            assistant_text = rc_scrub(assistant_text)
        assistant_meta = {
            "ts": _iso_now(),
            "badges": [],
            "badge_details": [],
        }

        if switch_notice:
            assistant_meta.setdefault("badge_details", []).append(
                {
                    "text": switch_notice,
                    "tone": "info" if switch_success else "warn",
                }
            )

        assistant_meta["persona_id"] = persona_for_turn
        if persona_meta:
            assistant_meta["persona_title"] = persona_meta.get("title", persona_for_turn)

        if reply.get("ucnrr_reply") and persona_for_turn != "relationship_coach":
            info = reply["ucnrr_reply"]
            badge_text = "UCN/RR updated" if info.get("ok", True) else f"UCN/RR error: {info.get('reason', 'unknown')}"
            tone = "success" if info.get("ok", True) else "error"
            assistant_meta.setdefault("badge_details", []).append({"text": badge_text, "tone": tone})

        if reply.get("added_by_core_ai"):
            assistant_meta.setdefault("badge_details", []).append(
                {
                    "text": f"Core AI additions: {len(reply['added_by_core_ai'])}",
                    "tone": "info",
                }
            )

        holistic_counts = reply.get("holistic") or {}
        if holistic_counts.get("ran"):
            assistant_meta.setdefault("badge_details", []).append(
                {
                    "text": (
                        "Holistic: "
                        f"{holistic_counts.get('ucn_rr_updates', 0)} adjusted, "
                        f"{holistic_counts.get('implied_additions', 0)} implied, "
                        f"{holistic_counts.get('contradictions', 0)} contradictions"
                    ),
                    "tone": "info",
                }
            )

        if reply.get("core_error"):
            core_err = reply["core_error"]
            badge = f"Core error {core_err.get('status', '?')}: {core_err.get('reason', 'unknown')}"
            assistant_meta.setdefault("badge_details", []).append({"text": badge, "tone": "error"})

        rc_capture = reply.get("rc_capture") or {}
        st.session_state[f"{page_prefix}_capture_summary"] = rc_capture
        if rc_capture.get("captured"):
            assistant_meta.setdefault("badge_details", []).append(
                {
                    "text": f"RC capture: {rc_capture['captured']} insights",
                    "tone": "success",
                }
            )
        elif rc_capture.get("reason") == "disabled":
            assistant_meta.setdefault("badge_details", []).append(
                {
                    "text": "RC capture off",
                    "tone": "warn",
                }
            )
        elif rc_capture and not rc_capture.get("ok", True):
            assistant_meta.setdefault("badge_details", []).append(
                {
                    "text": "RC capture error",
                    "tone": "error",
                }
            )

        if reply.get("persona_id"):
            assistant_meta["persona_id"] = reply.get("persona_id")
        if reply.get("persona_title"):
            assistant_meta["persona_title"] = reply.get("persona_title")

        if reply.get("canonical_suggestions"):
            assistant_meta["canonical_suggestions"] = reply["canonical_suggestions"]

        recent_changes = reply.get("recent_changes") or {}
        updated_paths = recent_changes.get("from_user") or reply.get("ucnrr_reply", {}).get("changed_keys") or []
        core_ai_paths = recent_changes.get("core_ai") or reply.get("added_by_core_ai") or []
        st.session_state[badges_key][active_user] = {
            "updated": updated_paths,
            "core_ai": core_ai_paths,
            "proposed": reply.get("canonical_suggestions") or [],
            "holistic": holistic_counts if holistic_counts.get("ran") else {},
        }

        st.session_state[context_key][active_user] = {
            "recent_changes": reply.get("recent_changes"),
            "top_curiosity": reply.get("top_curiosity"),
            "holistic": holistic_counts if holistic_counts.get("ran") else None,
        }

        assistant_entry = {
            "role": "assistant",
            "content": assistant_text,
            "meta": assistant_meta,
        }
        history.append(assistant_entry)

        if switch_success:
            greeting_text = _persona_greeting(active_persona_id)
            if active_persona_id == "relationship_coach":
                greeting_text = rc_scrub(greeting_text)
            greeting_meta = {
                "ts": _iso_now(),
                "persona_id": active_persona_id,
                "badge_details": [],
            }
            new_descriptor = _safe_persona_lookup(active_persona_id)
            if new_descriptor:
                greeting_meta["persona_title"] = new_descriptor.title
            greeting_entry = {
                "role": "assistant",
                "content": greeting_text,
                "meta": greeting_meta,
            }
            history.append(greeting_entry)

        st.session_state[msgs_key][active_user] = history
        should_rerun = True
        ss["_hc_clear_text_input"] = True

    if active_persona_id == "relationship_coach":
        capture_summary = st.session_state.get(f"{page_prefix}_capture_summary") or {}
        if capture_summary.get("captured"):
            st.caption(f"🗂️ Background capture stored {capture_summary['captured']} insights this turn.")
        elif capture_summary.get("reason") == "disabled":
            st.caption("🛑 Background capture is turned off for Relationship Coach.")


    if enable_personas and persona_roster:
        descriptor_for_body = _safe_persona_lookup(active_persona_id)
        if descriptor_for_body and descriptor_for_body.render_panel:
            descriptor_for_body.render_panel(active_user)

    if callable(extra_body_renderer):
        extra_body_renderer(active_user)

    if pending_command and active_user:
        st.session_state[persona_mode_force_key] = True
        set_persona_for_user(
            active_user,
            pending_command,
            reason="chat_command",
            metadata={"source": page_prefix, "message_preview": prompt[:120]},
        )
        st.session_state[persona_manual_key] = pending_command
        st.session_state[persona_current_key] = pending_command
        ss["_hc_clear_text_input"] = True

    if should_rerun and not pending_command:
        _trigger_rerun()

    if st.session_state.pop("_deferred_rerun", False):
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()


def chat_surface(**kwargs: Any) -> None:
    """Wrapper alias for render_coach_tab to align with newer call sites."""

    render_coach_tab(**kwargs)

_PERSONA_COMMAND_ALIASES = {
    "relationship_coach": ("relationship coach", "rc"),
    "photo": ("photo coach", "photo"),
    "padna": ("padna", "padna coach"),
    "head_coach": ("head coach", "main coach", "primary coach"),
}


def _match_persona_command(text: str) -> Optional[str]:
    lowered = (text or "").strip().lower()
    if not lowered:
        return None
    for persona_id, aliases in _PERSONA_COMMAND_ALIASES.items():
        for alias in aliases:
            if f"switch to {alias}" in lowered:
                return persona_id
            if f"switch over to {alias}" in lowered:
                return persona_id
            if f"switch back to {alias}" in lowered:
                return persona_id
    return None
