"""
Tests for Policy Engine

Tests capability evaluation, scope checking, and enforcement.
"""

import pytest
from datetime import datetime

from core.policy.policy_engine import PolicyEngine, evaluate_capability
from services.consent.models import CapabilityToken, DataPolicy
from services.consent.jwt_utils import sign_capability, compute_expiration
from services.consent.storage import ConsentStorage


class TestPolicyEngine:
    """Test policy engine capability evaluation."""

    def setup_method(self):
        """Setup test engine and storage."""
        self.engine = PolicyEngine()
        self.storage = ConsentStorage()

    def _create_test_capability(
        self,
        cap_id="test-cap",
        user_id="TEST",
        grantee_id="career_coach",
        scopes=None,
        ttl="PT24H",
        export_allowed=False,
        remote_access=False,
        revoked=False,
    ):
        """Helper to create a test capability."""
        if scopes is None:
            scopes = ["read:SkillDNA"]

        issued_at = int(datetime.utcnow().timestamp())
        exp = compute_expiration(ttl)

        capability = CapabilityToken(
            cap_id=cap_id,
            user_id=user_id,
            grantee_id=grantee_id,
            purpose="test_purpose",
            scopes=scopes,
            ttl=ttl,
            data_policy=DataPolicy(export=export_allowed, remote_access=remote_access),
            issued_at=issued_at,
            exp=exp,
            audit_id="test-audit",
            revoked=revoked,
        )

        # Save to storage
        self.storage.save_capability(capability)

        # Sign JWT
        jwt_payload = {
            "cap_id": cap_id,
            "user_id": user_id,
            "grantee_id": grantee_id,
            "scopes": scopes,
            "ttl": ttl,
            "data_policy": capability.data_policy.model_dump(),
            "iat": issued_at,
            "exp": exp,
            "audit_id": "test-audit",
        }

        jwt_token = sign_capability(jwt_payload)
        return jwt_token

    def test_valid_capability_read_access(self):
        """Test valid capability for read access."""
        jwt_token = self._create_test_capability(
            cap_id="cap-read-1",
            scopes=["read:SkillDNA"],
        )

        result = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="read",
        )

        assert result["allowed"] is True
        assert result["reason"] == "All policy checks passed"
        assert result["cap_id"] == "cap-read-1"

    def test_insufficient_scope(self):
        """Test denial for insufficient scope."""
        jwt_token = self._create_test_capability(
            cap_id="cap-read-2",
            scopes=["read:SkillDNA"],  # Only SkillDNA
        )

        result = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:ProfDNA",  # Request ProfDNA
            requested_operation="read",
        )

        assert result["allowed"] is False
        assert "Insufficient scopes" in result["reason"]

    def test_wildcard_scope(self):
        """Test wildcard scope matching."""
        jwt_token = self._create_test_capability(
            cap_id="cap-wildcard",
            scopes=["read:*"],  # Wildcard read
        )

        # Should allow reading any namespace
        result1 = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="read",
        )
        assert result1["allowed"] is True

        result2 = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:ProfDNA",
            requested_operation="read",
        )
        assert result2["allowed"] is True

        # But not write
        result3 = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="write:Goals",
            requested_operation="write",
        )
        assert result3["allowed"] is False

    def test_export_denied_by_policy(self):
        """Test export denied when data_policy.export = false."""
        jwt_token = self._create_test_capability(
            cap_id="cap-no-export",
            scopes=["read:SkillDNA"],
            export_allowed=False,
        )

        result = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="export",
        )

        assert result["allowed"] is False
        assert "Export denied" in result["reason"]

    def test_export_allowed_by_policy(self):
        """Test export allowed when data_policy.export = true."""
        jwt_token = self._create_test_capability(
            cap_id="cap-with-export",
            scopes=["read:SkillDNA"],
            export_allowed=True,
        )

        result = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="export",
        )

        assert result["allowed"] is True

    def test_remote_access_denied(self):
        """Test remote access denied when remote_access = false."""
        jwt_token = self._create_test_capability(
            cap_id="cap-local-only",
            scopes=["read:SkillDNA"],
            remote_access=False,
        )

        result = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="read",
            remote_request=True,  # Simulate remote request
        )

        assert result["allowed"] is False
        assert "Remote access denied" in result["reason"]

    def test_remote_access_allowed(self):
        """Test remote access allowed when remote_access = true."""
        jwt_token = self._create_test_capability(
            cap_id="cap-remote-ok",
            scopes=["read:SkillDNA"],
            remote_access=True,
        )

        result = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="read",
            remote_request=True,
        )

        assert result["allowed"] is True

    def test_revoked_capability(self):
        """Test denied access for revoked capability."""
        jwt_token = self._create_test_capability(
            cap_id="cap-revoked",
            scopes=["read:SkillDNA"],
            revoked=True,
        )

        result = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="read",
        )

        assert result["allowed"] is False
        assert "revoked" in result["reason"].lower()

    def test_multiple_scopes(self):
        """Test capability with multiple scopes."""
        jwt_token = self._create_test_capability(
            cap_id="cap-multi-scope",
            scopes=["read:SkillDNA", "read:ProfDNA", "write:Goals"],
        )

        # Read SkillDNA - allowed
        result1 = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:SkillDNA",
            requested_operation="read",
        )
        assert result1["allowed"] is True

        # Read ProfDNA - allowed
        result2 = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:ProfDNA",
            requested_operation="read",
        )
        assert result2["allowed"] is True

        # Write Goals - allowed
        result3 = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="write:Goals",
            requested_operation="write",
        )
        assert result3["allowed"] is True

        # Read PsyDNA - denied (not in scopes)
        result4 = self.engine.evaluate(
            jwt_token=jwt_token,
            requested_scope="read:PsyDNA",
            requested_operation="read",
        )
        assert result4["allowed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
