from __future__ import annotations

"""
Agent registry persistence helpers.

The registry keeps a canonical list of per-user Head Coach agents along with
their autonomy configuration, quotas, and permissions. The backing store is a
simple JSON file committed to the repository so new environments bootstrap with
the expected agents. Runtime mutations are safe because writes are serialized
through an in-process lock; callers should treat the helpers as the single entry
point for registry access.
"""

import json
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


AGENTS_ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = AGENTS_ROOT / "registry.json"
REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

_REGISTRY_LOCK = threading.Lock()

VALID_AUTONOMY = {"manual", "propose", "semi", "auto"}
DEFAULT_NAMESPACES = ["SkillDNA", "Career", "Core"]
DEFAULT_SENSITIVE = ["PsyDNA", "PaDNA"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_namespaces(namespaces: Optional[Iterable[str]]) -> List[str]:
    result: List[str] = []
    if namespaces:
        for item in namespaces:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if item:
                result.append(item)
    return result


@dataclass
class AgentRecord:
    user_id: str
    agent_id: str
    status: str = "enabled"
    autonomy: str = "semi"
    quotas: Dict[str, int] = field(default_factory=lambda: {"jobs_per_day": 50})
    permissions: Dict[str, Any] = field(
        default_factory=lambda: {"namespaces": list(DEFAULT_NAMESPACES), "sensitive": list(DEFAULT_SENSITIVE)}
    )
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["permissions"] = {
            "namespaces": list(self.permissions.get("namespaces", [])),
            "sensitive": list(self.permissions.get("sensitive", [])),
        }
        payload["quotas"] = dict(self.quotas)
        payload["metadata"] = dict(self.metadata)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AgentRecord":
        user_id = str(payload.get("user_id") or "").strip()
        agent_id = str(payload.get("agent_id") or "").strip()
        if not user_id or not agent_id:
            raise ValueError("Agent record requires user_id and agent_id")

        status = str(payload.get("status") or "enabled")
        raw_autonomy = payload.get("autonomy")
        if raw_autonomy is None:
            autonomy = "manual"
        else:
            autonomy = str(raw_autonomy).lower()
            if autonomy not in VALID_AUTONOMY:
                autonomy = "semi"

        quotas = payload.get("quotas") or {}
        if not isinstance(quotas, dict):
            quotas = {}
        normalized_quotas: Dict[str, int] = {}
        for key, value in quotas.items():
            try:
                normalized_quotas[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        if "jobs_per_day" not in normalized_quotas:
            normalized_quotas["jobs_per_day"] = 50

        permissions = payload.get("permissions") or {}
        if not isinstance(permissions, dict):
            permissions = {}
        namespaces = _coerce_namespaces(permissions.get("namespaces"))
        sensitive = _coerce_namespaces(permissions.get("sensitive"))
        if not namespaces:
            namespaces = list(DEFAULT_NAMESPACES)
        if not sensitive:
            sensitive = list(DEFAULT_SENSITIVE)

        created_at = str(payload.get("created_at") or _utc_now())
        updated_at = str(payload.get("updated_at") or created_at)

        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            user_id=user_id,
            agent_id=agent_id,
            status=status,
            autonomy=autonomy,
            quotas=normalized_quotas,
            permissions={"namespaces": namespaces, "sensitive": sensitive},
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata,
        )


def _load_raw() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"agents": [], "updated_at": None}
    try:
        with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                return payload
    except json.JSONDecodeError:
        pass
    return {"agents": [], "updated_at": None}


def _write_raw(payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload["updated_at"] = _utc_now()
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def list_agents() -> List[AgentRecord]:
    raw = _load_raw()
    records: List[AgentRecord] = []
    for entry in raw.get("agents", []):
        if isinstance(entry, dict):
            try:
                records.append(AgentRecord.from_dict(entry))
            except ValueError:
                continue
    records.sort(key=lambda record: record.user_id)
    return records


def get_agent_record(user_id: str) -> Optional[AgentRecord]:
    user_id = str(user_id or "").strip()
    if not user_id:
        return None
    for record in list_agents():
        if record.user_id == user_id:
            return record
    return None


def save_agent_records(records: List[AgentRecord]) -> None:
    serializable = [record.to_dict() for record in records]
    _write_raw({"agents": serializable})


def ensure_agent_record(user_id: str, *, autonomy: Optional[str] = None) -> AgentRecord:
    """
    Ensure an agent record exists for the given user.

    Returns the existing record if present, or creates a new one with defaults.
    """
    user_id = str(user_id or "").strip()
    if not user_id:
        raise ValueError("user_id is required")

    with _REGISTRY_LOCK:
        existing = get_agent_record(user_id)
        if existing:
            return existing

        agent_id = f"hc_{user_id}"
        if autonomy is None:
            autonomy_value = "manual"
        else:
            autonomy_value = str(autonomy).lower()
            if autonomy_value not in VALID_AUTONOMY:
                autonomy_value = "semi"

        record = AgentRecord(
            user_id=user_id,
            agent_id=agent_id,
            autonomy=autonomy_value,
        )

        records = list_agents()
        records.append(record)
        records.sort(key=lambda item: item.user_id)
        save_agent_records(records)
        return record


def update_agent_record(user_id: str, updates: Dict[str, Any]) -> AgentRecord:
    """
    Update an agent record with the provided changes.

    Supported fields: status, autonomy, quotas, permissions, metadata.
    """
    if not isinstance(updates, dict):
        raise ValueError("updates must be a dict")

    user_id = str(user_id or "").strip()
    if not user_id:
        raise ValueError("user_id is required")

    with _REGISTRY_LOCK:
        records = list_agents()
        updated: Optional[AgentRecord] = None
        for idx, record in enumerate(records):
            if record.user_id != user_id:
                continue

            status = updates.get("status", record.status)
            autonomy = updates.get("autonomy", record.autonomy)
            quotas = updates.get("quotas", record.quotas)
            permissions = updates.get("permissions", record.permissions)
            metadata = updates.get("metadata", record.metadata)

            if autonomy is None:
                new_autonomy = "manual"
            else:
                new_autonomy = str(autonomy or record.autonomy).lower()
                if new_autonomy not in VALID_AUTONOMY:
                    new_autonomy = record.autonomy

            new_status = str(status or record.status)

            normalized_quotas: Dict[str, int] = {}
            if isinstance(quotas, dict):
                for key, value in quotas.items():
                    try:
                        normalized_quotas[str(key)] = int(value)
                    except (TypeError, ValueError):
                        continue
            if "jobs_per_day" not in normalized_quotas:
                normalized_quotas["jobs_per_day"] = record.quotas.get("jobs_per_day", 50)

            normalized_permissions = record.permissions
            if isinstance(permissions, dict):
                namespaces = _coerce_namespaces(permissions.get("namespaces"))
                sensitive = _coerce_namespaces(permissions.get("sensitive"))
                if namespaces:
                    normalized_permissions = dict(normalized_permissions)
                    normalized_permissions["namespaces"] = namespaces
                if sensitive:
                    normalized_permissions = dict(normalized_permissions)
                    normalized_permissions["sensitive"] = sensitive

            normalized_metadata: Dict[str, Any] = record.metadata
            if isinstance(metadata, dict):
                normalized_metadata = dict(metadata)

            updated = AgentRecord(
                user_id=record.user_id,
                agent_id=record.agent_id,
                status=new_status,
                autonomy=new_autonomy,
                quotas=normalized_quotas,
                permissions=normalized_permissions,
                created_at=record.created_at,
                updated_at=_utc_now(),
                metadata=normalized_metadata,
            )
            records[idx] = updated
            break

        if not updated:
            raise KeyError(f"No agent record for user_id={user_id}")

        save_agent_records(records)
        return updated


def upsert_agent_record(payload: Dict[str, Any]) -> AgentRecord:
    """
    Add or update an agent record from a payload dictionary.
    """
    candidate = AgentRecord.from_dict(payload)
    with _REGISTRY_LOCK:
        records = list_agents()
        for idx, record in enumerate(records):
            if record.user_id == candidate.user_id:
                candidate.created_at = record.created_at
                candidate.updated_at = _utc_now()
                records[idx] = candidate
                save_agent_records(records)
                return candidate

        records.append(candidate)
        records.sort(key=lambda item: item.user_id)
        save_agent_records(records)
        return candidate
