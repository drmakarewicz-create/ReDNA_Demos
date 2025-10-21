"""
Test suite for debug endpoint authentication (Phase 9)

Tests authentication requirements for /core/debug/* endpoints.
"""
import pytest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_storage():
    """Mock graph storage to avoid file system dependencies."""
    from ReDNACoreDemo.core.graph.schemas import BeliefGraph

    class MockStorage:
        def load_user_graph(self, user_id: str) -> BeliefGraph:
            return BeliefGraph(nodes=[], edges=[])

    return MockStorage()


@pytest.fixture
def client_no_auth(mock_storage):
    """
    Test client with debug routes enabled but NO auth token required.
    Simulates dev mode.
    """
    with patch.dict(os.environ, {
        'DEBUG_ROUTES_ENABLED': 'true',
        'X_REDNA_DEBUG_TOKEN': ''  # Empty = no auth
    }):
        # Force reload of module to pick up new env vars
        import importlib
        from ReDNACoreDemo.core.graph import debug_api
        importlib.reload(debug_api)

        # Mock storage
        with patch('ReDNACoreDemo.core.graph.debug_api.get_graph_storage', return_value=mock_storage):
            from ReDNACoreDemo.core.api import create_app
            app = create_app()
            yield TestClient(app)


@pytest.fixture
def client_with_auth(mock_storage):
    """
    Test client with debug routes enabled AND auth token required.
    Simulates production mode with auth.
    """
    with patch.dict(os.environ, {
        'DEBUG_ROUTES_ENABLED': 'true',
        'X_REDNA_DEBUG_TOKEN': 'test-secret-token-12345'
    }):
        # Force reload of module to pick up new env vars
        import importlib
        from ReDNACoreDemo.core.graph import debug_api
        importlib.reload(debug_api)

        # Mock storage
        with patch('ReDNACoreDemo.core.graph.debug_api.get_graph_storage', return_value=mock_storage):
            from ReDNACoreDemo.core.api import create_app
            app = create_app()
            yield TestClient(app)


@pytest.fixture
def client_disabled(mock_storage):
    """
    Test client with debug routes DISABLED.
    Simulates production lockdown.
    """
    with patch.dict(os.environ, {
        'DEBUG_ROUTES_ENABLED': 'false',
        'X_REDNA_DEBUG_TOKEN': ''
    }):
        # Force reload of module to pick up new env vars
        import importlib
        from ReDNACoreDemo.core.graph import debug_api
        importlib.reload(debug_api)

        # Mock storage
        with patch('ReDNACoreDemo.core.graph.debug_api.get_graph_storage', return_value=mock_storage):
            from ReDNACoreDemo.core.api import create_app
            app = create_app()
            yield TestClient(app)


class TestDebugAuthNoToken:
    """Test debug endpoints when no auth token is configured (dev mode)."""

    def test_health_allowed_without_token(self, client_no_auth):
        """Test: /core/debug/health is accessible without token in dev mode."""
        response = client_no_auth.get("/core/debug/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["module"] == "debug"
        assert data["enabled"] is True
        assert data["auth_required"] is False  # No token configured

    def test_rr_audit_allowed_without_token(self, client_no_auth):
        """Test: /core/debug/rr_audit/{user_id} is accessible without token in dev mode."""
        response = client_no_auth.get("/core/debug/rr_audit/test_user")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user"
        assert "summary" in data

    def test_ucn_propagation_allowed_without_token(self, client_no_auth):
        """Test: /core/debug/ucn_propagation/{user_id} is accessible without token in dev mode."""
        response = client_no_auth.get("/core/debug/ucn_propagation/test_user")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user"
        assert "summary" in data


class TestDebugAuthWithToken:
    """Test debug endpoints when auth token IS configured (production mode)."""

    def test_health_denied_without_token(self, client_with_auth):
        """Test: /core/debug/health returns 403 when token is required but not provided."""
        response = client_with_auth.get("/core/debug/health")
        assert response.status_code == 403
        data = response.json()
        assert "X-REDNA-DEBUG-TOKEN" in data["detail"]

    def test_health_denied_with_wrong_token(self, client_with_auth):
        """Test: /core/debug/health returns 403 with wrong token."""
        response = client_with_auth.get(
            "/core/debug/health",
            headers={"X-REDNA-DEBUG-TOKEN": "wrong-token"}
        )
        assert response.status_code == 403
        data = response.json()
        assert "Invalid debug token" in data["detail"]

    def test_health_allowed_with_correct_token(self, client_with_auth):
        """Test: /core/debug/health returns 200 with correct token."""
        response = client_with_auth.get(
            "/core/debug/health",
            headers={"X-REDNA-DEBUG-TOKEN": "test-secret-token-12345"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["auth_required"] is True  # Token configured

    def test_rr_audit_denied_without_token(self, client_with_auth):
        """Test: /core/debug/rr_audit/{user_id} returns 403 without token."""
        response = client_with_auth.get("/core/debug/rr_audit/test_user")
        assert response.status_code == 403

    def test_rr_audit_allowed_with_token(self, client_with_auth):
        """Test: /core/debug/rr_audit/{user_id} returns 200 with token."""
        response = client_with_auth.get(
            "/core/debug/rr_audit/test_user",
            headers={"X-REDNA-DEBUG-TOKEN": "test-secret-token-12345"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user"

    def test_ucn_propagation_denied_without_token(self, client_with_auth):
        """Test: /core/debug/ucn_propagation/{user_id} returns 403 without token."""
        response = client_with_auth.get("/core/debug/ucn_propagation/test_user")
        assert response.status_code == 403

    def test_ucn_propagation_allowed_with_token(self, client_with_auth):
        """Test: /core/debug/ucn_propagation/{user_id} returns 200 with token."""
        response = client_with_auth.get(
            "/core/debug/ucn_propagation/test_user",
            headers={"X-REDNA-DEBUG-TOKEN": "test-secret-token-12345"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user"


class TestDebugRoutesDisabled:
    """Test debug endpoints when routes are completely disabled."""

    def test_health_returns_503_when_disabled(self, client_disabled):
        """Test: /core/debug/health returns 503 when DEBUG_ROUTES_ENABLED=false."""
        response = client_disabled.get("/core/debug/health")
        assert response.status_code == 503
        data = response.json()
        assert "Debug routes are disabled" in data["detail"]

    def test_health_returns_503_even_with_token(self, client_disabled):
        """Test: /core/debug/health returns 503 even with valid token when disabled."""
        response = client_disabled.get(
            "/core/debug/health",
            headers={"X-REDNA-DEBUG-TOKEN": "any-token"}
        )
        assert response.status_code == 503

    def test_rr_audit_returns_503_when_disabled(self, client_disabled):
        """Test: /core/debug/rr_audit/{user_id} returns 503 when disabled."""
        response = client_disabled.get("/core/debug/rr_audit/test_user")
        assert response.status_code == 503

    def test_ucn_propagation_returns_503_when_disabled(self, client_disabled):
        """Test: /core/debug/ucn_propagation/{user_id} returns 503 when disabled."""
        response = client_disabled.get("/core/debug/ucn_propagation/test_user")
        assert response.status_code == 503


class TestDebugAuthBehavior:
    """Test specific auth behavior edge cases."""

    def test_case_sensitive_token(self, client_with_auth):
        """Test: Token is case-sensitive."""
        response = client_with_auth.get(
            "/core/debug/health",
            headers={"X-REDNA-DEBUG-TOKEN": "TEST-SECRET-TOKEN-12345"}  # Wrong case
        )
        assert response.status_code == 403

    def test_header_name_case_insensitive(self, client_with_auth):
        """Test: Header name is case-insensitive (HTTP spec)."""
        response = client_with_auth.get(
            "/core/debug/health",
            headers={"x-redna-debug-token": "test-secret-token-12345"}  # Lowercase header
        )
        # FastAPI/Starlette normalizes header names, should work
        assert response.status_code == 200

    def test_empty_token_header_rejected(self, client_with_auth):
        """Test: Empty token header is rejected when token is required."""
        response = client_with_auth.get(
            "/core/debug/health",
            headers={"X-REDNA-DEBUG-TOKEN": ""}
        )
        assert response.status_code == 403


# Integration note: These tests mock storage to avoid file I/O.
# For full integration tests, run against live Core API with real storage.
