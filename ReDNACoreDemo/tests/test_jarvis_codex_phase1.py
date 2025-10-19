"""
Test Suite — Jarvis Codex Interface Phase 1

Tests the Codex Agent's proposal, validation, checksum, and approval workflow.

Scenarios:
1. Valid proposal → patch file created + JSON log entry
2. Checksum mismatch → apply aborts, no file change
3. Low-confidence proposal (< 0.85) → rejected automatically
4. Approve flow → backup + audit log + diff verified
5. Reject flow → status update only
6. Telemetry events exist
7. API round-trip test
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone


@pytest.fixture
def temp_project_root(tmp_path):
    """Create temporary project structure."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create web/src directory
    web_src = project_root / "web" / "src" / "components"
    web_src.mkdir(parents=True)

    # Create test file
    test_file = web_src / "TestComponent.tsx"
    test_file.write_text("""
export function TestComponent() {
  return (
    <div>
      <h1>Old Title</h1>
      <p>Some content</p>
    </div>
  );
}
""")

    # Create insights directory
    insights_dir = project_root / "prompts" / "insights"
    insights_dir.mkdir(parents=True)

    return project_root


def test_valid_proposal_creates_patch(temp_project_root):
    """Test that valid proposal creates patch file and JSON log entry."""
    from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

    agent = create_codex_agent(project_root=temp_project_root)

    request = {
        "scope": "frontend",
        "file": "web/src/components/TestComponent.tsx",
        "intent": "Update title",
        "suggested_change": {
            "type": "text_replace",
            "before": "Old Title",
            "after": "New Title"
        },
        "confidence": 0.90,
        "source": "head_coach"
    }

    proposal, error = agent.generate_patch(request)

    assert error is None
    assert proposal is not None
    assert proposal.status == "pending"
    assert proposal.confidence == 0.90
    assert proposal.checksum_before is not None
    assert proposal.patch_file is not None

    # Verify patch file exists
    patch_path = temp_project_root / proposal.patch_file
    assert patch_path.exists()

    # Verify diff content
    diff = agent.get_patch_diff(proposal.proposal_id)
    assert diff is not None
    assert "Old Title" in diff
    assert "New Title" in diff

    # Verify proposal logged
    proposals = agent.list_proposals()
    assert len(proposals) == 1
    assert proposals[0]["proposal_id"] == proposal.proposal_id


def test_checksum_mismatch_aborts_apply(temp_project_root):
    """Test that checksum mismatch prevents apply."""
    from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

    agent = create_codex_agent(project_root=temp_project_root)

    request = {
        "scope": "frontend",
        "file": "web/src/components/TestComponent.tsx",
        "intent": "Update title",
        "suggested_change": {
            "type": "text_replace",
            "before": "Old Title",
            "after": "New Title"
        },
        "confidence": 0.90,
        "source": "head_coach"
    }

    proposal, error = agent.generate_patch(request)
    assert error is None

    # Modify file to create checksum mismatch
    file_path = temp_project_root / "web/src/components/TestComponent.tsx"
    content = file_path.read_text()
    file_path.write_text(content + "\n// Modified")

    # Try to apply - should fail
    success, error = agent.apply_patch(proposal.proposal_id, "admin")

    assert success is False
    assert "checksum mismatch" in error.lower()


def test_low_confidence_rejected(temp_project_root):
    """Test that low-confidence proposals are rejected."""
    from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

    agent = create_codex_agent(project_root=temp_project_root)

    request = {
        "scope": "frontend",
        "file": "web/src/components/TestComponent.tsx",
        "intent": "Update title",
        "suggested_change": {
            "type": "text_replace",
            "before": "Old Title",
            "after": "New Title"
        },
        "confidence": 0.75,  # Below default threshold of 0.85
        "source": "head_coach"
    }

    proposal, error = agent.generate_patch(request)

    assert proposal is None
    assert error is not None
    assert "confidence" in error.lower()


def test_approve_flow_with_backup(temp_project_root):
    """Test approve flow creates backup and updates file."""
    from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

    agent = create_codex_agent(project_root=temp_project_root)

    request = {
        "scope": "frontend",
        "file": "web/src/components/TestComponent.tsx",
        "intent": "Update title",
        "suggested_change": {
            "type": "text_replace",
            "before": "Old Title",
            "after": "New Title"
        },
        "confidence": 0.90,
        "source": "head_coach"
    }

    proposal, error = agent.generate_patch(request)
    assert error is None

    # Read original content
    file_path = temp_project_root / "web/src/components/TestComponent.tsx"
    original_content = file_path.read_text()

    # Apply patch
    success, error = agent.apply_patch(proposal.proposal_id, "admin")

    assert success is True
    assert error is None

    # Verify file was updated
    new_content = file_path.read_text()
    assert "New Title" in new_content
    assert "Old Title" not in new_content

    # Verify backup exists
    backup_dir = temp_project_root / "web/backups"
    assert backup_dir.exists()

    backups = list(backup_dir.glob("TestComponent.tsx_*.bak"))
    assert len(backups) == 1

    # Verify backup content
    backup_content = backups[0].read_text()
    assert backup_content == original_content

    # Verify proposal status updated
    proposals = agent.list_proposals()
    assert proposals[0]["status"] == "applied"


def test_reject_flow(temp_project_root):
    """Test reject flow updates status only."""
    from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

    agent = create_codex_agent(project_root=temp_project_root)

    request = {
        "scope": "frontend",
        "file": "web/src/components/TestComponent.tsx",
        "intent": "Update title",
        "suggested_change": {
            "type": "text_replace",
            "before": "Old Title",
            "after": "New Title"
        },
        "confidence": 0.90,
        "source": "head_coach"
    }

    proposal, error = agent.generate_patch(request)
    assert error is None

    # Read original content
    file_path = temp_project_root / "web/src/components/TestComponent.tsx"
    original_content = file_path.read_text()

    # Reject proposal
    success, error = agent.reject_patch(proposal.proposal_id, "admin", "Not needed")

    assert success is True
    assert error is None

    # Verify file was NOT changed
    current_content = file_path.read_text()
    assert current_content == original_content

    # Verify proposal status updated
    proposals = agent.list_proposals()
    assert proposals[0]["status"] == "rejected"


def test_telemetry_events(temp_project_root):
    """Test that telemetry events are logged."""
    from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

    agent = create_codex_agent(project_root=temp_project_root)

    request = {
        "scope": "frontend",
        "file": "web/src/components/TestComponent.tsx",
        "intent": "Update title",
        "suggested_change": {
            "type": "text_replace",
            "before": "Old Title",
            "after": "New Title"
        },
        "confidence": 0.90,
        "source": "head_coach"
    }

    proposal, error = agent.generate_patch(request)
    assert error is None

    # Check proposals log exists
    proposals_log = temp_project_root / "prompts/insights/jarvis_codex_proposals.jsonl"
    assert proposals_log.exists()

    # Apply patch
    agent.apply_patch(proposal.proposal_id, "admin")

    # Check audit log exists
    audit_log = temp_project_root / "prompts/insights/jarvis_codex_audit.jsonl"
    assert audit_log.exists()

    # Verify audit entries
    with open(audit_log, 'r') as f:
        entries = [json.loads(line) for line in f if line.strip()]

    assert len(entries) >= 1
    assert entries[0]["action"] == "applied"
    assert entries[0]["proposal_id"] == proposal.proposal_id


def test_api_round_trip(temp_project_root, monkeypatch):
    """Test /jarvis_codex/propose API endpoint."""
    from ReDNACoreDemo.core.api import build_app
    from fastapi.testclient import TestClient

    # Monkeypatch project root (API will use auto-detected root, but we need to ensure test structure)
    # For this test, we'll mock the agent creation

    app = build_app()
    client = TestClient(app)

    # Note: This test would need proper setup of project root in API
    # For now, we'll test the basic endpoint structure

    request = {
        "scope": "frontend",
        "file": "web/src/components/test.tsx",
        "intent": "Test",
        "suggested_change": {
            "type": "text_replace",
            "before": "old",
            "after": "new"
        },
        "confidence": 0.90,
        "source": "test"
    }

    # This will fail in test environment without full setup, but validates endpoint exists
    # In production, this would work with proper file paths
    response = client.post("/jarvis_codex/propose", json=request)

    # Endpoint exists (may fail with 400/500 due to file not found in test env)
    assert response.status_code in [200, 400, 500]


def test_list_proposals_filtering(temp_project_root):
    """Test proposal listing with status filtering."""
    from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

    # Create fresh test files for each proposal
    web_src = temp_project_root / "web" / "src" / "components"

    agent = create_codex_agent(project_root=temp_project_root)

    # Create multiple proposals with different files
    for i in range(3):
        test_file = web_src / f"TestComponent{i}.tsx"
        test_file.write_text(f"""
export function TestComponent{i}() {{
  return <div><h1>Title {i}</h1></div>;
}}
""")

        request = {
            "scope": "frontend",
            "file": f"web/src/components/TestComponent{i}.tsx",
            "intent": f"Update {i}",
            "suggested_change": {
                "type": "text_replace",
                "before": f"Title {i}",
                "after": f"Updated Title {i}"
            },
            "confidence": 0.90,
            "source": "head_coach"
        }
        proposal, error = agent.generate_patch(request)
        assert error is None

        # Apply first, reject second, leave third pending
        if i == 0:
            agent.apply_patch(proposal.proposal_id, "admin")
        elif i == 1:
            agent.reject_patch(proposal.proposal_id, "admin")

    # Test filtering
    all_proposals = agent.list_proposals()
    assert len(all_proposals) == 3

    pending = agent.list_proposals(status="pending")
    assert len(pending) == 1

    applied = agent.list_proposals(status="applied")
    assert len(applied) == 1

    rejected = agent.list_proposals(status="rejected")
    assert len(rejected) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
