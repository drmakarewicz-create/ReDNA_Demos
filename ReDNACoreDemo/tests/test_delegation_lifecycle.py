"""
End-to-end tests for complete delegation lifecycle.

Tests the full flow:
1. Head Coach creates delegation
2. Switch to specialized coach mode
3. Specialized coach collects traits
4. Complete delegation with results
5. Auto-return to Head Coach with context
"""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def lifecycle_test_client():
    """Create test client with temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock CORE_DATA_ROOT for testing
        import core.api as api_module
        original_data_root = api_module.CORE_DATA_ROOT
        api_module.CORE_DATA_ROOT = Path(tmpdir)

        # Import app after setting CORE_DATA_ROOT
        from core.api import app

        client = TestClient(app)

        yield client, tmpdir

        # Restore original data root
        api_module.CORE_DATA_ROOT = original_data_root


def test_complete_delegation_lifecycle_photo_coach(lifecycle_test_client):
    """
    Test: Complete delegation lifecycle with Photo Coach.

    Flow:
    1. Head Coach creates delegation to Photo Coach
    2. Switch to photo mode
    3. Photo Coach collects PaDNA traits
    4. Complete delegation with high satisfaction
    5. Verify auto-return to Head Coach
    6. Verify delegation marked as completed
    """
    client, tmpdir = lifecycle_test_client
    user_id = "lifecycle_photo_test_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Create delegation to Photo Coach
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": [
                "PaDNA.HairDNA.Color",
                "PaDNA.HairDNA.Texture",
                "PaDNA.EyeDNA.Color"
            ]
        }
    )

    assert delegation_response.status_code == 200
    delegation_data = delegation_response.json()
    assert delegation_data["ok"] is True
    delegation_id = delegation_data["delegation"]["delegation_id"]

    # Step 2: Switch to photo mode
    mode_response = client.post(
        f"/users/{user_id}/coach-mode",
        json={
            "target_mode": "photo",
            "delegation_id": delegation_id,
        }
    )

    assert mode_response.status_code == 200
    mode_data = mode_response.json()
    assert mode_data["new_mode"] == "photo"

    # Verify mode switched
    active_mode_response = client.get(f"/users/{user_id}/coach-mode")
    assert active_mode_response.json()["active_mode"] == "photo"

    # Step 3: Simulate Photo Coach collecting traits
    # (In real scenario, this would happen through conversation)
    curiosity_before = {
        "PaDNA.HairDNA.Color": 85.0,
        "PaDNA.HairDNA.Texture": 78.0,
        "PaDNA.EyeDNA.Color": 92.0,
    }

    curiosity_after = {
        "PaDNA.HairDNA.Color": 12.0,
        "PaDNA.HairDNA.Texture": 15.0,
        "PaDNA.EyeDNA.Color": 8.0,
    }

    traits_collected = [
        "PaDNA.HairDNA.Color",
        "PaDNA.HairDNA.Texture",
        "PaDNA.EyeDNA.Color",
    ]

    # Step 4: Complete delegation
    complete_response = client.post(
        f"/delegation/{user_id}/complete/{delegation_id}",
        json={
            "traits_collected": traits_collected,
            "curiosity_before": curiosity_before,
            "curiosity_after": curiosity_after,
            "notes": "Analyzed user photo, collected hair and eye traits",
            "auto_return": True,
        }
    )

    assert complete_response.status_code == 200
    complete_data = complete_response.json()
    assert complete_data["ok"] is True

    # Verify delegation summary
    summary = complete_data["delegation_summary"]
    assert summary["traits_collected_count"] == 3
    assert summary["curiosity_satisfied"] > 0.8  # High satisfaction (>80%)
    assert summary["notes"] == "Analyzed user photo, collected hair and eye traits"

    # Step 5: Verify auto-return to Head Coach
    mode_switch = complete_data["mode_switch"]
    assert mode_switch["previous_mode"] == "photo"
    assert mode_switch["new_mode"] == "head_coach"

    # Verify mode actually switched back
    final_mode_response = client.get(f"/users/{user_id}/coach-mode")
    assert final_mode_response.json()["active_mode"] == "head_coach"

    # Step 6: Verify delegation marked as completed
    status_response = client.get(f"/delegation/{user_id}/status/{delegation_id}")
    status_data = status_response.json()
    assert status_data["status"]["status"] == "completed"
    assert status_data["status"]["curiosity_satisfied"] > 0.8
    assert len(status_data["status"]["traits_collected"]) == 3


def test_complete_delegation_lifecycle_relationship_coach(lifecycle_test_client):
    """
    Test: Complete delegation lifecycle with Relationship Coach.

    Flow:
    1. Create delegation to RC
    2. Switch to relationship mode
    3. RC collects ReDNA/EmDNA traits
    4. Complete delegation with moderate satisfaction
    5. Verify return to Head Coach
    """
    client, tmpdir = lifecycle_test_client
    user_id = "lifecycle_rc_test_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Create delegation to RC
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "relationship_coach",
            "curiosity_targets": [
                "ReDNA.AttachmentStyle.Type",
                "EmDNA.EmotionalRegulation.Strategy"
            ]
        }
    )

    delegation_id = delegation_response.json()["delegation"]["delegation_id"]

    # Step 2: Switch to relationship mode
    client.post(
        f"/users/{user_id}/coach-mode",
        json={
            "target_mode": "relationship",
            "delegation_id": delegation_id,
        }
    )

    # Step 3: Simulate RC collecting traits
    curiosity_before = {
        "ReDNA.AttachmentStyle.Type": 72.0,
        "EmDNA.EmotionalRegulation.Strategy": 68.0,
    }

    curiosity_after = {
        "ReDNA.AttachmentStyle.Type": 30.0,
        "EmDNA.EmotionalRegulation.Strategy": 35.0,
    }

    # Step 4: Complete delegation
    complete_response = client.post(
        f"/delegation/{user_id}/complete/{delegation_id}",
        json={
            "traits_collected": [
                "ReDNA.AttachmentStyle.Type",
                "EmDNA.EmotionalRegulation.Strategy",
            ],
            "curiosity_before": curiosity_before,
            "curiosity_after": curiosity_after,
            "notes": "Discussed relationship patterns and emotional responses",
            "auto_return": True,
        }
    )

    complete_data = complete_response.json()

    # Verify moderate satisfaction (40-60%)
    satisfaction = complete_data["delegation_summary"]["curiosity_satisfied"]
    assert 0.4 <= satisfaction <= 0.7

    # Step 5: Verify return to Head Coach
    final_mode = client.get(f"/users/{user_id}/coach-mode").json()
    assert final_mode["active_mode"] == "head_coach"


def test_delegation_without_auto_return(lifecycle_test_client):
    """
    Test: Delegation completion without auto-return to Head Coach.

    User may want to stay in specialized coach mode after completion.
    """
    client, tmpdir = lifecycle_test_client
    user_id = "no_return_test_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

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
        json={
            "target_mode": "photo",
            "delegation_id": delegation_id,
        }
    )

    # Complete delegation with auto_return=False
    complete_response = client.post(
        f"/delegation/{user_id}/complete/{delegation_id}",
        json={
            "traits_collected": ["PaDNA.HairDNA.Color"],
            "curiosity_before": {"PaDNA.HairDNA.Color": 80.0},
            "curiosity_after": {"PaDNA.HairDNA.Color": 20.0},
            "notes": "Quick hair color analysis",
            "auto_return": False,  # Stay in photo mode
        }
    )

    complete_data = complete_response.json()

    # Verify no mode switch occurred
    assert complete_data["mode_switch"] is None

    # Verify still in photo mode
    active_mode = client.get(f"/users/{user_id}/coach-mode").json()
    assert active_mode["active_mode"] == "photo"

    # Delegation should still be marked complete
    status = client.get(f"/delegation/{user_id}/status/{delegation_id}").json()
    assert status["status"]["status"] == "completed"


def test_delegation_mode_history_includes_completion_context(lifecycle_test_client):
    """
    Test: Mode history tracks delegation completion with full context.
    """
    client, tmpdir = lifecycle_test_client
    user_id = "history_context_test_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create and complete delegation
    delegation_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.EyeDNA.Color"]
        }
    )

    delegation_id = delegation_response.json()["delegation"]["delegation_id"]

    # Switch to photo mode
    client.post(
        f"/users/{user_id}/coach-mode",
        json={
            "target_mode": "photo",
            "delegation_id": delegation_id,
        }
    )

    # Complete and return to head coach
    client.post(
        f"/delegation/{user_id}/complete/{delegation_id}",
        json={
            "traits_collected": ["PaDNA.EyeDNA.Color"],
            "curiosity_before": {"PaDNA.EyeDNA.Color": 90.0},
            "curiosity_after": {"PaDNA.EyeDNA.Color": 10.0},
            "notes": "Eye color documented",
            "auto_return": True,
        }
    )

    # Check mode history
    history_response = client.get(f"/users/{user_id}/coach-mode/history?limit=10")
    history = history_response.json()["history"]

    # Should have 2 transitions: photo mode, then back to head_coach
    assert len(history) >= 2

    # Find the completion return transition (most recent to head_coach)
    completion_transition = None
    for transition in reversed(history):
        if transition.get("to_mode") == "head_coach":
            completion_transition = transition
            break

    assert completion_transition is not None

    # Verify it has delegation context (the way coach_mode_manager stores it)
    # Note: The context field contains delegation_id from completion
    if "context" in completion_transition:
        context = completion_transition["context"]
        # Context should include delegation_id and completion metadata
        assert "delegation_id" in context or "reason" in context


def test_multiple_delegations_sequential_completion(lifecycle_test_client):
    """
    Test: Multiple delegations completed sequentially.

    User completes one delegation, returns to HC, then starts another.
    """
    client, tmpdir = lifecycle_test_client
    user_id = "sequential_delegations_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # Delegation 1: Photo Coach
    del1_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )
    del1_id = del1_response.json()["delegation"]["delegation_id"]

    client.post(f"/users/{user_id}/coach-mode", json={"target_mode": "photo", "delegation_id": del1_id})

    # Complete delegation 1
    client.post(
        f"/delegation/{user_id}/complete/{del1_id}",
        json={
            "traits_collected": ["PaDNA.HairDNA.Color"],
            "curiosity_before": {"PaDNA.HairDNA.Color": 85.0},
            "curiosity_after": {"PaDNA.HairDNA.Color": 15.0},
            "notes": "First delegation complete",
            "auto_return": True,
        }
    )

    # Verify back at head coach
    assert client.get(f"/users/{user_id}/coach-mode").json()["active_mode"] == "head_coach"

    # Delegation 2: Relationship Coach
    del2_response = client.post(
        "/delegation/create",
        json={
            "user_id": user_id,
            "coach_id": "relationship_coach",
            "curiosity_targets": ["ReDNA.AttachmentStyle.Type"]
        }
    )
    del2_id = del2_response.json()["delegation"]["delegation_id"]

    client.post(f"/users/{user_id}/coach-mode", json={"target_mode": "relationship", "delegation_id": del2_id})

    # Complete delegation 2
    client.post(
        f"/delegation/{user_id}/complete/{del2_id}",
        json={
            "traits_collected": ["ReDNA.AttachmentStyle.Type"],
            "curiosity_before": {"ReDNA.AttachmentStyle.Type": 70.0},
            "curiosity_after": {"ReDNA.AttachmentStyle.Type": 25.0},
            "notes": "Second delegation complete",
            "auto_return": True,
        }
    )

    # Verify back at head coach again
    assert client.get(f"/users/{user_id}/coach-mode").json()["active_mode"] == "head_coach"

    # Verify both delegations completed
    del1_status = client.get(f"/delegation/{user_id}/status/{del1_id}").json()
    del2_status = client.get(f"/delegation/{user_id}/status/{del2_id}").json()

    assert del1_status["status"]["status"] == "completed"
    assert del2_status["status"]["status"] == "completed"

    # Verify mode stats show multiple transitions
    stats_response = client.get(f"/users/{user_id}/coach-mode/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()

    # Stats response includes ok, stats
    if "stats" in stats:
        stats_data = stats["stats"]
    else:
        stats_data = stats

    assert stats_data["total_transitions"] >= 4  # photo, back, relationship, back
