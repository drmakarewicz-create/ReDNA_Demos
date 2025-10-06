"""Canonical persona schema definitions and validators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence


class PersonaValidationError(ValueError):
    """Raised when persona configuration fails validation."""


@dataclass(slots=True)
class PersonaVibe:
    keywords: List[str] = field(default_factory=list)
    energy: str = "medium"


@dataclass(slots=True)
class PersonaHonesty:
    mode: str
    allowed_ranges: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PersonaTone:
    baseline: str
    escalations: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PersonaHonestyContract:
    default: str
    overrides: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PersonaDataDependencies:
    bundle: List[str] = field(default_factory=list)
    session: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PersonaPromptAssets:
    system: str
    dialogue_templates: List[str] = field(default_factory=list)
    micro_actions: List[str] = field(default_factory=list)
    evaluations: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PersonaUIHooks:
    persona_card: str
    micro_action_stream: Optional[str] = None


@dataclass(slots=True)
class PersonaRRContract:
    base_increment: float = 0.0
    contradiction_escalation: float = 0.0


@dataclass(slots=True)
class PersonaConsentRequirements:
    needs_partner_opt_in: bool = False
    share_scope: str = "self_only"


@dataclass(slots=True)
class PersonaLifecycle:
    beta: bool = False
    requires_head_coach_supervision: bool = True


@dataclass(slots=True)
class PersonaStyleDefaults:
    tone: str = "Neutral"
    formality: int = 50
    warmth: int = 50
    directness: int = 50
    micro_actions: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PersonaStylePreset:
    id: str
    label: str
    description: str = ""
    prompt_overrides: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PersonaHandoffIntent:
    phrase: str
    match_type: str = "contains"
    reason: str = "handoff_intent"


@dataclass(slots=True)
class PersonaRegistration:
    id: str
    version: str
    display_name: str
    greeting_template: str
    handoff_intents: List[PersonaHandoffIntent] = field(default_factory=list)
    style_presets: List[PersonaStylePreset] = field(default_factory=list)
    metrics_keys: List[str] = field(default_factory=list)
    style_defaults: Optional[PersonaStyleDefaults] = None


@dataclass(slots=True)
class PersonaConfig:
    id: str
    version: str
    name: str
    role: str
    vibe: PersonaVibe
    honesty: PersonaHonesty
    tone: PersonaTone
    honesty_contract: PersonaHonestyContract
    data_dependencies: PersonaDataDependencies
    prompt_assets: PersonaPromptAssets
    ui_hooks: PersonaUIHooks
    rr_contract: PersonaRRContract
    consent_requirements: PersonaConsentRequirements
    lifecycle: PersonaLifecycle
    keywords: List[str] = field(default_factory=list)
    accent_color: str = "#1F2933"
    description: str = ""


@dataclass(slots=True)
class PersonaHooks:
    """Optional hook factories executed during registration."""

    descriptor_factory: Optional[Callable[[PersonaConfig], Any]] = None
    card_factory: Optional[Callable[[PersonaConfig], Mapping[str, Any]]] = None
    extra_validators: Sequence[Callable[[PersonaConfig], None]] = ()


@dataclass(slots=True)
class PersonaSummary:
    id: str
    name: str
    role: str
    version: str
    accent_color: str


_ALLOWED_MATCH_TYPES = {"contains", "startswith", "regex"}


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise PersonaValidationError(message)


def _require_keys(payload: Mapping[str, Any], required: Iterable[str], *, context: str) -> None:
    missing = [key for key in required if key not in payload]
    _ensure(not missing, f"Missing keys in {context}: {', '.join(missing)}")


def _as_list(value: Any, *, field_name: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    raise PersonaValidationError(f"Expected a list for {field_name}")


def _as_dict(value: Any, *, field_name: str) -> Dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(k): str(v) for k, v in value.items()}
    raise PersonaValidationError(f"Expected a mapping for {field_name}")


def _as_float(value: Any, *, field_name: str) -> float:
    try:
        return float(value)
    except Exception as exc:  # pragma: no cover - propagate
        raise PersonaValidationError(f"Expected a number for {field_name}") from exc


def _as_int_range(
    value: Any,
    *,
    field_name: str,
    default: int,
    min_value: int = 0,
    max_value: int = 100,
) -> int:
    if value is None:
        return default
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - propagate for clarity
        raise PersonaValidationError(f"Expected an integer for {field_name}") from exc
    _ensure(
        min_value <= integer <= max_value,
        f"{field_name} must be between {min_value} and {max_value}",
    )
    return integer


def _validate_color(color: str) -> str:
    if not isinstance(color, str):
        raise PersonaValidationError("Accent color must be a string")
    text = color.strip()
    _ensure(text.startswith("#") and len(text) in {4, 7}, "Accent color must be in #RGB or #RRGGBB format")
    return text.upper()


def _coerce_prompt_assets(payload: Mapping[str, Any]) -> PersonaPromptAssets:
    _require_keys(payload, ["system"], context="prompt_assets")
    system = str(payload["system"]).strip()
    _ensure(system, "prompt_assets.system cannot be empty")
    dialogue_templates = _as_list(payload.get("dialogue_templates"), field_name="prompt_assets.dialogue_templates")
    micro_actions = _as_list(payload.get("micro_actions"), field_name="prompt_assets.micro_actions")
    evaluations = _as_list(payload.get("evaluations"), field_name="prompt_assets.evaluations")
    return PersonaPromptAssets(
        system=system,
        dialogue_templates=dialogue_templates,
        micro_actions=micro_actions,
        evaluations=evaluations,
    )


def _coerce_data_dependencies(payload: Mapping[str, Any]) -> PersonaDataDependencies:
    bundle = _as_list(payload.get("bundle"), field_name="data_dependencies.bundle")
    session = _as_list(payload.get("session"), field_name="data_dependencies.session")
    optional = _as_list(payload.get("optional"), field_name="data_dependencies.optional")
    return PersonaDataDependencies(bundle=bundle, session=session, optional=optional)


def _coerce_vibe(payload: Mapping[str, Any]) -> PersonaVibe:
    keywords = _as_list(payload.get("keywords"), field_name="vibe.keywords")
    energy = str(payload.get("energy", "medium"))
    _ensure(energy in {"low", "medium", "high"}, "vibe.energy must be one of {'low','medium','high'}")
    return PersonaVibe(keywords=keywords, energy=energy)


def _coerce_honesty(payload: Mapping[str, Any]) -> PersonaHonesty:
    _require_keys(payload, ["mode"], context="honesty")
    mode = str(payload["mode"])
    allowed = _as_list(payload.get("allowed_ranges"), field_name="honesty.allowed_ranges")
    return PersonaHonesty(mode=mode, allowed_ranges=allowed)


def _coerce_tone(payload: Mapping[str, Any]) -> PersonaTone:
    _require_keys(payload, ["baseline"], context="tone")
    baseline = str(payload["baseline"])
    escalations = _as_dict(payload.get("escalations"), field_name="tone.escalations")
    return PersonaTone(baseline=baseline, escalations=escalations)


def _coerce_honesty_contract(payload: Mapping[str, Any]) -> PersonaHonestyContract:
    _require_keys(payload, ["default"], context="honesty_contract")
    default = str(payload["default"])
    overrides = _as_dict(payload.get("overrides"), field_name="honesty_contract.overrides")
    return PersonaHonestyContract(default=default, overrides=overrides)


def _coerce_ui_hooks(payload: Mapping[str, Any]) -> PersonaUIHooks:
    _require_keys(payload, ["persona_card"], context="ui_hooks")
    persona_card = str(payload["persona_card"])
    micro = payload.get("micro_action_stream")
    micro_value = str(micro) if micro is not None else None
    return PersonaUIHooks(persona_card=persona_card, micro_action_stream=micro_value)


def _coerce_rr_contract(payload: Mapping[str, Any]) -> PersonaRRContract:
    base_increment = _as_float(payload.get("base_increment", 0.0), field_name="rr_contract.base_increment")
    contradiction = _as_float(payload.get("contradiction_escalation", 0.0), field_name="rr_contract.contradiction_escalation")
    return PersonaRRContract(base_increment=base_increment, contradiction_escalation=contradiction)


def _coerce_consent(payload: Mapping[str, Any]) -> PersonaConsentRequirements:
    needs_opt_in = bool(payload.get("needs_partner_opt_in", False))
    scope = str(payload.get("share_scope", "self_only"))
    return PersonaConsentRequirements(needs_partner_opt_in=needs_opt_in, share_scope=scope)


def _coerce_lifecycle(payload: Mapping[str, Any]) -> PersonaLifecycle:
    beta = bool(payload.get("beta", False))
    supervised = bool(payload.get("requires_head_coach_supervision", True))
    return PersonaLifecycle(beta=beta, requires_head_coach_supervision=supervised)


def _coerce_style_presets(value: Any) -> List[PersonaStylePreset]:
    presets: List[PersonaStylePreset] = []
    if value is None:
        return presets
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise PersonaValidationError("style_presets must be a list")
    for item in value:
        if isinstance(item, str):
            preset_id = item.strip().lower().replace(" ", "_")
            _ensure(preset_id, "style preset string entries cannot be empty")
            presets.append(
                PersonaStylePreset(
                    id=preset_id,
                    label=item.strip(),
                )
            )
            continue
        if not isinstance(item, Mapping):
            raise PersonaValidationError("style preset entries must be mappings or strings")
        preset_id = str(item.get("id") or "").strip()
        _ensure(preset_id, "style_presets entries require an 'id'")
        label = str(item.get("label") or preset_id.replace("_", " ").title()).strip()
        description = str(item.get("description") or "").strip()
        overrides_raw = item.get("prompt_overrides")
        if overrides_raw is None:
            overrides = {}
        elif isinstance(overrides_raw, Mapping):
            overrides = {str(k): str(v) for k, v in overrides_raw.items()}
        else:
            raise PersonaValidationError("style preset prompt_overrides must be a mapping")
        presets.append(
            PersonaStylePreset(
                id=preset_id,
                label=label,
                description=description,
                prompt_overrides=overrides,
            )
        )
    return presets


def _coerce_style_defaults(value: Any) -> Optional[PersonaStyleDefaults]:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise PersonaValidationError("style_defaults must be a mapping")

    tone_raw = value.get("tone")
    tone = str(tone_raw).strip() if tone_raw is not None else "Neutral"
    if not tone:
        tone = "Neutral"

    formality = _as_int_range(
        value.get("formality"),
        field_name="style_defaults.formality",
        default=50,
    )
    warmth = _as_int_range(
        value.get("warmth"),
        field_name="style_defaults.warmth",
        default=50,
    )
    directness = _as_int_range(
        value.get("directness"),
        field_name="style_defaults.directness",
        default=50,
    )

    micro_source = value.get("micro_actions")
    if micro_source is None:
        micro_source = value.get("micro")

    micro_actions: List[str] = []
    if micro_source is None:
        micro_actions = []
    elif isinstance(micro_source, str):
        tokens = [token.strip() for token in micro_source.split(",")]
        micro_actions = [token for token in tokens if token]
    elif isinstance(micro_source, Iterable):
        micro_actions = [str(item).strip() for item in micro_source if str(item).strip()]
    else:
        raise PersonaValidationError("style_defaults.micro/micro_actions must be a list or string")

    return PersonaStyleDefaults(
        tone=tone,
        formality=formality,
        warmth=warmth,
        directness=directness,
        micro_actions=micro_actions,
    )


def _coerce_handoff_intents(value: Any) -> List[PersonaHandoffIntent]:
    intents: List[PersonaHandoffIntent] = []
    if value is None:
        return intents
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise PersonaValidationError("handoff_intents must be a list")
    for item in value:
        if isinstance(item, str):
            phrase = item.strip()
            _ensure(phrase, "handoff intent strings cannot be empty")
            intents.append(PersonaHandoffIntent(phrase=phrase))
            continue
        if not isinstance(item, Mapping):
            raise PersonaValidationError("handoff intent entries must be mappings or strings")
        phrase = str(item.get("phrase") or "").strip()
        _ensure(phrase, "handoff intent entries require a 'phrase'")
        match_type = str(item.get("match_type") or "contains").strip().lower()
        _ensure(match_type in _ALLOWED_MATCH_TYPES, "handoff intent match_type must be one of contains|startswith|regex")
        reason = str(item.get("reason") or "handoff_intent").strip() or "handoff_intent"
        intents.append(
            PersonaHandoffIntent(
                phrase=phrase,
                match_type=match_type,
                reason=reason,
            )
        )
    return intents


def validate_persona_registration(payload: Mapping[str, Any]) -> PersonaRegistration:
    _require_keys(payload, ["id", "version", "display_name", "greeting_template"], context="persona_registration")
    persona_id = str(payload["id"]).strip()
    _ensure(persona_id, "persona registration id cannot be empty")
    version = str(payload["version"]).strip()
    _ensure(version, "persona registration version cannot be empty")
    display_name = str(payload["display_name"]).strip()
    _ensure(display_name, "persona registration display_name cannot be empty")
    greeting_template = str(payload["greeting_template"]).strip()
    _ensure(greeting_template, "persona registration greeting_template cannot be empty")
    handoff_intents = _coerce_handoff_intents(payload.get("handoff_intents"))
    style_presets = _coerce_style_presets(payload.get("style_presets"))
    metrics_keys = _as_list(payload.get("metrics_keys"), field_name="persona_registration.metrics_keys")
    style_defaults = _coerce_style_defaults(payload.get("style_defaults"))
    return PersonaRegistration(
        id=persona_id,
        version=version,
        display_name=display_name,
        greeting_template=greeting_template,
        handoff_intents=handoff_intents,
        style_presets=style_presets,
        metrics_keys=metrics_keys,
        style_defaults=style_defaults,
    )


def persona_registration_summary(registration: PersonaRegistration) -> Dict[str, Any]:
    summary = {
        "id": registration.id,
        "version": registration.version,
        "display_name": registration.display_name,
        "greeting_template": registration.greeting_template,
        "handoff_intents": [
            {
                "phrase": intent.phrase,
                "match_type": intent.match_type,
                "reason": intent.reason,
            }
            for intent in registration.handoff_intents
        ],
        "style_presets": [
            {
                "id": preset.id,
                "label": preset.label,
                "description": preset.description,
                "prompt_overrides": dict(preset.prompt_overrides),
            }
            for preset in registration.style_presets
        ],
        "metrics_keys": list(registration.metrics_keys),
    }
    if registration.style_defaults is not None:
        summary["style_defaults"] = {
            "tone": registration.style_defaults.tone,
            "formality": registration.style_defaults.formality,
            "warmth": registration.style_defaults.warmth,
            "directness": registration.style_defaults.directness,
            "micro_actions": list(registration.style_defaults.micro_actions),
        }
    return summary


def validate_persona_config(payload: Mapping[str, Any]) -> PersonaConfig:
    """Validate incoming mapping and return a PersonaConfig dataclass."""

    _require_keys(payload, ["id", "version", "name", "role", "vibe", "honesty", "tone",
                            "honesty_contract", "data_dependencies", "prompt_assets",
                            "ui_hooks", "rr_contract", "consent_requirements", "lifecycle"],
                   context="persona_config")

    persona_id = str(payload["id"]).strip()
    _ensure(persona_id, "Persona id cannot be empty")
    version = str(payload["version"]).strip()
    _ensure(version, "Persona version cannot be empty")
    name = str(payload["name"]).strip()
    role = str(payload["role"]).strip()
    _ensure(name and role, "Persona name and role cannot be empty")

    accent_color = _validate_color(str(payload.get("accent_color", "#1F2933")))
    description = str(payload.get("description", "")).strip()
    keywords = _as_list(payload.get("keywords"), field_name="persona.keywords")

    vibe = _coerce_vibe(payload["vibe"])
    honesty = _coerce_honesty(payload["honesty"])
    tone = _coerce_tone(payload["tone"])
    honesty_contract = _coerce_honesty_contract(payload["honesty_contract"])
    data_dependencies = _coerce_data_dependencies(payload["data_dependencies"])
    prompt_assets = _coerce_prompt_assets(payload["prompt_assets"])
    ui_hooks = _coerce_ui_hooks(payload["ui_hooks"])
    rr_contract = _coerce_rr_contract(payload["rr_contract"])
    consent_requirements = _coerce_consent(payload["consent_requirements"])
    lifecycle = _coerce_lifecycle(payload["lifecycle"])

    config = PersonaConfig(
        id=persona_id,
        version=version,
        name=name,
        role=role,
        vibe=vibe,
        honesty=honesty,
        tone=tone,
        honesty_contract=honesty_contract,
        data_dependencies=data_dependencies,
        prompt_assets=prompt_assets,
        ui_hooks=ui_hooks,
        rr_contract=rr_contract,
        consent_requirements=consent_requirements,
        lifecycle=lifecycle,
        keywords=keywords,
        accent_color=accent_color,
        description=description,
    )
    return config


def persona_summary(config: PersonaConfig) -> PersonaSummary:
    return PersonaSummary(
        id=config.id,
        name=config.name,
        role=config.role,
        version=config.version,
        accent_color=config.accent_color,
    )


__all__ = [
    "PersonaConfig",
    "PersonaHooks",
    "PersonaSummary",
    "PersonaValidationError",
    "PersonaVibe",
    "PersonaHonesty",
    "PersonaTone",
    "PersonaHonestyContract",
    "PersonaDataDependencies",
    "PersonaPromptAssets",
    "PersonaUIHooks",
    "PersonaRRContract",
    "PersonaConsentRequirements",
    "PersonaLifecycle",
    "PersonaStyleDefaults",
    "PersonaStylePreset",
    "PersonaHandoffIntent",
    "PersonaRegistration",
    "validate_persona_config",
    "persona_summary",
    "validate_persona_registration",
    "persona_registration_summary",
]
