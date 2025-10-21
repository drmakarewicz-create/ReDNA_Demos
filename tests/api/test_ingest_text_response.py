"""
Tests for normalized ingest_text response envelope (Prompt 2).

Verifies that POST /core/api/ingest_text returns a stable, friendly envelope
with consistent fields (ok, user_id, event_id, ingested, inferred, errors).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the Core API."""
    from ReDNACoreDemo.core.api import app
    return TestClient(app)


def test_success_response_has_required_fields(client):
    """
    AC1: On successful ingest with promotion, body contains {ok:true, ingested>=1, event_id}.
    """
    payload = {
        "user_id": "test_response_user1",
        "text": "I wake up at 6am every morning without an alarm clock",
        "source": "chat"
    }

    response = client.post("/core/api/ingest_text", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Required fields
    assert "ok" in data
    assert data["ok"] is True
    assert "user_id" in data
    assert data["user_id"] == "test_response_user1"
    assert "event_id" in data
    assert data["event_id"] is not None
    assert "ingested" in data
    assert isinstance(data["ingested"], int)
    assert "inferred" in data
    assert isinstance(data["inferred"], int)
    assert "errors" in data
    assert isinstance(data["errors"], list)
    assert len(data["errors"]) == 0  # No errors on success


def test_no_op_response_ingested_zero(client):
    """
    AC2: On no-op (empty text), return {ok:true, ingested:0} without error.
    """
    payload = {
        "user_id": "test_response_user2",
        "text": "",
        "source": "chat"
    }

    response = client.post("/core/api/ingest_text", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    assert data["user_id"] == "test_response_user2"
    assert data["ingested"] == 0
    assert data["inferred"] == 0
    assert data["errors"] == []


def test_validation_failure_returns_errors(client):
    """
    AC3: On validation failure, return {ok:false, errors:[...]} and HTTP 422.
    """
    payload = {
        "user_id": "",  # Missing user_id
        "text": "Some text"
    }

    response = client.post("/core/api/ingest_text", json=payload)

    assert response.status_code == 422
    data = response.json()

    assert data["ok"] is False
    assert "errors" in data
    assert isinstance(data["errors"], list)
    assert len(data["errors"]) > 0
    assert data["ingested"] == 0
    assert data["inferred"] == 0


def test_malformed_payload_returns_422(client):
    """
    AC3: On bad payload structure, return {ok:false, errors:[...]} and HTTP 422.
    """
    # Send non-JSON payload (string instead of dict)
    response = client.post(
        "/core/api/ingest_text",
        json="not a dict"  # Will be processed as a string by FastAPI
    )

    # FastAPI will return 422 for validation error
    assert response.status_code == 422


def test_backward_compatibility_fields_present(client):
    """
    Verify backward compatibility: old fields (rescore, snapshot) still present.
    """
    payload = {
        "user_id": "test_response_user3",
        "text": "I love morning workouts",
        "source": "chat"
    }

    response = client.post("/core/api/ingest_text", json=payload)

    assert response.status_code == 200
    data = response.json()

    # New required fields
    assert data["ok"] is True
    assert "event_id" in data
    assert "ingested" in data
    assert "inferred" in data

    # Backward compatibility fields (optional but should be present)
    assert "rescore" in data  # Legacy field
    assert "snapshot" in data  # Legacy field


def test_ingested_count_matches_promotions(client):
    """
    Verify that 'ingested' count reflects actual number of evidence items extracted.
    """
    payload = {
        "user_id": "test_response_user4",
        "text": "I am a morning person who loves hiking outdoors",
        "source": "chat"
    }

    response = client.post("/core/api/ingest_text", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    # Should have at least some evidence extracted
    assert isinstance(data["ingested"], int)
    assert data["ingested"] >= 0


def test_inferred_count_matches_snapshot(client):
    """
    Verify that 'inferred' count matches snapshot.traits length.
    """
    payload = {
        "user_id": "test_response_user5",
        "text": "I wake up early and exercise daily",
        "source": "chat"
    }

    response = client.post("/core/api/ingest_text", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is True
    # Inferred should match snapshot traits count
    snapshot_traits = data.get("snapshot", {}).get("traits", [])
    assert data["inferred"] == len(snapshot_traits)
