"""
Consent Timeline - Phase 6

Tracks all consent-related events for a user in chronological order.

Data structure: data/users/{user_id}/consent_timeline.jsonl

Each line is a consent event:
- Grant: Capability issued
- Revoke: Capability revoked
- Use: Capability used
- Expire: Capability expired
- Deny: Request denied

Provides:
- Chronological audit trail
- Consent state reconstruction
- GDPR compliance support
- Timeline export (JSON, CSV)
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Consent event types."""

    GRANT = "grant"
    REVOKE = "revoke"
    USE = "use"
    EXPIRE = "expire"
    DENY = "deny"
    REFRESH = "refresh"


class ConsentEvent(BaseModel):
    """Single consent event."""

    event_id: str = Field(..., description="Unique event ID")
    timestamp: str = Field(..., description="ISO-8601 timestamp")
    event_type: EventType
    user_id: str
    cap_id: Optional[str] = None
    grantee_id: Optional[str] = None
    purpose: Optional[str] = None
    scopes: Optional[List[str]] = None
    ttl: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConsentTimeline:
    """
    Consent timeline manager for a user.

    Handles:
    - Append events to timeline
    - Query events by type/date range
    - Reconstruct consent state at any point
    - Export timeline in various formats
    """

    def __init__(self, user_id: str):
        """
        Initialize consent timeline.

        Args:
            user_id: User ID
        """
        self.user_id = user_id
        self.timeline_file = (
            Path("data") / "users" / user_id / "consent_timeline.jsonl"
        )
        self.timeline_file.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: ConsentEvent) -> None:
        """
        Append event to timeline.

        Args:
            event: Consent event to append
        """
        try:
            with open(self.timeline_file, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
            logger.info(
                f"Appended {event.event_type} event to timeline for {self.user_id}"
            )
        except Exception as e:
            logger.error(f"Failed to append to consent timeline: {e}")
            raise

    def get_all_events(self) -> List[ConsentEvent]:
        """
        Get all events from timeline.

        Returns:
            List of consent events in chronological order
        """
        if not self.timeline_file.exists():
            return []

        events = []
        try:
            with open(self.timeline_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        event_data = json.loads(line)
                        events.append(ConsentEvent(**event_data))
        except Exception as e:
            logger.error(f"Failed to read consent timeline: {e}")
            raise

        return events

    def get_events_by_type(self, event_type: EventType) -> List[ConsentEvent]:
        """
        Get events of a specific type.

        Args:
            event_type: Event type to filter by

        Returns:
            List of matching events
        """
        all_events = self.get_all_events()
        return [e for e in all_events if e.event_type == event_type]

    def get_events_in_range(
        self, start: datetime, end: datetime
    ) -> List[ConsentEvent]:
        """
        Get events within a date range.

        Args:
            start: Start datetime
            end: End datetime

        Returns:
            List of events in range
        """
        all_events = self.get_all_events()
        filtered = []

        for event in all_events:
            try:
                event_time = datetime.fromisoformat(
                    event.timestamp.replace("Z", "+00:00")
                )
                if start <= event_time <= end:
                    filtered.append(event)
            except ValueError:
                logger.warning(f"Invalid timestamp in event: {event.timestamp}")
                continue

        return filtered

    def get_active_capabilities(self) -> List[Dict[str, Any]]:
        """
        Get currently active capabilities.

        Returns:
            List of active capabilities with metadata
        """
        events = self.get_all_events()
        capabilities: Dict[str, Dict[str, Any]] = {}

        # Process events chronologically
        for event in events:
            if not event.cap_id:
                continue

            if event.event_type == EventType.GRANT:
                # Add capability
                capabilities[event.cap_id] = {
                    "cap_id": event.cap_id,
                    "grantee_id": event.grantee_id,
                    "purpose": event.purpose,
                    "scopes": event.scopes,
                    "granted_at": event.timestamp,
                    "ttl": event.ttl,
                    "revoked": False,
                    "use_count": 0,
                }

            elif event.event_type == EventType.USE:
                # Increment use count
                if event.cap_id in capabilities:
                    capabilities[event.cap_id]["use_count"] += 1

            elif event.event_type in (EventType.REVOKE, EventType.EXPIRE):
                # Mark as revoked/expired
                if event.cap_id in capabilities:
                    capabilities[event.cap_id]["revoked"] = True
                    capabilities[event.cap_id]["revoked_at"] = event.timestamp
                    capabilities[event.cap_id]["revoke_reason"] = event.reason

        # Filter to only active (not revoked, not expired)
        now = datetime.utcnow()
        active = []

        for cap in capabilities.values():
            if cap["revoked"]:
                continue

            # Check TTL expiration
            granted_at = datetime.fromisoformat(
                cap["granted_at"].replace("Z", "+00:00")
            )
            ttl_seconds = self._parse_ttl(cap.get("ttl", "PT24H"))
            expiry = granted_at + timedelta(seconds=ttl_seconds)

            if now.replace(tzinfo=None) < expiry.replace(tzinfo=None):
                active.append(cap)

        return active

    def _parse_ttl(self, ttl: str) -> int:
        """
        Parse ISO-8601 duration to seconds.

        Args:
            ttl: ISO-8601 duration (e.g., 'PT24H')

        Returns:
            Duration in seconds
        """
        # Simple parser for common patterns
        if ttl.startswith("PT") and ttl.endswith("H"):
            hours = int(ttl[2:-1])
            return hours * 3600
        elif ttl.startswith("PT") and ttl.endswith("M"):
            minutes = int(ttl[2:-1])
            return minutes * 60
        elif ttl.startswith("P") and "D" in ttl:
            days = int(ttl[1:].split("D")[0])
            return days * 86400
        else:
            # Default to 24 hours
            return 86400

    def export_to_json(self) -> str:
        """
        Export timeline to JSON.

        Returns:
            JSON string of all events
        """
        events = self.get_all_events()
        return json.dumps([e.model_dump() for e in events], indent=2)

    def export_to_csv(self) -> str:
        """
        Export timeline to CSV.

        Returns:
            CSV string of all events
        """
        events = self.get_all_events()
        if not events:
            return "event_id,timestamp,event_type,user_id,cap_id,purpose\n"

        csv_lines = ["event_id,timestamp,event_type,user_id,cap_id,purpose"]

        for event in events:
            csv_lines.append(
                f"{event.event_id},"
                f"{event.timestamp},"
                f"{event.event_type},"
                f"{event.user_id},"
                f"{event.cap_id or ''},"
                f'"{event.purpose or ''}"'
            )

        return "\n".join(csv_lines)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get timeline summary statistics.

        Returns:
            Dictionary with summary stats
        """
        events = self.get_all_events()
        active_caps = self.get_active_capabilities()

        event_counts = {
            "grant": 0,
            "revoke": 0,
            "use": 0,
            "expire": 0,
            "deny": 0,
        }

        for event in events:
            event_counts[event.event_type] += 1

        return {
            "total_events": len(events),
            "event_counts": event_counts,
            "active_capabilities": len(active_caps),
            "first_event": events[0].timestamp if events else None,
            "last_event": events[-1].timestamp if events else None,
        }


__all__ = ["ConsentTimeline", "ConsentEvent", "EventType"]
