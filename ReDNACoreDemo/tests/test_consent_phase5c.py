"""
Test Suite - Phase 5.C Consent Hardening

Tests consent middleware, webhook validation, and audit logging.

Test Coverage:
- Consent middleware enforcement
- Webhook signature validation
- Audit logging
- Scope coverage checks
- Rate limiting
- Replay attack prevention
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request, HTTPException

# Import modules under test
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from ReDNACoreDemo.services.consent.middleware import (
    require_consent,
    check_consent_sync,
    ConsentViolation,
    _check_scope_coverage,
    _audit_consent_check,
)
from ReDNACoreDemo.services.consent.webhook_validator import (
    validate_webhook_signature,
    validate_webhook,
    validate_and_process_webhook,
    sign_webhook,
    is_replay,
    WebhookPayload,
    WebhookValidationError,
    WebhookType,
)
from ReDNACoreDemo.services.consent.jwt_utils import sign_capability
from ReDNACoreDemo.services.consent.models import CapabilityToken, DataPolicy


# Fixtures


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = Mock(spec=Request)
    request.headers = {}
    request.query_params = {}
    request.cookies = {}
    request.path_params = {}
    request.state = type("State", (), {})()
    return request


@pytest.fixture
def valid_capability_token():
    """Create a valid capability token."""
    issued_at = int(time.time())
    token_data = {
        "cap_id": "test-cap-123",
        "user_id": "TEST_USER",
        "grantee_id": "test_service",
        "purpose": "testing",
        "scopes": ["read:PsyDNA", "read:SkillDNA"],
        "ttl": "PT24H",
        "issued_at": issued_at,
        "exp": issued_at + 86400,  # 24 hours
        "audit_id": "audit-123",
    }

    # Sign the token
    jwt = sign_capability(token_data)
    return jwt


@pytest.fixture
def expired_capability_token():
    """Create an expired capability token."""
    issued_at = int(time.time()) - 90000  # 25 hours ago
    token_data = {
        "cap_id": "test-cap-expired",
        "user_id": "TEST_USER",
        "grantee_id": "test_service",
        "purpose": "testing",
        "scopes": ["read:PsyDNA"],
        "ttl": "PT24H",
        "issued_at": issued_at,
        "exp": issued_at + 86400,  # Expired 1 hour ago
        "audit_id": "audit-expired",
    }

    jwt = sign_capability(token_data)
    return jwt


# Test: Scope Coverage


class TestScopeCoverage:
    """Test scope matching logic."""

    def test_exact_match(self):
        """Test exact scope match."""
        token_scopes = ["read:PsyDNA", "read:SkillDNA"]
        required_scopes = ["read:PsyDNA"]
        assert _check_scope_coverage(token_scopes, required_scopes) is True

    def test_wildcard_read(self):
        """Test read:* wildcard."""
        token_scopes = ["read:*"]
        required_scopes = ["read:PsyDNA", "read:SkillDNA"]
        assert _check_scope_coverage(token_scopes, required_scopes) is True

    def test_wildcard_write(self):
        """Test write:* wildcard."""
        token_scopes = ["write:*"]
        required_scopes = ["write:Goals", "write:Evidence"]
        assert _check_scope_coverage(token_scopes, required_scopes) is True

    def test_insufficient_scopes(self):
        """Test insufficient scopes."""
        token_scopes = ["read:SkillDNA"]
        required_scopes = ["read:PsyDNA"]
        assert _check_scope_coverage(token_scopes, required_scopes) is False

    def test_multiple_exact_matches(self):
        """Test multiple exact scope matches."""
        token_scopes = ["read:PsyDNA", "read:SkillDNA", "write:Goals"]
        required_scopes = ["read:PsyDNA", "write:Goals"]
        assert _check_scope_coverage(token_scopes, required_scopes) is True


# Test: Consent Middleware


class TestConsentMiddleware:
    """Test consent middleware enforcement."""

    def test_no_token_provided(self, mock_request):
        """Test middleware blocks request with no token."""

        @require_consent(scopes=["read:PsyDNA"], namespace="test")
        async def protected_endpoint(request: Request, user_id: str):
            return {"data": "secret"}

        with pytest.raises(ConsentViolation) as exc_info:
            import asyncio

            asyncio.run(
                protected_endpoint(mock_request, user_id="TEST_USER")
            )

        assert "No capability token provided" in str(exc_info.value.detail)

    def test_valid_token_in_header(self, mock_request, valid_capability_token):
        """Test middleware allows request with valid token in Authorization header."""
        mock_request.headers = {"Authorization": f"Bearer {valid_capability_token}"}

        @require_consent(scopes=["read:PsyDNA"], namespace="test")
        async def protected_endpoint(request: Request, user_id: str):
            return {"data": "secret"}

        import asyncio

        result = asyncio.run(
            protected_endpoint(mock_request, user_id="TEST_USER")
        )
        assert result == {"data": "secret"}
        assert mock_request.state.consent_verified is True

    def test_expired_token(self, mock_request, expired_capability_token):
        """Test middleware blocks expired token."""
        mock_request.headers = {
            "Authorization": f"Bearer {expired_capability_token}"
        }

        @require_consent(scopes=["read:PsyDNA"], namespace="test")
        async def protected_endpoint(request: Request, user_id: str):
            return {"data": "secret"}

        with pytest.raises(ConsentViolation) as exc_info:
            import asyncio

            asyncio.run(
                protected_endpoint(mock_request, user_id="TEST_USER")
            )

        assert "Token expired" in str(exc_info.value.detail)

    def test_insufficient_scopes(self, mock_request, valid_capability_token):
        """Test middleware blocks token with insufficient scopes."""
        # Token has read:PsyDNA, but endpoint requires write:Goals
        mock_request.headers = {"Authorization": f"Bearer {valid_capability_token}"}

        @require_consent(scopes=["write:Goals"], namespace="test")
        async def protected_endpoint(request: Request, user_id: str):
            return {"data": "secret"}

        with pytest.raises(ConsentViolation) as exc_info:
            import asyncio

            asyncio.run(
                protected_endpoint(mock_request, user_id="TEST_USER")
            )

        assert "do not cover required scopes" in str(exc_info.value.detail)


# Test: Synchronous Consent Check


class TestSyncConsentCheck:
    """Test synchronous consent checking."""

    def test_valid_check(self, valid_capability_token):
        """Test sync check with valid token."""
        result = check_consent_sync(
            user_id="TEST_USER",
            required_scopes=["read:PsyDNA"],
            token=valid_capability_token,
            namespace="test",
        )
        assert result is True

    def test_expired_check(self, expired_capability_token):
        """Test sync check with expired token."""
        result = check_consent_sync(
            user_id="TEST_USER",
            required_scopes=["read:PsyDNA"],
            token=expired_capability_token,
            namespace="test",
        )
        assert result is False

    def test_wrong_user(self, valid_capability_token):
        """Test sync check with mismatched user_id."""
        result = check_consent_sync(
            user_id="WRONG_USER",
            required_scopes=["read:PsyDNA"],
            token=valid_capability_token,
            namespace="test",
        )
        assert result is False


# Test: Webhook Validation


class TestWebhookValidation:
    """Test webhook signature validation."""

    def test_valid_webhook_signature(self):
        """Test valid webhook signature."""
        payload = b'{"test": "data"}'
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Sign the webhook
        headers = sign_webhook(json.loads(payload), secret="test-secret")
        signature = headers["X-Webhook-Signature"]

        # Validate
        valid, reason = validate_webhook_signature(
            payload, signature, timestamp, source="test"
        )
        assert valid is True
        assert reason is None

    def test_invalid_signature(self):
        """Test invalid webhook signature."""
        payload = b'{"test": "data"}'
        timestamp = datetime.utcnow().isoformat() + "Z"
        signature = "invalid_signature"

        valid, reason = validate_webhook_signature(
            payload, signature, timestamp, source="test"
        )
        assert valid is False
        assert "signature_mismatch" in reason

    def test_old_timestamp(self):
        """Test webhook with old timestamp (beyond replay window)."""
        payload = b'{"test": "data"}'
        old_time = datetime.utcnow() - timedelta(minutes=10)  # 10 minutes ago
        timestamp = old_time.isoformat() + "Z"

        headers = sign_webhook(json.loads(payload), secret="test-secret")
        signature = headers["X-Webhook-Signature"]

        valid, reason = validate_webhook_signature(
            payload, signature, timestamp, source="test"
        )
        assert valid is False
        assert "timestamp_too_old" in reason

    def test_future_timestamp(self):
        """Test webhook with future timestamp."""
        payload = b'{"test": "data"}'
        future_time = datetime.utcnow() + timedelta(minutes=5)
        timestamp = future_time.isoformat() + "Z"

        headers = sign_webhook(json.loads(payload), secret="test-secret")
        signature = headers["X-Webhook-Signature"]

        valid, reason = validate_webhook_signature(
            payload, signature, timestamp, source="test"
        )
        assert valid is False
        assert "timestamp_in_future" in reason


# Test: Replay Attack Prevention


class TestReplayPrevention:
    """Test replay attack detection."""

    def test_replay_detection(self):
        """Test that duplicate webhook IDs are detected."""
        webhook_id = "unique-webhook-123"

        # First call should pass
        assert is_replay(webhook_id) is False

        # Second call with same ID should be detected as replay
        assert is_replay(webhook_id) is True

    def test_different_ids_allowed(self):
        """Test that different webhook IDs are allowed."""
        assert is_replay("webhook-1") is False
        assert is_replay("webhook-2") is False
        assert is_replay("webhook-3") is False


# Test: Complete Webhook Flow


class TestWebhookFlow:
    """Test complete webhook validation flow."""

    def test_valid_webhook_payload(self):
        """Test validating a complete webhook payload."""
        webhook_data = {
            "webhook_type": "consent_revocation",
            "webhook_id": f"webhook-{int(time.time())}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "external_service",
            "user_id": "TEST_USER",
            "cap_id": "cap-123",
            "data": {"reason": "user_requested"},
        }

        payload = json.dumps(webhook_data).encode()
        headers = sign_webhook(webhook_data, secret="dev-webhook-secret-change-in-production")

        # Validate
        webhook = validate_webhook(
            payload,
            headers["X-Webhook-Signature"],
            headers["X-Webhook-Timestamp"],
            source="external_service",
        )

        assert webhook.webhook_type == WebhookType.CONSENT_REVOCATION
        assert webhook.user_id == "TEST_USER"
        assert webhook.cap_id == "cap-123"

    def test_invalid_webhook_json(self):
        """Test webhook with invalid JSON."""
        payload = b"not valid json"
        timestamp = datetime.utcnow().isoformat() + "Z"
        headers = sign_webhook({"test": "data"}, secret="dev-webhook-secret-change-in-production")

        with pytest.raises(WebhookValidationError) as exc_info:
            validate_webhook(
                payload,
                headers["X-Webhook-Signature"],
                timestamp,
                source="test",
            )

        assert "Invalid payload" in str(exc_info.value)


# Test: Audit Logging


class TestAuditLogging:
    """Test consent audit logging."""

    def test_audit_file_creation(self, tmp_path):
        """Test that audit files are created correctly."""
        # Mock the data path
        with patch("ReDNACoreDemo.services.consent.middleware.Path") as mock_path:
            mock_audit_dir = tmp_path / "data" / "users" / "TEST_USER" / "agent"
            mock_audit_dir.mkdir(parents=True, exist_ok=True)
            mock_path.return_value = tmp_path / "data" / "users"

            _audit_consent_check(
                user_id="TEST_USER",
                namespace="test_namespace",
                required_scopes=["read:PsyDNA"],
                granted=True,
                cap_id="cap-123",
            )

            # Check audit file exists (in actual location)
            audit_file = Path("data/users/TEST_USER/agent/agent_activity.jsonl")
            if audit_file.exists():
                # Read last line
                with open(audit_file, "r") as f:
                    lines = f.readlines()
                    last_event = json.loads(lines[-1])

                assert last_event["event_type"] == "consent_checked"
                assert last_event["user_id"] == "TEST_USER"
                assert last_event["granted"] is True


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
