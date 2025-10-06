from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import streamlit as st

from .coach_api import apply_canonical_lines, record_free_text
from .onboarding_state import (
    DEFAULT_COACH_NAME,
    advance_phase,
    basics_complete,
    current_phase,
    current_wyr_question,
    end_onboarding,
    ensure_state,
    get_coach_name,
    get_wyr_count,
    increment_wyr,
    load_basics,
    next_wyr_question,
    onboarding_active,
    onboarding_completed,
    reset_state,
    set_basic,
    set_coach_name,
    start_onboarding,
)
from .session import set_user_id

try:  # pragma: no cover - guard for contexts without persona bus
    from .persona_bus import set_active as persona_set_active  # type: ignore
except Exception:  # pragma: no cover
    persona_set_active = None  # type: ignore

try:  # pragma: no cover - package vs. script import
    from explorer_api import ucnrr_init_user
except ImportError:  # pragma: no cover
    from ..explorer_api import ucnrr_init_user  # type: ignore

BASICS_CANONICAL = {
    "age_range": "SocDNA.Demographics.AgeRange",
    "gender": "SocDNA.Identity.Gender",
    "orientation": "SocDNA.Identity.Orientation",
    "language": "SocDNA.Prefs.LanguagePrimary",
    "relationship_status": "SocDNA.Relationship.Status",
}

COACH_PROMOS: List[Tuple[str, str]] = [
    ("Bucket List Coach", "Prompts fun adventures and shared goals."),
    ("Physical Attribute Coach", "Explores body confidence and appreciation."),
    ("Initial Couples Coach", "Sets couple-focused conversation starters."),
    ("Initial Looks Rater Coach", "Guides first-impression feedback kindly."),
]

OTHER_OPTIONS: List[Tuple[str, str]] = [
    ("A", "How ReDNA works & quick quiz"),
    ("B", "Share a thought with the Head Coach"),
    ("C", "Pick our relationship type"),
    ("D", "Dive into Bucket List ideas"),
    ("E", "Explore Physical Attribute Coach"),
    ("F", "Start Initial Couples Coach"),
    ("G", "Launch Initial Looks Rater Coach"),
]

CONSENT_LINE = "Data stays private unless you choose to share it. For positive, respectful use only."


def _rerun() -> None:
    fn = getattr(st, "rerun", None)
    if callable(fn):
        fn()
        return
    fn = getattr(st, "experimental_rerun", None)
    if callable(fn):
        fn()


def _go_to_head_coach() -> None:
    if callable(persona_set_active):
        persona_set_active(
            "head_coach",
            trigger="onboarding_complete",
            metadata={"source": "onboarding"},
        )
    switch_page = getattr(st, "switch_page", None)
    if callable(switch_page):
        try:
            switch_page("pages/05_Head_Coach.py")
            return
        except Exception:
            pass
    st.experimental_set_query_params(page="Head Coach")
    st.experimental_rerun()


def _post_text(user_id: str, text: str) -> None:
    record_free_text(
        user_id,
        text,
        persona_id="head_coach",
        actor="user",
        source="onboarding",
    )


def render_sidebar_controls(user_id: str) -> None:
    state = ensure_state(user_id)
    if st.session_state.pop("onb_clear_input", False):
        st.session_state["onb_new_user_input"] = ""

    new_user_value = st.sidebar.text_input(
        "Create new user",
        key="onb_new_user_input",
    )
    if st.sidebar.button("Create", type="primary"):
        username = st.session_state.get("onb_new_user_input", "").strip()
        if not username:
            st.session_state["onb_creation_error"] = "Enter a user id before creating."
            _rerun()
            return
        try:
            resp = ucnrr_init_user(username)
            new_id = resp.get("user_id", username)
            set_user_id(new_id)
            reset_state()
            start_onboarding(new_id)
            st.session_state["onb_creation_status"] = f"User `{new_id}` created. Starting onboarding."
            st.session_state["onb_clear_input"] = True
        except Exception as exc:
            st.session_state["onb_creation_error"] = f"Create failed: {exc}"[:200]
        _rerun()

    if onboarding_active(user_id):
        if st.sidebar.button("End Onboarding", help="Skip onboarding and return to coaching"):
            end_onboarding(mark_complete=True)
            _rerun()
    st.sidebar.caption(CONSENT_LINE)
    st.sidebar.write("\n")


def render_onboarding_panel(user_id: str) -> None:
    state = ensure_state(user_id)
    status_msg = st.session_state.pop("onb_creation_status", None)
    error_msg = st.session_state.pop("onb_creation_error", None)
    if status_msg:
        st.success(status_msg)
    if error_msg:
        st.error(error_msg)
    phase = current_phase()
    if not phase:
        if onboarding_completed(user_id):
            _go_to_head_coach()
        else:
            st.info("Create a new user on the left to begin onboarding.")
        return

    st.markdown(f"### Onboarding — Phase {phase.upper() if isinstance(phase, str) else ''}")
    st.caption(CONSENT_LINE)

    if phase == "p1":
        _render_phase_one(user_id)
    elif phase == "p1_wyr":
        _render_phase_one_wyr(user_id)
    elif phase == "p2":
        _render_phase_two(user_id)
    elif phase == "p3":
        _render_phase_three(user_id)


def _render_phase_one(user_id: str) -> None:
    ensure_state(user_id)
    basics = load_basics()
    st.markdown("#### Basic setup")
    st.caption("RR is at 0% for now — let’s gather a few quick signals.")
    fields = [
        ("age_range", "Age Range", basics.get("age_ranges", [])),
        ("gender", "Gender", basics.get("genders", [])),
        ("orientation", "Orientation", basics.get("orientations", [])),
        ("language", "Preferred Language", basics.get("languages", [])),
        ("relationship_status", "Relationship Status", basics.get("relationship_statuses", [])),
    ]

    for key, label, options in fields:
        _render_option_buttons(user_id, key, label, options)

    if basics_complete():
        st.success("Basics captured! Next up: a quick intro and one playful question.")
        advance_phase("p1_wyr")
        _rerun()


def _render_option_buttons(user_id: str, key: str, label: str, options: List[str]) -> None:
    st.write(f"**{label}**")
    cols = st.columns(min(len(options), 3) or 1)
    state = ensure_state(user_id)
    basics_state = state.setdefault("basics", {})
    current_value = basics_state.get(key)

    for idx, option in enumerate(options):
        col = cols[idx % len(cols)]
        with col:
            is_selected = current_value == option
            if st.button(option, key=f"onb_{key}_{option}", help=None, type="primary" if is_selected else "secondary"):
                if option == "Other":
                    basics_state.pop(key, None)
                else:
                    set_basic(key, option)
                    state["basics_submitted"] = False
                _rerun()

    if key in basics_state and basics_state.get(key) not in (None, "") and basics_state.get(key) != "Other":
        set_basic(key, basics_state[key])

    if key not in basics_state:
        other_value = st.text_input(f"Enter {label}", key=f"onb_other_{key}")
        if other_value and st.button(f"Save {label}", key=f"onb_save_{key}"):
            set_basic(key, other_value)
            state["basics_submitted"] = False
            _rerun()


def _render_phase_one_wyr(user_id: str) -> None:
    ensure_state(user_id)
    st.markdown("#### Meet your Head Coach")
    current_name = get_coach_name()
    new_name = st.text_input("Head Coach name", value=current_name, key="onb_coach_name")
    set_coach_name(new_name)

    st.write("Let’s get a feel for your style. Pick the option that resonates most:")
    state = ensure_state(user_id)
    question = current_wyr_question()
    if not question:
        st.warning("No questions available right now.")
        return

    st.write(f"**Would You Rather — {question.get('title', '')}**")
    st.caption("Sharing one choice gives us a tiny RR lift — I wonder if this nudges us to ~5%.")
    options = question.get("options", {})
    cols = st.columns(2)
    selected = state.get("selected_wyr")
    for idx, (code, text) in enumerate(options.items()):
        with cols[idx % 2]:
            label = f"{code}: {text}"
            button_type = "primary" if selected and selected.get("code") == code else "secondary"
            if st.button(label, key=f"onb_wyr_{code}", type=button_type):
                state["selected_wyr"] = {
                    "code": code,
                    "text": text,
                    "title": question.get("title", ""),
                }
                state["wyr_submitted"] = False
                _rerun()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("New Question", key="onb_new_wyr"):
            next_wyr_question()
            _rerun()
    with col2:
        if st.button("Submit & continue", key="onb_submit_phase1", disabled=not (basics_complete() and state.get("selected_wyr"))):
            lines: List[str] = []
            summary_parts: List[str] = []

            if not state.get("basics_submitted"):
                basics = state.get("basics", {})
                for key, value in basics.items():
                    path = BASICS_CANONICAL.get(key)
                    if path and value:
                        lines.append(f"{path}={value}")
                        label = key.replace("_", " ").title()
                        summary_parts.append(f"{label}: {value}")
                state["basics_submitted"] = True

            selected = state.get("selected_wyr")
            if selected and not state.get("wyr_submitted"):
                lines.append(f"PrefDNA.Bonding.Style={selected['code']}")
                summary_parts.append(
                    f"WYR {selected.get('title', '')}: {selected['code']} — {selected['text']}"
                )
                state["wyr_submitted"] = True
                increment_wyr()

            if lines:
                apply_canonical_lines(
                    user_id,
                    lines,
                    persona_id="head_coach",
                    actor="user",
                    source="onboarding",
                )
            if summary_parts:
                _post_text(user_id, "Onboarding selections: " + "; ".join(summary_parts))

            advance_phase("p2")
            _rerun()
    with col3:
        if st.button("End Onboarding", key="onb_end_p1"):
            end_onboarding()
            _rerun()


def _render_phase_two(user_id: str) -> None:
    ensure_state(user_id)
    st.markdown("#### Quick coach promos")
    st.caption("RR is still speculative (~5%) — pick what you’d like to explore next.")
    for title, blurb in COACH_PROMOS:
        if st.button(title, key=f"onb_promo_{title}"):
            _post_text(user_id, f"Interested in {title}: {blurb}")
            st.info(f"Noted! {title} queued up.")

    if st.button("Continue", type="primary", key="onb_continue_p3"):
        advance_phase("p3")
        _rerun()


def _render_phase_three(user_id: str) -> None:
    ensure_state(user_id)
    st.markdown("#### Other options")
    st.caption("RR is ready to grow as we explore — choose what feels right next.")
    cols = st.columns(2)
    for idx, (code, label) in enumerate(OTHER_OPTIONS):
        with cols[idx % 2]:
            if st.button(f"{code}. {label}", key=f"onb_other_{code}"):
                _post_text(user_id, f"Onboarding option {code}: {label}")
                st.success(f"Logged choice {code} — {label}")

    if st.button("Finish Onboarding", type="primary", key="onb_finish"):
        end_onboarding()
        _rerun()
