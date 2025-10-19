"""
UCNRR Health and Selftest Validation

Ensures that UCNRR service responds with healthy status and passes self-test.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the UCNRR service."""
    from UCN_RR_Demo.ucnrr_app import app
    return TestClient(app)


def test_ucnrr_health_endpoint(client):
    """Ensure /health endpoint returns healthy status with prompt info."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ucnrr"
    assert "prompt_sha256" in data
    assert data["prompt_sha256"] != "none"
    assert "prompt_version" in data
    assert "llm_configured" in data


def test_ucnrr_selftest_passes(client):
    """Ensure /ucnrr/selftest passes with valid UCN score."""
    response = client.get("/ucnrr/selftest")
    assert response.status_code == 200

    data = response.json()
    assert data["ok"] is True, f"Selftest failed: {data}"
    assert "ucn" in data
    assert 0.75 <= data["ucn"] <= 0.95, f"UCN {data['ucn']} out of range [0.75, 0.95]"
    assert data["ucn_in_range"] is True
    assert "elapsed_ms" in data
    assert data["elapsed_ms"] < 5000, f"Selftest too slow: {data['elapsed_ms']}ms"


def test_ucnrr_selftest_returns_prompt_info(client):
    """Ensure selftest includes prompt SHA256 and LLM config."""
    response = client.get("/ucnrr/selftest")
    assert response.status_code == 200

    data = response.json()
    assert "prompt_sha256" in data
    assert data["prompt_sha256"] != "none"
    assert "llm_configured" in data
    assert isinstance(data["llm_configured"], bool)


def test_ucnrr_blue_eyes_test_case(client):
    """Verify the blue eyes canonical test case."""
    response = client.get("/ucnrr/selftest")
    assert response.status_code == 200

    data = response.json()
    assert data["test_case"] == "blue_eyes"
    assert data["trait_id"] == "PaDNA.EyeDNA.IrisColor"
    assert data["ucn"] == 0.8  # Expected UCN for direct self-report


def test_ucnrr_health_has_timestamp(client):
    """Ensure health endpoint includes timestamp."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "timestamp" in data
    # Timestamp should be ISO format
    assert "T" in data["timestamp"]


def test_ucnrr_prompt_loaded(client):
    """Ensure prompt is loaded on startup."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "prompt_loaded_at" in data
    assert data["prompt_loaded_at"] != "never", "Prompt was never loaded"
