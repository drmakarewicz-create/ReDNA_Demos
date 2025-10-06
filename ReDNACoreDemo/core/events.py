# ReDNACoreDemo/core/events.py
"""
Event Bus for HC v1

Simple file-based event system for HC communication.
Event types: OBS_INGESTED, UCNRR_UPDATED, HC_PLAN_UPDATED, NUDGE_TRIGGERED
"""
from __future__ import annotations
from typing import Any, Dict
import json
from pathlib import Path
from datetime import datetime
from .storage import event_checkpoint

def capture(user_id: str, name: str, payload: Dict[str, Any]) -> None:
    """Legacy event capture (calls event_checkpoint)."""
    event_checkpoint(user_id, name, payload)


def publish_event(event_type: str, payload: Dict[str, Any]) -> None:
    """
    Publish event to file-based queue.

    Events are written to data/events/<event_type>/<timestamp>.json
    for async processing.

    Args:
        event_type: Event type (OBS_INGESTED, UCNRR_UPDATED, HC_PLAN_UPDATED, NUDGE_TRIGGERED)
        payload: Event data
    """
    events_dir = Path("data") / "events" / event_type
    events_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    event_file = events_dir / f"{timestamp}.json"

    event = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": payload
    }

    with open(event_file, 'w', encoding='utf-8') as f:
        json.dump(event, f, indent=2, ensure_ascii=False)