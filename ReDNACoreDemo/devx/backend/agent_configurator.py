from __future__ import annotations

"""
Agency configuration orchestrator for Head Coach agents.

This module applies preset bundles (policy, schedule, quotas, capabilities,
and metadata) when a DevX operator selects an agency level from the UI.
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from ReDNACoreDemo import agents
from ReDNACoreDemo.core.agent_capabilities import (
    issue_capability_record,
    revoke_capabilities,
)
from ReDNACoreDemo.core.storage import CORE_DATA_ROOT

ISO_FORMAT = "%Y%m%dT%H%M%SZ"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: Optional[datetime] = None) -> str:
    return (dt or _utc_now()).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CapabilityPreset:
    scopes: Sequence[str] = field(default_factory=tuple)
    ttl_minutes: int = 45


@dataclass(frozen=True)
class AgencyPreset:
    level: int
    name: str
    autonomy: str
    schedule_hours: Optional[float]
    quotas: Dict[str, int]
    features: Dict[str, Any] = field(default_factory=dict)
    rsc_enabled: bool = False
    capability: CapabilityPreset = CapabilityPreset()
    workflow_toggles: Dict[str, bool] = field(default_factory=dict)
    notes: Optional[str] = None


AGENCY_PRESETS: Dict[int, AgencyPreset] = {
    0: AgencyPreset(
        level=0,
        name="Manual",
        autonomy="manual",
        schedule_hours=None,
        quotas={"jobs_per_day": 0},
        features={
            "automation": {"enabled": False},
            "consent": {"fail_closed_sensitive": True},
        },
        rsc_enabled=False,
        capability=CapabilityPreset(scopes=(), ttl_minutes=0),
        workflow_toggles={},
        notes="Agent disabled; manual head coach only.",
    ),
    1: AgencyPreset(
        level=1,
        name="Background",
        autonomy="propose",
        schedule_hours=12,
        quotas={"jobs_per_day": 10},
        features={
            "automation": {"enabled": True, "mode": "propose"},
            "consent": {"fail_closed_sensitive": True},
            "refinement": {"auto_accept_threshold": 0.6, "max_risk": "low"},
        },
        rsc_enabled=False,
        capability=CapabilityPreset(scopes=(), ttl_minutes=0),
        workflow_toggles={},
        notes="Background agent proposes work; no persistent capabilities.",
    ),
    2: AgencyPreset(
        level=2,
        name="Autonomous",
        autonomy="auto",
        schedule_hours=4,
        quotas={"jobs_per_day": 50},
        features={
            "automation": {"enabled": True, "mode": "auto"},
            "self_improvement": {"trivial_auto_apply": True},
            "refinement": {"auto_accept_threshold": 0.75, "max_risk": "low"},
            "consent": {"fail_closed_sensitive": True},
        },
        rsc_enabled=False,
        capability=CapabilityPreset(scopes=("core.agent.run", "core.agent.config"), ttl_minutes=45),
        workflow_toggles={},
        notes="Autonomous execution with short-lived capability tokens.",
    ),
    3: AgencyPreset(
        level=3,
        name="Collaborative",
        autonomy="auto",
        schedule_hours=4,
        quotas={"jobs_per_day": 50},
        features={
            "automation": {"enabled": True, "mode": "auto"},
            "self_improvement": {"trivial_auto_apply": True},
            "refinement": {"auto_accept_threshold": 0.75, "max_risk": "low"},
            "rsc": {"collaboration_enabled": True},
        },
        rsc_enabled=True,
        capability=CapabilityPreset(
            scopes=("core.agent.run", "core.agent.config", "agents.rsc.send", "agents.rsc.read"),
            ttl_minutes=45,
        ),
        workflow_toggles={},
        notes="Collaborative mode with RSC enabled.",
    ),
    4: AgencyPreset(
        level=4,
        name="Delegated",
        autonomy="auto",
        schedule_hours=2,
        quotas={"jobs_per_day": 120},
        features={
            "automation": {"enabled": True, "mode": "auto"},
            "self_improvement": {"trivial_auto_apply": True},
            "refinement": {"auto_accept_threshold": 0.75, "max_risk": "low"},
            "rsc": {"collaboration_enabled": True},
            "back_pressure": {"circuit_breaker": {"window_minutes": 15, "max_failures": 3}},
        },
        rsc_enabled=True,
        capability=CapabilityPreset(
            scopes=(
                "core.agent.run",
                "core.agent.config",
                "agents.rsc.send",
                "agents.rsc.read",
                "agents.workflow.calendar",
                "agents.workflow.report",
                "agents.workflow.email",
            ),
            ttl_minutes=30,
        ),
        workflow_toggles={"calendar": True, "report": True, "email": True},
        notes="Delegated operations with workflow toggles and circuit breaker.",
    ),
}


def _activity_log_path() -> Path:
    """Canonical agent activity audit log."""
    path = CORE_DATA_ROOT / "telemetry" / "agents"
    path.mkdir(parents=True, exist_ok=True)
    return path / "agent_activity.jsonl"


def _quarantine_dir(user_id: str) -> Path:
    path = CORE_DATA_ROOT / "quarantine" / "agents" / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _infer_existing_level(record: Optional[agents.AgentRecord]) -> int:
    if not record:
        return 0
    metadata = record.metadata or {}
    if isinstance(metadata, dict):
        level = metadata.get("agency_level")
        try:
            return int(level)
        except (TypeError, ValueError):
            pass
        if metadata.get("workflow_toggles", {}).get("calendar"):
            return 4
        if metadata.get("rsc_enabled"):
            return 3
    if record.status == "disabled":
        return 0
    if record.autonomy == "auto":
        return 2
    if record.autonomy in {"semi", "propose"}:
        return 1
    return 0


def _archive_state(state_path: Path, dest_dir: Path) -> Optional[Path]:
    if not state_path.exists():
        return None
    timestamp = _utc_now().strftime(ISO_FORMAT)
    target = dest_dir / f"state_{timestamp}.json"
    shutil.copy2(state_path, target)
    return target


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def configure_agent(
    user_id: str,
    *,
    level: int,
    apply_defaults: bool,
    actor: str = "devx_ui",
    downgrade_confirmed: bool = False,
) -> Dict[str, Any]:
    if level not in AGENCY_PRESETS:
        raise ValueError(f"Invalid agency level {level}")

    preset = AGENCY_PRESETS[level]
    sanitized = str(user_id or "").strip()
    if not sanitized:
        raise ValueError("user_id is required")

    existing_record = agents.get_agent_record(sanitized)
    old_level = _infer_existing_level(existing_record)

    if existing_record is None and level == 0:
        # No record exists and manual level requested; nothing to configure.
        # Create a placeholder record to ensure policy/state helpers work.
        existing_record = agents.ensure_agent_record(sanitized, autonomy="manual")

    record = existing_record or agents.ensure_agent_record(sanitized)

    if level < old_level and not downgrade_confirmed:
        raise PermissionError("Downgrade requires confirmation.")

    policy_before = agents.get_agent_policy(sanitized)
    policy_before_dict = policy_before.to_dict()

    revoked_tokens = revoke_capabilities(
        sanitized,
        reason=f"agency_level_{old_level}_to_{level}",
    )

    policy_changes: Dict[str, Any] = {}
    if preset.autonomy == "manual":
        policy_changes["autonomy"] = "manual"
    else:
        policy_changes["autonomy"] = preset.autonomy

    if apply_defaults:
        policy_changes["quotas"] = dict(preset.quotas)
        if preset.features:
            policy_changes["features"] = dict(preset.features)
    else:
        if preset.features:
            # Merge without overwriting existing custom flags
            merged = dict(policy_before.features)
            merged.update(preset.features)
            policy_changes["features"] = merged

    updated_policy = agents.update_agent_policy(sanitized, policy_changes)

    metadata = dict(record.metadata or {})
    metadata.update(
        {
            "agency_level": level,
            "agency_level_name": preset.name,
            "preset_applied_at": _utc_iso(),
            "rsc_enabled": preset.rsc_enabled,
            "schedule": {"interval_hours": preset.schedule_hours} if preset.schedule_hours else None,
        }
    )
    if preset.workflow_toggles:
        metadata["workflow_toggles"] = dict(preset.workflow_toggles)

    if preset.notes:
        metadata["preset_notes"] = preset.notes

    record_updates: Dict[str, Any] = {
        "autonomy": preset.autonomy,
        "status": "enabled" if level > 0 else "disabled",
        "metadata": metadata,
    }
    if apply_defaults:
        record_updates["quotas"] = dict(preset.quotas)

    updated_record = agents.update_agent_record(sanitized, record_updates)

    state_store = agents.AgentStateStore(sanitized)
    state = state_store.load()

    archived_state_path: Optional[str] = None
    if level == 0:
        archived = _archive_state(state_store.runtime_path, _quarantine_dir(sanitized))
        if not archived:
            archived = _archive_state(state_store.template_path, _quarantine_dir(sanitized))
        if archived:
            archived_state_path = str(archived)
        state_store.update(status="idle", next_run=None, pending_jobs=[], inbox_cursor=0, outbox_cursor=state.outbox_cursor)
    else:
        if preset.schedule_hours:
            minutes = max(int(preset.schedule_hours * 60), 1)
            state_store.touch_next_run(minutes)
        state_store.update(status="scheduled" if preset.autonomy != "manual" else "idle")

    issued_tokens: List[Dict[str, Any]] = []
    if preset.capability.scopes and preset.capability.ttl_minutes > 0 and level > 1:
        for scope in preset.capability.scopes:
            issued = issue_capability_record(
                sanitized,
                scope,
                ttl_minutes=preset.capability.ttl_minutes,
                issued_by=f"preset_level_{level}",
                metadata={"preset_level": level, "preset_name": preset.name},
            )
            issued_tokens.append(issued)

    policy_after_dict = updated_policy.to_dict()

    changes: Dict[str, Any] = {
        "autonomy": {"from": policy_before_dict.get("autonomy"), "to": policy_after_dict.get("autonomy")},
        "quotas": {"from": policy_before_dict.get("quotas"), "to": policy_after_dict.get("quotas")},
        "features": {"from": policy_before_dict.get("features"), "to": policy_after_dict.get("features")},
        "schedule": {
            "from": (record.metadata or {}).get("schedule") if record.metadata else None,
            "to": metadata.get("schedule"),
        },
        "rsc_enabled": {"from": (record.metadata or {}).get("rsc_enabled") if record.metadata else False, "to": preset.rsc_enabled},
    }

    audit_id = uuid4().hex
    audit_event = {
        "audit_id": audit_id,
        "event": "agent_configured",
        "timestamp": _utc_iso(),
        "user_id": sanitized,
        "agent_id": updated_record.agent_id,
        "old_level": old_level,
        "new_level": level,
        "by": actor,
        "changes": changes,
        "revoked_capabilities": [item.get("capability_id") for item in revoked_tokens],
        "issued_capabilities": [item.get("capability_id") for item in issued_tokens],
    }
    _append_jsonl(_activity_log_path(), audit_event)

    schedule_payload = metadata.get("schedule") or {}
    return {
        "ok": True,
        "user_id": sanitized,
        "agent_level": level,
        "agent_id": updated_record.agent_id,
        "policy": policy_after_dict,
        "schedule": schedule_payload,
        "quotas": updated_policy.quotas,
        "capabilities": {"issued": issued_tokens, "revoked": revoked_tokens},
        "rsc_enabled": preset.rsc_enabled,
        "workflow_toggles": metadata.get("workflow_toggles", {}),
        "audit_id": audit_id,
        "archived_state": archived_state_path,
    }
