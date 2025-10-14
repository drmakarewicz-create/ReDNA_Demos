from __future__ import annotations

"""
Trigger configuration helpers for Agentic Head Coach.

Stores per-user trigger preferences under `data/users/<id>/agent/triggers.json`.
The configuration controls which trigger sources are enabled and the thresholds
used for rate limiting and deduplication.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .storage import ensure_dirs_for_user


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class FileWatcherConfig:
    enabled: bool = True
    paths: List[str] = field(default_factory=lambda: ["watched"])
    dedupe_minutes: int = 5
    max_events_per_minute: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "paths": list(self.paths or ["watched"]),
            "dedupe_minutes": self.dedupe_minutes,
            "max_events_per_minute": self.max_events_per_minute,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileWatcherConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            paths=list(data.get("paths") or ["watched"]),
            dedupe_minutes=int(data.get("dedupe_minutes", 5)),
            max_events_per_minute=int(data.get("max_events_per_minute", 5)),
        )


@dataclass
class CalendarConfig:
    enabled: bool = False
    shared_secret: Optional[str] = None
    lead_minutes: int = 120
    max_events_per_day: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "shared_secret": self.shared_secret,
            "lead_minutes": self.lead_minutes,
            "max_events_per_day": self.max_events_per_day,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarConfig":
        return cls(
            enabled=bool(data.get("enabled", False)),
            shared_secret=(data.get("shared_secret") or None),
            lead_minutes=int(data.get("lead_minutes", 120)),
            max_events_per_day=int(data.get("max_events_per_day", 10)),
        )


@dataclass
class TelemetryThresholdConfig:
    enabled: bool = True
    event_count: int = 3
    window_hours: int = 6
    sentiment_threshold: float = -0.5
    max_events_per_day: int = 12

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "event_count": self.event_count,
            "window_hours": self.window_hours,
            "sentiment_threshold": self.sentiment_threshold,
            "max_events_per_day": self.max_events_per_day,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryThresholdConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            event_count=int(data.get("event_count", 3)),
            window_hours=int(data.get("window_hours", 6)),
            sentiment_threshold=float(data.get("sentiment_threshold", -0.5)),
            max_events_per_day=int(data.get("max_events_per_day", 12)),
        )


@dataclass
class ConflictBacklogConfig:
    enabled: bool = True
    threshold: int = 5
    max_events_per_day: int = 8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "threshold": self.threshold,
            "max_events_per_day": self.max_events_per_day,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConflictBacklogConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            threshold=int(data.get("threshold", 5)),
            max_events_per_day=int(data.get("max_events_per_day", 8)),
        )


@dataclass
class TriggerConfig:
    file_watcher: FileWatcherConfig = field(default_factory=FileWatcherConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    telemetry_threshold: TelemetryThresholdConfig = field(default_factory=TelemetryThresholdConfig)
    conflict_backlog: ConflictBacklogConfig = field(default_factory=ConflictBacklogConfig)
    dedupe_window_minutes: int = 15
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_watcher": self.file_watcher.to_dict(),
            "calendar": self.calendar.to_dict(),
            "telemetry_threshold": self.telemetry_threshold.to_dict(),
            "conflict_backlog": self.conflict_backlog.to_dict(),
            "dedupe_window_minutes": self.dedupe_window_minutes,
            "updated_at": self.updated_at or _utc_iso(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerConfig":
        return cls(
            file_watcher=FileWatcherConfig.from_dict(data.get("file_watcher") or {}),
            calendar=CalendarConfig.from_dict(data.get("calendar") or {}),
            telemetry_threshold=TelemetryThresholdConfig.from_dict(data.get("telemetry_threshold") or {}),
            conflict_backlog=ConflictBacklogConfig.from_dict(data.get("conflict_backlog") or {}),
            dedupe_window_minutes=int(data.get("dedupe_window_minutes", 15)),
            updated_at=data.get("updated_at"),
        )


def _config_path(user_id: str) -> Path:
    paths = ensure_dirs_for_user(user_id)
    agent_dir = Path(paths["udir"]) / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    return agent_dir / "triggers.json"


def load_trigger_config(user_id: str) -> TriggerConfig:
    """
    Load trigger configuration for a user. Returns defaults if no config exists.
    """
    path = _config_path(user_id)
    if not path.exists():
        return TriggerConfig()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return TriggerConfig()
        return TriggerConfig.from_dict(raw)
    except json.JSONDecodeError:
        return TriggerConfig()


def save_trigger_config(user_id: str, config: TriggerConfig) -> None:
    """
    Persist trigger configuration to disk.
    """
    path = _config_path(user_id)
    payload = config.to_dict()
    payload["updated_at"] = _utc_iso()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    tmp_path.replace(path)
