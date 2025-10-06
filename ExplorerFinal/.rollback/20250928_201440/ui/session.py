# ExplorerFinal/ui/session.py
from __future__ import annotations

import os, json, requests, yaml
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

import streamlit as st

from ui.onboarding_state import mark_completed

# ---- Config ----
UCNRR_BASE = os.getenv("UCNRR_BASE", "http://127.0.0.1:8011").rstrip("/")
CORE_BASE  = os.getenv("CORE_BASE",  "http://127.0.0.1:8015").rstrip("/")

_BASE_PATH = Path(__file__).resolve().parents[1]
_DEFAULT_CORE_STORAGE = (_BASE_PATH / "../ReDNACoreDemo/data/storage").resolve()
_DEFAULT_CORE_LEGACY = (_BASE_PATH / "../ReDNACoreDemo/data/users").resolve()

CORE_DATA_DIR = Path(
    os.getenv("CORE_DATA_DIR")
    or os.getenv("REDNA_CORE_DATA")
    or str(_DEFAULT_CORE_STORAGE)
).expanduser().resolve()
CORE_USERS_DIR = CORE_DATA_DIR / "users"
CORE_LEGACY_USERS_DIR = Path(
    os.getenv("CORE_LEGACY_USERS_DIR", str(_DEFAULT_CORE_LEGACY))
).expanduser().resolve()

UCNRR_DATA_DIR = Path(
    os.getenv("UCNRR_DATA_DIR", str((_BASE_PATH / "../UCN_RR_Demo/data").resolve()))
).expanduser().resolve()
UCNRR_USERS_DIR = UCNRR_DATA_DIR / "users"
TRAITS_REGISTRY_PATH = Path(
    os.getenv(
        "TRAITS_REGISTRY_PATH",
        str((_BASE_PATH / "../ReDNACoreDemo/data/config/traits_registry.yaml").resolve()),
    )
).expanduser().resolve()
_TRAIT_META_KEYS = {"type", "choices", "enum", "notes", "description", "instructions", "help", "examples"}

SESSION_USER_KEY = "_active_user_id"
LEGACY_USER_KEYS = ("user_id", "active_user_id", "active_user")
USER_TOAST_KEY = "_user_loaded_toast"
PERSONA_MAP_KEY = "_persona_ctx_by_user"
PERSONA_TOAST_KEY = "_toast_persona_switched"


@dataclass(frozen=True)
class PersonaDescriptor:
    key: str
    label: str
    icon: str


_DEFAULT_PERSONA_KEY = "head coach"

_PERSONA_DESCRIPTORS: Dict[str, PersonaDescriptor] = {
    "head coach": PersonaDescriptor("head coach", "Head Coach", "🧠"),
    "padna": PersonaDescriptor("padna", "PaDNA", "🧬"),
    "photo": PersonaDescriptor("photo", "Photo Coach", "📷"),
    "rc": PersonaDescriptor("rc", "Relationship Coach", "💞"),
}

_PERSONA_ALIASES: Dict[str, str] = {
    "head": "head coach",
    "head coach": "head coach",
    "head_coach": "head coach",
    "headcoach": "head coach",
    "hc": "head coach",
    "relationship": "rc",
    "relationship coach": "rc",
    "relationship_coach": "rc",
    "rc": "rc",
    "photo": "photo",
    "photo coach": "photo",
    "photo_coach": "photo",
    "padna": "padna",
    "padna coach": "padna",
    "padna_coach": "padna",
}

_PERSONA_BUS_IDS: Dict[str, str] = {
    "head coach": "head_coach",
    "padna": "padna",
    "photo": "photo",
    "rc": "relationship_coach",
}

_TRUE_SET = {"1", "true", "yes", "on"}

PHOTO_COACH_ENABLED = os.getenv("PHOTO_COACH_ENABLED", "true").strip().lower() in _TRUE_SET
PADNA_ENABLED = os.getenv("PADNA_ENABLED", "true").strip().lower() in _TRUE_SET
RC_ENABLED = os.getenv("RC_ENABLED", "true").strip().lower() in _TRUE_SET


def normalize_persona_key(raw: Optional[str]) -> str:
    token = (raw or "").strip().lower()
    if token in _PERSONA_DESCRIPTORS:
        return token
    return _PERSONA_ALIASES.get(token, _DEFAULT_PERSONA_KEY)


def _canonical_persona_key(raw: Optional[str]) -> str:
    return normalize_persona_key(raw)


def get_persona_descriptor(key: Optional[str]) -> PersonaDescriptor:
    canonical = normalize_persona_key(key)
    return _PERSONA_DESCRIPTORS[canonical]


def persona_choices() -> List[Dict[str, str]]:
    return [
        {"key": desc.key, "label": desc.label, "icon": desc.icon}
        for desc in _PERSONA_DESCRIPTORS.values()
    ]


def persona_status(key: str) -> Tuple[str, str]:
    canonical = normalize_persona_key(key)
    if canonical == "photo":
        return ("ready", "OK") if PHOTO_COACH_ENABLED else ("off", "flag off")
    if canonical == "padna":
        return ("ready", "OK") if PADNA_ENABLED else ("off", "flag off")
    if canonical == "rc":
        return ("ready", "OK") if RC_ENABLED else ("off", "flag off")
    return "ready", "OK"


def current_persona_for(user_id: str) -> str:
    mapping: Dict[str, str] = st.session_state.setdefault(PERSONA_MAP_KEY, {})
    normalized_user = (user_id or "").strip()
    if not normalized_user:
        return _DEFAULT_PERSONA_KEY
    stored = mapping.get(normalized_user)
    canonical = _canonical_persona_key(stored)
    if stored != canonical:
        mapping[normalized_user] = canonical
    elif canonical not in _PERSONA_DESCRIPTORS:
        mapping[normalized_user] = _DEFAULT_PERSONA_KEY
        canonical = _DEFAULT_PERSONA_KEY
    return canonical


def get_persona_for_user(user_id: str, default: str = "head_coach") -> str:
    """Return the persona bus id for a user, seeding defaults when missing."""

    normalized_user = (user_id or "").strip()
    canonical_default = _canonical_persona_key(default)
    if not normalized_user:
        return _PERSONA_BUS_IDS.get(canonical_default, "head_coach")
    canonical = current_persona_for(normalized_user)
    return _PERSONA_BUS_IDS.get(canonical, "head_coach")

# ---- Session helpers ----
def get_user_id() -> str:
    return st.session_state.get(SESSION_USER_KEY, "").strip()

def set_user_id(uid: str) -> None:
    value = (uid or "").strip()
    st.session_state[SESSION_USER_KEY] = value
    for key in LEGACY_USER_KEYS:
        st.session_state[key] = value

def ensure_state() -> None:
    st.session_state.setdefault(SESSION_USER_KEY, "")
    for key in LEGACY_USER_KEYS:
        st.session_state.setdefault(key, "")


def _clear_user_caches() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass


def switch_active_user(user_id: str, *, trigger_toast: bool = True) -> bool:
    ensure_state()
    normalized = (user_id or "").strip()
    current = get_user_id()
    if normalized == current:
        return False
    set_user_id(normalized)
    persona_key = current_persona_for(normalized) if normalized else _DEFAULT_PERSONA_KEY
    if normalized:
        try:
            mark_completed(normalized)
        except Exception:
            pass
        try:
            from ui.persona_bus import set_active as persona_set_active  # type: ignore

            persona_set_active(
                _PERSONA_BUS_IDS.get(persona_key, "head_coach"),
                trigger="user_switch",
                metadata={"user_id": normalized},
            )
        except Exception:
            pass
    else:
        try:
            from ui.persona_bus import reset as persona_reset  # type: ignore

            persona_reset(optional=True)
        except Exception:
            pass
    _clear_user_caches()
    if trigger_toast and normalized:
        st.session_state[USER_TOAST_KEY] = normalized
    return True


def consume_user_loaded_toast() -> Optional[str]:
    return st.session_state.pop(USER_TOAST_KEY, None)


def consume_persona_toast() -> Optional[str]:
    return st.session_state.pop(PERSONA_TOAST_KEY, None)


def safe_rerun() -> None:
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()


def set_persona_for_user(
    user_id: str,
    persona_id: str,
    reason: str = "manual",
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Assign a persona to the given user and trigger a refresh when it changes."""

    canonical = normalize_persona_key(persona_id)
    descriptor = get_persona_descriptor(canonical)
    status_state, status_note = persona_status(canonical)
    ss = st.session_state

    if status_state == "off":
        ss["_toast_persona_err"] = f"{descriptor.label} is disabled ({status_note})."
        return

    mapping: Dict[str, str] = ss.setdefault(PERSONA_MAP_KEY, {})
    normalized_user = (user_id or "").strip()
    previous = _canonical_persona_key(mapping.get(normalized_user)) if normalized_user else None
    changed = False
    if normalized_user:
        if previous != canonical:
            changed = True
        mapping[normalized_user] = canonical

    payload_meta: Dict[str, Any] = dict(metadata or {})
    if normalized_user and "user_id" not in payload_meta:
        payload_meta["user_id"] = normalized_user
    if reason:
        payload_meta.setdefault("reason", reason)

    source = payload_meta.get("source")
    manual_reasons = {"manual", "manual_selector", "persona_chip", "dropdown", "chat_command"}
    if reason in manual_reasons:
        ss["_persona_force_manual"] = True
        if source:
            ss[f"_persona_force_manual_{source}"] = True

    bus_id = _PERSONA_BUS_IDS.get(canonical, "head_coach")
    try:
        from ui.persona_bus import set_active as persona_set_active  # type: ignore
    except Exception:
        persona_set_active = None

    error_message: Optional[str] = None
    if persona_set_active is not None:
        try:
            persona_set_active(
                bus_id,
                trigger=reason,
                metadata=payload_meta,
            )
        except KeyError:
            error_message = f"{descriptor.label} isn't available right now."

    if error_message:
        if normalized_user and previous not in (None, canonical):
            mapping[normalized_user] = previous  # revert assignment on failure
        ss["_toast_persona_err"] = error_message
        ss["_deferred_rerun"] = True
        return

    if status_state != "ready":
        note_suffix = f" ({status_note})" if status_note and status_note != "OK" else ""
        ss["_toast_persona_info"] = f"{descriptor.label} availability: {status_state}{note_suffix}"
        ss["_deferred_rerun"] = True

    if changed:
        toast_message = f"Switched to {descriptor.label}"
        ss["_toast_persona_switched"] = toast_message
        ss[PERSONA_TOAST_KEY] = toast_message
        ss["_deferred_rerun"] = True


def render_user_banner(label: str = "Active user") -> str:
    """Render the prominently styled active-user banner and return the current user id."""
    ensure_state()
    uid = get_user_id()
    display_name = uid or "No active user selected"
    st.markdown(
        f"""
        <div style=\"font-size:2rem;font-weight:700;margin-bottom:0.75rem;\">
          👤 {display_name}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if uid:
        flat = core_get_resolved_flat(uid)
        rows = flat.get("rows", []) if isinstance(flat, dict) else []
        padna_rows = [row for row in rows if isinstance(row, dict) and str(row.get("canonical_path", "")).startswith("PaDNA.")]
        path_aliases = sum(1 for row in rows if isinstance(row, dict) and row.get("path_alias"))
        value_aliases = sum(1 for row in rows if isinstance(row, dict) and row.get("value_alias"))
        ai_canon = sum(
            1
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("provenance"), dict)
            and row["provenance"].get("canonical_mapper")
        )
        st.caption(
            f"Canonical PaDNA traits: {len(padna_rows)} • Path aliases: {path_aliases} • Value aliases: {value_aliases} • AI mapped: {ai_canon}"
        )
    return uid


@lru_cache()
def load_trait_catalog() -> Dict[str, Dict[str, Any]]:
    """Return a flattened map of trait path -> metadata from the registry."""
    try:
        with open(TRAITS_REGISTRY_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:
        return {}

    catalog: Dict[str, Dict[str, Any]] = {}

    def _collect(node: Any, prefix: str = "") -> None:
        if not isinstance(node, dict):
            return
        is_leaf = any(k in node for k in _TRAIT_META_KEYS)
        if is_leaf and prefix:
            entry = {k: node.get(k) for k in _TRAIT_META_KEYS if k in node}
            catalog[prefix] = entry
        for key, value in node.items():
            if key in _TRAIT_META_KEYS:
                continue
            if not isinstance(value, dict):
                continue
            new_prefix = f"{prefix}.{key}" if prefix else key
            _collect(value, new_prefix)

    _collect(data)
    return catalog

# ---- Data access ----
def list_users(max_items: int = 500) -> List[str]:
    roots = [CORE_USERS_DIR, CORE_LEGACY_USERS_DIR, UCNRR_USERS_DIR]
    seen: Set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                seen.add(p.name)
                if len(seen) >= max_items:
                    return sorted(seen)
    return sorted(seen)

def core_get_resolved(user_id: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{CORE_BASE}/resolved/{user_id}", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"user_id": user_id, "schema_version": 4, "resolved": {}}

def core_get_resolved_flat(user_id: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{CORE_BASE}/resolved/flat/{user_id}", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"rows": []}


def core_get_last_holistic(user_id: str) -> Dict[str, Any]:
    try:
        path = CORE_USERS_DIR / user_id / "last_holistic.json"
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}

def ucnrr_ingest_text(user_id: str, text: str) -> Dict[str, Any]:
    try:
        payload = {"user_id": user_id, "text": text}
        r = requests.post(f"{UCNRR_BASE}/ingest_text", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"ok": False, "reason": f"ucnrr_error:{e}"}

# ---- UI widgets ----
def user_picker(label_left: str = "Existing users", label_right: str = "Active user") -> Tuple[str, str]:
    """Dropdown + input, returns (chosen_from_list, active_input)."""
    ensure_state()
    users = list_users()
    dd = st.selectbox(label_left, ["—"] + users, index=0, key="existing_users_dd")
    active_display = get_user_id() or ""
    st.text_input(label_right, value=active_display, disabled=True, key="active_user_display")
    cols = st.columns([1,1,8])
    with cols[0]:
        if st.button("Load user", type="primary"):
            use_id = dd if dd != "—" else ""
            if use_id and switch_active_user(use_id):
                safe_rerun()
    with cols[1]:
        if st.button("Reload"):
            safe_rerun()
    return dd, active_display

def freeform_block(title: str = "Freeform Text") -> None:
    """Shared ‘free text → UCN/RR → Core’ block."""
    uid = get_user_id()
    st.subheader(title)
    with st.expander("What should I learn?", expanded=True):
        text = st.text_area("", height=180, placeholder="Try: “I'm around 6 feet” or “I've been a husband for 25 years”")
        if st.button("Process", type="primary", use_container_width=False):
            if not uid:
                st.warning("Pick an active user (top of page) before processing.")
            elif not text.strip():
                st.info("Type something for me to learn.")
            else:
                res = ucnrr_ingest_text(uid, text.strip())
                st.json(res, expanded=False)
                # force a refresh so tables show latest Core view
                st.rerun()

def resolved_flat_table() -> None:
    uid = get_user_id()
    st.subheader("Resolved (flat)")
    if not uid:
        st.info("Pick an active user to view resolved traits.")
        return
    flat = core_get_resolved_flat(uid)
    rows = flat.get("rows", [])
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No resolved traits yet.")
