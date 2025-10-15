"""Trait provenance timeline helpers for UI shells."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import storage


def _ts_to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 1e12:  # milliseconds
            seconds /= 1000.0
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        if token.isdigit():
            try:
                return _ts_to_dt(int(token))
            except Exception:
                return None
        try:
            dt = datetime.fromisoformat(token)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _load_observations(user_id: str) -> Dict[str, Any]:
    paths = storage.ensure_dirs_for_user(user_id)
    obs_path = paths["observations"]
    payload = storage.load_json(obs_path, default={})
    return payload if isinstance(payload, dict) else {}


def _observation_entries(obs_store: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    items = obs_store.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                yield item

    # legacy format may nest by timestamp -> trait -> payload
    for value in obs_store.values():
        if isinstance(value, dict) and not {"items", "by_trait"} & set(value.keys()):
            for trait_payload in value.values():
                if isinstance(trait_payload, dict):
                    yield trait_payload


def _events_dir(user_id: str) -> Path:
    ensure = storage.ensure_dirs_for_user(user_id)
    events_dir = ensure["events"]
    events_dir.mkdir(parents=True, exist_ok=True)
    return events_dir


def _iter_events(user_id: str) -> Iterable[Tuple[Path, Dict[str, Any]]]:
    events_dir = _events_dir(user_id)
    if not events_dir.exists():
        return []
    files = sorted(events_dir.glob("*.json"), reverse=True)
    entries: List[Tuple[Path, Dict[str, Any]]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            entries.append((path, payload))
    return entries


def _entry_from_observation(trait_id: str, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    trait = item.get("trait") or item.get("trait_id")
    if str(trait) != trait_id:
        return None

    provenance = item.get("provenance") or {}
    if not isinstance(provenance, dict):
        provenance = {}

    ts_value = provenance.get("when") or provenance.get("meta", {}).get("ts") or item.get("ts")
    ts_dt = _ts_to_dt(ts_value)

    source = provenance.get("source") or item.get("source") or "observation"
    reasons = provenance.get("reasons") or item.get("reasons") or []
    if isinstance(reasons, (list, tuple)):
        reason_text = ", ".join(str(r) for r in reasons if r)
    else:
        reason_text = str(reasons) if reasons else None

    value = item.get("value")
    if value is None:
        value = item.get("resolved_value")

    entry = {
        "ts": _dt_to_iso(ts_dt) or _dt_to_iso(_ts_to_dt(datetime.utcnow())),
        "source": str(source),
        "reason": reason_text,
        "value": value,
        "ucn": item.get("ucn"),
        "delta_ucn": item.get("delta_ucn"),
    }
    return entry


def _entry_from_event(trait_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    change = payload.get("change_event") if isinstance(payload, dict) else None
    if not isinstance(change, dict):
        return None
    if str(change.get("path")) != trait_id:
        return None

    ts_dt = _ts_to_dt(change.get("ts") or payload.get("ts") or payload.get("written_at"))
    provenance = change.get("provenance")
    reason = None
    if isinstance(provenance, dict):
        reason = provenance.get("reason") or provenance.get("note") or provenance.get("why")
    elif provenance:
        reason = str(provenance)

    entry = {
        "ts": _dt_to_iso(ts_dt) or _dt_to_iso(_ts_to_dt(datetime.utcnow())),
        "source": change.get("provenance") if isinstance(change.get("provenance"), str) else "change_event",
        "reason": reason,
        "value": change.get("new_value"),
        "ucn": None,
        "delta_ucn": None,
    }

    ucnrr = payload.get("ucnrr_result")
    if isinstance(ucnrr, dict):
        entry["ucn"] = ucnrr.get("ucn")
        rr_before = ucnrr.get("rr_before")
        rr_after = ucnrr.get("rr")
        if isinstance(rr_before, (int, float)) and isinstance(rr_after, (int, float)):
            entry["delta_ucn"] = float(rr_after) - float(rr_before)
    return entry


def build_timeline(user_id: str, trait_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    trait_id = trait_id.strip()
    if not trait_id:
        return []

    now_dt = datetime.now(timezone.utc)
    obs_store = _load_observations(user_id)
    entries: List[Tuple[datetime, Dict[str, Any]]] = []

    for item in _observation_entries(obs_store):
        entry = _entry_from_observation(trait_id, item)
        if not entry:
            continue
        ts_dt = _ts_to_dt(entry.get("ts"))
        ts_dt = ts_dt or now_dt
        entry["ts"] = _dt_to_iso(ts_dt)
        entry.setdefault("source", "observation")
        entries.append((ts_dt, entry))

    for _, payload in _iter_events(user_id):
        entry = _entry_from_event(trait_id, payload)
        if not entry:
            continue
        ts_dt = _ts_to_dt(entry.get("ts")) or now_dt
        entry["ts"] = _dt_to_iso(ts_dt)
        entries.append((ts_dt, entry))

    entries.sort(key=lambda row: row[0], reverse=True)
    limited = [item for _, item in entries[: max(1, limit)]]
    return limited


__all__ = ["build_timeline"]
