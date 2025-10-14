"""
Test Suite - Phase 6 Governance & Compliance

Tests consent timeline, audit bundles, privacy overlays, and policy enforcement.

Test Coverage:
- Consent timeline (append, query, export)
- Audit bundle creation and performance
- Privacy level indicators
- Policy enforcement rules
- API endpoints
"""

import pytest
import json
import time
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import modules under test
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))

from ReDNACoreDemo.core.governance import (
    ConsentTimeline,
    ConsentEvent,
    EventType,
    create_audit_bundle,
    PrivacyLevel,
    check_privacy_level,
    get_privacy_indicator,
    get_namespace_indicator,
    PolicyEnforcer,
    PolicyViolation,
)


# Fixtures


@pytest.fixture
def test_user_id():
    """Test user ID."""
    return "TEST_GOVERNANCE_USER"


@pytest.fixture
def sample_consent_event(test_user_id):
    """Create a sample consent event."""
    return ConsentEvent(
        event_id=f"evt-{int(time.time())}",
        timestamp=datetime.utcnow().isoformat() + "Z",
        event_type=EventType.GRANT,
        user_id=test_user_id,
        cap_id="cap-test-123",
        grantee_id="test_app",
        purpose="testing",
        scopes=["read:PsyDNA"],
        ttl="PT24H",
    )


@pytest.fixture
def timeline(test_user_id):
    """Create consent timeline instance."""
    return ConsentTimeline(test_user_id)


@pytest.fixture
def policy_enforcer():
    """Create policy enforcer instance."""
    return PolicyEnforcer()


# Test: Consent Timeline


class TestConsentTimeline:
    """Test consent timeline functionality."""

    def test_timeline_creation(self, test_user_id):
        """Test timeline instance creation."""
        timeline = ConsentTimeline(test_user_id)
        assert timeline.user_id == test_user_id
        assert timeline.timeline_file.parent.exists()

    def test_append_event(self, timeline, sample_consent_event):
        """Test appending event to timeline."""
        timeline.append(sample_consent_event)

        events = timeline.get_all_events()
        assert len(events) > 0

        # Find our event
        our_event = next(
            (e for e in events if e.event_id == sample_consent_event.event_id),
            None
        )
        assert our_event is not None
        assert our_event.event_type == EventType.GRANT
        assert our_event.user_id == sample_consent_event.user_id

    def test_get_events_by_type(self, timeline, sample_consent_event):
        """Test filtering events by type."""
        timeline.append(sample_consent_event)

        grants = timeline.get_events_by_type(EventType.GRANT)
        assert len(grants) > 0
        assert all(e.event_type == EventType.GRANT for e in grants)

    def test_get_events_in_range(self, timeline, sample_consent_event):
        """Test filtering events by date range."""
        timeline.append(sample_consent_event)

        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)

        events = timeline.get_events_in_range(start, end)
        assert len(events) > 0

    def test_export_to_json(self, timeline, sample_consent_event):
        """Test JSON export."""
        timeline.append(sample_consent_event)

        json_export = timeline.export_to_json()
        assert isinstance(json_export, str)

        # Parse to validate
        data = json.loads(json_export)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_export_to_csv(self, timeline, sample_consent_event):
        """Test CSV export."""
        timeline.append(sample_consent_event)

        csv_export = timeline.export_to_csv()
        assert isinstance(csv_export, str)
        assert "event_id,timestamp,event_type" in csv_export

    def test_get_summary(self, timeline, sample_consent_event):
        """Test summary statistics."""
        timeline.append(sample_consent_event)

        summary = timeline.get_summary()
        assert "total_events" in summary
        assert "event_counts" in summary
        assert summary["total_events"] > 0

    def test_get_active_capabilities(self, timeline, test_user_id):
        """Test getting active capabilities."""
        # Add a grant event
        grant_event = ConsentEvent(
            event_id=f"evt-grant-{int(time.time())}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=EventType.GRANT,
            user_id=test_user_id,
            cap_id="cap-active-123",
            grantee_id="test_app",
            purpose="testing",
            scopes=["read:SkillDNA"],
            ttl="PT24H",
        )
        timeline.append(grant_event)

        active_caps = timeline.get_active_capabilities()
        assert isinstance(active_caps, list)


# Test: Audit Bundle


class TestAuditBundle:
    """Test audit bundle creation."""

    def test_create_bundle(self, test_user_id, tmp_path):
        """Test creating audit bundle."""
        # Create test user data
        user_dir = Path("data/users") / test_user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        user_file = user_dir / "user.json"
        user_file.write_text(json.dumps({"user_id": test_user_id, "name": "Test User"}))

        # Create bundle
        bundle_path = create_audit_bundle(
            user_id=test_user_id,
            requester="test",
            purpose="testing",
            output_dir=tmp_path
        )

        assert bundle_path.exists()
        assert bundle_path.suffix == ".zip"
        assert test_user_id in bundle_path.name

    def test_bundle_performance(self, test_user_id, tmp_path):
        """Test bundle creation performance (<5s target)."""
        # Create test user data
        user_dir = Path("data/users") / test_user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        user_file = user_dir / "user.json"
        user_file.write_text(json.dumps({"user_id": test_user_id}))

        start_time = time.time()
        bundle_path = create_audit_bundle(
            user_id=test_user_id,
            requester="test",
            purpose="performance_test",
            output_dir=tmp_path
        )
        duration = time.time() - start_time

        assert duration < 5.0, f"Bundle creation took {duration:.2f}s (target: <5s)"

    def test_bundle_contents(self, test_user_id, tmp_path):
        """Test bundle contains expected files."""
        # Create minimal test data
        user_dir = Path("data/users") / test_user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        user_file = user_dir / "user.json"
        user_file.write_text(json.dumps({"user_id": test_user_id}))

        # Create bundle
        bundle_path = create_audit_bundle(
            user_id=test_user_id,
            requester="test",
            purpose="content_test",
            output_dir=tmp_path
        )

        # Check contents
        with zipfile.ZipFile(bundle_path, 'r') as zf:
            namelist = zf.namelist()

            # Check required files
            assert "metadata.json" in namelist
            assert "user_profile.json" in namelist
            assert "provenance.json" in namelist
            assert "consent/timeline.json" in namelist

            # Read and validate metadata
            metadata_json = zf.read("metadata.json").decode("utf-8")
            metadata = json.loads(metadata_json)
            assert metadata["user_id"] == test_user_id
            assert "bundle_id" in metadata
            assert "generation_time_ms" in metadata


# Test: Privacy Overlay


class TestPrivacyOverlay:
    """Test privacy level indicators."""

    def test_check_privacy_level_public(self):
        """Test public namespace privacy level."""
        assert check_privacy_level("SkillDNA") == PrivacyLevel.PUBLIC
        assert check_privacy_level("ProfDNA") == PrivacyLevel.PUBLIC

    def test_check_privacy_level_sensitive(self):
        """Test sensitive namespace privacy level."""
        assert check_privacy_level("ChatDNA") == PrivacyLevel.SENSITIVE
        assert check_privacy_level("RelationshipDNA") == PrivacyLevel.SENSITIVE

    def test_check_privacy_level_highly_sensitive(self):
        """Test highly sensitive namespace privacy level."""
        assert check_privacy_level("PsyDNA") == PrivacyLevel.HIGHLY_SENSITIVE
        assert check_privacy_level("BeliefDNA") == PrivacyLevel.HIGHLY_SENSITIVE

    def test_get_privacy_indicator_green(self):
        """Test green (public) indicator properties."""
        indicator = get_privacy_indicator(PrivacyLevel.PUBLIC)

        assert indicator["color"] == "green"
        assert indicator["label"] == "Public"
        assert indicator["requires_consent"] is False
        assert "icon" in indicator

    def test_get_privacy_indicator_yellow(self):
        """Test yellow (sensitive) indicator properties."""
        indicator = get_privacy_indicator(PrivacyLevel.SENSITIVE)

        assert indicator["color"] == "yellow"
        assert indicator["label"] == "Sensitive"
        assert indicator["requires_consent"] is True

    def test_get_privacy_indicator_red(self):
        """Test red (highly sensitive) indicator properties."""
        indicator = get_privacy_indicator(PrivacyLevel.HIGHLY_SENSITIVE)

        assert indicator["color"] == "red"
        assert indicator["label"] == "Highly Sensitive"
        assert indicator["requires_consent"] is True

    def test_get_namespace_indicator(self):
        """Test getting indicator for namespace."""
        indicator = get_namespace_indicator("PsyDNA")

        assert indicator["namespace"] == "PsyDNA"
        assert indicator["color"] == "red"
        assert indicator["label"] == "Highly Sensitive"


# Test: Policy Enforcement


class TestPolicyEnforcement:
    """Test policy enforcement rules."""

    def test_write_policy_allows_explicit_scope(self, policy_enforcer):
        """Test write policy allows with explicit scope."""
        # Should pass
        result = policy_enforcer.check_write_policy(
            namespace="PsyDNA",
            scopes=["write:PsyDNA"],
            data_policy={}
        )
        assert result is True

    def test_write_policy_allows_wildcard(self, policy_enforcer):
        """Test write policy allows with wildcard scope."""
        # Should pass
        result = policy_enforcer.check_write_policy(
            namespace="PsyDNA",
            scopes=["write:*"],
            data_policy={}
        )
        assert result is True

    def test_write_policy_denies_insufficient_scope(self, policy_enforcer):
        """Test write policy denies without proper scope."""
        # Should raise PolicyViolation
        with pytest.raises(PolicyViolation):
            policy_enforcer.check_write_policy(
                namespace="PsyDNA",
                scopes=["read:PsyDNA"],  # Read, not write
                data_policy={}
            )

    def test_export_policy_requires_permission(self, policy_enforcer):
        """Test export policy requires explicit permission."""
        # Without export scope or data_policy.export
        with pytest.raises(PolicyViolation):
            policy_enforcer.check_export_policy(
                scopes=["read:PsyDNA"],
                data_policy={"export": False}
            )

    def test_export_policy_allows_with_scope(self, policy_enforcer):
        """Test export policy allows with export scope."""
        result = policy_enforcer.check_export_policy(
            scopes=["export", "read:PsyDNA"],
            data_policy={"export": True}
        )
        assert result is True

    def test_export_policy_blocks_aggregate_only(self, policy_enforcer):
        """Test export policy blocks aggregate_only data."""
        with pytest.raises(PolicyViolation):
            policy_enforcer.check_export_policy(
                scopes=["export"],
                data_policy={"export": True, "aggregate_only": True}
            )

    def test_remote_access_policy_allows_local(self, policy_enforcer):
        """Test remote access policy allows local requests."""
        result = policy_enforcer.check_remote_access_policy(
            namespace="PsyDNA",
            scopes=["read:PsyDNA"],
            remote=False
        )
        assert result is True

    def test_remote_access_policy_requires_scope(self, policy_enforcer):
        """Test remote access policy requires remote_ok scope."""
        # Remote access to sensitive namespace without remote_ok
        with pytest.raises(PolicyViolation):
            policy_enforcer.check_remote_access_policy(
                namespace="PsyDNA",
                scopes=["read:PsyDNA"],
                remote=True
            )

    def test_remote_access_policy_allows_with_scope(self, policy_enforcer):
        """Test remote access policy allows with remote_ok scope."""
        result = policy_enforcer.check_remote_access_policy(
            namespace="PsyDNA",
            scopes=["read:PsyDNA", "remote_ok"],
            remote=True
        )
        assert result is True

    def test_validate_capability_complete(self, policy_enforcer):
        """Test complete capability validation."""
        # All policies should pass
        result = policy_enforcer.validate_capability(
            scopes=["read:PsyDNA", "remote_ok"],
            operation="read",
            namespace="PsyDNA",
            data_policy={},
            remote=True
        )
        assert result is True


# Test: Integration


class TestGovernanceIntegration:
    """Test integration between governance components."""

    def test_timeline_to_audit_bundle(self, test_user_id, tmp_path):
        """Test timeline events are included in audit bundle."""
        # Create timeline events
        timeline = ConsentTimeline(test_user_id)
        event = ConsentEvent(
            event_id=f"evt-integration-{int(time.time())}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=EventType.GRANT,
            user_id=test_user_id,
            cap_id="cap-integration-123",
            grantee_id="test_app",
            purpose="integration_test",
            scopes=["read:SkillDNA"],
            ttl="PT24H",
        )
        timeline.append(event)

        # Create audit bundle
        bundle_path = create_audit_bundle(
            user_id=test_user_id,
            requester="test",
            purpose="integration_test",
            output_dir=tmp_path
        )

        # Verify timeline is in bundle
        with zipfile.ZipFile(bundle_path, 'r') as zf:
            timeline_json = zf.read("consent/timeline.json").decode("utf-8")
            timeline_data = json.loads(timeline_json)

            assert "timeline" in timeline_data
            assert len(timeline_data["timeline"]) > 0

    def test_privacy_with_policy(self, policy_enforcer):
        """Test privacy levels match policy enforcement."""
        # PsyDNA is highly sensitive
        level = check_privacy_level("PsyDNA")
        assert level == PrivacyLevel.HIGHLY_SENSITIVE

        # Should require explicit write scope
        with pytest.raises(PolicyViolation):
            policy_enforcer.check_write_policy(
                namespace="PsyDNA",
                scopes=["read:PsyDNA"],
                data_policy={}
            )


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
