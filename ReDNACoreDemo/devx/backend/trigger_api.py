from __future__ import annotations

"""
DevX API endpoints for per-user trigger configuration and testing.
"""

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel
from typing import Any, Dict, Optional

from ReDNACoreDemo.core.agent_triggers import TriggerEngine
from ReDNACoreDemo.core.agent_trigger_config import TriggerConfig, FileWatcherConfig, CalendarConfig, TelemetryThresholdConfig, ConflictBacklogConfig
from ReDNACoreDemo.core.agent_capabilities import CapabilityError, require_capability_header


router = APIRouter(prefix="/devx/api/users", tags=["triggers"])
engine = TriggerEngine()


class TriggerConfigPayload(BaseModel):
    file_watcher: Optional[Dict[str, Any]] = None
    calendar: Optional[Dict[str, Any]] = None
    telemetry_threshold: Optional[Dict[str, Any]] = None
    conflict_backlog: Optional[Dict[str, Any]] = None


class TriggerTestRequest(BaseModel):
    type: str
    payload: Dict[str, Any] = {}


def _update_section(config: TriggerConfig, payload: Dict[str, Any]) -> TriggerConfig:
    if "file_watcher" in payload and payload["file_watcher"] is not None:
        config.file_watcher = FileWatcherConfig.from_dict(payload["file_watcher"])
    if "calendar" in payload and payload["calendar"] is not None:
        config.calendar = CalendarConfig.from_dict(payload["calendar"])
    if "telemetry_threshold" in payload and payload["telemetry_threshold"] is not None:
        config.telemetry_threshold = TelemetryThresholdConfig.from_dict(payload["telemetry_threshold"])
    if "conflict_backlog" in payload and payload["conflict_backlog"] is not None:
        config.conflict_backlog = ConflictBacklogConfig.from_dict(payload["conflict_backlog"])
    return config


def _require_config_capability(request: Request, user_id: str) -> None:
    try:
        require_capability_header(request.headers, user_id=user_id, scope="core.agent.config")
    except CapabilityError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/{user_id}/triggers/config")
async def get_triggers_config(user_id: str, request: Request) -> Dict[str, Any]:
    _require_config_capability(request, user_id)
    config = engine.load_config(user_id)
    recent = engine.list_recent_events(user_id)
    return {"config": config.to_dict(), "recent": recent}


@router.get("/{user_id}/triggers/recent")
async def get_recent_triggers(user_id: str, request: Request, limit: int = 20) -> Dict[str, Any]:
    _require_config_capability(request, user_id)
    events = engine.list_recent_events(user_id, limit=limit)
    return {"events": events, "count": len(events)}


@router.post("/{user_id}/triggers/config")
async def set_triggers_config(user_id: str, request: Request, payload: TriggerConfigPayload) -> Dict[str, Any]:
    _require_config_capability(request, user_id)
    config = engine.load_config(user_id)
    updated = _update_section(config, payload.dict(exclude_none=True))
    engine.save_config(user_id, updated)
    return {"ok": True, "config": updated.to_dict()}


@router.post("/{user_id}/triggers/test")
async def create_test_trigger(user_id: str, request: Request, payload: TriggerTestRequest) -> Dict[str, Any]:
    _require_config_capability(request, user_id)
    event_type = payload.type
    data = payload.payload or {}
    try:
        result = engine.emit_trigger(user_id, event_type, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result:
        return {"ok": False, "ignored": True}
    return {"ok": True, "event": result}


@router.post("/{user_id}/triggers/webhook")
async def trigger_webhook(user_id: str, request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    config = engine.load_config(user_id)
    secret_header = request.headers.get("x-triggers-secret")
    expected_secret = config.calendar.shared_secret
    if expected_secret and secret_header != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret.")

    trigger_type = payload.get("type")
    if trigger_type == "calendar":
        result = engine.ingest_calendar_event(user_id, payload.get("event", {}))
    elif trigger_type == "file":
        path = payload.get("path")
        if not path:
            raise HTTPException(status_code=400, detail="Payload missing path")
        result = engine.ingest_file_event(user_id, path)
    else:
        raise HTTPException(status_code=400, detail="Unknown webhook trigger type")

    if not result:
        return {"ok": False, "ignored": True}
    return {"ok": True, "event": result}
