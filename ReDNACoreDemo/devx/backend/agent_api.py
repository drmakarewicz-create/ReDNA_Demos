from __future__ import annotations

"""
DevX API endpoints for Agentic Head Coach operations.
"""

import json
import os
from pathlib import Path
from fastapi import APIRouter, Body, HTTPException, Query, Request, status
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ReDNACoreDemo import agents
from ReDNACoreDemo.core.agent_capabilities import (
    CapabilityError,
    generate_token,
    require_capability_header,
    issue_capability_record,
    audit_event,
)
from ReDNACoreDemo.core.agent_daemon import AgentDaemon
from ReDNACoreDemo.core.storage import CORE_DATA_ROOT
from . import agent_configurator


router = APIRouter(prefix="/devx/api/agents", tags=["agents"])
user_router = APIRouter(prefix="/devx/api/users", tags=["agents"])
capability_router = APIRouter(prefix="/devx/api/capability", tags=["capability"])

DEVX_ADMIN_TOKEN = os.getenv("DEVX_AGENT_ADMIN_TOKEN", "devx-local")
CAPABILITY_HEADER = "x-agent-capability"
ALLOWED_DEVX_SCOPES = {
    "core.agent.config",
    "core.agent.run",
    "agents.rsc.send",
    "agents.rsc.read",
}
EXECUTION_SCOPES = {"core.agent.run", "agents.rsc.send", "agents.rsc.read"}
MAX_DEVX_TTL_MINUTES = 15


def _today_key() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("day_%Y%m%d")


def _require_admin(request: Request) -> None:
    token = request.headers.get("x-devx-auth")
    if token != DEVX_ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="DevX admin token required")


def _require_capability(request: Request, user_id: str, scope: str) -> Dict[str, Any]:
    try:
        return require_capability_header(request.headers, user_id=user_id, scope=scope)
    except CapabilityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _infer_agency_level(record: agents.AgentRecord) -> int:
    metadata = record.metadata or {}
    level = metadata.get("agency_level") if isinstance(metadata, dict) else None
    try:
        if level is not None:
            return int(level)
    except (TypeError, ValueError):
        pass
    autonomy = (record.autonomy or "manual").lower()
    if autonomy == "manual":
        return 0
    if autonomy in {"propose", "semi"}:
        return 1
    if autonomy == "auto":
        return 2
    return 1


@router.get("")
async def list_agents() -> Dict[str, Any]:
    summaries: List[Dict[str, Any]] = []
    for record in agents.list_agents():
        state = agents.AgentStateStore(record.user_id).load()
        today_key = _today_key()
        executed_today = int(state.job_counts.get(today_key, 0))
        quota = record.quotas.get("jobs_per_day", 50)
        summaries.append(
            {
                "user_id": record.user_id,
                "agent_id": record.agent_id,
                "status": record.status,
                "autonomy": record.autonomy,
                "quotas": record.quotas,
                "permissions": record.permissions,
                "last_run": state.last_run,
                "next_run": state.next_run,
                "pending_jobs": len(state.pending_jobs),
                "errors": len(state.errors),
                "executed_today": executed_today,
                "quota_remaining": max(quota - executed_today, 0),
            }
        )
    return {"agents": summaries, "count": len(summaries)}


@router.get("/{user_id}")
async def get_agent_detail(user_id: str) -> Dict[str, Any]:
    record = agents.get_agent_record(user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found")

    policy = agents.get_agent_policy(user_id)
    state = agents.AgentStateStore(user_id).load()
    mailbox = agents.AgentMailbox(user_id)
    inbox_entries, inbox_index = mailbox.read_inbox(limit=50, start_index=0)
    outbox_entries, outbox_index = mailbox.read_outbox(limit=50, start_index=0)

    return {
        "record": record.to_dict(),
        "policy": policy.to_dict(),
        "state": state.to_dict(),
        "mailbox": {
            "inbox_count": inbox_index,
            "outbox_count": outbox_index,
            "inbox": inbox_entries[-10:],
            "outbox": outbox_entries[-10:],
        },
    }


@router.post("/{user_id}/run")
async def run_agent(user_id: str, request: Request) -> Dict[str, Any]:
    _require_capability(request, user_id, scope="core.agent.run")
    summary = AgentDaemon().run_once(user_id)
    return summary


@router.post("/{user_id}/autonomy")
async def update_autonomy(user_id: str, request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    _require_capability(request, user_id, scope="core.agent.config")
    autonomy = payload.get("autonomy")
    if autonomy not in {"propose", "semi", "auto"}:
        raise HTTPException(status_code=400, detail="Invalid autonomy value")
    policy = agents.update_agent_policy(user_id, {"autonomy": autonomy})
    agents.update_agent_record(user_id, {"autonomy": autonomy})
    return {"user_id": user_id, "autonomy": policy.autonomy}


@router.post("/{user_id}/status")
async def set_agent_status(user_id: str, request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    _require_capability(request, user_id, scope="core.agent.config")
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"enabled", "disabled"}:
        raise HTTPException(status_code=400, detail="Status must be 'enabled' or 'disabled'")
    record = agents.ensure_agent_record(user_id)
    updated = agents.update_agent_record(user_id, {"status": status})
    return {"user_id": user_id, "agent_id": record.agent_id, "status": updated.status}


@router.get("/{user_id}/mailbox")
async def get_mailbox(
    user_id: str,
    limit: int = Query(20, ge=1, le=200),
) -> Dict[str, Any]:
    if not agents.get_agent_record(user_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    mailbox = agents.AgentMailbox(user_id)
    inbox_entries, inbox_index = mailbox.read_inbox(limit=limit, start_index=0)
    outbox_entries, outbox_index = mailbox.read_outbox(limit=limit, start_index=0)
    return {
        "inbox_count": inbox_index,
        "outbox_count": outbox_index,
        "inbox": inbox_entries[-limit:],
        "outbox": outbox_entries[-limit:],
    }


@router.post("/{user_id}/capability")
async def issue_capability(
    user_id: str,
    request: Request,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    Issue a development capability token for the agent control center.
    Requires header `x-devx-auth`.
    """
    _require_admin(request)
    scope = payload.get("scope")
    if not isinstance(scope, str):
        raise HTTPException(status_code=400, detail="Scope is required")
    ttl_seconds = int(payload.get("ttl_seconds", 900))
    token = generate_token(agent_id=f"hc_{user_id}", scope=scope, user_id=user_id, ttl_seconds=ttl_seconds)
    return {"token": token.token, "payload": token.payload}


class ConfigureAgentRequest(BaseModel):
    level: int
    apply_defaults: bool = True
    confirm: Optional[str] = None


@capability_router.post("/issue")
async def issue_devx_capability(request: Request, payload: DevXCapabilityRequest) -> Dict[str, Any]:
    _require_admin(request)

    user_id = (payload.user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")

    scope = (payload.scope or "").strip()
    if scope not in ALLOWED_DEVX_SCOPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Scope '{scope}' is not permitted")

    ttl = int(payload.ttl_minutes or 1)
    if ttl <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ttl_minutes must be positive")
    if ttl > MAX_DEVX_TTL_MINUTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"ttl_minutes must be <= {MAX_DEVX_TTL_MINUTES}")

    agent_id = (payload.agent_id or f"hc_{user_id}").strip()

    record = agents.get_agent_record(user_id)
    if not record:
        record = agents.ensure_agent_record(user_id)

    agency_level = _infer_agency_level(record)
    if scope in EXECUTION_SCOPES and agency_level <= 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Execution capability denied for manual agents")

    issued = issue_capability_record(
        user_id=user_id,
        scope=scope,
        ttl_minutes=ttl,
        issued_by="devx_api",
        metadata={"requested_by": "devx_api"},
        agent_id=agent_id,
    )

    expires_at = issued.get("expires_at")
    audit_id = issued.get("metadata", {}).get("capability_id") or issued.get("capability_id")

    audit_event(
        "capability_issued_devx",
        {
            "user_id": user_id,
            "agent_id": agent_id,
            "scope": scope,
            "ttl": ttl,
            "audit_id": audit_id,
            "by": "devx_operator",
        },
    )

    return {
        "ok": True,
        "token": issued.get("token"),
        "capability_id": issued.get("capability_id"),
        "scope": scope,
        "ttl_minutes": ttl,
        "expires_at": expires_at,
        "audit_id": audit_id,
    }


class DevXCapabilityRequest(BaseModel):
    user_id: str
    agent_id: Optional[str] = None
    scope: str
    ttl_minutes: int = 5


@user_router.post("/{user_id}/agent/configure")
async def configure_agent_endpoint(user_id: str, request: Request, payload: ConfigureAgentRequest) -> Dict[str, Any]:
    level = int(payload.level)
    if level < 0 or level > max(agent_configurator.AGENCY_PRESETS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agency level.")

    confirm = (payload.confirm or "").strip().lower()
    downgrade_confirmed = confirm == "apply"

    actor = request.headers.get("x-devx-actor", "devx_api")

    try:
        result = agent_configurator.configure_agent(
            user_id.strip(),
            level=level,
            apply_defaults=bool(payload.apply_defaults),
            actor=actor,
            downgrade_confirmed=downgrade_confirmed,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return result


@router.get("/{user_id}/audit")
async def get_agent_audit(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """
    Retrieve agent activity audit log entries.
    Returns the last N entries from the unified agent_activity.jsonl log.
    """
    activity_log = CORE_DATA_ROOT / "telemetry" / "agents" / "agent_activity.jsonl"
    if not activity_log.exists():
        return {"audit": [], "count": 0}

    entries: List[Dict[str, Any]] = []
    with activity_log.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Filter to this user's events
                if entry.get("user_id") == user_id:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    # Return last N entries (most recent)
    tail = entries[-limit:] if len(entries) > limit else entries
    return {"audit": tail, "count": len(tail), "total": len(entries)}
