"""
Tests for Permission Coach

Tests capability request mediation, auditing, and permission workflows.
"""

import pytest
import asyncio

from core.permission_coach.permcoach_service import PermissionCoach
from core.permission_coach.client import ensure_capability, PermissionDeniedError, PermissionPendingError


@pytest.mark.asyncio
class TestPermissionCoach:
    """Test Permission Coach service."""

    def setup_method(self):
        """Setup test coach."""
        self.permcoach = PermissionCoach()

    async def test_request_capability_without_approval(self):
        """Test capability request returns pending status without approval."""
        result = await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="career_coach",
            purpose="resume_builder",
            scopes=["read:SkillDNA", "read:ProfDNA"],
            suggested_ttl="PT24H",
            user_approval=False,  # No approval yet
        )

        assert result["status"] == "pending_approval"
        assert "explanation" in result
        assert "risk_level" in result
        assert result["risk_level"] in ["low", "medium", "high"]
        assert "request" in result

    async def test_request_capability_with_approval(self):
        """Test capability request with user approval grants capability."""
        result = await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="career_coach",
            purpose="resume_builder",
            scopes=["read:SkillDNA"],
            suggested_ttl="PT1H",
            user_approval=True,  # User approved
        )

        assert result["status"] == "granted"
        assert "capability" in result
        assert result["capability"]["jwt"] is not None

    async def test_risk_assessment_low(self):
        """Test risk assessment for low-risk request."""
        result = await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="career_coach",
            purpose="skill_review",
            scopes=["read:SkillDNA"],  # Specific scope, no export
            suggested_ttl="PT1H",  # Short duration
            export_allowed=False,
            user_approval=False,
        )

        assert result["risk_level"] == "low"

    async def test_risk_assessment_medium_write(self):
        """Test risk assessment for medium-risk write request."""
        result = await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="career_coach",
            purpose="update_goals",
            scopes=["write:Goals"],  # Write access
            suggested_ttl="PT24H",
            user_approval=False,
        )

        assert result["risk_level"] == "medium"

    async def test_risk_assessment_high_wildcard(self):
        """Test risk assessment for high-risk wildcard request."""
        result = await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="malicious_coach",
            purpose="full_access",
            scopes=["read:*", "write:*"],  # Wildcard scopes
            suggested_ttl="P7D",
            user_approval=False,
        )

        assert result["risk_level"] == "high"

    async def test_revoke_capability(self):
        """Test capability revocation."""
        # First grant a capability
        grant_result = await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="career_coach",
            purpose="test_revoke",
            scopes=["read:SkillDNA"],
            suggested_ttl="PT1H",
            user_approval=True,
        )

        cap_id = grant_result["capability"]["cap_id"]

        # Revoke it
        revoke_result = await self.permcoach.revoke_capability(
            cap_id=cap_id,
            reason="Test revocation"
        )

        assert revoke_result["status"] == "revoked"
        assert revoke_result["cap_id"] == cap_id

    async def test_audit_capabilities(self):
        """Test capability auditing."""
        # Grant a capability first
        await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="career_coach",
            purpose="audit_test",
            scopes=["read:SkillDNA"],
            suggested_ttl="PT1H",
            user_approval=True,
        )

        # Run audit
        audit_result = await self.permcoach.audit_capabilities(user_id="TEST")

        assert "user_id" in audit_result
        assert audit_result["user_id"] == "TEST"
        assert "audit_timestamp" in audit_result
        assert "total_capabilities" in audit_result
        assert "anomalies" in audit_result
        assert "summary" in audit_result

    async def test_audit_detects_broad_scope(self):
        """Test audit detects overly broad scopes."""
        # Grant capability with broad scope
        await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="broad_coach",
            purpose="broad_access",
            scopes=["read:*"],  # Broad scope
            suggested_ttl="PT24H",
            user_approval=True,
        )

        # Run audit
        audit_result = await self.permcoach.audit_capabilities(user_id="TEST")

        # Should detect broad scope anomaly
        anomalies = audit_result["anomalies"]
        broad_scope_anomalies = [a for a in anomalies if a["type"] == "broad_scope"]
        assert len(broad_scope_anomalies) > 0

    async def test_audit_detects_export_permission(self):
        """Test audit detects export permissions."""
        # Grant capability with export
        await self.permcoach.request_capability(
            user_id="TEST",
            requester_id="export_coach",
            purpose="data_export",
            scopes=["read:SkillDNA"],
            suggested_ttl="PT24H",
            export_allowed=True,
            user_approval=True,
        )

        # Run audit
        audit_result = await self.permcoach.audit_capabilities(user_id="TEST")

        # Should detect export permission
        anomalies = audit_result["anomalies"]
        export_anomalies = [a for a in anomalies if a["type"] == "export_allowed"]
        assert len(export_anomalies) > 0


@pytest.mark.asyncio
class TestPermissionCoachClient:
    """Test Permission Coach client helper."""

    async def test_ensure_capability_pending(self):
        """Test ensure_capability raises PermissionPendingError without approval."""
        with pytest.raises(PermissionPendingError) as exc_info:
            await ensure_capability(
                user_id="TEST",
                requester_id="career_coach",
                purpose="test",
                scopes=["read:SkillDNA"],
            )

        assert "User approval required" in str(exc_info.value)
        assert exc_info.value.request_data is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
