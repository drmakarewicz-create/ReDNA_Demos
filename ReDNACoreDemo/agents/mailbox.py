from __future__ import annotations

"""
Mailbox helpers for Head Coach agents.

Inbox/outbox messages are persisted as newline-delimited JSON records inside the
user's agent directory (`data/users/<id>/agent`). The AgentMailbox helper
handles serialization and cursor management.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from .registry import ensure_agent_record

try:
    from ReDNACoreDemo.core.storage import ensure_dirs_for_user  # pragma: no cover
except ImportError:  # pragma: no cover - tests may provide stub
    def ensure_dirs_for_user(user_id: str) -> Dict[str, Path]:
        path = Path("data/users") / user_id
        path.mkdir(parents=True, exist_ok=True)
        return {"udir": path}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Mailbox:
    inbox: Path
    outbox: Path


class AgentMailbox:
    def __init__(self, user_id: str):
        record = ensure_agent_record(user_id)
        self.user_id = record.user_id
        self.agent_id = record.agent_id
        base_dir = self._ensure_agent_dir()
        self.mailbox = Mailbox(
            inbox=base_dir / "inbox.jsonl",
            outbox=base_dir / "outbox.jsonl",
        )
        for path in (self.mailbox.inbox, self.mailbox.outbox):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

    def _ensure_agent_dir(self) -> Path:
        paths = ensure_dirs_for_user(self.user_id)
        user_dir = paths.get("udir") or Path("data/users") / self.user_id
        agent_dir = Path(user_dir) / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir

    def append_inbox(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = dict(payload)
        message.setdefault("job_id", f"{self.agent_id}-{uuid4().hex}")
        message.setdefault("agent_id", self.agent_id)
        message.setdefault("user_id", self.user_id)
        message.setdefault("queued_at", _utc_now())
        self._append(self.mailbox.inbox, message)
        return message

    def append_outbox(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = dict(payload)
        message.setdefault("agent_id", self.agent_id)
        message.setdefault("user_id", self.user_id)
        message.setdefault("emitted_at", _utc_now())
        self._append(self.mailbox.outbox, message)
        return message

    def read_inbox(self, *, limit: Optional[int] = None, start_index: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        return self._read(self.mailbox.inbox, limit=limit, start_index=start_index)

    def read_outbox(self, *, limit: Optional[int] = None, start_index: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        return self._read(self.mailbox.outbox, limit=limit, start_index=start_index)

    def _append(self, path: Path, payload: Dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")

    def _read(self, path: Path, *, limit: Optional[int], start_index: int) -> Tuple[List[Dict[str, Any]], int]:
        entries: List[Dict[str, Any]] = []
        next_index = start_index
        if not path.exists():
            return entries, next_index

        with path.open("r", encoding="utf-8") as handle:
            for idx, line in enumerate(handle):
                next_index = idx + 1
                if idx < start_index:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    entries.append(payload)
                if limit is not None and len(entries) >= limit:
                    break
        return entries, next_index
