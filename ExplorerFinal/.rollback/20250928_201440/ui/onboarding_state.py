from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st
import yaml
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BASICS_PATH = DATA_DIR / "onboarding_basics.yaml"
WYR_PATH = DATA_DIR / "onboarding_wyr.yaml"

DEFAULT_COACH_NAME = "Alex Harmony"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_basics() -> Dict[str, List[str]]:
    data = _load_yaml(BASICS_PATH)
    return {
        "age_ranges": data.get("age_ranges", []),
        "genders": data.get("genders", []),
        "orientations": data.get("orientations", []),
        "languages": data.get("languages", []),
        "relationship_statuses": data.get("relationship_statuses", []),
    }


def load_wyr_questions() -> List[Dict[str, Any]]:
    data = _load_yaml(WYR_PATH)
    return data.get("questions", [])


# ---- Session state management ----

STATE_KEY = "onboarding_state"


def _empty_state() -> Dict[str, Any]:
    return {
        "phase": None,
        "basics": {},
        "coach_name": DEFAULT_COACH_NAME,
        "wyr_count": 0,
        "current_wyr": None,
        "selected_wyr": None,
        "basics_submitted": False,
        "wyr_submitted": False,
        "started_at": None,
        "user_id": None,
        "completed": False,
    }


def ensure_state(user_id: Optional[str] = None) -> Dict[str, Any]:
    state = st.session_state.setdefault(STATE_KEY, _empty_state())
    if user_id is not None and state.get("user_id") not in (None, user_id):
        st.session_state[STATE_KEY] = _empty_state()
        state = st.session_state[STATE_KEY]
    if user_id is not None:
        state["user_id"] = user_id
    return state


def reset_state() -> None:
    st.session_state[STATE_KEY] = _empty_state()


def start_onboarding(user_id: Optional[str] = None) -> Dict[str, Any]:
    state = ensure_state(user_id)
    state.update(
        {
            "phase": "p1",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed": False,
        }
    )
    return state


def end_onboarding(mark_complete: bool = True) -> Dict[str, Any]:
    state = ensure_state()
    state["phase"] = None
    state["current_wyr"] = None
    if mark_complete:
        state["completed"] = True
    return state


def mark_completed(user_id: Optional[str]) -> None:
    if not user_id:
        return
    state = ensure_state(user_id)
    state["phase"] = None
    state["completed"] = True


def set_basic(category: str, value: str) -> None:
    state = ensure_state()
    basics = state.setdefault("basics", {})
    basics[category] = value


def basics_complete() -> bool:
    state = ensure_state()
    basics = state.get("basics", {})
    required = {"age_range", "gender", "orientation", "language", "relationship_status"}
    return required.issubset(basics.keys())


def current_phase() -> Optional[str]:
    return ensure_state().get("phase")


def advance_phase(next_phase: str) -> None:
    state = ensure_state()
    state["phase"] = next_phase


def get_coach_name() -> str:
    return ensure_state().get("coach_name", DEFAULT_COACH_NAME)


def set_coach_name(name: str) -> None:
    ensure_state()["coach_name"] = name.strip() or DEFAULT_COACH_NAME


def increment_wyr() -> None:
    state = ensure_state()
    state["wyr_count"] = int(state.get("wyr_count", 0)) + 1


def get_wyr_count() -> int:
    return int(ensure_state().get("wyr_count", 0))


def next_wyr_question() -> Optional[Dict[str, Any]]:
    questions = load_wyr_questions()
    if not questions:
        return None
    question = random.choice(questions)
    ensure_state()["current_wyr"] = question
    ensure_state()["selected_wyr"] = None
    return question


def current_wyr_question() -> Optional[Dict[str, Any]]:
    state = ensure_state()
    question = state.get("current_wyr")
    if question:
        return question
    return next_wyr_question()


def onboarding_active(user_id: Optional[str] = None) -> bool:
    state = ensure_state(user_id)
    return state.get("phase") is not None


def onboarding_completed(user_id: Optional[str] = None) -> bool:
    return bool(ensure_state(user_id).get("completed"))


def should_show_onboarding_tab(user_id: Optional[str]) -> bool:
    if not user_id:
        return True
    state = ensure_state(user_id)
    return not state.get("completed")
