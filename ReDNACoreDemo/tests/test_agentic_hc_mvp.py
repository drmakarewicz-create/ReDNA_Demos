from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ReDNACoreDemo import agents
from ReDNACoreDemo.agents import cli as agent_cli
from ReDNACoreDemo.agents import PolicyValidationError
from ReDNACoreDemo.core import agent_capabilities
from ReDNACoreDemo.core import agent_daemon as agent_daemon_module
from ReDNACoreDemo.devx.backend import agent_api as agent_api_module


@pytest.fixture(autouse=True)
def isolated_agent_environment(tmp_path, monkeypatch):
    """
    Provide an isolated filesystem sandbox for agent data to keep tests hermetic.
    """

    sandbox_root = tmp_path / "agents"
    policies_dir = sandbox_root / "policies"
    state_dir = sandbox_root / "state"
    sandbox_root.mkdir()
    policies_dir.mkdir()
    state_dir.mkdir()

    # Patch registry paths
    monkeypatch.setattr(agents.registry, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.registry, "REGISTRY_PATH", sandbox_root / "registry.json", raising=False)
    monkeypatch.setattr(agents.registry, "_REGISTRY_LOCK", threading.Lock(), raising=False)

    # Patch policy paths
    monkeypatch.setattr(agents.policy, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.policy, "POLICIES_DIR", policies_dir, raising=False)

    # Patch state paths and storage helpers
    monkeypatch.setattr(agents.state, "AGENTS_ROOT", sandbox_root, raising=False)
    monkeypatch.setattr(agents.state, "STATE_TEMPLATE_DIR", state_dir, raising=False)

    def ensure_dirs_for_user_stub(user_id: str) -> Dict[str, Path]:
        user_dir = tmp_path / "data" / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return {"udir": user_dir}

    monkeypatch.setattr(agents.state, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)
    monkeypatch.setattr(agents.mailbox, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)

    # Patch telemetry directory for daemon to avoid writing to repo
    telemetry_root = tmp_path / "telemetry"
    telemetry_root.mkdir()
    monkeypatch.setattr(agent_daemon_module, "CORE_DATA_ROOT", telemetry_root, raising=False)

    # Capability audit log should also write into sandbox
    audit_dir = telemetry_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent_capabilities, "CORE_DATA_ROOT", telemetry_root, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_DIR", audit_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_LOG", audit_dir / "agent_capability_failures.jsonl", raising=False)
    cap_store = telemetry_root / "capability_tokens"
    cap_store.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent_capabilities, "CAPABILITY_STORE_ROOT", cap_store, raising=False)

    yield


# --------------------------------------------------------------------------- #
# Registry and policy management
# --------------------------------------------------------------------------- #


def test_agent_registry_crud_operations():
    record = agents.ensure_agent_record("TESTUSER")
    assert record.user_id == "TESTUSER"
    assert record.agent_id == "hc_TESTUSER"
    assert record.autonomy == "semi"

    # Newly created record should be discoverable
    listing = agents.list_agents()
    assert any(item.user_id == "TESTUSER" for item in listing)

    # Update autonomy and status
    updated = agents.update_agent_record("TESTUSER", {"autonomy": "auto", "status": "disabled"})
    assert updated.autonomy == "auto"
    assert updated.status == "disabled"

    fetched = agents.get_agent_record("TESTUSER")
    assert fetched is not None
    assert fetched.autonomy == "auto"
    assert fetched.status == "disabled"


def test_policy_fetch_and_update_validations():
    # Default policy is created lazily
    policy = agents.get_agent_policy("ALPHA")
    assert policy.autonomy == "semi"
    assert policy.quotas["jobs_per_day"] == 50

    # Valid update succeeds
    updated = agents.update_agent_policy(
        "ALPHA",
        {
            "autonomy": "auto",
            "quotas": {"jobs_per_day": 10},
            "permissions": {"namespaces": ["SkillDNA"], "sensitive": ["PsyDNA"]},
        },
    )
    assert updated.autonomy == "auto"
    assert updated.quotas["jobs_per_day"] == 10
    assert updated.permissions["namespaces"] == ["SkillDNA"]

    # Invalid autonomy should raise
    with pytest.raises(PolicyValidationError):
        agents.update_agent_policy("ALPHA", {"autonomy": "invalid-mode"})

    # Permissions cannot be empty
    with pytest.raises(PolicyValidationError):
        agents.update_agent_policy("ALPHA", {"permissions": {"namespaces": []}})


# --------------------------------------------------------------------------- #
# Daemon behaviour
# --------------------------------------------------------------------------- #


def test_agent_daemon_processes_jobs_with_quota(monkeypatch, tmp_path):
    user_id = "DAEMON1"
    agents.ensure_agent_record(user_id)
    agents.update_agent_policy(user_id, {"autonomy": "auto"})

    executed_jobs: List[str] = []

    def curiosity_provider(_user_id, _policy, _state):
        return [{"job_id": "curiosity-1", "kind": "nudge", "payload": {"trait_id": "SkillDNA/coachability"}}]

    def refinement_provider(_user_id, _policy, _state):
        return [
            {"job_id": "refine-1", "kind": "refine", "payload": {"trait_id": "Career/storytelling"}},
            {"job_id": "resolve-1", "kind": "resolve", "payload": {"trait_id": "SkillDNA/system_thinking"}},
        ]

    def improvement_provider(_user_id, _policy, _state):
        return [{"job_id": "improve-1", "kind": "analyze", "payload": {"name": "self-improvement-cycle"}}]

    def executor(job, _policy):
        executed_jobs.append(job.job_id)
        return {"ok": True, "job_id": job.job_id}

    daemon = agent_daemon_module.AgentDaemon(
        interval_minutes=1,
        curiosity_provider=curiosity_provider,
        refinement_provider=refinement_provider,
        improvement_provider=improvement_provider,
        executor=executor,
    )

    summary = daemon.run_once(user_id)
    assert summary["executed"] == 4
    assert summary["proposed"] == 0
    assert summary["failures"] == 0
    assert set(executed_jobs) == {"curiosity-1", "refine-1", "resolve-1", "improve-1"}

    mailbox = agents.AgentMailbox(user_id)
    _, inbox_count = mailbox.read_inbox(start_index=0)
    outbox_entries, outbox_count = mailbox.read_outbox(start_index=0)
    assert inbox_count == 0  # No manual inbox items queued
    assert outbox_count == 4
    assert all(entry.get("status") == "completed" for entry in outbox_entries)

    # Re-run should respect quotas when lowered
    agents.update_agent_policy(user_id, {"quotas": {"jobs_per_day": 2}})
    summary2 = daemon.run_once(user_id)
    assert summary2["executed"] == 0
    assert summary2["failures"] == 4  # quota_exceeded for each job


def test_autonomy_modes_gate_execution(monkeypatch):
    user_id = "AUTONOMY"
    agents.ensure_agent_record(user_id)
    agents.update_agent_policy(user_id, {"autonomy": "propose"})

    daemon = agent_daemon_module.AgentDaemon(
        interval_minutes=1,
        curiosity_provider=lambda *_: [{"job_id": "job-1", "kind": "nudge", "payload": {}}],
    )
    result = daemon.run_once(user_id)
    assert result["executed"] == 0
    assert result["proposed"] == 1

    mailbox = agents.AgentMailbox(user_id)
    outbox, _ = mailbox.read_outbox(start_index=0)
    assert any(entry.get("status") == "awaiting_manual" for entry in outbox)


# --------------------------------------------------------------------------- #
# Capability tokens
# --------------------------------------------------------------------------- #


def test_capability_token_lifecycle(monkeypatch):
    token = agent_capabilities.generate_token(agent_id="hc_USER", scope="core.agent.run", user_id="USER", ttl_seconds=1)
    payload = agent_capabilities.verify_token(token.token, required_scope="core.agent.run", user_id="USER")
    assert payload["agent"] == "hc_USER"

    # Wrong scope should be rejected
    with pytest.raises(agent_capabilities.CapabilityError):
        agent_capabilities.verify_token(token.token, required_scope="core.agent.config", user_id="USER")

    # Wait for expiry and ensure verification fails
    time.sleep(1.2)
    with pytest.raises(agent_capabilities.CapabilityError):
        agent_capabilities.verify_token(token.token, required_scope="core.agent.run", user_id="USER")


# --------------------------------------------------------------------------- #
# DevX Agent Control API
# --------------------------------------------------------------------------- #


@pytest.fixture
def agent_api_client(monkeypatch):
    app = FastAPI()
    monkeypatch.setattr(agent_api_module, "DEVX_ADMIN_TOKEN", "test-admin", raising=False)

    class DummyDaemon:
        def run_once(self, user_id: str) -> Dict[str, Any]:
            return {
                "user_id": user_id,
                "agent_id": f"hc_{user_id}",
                "executed": 1,
                "proposed": 0,
                "failures": 0,
                "pending_after": 0,
            }

    monkeypatch.setattr(agent_api_module, "AgentDaemon", lambda *args, **kwargs: DummyDaemon(), raising=False)
    app.include_router(agent_api_module.router)
    return TestClient(app)


def test_agent_api_endpoints(agent_api_client):
    user_id = "APIUSER"
    agents.ensure_agent_record(user_id)

    # Issue capability via admin endpoint
    response = agent_api_client.post(
        f"/devx/api/agents/{user_id}/capability",
        headers={"x-devx-auth": "test-admin"},
        json={"scope": "core.agent.run", "ttl_seconds": 60},
    )
    assert response.status_code == 200
    run_token = response.json()["token"]

    # Run agent using capability
    run_response = agent_api_client.post(
        f"/devx/api/agents/{user_id}/run",
        headers={agent_api_module.CAPABILITY_HEADER: run_token},
        json={},
    )
    assert run_response.status_code == 200
    assert run_response.json()["executed"] == 1

    # Update autonomy
    config_token_response = agent_api_client.post(
        f"/devx/api/agents/{user_id}/capability",
        headers={"x-devx-auth": "test-admin"},
        json={"scope": "core.agent.config", "ttl_seconds": 60},
    )
    config_token = config_token_response.json()["token"]

    autonomy_response = agent_api_client.post(
        f"/devx/api/agents/{user_id}/autonomy",
        headers={agent_api_module.CAPABILITY_HEADER: config_token},
        json={"autonomy": "auto"},
    )
    assert autonomy_response.status_code == 200
    assert autonomy_response.json()["autonomy"] == "auto"

    # List agents should include our record
    list_response = agent_api_client.get("/devx/api/agents")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert any(agent["user_id"] == user_id for agent in payload["agents"])

    # Mailbox endpoint returns structure
    mailbox_response = agent_api_client.get(f"/devx/api/agents/{user_id}/mailbox?limit=10")
    assert mailbox_response.status_code == 200
    assert "inbox" in mailbox_response.json()


def test_agent_api_requires_capabilities(agent_api_client):
    user_id = "API_SCOPES"
    agents.ensure_agent_record(user_id)

    # Missing header
    response = agent_api_client.post(f"/devx/api/agents/{user_id}/run", json={})
    assert response.status_code == 403

    # Invalid token
    bad_response = agent_api_client.post(
        f"/devx/api/agents/{user_id}/run",
        headers={agent_api_module.CAPABILITY_HEADER: "invalid.token"},
        json={},
    )
    assert bad_response.status_code == 403


# --------------------------------------------------------------------------- #
# CLI smoke test
# --------------------------------------------------------------------------- #


def test_cli_status_and_run(monkeypatch, capsys):
    user_id = "CLITEST"
    agents.ensure_agent_record(user_id)

    class DummyDaemon:
        def run_once(self, user_id: str) -> Dict[str, Any]:
            return {"user_id": user_id, "executed": 0, "proposed": 0, "failures": 0, "pending_after": 0}

    monkeypatch.setattr(agent_daemon_module, "AgentDaemon", lambda *args, **kwargs: DummyDaemon(), raising=False)

    agent_cli.main(["--user", user_id, "--status"])
    status_output = json.loads(capsys.readouterr().out)
    assert status_output["status"]["user_id"] == user_id

    agent_cli.main(["--user", user_id, "--run-once"])
    run_output = json.loads(capsys.readouterr().out)
    assert run_output["run"]["executed"] == 0
