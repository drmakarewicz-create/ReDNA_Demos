"""Streamlit dev surface for Relationship Coach persona scaffolding."""

from __future__ import annotations

try:
    from .. import _prelude  # noqa: F401
    from .. import _bootstrap  # noqa: F401
except Exception:  # pragma: no cover - fallback when executed as script
    import pathlib
    import sys

    _f = pathlib.Path(__file__).resolve()
    sys.path.insert(0, str(_f.parent))
    sys.path.insert(0, str(_f.parent.parent))
    import ExplorerFinal._prelude  # noqa: F401
    import ExplorerFinal._bootstrap  # noqa: F401

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from shared.persona_schema import (
    PersonaConfig,
    PersonaHooks,
    PersonaValidationError,
    validate_persona_config,
)

try:
    from ReDNACoreDemo.core import persona_registry
    from ReDNACoreDemo.ai.prompt_registry import (
        REPO_ROOT,
        ensure_persona_assets,
        get_persona_bundle,
        resolve_asset_path,
    )
    from ReDNACoreDemo.core.persona_registry import get_last_registered, to_plain
except Exception as exc:  # pragma: no cover - import guard for tests
    st.error(f"Persona registry unavailable: {exc}")
    st.stop()

from ExplorerFinal.ui import persona_router  # late import to avoid circular load
from ExplorerFinal.ui.personas.relationship_coach import (
    DEFAULT_RC_CONFIG,
    PERSONA_ID,
    ensure_registered,
)

DEV_ENABLED = os.getenv("PERSONA_DEV_TABS", "false").strip().lower() in {"1", "true", "yes", "on"}

ensure_registered(auto_create_assets=True)


if not DEV_ENABLED:
    st.warning("Persona dev tabs are disabled. Set PERSONA_DEV_TABS=true to use this surface.")
    st.stop()

st.set_page_config(page_title="Relationship Coach Dev", layout="wide")
st.title("🧪 Relationship Coach Persona Dev")

st.caption(
    "Edit the JSON config, validate it against the schema, and register the persona into the Head Coach registry."
)

config_state_key = "rc_dev_config_text"
if config_state_key not in st.session_state:
    raw = persona_registry.get_raw_payload(PERSONA_ID) or DEFAULT_RC_CONFIG
    st.session_state[config_state_key] = json.dumps(raw, indent=2)

config_editor = st.text_area(
    "Persona configuration (JSON)",
    value=st.session_state[config_state_key],
    height=420,
    key="rc_config_text",
)

cols = st.columns(3)
with cols[0]:
    if st.button("Reload from registry", use_container_width=True):
        raw = persona_registry.get_raw_payload(PERSONA_ID) or DEFAULT_RC_CONFIG
        st.session_state[config_state_key] = json.dumps(raw, indent=2)
        st.experimental_rerun()

validation_feedback = st.empty()
registration_feedback = st.empty()
assets_feedback = st.empty()


def _parse_config(raw_text: str) -> Dict[str, Any]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as err:
        raise PersonaValidationError(f"Invalid JSON: {err}")


def _collect_asset_refs(config: PersonaConfig) -> List[str]:
    prompt_assets = config.prompt_assets
    refs: List[str] = []
    if prompt_assets.system:
        refs.append(prompt_assets.system)
    refs.extend(prompt_assets.dialogue_templates)
    refs.extend(prompt_assets.micro_actions)
    refs.extend(prompt_assets.evaluations)
    return [ref for ref in refs if ref]


def _missing_assets(config: PersonaConfig) -> List[Path]:
    missing: List[Path] = []
    for ref in _collect_asset_refs(config):
        candidate = resolve_asset_path(ref)
        if not candidate.exists():
            missing.append(candidate)
    return missing


def _render_asset_status(missing: List[Path], *, action_key: str) -> None:
    assets_feedback.empty()
    if not missing:
        return
    with assets_feedback.container():
        st.warning("Missing prompt assets referenced in this config.")
        for entry in missing:
            try:
                display = entry.relative_to(REPO_ROOT)
            except Exception:
                display = entry
            st.markdown(f"- `{display}`")
        if st.button(
            "Create assets",
            key=f"create_assets_{action_key}",
            use_container_width=True,
        ):
            ensure_persona_assets(PERSONA_ID)
            st.experimental_rerun()


with cols[1]:
    if st.button("Validate config", use_container_width=True):
        try:
            payload = _parse_config(config_editor)
            config = validate_persona_config(payload)
            validation_feedback.success("Config passes schema validation.")
            st.json(
                {
                    "id": config.id,
                    "version": config.version,
                    "honesty": config.honesty.mode,
                    "keywords": config.keywords,
                    "data_dependencies": {
                        "bundle": config.data_dependencies.bundle,
                        "session": config.data_dependencies.session,
                    },
                },
                expanded=False,
            )
            _render_asset_status(_missing_assets(config), action_key="validate")
        except PersonaValidationError as err:
            validation_feedback.error(str(err))
        except Exception as exc:  # pragma: no cover - defensive
            validation_feedback.error(f"Unexpected error: {exc}")

with cols[2]:
    if st.button("Register to Head Coach", use_container_width=True):
        try:
            payload = _parse_config(config_editor)
            config = validate_persona_config(payload)
            missing = _missing_assets(config)
            if missing:
                registration_feedback.error(
                    "Cannot register until all prompt assets exist."
                )
                _render_asset_status(missing, action_key="register")
            else:
                persona_registry.register_persona(payload, hooks=PersonaHooks())
                registration_feedback.success("Persona registered successfully.")
                assets_feedback.empty()
                toast = getattr(st, "toast", None)
                if callable(toast):
                    toast("Relationship Coach registered · assets loaded")
                switch_page = getattr(st, "switch_page", None)
                if callable(switch_page):
                    switch_page("pages/RC_Coach.py")
        except PersonaValidationError as err:
            registration_feedback.error(str(err))
        except FileNotFoundError as err:
            registration_feedback.error(f"Missing asset: {err}")
        except Exception as exc:  # pragma: no cover
            registration_feedback.error(f"Registration failed: {exc}")

st.markdown("---")

st.subheader("Dry-run prompt preview")

left, right = st.columns([1, 1])
with left:
    orientation = st.selectbox(
        "Orientation",
        ["monogamous", "ethical_non_monogamy", "questioning"],
        index=0,
    )
    relationship_status = st.selectbox(
        "Relationship status",
        ["single", "dating", "engaged", "married"],
        index=1,
    )
    honesty_pref = st.select_slider("Honesty preference", ["gentle", "balanced", "direct"], value="balanced")
    vibe = st.text_input("User vibe keyword", value="curious optimist")

with right:
    top_trait = st.text_input("High-curiosity trait path", value="social.communication_style.clarity")
    top_value = st.text_input("Trait value hint", value="prefers emotional check-ins")
    reflection_prompt = st.text_area(
        "Sample user message",
        value="I'd love help staying honest without overwhelming my partner.",
        height=100,
    )

persona_meta = persona_router.get_persona(PERSONA_ID)
if not persona_meta:
    st.info("Relationship Coach not yet registered. Register the persona to preview prompts.")
else:
    user_context = {
        "top_curiosity": [
            {
                "path": top_trait,
                "value": top_value,
                "curiosity": 78,
                "rr": 42,
            }
        ],
        "recent_changes": {"from_user": ["relationship_status", "communication_style"]},
        "session_preferences": {"honesty": honesty_pref, "vibe": vibe},
    }
    system_prompt = persona_router.compose_system_prompt(
        persona_meta,
        dev_mode=True,
        user_context=user_context,
        persona_id=PERSONA_ID,
        display_name=persona_meta.get("title") or persona_meta.get("name") or PERSONA_ID,
    )
    st.markdown("**System prompt**")
    st.code(system_prompt, language="markdown")

    bundle = get_persona_bundle(PERSONA_ID)
    if bundle:
        st.markdown("**Micro-action templates**")
        if bundle.micro_actions:
            st.code("\n---\n".join(bundle.micro_actions), language="markdown")
        else:
            st.caption("No micro-action prompts attached.")

    rr_contract = persona_meta.get("rr_contract") or {}
    st.markdown("**RR contract**")
    st.json(rr_contract)

    st.markdown("**LLM call payload (simulated)**")
    st.json(
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": reflection_prompt,
                    "meta": {
                        "orientation": orientation,
                        "relationship_status": relationship_status,
                        "honesty": honesty_pref,
                    },
                },
            ],
            "rr_increment_on_success": rr_contract.get("base_increment"),
        }
    )

st.markdown("---")

st.subheader("Telemetry")
last_registered = get_last_registered(PERSONA_ID)
if last_registered is None:
    st.info(
        "Relationship Coach not registered yet. Use 'Register to Head Coach' above to add it before reading telemetry."
    )
else:
    telemetry = {
        "persona_id": last_registered.id,
        "registered_at": datetime.utcnow().isoformat() + "Z",
        "version": getattr(last_registered, "version", "unknown"),
        "lifecycle": to_plain(getattr(last_registered, "lifecycle", {})),
        "data_dependencies": to_plain(getattr(last_registered, "data_dependencies", {})),
        "prompt_assets": to_plain(getattr(last_registered, "prompt_assets", {})),
    }
    st.json(telemetry, expanded=False)
