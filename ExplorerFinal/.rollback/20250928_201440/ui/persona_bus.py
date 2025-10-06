"""Shared persona bus for coordinating Head Coach personas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

try:  # Streamlit is optional when running tests or scripts
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - fallback for non-Streamlit contexts
    st = None  # type: ignore

try:  # persona cards are optional during boot
    from . import persona_cards_registry as _CARD_REGISTRY  # type: ignore
except Exception:  # pragma: no cover - fallback when registry missing
    _CARD_REGISTRY = None  # type: ignore


OnHook = Callable[[str, Optional[Dict[str, Any]]], None]
RenderHook = Callable[[str], None]


@dataclass
class PersonaDescriptor:
    """Metadata and hooks describing a coach persona."""

    id: str
    title: str
    icon: str = ""
    color: str = "#1F2933"
    description: str = ""
    ribbon_caption: Optional[str] = None
    render_panel: Optional[RenderHook] = None
    render_sidebar: Optional[RenderHook] = None
    on_enter: Optional[OnHook] = None
    on_exit: Optional[OnHook] = None
    capabilities: Dict[str, Callable[..., Any]] = field(default_factory=dict)

    def public_payload(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "icon": self.icon,
            "color": self.color,
            "description": self.description,
            "ribbon_caption": self.ribbon_caption,
        }
        if _CARD_REGISTRY is not None:
            try:
                card = _CARD_REGISTRY.get_card(self.id)  # type: ignore[attr-defined]
            except Exception:
                card = None
            if card:
                data = card.payload() if hasattr(card, "payload") else dict(card)
                payload.update({
                    "icon": data.get("icon", payload["icon"]),
                    "color": data.get("accent", payload["color"]),
                    "description": data.get("description", payload["description"]),
                    "tagline": data.get("tagline"),
                    "keywords": data.get("keywords", []),
                    "honesty_mode": data.get("honesty_mode"),
                    "allowed_honesty": data.get("allowed_honesty", []),
                    "vibe_keywords": data.get("vibe_keywords", []),
                    "beta": data.get("beta", False),
                })
        return payload


_STATE_KEY = "persona_bus_state"
_CTX_PREFIX = "persona_ctx_"

_REGISTRY: Dict[str, PersonaDescriptor] = {}
_FALLBACK_STATE: Dict[str, Any] = {"active": None, "log": []}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_streamlit() -> bool:
    return st is not None and hasattr(st, "session_state")


def _state() -> Dict[str, Any]:
    if _is_streamlit():
        if _STATE_KEY not in st.session_state:
            st.session_state[_STATE_KEY] = {"active": None, "log": []}
        return st.session_state[_STATE_KEY]
    return _FALLBACK_STATE


def _context_key(persona_id: str) -> str:
    return f"{_CTX_PREFIX}{persona_id}"


def register_persona(descriptor: PersonaDescriptor, *, overwrite: bool = False) -> None:
    if not overwrite and descriptor.id in _REGISTRY:
        raise ValueError(f"Persona '{descriptor.id}' already registered")
    _REGISTRY[descriptor.id] = descriptor


def list_registered() -> List[PersonaDescriptor]:
    return list(_REGISTRY.values())


def ensure_active(default_id: str = "head_coach") -> PersonaDescriptor:
    state = _state()
    active_id = state.get("active")
    if active_id and active_id in _REGISTRY:
        return _REGISTRY[active_id]
    if default_id in _REGISTRY:
        set_active(default_id, trigger="bootstrap")
        return _REGISTRY[default_id]
    if not _REGISTRY:
        raise RuntimeError("No personas registered")
    first = next(iter(_REGISTRY))
    set_active(first, trigger="bootstrap")
    return _REGISTRY[first]


def _run_hook(hook: Optional[OnHook], persona_id: str, metadata: Optional[Dict[str, Any]]) -> None:
    if callable(hook):
        hook(persona_id, metadata)


def set_active(
    persona_id: str,
    *,
    trigger: str = "manual",
    metadata: Optional[Dict[str, Any]] = None,
) -> PersonaDescriptor:
    if persona_id not in _REGISTRY:
        raise KeyError(f"Persona '{persona_id}' is not registered")

    state = _state()
    current_id = state.get("active")
    if current_id == persona_id:
        return _REGISTRY[persona_id]

    current_descriptor = _REGISTRY.get(current_id) if current_id else None
    next_descriptor = _REGISTRY[persona_id]

    log_entry = {
        "ts": _now(),
        "from": current_id,
        "to": persona_id,
        "trigger": trigger,
        "meta": metadata or {},
    }
    state.setdefault("log", []).append(log_entry)

    _run_hook(current_descriptor.on_exit if current_descriptor else None, persona_id, metadata)
    state["active"] = persona_id
    _run_hook(next_descriptor.on_enter, persona_id, metadata)
    return next_descriptor


def get_active_id(default_id: str = "head_coach") -> str:
    descriptor = ensure_active(default_id)
    return descriptor.id


def get_active_descriptor(default_id: str = "head_coach") -> PersonaDescriptor:
    return ensure_active(default_id)


def get_persona(persona_id: str) -> Optional[PersonaDescriptor]:
    return _REGISTRY.get(persona_id)


def get_context(persona_id: Optional[str] = None) -> Dict[str, Any]:
    pid = persona_id or get_active_id()
    key = _context_key(pid)
    if _is_streamlit():
        st.session_state.setdefault(key, {})
        return st.session_state[key]
    return _FALLBACK_STATE.setdefault(key, {})


def set_context_value(persona_id: Optional[str], key: str, value: Any) -> None:
    ctx = get_context(persona_id)
    ctx[key] = value


def handoff_log(limit: int = 50) -> List[Dict[str, Any]]:
    state = _state()
    log: List[Dict[str, Any]] = state.get("log", [])
    return log[-limit:]


def reset(optional: bool = False) -> None:
    if optional and not _REGISTRY:
        return
    if _is_streamlit() and _STATE_KEY in st.session_state:
        st.session_state[_STATE_KEY] = {"active": None, "log": []}
        for descriptor in _REGISTRY.values():
            key = _context_key(descriptor.id)
            st.session_state.pop(key, None)
    else:
        _FALLBACK_STATE.clear()
        _FALLBACK_STATE.update({"active": None, "log": []})


def public_roster() -> List[Dict[str, Any]]:
    roster: List[Dict[str, Any]] = []
    active_id = _state().get("active")
    for descriptor in list_registered():
        payload = descriptor.public_payload()
        payload["active"] = descriptor.id == active_id
        roster.append(payload)
    return roster

