from __future__ import annotations

"""
RSC (Remote Sentient Collaboration) message schema and storage.

Messages enable Head Coach agents to invite, accept/decline, exchange briefs,
and close collaboration threads under policy and consent constraints.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from ReDNACoreDemo.core.storage import CORE_DATA_ROOT


MessageType = Literal["rsc_invite", "rsc_accept", "rsc_decline", "rsc_brief", "rsc_close"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: Optional[datetime] = None) -> str:
    return (dt or _utc_now()).isoformat().replace("+00:00", "Z")


@dataclass
class RSCMessage:
    """Base RSC message structure."""

    id: str
    type: MessageType
    from_agent: str
    to_agent: str
    timestamp: str
    ttl_seconds: int = 86400  # 24 hours default

    # Optional fields
    topic: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    policy: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Thread tracking
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None

    @classmethod
    def create(
        cls,
        message_type: MessageType,
        from_agent: str,
        to_agent: str,
        *,
        topic: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        policy: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 86400,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> RSCMessage:
        """Create a new RSC message with auto-generated ID and timestamp."""
        message_id = uuid4().hex
        timestamp = _utc_iso()

        # Auto-generate thread_id for invites
        if message_type == "rsc_invite" and not thread_id:
            thread_id = f"thread_{message_id[:12]}"

        return cls(
            id=message_id,
            type=message_type,
            from_agent=from_agent,
            to_agent=to_agent,
            timestamp=timestamp,
            ttl_seconds=ttl_seconds,
            topic=topic,
            constraints=constraints or {},
            policy=policy or {},
            payload=payload or {},
            metadata=metadata or {},
            thread_id=thread_id,
            in_reply_to=in_reply_to,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "from": self.from_agent,
            "to": self.to_agent,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "topic": self.topic,
            "constraints": self.constraints,
            "policy": self.policy,
            "payload": self.payload,
            "metadata": self.metadata,
            "thread_id": self.thread_id,
            "in_reply_to": self.in_reply_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RSCMessage:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            type=data["type"],
            from_agent=data.get("from") or data.get("from_agent", ""),
            to_agent=data.get("to") or data.get("to_agent", ""),
            timestamp=data["timestamp"],
            ttl_seconds=data.get("ttl_seconds", 86400),
            topic=data.get("topic"),
            constraints=data.get("constraints", {}),
            policy=data.get("policy", {}),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            thread_id=data.get("thread_id"),
            in_reply_to=data.get("in_reply_to"),
        )

    def is_expired(self) -> bool:
        """Check if message has exceeded TTL."""
        try:
            ts = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            age_seconds = (_utc_now() - ts).total_seconds()
            return age_seconds > self.ttl_seconds
        except (ValueError, TypeError):
            return False

    def get_expiry(self) -> Optional[str]:
        """Calculate expiry timestamp."""
        try:
            from datetime import timedelta
            ts = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            expiry = ts + timedelta(seconds=self.ttl_seconds)
            return expiry.isoformat().replace("+00:00", "Z")
        except (ValueError, TypeError):
            return None


class RSCMessageStore:
    """Storage for RSC messages (inbox and sent)."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.base_path = CORE_DATA_ROOT / "users" / user_id / "agent"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.inbox_path = self.base_path / "rsc_inbox.jsonl"
        self.sent_path = self.base_path / "rsc_sent.jsonl"

    def append_inbox(self, message: RSCMessage) -> None:
        """Append message to inbox."""
        self._append_jsonl(self.inbox_path, message.to_dict())

    def append_sent(self, message: RSCMessage) -> None:
        """Append message to sent box."""
        self._append_jsonl(self.sent_path, message.to_dict())

    def read_inbox(
        self,
        *,
        limit: Optional[int] = None,
        message_type: Optional[MessageType] = None,
        thread_id: Optional[str] = None,
        include_expired: bool = False,
    ) -> List[RSCMessage]:
        """Read messages from inbox with optional filtering."""
        messages = self._read_jsonl(self.inbox_path)

        # Filter
        if message_type:
            messages = [m for m in messages if m.type == message_type]
        if thread_id:
            messages = [m for m in messages if m.thread_id == thread_id]
        if not include_expired:
            messages = [m for m in messages if not m.is_expired()]

        # Sort by timestamp descending (newest first)
        messages.sort(key=lambda m: m.timestamp, reverse=True)

        if limit:
            messages = messages[:limit]

        return messages

    def read_sent(
        self,
        *,
        limit: Optional[int] = None,
        message_type: Optional[MessageType] = None,
        thread_id: Optional[str] = None,
    ) -> List[RSCMessage]:
        """Read messages from sent box with optional filtering."""
        messages = self._read_jsonl(self.sent_path)

        # Filter
        if message_type:
            messages = [m for m in messages if m.type == message_type]
        if thread_id:
            messages = [m for m in messages if m.thread_id == thread_id]

        # Sort by timestamp descending (newest first)
        messages.sort(key=lambda m: m.timestamp, reverse=True)

        if limit:
            messages = messages[:limit]

        return messages

    def find_message(self, message_id: str) -> Optional[RSCMessage]:
        """Find a message by ID in inbox or sent."""
        # Check inbox first
        for msg in self._read_jsonl(self.inbox_path):
            if msg.id == message_id:
                return msg

        # Check sent
        for msg in self._read_jsonl(self.sent_path):
            if msg.id == message_id:
                return msg

        return None

    def _read_jsonl(self, path: Path) -> List[RSCMessage]:
        """Read all messages from a JSONL file."""
        if not path.exists():
            return []

        messages: List[RSCMessage] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    messages.append(RSCMessage.from_dict(data))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        return messages

    def _append_jsonl(self, path: Path, data: Dict[str, Any]) -> None:
        """Append a JSON line to file."""
        line = json.dumps(data, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def send_message(
    from_user_id: str,
    to_user_id: str,
    message_type: MessageType,
    *,
    topic: Optional[str] = None,
    constraints: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = 86400,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
) -> RSCMessage:
    """
    Send an RSC message from one agent to another.

    Writes to sender's sent box and recipient's inbox.
    Returns the created message.
    """
    from_agent = f"hc_{from_user_id}"
    to_agent = f"hc_{to_user_id}"

    message = RSCMessage.create(
        message_type=message_type,
        from_agent=from_agent,
        to_agent=to_agent,
        topic=topic,
        constraints=constraints,
        policy=policy,
        payload=payload,
        metadata=metadata,
        ttl_seconds=ttl_seconds,
        thread_id=thread_id,
        in_reply_to=in_reply_to,
    )

    # Append to sender's sent box
    sender_store = RSCMessageStore(from_user_id)
    sender_store.append_sent(message)

    # Append to recipient's inbox
    recipient_store = RSCMessageStore(to_user_id)
    recipient_store.append_inbox(message)

    return message
