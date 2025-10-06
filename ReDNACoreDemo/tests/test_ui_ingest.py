# ReDNACoreDemo/tests/test_ui_ingest.py
"""
Unit tests for /ui/ingest/text and /ui/ingest/json endpoints.
Tests provenance logging, UCNRR error handling, and edge cases.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import os


# Create a test client with mocked storage
@pytest.fixture
def client():
    """FastAPI test client with temporary storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override storage directory for tests
        os.environ["CORE_STORAGE_ROOT"] = tmpdir

        # Import after setting env var
        from ReDNACoreDemo.core.api import build_app
        app = build_app()

        yield TestClient(app)


@pytest.fixture
def mock_ucnrr_success():
    """Mock successful UCNRR response."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "ok": True,
        "user_id": "test_user",
        "rr_by_trait": {
            "PaDNA.EyeDNA.IrisColor": 850.0,
        },
        "curiosity_by_trait": {
            "PaDNA.EyeDNA.IrisColor": 0.15,
        },
        "global_curiosity": 0.15,
    }
    return mock_response


@pytest.fixture
def mock_ucnrr_error():
    """Mock UCNRR connection error."""
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 500
    return mock_response


def test_ingest_text_simple_string(client, mock_ucnrr_success):
    """Test POST /ui/ingest/text with simple string."""
    with patch("ReDNACoreDemo.core.api.requests.post", return_value=mock_ucnrr_success):
        payload = {
            "user_id": "test_user_001",
            "text": "PaDNA.EyeDNA.IrisColor=Blue",
        }

        response = client.post("/ui/ingest/text", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert data["user_id"] == "test_user_001"
        assert "event_written" in data
        assert data["status"] == "accepted"
        assert data["rescore"]["ok"] is True


def test_ingest_text_missing_user_id(client):
    """Test POST /ui/ingest/text without user_id returns 400."""
    payload = {
        "text": "Some text",
    }

    response = client.post("/ui/ingest/text", json=payload)
    assert response.status_code == 400
    assert "user_id and text are required" in response.json()["message"]


def test_ingest_text_missing_text(client):
    """Test POST /ui/ingest/text without text returns 400."""
    payload = {
        "user_id": "test_user_002",
    }

    response = client.post("/ui/ingest/text", json=payload)
    assert response.status_code == 400


def test_ingest_text_ucnrr_connection_error(client):
    """Test /ui/ingest/text logs failure when UCNRR connection fails."""
    import requests
    with patch("ReDNACoreDemo.core.api.requests.post", side_effect=requests.exceptions.ConnectionError("UCNRR not available")):
        payload = {
            "user_id": "test_user_003",
            "text": "Test text",
        }

        response = client.post("/ui/ingest/text", json=payload)

        # Core should not crash - it logs the error
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "Connection error" in data["rescore"]["error"]


def test_ingest_text_ucnrr_http_500(client, mock_ucnrr_error):
    """Test /ui/ingest/text handles UCNRR 500 error gracefully."""
    with patch("ReDNACoreDemo.core.api.requests.post", return_value=mock_ucnrr_error):
        payload = {
            "user_id": "test_user_004",
            "text": "Test text",
        }

        response = client.post("/ui/ingest/text", json=payload)

        # Core logs failure but doesn't crash
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "HTTP 500" in data["rescore"]["error"]


def test_ingest_json_structured_payload(client, mock_ucnrr_success):
    """Test POST /ui/ingest/json with structured trait payload."""
    with patch("ReDNACoreDemo.core.api.requests.post", return_value=mock_ucnrr_success):
        payload = {
            "user_id": "test_user_005",
            "traits": [
                {"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue", "rr": 850.0},
                {"id": "PaDNA.HairDNA.Color", "value": "Brown", "rr": 700.0},
            ],
        }

        response = client.post("/ui/ingest/json", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert data["user_id"] == "test_user_005"
        assert data["traits_count"] == 2
        assert data["status"] == "accepted"


def test_ingest_json_missing_user_id(client):
    """Test POST /ui/ingest/json without user_id returns 400."""
    payload = {
        "traits": [{"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue"}],
    }

    response = client.post("/ui/ingest/json", json=payload)
    assert response.status_code == 400
    assert "user_id and traits (list) are required" in response.json()["message"]


def test_ingest_json_missing_traits(client):
    """Test POST /ui/ingest/json without traits returns 400."""
    payload = {
        "user_id": "test_user_006",
    }

    response = client.post("/ui/ingest/json", json=payload)
    assert response.status_code == 400


def test_ingest_json_traits_not_list(client):
    """Test POST /ui/ingest/json with traits as non-list returns 400."""
    payload = {
        "user_id": "test_user_007",
        "traits": "not a list",
    }

    response = client.post("/ui/ingest/json", json=payload)
    assert response.status_code == 400


def test_ingest_json_ucnrr_connection_error(client):
    """Test /ui/ingest/json logs failure when UCNRR fails."""
    import requests
    with patch("ReDNACoreDemo.core.api.requests.post", side_effect=requests.exceptions.ConnectionError("UCNRR unreachable")):
        payload = {
            "user_id": "test_user_008",
            "traits": [{"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue"}],
        }

        response = client.post("/ui/ingest/json", json=payload)

        # Should not crash - logs failure
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "Connection error" in data["rescore"]["error"]


def test_ingest_json_ucnrr_timeout(client):
    """Test /ui/ingest/json handles timeout gracefully."""
    import requests
    with patch("ReDNACoreDemo.core.api.requests.post", side_effect=requests.exceptions.Timeout("Request timed out")):
        payload = {
            "user_id": "test_user_009",
            "traits": [{"id": "PaDNA.EyeDNA.IrisColor", "value": "Blue"}],
        }

        response = client.post("/ui/ingest/json", json=payload)

        # Should log timeout, not crash
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "Timeout" in data["rescore"]["error"]


def test_ingest_text_provenance_always_logged(client):
    """Test that provenance is always logged even when UCNRR fails."""
    with patch("ReDNACoreDemo.core.api.requests.post", side_effect=Exception("Unexpected error")):
        payload = {
            "user_id": "test_user_010",
            "text": "Test text for provenance",
        }

        response = client.post("/ui/ingest/text", json=payload)

        # Provenance logged, failure recorded
        data = response.json()
        assert "event_written" in data
        assert data["status"] == "failed"
        assert "rescore" in data
        assert "error" in data["rescore"]


def test_ingest_json_provenance_always_logged(client):
    """Test that JSON ingest provenance is always logged."""
    with patch("ReDNACoreDemo.core.api.requests.post", side_effect=Exception("Network failure")):
        payload = {
            "user_id": "test_user_011",
            "traits": [{"id": "PaDNA.EyeDNA.IrisColor", "value": "Green"}],
        }

        response = client.post("/ui/ingest/json", json=payload)

        # Provenance logged despite error
        data = response.json()
        assert "event_written" in data
        assert data["status"] == "failed"
        assert "Unexpected error" in data["rescore"]["error"] or "Network failure" in data["rescore"]["error"]
