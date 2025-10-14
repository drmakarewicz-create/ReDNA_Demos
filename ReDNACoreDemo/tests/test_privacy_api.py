"""
Tests for DevX Privacy Dashboard API surface.
"""

import json
from typing import Any, Dict

import httpx
import pytest
from fastapi.testclient import TestClient

from ReDNACoreDemo.devx.backend.api import app
from ReDNACoreDemo.devx.backend import privacy_dashboard_api
from ReDNACoreDemo.core.permission_coach import permcoach_audit


class MockResponse:
    """Simple payload stub for httpx responses."""

    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload
        try:
            self.text = json.dumps(payload)
        except TypeError:
            self.text = str(payload)

    def json(self):
        return self._payload


class SuccessAsyncClient:
    """AsyncClient stub that returns canned responses."""

    def __init__(self, responses: Dict[str, MockResponse], *args, **kwargs):
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None, timeout=None):
        if "capabilities" in url:
            return self._responses["capabilities"]
        if "ledger" in url:
            return self._responses["ledger"]
        raise AssertionError(f"Unexpected URL: {url}")


class FailingAsyncClient:
    """AsyncClient stub that simulates network failure."""

    def __init__(self, *args, **kwargs):
        self.request = httpx.Request("GET", "http://consent.test")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None, timeout=None):
        raise httpx.RequestError("consent unavailable", request=self.request)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_privacy_summary_includes_capability_totals(monkeypatch, client):
    """Summary endpoint should surface capability_totals."""
    mock_responses = {
        "capabilities": MockResponse(
            200,
            [
                {"cap_id": "1", "revoked": False, "export_allowed": True},
                {"cap_id": "2", "revoked": True, "export_allowed": True},
                {"cap_id": "3", "revoked": False, "export_allowed": False},
            ],
        ),
        "ledger": MockResponse(
            200,
            [
                {"event_type": "grant", "timestamp": "2024-01-01T00:00:00Z"},
                {"event_type": "revoke", "timestamp": "2024-01-02T00:00:00Z"},
            ],
        ),
    }

    monkeypatch.setattr(
        privacy_dashboard_api.httpx,
        "AsyncClient",
        lambda *args, **kwargs: SuccessAsyncClient(mock_responses, *args, **kwargs),
    )
    monkeypatch.setattr(
        privacy_dashboard_api, "get_consent_service_url", lambda: "http://consent.test"
    )

    response = client.get("/devx/api/privacy/summary", params={"user_id": "TEST"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "TEST"
    assert payload["capability_totals"] == {
        "total": 3,
        "revoked": 1,
        "export_enabled": 1,
    }


def test_privacy_audit_endpoint_returns_expected_shape(monkeypatch, client):
    """Audit endpoint should proxy anomalies from PermCoach."""

    async def fake_audit_user(user_id: str):
        return {
            "user_id": user_id,
            "anomalies": [
                {"severity": "high"},
                {"severity": "medium"},
            ],
            "summary": {"severity_breakdown": {"high": 1, "medium": 1, "low": 0}},
        }

    monkeypatch.setattr(permcoach_audit, "audit_user", fake_audit_user)

    response = client.post("/devx/api/privacy/audit", params={"user_id": "TEST"})
    assert response.status_code == 200
    payload = response.json()
    assert "anomalies" in payload
    assert "summary" in payload
    assert payload["user_id"] == "TEST"


def test_privacy_summary_returns_503_when_consent_unavailable(monkeypatch, client):
    """Summary endpoint should bubble up Consent connectivity issues."""
    monkeypatch.setattr(
        privacy_dashboard_api.httpx, "AsyncClient", FailingAsyncClient
    )
    monkeypatch.setattr(
        privacy_dashboard_api, "get_consent_service_url", lambda: "http://consent.test"
    )

    response = client.get("/devx/api/privacy/summary", params={"user_id": "TEST"})
    assert response.status_code == 503
    payload = response.json()
    assert "Consent Service unavailable" in payload["detail"]
