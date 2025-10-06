# ReDNACoreDemo/core/events.py
from __future__ import annotations
from typing import Any, Dict
from .storage import event_checkpoint

def capture(user_id: str, name: str, payload: Dict[str, Any]) -> None:
    event_checkpoint(user_id, name, payload)