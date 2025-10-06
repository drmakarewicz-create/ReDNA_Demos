"""Operational helpers for Coach ReDNA coverage and mapping."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ExplorerDev import schema_utils
from ExplorerDev.credna import credna_store
from ExplorerDev.credna.ctg import compute_coverage
from ExplorerDev.write_utils import WriteProtectContext


def list_coaches(registry: Mapping[str, Any]) -> List[str]:
    coaches = registry.get("coaches") if isinstance(registry, Mapping) else None
    if isinstance(coaches, Mapping):
        return sorted(str(key) for key in coaches.keys())
    return []


def get_coach(registry: Mapping[str, Any], coach_id: str) -> Optional[Dict[str, Any]]:
    coaches = registry.get("coaches") if isinstance(registry, Mapping) else None
    if isinstance(coaches, Mapping):
        coach = coaches.get(coach_id)
        if isinstance(coach, Mapping):
            return dict(coach)
    return None


def coach_trait_iterator(coach: Mapping[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    containers = coach.get("containers") if isinstance(coach.get("containers"), list) else []
    bundle: List[Tuple[str, Dict[str, Any]]] = []
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
            node_id = f"{container_id}.{trait_id}" if container_id else trait_id
            bundle.append((node_id, dict(trait)))
    return bundle


def _normalise_key(value: str) -> str:
    return value.replace(" ", "").replace("_", "").lower()


def _normalise_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def resolve_coach_for_persona(
    registry: Mapping[str, Any],
    persona_id: str,
    *,
    display_name: Optional[str] = None,
) -> Optional[str]:
    """Attempt to map a persona identifier to a CReDNA coach id."""

    coaches = registry.get("coaches") if isinstance(registry, Mapping) else None
    if not isinstance(coaches, Mapping) or not coaches:
        return None

    persona_tokens = {persona_id.strip().lower()} if persona_id else set()
    if display_name:
        persona_tokens.add(display_name.strip().lower())
    persona_tokens = {token for token in persona_tokens if token}
    persona_norm = {_normalise_token(token) for token in persona_tokens}

    def _coach_tokens(coach_id: str, coach_payload: Mapping[str, Any]) -> Tuple[set[str], set[str]]:
        raw_candidates = {
            coach_id,
            str(coach_payload.get("label") or ""),
            str(coach_payload.get("name") or ""),
        }
        raw_tokens = {token.strip().lower() for token in raw_candidates if token and token.strip()}
        norm_tokens = {_normalise_token(token) for token in raw_tokens}
        return raw_tokens, norm_tokens

    # Direct match on raw or normalised tokens
    for coach_id, payload in coaches.items():
        if not isinstance(payload, Mapping):
            continue
        raw_tokens, norm_tokens = _coach_tokens(coach_id, payload)
        if persona_tokens & raw_tokens or persona_norm & norm_tokens:
            return coach_id

    # Fallback — substring match on normalised tokens
    for coach_id, payload in coaches.items():
        if not isinstance(payload, Mapping):
            continue
        _, norm_tokens = _coach_tokens(coach_id, payload)
        if any(
            norm and norm in candidate
            for candidate in norm_tokens
            for norm in persona_norm
        ):
            return coach_id

    return None


def _core_lookup_from_resolved(flat_payload: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    if not isinstance(flat_payload, Mapping):
        return lookup
    for raw_key, payload in flat_payload.items():
        if not isinstance(payload, Mapping):
            continue
        key = _normalise_key(str(raw_key))
        ucn = _safe_float(payload.get("ucn"))
        lookup[key] = {
            "raw_key": raw_key,
            "ucn": ucn,
            "payload": dict(payload),
        }
    return lookup


def _curiosity_lookup(snapshot: Optional[schema_utils.LiveCuriositySnapshot]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    if snapshot is None:
        return lookup

    for row in snapshot.top_traits:
        if not isinstance(row, Mapping):
            continue
        container = str(row.get("container_id") or row.get("container") or "").strip()
        trait = str(row.get("trait_id") or row.get("trait") or "").strip()
        if not container or not trait:
            continue
        key = _normalise_key(f"{container}.{trait}")
        lookup[key] = {
            "curiosity": _safe_float(row.get("curiosity")),
            "ucn": _safe_float(row.get("ucn")),
            "container": container,
            "trait": trait,
            "resolved_value": row.get("resolved_value"),
            "weight": _safe_float(row.get("weight")) or 1.0,
            "source": row.get("source") or row.get("curiosity_source"),
            "rr": _safe_float(row.get("rr")),
        }

    # fall back to snapshot.resolved which is keyed by trait only
    for trait_key, payload in snapshot.resolved.items():
        if not isinstance(payload, Mapping):
            continue
        container = str(payload.get("container_id") or "").strip()
        key_options = [trait_key, f"{container}.{trait_key}" if container else trait_key]
        entry = {
            "curiosity": _safe_float(payload.get("curiosity")),
            "ucn": _safe_float(payload.get("ucn")),
            "container": container,
            "trait": trait_key,
            "resolved_value": payload.get("resolved_value"),
            "weight": _safe_float(payload.get("curiosity_weight")) or 1.0,
            "source": payload.get("curiosity_source"),
            "rr": _safe_float(payload.get("curiosity_rr")),
        }
        for option in key_options:
            if option:
                lookup.setdefault(_normalise_key(option), entry)
    return lookup


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric


def compute_coach_curiosity(
    trait: Mapping[str, Any],
    *,
    weight: float,
    curiosity_lookup: Mapping[str, Dict[str, Any]],
    core_trait_key: Optional[str],
) -> Tuple[float, Optional[float]]:
    default_curiosity = _safe_float(
        trait.get("curiosity", {}).get("default") if isinstance(trait.get("curiosity"), Mapping) else trait.get("curiosity_default")
    ) or 0.0
    core_curiosity = None
    if core_trait_key:
        entry = curiosity_lookup.get(core_trait_key)
        if entry is None:
            entry = curiosity_lookup.get(_normalise_key(core_trait_key))
        if entry is not None:
            core_curiosity = entry.get("curiosity")
    if core_curiosity is not None:
        blended = max(default_curiosity, max(core_curiosity, 0.0) * max(weight, 0.0))
    else:
        blended = default_curiosity
    return blended, core_curiosity


def build_coach_snapshot(
    registry: Mapping[str, Any],
    coach_id: str,
    *,
    user_id: Optional[str] = None,
    core_base: Optional[str] = None,
    curiosity_limit: int = 200,
    timeout: float = 3.0,
) -> Dict[str, Any]:
    """Compute coverage + curiosity details for a coach (read-only)."""

    coach = get_coach(registry, coach_id)
    if coach is None:
        return {"ok": False, "error": f"Coach `{coach_id}` not found."}

    resolved_flat: Optional[Dict[str, Any]] = None
    resolved_error: Optional[str] = None
    if user_id:
        resolved_flat, resolved_error = schema_utils.fetch_core_resolved_flat(
            user_id,
            core_base=core_base,
            timeout=timeout,
        )

    curiosity_snapshot: Optional[schema_utils.LiveCuriositySnapshot] = None
    curiosity_error: Optional[str] = None
    if user_id:
        snapshot = schema_utils.load_live_curiosity_snapshot(
            user_id,
            core_base=core_base,
            limit=curiosity_limit,
            timeout=timeout,
        )
        curiosity_snapshot = snapshot
        curiosity_error = snapshot.error

    coverage = compute_coverage(coach, resolved_flat)

    curiosity_lookup = _curiosity_lookup(curiosity_snapshot)
    resolved_lookup = _core_lookup_from_resolved(resolved_flat)

    items: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []

    for trait_id, trait in coach_trait_iterator(coach):
        weight = _safe_float(trait.get("weight")) or 0.0
        core_trait = str(trait.get("core_trait") or "").strip() or None
        core_key = _normalise_key(core_trait) if core_trait else None
        blended_curiosity, core_curiosity = compute_coach_curiosity(
            trait,
            weight=weight or 1.0,
            curiosity_lookup=curiosity_lookup,
            core_trait_key=core_key,
        )
        resolved_entry = resolved_lookup.get(core_key) if core_key else None
        has_templates = _trait_has_templates(trait)
        reason_list: List[str] = []
        if not has_templates:
            reason_list.append("missing template")
        if not core_trait:
            reason_list.append("missing core mapping")
        elif resolved_entry is None:
            reason_list.append("core trait not in resolved snapshot")
        item = {
            "trait": trait_id,
            "label": trait.get("label", trait_id.split(".")[-1]),
            "coach_curiosity": blended_curiosity,
            "core_curiosity": core_curiosity,
            "core_ucn": resolved_entry.get("ucn") if resolved_entry else None,
            "core_trait": core_trait,
            "weight": weight,
            "has_templates": has_templates,
        }
        items.append(item)
        if reason_list:
            gaps.append({"trait": trait_id, "reasons": reason_list})

    items.sort(key=lambda row: row.get("coach_curiosity") or 0.0, reverse=True)

    snapshot_payload = {
        "coach_id": coach_id,
        "user_id": user_id,
        "coverage": coverage,
        "top_curiosity": items[:15],
        "all_curiosity": items,
        "gaps": gaps,
        "resolved_error": resolved_error,
        "curiosity_error": curiosity_error,
    }
    return {"ok": True, "snapshot": snapshot_payload}


def find_trait_template(
    coach: Mapping[str, Any],
    container_id: str,
    trait_id: str,
    tone: str,
) -> Optional[Dict[str, Any]]:
    """Return the preferred template payload for a given trait within a coach."""

    if not isinstance(coach, Mapping):
        return None

    containers = coach.get("containers") if isinstance(coach.get("containers"), list) else []
    selected_trait: Optional[Mapping[str, Any]] = None
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        if str(container.get("id") or "").strip() != container_id:
            continue
        traits = container.get("traits") if isinstance(container.get("traits"), list) else []
        for trait in traits:
            if not isinstance(trait, Mapping):
                continue
            if str(trait.get("id") or "").strip() == trait_id:
                selected_trait = trait
                break
        if selected_trait is not None:
            break

    if selected_trait is None:
        return None

    templates = selected_trait.get("templates") if isinstance(selected_trait.get("templates"), Mapping) else {}
    if not templates:
        return None

    def _tone_key(value: str) -> str:
        return value.replace("-", " ").replace("_", " ").strip().lower()

    tone_key = _tone_key(str(tone or ""))
    candidate = templates.get(tone_key)
    tone_used = tone_key
    if not isinstance(candidate, str) or not candidate.strip():
        neutral = templates.get("neutral") or templates.get("default")
        if isinstance(neutral, str) and neutral.strip():
            candidate = neutral
            tone_used = "neutral"
        else:
            for key, value in templates.items():
                if isinstance(value, str) and value.strip():
                    candidate = value
                    tone_used = key
                    break

    if not isinstance(candidate, str) or not candidate.strip():
        return None

    return {
        "template": candidate.strip(),
        "tone_used": tone_used,
        "trait_label": str(selected_trait.get("label") or trait_id),
        "provenance": selected_trait.get("provenance"),
        "weight": selected_trait.get("weight"),
    }


def _trait_has_templates(trait: Mapping[str, Any]) -> bool:
    templates = trait.get("templates")
    if isinstance(templates, Mapping):
        return any(
            isinstance(value, str) and value.strip()
            for value in templates.values()
        )
    return False


def ensure_registry(context: Optional[WriteProtectContext] = None) -> Dict[str, Any]:
    """Load registry through the store helper."""

    return credna_store.load_registry(context)


__all__ = [
    "list_coaches",
    "get_coach",
    "coach_trait_iterator",
    "build_coach_snapshot",
    "compute_coach_curiosity",
    "ensure_registry",
    "resolve_coach_for_persona",
    "find_trait_template",
]
