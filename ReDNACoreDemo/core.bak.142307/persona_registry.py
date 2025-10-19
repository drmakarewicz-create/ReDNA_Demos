"""Runtime registry for persona configurations and assets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

from shared.persona_schema import (
    PersonaConfig,
    PersonaHooks,
    PersonaRegistration,
    PersonaSummary,
    persona_registration_summary,
    persona_summary,
    validate_persona_config,
    validate_persona_registration,
)
from ReDNACoreDemo.ai.prompt_registry import (
    PromptBundle,
    read_asset,
    register_persona_bundle,
    resolve_asset_path,
)

@dataclass(slots=True)
class PersonaRecord:
    config: PersonaConfig
    summary: PersonaSummary
    registration: PersonaRegistration
    registration_raw: Dict[str, object]
    raw: Dict[str, object]


_REGISTRY: Dict[str, PersonaRecord] = {}
_LAST_REGISTERED_ID: Optional[str] = None


def to_plain(obj: object) -> object:
    """Convert dataclasses/pydantic/other objects to basic Python types."""

    try:
        if is_dataclass(obj):
            return asdict(obj)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - dataclass guard only
        pass

    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - best effort
            pass

    if hasattr(obj, "dict"):
        try:
            return obj.dict()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - best effort
            pass

    try:
        return json.loads(
            json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o)))
        )
    except Exception:  # pragma: no cover - final fallback
        if hasattr(obj, "__dict__"):
            return dict(getattr(obj, "__dict__"))
        return str(obj)


def _resolve_asset(path_value: str) -> str:
    try:
        return read_asset(path_value)
    except FileNotFoundError as exc:
        resolved = resolve_asset_path(path_value)
        raise FileNotFoundError(
            f"Persona asset not found: {path_value} (resolved={resolved}, cwd={Path.cwd()})"
        ) from exc


def _default_descriptor_factory(config: PersonaConfig):  # pragma: no cover - thin passthrough
    try:
        from ExplorerFinal.ui.persona_bus import PersonaDescriptor, register_persona  # type: ignore
    except Exception:
        return

    descriptor = PersonaDescriptor(
        id=config.id,
        title=config.name,
        icon="",
        color=config.accent_color,
        description=config.description,
    )
    register_persona(descriptor, overwrite=True)


def _default_card_factory(config: PersonaConfig) -> Mapping[str, object]:
    return {
        "id": config.id,
        "title": config.name,
        "accent": config.accent_color,
        "tagline": config.role,
        "keywords": config.keywords,
        "honesty_mode": config.honesty.mode,
        "allowed_honesty": config.honesty.allowed_ranges,
        "vibe_keywords": config.vibe.keywords,
        "description": config.description,
        "beta": config.lifecycle.beta,
    }


def _register_card(card_payload: Mapping[str, object]) -> None:  # pragma: no cover - Streamlit dependent
    try:
        from ExplorerFinal.ui import persona_cards_registry  # type: ignore
    except Exception:
        return

    persona_cards_registry.register_card(card_payload)


def _run_descriptor_factory(config: PersonaConfig, hook: Optional[object]) -> None:
    if hook is None:
        _default_descriptor_factory(config)
        return
    hook(config)


def _run_card_factory(config: PersonaConfig, hook: Optional[object]) -> None:
    payload = None
    if hook is None:
        payload = _default_card_factory(config)
    else:
        payload = hook(config)
    if payload:
        _register_card(payload)


def _derive_registration_payload(
    *,
    persona_id: str,
    config: PersonaConfig,
    raw_payload: Mapping[str, object],
) -> Dict[str, object]:
    registration_candidate: Optional[Mapping[str, object]] = None
    for key in ("registration", "registration_contract"):
        candidate = raw_payload.get(key)
        if isinstance(candidate, Mapping):
            registration_candidate = candidate
            break
    if registration_candidate is None:
        # Allow top-level overrides to avoid forcing all callers to nest data.
        registration_candidate = {
            "display_name": raw_payload.get("display_name"),
            "greeting_template": raw_payload.get("greeting_template"),
            "handoff_intents": raw_payload.get("handoff_intents"),
            "style_presets": raw_payload.get("style_presets"),
            "metrics_keys": raw_payload.get("metrics_keys"),
        }
    display_name = registration_candidate.get("display_name") or raw_payload.get("name") or config.name
    greeting_template = registration_candidate.get("greeting_template") or (
        f"Hi there — I’m {config.name}."
    )
    payload = {
        "id": persona_id,
        "version": registration_candidate.get("version") or config.version,
        "display_name": display_name,
        "greeting_template": greeting_template,
        "handoff_intents": registration_candidate.get("handoff_intents")
        or raw_payload.get("handoff_intents"),
        "style_presets": registration_candidate.get("style_presets")
        or raw_payload.get("style_presets"),
        "metrics_keys": registration_candidate.get("metrics_keys")
        or raw_payload.get("metrics_keys"),
    }
    return payload


def register_persona(config: PersonaConfig | Mapping[str, object], hooks: Optional[PersonaHooks] = None) -> None:
    """Register a persona, validating config and wiring prompt/UI assets."""

    hooks = hooks or PersonaHooks()
    if isinstance(config, Mapping):
        config_obj = validate_persona_config(config)
        raw_payload = dict(config)  # shallow copy for dev tools
    elif isinstance(config, PersonaConfig):
        config_obj = config
        raw_payload = asdict(config_obj)
    else:  # pragma: no cover - defensive
        raise TypeError("config must be a PersonaConfig or mapping")

    for validator in hooks.extra_validators:
        validator(config_obj)

    persona_id = config_obj.id

    registration_payload = _derive_registration_payload(
        persona_id=persona_id,
        config=config_obj,
        raw_payload=raw_payload,
    )
    registration_obj = validate_persona_registration(registration_payload)

    system_prompt = _resolve_asset(config_obj.prompt_assets.system)
    dialogue_prompts = [_resolve_asset(path) for path in config_obj.prompt_assets.dialogue_templates]
    micro_actions = [_resolve_asset(path) for path in config_obj.prompt_assets.micro_actions]
    evaluations = [_resolve_asset(path) for path in config_obj.prompt_assets.evaluations]

    bundle = PromptBundle(
        system=system_prompt,
        dialogue_templates=dialogue_prompts,
        micro_actions=micro_actions,
        evaluations=evaluations,
    )
    register_persona_bundle(persona_id, bundle)

    _run_card_factory(config_obj, hooks.card_factory)
    _run_descriptor_factory(config_obj, hooks.descriptor_factory)

    record = PersonaRecord(
        config=config_obj,
        summary=persona_summary(config_obj),
        registration=registration_obj,
        registration_raw=persona_registration_summary(registration_obj),
        raw=raw_payload,
    )
    _REGISTRY[persona_id] = record
    global _LAST_REGISTERED_ID
    _LAST_REGISTERED_ID = persona_id
    try:
        from ExplorerFinal.ui import persona_router  # type: ignore
        persona_router.load_personas.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass



def get_persona(persona_id: str) -> Optional[PersonaConfig]:
    record = _REGISTRY.get(persona_id)
    return record.config if record else None


def list_personas() -> Iterable[PersonaSummary]:
    return [record.summary for record in _REGISTRY.values()]


def get_raw_payload(persona_id: str) -> Optional[Dict[str, object]]:
    record = _REGISTRY.get(persona_id)
    return dict(record.raw) if record else None


def get_registration(persona_id: str) -> Optional[PersonaRegistration]:
    record = _REGISTRY.get(persona_id)
    return record.registration if record else None


def get_registration_payload(persona_id: str) -> Optional[Dict[str, object]]:
    record = _REGISTRY.get(persona_id)
    return dict(record.registration_raw) if record else None


def get_last_registered(persona_id: Optional[str] = None) -> Optional[PersonaConfig]:
    """Return the most recently registered persona (optionally for a specific id)."""

    if persona_id:
        record = _REGISTRY.get(persona_id)
        return record.config if record else None

    if _LAST_REGISTERED_ID and _LAST_REGISTERED_ID in _REGISTRY:
        return _REGISTRY[_LAST_REGISTERED_ID].config

    if _REGISTRY:
        # Python dict preserves insertion order; last item is most recent.
        last_key = next(reversed(_REGISTRY))
        return _REGISTRY[last_key].config

    return None


def clear_registry() -> None:
    _REGISTRY.clear()
    global _LAST_REGISTERED_ID
    _LAST_REGISTERED_ID = None


def dump_registry_snapshot(target: str | Path) -> None:
    """Persist the current persona registry registrations to a JSON file."""

    snapshot_path = Path(target)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for record in _REGISTRY.values():
        payload.append(
            {
                "summary": {
                    "id": record.summary.id,
                    "name": record.summary.name,
                    "role": record.summary.role,
                    "version": record.summary.version,
                    "accent_color": record.summary.accent_color,
                },
                "registration": record.registration_raw,
            }
        )

    snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


__all__ = [
    "PersonaConfig",
    "PersonaHooks",
    "PersonaRegistration",
    "register_persona",
    "get_persona",
    "list_personas",
    "get_raw_payload",
    "get_registration",
    "get_registration_payload",
    "get_last_registered",
    "to_plain",
    "clear_registry",
    "dump_registry_snapshot",
]
