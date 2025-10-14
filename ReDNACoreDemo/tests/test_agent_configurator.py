from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ReDNACoreDemo import agents
from ReDNACoreDemo.core import agent_capabilities
from ReDNACoreDemo.devx.backend import agent_configurator, agent_api


@pytest.fixture
def agent_config_env(tmp_path, monkeypatch):
    """
    Provide an isolated filesystem sandbox for agent configuration tests.
    """
    sandbox_root = tmp_path / "agents"
    policies_dir = sandbox_root / "policies"
    state_dir = sandbox_root / "state"
    sandbox_root.mkdir()
    policies_dir.mkdir()
    state_dir.mkdir()

    registry_path = sandbox_root / "registry.json"
    monkeypatch.setattr(agents.registry, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.registry, "REGISTRY_PATH", registry_path, raising=False)
    monkeypatch.setattr(agents.registry, "_REGISTRY_LOCK", threading.Lock(), raising=False)

    monkeypatch.setattr(agents.policy, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.policy, "POLICIES_DIR", policies_dir, raising=False)

    monkeypatch.setattr(agents.state, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.state, "STATE_TEMPLATE_DIR", state_dir, raising=False)

    def ensure_dirs_for_user_stub(user_id: str):
        user_dir = tmp_path / "data" / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return {"udir": user_dir}

    monkeypatch.setattr(agents.state, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)
    monkeypatch.setattr(agents.mailbox, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)

    core_data_root = tmp_path / "core_data"
    telemetry_dir = core_data_root / "telemetry" / "agents"
    audit_dir = core_data_root / "audit" / "agents"
    capability_store = core_data_root / "capability_tokens"
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    capability_store.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(agent_capabilities, "CORE_DATA_ROOT", core_data_root, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_DIR", audit_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_LOG", audit_dir / "agent_capability_failures.jsonl", raising=False)
    monkeypatch.setattr(agent_capabilities, "CAPABILITY_STORE_ROOT", capability_store, raising=False)

    monkeypatch.setattr(agent_configurator, "CORE_DATA_ROOT", core_data_root, raising=False)

    return {
        "core_data_root": core_data_root,
        "telemetry_dir": telemetry_dir,
        "audit_dir": audit_dir,
        "capability_store": capability_store,
        "sandbox_root": sandbox_root,
    }


def test_level_zero_to_one_creates_background_agent(agent_config_env):
    user_id = "USER1"

    result = agent_configurator.configure_agent(
        user_id,
        level=1,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=False,
    )

    assert result["ok"] is True
    assert result["agent_level"] == 1
    assert result["policy"]["autonomy"] == "propose"
    assert result["schedule"].get("interval_hours") == 12
    assert result["capabilities"]["issued"] == []

    record = agents.get_agent_record(user_id)
    assert record is not None
    assert record.autonomy == "propose"
    assert record.status == "enabled"

    policy = agents.get_agent_policy(user_id)
    assert policy.quotas["jobs_per_day"] == 10

    state = agents.AgentStateStore(user_id).load()
    assert state.next_run is not None
    next_run = datetime.fromisoformat(state.next_run.replace("Z", "+00:00"))
    delta_hours = abs((next_run - datetime.now(timezone.utc)).total_seconds() / 3600)
    assert 11.0 <= delta_hours <= 12.5


def test_level_one_to_two_autonomous_preset(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=1, apply_defaults=True, actor="pytest", downgrade_confirmed=False)

    result = agent_configurator.configure_agent(
        user_id,
        level=2,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=False,
    )

    assert result["agent_level"] == 2
    assert result["policy"]["autonomy"] == "auto"
    assert result["schedule"].get("interval_hours") == 4
    features = result["policy"]["features"]
    assert features["self_improvement"]["trivial_auto_apply"] is True
    assert features["refinement"]["auto_accept_threshold"] == pytest.approx(0.75)

    issued_scopes = {cap["scope"] for cap in result["capabilities"]["issued"]}
    assert {"core.agent.run", "core.agent.config"} <= issued_scopes
    assert all(cap["ttl_minutes"] <= 60 for cap in result["capabilities"]["issued"])
    assert len(result["capabilities"]["revoked"]) == 0

    store_path = agent_config_env["capability_store"] / f"{user_id}.json"
    tokens = json.loads(store_path.read_text(encoding="utf-8"))
    assert all(token["status"] == "active" for token in tokens)


def test_level_two_to_zero_requires_confirmation(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=2, apply_defaults=True, actor="pytest", downgrade_confirmed=False)

    with pytest.raises(PermissionError):
        agent_configurator.configure_agent(
            user_id,
            level=0,
            apply_defaults=True,
            actor="pytest",
            downgrade_confirmed=False,
        )

    result = agent_configurator.configure_agent(
        user_id,
        level=0,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=True,
    )

    assert result["agent_level"] == 0
    assert result["policy"]["autonomy"] is None
    assert len(result["capabilities"]["issued"]) == 0
    assert len(result["capabilities"]["revoked"]) >= 2

    store_path = agent_config_env["capability_store"] / f"{user_id}.json"
    tokens = json.loads(store_path.read_text(encoding="utf-8"))
    assert tokens and all(token["status"] == "revoked" for token in tokens)

    state = agents.AgentStateStore(user_id).load()
    assert state.next_run is None
    assert state.pending_jobs == []

    archived = result.get("archived_state")
    assert archived
    assert Path(archived).exists()


def test_level_three_enables_rsc(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=2, apply_defaults=True, actor="pytest", downgrade_confirmed=False)

    result = agent_configurator.configure_agent(
        user_id,
        level=3,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=False,
    )

    scopes = {cap["scope"] for cap in result["capabilities"]["issued"]}
    assert {"agents.rsc.send", "agents.rsc.read"} <= scopes
    assert result["rsc_enabled"] is True

    record = agents.get_agent_record(user_id)
    assert record.metadata.get("rsc_enabled") is True


def test_reapply_defaults_refreshes_tokens(agent_config_env):
    user_id = "USER1"
    first = agent_configurator.configure_agent(
        user_id,
        level=2,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=False,
    )

    first_tokens = {cap["capability_id"] for cap in first["capabilities"]["issued"]}
    assert len(first_tokens) == 2

    second = agent_configurator.configure_agent(
        user_id,
        level=2,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=False,
    )

    second_tokens = {cap["capability_id"] for cap in second["capabilities"]["issued"]}
    assert len(second_tokens) == 2
    assert first_tokens.isdisjoint(second_tokens)
    assert len(second["capabilities"]["revoked"]) == 2

    store_path = agent_config_env["capability_store"] / f"{user_id}.json"
    tokens = json.loads(store_path.read_text(encoding="utf-8"))
    statuses = {entry["status"] for entry in tokens}
    assert statuses == {"active", "revoked"}


def test_level_four_workflow_metadata(agent_config_env):
    user_id = "USER1"
    result = agent_configurator.configure_agent(
        user_id,
        level=4,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=False,
    )

    toggles = result.get("workflow_toggles", {})
    assert toggles == {"calendar": True, "report": True, "email": True}
    assert result["quotas"]["jobs_per_day"] == 120
    assert "back_pressure" in result["policy"]["features"]

    scopes = {cap["scope"] for cap in result["capabilities"]["issued"]}
    assert {"agents.workflow.calendar", "agents.workflow.report", "agents.workflow.email"} <= scopes


def test_policy_file_contains_null_autonomy_for_manual(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=2, apply_defaults=True, actor="pytest", downgrade_confirmed=False)
    agent_configurator.configure_agent(user_id, level=0, apply_defaults=True, actor="pytest", downgrade_confirmed=True)

    policy_path = agent_config_env["sandbox_root"] / "policies" / f"hc_{user_id}.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    assert payload["autonomy"] is None


def test_multiple_archives_created_on_repeated_downgrades(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=2, apply_defaults=True, actor="pytest", downgrade_confirmed=False)
    first = agent_configurator.configure_agent(
        user_id,
        level=0,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=True,
    )
    first_path = Path(first["archived_state"])
    assert first_path.exists()

    agent_configurator.configure_agent(user_id, level=1, apply_defaults=True, actor="pytest", downgrade_confirmed=False)
    second = agent_configurator.configure_agent(
        user_id,
        level=0,
        apply_defaults=True,
        actor="pytest",
        downgrade_confirmed=True,
    )
    second_path = Path(second["archived_state"])
    assert second_path.exists()
    archive_dir = agent_config_env["core_data_root"] / "quarantine" / "agents" / user_id
    assert first_path.parent == archive_dir
    assert second_path.parent == archive_dir


def test_apply_defaults_false_keeps_custom_quota(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=2, apply_defaults=True, actor="pytest", downgrade_confirmed=False)

    agents.update_agent_policy(user_id, {"quotas": {"jobs_per_day": 7}})
    agents.update_agent_record(user_id, {"quotas": {"jobs_per_day": 7}})

    result = agent_configurator.configure_agent(
        user_id,
        level=2,
        apply_defaults=False,
        actor="pytest",
        downgrade_confirmed=False,
    )

    assert result["quotas"]["jobs_per_day"] == 7
    record = agents.get_agent_record(user_id)
    assert record.quotas["jobs_per_day"] == 7


def test_capability_metadata_includes_preset_details(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=3, apply_defaults=True, actor="pytest", downgrade_confirmed=False)

    store_path = agent_config_env["capability_store"] / f"{user_id}.json"
    tokens = json.loads(store_path.read_text(encoding="utf-8"))
    assert tokens
    for record in tokens:
        assert record["metadata"]["preset_level"] in {3}
        assert record["metadata"]["preset_name"] == "Collaborative"


def test_ui_smoke_hctab_strings_present():
    tab_path = Path("ReDNACoreDemo/devx/frontend/src/routes/user-ops/tabs/HCTab.tsx")
    contents = tab_path.read_text(encoding="utf-8")

    assert "Agency Level" in contents
    assert "Create Background Agent (L1)" in contents
    assert "Apply downgrade" in contents
    assert "Agent Control Center" in contents
    assert "LEVEL_OPTIONS" in contents


def test_audit_and_telemetry_entries(agent_config_env):
    user_id = "USER1"
    agent_configurator.configure_agent(user_id, level=2, apply_defaults=True, actor="pytest", downgrade_confirmed=False)

    # All events now go to unified activity log
    activity_log_path = agent_config_env["telemetry_dir"] / "agent_activity.jsonl"
    assert activity_log_path.exists(), "Unified agent_activity.jsonl should exist"

    activity_entries = [json.loads(line) for line in activity_log_path.read_text(encoding="utf-8").splitlines() if line]

    # Should have agent_configured event
    assert any(entry["event"] == "agent_configured" and entry["new_level"] == 2 for entry in activity_entries), \
        f"Should have agent_configured event in {activity_entries}"

    # Verify audit structure
    config_entry = next((e for e in activity_entries if e["event"] == "agent_configured"), None)
    assert config_entry["audit_id"], "Should have audit_id"
    assert config_entry["changes"], "Should have changes field"
    assert "issued_capabilities" in config_entry, "Should track issued capabilities"


def test_configure_endpoint_requires_confirm(agent_config_env):
    app = FastAPI()
    app.include_router(agent_api.router)
    app.include_router(agent_api.user_router)
    client = TestClient(app)
    user_id = "USER1"

    res = client.post(
        f"/devx/api/users/{user_id}/agent/configure",
        json={"level": 2, "apply_defaults": True},
    )
    assert res.status_code == 200

    res_downgrade = client.post(
        f"/devx/api/users/{user_id}/agent/configure",
        json={"level": 0, "apply_defaults": True},
    )
    assert res_downgrade.status_code == 409

    res_confirmed = client.post(
        f"/devx/api/users/{user_id}/agent/configure",
        json={"level": 0, "apply_defaults": True, "confirm": "apply"},
    )
    assert res_confirmed.status_code == 200
    payload = res_confirmed.json()
    assert len(payload["capabilities"]["revoked"]) >= 2
