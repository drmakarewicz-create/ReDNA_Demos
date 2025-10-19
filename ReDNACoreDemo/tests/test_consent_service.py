"""
Tests for Consent Service

Tests capability issuance, revocation, ledger, and JWT operations.
"""

import pytest
import asyncio
from datetime import datetime
import httpx

from services.consent.models import (
    CapabilityRequest,
    CapabilityToken,
    LedgerEventType,
    DataPolicy,
)
from services.consent.storage import ConsentStorage
from services.consent.jwt_utils import sign_capability, verify_capability, parse_ttl_to_seconds, compute_expiration


class TestJWTUtils:
    """Test JWT signing and verification."""

    def test_sign_and_verify_capability(self):
        """Test signing and verifying a capability JWT."""
        payload = {
            "cap_id": "test-cap-123",
            "user_id": "TEST",
            "grantee_id": "career_coach",
            "scopes": ["read:SkillDNA"],
            "exp": compute_expiration("PT24H"),
        }

        # Sign
        jwt_token = sign_capability(payload)
        assert isinstance(jwt_token, str)
        assert len(jwt_token) > 0

        # Verify
        decoded = verify_capability(jwt_token)
        assert decoded["cap_id"] == "test-cap-123"
        assert decoded["user_id"] == "TEST"
        assert decoded["grantee_id"] == "career_coach"
        assert "read:SkillDNA" in decoded["scopes"]

    def test_parse_ttl_to_seconds(self):
        """Test TTL parsing."""
        assert parse_ttl_to_seconds("PT1H") == 3600  # 1 hour
        assert parse_ttl_to_seconds("PT24H") == 86400  # 24 hours
        assert parse_ttl_to_seconds("PT30M") == 1800  # 30 minutes
        assert parse_ttl_to_seconds("P7D") == 604800  # 7 days
        assert parse_ttl_to_seconds("P1W") == 604800  # 1 week

    def test_compute_expiration(self):
        """Test expiration computation."""
        exp = compute_expiration("PT1H")
        now = int(datetime.utcnow().timestamp())
        assert exp > now  # Expiration is in future
        assert exp <= now + 3600  # Within 1 hour


class TestConsentStorage:
    """Test consent storage operations."""

    def setup_method(self):
        """Setup test storage."""
        self.storage = ConsentStorage()

    def test_save_and_get_capability(self):
        """Test saving and retrieving a capability."""
        capability = CapabilityToken(
            cap_id="test-cap-456",
            user_id="TEST",
            grantee_id="career_coach",
            purpose="test_purpose",
            scopes=["read:SkillDNA"],
            ttl="PT24H",
            data_policy=DataPolicy(),
            issued_at=int(datetime.utcnow().timestamp()),
            exp=compute_expiration("PT24H"),
            audit_id="audit-123",
        )

        # Save
        self.storage.save_capability(capability)

        # Get
        retrieved = self.storage.get_capability("test-cap-456")
        assert retrieved is not None
        assert retrieved.cap_id == "test-cap-456"
        assert retrieved.user_id == "TEST"
        assert retrieved.grantee_id == "career_coach"

    def test_list_capabilities(self):
        """Test listing capabilities with filters."""
        # Create multiple capabilities
        cap1 = CapabilityToken(
            cap_id="cap-1",
            user_id="USER1",
            grantee_id="career_coach",
            purpose="test",
            scopes=["read:SkillDNA"],
            ttl="PT24H",
            data_policy=DataPolicy(),
            issued_at=int(datetime.utcnow().timestamp()),
            exp=compute_expiration("PT24H"),
            audit_id="audit-1",
        )

        cap2 = CapabilityToken(
            cap_id="cap-2",
            user_id="USER2",
            grantee_id="ptc",
            purpose="test",
            scopes=["read:PsyDNA"],
            ttl="PT24H",
            data_policy=DataPolicy(),
            issued_at=int(datetime.utcnow().timestamp()),
            exp=compute_expiration("PT24H"),
            audit_id="audit-2",
        )

        self.storage.save_capability(cap1)
        self.storage.save_capability(cap2)

        # List all
        all_caps = self.storage.list_capabilities()
        assert len(all_caps) >= 2

        # Filter by user
        user1_caps = self.storage.list_capabilities(user_id="USER1")
        assert len(user1_caps) >= 1
        assert all(cap.user_id == "USER1" for cap in user1_caps)

        # Filter by grantee
        career_caps = self.storage.list_capabilities(grantee_id="career_coach")
        assert len(career_caps) >= 1
        assert all(cap.grantee_id == "career_coach" for cap in career_caps)

    def test_create_and_read_ledger_event(self):
        """Test creating and reading ledger events."""
        # Create event
        event = self.storage.create_ledger_event(
            event_type=LedgerEventType.GRANT,
            user_id="TEST",
            cap_id="cap-789",
            grantee_id="career_coach",
            purpose="test_purpose",
            scopes=["read:SkillDNA"],
            ttl="PT24H",
        )

        assert event.event_id is not None
        assert event.event_type == LedgerEventType.GRANT
        assert event.user_id == "TEST"

        # Read ledger
        events = self.storage.read_ledger(user_id="TEST")
        assert len(events) >= 1

        matching_events = [e for e in events if e.cap_id == "cap-789"]
        assert len(matching_events) >= 1
        assert matching_events[0].event_type == LedgerEventType.GRANT


@pytest.mark.asyncio
class TestConsentServiceAPI:
    """
    Test Consent Service API endpoints.

    NOTE: These tests require the Consent Service to be running.
    Run with: python3 ReDNACoreDemo/services/consent/run_consent.py
    """

    @pytest.fixture
    def consent_url(self):
        """Get Consent Service URL."""
        return "http://127.0.0.1:8200"

    async def test_health_check(self, consent_url):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{consent_url}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    async def test_grant_capability(self, consent_url):
        """Test granting a capability."""
        request = {
            "user_id": "TEST",
            "grantee_id": "career_coach",
            "purpose": "resume_builder",
            "scopes": ["read:SkillDNA", "read:ProfDNA"],
            "suggested_ttl": "PT24H",
            "export_allowed": False,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{consent_url}/consent/grant", json=request)
            assert response.status_code == 200

            data = response.json()
            assert "cap_id" in data
            assert "jwt" in data
            assert "issued_at" in data
            assert "expires_at" in data
            assert data["purpose"] == "resume_builder"

            # Verify JWT can be decoded
            jwt_token = data["jwt"]
            decoded = verify_capability(jwt_token)
            assert decoded["user_id"] == "TEST"
            assert decoded["grantee_id"] == "career_coach"

    async def test_revoke_capability(self, consent_url):
        """Test revoking a capability."""
        # First grant a capability
        request = {
            "user_id": "TEST",
            "grantee_id": "career_coach",
            "purpose": "test_revoke",
            "scopes": ["read:SkillDNA"],
            "suggested_ttl": "PT1H",
            "export_allowed": False,
        }

        async with httpx.AsyncClient() as client:
            grant_response = await client.post(f"{consent_url}/consent/grant", json=request)
            assert grant_response.status_code == 200
            cap_id = grant_response.json()["cap_id"]

            # Revoke it
            revoke_request = {"cap_id": cap_id, "reason": "Test revocation"}
            revoke_response = await client.post(f"{consent_url}/consent/revoke", json=revoke_request)
            assert revoke_response.status_code == 200

            data = revoke_response.json()
            assert data["status"] == "revoked"
            assert data["cap_id"] == cap_id

    async def test_list_capabilities(self, consent_url):
        """Test listing capabilities."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{consent_url}/consent/capabilities",
                params={"user_id": "TEST"}
            )
            assert response.status_code == 200

            capabilities = response.json()
            assert isinstance(capabilities, list)

    async def test_get_ledger(self, consent_url):
        """Test retrieving ledger events."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{consent_url}/consent/ledger",
                params={"user_id": "TEST"}
            )
            assert response.status_code == 200

            events = response.json()
            assert isinstance(events, list)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
