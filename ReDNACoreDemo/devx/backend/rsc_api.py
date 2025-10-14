from __future__ import annotations

"""
DevX API endpoints for RSC (Remote Sentient Collaboration) messaging.

Enables Head Coach agents to invite, accept/decline, exchange briefs,
and close collaboration threads under policy and consent constraints.
"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Body, HTTPException, Query, status, Request
from pathlib import Path
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ReDNACoreDemo import agents
from ReDNACoreDemo.agents.messages import RSCMessage, RSCMessageStore, send_message, MessageType
from ReDNACoreDemo.agents.policy import can_send_rsc_message, can_receive_rsc_message, get_agent_policy
from ReDNACoreDemo.core.storage import CORE_DATA_ROOT
from ReDNACoreDemo.core.agent_capabilities import require_capability_header, CapabilityError, ensure_consent, ConsentDeniedError


router = APIRouter(prefix="/devx/api/agents/rsc", tags=["rsc"])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _activity_log_path() -> Path:
    """Canonical agent activity audit log."""
    path = CORE_DATA_ROOT / "telemetry" / "agents"
    path.mkdir(parents=True, exist_ok=True)
    return path / "agent_activity.jsonl"


def _append_audit(event: str, payload: Dict[str, Any]) -> None:
    """Append audit entry to unified activity log."""
    data = dict(payload)
    data["event"] = event
    data.setdefault("timestamp", _utc_iso())
    line = json.dumps(data, ensure_ascii=False)
    with _activity_log_path().open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


class SendMessageRequest(BaseModel):
    from_user: str
    to_user: str
    type: MessageType
    topic: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = None
    ttl_seconds: int = 86400
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None


class ActOnMessageRequest(BaseModel):
    message_id: str
    action: str  # accept, decline, close
    payload: Optional[Dict[str, Any]] = None


@router.post("/send")
async def send_rsc_message(request: Request, req: SendMessageRequest) -> Dict[str, Any]:
    """
    Send an RSC message between agents.

    Validates:
    - Both agents' RSC policies (enabled, allow/deny lists)
    - Sender/recipient consent for sensitive namespaces
    - Capability scopes: agents.rsc.send

    Enqueues to recipient's inbox, echoes to sender's sent box.
    """
    from_user = req.from_user.strip()
    to_user = req.to_user.strip()

    if not from_user or not to_user:
        raise HTTPException(status_code=400, detail="from_user and to_user are required")

    if from_user == to_user:
        raise HTTPException(status_code=400, detail="Cannot send message to self")

    from_agent_id = f"hc_{from_user}"
    to_agent_id = f"hc_{to_user}"

    try:
        require_capability_header(request.headers, user_id=from_user, scope="agents.rsc.send")
    except CapabilityError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    # Load policies
    try:
        from_policy = get_agent_policy(from_user)
        to_policy = get_agent_policy(to_user)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Policy not found: {exc}") from exc

    # Check sender policy
    can_send, send_reason = can_send_rsc_message(from_policy, to_agent_id)
    if not can_send:
        _append_audit(
            "rsc_invite_denied",
            {
                "from_user": from_user,
                "to_user": to_user,
                "reason": send_reason,
                "stage": "sender_policy",
            },
        )
        raise HTTPException(
            status_code=403,
            detail=f"Sender policy denies RSC message: {send_reason}",
        )

    # Check recipient policy
    can_receive, receive_reason = can_receive_rsc_message(to_policy, from_agent_id)
    if not can_receive:
        _append_audit(
            "rsc_invite_denied",
            {
                "from_user": from_user,
                "to_user": to_user,
                "reason": receive_reason,
                "stage": "recipient_policy",
            },
        )
        raise HTTPException(
            status_code=403,
            detail=f"Recipient policy denies RSC message: {receive_reason}",
        )

    namespaces = []
    if req.constraints and isinstance(req.constraints, dict):
        namespaces = list(req.constraints.get("namespaces") or [])
    if namespaces:
        try:
            ensure_consent(from_user, namespaces, action="read")
            ensure_consent(to_user, namespaces, action="read")
        except ConsentDeniedError as exc:
            _append_audit(
                "rsc_invite_denied",
                {
                    "from_user": from_user,
                    "to_user": to_user,
                    "reason": str(exc),
                    "stage": "consent",
                },
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    # Send message
    try:
        message = send_message(
            from_user_id=from_user,
            to_user_id=to_user,
            message_type=req.type,
            topic=req.topic,
            constraints=req.constraints,
            policy=req.policy,
            payload=req.payload,
            ttl_seconds=req.ttl_seconds,
            thread_id=req.thread_id,
            in_reply_to=req.in_reply_to,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {exc}") from exc

    # Audit
    _append_audit(
        f"rsc_{req.type}_sent",
        {
            "message_id": message.id,
            "from_user": from_user,
            "to_user": to_user,
            "type": req.type,
            "topic": req.topic,
            "thread_id": message.thread_id,
        },
    )

    return {
        "ok": True,
        "message": message.to_dict(),
    }


@router.get("/{user_id}/inbox")
async def get_inbox(
    request: Request,
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    message_type: Optional[str] = Query(None),
    thread_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    try:
        require_capability_header(request.headers, user_id=user_id, scope="agents.rsc.read")
    except CapabilityError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    """Retrieve RSC inbox for a user."""
    store = RSCMessageStore(user_id)

    try:
        msg_type = MessageType(message_type) if message_type else None
    except ValueError:
        msg_type = None

    messages = store.read_inbox(
        limit=limit,
        message_type=msg_type,
        thread_id=thread_id,
        include_expired=False,
    )

    return {
        "inbox": [m.to_dict() for m in messages],
        "count": len(messages),
    }


@router.get("/{user_id}/sent")
async def get_sent(
    request: Request,
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    message_type: Optional[str] = Query(None),
    thread_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    try:
        require_capability_header(request.headers, user_id=user_id, scope="agents.rsc.read")
    except CapabilityError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    """Retrieve RSC sent messages for a user."""
    store = RSCMessageStore(user_id)

    try:
        msg_type = MessageType(message_type) if message_type else None
    except ValueError:
        msg_type = None

    messages = store.read_sent(
        limit=limit,
        message_type=msg_type,
        thread_id=thread_id,
    )

    return {
        "sent": [m.to_dict() for m in messages],
        "count": len(messages),
    }


@router.post("/{user_id}/act")
async def act_on_message(user_id: str, req: ActOnMessageRequest) -> Dict[str, Any]:
    """
    Act on an RSC message (accept, decline, close).

    Writes corresponding response message back to partner and audits.
    """
    action = req.action.lower()
    if action not in {"accept", "decline", "close"}:
        raise HTTPException(status_code=400, detail="Invalid action")

    store = RSCMessageStore(user_id)
    message = store.find_message(req.message_id)

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Determine partner user_id
    from_agent = message.from_agent
    to_agent = message.to_agent
    current_agent = f"hc_{user_id}"

    if current_agent == to_agent:
        # We're the recipient, reply to sender
        partner_agent = from_agent
    elif current_agent == from_agent:
        # We're the sender, reply to recipient (for close)
        partner_agent = to_agent
    else:
        raise HTTPException(status_code=403, detail="Not a participant in this thread")

    # Extract partner user_id
    if partner_agent.startswith("hc_"):
        partner_user_id = partner_agent[3:]
    else:
        raise HTTPException(status_code=400, detail="Invalid partner agent ID")

    # Map action to response type
    response_type: MessageType
    if action == "accept":
        response_type = "rsc_accept"
    elif action == "decline":
        response_type = "rsc_decline"
    else:  # close
        response_type = "rsc_close"

    # Send response
    try:
        response = send_message(
            from_user_id=user_id,
            to_user_id=partner_user_id,
            message_type=response_type,
            topic=message.topic,
            thread_id=message.thread_id,
            in_reply_to=message.id,
            payload=req.payload or {},
            ttl_seconds=message.ttl_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send response: {exc}") from exc

    # Audit
    _append_audit(
        f"rsc_{action}",
        {
            "user_id": user_id,
            "message_id": req.message_id,
            "response_id": response.id,
            "partner_user": partner_user_id,
            "thread_id": message.thread_id,
            "action": action,
        },
    )

    return {
        "ok": True,
        "action": action,
        "response": response.to_dict(),
    }
