"""Import helpers for mapping persona contracts into Coach ReDNA."""

from __future__ import annotations

import difflib
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ExplorerDev import registry_helpers, schema_utils
from ExplorerDev.credna import credna_store
from ExplorerDev.credna.credna_ops import coach_trait_iterator, get_coach


def list_personas() -> List[Dict[str, Any]]:
    """Return persona metadata available in the local registry."""

    registry = registry_helpers.load_persona_registry(mode="warn")
    personas: List[Dict[str, Any]] = []
    for item in registry.items:
        personas.append(
            {
                "id": item.get("id"),
                "label": item.get("label") or item.get("summary", {}).get("name") or item.get("id"),
                "style_presets": len(item.get("style_presets") or []),
                "tone_presets": len(item.get("tone_presets") or []),
            }
        )
    return personas


def build_import_preview(
    registry: Mapping[str, Any],
    coach_id: str,
    persona_id: str,
) -> Dict[str, Any]:
    coach = get_coach(registry, coach_id)
    if coach is None:
        return {"ok": False, "error": f"Coach `{coach_id}` not found."}

    persona = registry_helpers.get_persona_contract(persona_id)
    suggestions = _extract_suggestions(persona)
    if not suggestions:
        return {
            "ok": False,
            "error": f"Persona `{persona_id}` does not expose importable traits.",
        }

    existing_ids = {trait_id for trait_id, _ in coach_trait_iterator(coach)}
    filtered: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for suggestion in suggestions:
        trait_key = suggestion.get("trait_id")
        if trait_key in existing_ids:
            skipped.append({"trait_id": trait_key, "reason": "already exists"})
            continue
        filtered.append(suggestion)

    summary = {
        "persona_id": persona_id,
        "coach_id": coach_id,
        "total_suggested": len(suggestions),
        "new_traits": len(filtered),
        "skipped": len(skipped),
    }

    return {
        "ok": True,
        "suggestions": filtered,
        "skipped": skipped,
        "summary": summary,
    }


def apply_import(
    registry: Dict[str, Any],
    coach_id: str,
    traits: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    coach = get_coach(registry, coach_id)
    if coach is None:
        raise KeyError(f"Coach `{coach_id}` not found in registry")

    container_id = _ensure_default_container(coach, traits)

    for entry in traits:
        trait_payload = {
            "id": entry.get("trait_id"),
            "label": entry.get("label") or entry.get("trait_id"),
            "core_trait": entry.get("core_trait"),
            "weight": entry.get("weight", 0.5),
            "curiosity": entry.get("curiosity"),
            "templates": entry.get("templates"),
            "provenance": entry.get("provenance", [entry.get("source") or "persona_import"]),
        }
        _append_trait(coach, container_id, trait_payload)

    registry.setdefault("coaches", {})[coach_id] = coach
    return registry


def _ensure_default_container(coach: Dict[str, Any], traits: Sequence[Mapping[str, Any]]) -> str:
    containers = coach.setdefault("containers", [])
    if not isinstance(containers, list):
        containers = []
        coach["containers"] = containers

    requested_container = None
    for entry in traits:
        raw_container = entry.get("container_id")
        if isinstance(raw_container, str) and raw_container.strip():
            requested_container = raw_container.strip()
            break

    container_id = requested_container or coach.get("default_container")
    if isinstance(container_id, str) and container_id.strip():
        container_id = container_id.strip()
    else:
        container_id = coach.get("containers", [{}])[0].get("id") if coach.get("containers") else "coach"
        container_id = str(container_id or "coach")

    for container in containers:
        if isinstance(container, Mapping) and container.get("id") == container_id:
            return container_id

    containers.append(
        {
            "id": container_id,
            "label": container_id.replace("_", " ").title(),
            "traits": [],
        }
    )
    return container_id


def _append_trait(coach: Dict[str, Any], container_id: str, trait_payload: Mapping[str, Any]) -> None:
    containers = coach.setdefault("containers", [])
    for container in containers:
        if isinstance(container, Mapping) and container.get("id") == container_id:
            traits = container.setdefault("traits", [])
            if isinstance(traits, list):
                traits.append(dict(trait_payload))
            return
    # Fallback — container missing because payload mutated elsewhere
    containers.append(
        {
            "id": container_id,
            "label": container_id.replace("_", " ").title(),
            "traits": [dict(trait_payload)],
        }
    )


def _extract_suggestions(persona: Mapping[str, Any]) -> List[Dict[str, Any]]:
    coach_id = str(persona.get("id") or persona.get("summary", {}).get("id") or "persona").strip()
    container_id = coach_id or "persona"
    catalog = _core_trait_catalog()

    suggestions: List[Dict[str, Any]] = []
    style_defaults = persona.get("style_defaults") if isinstance(persona.get("style_defaults"), Mapping) else {}

    # Style presets → traits
    for preset in persona.get("style_presets") or []:
        if not isinstance(preset, Mapping):
            continue
        preset_id = str(preset.get("id") or "").strip()
        if not preset_id:
            continue
        trait_id = f"style.{preset_id}"
        label = preset.get("label") or preset_id.replace("_", " ").title()
        description = preset.get("description") or ""
        templates = {"neutral": description} if description else {}
        core_trait = _match_core_trait(label, catalog)
        suggestions.append(
            _build_trait_suggestion(
                container_id,
                trait_id,
                label,
                templates,
                core_trait=core_trait,
                source="style_preset",
                curiosity=_default_curiosity(style_defaults),
            )
        )

    # prompt bundle entries → traits
    prompt_bundle = persona.get("prompt_bundle") if isinstance(persona.get("prompt_bundle"), Mapping) else {}
    for key, value in prompt_bundle.items():
        if not isinstance(value, str) or not value.strip():
            continue
        trait_id = f"prompt.{key}"
        label = f"Prompt · {key.replace('_', ' ').title()}"
        templates = {"neutral": value.strip()}
        core_trait = _match_core_trait(label, catalog)
        suggestions.append(
            _build_trait_suggestion(
                container_id,
                trait_id,
                label,
                templates,
                core_trait=core_trait,
                source="prompt_bundle",
                curiosity=_default_curiosity(style_defaults),
            )
        )

    # tone presets (if available)
    for preset in persona.get("tone_presets") or []:
        if not isinstance(preset, Mapping):
            continue
        preset_id = str(preset.get("id") or "").strip()
        if not preset_id:
            continue
        trait_id = f"tone.{preset_id}"
        label = preset.get("label") or preset_id.replace("_", " ").title()
        description = preset.get("description") or ""
        templates = {"neutral": description} if description else {}
        core_trait = _match_core_trait(label, catalog)
        suggestions.append(
            _build_trait_suggestion(
                container_id,
                trait_id,
                label,
                templates,
                core_trait=core_trait,
                source="tone_preset",
                curiosity=_default_curiosity(style_defaults),
            )
        )

    return suggestions


_CORE_TRAIT_CATALOG: Optional[List[Tuple[str, str]]] = None


def _core_trait_catalog() -> List[Tuple[str, str]]:
    global _CORE_TRAIT_CATALOG
    if _CORE_TRAIT_CATALOG is not None:
        return _CORE_TRAIT_CATALOG

    schema = schema_utils.load_schema(credna_store.REPO_ROOT)
    catalog: List[Tuple[str, str]] = []
    containers = schema.get("containers") if isinstance(schema.get("containers"), list) else []
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        container_id = str(container.get("id") or "").strip()
        traits = container.get("traits") if isinstance(container.get("traits"), list) else []
        for trait in traits:
            if not isinstance(trait, Mapping):
                continue
            trait_id = str(trait.get("id") or "").strip()
            if not trait_id:
                continue
            path = f"{container_id}.{trait_id}" if container_id else trait_id
            label = str(trait.get("label") or trait_id)
            catalog.append((path, label))
    _CORE_TRAIT_CATALOG = catalog
    return catalog


def _match_core_trait(label: str, catalog: Sequence[Tuple[str, str]]) -> Optional[str]:
    if not label:
        return None
    candidate = label.lower()
    best_score = 0.0
    best_path: Optional[str] = None
    for path, core_label in catalog:
        score = difflib.SequenceMatcher(None, candidate, core_label.lower()).ratio()
        if score > best_score:
            best_score = score
            best_path = path
    return best_path if best_score >= 0.72 else None


def _build_trait_suggestion(
    container_id: str,
    trait_id: str,
    label: str,
    templates: Mapping[str, Any],
    *,
    core_trait: Optional[str],
    source: str,
    curiosity: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "container_id": container_id,
        "trait_id": trait_id,
        "label": label,
        "templates": dict(templates),
        "core_trait": core_trait,
        "source": source,
        "weight": 0.5,
        "curiosity": curiosity,
    }


def _default_curiosity(style_defaults: Mapping[str, Any]) -> Dict[str, Any]:
    base = 0.5
    warmth = style_defaults.get("warmth")
    try:
        warmth_value = float(warmth)
    except (TypeError, ValueError):
        warmth_value = None
    if warmth_value is not None:
        base = min(max(warmth_value / 100.0, 0.2), 0.95)
    return {"default": round(base, 3), "decay_days": 30}


__all__ = [
    "list_personas",
    "build_import_preview",
    "apply_import",
]
