from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from ReDNACoreDemo import agents
from ReDNACoreDemo.devx.backend import agent_api
from ReDNACoreDemo.core import agent_capabilities


@pytest.fixture
def capability_app(tmp_path, monkeypatch):
    sandbox_root = tmp_path / "agents"
    policies_dir = sandbox_root / "policies"
    state_dir = sandbox_root / "state"
    sandbox_root.mkdir()
    policies_dir.mkdir()
    state_dir.mkdir()

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

    telemetry_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    cap_dir.mkdir(parents=True, exist_ok=True)
    consent_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(agent_capabilities, "CORE_DATA_ROOT", data_root, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_DIR", audit_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "AUDIT_LOG", audit_dir / "agent_capability_failures.jsonl", raising=False)
    monkeypatch.setattr(agent_capabilities, "CAPABILITY_STORE_ROOT", cap_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "CONSENT_STORE_ROOT", consent_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "TELEMETRY_DIR", telemetry_dir, raising=False)
    monkeypatch.setattr(agent_capabilities, "TELEMETRY_LOG", telemetry_dir / "agent_activity.jsonl", raising=False)

    telemetry_dir.joinpath("agent_activity.jsonl").write_text("", encoding="utf-8")
    audit_dir.joinpath("agent_capability_failures.jsonl").write_text("", encoding="utf-8")

    def ensure_dirs_for_user_stub(user_id: str) -> Dict[str, Path]:
        user_dir = data_root / "users" / user_id
        agent_dir = user_dir / "agent"
        user_dir.mkdir(parents=True, exist_ok=True)
        agent_dir.mkdir(parents=True, exist_ok=True)
        return {"udir": user_dir, "agent": agent_dir}

    monkeypatch.setattr(agents.state, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)
    monkeypatch.setattr(agents.mailbox, "ensure_dirs_for_user", ensure_dirs_for_user_stub, raising=False)

    app = FastAPI()
    app.include_router(agent_api.capability_router)
    return TestClient(app), telemetry_dir / "agent_activity.jsonl"


def read_audit(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def test_issue_devx_capability(capability_app):
    client, audit_log = capability_app
    user_id = "USER_CAP"
    agents.ensure_agent_record(user_id)

    payload = {
        "user_id": user_id,
        "scope": "core.agent.config",
        "ttl_minutes": 5,
    }

    response = client.post(
        "/devx/api/capability/issue",
        json=payload,
        headers={"x-devx-auth": "devx-local"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["ok"] is True
    assert data["scope"] == "core.agent.config"
    assert data["ttl_minutes"] == 5
    assert isinstance(data.get("token"), str) and data["token"]
    assert isinstance(data.get("capability_id"), str)
    assert data.get("expires_at")

    audit_entries = read_audit(audit_log)
    assert any(entry.get("event") == "capability_issued_devx" and entry.get("user_id") == user_id for entry in audit_entries)


def test_issue_devx_capability_rejects_long_ttl(capability_app):
    client, _ = capability_app
    response = client.post(
        "/devx/api/capability/issue",
        json={"user_id": "USER_FAIL", "scope": "core.agent.config", "ttl_minutes": 60},
        headers={"x-devx-auth": "devx-local"},
    )
    assert response.status_code == 400
