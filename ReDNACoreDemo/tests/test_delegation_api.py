"""
Integration tests for Coach Delegation API endpoints
"""
import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def delegation_test_client():
    """Create test client with delegation endpoints (unique per test)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up test environment
        import os
        import sys
        os.environ["CORE_DATA_DIR"] = str(tmpdir)

        # Clear any cached modules to ensure fresh imports
        for module_name in list(sys.modules.keys()):
            if module_name.startswith("core.coach_delegation"):
                del sys.modules[module_name]

        # Import app (needs to be after env setup)
        from core.api import build_app
        app = build_app()
        client = TestClient(app)

        # Create test user with some data
        user_dir = Path(tmpdir) / "users" / "test_user"
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create resolved.json with some traits and tolerance
        resolved = {
            "resolved": {
                "PaDNA.HairDNA.Color": {
                    "value": "Brown",
                    "ucn": 65,
                    "rr": 45,
                    "curiosity": 55
                },
                "ReDNA.ToleranceForNudging": {
                    "value": 0.7,
                    "ucn": 80,
                    "rr": 80
                }
            }
        }
        with open(user_dir / "resolved.json", "w") as f:
            json.dump(resolved, f)

        # Create coach registry
        registry_path = Path(tmpdir) / ".." / "coach_registry.yaml"
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
    natural_domains:
      - "facial features"
    suitable_for_types:
      - trait
      - missing

availability:
  photo_coach: true
"""
        registry_path.write_text(registry_content)

        yield client, tmpdir


def test_analyze_delegation_endpoint(delegation_test_client):
    """Test /delegation/analyze endpoint."""
    client, tmpdir = delegation_test_client

    response = client.post(
        "/delegation/analyze",
        json={"user_id": "test_user"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert "should_delegate" in data
    assert "user_tolerance" in data
    assert "recommendations" in data


def test_create_delegation_endpoint(delegation_test_client):
    """Test /delegation/create endpoint."""
    client, tmpdir = delegation_test_client

    response = client.post(
        "/delegation/create",
        json={
            "user_id": "test_user",
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
            "context": {"delegation_reason": "high_curiosity"}
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert "delegation" in data
    delegation = data["delegation"]
    assert delegation["coach"] == "photo_coach"
    assert delegation["delegation_id"] != ""
    assert len(delegation["curiosity_targets"]) == 2


def test_get_delegation_status_endpoint(delegation_test_client):
    """Test /delegation/{user_id}/status/{delegation_id} endpoint."""
    client, tmpdir = delegation_test_client

    # Create delegation first
    create_response = client.post(
        "/delegation/create",
        json={
            "user_id": "test_user",
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )

    delegation_id = create_response.json()["delegation"]["delegation_id"]

    # Get status
    response = client.get(f"/delegation/test_user/status/{delegation_id}")

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert "status" in data
    status = data["status"]
    assert status["delegation_id"] == delegation_id
    assert status["coach"] == "photo_coach"
    assert status["status"] == "pending"


def test_get_active_delegations_endpoint(delegation_test_client):
    """Test /delegation/{user_id}/active endpoint."""
    client, tmpdir = delegation_test_client

    # Use unique user to avoid cross-test pollution
    test_user = "active_test_user"

    # Create user directory
    user_dir = Path(tmpdir) / "users" / test_user
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create two delegations
    client.post(
        "/delegation/create",
        json={
            "user_id": test_user,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )

    client.post(
        "/delegation/create",
        json={
            "user_id": test_user,
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.EyeDNA.Color"]
        }
    )

    # Get active delegations
    response = client.get(f"/delegation/{test_user}/active")

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert data["count"] == 2
    assert len(data["delegations"]) == 2


def test_complete_delegation_endpoint(delegation_test_client):
    """Test /delegation/{user_id}/complete/{delegation_id} endpoint."""
    client, tmpdir = delegation_test_client

    # Create delegation
    create_response = client.post(
        "/delegation/create",
        json={
            "user_id": "test_user",
            "coach_id": "photo_coach",
            "curiosity_targets": ["PaDNA.HairDNA.Color"]
        }
    )

    delegation_id = create_response.json()["delegation"]["delegation_id"]

    # Complete delegation
    response = client.post(
        f"/delegation/test_user/complete/{delegation_id}",
        json={
            "traits_collected": ["PaDNA.HairDNA.Color"],
            "curiosity_before": {"PaDNA.HairDNA.Color": 75},
            "curiosity_after": {"PaDNA.HairDNA.Color": 12},
            "notes": "Photo analysis completed"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert "message" in data

    # Verify status updated
    status_response = client.get(f"/delegation/test_user/status/{delegation_id}")
    status_data = status_response.json()
    assert status_data["status"]["status"] == "completed"


def test_create_delegation_missing_params(delegation_test_client):
    """Test /delegation/create with missing parameters."""
    client, tmpdir = delegation_test_client

    response = client.post(
        "/delegation/create",
        json={"user_id": "test_user"}  # Missing coach_id
    )

    assert response.status_code == 400
    data = response.json()
    assert data["ok"] is False
    assert "Missing user_id or coach_id" in data["message"]


def test_get_delegation_status_not_found(delegation_test_client):
    """Test /delegation/{user_id}/status/{delegation_id} with invalid ID."""
    client, tmpdir = delegation_test_client

    response = client.get("/delegation/test_user/status/invalid_id")

    assert response.status_code == 404
    data = response.json()
    assert "Delegation not found" in data["detail"]
