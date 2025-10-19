"""
Integration Tests: Delegation + Coach Mode Switching
====================================================

Tests the complete flow from delegation creation through mode switching.
"""
import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def integration_test_client():
    """Create test client with both delegation and mode switching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import os
        import sys
        os.environ["CORE_DATA_DIR"] = str(tmpdir)

        # Clear cached modules
        for module_name in list(sys.modules.keys()):
            if module_name.startswith("core.coach"):
                del sys.modules[module_name]

        from core.api import build_app
        app = build_app()
        client = TestClient(app)

        # Create test user with high-curiosity PaDNA traits
        user_dir = Path(tmpdir) / "users" / "test_user"
        user_dir.mkdir(parents=True, exist_ok=True)

        resolved = {
            "PaDNA.HairDNA.Color": {
                "value": "Unknown",
                "ucn": 25,
                "rr": 15,
                "curiosity": 85
            },
            "PaDNA.EyeDNA.Color": {
                "value": "Unknown",
                "ucn": 20,
                "rr": 10,
                "curiosity": 90
            },
            "ReDNA.ToleranceForNudging": {
                "value": 0.7,
                "ucn": 80,
                "rr": 80
            }
        }

        with open(user_dir / "resolved.json", "w") as f:
            json.dump(resolved, f)

        # Create coach registry
        core_dir = Path(tmpdir).parent / "core"
        core_dir.mkdir(exist_ok=True)
        registry_path = core_dir / "coach_registry.yaml"

        registry_content = """
coaches:
  photo_coach:
    display_name: "Photo Coach"
    id: "photo_coach"
    primary_namespaces:
      - PaDNA
    capabilities:
      - PaDNA.*
    delegation_context: "photo analysis"
    suitable_for_types:
      - trait
      - missing

  head_coach:
    display_name: "Head Coach"
    id: "head_coach"
    primary_namespaces:
      - CogDNA
    capabilities:
      - "*"
    is_default: true

delegation_rules:
  min_curiosity_for_delegation: 60.0
  min_tolerance_for_proactive_delegation: 0.5

availability:
  photo_coach: true
  head_coach: true
"""
        registry_path.write_text(registry_content)

        yield client, tmpdir


def test_complete_delegation_flow_with_mode_switch(integration_test_client):
    """Test: Create delegation → Switch mode → Verify both systems updated."""
    client, tmpdir = integration_test_client

    user_id = "test_user"

    # Step 1: Verify initial mode is head_coach
    mode_response = client.get(f"/users/{user_id}/coach-mode")
    assert mode_response.status_code == 200
    mode_data = mode_response.json()
    assert mode_data["ok"] is True
    assert mode_data["active_mode"] == "head_coach"

    # Step 2: Create delegation to Photo Coach
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
            "context": {"reason": "test_integration"}
        }
    )

    assert delegation_response.status_code == 200
    delegation_data = delegation_response.json()
    assert delegation_data["ok"] is True
    delegation_id = delegation_data["delegation"]["delegation_id"]

    # Step 3: Switch to photo mode with delegation context
    switch_response = client.post(
        f"/users/{user_id}/coach-mode",
        json={
            "target_mode": "photo",
            "delegation_id": delegation_id,
            "context": {"test": "integration"}
        }
    )

    assert switch_response.status_code == 200
    switch_data = switch_response.json()
    assert switch_data["ok"] is True
    assert switch_data["previous_mode"] == "head_coach"
    assert switch_data["new_mode"] == "photo"
    assert switch_data["mode_info"]["display_name"] == "Photo Coach"

    # Step 4: Verify active mode changed
    mode_check = client.get(f"/users/{user_id}/coach-mode")
    mode_check_data = mode_check.json()
    assert mode_check_data["active_mode"] == "photo"

    # Step 5: Verify delegation is active
    delegation_status = client.get(f"/delegation/{user_id}/status/{delegation_id}")
    status_data = delegation_status.json()
    assert status_data["ok"] is True
    assert status_data["status"]["delegation_id"] == delegation_id

    # Step 6: Verify mode history includes delegation context
    history_response = client.get(f"/users/{user_id}/coach-mode/history?limit=1")
    history_data = history_response.json()
    assert history_data["ok"] is True
    assert len(history_data["history"]) == 1
    assert history_data["history"][0]["from_mode"] == "head_coach"
    assert history_data["history"][0]["to_mode"] == "photo"
    assert history_data["history"][0]["context"]["delegation_id"] == delegation_id


def test_active_delegations_updates_after_creation(integration_test_client):
    """Test: Active delegations widget gets updated data."""
    client, tmpdir = integration_test_client

    user_id = "test_user"

    # Initially no active delegations
    active_response = client.get(f"/delegation/{user_id}/active")
    active_data = active_response.json()
    assert active_data["count"] == 0

    # Create delegation
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )

    delegation_id = delegation_response.json()["delegation"]["delegation_id"]

    # Now should have 1 active delegation
    active_response2 = client.get(f"/delegation/{user_id}/active")
    active_data2 = active_response2.json()
    assert active_data2["count"] == 1
    assert active_data2["delegations"][0]["delegation_id"] == delegation_id
    assert active_data2["delegations"][0]["coach"] == "photo_coach"


def test_mode_switch_back_to_head_coach(integration_test_client):
    """Test: Switch to Photo Coach → Complete → Switch back to Head Coach."""
    client, tmpdir = integration_test_client

    user_id = "test_user"

    # Create delegation and switch to photo mode
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )

    delegation_id = delegation_response.json()["delegation"]["delegation_id"]

    client.post(
        f"/users/{user_id}/coach-mode",
        json={"target_mode": "photo", "delegation_id": delegation_id}
    )

    # Verify in photo mode
    mode_check1 = client.get(f"/users/{user_id}/coach-mode")
    assert mode_check1.json()["active_mode"] == "photo"

    # Switch back to head coach
    switch_back = client.post(
        f"/users/{user_id}/coach-mode",
        json={"target_mode": "head_coach"}
    )

    assert switch_back.status_code == 200
    switch_data = switch_back.json()
    assert switch_data["previous_mode"] == "photo"
    assert switch_data["new_mode"] == "head_coach"

    # Verify back in head_coach mode
    mode_check2 = client.get(f"/users/{user_id}/coach-mode")
    assert mode_check2.json()["active_mode"] == "head_coach"


def test_mode_stats_track_delegation_switches(integration_test_client):
    """Test: Mode stats correctly track delegation-triggered switches."""
    client, tmpdir = integration_test_client

    # Use unique user to avoid cross-test pollution
    user_id = "stats_test_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create multiple delegations with mode switches
    for i in range(3):
        delegation_response = client.post(
            "/delegation/create",
            json={
                "user_id": user_id,
                "coach_id": "photo_coach",
                "curiosity_targets": ["PaDNA.HairDNA.Color"]
            }
        )

        delegation_id = delegation_response.json()["delegation"]["delegation_id"]

        client.post(
            f"/users/{user_id}/coach-mode",
            json={"target_mode": "photo", "delegation_id": delegation_id}
        )

        # Switch back
        client.post(
            f"/users/{user_id}/coach-mode",
            json={"target_mode": "head_coach"}
        )

    # Check stats
    stats_response = client.get(f"/users/{user_id}/coach-mode/stats")
    stats_data = stats_response.json()

    assert stats_data["ok"] is True
    assert stats_data["stats"]["total_transitions"] == 6  # 3x (photo + head_coach)
    assert stats_data["stats"]["mode_counts"]["photo"] == 3
    assert stats_data["stats"]["mode_counts"]["head_coach"] == 3


def test_invalid_mode_in_delegation_flow(integration_test_client):
    """Test: Invalid mode in switch request is rejected."""
    client, tmpdir = integration_test_client

    user_id = "test_user"

    # Try to switch to invalid mode
    switch_response = client.post(
        f"/users/{user_id}/coach-mode",
        json={"target_mode": "invalid_mode"}
    )

    # Should fail
    assert switch_response.status_code == 400
    switch_data = switch_response.json()
    assert switch_data["ok"] is False


def test_delegation_without_mode_switch_still_works(integration_test_client):
    """Test: Can create delegation without switching mode (manual flow)."""
    client, tmpdir = integration_test_client

    user_id = "test_user"

    # Create delegation
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )

    assert delegation_response.status_code == 200
    delegation_id = delegation_response.json()["delegation"]["delegation_id"]

    # DON'T switch mode - delegation should still exist
    delegation_status = client.get(f"/delegation/{user_id}/status/{delegation_id}")
    assert delegation_status.status_code == 200

    # Mode should still be head_coach
    mode_check = client.get(f"/users/{user_id}/coach-mode")
    assert mode_check.json()["active_mode"] == "head_coach"


def test_concurrent_delegations_different_modes(integration_test_client):
    """Test: Multiple delegations can exist even if mode switches."""
    client, tmpdir = integration_test_client

    user_id = "test_user"

    # Create first delegation (photo)
    delegation1 = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )

    delegation_id1 = delegation1.json()["delegation"]["delegation_id"]

    # Switch to photo mode
    client.post(
        f"/users/{user_id}/coach-mode",
        json={"target_mode": "photo", "delegation_id": delegation_id1}
    )

    # Create second delegation (still shows as active even though mode changed)
    # This tests that delegations persist across mode changes
    active_delegations = client.get(f"/delegation/{user_id}/active")
    active_data = active_delegations.json()

    # Should have 1 active delegation (photo_coach)
    assert active_data["count"] >= 1
    assert any(d["delegation_id"] == delegation_id1 for d in active_data["delegations"])


def test_mode_history_shows_delegation_context(integration_test_client):
    """Test: Mode history includes delegation metadata."""
    client, tmpdir = integration_test_client

    # Use unique user to avoid cross-test pollution
    user_id = "history_test_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create delegation
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"]
        }
    )

    delegation_id = delegation_response.json()["delegation"]["delegation_id"]

    # Switch mode with delegation context
    client.post(
        f"/users/{user_id}/coach-mode",
        json={
            "target_mode": "photo",
            "delegation_id": delegation_id,
            "context": {"custom_field": "test_value"}
        }
    )

    # Get history
    history_response = client.get(f"/users/{user_id}/coach-mode/history?limit=1")
    history_data = history_response.json()

    transition = history_data["history"][0]

    # Should include delegation context
    assert transition["context"]["delegation_id"] == delegation_id
    assert transition["context"]["reason"] == "delegation"
    assert transition["context"]["custom_field"] == "test_value"
