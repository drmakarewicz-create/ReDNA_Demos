from __future__ import annotations

"""
Trigger engine for Agentic Head Coach.

Transforms filesystem, calendar, telemetry, and conflict signals into normalized
trigger events and appends them to the agent inbox. The engine also enforces
deduplication and per-type rate limits using a lightweight JSON store under the
user's agent directory.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from ReDNACoreDemo import agents
from .agent_trigger_config import (
    TriggerConfig,
    load_trigger_config,
    save_trigger_config,
)
from .agent_capabilities import audit_event
from .storage import ensure_dirs_for_user


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: Optional[datetime] = None) -> str:
    return (dt or _utc_now()).isoformat().replace("+00:00", "Z")


TRIGGER_STATE_FILENAME = "triggers.cache.json"


@dataclass
class TriggerEvent:
    user_id: str
    event_type: str
    source: str
    key: str
    payload: Dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": f"trg_{uuid4().hex}",
            "type": self.event_type,
            "source": self.source,
            "key": self.key,
            "payload": self.payload,
            "timestamp": _utc_iso(self.timestamp),
        }


class TriggerStateStore:
    """
    Persists deduplication and rate-limit metadata.
    """

    def __init__(self, user_id: str):
        paths = ensure_dirs_for_user(user_id)
        self.user_id = user_id
        self.agent_dir = Path(paths["udir"]) / "agent"
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.agent_dir / TRIGGER_STATE_FILENAME
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"recent": {}, "rate": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("recent", {})
                data.setdefault("rate", {})
                return data
        except json.JSONDecodeError:
            pass
        return {"recent": {}, "rate": {}}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2, sort_keys=False), encoding="utf-8")
        tmp.replace(self.path)

    def record_event(self, event: TriggerEvent, dedupe_minutes: int, rate_limit: Dict[str, int]) -> bool:
        """
        Returns True when the event should proceed (not deduped or rate-limited).
        """
        now = event.timestamp
        key = f"{event.event_type}:{event.key}"

        # Deduplication
        recent: Dict[str, str] = self._state.setdefault("recent", {})
        if key in recent:
            last_ts = datetime.fromisoformat(recent[key])
            if now - last_ts < timedelta(minutes=dedupe_minutes):
                return False

        # Rate limiting
        rate = self._state.setdefault("rate", {})
        entry = rate.setdefault(
            event.event_type,
            {
                "window_minutes": rate_limit.get("window_minutes", 60),
                "max_events": rate_limit.get("max_events", 10),
                "timestamps": [],
            },
        )
        window_minutes = int(rate_limit.get("window_minutes", entry.get("window_minutes", 60)))
        max_events = int(rate_limit.get("max_events", entry.get("max_events", 10)))
        timestamps: List[str] = entry.setdefault("timestamps", [])
        cutoff = now - timedelta(minutes=window_minutes)
        filtered = [ts for ts in timestamps if datetime.fromisoformat(ts) > cutoff]
        if len(filtered) >= max_events:
            entry["timestamps"] = filtered
            entry["window_minutes"] = window_minutes
            entry["max_events"] = max_events
            self._state["rate"][event.event_type] = entry
            self.save()
            return False

        filtered.append(_utc_iso(now))
        entry["timestamps"] = filtered
        entry["window_minutes"] = window_minutes
        entry["max_events"] = max_events
        self._state["rate"][event.event_type] = entry

        # Update dedupe record
        recent[key] = _utc_iso(now)
        self._state["recent"] = recent
        self.save()
        return True


class TriggerEngine:
    """
    Ingests trigger sources and appends normalized events to the agent inbox.
    """

    def __init__(self):
        self._config_cache: Dict[str, TriggerConfig] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def load_config(self, user_id: str) -> TriggerConfig:
        config = load_trigger_config(user_id)
        self._config_cache[user_id] = config
        return config

    def save_config(self, user_id: str, config: TriggerConfig) -> None:
        self._config_cache[user_id] = config
        save_trigger_config(user_id, config)

    def ingest_file_event(self, user_id: str, path: str, *, extra: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        config = self._ensure_config(user_id)
        if not config.file_watcher.enabled:
            return None
        normalized_path = path.strip()
        key = normalized_path.lower()
        payload = {"path": normalized_path}
        if extra:
            for key_name, value in extra.items():
                if key_name == "path":
                    continue
                payload[key_name] = value
        event = TriggerEvent(
            user_id=user_id,
            event_type="trigger.file_added",
            source="file_watcher",
            key=key,
            payload=payload,
            timestamp=_utc_now(),
        )
        rate_limit = {
            "window_minutes": 1,
            "max_events": config.file_watcher.max_events_per_minute,
        }
        return self._record_and_append(
            user_id,
            event,
            config.file_watcher.dedupe_minutes,
            rate_limit,
            meta={"path": normalized_path},
        )

    def ingest_calendar_event(self, user_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        config = self._ensure_config(user_id)
        if not config.calendar.enabled:
            return None
        event = TriggerEvent(
            user_id=user_id,
            event_type="trigger.calendar_upcoming",
            source="calendar",
            key=str(payload.get("event_id") or payload.get("summary") or uuid4().hex).lower(),
            payload=payload,
            timestamp=_utc_now(),
        )
        rate_limit = {
            "window_minutes": 1440,
            "max_events": config.calendar.max_events_per_day,
        }
        return self._record_and_append(user_id, event, config.dedupe_window_minutes, rate_limit, meta={"event_id": event.key})

    def ingest_telemetry_threshold(
        self,
        user_id: str,
        *,
        metric: str,
        count: int,
        window_hours: int,
        sentiment: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        config = self._ensure_config(user_id)
        if not config.telemetry_threshold.enabled:
            return None
        payload = {
            "metric": metric,
            "count": count,
            "window_hours": window_hours,
        }
        if sentiment is not None:
            payload["sentiment"] = sentiment
        event = TriggerEvent(
            user_id=user_id,
            event_type="trigger.telemetry_threshold",
            source="telemetry",
            key=f"{metric}:{window_hours}",
            payload=payload,
            timestamp=_utc_now(),
        )
        rate_limit = {
            "window_minutes": 1440,
            "max_events": config.telemetry_threshold.max_events_per_day,
        }
        return self._record_and_append(
            user_id,
            event,
            config.dedupe_window_minutes,
            rate_limit,
            meta={"metric": metric, "window_hours": window_hours},
        )

    def ingest_conflict_backlog(self, user_id: str, *, backlog_size: int) -> Optional[Dict[str, Any]]:
        config = self._ensure_config(user_id)
        if not config.conflict_backlog.enabled:
            return None
        event = TriggerEvent(
            user_id=user_id,
            event_type="trigger.conflict_backlog",
            source="conflict_monitor",
            key="conflict_backlog",
            payload={"backlog_size": backlog_size},
            timestamp=_utc_now(),
        )
        rate_limit = {
            "window_minutes": 720,
            "max_events": config.conflict_backlog.max_events_per_day,
        }
        return self._record_and_append(
            user_id,
            event,
            config.dedupe_window_minutes,
            rate_limit,
            meta={"backlog_size": backlog_size},
        )

    def emit_trigger(self, user_id: str, event_type: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event_type == "trigger.file_added":
            path = payload.get("path")
            if not isinstance(path, str):
                raise ValueError("trigger.file_added requires payload.path")
        extra = dict(payload)
        path = extra.pop("path", None)
        if not isinstance(path, str):
            raise ValueError("trigger.file_added requires payload.path")
        return self.ingest_file_event(user_id, path, extra=extra)
        if event_type == "trigger.telemetry_threshold":
            return self.ingest_telemetry_threshold(
                user_id,
                metric=str(payload.get("metric") or "sentiment"),
                count=int(payload.get("count", 0)),
                window_hours=int(payload.get("window_hours", 1)),
                sentiment=payload.get("sentiment"),
            )
        if event_type == "trigger.conflict_backlog":
            return self.ingest_conflict_backlog(user_id, backlog_size=int(payload.get("backlog_size", 0)))
        if event_type == "trigger.calendar_upcoming":
            return self.ingest_calendar_event(user_id, payload)
        raise ValueError(f"Unsupported trigger type {event_type}")

    def list_recent_events(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        mailbox = agents.AgentMailbox(user_id)
        entries, _ = mailbox.read_inbox(limit=200, start_index=0)
        trigger_entries: List[Dict[str, Any]] = []
        for entry in reversed(entries):
            if isinstance(entry, dict) and str(entry.get("type", "")).startswith("trigger."):
                trigger_entries.append(entry)
                if len(trigger_entries) >= limit:
                    break
        return trigger_entries

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_config(self, user_id: str) -> TriggerConfig:
        if user_id not in self._config_cache:
            self._config_cache[user_id] = load_trigger_config(user_id)
        return self._config_cache[user_id]

    def _record_and_append(
        self,
        user_id: str,
        event: TriggerEvent,
        dedupe_minutes: int,
        rate_limit: Dict[str, int],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        state = TriggerStateStore(user_id)
        if not state.record_event(event, dedupe_minutes, rate_limit):
            audit_event(
                "trigger_dropped",
                {
                    "user_id": user_id,
                    "type": event.event_type,
                    "source": event.source,
                    "key": event.key,
                    "reason": "dedupe_rate_limit",
                },
            )
            return None

        payload = event.to_dict()
        self._append_to_inbox(user_id, payload)
        audit_payload = {
            "user_id": user_id,
            "type": event.event_type,
            "source": event.source,
            "key": event.key,
        }
        if meta:
            audit_payload.update(meta)
        audit_event("trigger_emitted", audit_payload)
        return payload

    def _append_to_inbox(self, user_id: str, payload: Dict[str, Any]) -> None:
        mailbox = agents.AgentMailbox(user_id)
        inbox_path = mailbox.mailbox.inbox
        serialized = json.dumps(payload, ensure_ascii=False)
        with inbox_path.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")
