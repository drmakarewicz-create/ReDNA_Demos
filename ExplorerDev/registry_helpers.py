"""Helpers for reading and normalising persona registry contracts."""

from __future__ import annotations

import importlib
import importlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

from jsonschema import Draft7Validator, ValidationError

try:
    from .bootstrap import ensure_repo_root
except ImportError:  # pragma: no cover - running as a script
    import sys
    from pathlib import Path as _Path

    CURRENT_DIR = _Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from bootstrap import ensure_repo_root  # type: ignore

try:
    from .write_utils import write_guard
except ImportError:  # pragma: no cover - running as a script
    import sys
    from pathlib import Path as _Path

    CURRENT_DIR = _Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from write_utils import write_guard  # type: ignore

try:  # Optional at runtime but present in dev environment
    from ReDNACoreDemo.core import persona_registry  # type: ignore
except Exception:  # pragma: no cover - dev fallback
    persona_registry = None  # type: ignore


class WriteContext(Protocol):
    """Subset of DevWriteContext used by save_persona_registry."""

    write_protect: bool


REPO_ROOT = ensure_repo_root()
REGISTRY_PATH = REPO_ROOT / "data/dev_persona_registry.json"
SCHEMA_PATH = REPO_ROOT / "persona_config/schema/persona_contract.schema.json"

_SCHEMA_DATA: Optional[Dict[str, Any]] = None
_REGISTRY_VALIDATOR: Optional[Draft7Validator] = None
_PERSONA_VALIDATOR: Optional[Draft7Validator] = None


@dataclass(slots=True)
class RegistryLoadResult:
    items: List[Dict[str, Any]]
    errors: List[Dict[str, str]]
    imported: int
    failures: int
    total: int
    version: Optional[str] = None
    generated_at: Optional[str] = None
    validation_mode: str = "strict"


def _load_schema_data() -> Dict[str, Any]:
    global _SCHEMA_DATA
    if _SCHEMA_DATA is None:
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(
                f"Persona contract schema missing at {SCHEMA_PATH.relative_to(REPO_ROOT)}"
            )
        _SCHEMA_DATA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_DATA


def _get_registry_validator() -> Draft7Validator:
    global _REGISTRY_VALIDATOR
    if _REGISTRY_VALIDATOR is None:
        _REGISTRY_VALIDATOR = Draft7Validator(_load_schema_data())
    return _REGISTRY_VALIDATOR


def _get_persona_validator() -> Draft7Validator:
    global _PERSONA_VALIDATOR
    if _PERSONA_VALIDATOR is None:
        schema = _load_schema_data()
        persona_schema = schema.get("properties", {}).get("personas", {}).get("items", {})
        _PERSONA_VALIDATOR = Draft7Validator(persona_schema or {})
    return _PERSONA_VALIDATOR


def _title_from_identifier(identifier: str) -> str:
    words = identifier.replace("_", " ").replace("-", " ").split()
    return " ".join(word.capitalize() for word in words) or identifier.capitalize()


def _ensure_list(value: Any) -> Iterable[Any]:
    if isinstance(value, (list, tuple)):
        return value
    return []


def _normalize_style_sequence(values: Any) -> List[Dict[str, Any]]:
    normalised: List[Dict[str, Any]] = []
    for item in _ensure_list(values):
        if isinstance(item, str):
            ident = item.strip()
            if not ident:
                continue
            normalised.append({"id": ident, "label": _title_from_identifier(ident)})
        elif isinstance(item, dict):
            normalised_item = dict(item)
            ident_raw = normalised_item.get("id")
            if isinstance(ident_raw, str):
                ident = ident_raw.strip()
                normalised_item["id"] = ident
            else:
                ident = ""
            if not normalised_item.get("label") and ident:
                normalised_item["label"] = _title_from_identifier(ident)
            normalised.append(normalised_item)
    return normalised


def _normalize_style_defaults(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    defaults = {
        "tone": "Neutral",
        "formality": 50,
        "warmth": 50,
        "directness": 50,
        "micro_actions": [],
    }

    tone_raw = value.get("tone")
    if tone_raw is not None:
        tone_text = str(tone_raw).strip()
        if tone_text:
            defaults["tone"] = tone_text

    def _assign_int(key: str) -> None:
        raw = value.get(key)
        if raw is None:
            return
        try:
            integer = int(raw)
        except (TypeError, ValueError):
            return
        defaults[key] = max(0, min(100, integer))

    for key in ("formality", "warmth", "directness"):
        _assign_int(key)

    micro_source = value.get("micro_actions")
    if micro_source is None:
        micro_source = value.get("micro")

    if isinstance(micro_source, str):
        tokens = [token.strip() for token in micro_source.split(",") if token.strip()]
        defaults["micro_actions"] = tokens
    elif isinstance(micro_source, (list, tuple, set)):
        tokens = [str(item).strip() for item in micro_source if str(item).strip()]
        defaults["micro_actions"] = tokens

    return defaults


def _normalize_tags(values: Any) -> List[str]:
    return [str(value) for value in _ensure_list(values)]


class ModulePersona:
    __slots__ = ("module_name", "persona", "alias", "error")

    def __init__(
        self,
        module_name: str,
        persona: Optional[Dict[str, Any]] = None,
        alias: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        self.module_name = module_name
        self.persona = persona
        self.alias = alias
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "persona": self.persona,
            "alias": self.alias,
            "error": self.error,
        }


def discover_persona_modules(persona_packages: Iterable[str]) -> List[ModulePersona]:
    modules: List[ModulePersona] = []
    for module_path in persona_packages:
        module_name = module_path.rsplit(".", 1)[-1]
        contract: Optional[Dict[str, Any]] = None
        alias: Optional[str] = None
        error: Optional[str] = None

        try:
            module = importlib.import_module(module_path)
        except Exception as exc:  # pragma: no cover - diagnostics only
            modules.append(ModulePersona(module_name, error=f"Import failed: {exc}"))
            continue

        registration = None
        if hasattr(module, "get_persona_registration") and callable(module.get_persona_registration):
            try:
                registration = module.get_persona_registration()
            except Exception as exc:  # pragma: no cover
                error = f"get_persona_registration failed: {exc}"
        elif hasattr(module, "PERSONA_REGISTRATION"):
            registration = getattr(module, "PERSONA_REGISTRATION")

        if isinstance(registration, dict) and registration.get("id"):
            persona_id = str(registration["id"]).strip()
            if persona_id:
                contract = dict(registration)
                if persona_id != module_name:
                    alias = f"{module_name} → {persona_id}"
        else:
            error = error or "no persona contract found"

        modules.append(ModulePersona(module_name, persona=contract, alias=alias, error=error))
    return modules


def ensure_relationship_coach_contract(module_personas: List[ModulePersona]) -> None:
    fallback_assets = {
        "system": "You are the Relationship Coach (RC) focused on helping users navigate relationships respectfully.",
        "opening": "How can I help with relationships today?",
    }

    target = None
    for module_persona in module_personas:
        if module_persona.module_name == "relationship_coach":
            target = module_persona
            break

    if target is None:
        module_personas.append(
            ModulePersona(
                "relationship_coach",
                persona={
                    "id": "rc_coach",
                    "display_name": "Relationship Coach",
                    "role": "coach",
                    "prompt_assets": fallback_assets.copy(),
                },
                alias="relationship_coach → rc_coach (fallback)",
            )
        )
        return

    if target.persona is None:
        target.persona = {
            "id": "rc_coach",
            "display_name": "Relationship Coach",
            "role": "coach",
            "prompt_assets": fallback_assets.copy(),
        }
        target.alias = target.alias or "relationship_coach → rc_coach (fallback)"
        target.error = None
        return

    assets = target.persona.setdefault("prompt_assets", {}) if isinstance(target.persona, dict) else {}
    system_text = str(assets.get("system") or "").strip()
    opening_text = str(assets.get("opening") or "").strip()
    if not system_text:
        assets["system"] = fallback_assets["system"]
    if not opening_text:
        assets["opening"] = fallback_assets["opening"]


def _extract_summary_and_registration(raw_entry: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    summary = raw_entry.get("summary") if isinstance(raw_entry.get("summary"), dict) else {}
    registration = raw_entry.get("registration") if isinstance(raw_entry.get("registration"), dict) else {}
    return summary, registration


def _normalize_prompt_assets(raw_entry: Dict[str, Any], registration: Dict[str, Any]) -> Dict[str, Any]:
    prompt_assets = {}
    for source in (raw_entry.get("prompt_assets"), registration.get("prompt_assets")):
        if isinstance(source, dict):
            prompt_assets.update(source)
    system_val = prompt_assets.get("system")
    opening_val = prompt_assets.get("opening")
    system_text = "" if system_val is None else str(system_val).strip()
    opening_text = "" if opening_val is None else str(opening_val).strip()
    prompt_assets["system"] = system_text
    prompt_assets["opening"] = opening_text
    return prompt_assets


def _persona_override_paths(persona_id: str) -> Dict[str, Path]:
    base = REPO_ROOT / "persona_config/dev_overrides" / persona_id
    return {
        "system": base / "system.md",
        "opening": base / "opening.md",
    }


def _looks_like_path(value: str) -> bool:
    lowered = value.lower()
    return (
        "/" in value
        or "\\" in value
        or lowered.endswith(".md")
        or lowered.endswith(".txt")
        or lowered.endswith(".prompt")
    )


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (REPO_ROOT / value).resolve()
    return path


def _pretty_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _resolve_prompt_sources(
    persona_id: str,
    prompt_assets: Dict[str, Any],
    registration: Dict[str, Any],
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    overrides = _persona_override_paths(persona_id)
    bundle = {"system": "", "opening": ""}
    sources: Dict[str, Any] = {}

    def add_check(container: Dict[str, Any], source: str, detail: Optional[str], hit: bool) -> None:
        container.setdefault("checked", []).append(
            {"source": source, "detail": detail, "hit": bool(hit)}
        )

    for role in ("system", "opening"):
        info = {
            "used": "missing",
            "dev_path": _pretty_path(overrides[role]),
            "live_path": None,
            "inline_bytes": False,
            "checked": [],
        }
        text = ""

        override_path = overrides[role]
        add_check(info, "dev_override", info["dev_path"], override_path.exists())
        if override_path.exists():
            text = override_path.read_text(encoding="utf-8")
            info["used"] = "dev_override"
            sources[role] = info
            bundle[role] = text
            continue

        candidate = prompt_assets.get(role)
        candidate_str = str(candidate).strip() if isinstance(candidate, str) else ""
        if candidate_str:
            if _looks_like_path(candidate_str):
                candidate_path = _resolve_path(candidate_str)
                info["live_path"] = _pretty_path(candidate_path)
                exists = candidate_path.exists()
                add_check(info, "live_path", info["live_path"], exists)
                if exists:
                    text = candidate_path.read_text(encoding="utf-8")
                    info["used"] = "live"
                    sources[role] = info
                    bundle[role] = text
                    continue
                if "\n" in candidate_str:
                    add_check(info, "inline_literal", "from live path string", True)
                    text = candidate_str
                    info["used"] = "inline"
                    info["inline_bytes"] = bool(text.encode("utf-8"))
                    sources[role] = info
                    bundle[role] = text
                    continue
            else:
                add_check(info, "inline_prompt_assets", candidate_str[:64], True)
                text = candidate_str
                info["used"] = "inline"
                info["inline_bytes"] = bool(text.encode("utf-8"))
                sources[role] = info
                bundle[role] = text
                continue

        fallback_keys = (
            ["system_prompt", "system_text"] if role == "system" else ["opening_prompt", "opening_text"]
        )
        fallback_text = ""
        for key in fallback_keys:
            value = registration.get(key)
            if isinstance(value, str) and value.strip():
                fallback_text = value
                add_check(info, f"registration:{key}", None, True)
                break
        if fallback_text:
            text = fallback_text
            info["used"] = "inline"
            info["inline_bytes"] = bool(text.encode("utf-8"))
        else:
            add_check(info, "registration", None, False)

        sources[role] = info
        bundle[role] = text

    return bundle, sources


def normalize_persona(raw_entry: Dict[str, Any]) -> Dict[str, Any]:
    summary, registration = _extract_summary_and_registration(raw_entry)
    persona_id = str(
        raw_entry.get("id")
        or summary.get("id")
        or registration.get("id")
        or ""
    ).strip()

    prompt_assets = _normalize_prompt_assets(raw_entry, registration)
    bundle, resolved_sources = _resolve_prompt_sources(persona_id, prompt_assets, registration)

    display_name = (
        registration.get("display_name")
        or raw_entry.get("label")
        or summary.get("name")
        or persona_id
    )

    role = raw_entry.get("role") or summary.get("role") or ""

    status = str(raw_entry.get("status") or "draft")
    provenance = raw_entry.get("provenance") if isinstance(raw_entry.get("provenance"), dict) else {}

    normalized: Dict[str, Any] = dict(raw_entry)
    normalized.update(
        {
            "id": persona_id,
            "label": display_name,
            "role": role,
            "prompt_assets": prompt_assets,
            "style_presets": _normalize_style_sequence(
                raw_entry.get("style_presets") or registration.get("style_presets")
            ),
            "tone_presets": _normalize_style_sequence(
                raw_entry.get("tone_presets") or registration.get("tone_presets")
            ),
            "tags": _normalize_tags(
                raw_entry.get("tags")
                or summary.get("keywords")
                or registration.get("tags")
            ),
            "status": status,
            "updated_at": (
                str(raw_entry.get("updated_at")) if raw_entry.get("updated_at") is not None else None
            ),
            "provenance": provenance,
            "registration": registration,
            "summary": summary,
            "prompt_bundle": bundle,
            "resolved_sources": resolved_sources,
            "style_defaults": _normalize_style_defaults(
                raw_entry.get("style_defaults") or registration.get("style_defaults")
            ),
        }
    )

    version = (
        raw_entry.get("version")
        or registration.get("version")
        or summary.get("version")
    )
    if version is not None:
        normalized["version"] = str(version)

    greeting = registration.get("greeting_template") or raw_entry.get("greeting_template")
    if greeting:
        normalized["greeting_template"] = str(greeting)

    handoff = registration.get("handoff_intents") or raw_entry.get("handoff_intents")
    if handoff:
        normalized["handoff_intents"] = list(handoff)

    metrics = registration.get("metrics_keys") or raw_entry.get("metrics_keys")
    if metrics:
        normalized["metrics_keys"] = list(metrics)

    return normalized


def _build_registry_from_live() -> Dict[str, Any]:
    if persona_registry is None:
        return {"version": "unavailable", "generated_at": None, "personas": []}

    personas: List[Dict[str, Any]] = []
    try:
        summaries = list(persona_registry.list_personas())  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive
        summaries = []

    for summary in summaries:
        try:
            raw_payload = persona_registry.get_raw_payload(summary.id) or {}  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            raw_payload = {}

        try:
            registration = persona_registry.get_registration_payload(summary.id) or {}  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            registration = {}

        personas.append({"summary": getattr(summary, "__dict__", {}), "registration": registration, **raw_payload})

    return {
        "version": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "personas": personas,
    }


def _read_registry_payload() -> Any:
    if REGISTRY_PATH.exists():
        try:
            text = REGISTRY_PATH.read_text(encoding="utf-8")
            return json.loads(text)
        except json.JSONDecodeError:
            return _build_registry_from_live()
    return _build_registry_from_live()


def _extract_persona_id(raw_entry: Any) -> str:
    if isinstance(raw_entry, dict):
        summary = raw_entry.get("summary") if isinstance(raw_entry.get("summary"), dict) else {}
        registration = raw_entry.get("registration") if isinstance(raw_entry.get("registration"), dict) else {}
        return str(
            raw_entry.get("id")
            or summary.get("id")
            or registration.get("id")
            or ""
        ).strip()
    return ""


def load_persona_registry(mode: str = "strict") -> RegistryLoadResult:
    payload = _read_registry_payload()

    if isinstance(payload, dict) and isinstance(payload.get("personas"), list):
        raw_personas = payload.get("personas", [])
        version = payload.get("version")
        generated_at = payload.get("generated_at")
    elif isinstance(payload, list):
        raw_personas = payload
        version = None
        generated_at = None
    else:
        raw_personas = []
        version = None
        generated_at = None

    persona_validator = _get_persona_validator()
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    include_invalid = str(mode).lower() == "warn"

    for raw in raw_personas:
        if not isinstance(raw, dict):
            continue
        persona_id = _extract_persona_id(raw)
        try:
            normalized = normalize_persona(raw)
        except Exception as exc:  # pragma: no cover - defensive guard
            errors.append(
                {
                    "persona_id": persona_id or "<unknown>",
                    "path": "<normalize>",
                    "message": str(exc),
                }
            )
            if include_invalid:
                placeholder = dict(raw)
                placeholder["id"] = persona_id or placeholder.get("id")
                placeholder["_validation_warning"] = {
                    "path": "<normalize>",
                    "message": str(exc),
                }
                items.append(placeholder)
            continue

        try:
            persona_validator.validate(normalized)
        except ValidationError as exc:
            path = "/".join(str(part) for part in exc.absolute_path) or "<root>"
            error_entry = {
                "persona_id": persona_id or "<unknown>",
                "path": path,
                "message": exc.message,
            }
            errors.append(error_entry)
            if include_invalid:
                flagged = dict(normalized)
                flagged["_validation_warning"] = error_entry
                items.append(flagged)
        else:
            items.append(normalized)

    return RegistryLoadResult(
        items=items,
        errors=errors,
        imported=len(items),
        failures=len(errors),
        total=len([entry for entry in raw_personas if isinstance(entry, dict)]),
        version=str(version) if version is not None else None,
        generated_at=str(generated_at) if generated_at is not None else None,
        validation_mode="warn" if include_invalid else "strict",
    )


def get_persona_contract(persona_id: str) -> Dict[str, Any]:
    result = load_persona_registry()
    for item in result.items:
        if item.get("id") == persona_id:
            return item
    raise KeyError(f"Persona {persona_id} not found in registry")


def save_persona_registry(registry: RegistryLoadResult | Dict[str, Any], *, write_context: WriteContext) -> Path:
    write_guard(write_context, action="update persona registry")

    if isinstance(registry, RegistryLoadResult):
        payload = {
            "version": registry.version,
            "generated_at": registry.generated_at,
            "personas": registry.items,
        }
    else:
        payload = registry

    _get_registry_validator().validate(payload)

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return REGISTRY_PATH


__all__ = [
    "RegistryLoadResult",
    "load_persona_registry",
    "save_persona_registry",
    "normalize_persona",
    "get_persona_contract",
]
