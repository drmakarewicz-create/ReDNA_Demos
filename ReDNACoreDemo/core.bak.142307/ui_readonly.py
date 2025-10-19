"""Read-only utilities exposing Head Coach UI contracts.

These helpers surface persona rosters, planner ask queues, observation
aggregates, and unabridged trait snapshots without mutating storage.
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from . import persona_registry, storage, planner

_DEFAULT_ICON = "💬"
_DEFAULT_ICONS: Dict[str, str] = {
    "head_coach": "🧭",
    "relationship_coach": "💞",
    "rc": "💞",
    "padna_coach": "🧬",
    "padna": "🧬",
    "photo_coach": "📸",
    "photo": "📸",
    "nutrition": "🥗",
    "strength": "💪",
    "data_scientist": "📊",
    "ethics": "⚖️",
}
_FALSE_TOKENS = {"0", "false", "off", "no"}
_FALLBACK_PERSONAS = [
    {"key": "head_coach", "label": "Head Coach (Orchestrator)", "icon": _DEFAULT_ICONS["head_coach"]},
    {"key": "relationship_coach", "label": "Relationship Coach", "icon": _DEFAULT_ICONS["relationship_coach"]},
    {"key": "padna_coach", "label": "PaDNA Coach", "icon": _DEFAULT_ICONS["padna_coach"]},
    {"key": "photo_coach", "label": "Photo Coach", "icon": _DEFAULT_ICONS["photo_coach"]},
]

def _persona_enabled(persona_id: str) -> bool:
    env_name = f"PERSONA_{persona_id.upper()}_ENABLED"
    raw = os.getenv(env_name)
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() not in _FALSE_TOKENS


def _persona_label(persona_id: str, meta: Mapping[str, Any]) -> str:
    label = str(
        meta.get("title")
        or meta.get("label")
        or meta.get("name")
        or persona_id.replace("_", " ").title()
    )
    if persona_id == "head_coach" and "(Orchestrator)" not in label:
        label = f"{label} (Orchestrator)"
    return label


def _persona_icon(persona_id: str, meta: Mapping[str, Any]) -> str:
    icon = str(meta.get("icon", "")).strip()
    if icon:
        return icon
    return _DEFAULT_ICONS.get(persona_id, _DEFAULT_ICON)


def _load_persona_roster_from_router() -> List[Dict[str, Any]]:
    try:
        from ExplorerFinal.ui import persona_router  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        return []

    try:
        personas = persona_router.list_personas()  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - router failure
        return []

    roster: List[Dict[str, Any]] = []
    for entry in personas:
        if not isinstance(entry, Mapping):
            continue
        persona_id = str(entry.get("id") or "").strip()
        if not persona_id:
            continue
        roster.append(
            {
                "key": persona_id,
                "label": _persona_label(persona_id, entry),
                "icon": _persona_icon(persona_id, entry),
                "enabled": _persona_enabled(persona_id),
                "accent_color": entry.get("color") or entry.get("accent_color"),
            }
        )
    return roster


def _load_persona_roster_from_registry() -> List[Dict[str, Any]]:
    roster: List[Dict[str, Any]] = []
    try:
        summaries = persona_registry.list_personas()
    except Exception:  # pragma: no cover - registry unavailable
        return roster

    for summary in summaries:
        persona_id = summary.id
        config = persona_registry.get_persona(persona_id)
        meta: Mapping[str, Any] = {
            "title": getattr(config, "name", None),
            "color": getattr(config, "accent_color", None) if config else None,
        }
        roster.append(
            {
                "key": persona_id,
                "label": _persona_label(persona_id, meta),
                "icon": _persona_icon(persona_id, meta),
                "enabled": _persona_enabled(persona_id),
                "accent_color": getattr(config, "accent_color", None) if config else None,
            }
        )
    return roster


def persona_roster() -> List[Dict[str, Any]]:
    """Return persona roster metadata for UI shells."""

    roster = _load_persona_roster_from_router()
    if roster:
        roster.sort(key=lambda item: item["key"])
        return roster

    roster = _load_persona_roster_from_registry()
    roster.sort(key=lambda item: item["key"])
    if roster:
        return roster

    fallback: List[Dict[str, Any]] = []
    for entry in _FALLBACK_PERSONAS:
        persona_id = entry["key"]
        fallback.append(
            {
                "key": persona_id,
                "label": entry["label"],
                "icon": entry.get("icon", _DEFAULT_ICON),
                "enabled": _persona_enabled(persona_id),
                "accent_color": None,
            }
        )
    return fallback


def _user_file(user_id: str, filename: str) -> Path:
    safe_id = user_id.strip()
    return storage.USERS_DIR / safe_id / filename


def planner_asks(user_id: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    """Return planner asks enriched with policy metadata for UI shells."""

    entries = planner.list_for_ui(user_id, limit=limit)
    return entries


def _normalize_observation_entries(payload: Any) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []

    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    entries.append(item)
        else:
            for key, value in payload.items():
                if isinstance(value, dict):
                    for trait_id, trait_payload in value.items():
                        if isinstance(trait_payload, dict):
                            normalized = dict(trait_payload)
                            normalized.setdefault("trait_id", trait_id)
                            normalized.setdefault("ts", key)
                            entries.append(normalized)
        return entries

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                entries.append(item)
    return entries


def _latest_value(entries: Iterable[Mapping[str, Any]], trait_id: str) -> Optional[Any]:
    for entry in reversed(list(entries)):
        if str(entry.get("trait_id") or entry.get("trait")) == trait_id:
            return entry.get("value") or entry.get("resolved_value")
    return None


def _find_all(entries: Iterable[Mapping[str, Any]], trait_id: str) -> List[Any]:
    values: List[Any] = []
    for entry in entries:
        entry_trait = str(entry.get("trait_id") or entry.get("trait"))
        if entry_trait == trait_id:
            value = entry.get("value") or entry.get("resolved_value")
            if value is not None:
                values.append(value)
    return values


def _parse_histogram(value: Any) -> Dict[str, float]:
    if isinstance(value, Mapping):
        return {str(k): float(v) for k, v in value.items()}
    if isinstance(value, str):
        buckets: Dict[str, float] = {}
        for token in value.split(","):
            if ":" not in token:
                continue
            label, count = token.split(":", 1)
            try:
                buckets[label.strip()] = float(count.strip())
            except ValueError:
                continue
        return buckets
    return {}


def observation_aggregates(user_id: str) -> Dict[str, Any]:
    """Summarize conversational observation metrics for ``user_id``."""

    obs_path = _user_file(user_id, storage.OBS_FILENAME)
    payload = storage.load_json(obs_path, default={})
    entries = _normalize_observation_entries(payload)
    if not entries:
        return {
            "user_id": user_id,
            "dialog_acts": {"latest": None, "distribution": {}},
            "cadence": {"latest_bucket": None, "histogram": {}},
            "latency": {"median_ms": None, "mean_ms": None, "histogram": {}},
            "observation_count": 0,
        }

    latest_dialog = _latest_value(entries, "conversation.dialog_act")
    distribution_values = _find_all(entries, "conversation.dialog_distribution")
    histogram_values = _find_all(entries, "conversation.cadence_histogram")
    cadence_bucket = _latest_value(entries, "conversation.cadence")

    distribution = Counter()
    for value in distribution_values:
        distribution.update(_parse_histogram(value))

    cadence_histogram: Dict[str, float] = {}
    for value in histogram_values:
        parsed = _parse_histogram(value)
        for key, count in parsed.items():
            cadence_histogram[key] = cadence_histogram.get(key, 0.0) + count

    median_latency = _latest_value(entries, "conversation.response_latency_median")
    mean_latency = _latest_value(entries, "conversation.response_latency_mean")
    latency_histogram_values = _find_all(entries, "conversation.response_latency_histogram")
    latency_histogram: Dict[str, float] = {}
    for value in latency_histogram_values:
        parsed = _parse_histogram(value)
        for key, count in parsed.items():
            latency_histogram[key] = latency_histogram.get(key, 0.0) + count

    window_buckets = {
        "1h": _rolling_window(entries, 60),
        "24h": _rolling_window(entries, 24 * 60),
        "session": _rolling_window(entries, None),
    }

    return {
        "user_id": user_id,
        "dialog_acts": {
            "latest": latest_dialog,
            "distribution": dict(distribution),
        },
        "cadence": {
            "latest_bucket": cadence_bucket,
            "histogram": cadence_histogram,
        },
        "latency": {
            "median_ms": float(median_latency) if isinstance(median_latency, (int, float)) else None,
            "mean_ms": float(mean_latency) if isinstance(mean_latency, (int, float)) else None,
            "histogram": latency_histogram,
        },
        "observation_count": len(entries),
        "windows": window_buckets,
    }


def _normalized_timestamp(entry: Mapping[str, Any]) -> Optional[float]:
    raw_ts = entry.get("ts") or entry.get("timestamp")
    if raw_ts is None:
        return None
    try:
        return float(raw_ts)
    except (TypeError, ValueError):
        return None


def _rolling_window(entries: Iterable[Mapping[str, Any]], minutes: Optional[int]) -> Dict[str, Any]:
    now_ts: Optional[float] = None
    normalized_entries: List[Tuple[Mapping[str, Any], float]] = []
    for entry in entries:
        ts = _normalized_timestamp(entry)
        if ts is None:
            continue
        normalized_entries.append((entry, ts))
        if now_ts is None or ts > now_ts:
            now_ts = ts

    if now_ts is None:
        return {
            "observation_count": 0,
            "dialog_acts": {"distribution": {}, "latest": None},
            "cadence": {"histogram": {}, "latest_bucket": None},
            "latency": {"median_ms": None, "mean_ms": None, "histogram": {}},
            "per_persona": {},
        }

    cutoff = None if minutes is None else now_ts - (minutes * 60)

    filtered: List[Mapping[str, Any]] = []
    for entry, ts in normalized_entries:
        if cutoff is not None and ts < cutoff:
            continue
        filtered.append(entry)

    if not filtered:
        return {
            "observation_count": 0,
            "dialog_acts": {"distribution": {}, "latest": None},
            "cadence": {"histogram": {}, "latest_bucket": None},
            "latency": {"median_ms": None, "mean_ms": None, "histogram": {}},
            "per_persona": {},
        }

    persona_groups: Dict[str, List[Mapping[str, Any]]] = {}
    for entry in filtered:
        persona = str(entry.get("persona") or entry.get("speaker") or "assistant")
        persona_groups.setdefault(persona, []).append(entry)

    latest_dialog = _latest_value(filtered, "conversation.dialog_act")
    dialog_hist = Counter()
    for value in _find_all(filtered, "conversation.dialog_distribution"):
        dialog_hist.update(_parse_histogram(value))

    cadence_hist: Dict[str, float] = {}
    for value in _find_all(filtered, "conversation.cadence_histogram"):
        parsed = _parse_histogram(value)
        for key, count in parsed.items():
            cadence_hist[key] = cadence_hist.get(key, 0.0) + count

    latency_hist: Dict[str, float] = {}
    for value in _find_all(filtered, "conversation.response_latency_histogram"):
        parsed = _parse_histogram(value)
        for key, count in parsed.items():
            latency_hist[key] = latency_hist.get(key, 0.0) + count

    per_persona: Dict[str, Dict[str, Any]] = {}
    for persona, persona_entries in persona_groups.items():
        per_persona[persona] = {
            "observation_count": len(persona_entries),
            "dialog_acts": {
                "latest": _latest_value(persona_entries, "conversation.dialog_act"),
                "distribution": dict(_aggregate_histograms(persona_entries, "conversation.dialog_distribution")),
            },
        }

    return {
        "observation_count": len(filtered),
        "dialog_acts": {"latest": latest_dialog, "distribution": dict(dialog_hist)},
        "cadence": {"latest_bucket": _latest_value(filtered, "conversation.cadence"), "histogram": cadence_hist},
        "latency": {
            "median_ms": _latest_numeric(filtered, "conversation.response_latency_median"),
            "mean_ms": _latest_numeric(filtered, "conversation.response_latency_mean"),
            "histogram": latency_hist,
        },
        "per_persona": per_persona,
    }


def _aggregate_histograms(entries: Iterable[Mapping[str, Any]], key: str) -> Counter:
    aggregated = Counter()
    for value in _find_all(entries, key):
        aggregated.update(_parse_histogram(value))
    return aggregated


def _latest_numeric(entries: Iterable[Mapping[str, Any]], key: str) -> Optional[float]:
    value = _latest_value(entries, key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _trait_badges(trait_payload: Mapping[str, Any]) -> List[str]:
    badges: List[str] = []
    metadata = trait_payload.get("metadata") if isinstance(trait_payload.get("metadata"), Mapping) else {}
    if trait_payload.get("sensitive") or metadata.get("sensitive"):
        badges.append("sensitive")
    reasons = trait_payload.get("reasons")
    if isinstance(reasons, (list, tuple)):
        if any("observation" in str(reason).lower() for reason in reasons):
            badges.append("observational")
    return badges


def _resolved_payload(user_id: str) -> Dict[str, Any]:
    resolved_path = _user_file(user_id, storage.RESOLVED_FILENAME)
    payload = storage.load_json(resolved_path, default={})
    if isinstance(payload, Mapping) and isinstance(payload.get("resolved"), Mapping):
        return payload["resolved"]
    if isinstance(payload, Mapping):
        return dict(payload)
    return {}


def unabridged_snapshot(user_id: str) -> Dict[str, Any]:
    """Return per-trait resolved data with governance badges for ``user_id``."""

    resolved = _resolved_payload(user_id)
    traits: List[Dict[str, Any]] = []
    for trait_id, payload in sorted(resolved.items()):
        if not isinstance(payload, Mapping):
            payload = {"resolved_value": payload}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}

        # Support both 'value' (new canonical format) and 'resolved_value' (legacy)
        trait_value = payload.get("value") or payload.get("resolved_value")

        traits.append(
            {
                "trait_id": trait_id,
                "value": trait_value,
                "ucn": payload.get("ucn"),
                "rr": payload.get("rr"),
                "curiosity": payload.get("curiosity"),
                "reasons": list(payload.get("reasons", [])) if isinstance(payload.get("reasons"), (list, tuple)) else [],
                "last_observed": payload.get("last_observed"),
                "metadata": metadata,
                "badges": _trait_badges(payload),
            }
        )

    return {
        "user_id": user_id,
        "traits": traits,
        "count": len(traits),
    }


__all__ = [
    "persona_roster",
    "planner_asks",
    "observation_aggregates",
    "unabridged_snapshot",
]
