from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict

import pytest

from ReDNACoreDemo import agents
from ReDNACoreDemo.core import agent_daemon as agent_daemon_module
from ReDNACoreDemo.core import agent_triggers as agent_triggers_module
from ReDNACoreDemo.core import agent_capabilities


@pytest.fixture
def trigger_env(tmp_path, monkeypatch):
    sandbox_root = tmp_path / "agents"
    policies_dir = sandbox_root / "policies"
    state_dir = sandbox_root / "state"
    sandbox_root.mkdir()
    policies_dir.mkdir()
    state_dir.mkdir()

    # Patch agent registry/policy/state roots
    monkeypatch.setattr(agents.registry, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.registry, "REGISTRY_PATH", sandbox_root / "registry.json", raising=False)
    monkeypatch.setattr(agents.registry, "_REGISTRY_LOCK", threading.Lock(), raising=False)
    monkeypatch.setattr(agents.policy, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.policy, "POLICIES_DIR", policies_dir, raising=False)
    monkeypatch.setattr(agents.state, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.state, "STATE_TEMPLATE_DIR", state_dir, raising=False)

    data_root = tmp_path / "data"
    telemetry_dir = data_root / "telemetry" / "agents"
    audit_dir = data_root / "audit"
    cap_dir = data_root / "capability_tokens"
    consent_dir = data_root / "consent"
    permissions_dir = data_root / "permissions"
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    cap_dir.mkdir(parents=True, exist_ok=True)
    consent_dir.mkdir(parents=True, exist_ok=True)
    permissions_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(agent_capabilities, "CORE_DATA_ROOT", data_root, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_DIR", audit_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_LOG", audit_dir / "agent_capability_failures.jsonl", raising=False)
    monkeypatch.setattr(agent_capabilities, "CAPABILITY_STORE_ROOT", cap_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "CONSENT_STORE_ROOT", consent_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "TELEMETRY_DIR", telemetry_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "TELEMETRY_LOG", telemetry_dir / "agent_activity.jsonl", raising=False)

    telemetry_dir.joinpath("agent_activity.jsonl").write_text("", encoding="utf-8")
    audit_dir.joinpath("agent_capability_failures.jsonl").write_text("", encoding="utf-8")

    # Patch daemon constants to new data root
    monkeypatch.setattr(agent_daemon_module, "CORE_DATA_ROOT", data_root, raising=False)
    monkeypatch.setattr(agent_daemon_module, "audit_event", agent_capabilities.audit_event, raising=False)

    # Provide ensure_dirs_for_user stub
    def ensure_dirs_for_user_stub(user_id: str) -> Dict[str, Path]:
        user_dir = data_root / "users" / user_id
        agent_dir = user_dir / "agent"
        user_dir.mkdir(parents=True, exist_ok=True)
        agent_dir.mkdir(parents=True, exist_ok=True)
        return {
            "udir": user_dir,
            "agent": agent_dir,
        }

    monkeypatch.setattr(agents.state, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)
    monkeypatch.setattr(agents.mailbox, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)
    monkeypatch.setattr(agent_triggers_module, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)

    return {
        "data_root": data_root,
        "telemetry_log": telemetry_dir / "agent_activity.jsonl",
        "consent_dir": consent_dir,
        "permissions_dir": permissions_dir,
    }


def read_telemetry(log_path: Path) -> list[dict]:
    entries: list[dict] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def create_agent(user_id: str, autonomy: str = "auto"):
    agents.ensure_agent_record(user_id)
    agents.update_agent_policy(user_id, {"autonomy": autonomy})


def issue_capability(user_id: str, scope: str, minutes: int = 30):
    agent_capabilities.issue_capability_record(user_id, scope, ttl_minutes=minutes)


def write_consent(consent_dir: Path, user_id: str, scopes: dict):
    path = consent_dir / f"{user_id}.json"
    path.write_text(json.dumps(scopes, indent=2), encoding="utf-8")


def run_daemon(user_id: str):
    daemon = agent_daemon_module.AgentDaemon()
    return daemon.run_once(user_id)


def latest_outbox_entries(user_id: str):
    mailbox = agents.AgentMailbox(user_id)
    outbox, _ = mailbox.read_outbox(start_index=0)
    return outbox


def test_file_trigger_executes_in_l2(trigger_env):
    user_id = "USER1"
    create_agent(user_id, autonomy="auto")
    issue_capability(user_id, "core.agent.run")

    engine = agent_triggers_module.TriggerEngine()
    result = engine.ingest_file_event(user_id, "watched/USER1/notes.md")
    assert result is not None

    summary = run_daemon(user_id)
    assert summary["executed"] == 1

    outbox = latest_outbox_entries(user_id)
    assert any(entry.get("status") == "completed" and entry.get("kind") == "analyze" for entry in outbox)

    telemetry = read_telemetry(trigger_env["telemetry_log"])
    assert any(entry.get("event") == "trigger_emitted" for entry in telemetry)
    assert any(entry.get("event") == "trigger_consumed" for entry in telemetry)
    assert any(entry.get("event") == "job_completed" for entry in telemetry)


def test_conflict_trigger_without_capability_blocked(trigger_env):
    user_id = "USER2"
    create_agent(user_id, autonomy="auto")
    issue_capability(user_id, "core.agent.run")

    engine = agent_triggers_module.TriggerEngine()
    result = engine.ingest_conflict_backlog(user_id, backlog_size=7)
    assert result is not None

    summary = run_daemon(user_id)
    assert summary["executed"] == 0
    assert summary["failures"] >= 1

    outbox = latest_outbox_entries(user_id)
    assert any(entry.get("status") == "blocked" and entry.get("kind") == "resolve" for entry in outbox)

    telemetry = read_telemetry(trigger_env["telemetry_log"])
    assert any(entry.get("event") == "job_blocked" and entry.get("reason") == "capability_missing" for entry in telemetry)


def test_sensitive_trigger_without_consent_denied(trigger_env):
    user_id = "USER3"
    create_agent(user_id, autonomy="auto")
    issue_capability(user_id, "core.agent.run")

    engine = agent_triggers_module.TriggerEngine()
    payload = {
        "path": "watched/USER3/report.pdf",
        "sensitive_namespaces": ["PaDNA"],
    }
    result = engine.emit_trigger(user_id, "trigger.file_added", payload)
    assert result is not None
    assert result["payload"].get("sensitive_namespaces") == ["PaDNA"]

    with pytest.raises(agent_capabilities.ConsentDeniedError):
        agent_capabilities.ensure_consent(user_id, ["PaDNA"])

    summary = run_daemon(user_id)
    assert summary["executed"] == 0

    outbox = latest_outbox_entries(user_id)
    assert any(entry.get("status") == "blocked" and entry.get("error") for entry in outbox)

    telemetry = read_telemetry(trigger_env["telemetry_log"])
    assert any(entry.get("event") == "job_blocked" and entry.get("reason") == "consent_denied" for entry in telemetry)


def test_level_one_autonomy_proposes_only(trigger_env):
    user_id = "USER4"
    create_agent(user_id, autonomy="propose")
    issue_capability(user_id, "core.agent.run")

    engine = agent_triggers_module.TriggerEngine()
    result = engine.ingest_file_event(user_id, "watched/USER4/notes.md")
    assert result is not None

    summary = run_daemon(user_id)
    assert summary["executed"] == 0
    assert summary["proposed"] >= 1

    mailbox = agents.AgentMailbox(user_id)
    state_store = agents.AgentStateStore(user_id)
    state = state_store.load()
    assert any(job.get("status") == "awaiting_manual" for job in state.pending_jobs)

    telemetry = read_telemetry(trigger_env["telemetry_log"])
    assert any(entry.get("event") == "trigger_consumed" for entry in telemetry)
