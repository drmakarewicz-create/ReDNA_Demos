from __future__ import annotations

"""
Agent state persistence helpers.

Runtime state for the Head Coach agent is stored under the user's workspace
(`data/users/<id>/agent/state.json`). We also maintain a mirrored copy inside
`ReDNACoreDemo/agents/state` so repos retain a snapshot of the latest state for
sandbox demos. Callers should use AgentStateStore to interact with the files.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .registry import AGENTS_ROOT, ensure_agent_record

try:
    from ReDNACoreDemo.core.storage import ensure_dirs_for_user  # pragma: no cover
except ImportError:  # pragma: no cover - tests can stub storage
    def ensure_dirs_for_user(user_id: str) -> Dict[str, Path]:
        path = Path("data/users") / user_id
        path.mkdir(parents=True, exist_ok=True)
        return {"udir": path}


STATE_TEMPLATE_DIR = AGENTS_ROOT / "state"
STATE_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class AgentState:
    user_id: str
    agent_id: str
    status: str = "idle"
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    pending_jobs: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    inbox_cursor: int = 0
    outbox_cursor: int = 0
    run_count: int = 0
    job_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["pending_jobs"] = list(self.pending_jobs)
        payload["errors"] = list(self.errors)
        payload["job_counts"] = dict(self.job_counts)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AgentState":
        user_id = str(payload.get("user_id") or "").strip()
        agent_id = str(payload.get("agent_id") or "").strip()
        if not user_id or not agent_id:
            raise ValueError("Agent state requires user_id and agent_id")

        pending_jobs = payload.get("pending_jobs") or []
        if not isinstance(pending_jobs, list):
            pending_jobs = []

        errors = payload.get("errors") or []
        if not isinstance(errors, list):
            errors = []

        job_counts = payload.get("job_counts") or {}
        if not isinstance(job_counts, dict):
            job_counts = {}

        return cls(
            user_id=user_id,
            agent_id=agent_id,
            status=str(payload.get("status") or "idle"),
            last_run=payload.get("last_run"),
            next_run=payload.get("next_run"),
            pending_jobs=pending_jobs,
            errors=errors,
            inbox_cursor=int(payload.get("inbox_cursor") or 0),
            outbox_cursor=int(payload.get("outbox_cursor") or 0),
            run_count=int(payload.get("run_count") or 0),
            job_counts={str(k): int(v) for k, v in job_counts.items() if isinstance(k, str)},
        )

    def register_job(self, job: Dict[str, Any]) -> None:
        """Add or update a job in pending_jobs."""
        job_id = str(job.get("job_id") or "").strip()
        existing_index = None
        for idx, item in enumerate(self.pending_jobs):
            if isinstance(item, dict) and item.get("job_id") == job_id and job_id:
                existing_index = idx
                break
        job_payload = dict(job)
        if "status" not in job_payload:
            job_payload["status"] = "queued"
        if "queued_at" not in job_payload:
            job_payload["queued_at"] = _utc_now()
        if existing_index is None:
            self.pending_jobs.append(job_payload)
        else:
            self.pending_jobs[existing_index] = job_payload

    def mark_job(self, job_id: str, *, status: str, result: Optional[Dict[str, Any]] = None) -> None:
        for item in self.pending_jobs:
            if isinstance(item, dict) and item.get("job_id") == job_id:
                item["status"] = status
                if result is not None:
                    item["result"] = result
                item["completed_at"] = _utc_now()
                break

    def record_error(self, error: Dict[str, Any], limit: int = 20) -> None:
        error_payload = dict(error)
        error_payload.setdefault("timestamp", _utc_now())
        self.errors.append(error_payload)
        if len(self.errors) > limit:
            self.errors = self.errors[-limit:]

    def increment_job_count(self, kind: str) -> None:
        key = str(kind or "unknown")
        self.job_counts[key] = int(self.job_counts.get(key, 0)) + 1


class AgentStateStore:
    def __init__(self, user_id: str):
        record = ensure_agent_record(user_id)
        self.user_id = record.user_id
        self.agent_id = record.agent_id
        self.runtime_dir = self._ensure_runtime_dir()
        self.runtime_path = self.runtime_dir / "state.json"
        self.template_path = STATE_TEMPLATE_DIR / f"hc_{self.user_id}.json"

    def _ensure_runtime_dir(self) -> Path:
        paths = ensure_dirs_for_user(self.user_id)
        user_dir = paths.get("udir") or Path("data/users") / self.user_id
        agent_dir = Path(user_dir) / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir

    def load(self) -> AgentState:
        for path in (self.runtime_path, self.template_path):
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        return AgentState.from_dict(payload)
                except json.JSONDecodeError:
                    continue
        # Fallback to default state
        state = AgentState(user_id=self.user_id, agent_id=self.agent_id)
        self.save(state)
        return state

    def save(self, state: AgentState) -> None:
        payload = state.to_dict()
        payload["updated_at"] = _utc_now()
        self.runtime_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.template_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def update(self, **fields: Any) -> AgentState:
        state = self.load()
        for key, value in fields.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self.save(state)
        return state

    def touch_next_run(self, minutes: int) -> AgentState:
        state = self.load()
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(minutes=minutes)
        state.next_run = next_run.isoformat().replace("+00:00", "Z")
        self.save(state)
        return state
