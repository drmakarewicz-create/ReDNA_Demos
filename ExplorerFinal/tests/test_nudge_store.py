"""Comprehensive tests for nudge_store operations (CRUD, TTL, cohorts, batch dismiss)."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Import nudge_store from ExplorerFinal
import sys
_here = Path(__file__).parent
_explorer_final = _here.parent
sys.path.insert(0, str(_explorer_final.parent))

from ExplorerFinal.core import nudge_store


@pytest.fixture
def temp_data_dir(monkeypatch):
    """Create a temporary directory for test data and override MAILBOX_ROOT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        mailbox_root = temp_path / "mailbox"
        logs_root = temp_path / "logs"

        monkeypatch.setattr(nudge_store, "MAILBOX_ROOT", mailbox_root)
        monkeypatch.setattr(nudge_store, "LOGS_ROOT", logs_root)

        yield {
            "root": temp_path,
            "mailbox": mailbox_root,
            "logs": logs_root,
        }


@pytest.fixture
def sample_nudge_payload() -> Dict[str, Any]:
    """Sample nudge payload for testing."""
    return {
        "persona_id": "photo_coach",
        "mode": "curious",
        "tone_meta": "encouraging",
        "items": [
            {
                "container": "PhotoPreferences",
                "trait_id": "lighting_style",
                "text": "I noticed you prefer natural light. Tell me more!",
                "template_source": "curious_probe",
            }
        ],
        "provenance": {"source": "test"},
        "ttl_minutes": 60,
    }


class TestNudgeStoreCRUD:
    """Test basic CRUD operations for nudges."""

    def test_add_bundle_success(self, temp_data_dir, sample_nudge_payload):
        """Test successfully adding a nudge bundle."""
        result = nudge_store.add_bundle(
            "user123",
            sample_nudge_payload,
            write_protect=False,
        )

        assert result["duplicate"] is False
        assert "bundle" in result
        bundle = result["bundle"]
        assert bundle["id"].startswith("nudge_")
        assert bundle["status"] == "inbox"
        assert bundle["persona_id"] == "photo_coach"
        assert len(bundle["items"]) == 1
        assert bundle["ttl_minutes"] == 60

    def test_add_duplicate_bundle_rejected(self, temp_data_dir, sample_nudge_payload):
        """Test that duplicate bundles are rejected."""
        # Add first bundle
        result1 = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        assert result1["duplicate"] is False

        # Try to add duplicate
        result2 = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        assert result2["duplicate"] is True
        assert result2["bundle"]["id"] == result1["bundle"]["id"]

    def test_list_inbox_empty(self, temp_data_dir):
        """Test listing an empty inbox."""
        result = nudge_store.list_inbox("user123", write_protect=False)
        assert result == []

    def test_list_inbox_with_entries(self, temp_data_dir, sample_nudge_payload):
        """Test listing inbox with entries."""
        nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)

        result = nudge_store.list_inbox("user123", write_protect=False)
        assert len(result) == 1
        assert result[0]["status"] == "inbox"

    def test_accept_nudge(self, temp_data_dir, sample_nudge_payload):
        """Test accepting a nudge."""
        # Add bundle
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        # Accept it
        accept_result = nudge_store.accept(
            "user123",
            nudge_id,
            write_protect=False,
            deliver_to_chat=True,
        )

        assert accept_result["ok"] is True
        assert accept_result["bundle"]["status"] == "accepted"
        assert "chat_entry_ids" in accept_result
        assert len(accept_result["chat_entry_ids"]) == 1

    def test_dismiss_nudge(self, temp_data_dir, sample_nudge_payload):
        """Test dismissing a nudge."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        dismiss_result = nudge_store.dismiss("user123", nudge_id, write_protect=False)

        assert dismiss_result["ok"] is True
        assert dismiss_result["bundle"]["status"] == "dismissed"

    def test_undo_nudge(self, temp_data_dir, sample_nudge_payload):
        """Test undoing a nudge action."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        # Accept then undo
        nudge_store.accept("user123", nudge_id, write_protect=False, deliver_to_chat=True)
        undo_result = nudge_store.undo("user123", nudge_id, write_protect=False, deliver_to_chat=True)

        assert undo_result["ok"] is True
        assert undo_result["bundle"]["status"] == "inbox"

    def test_snooze_nudge(self, temp_data_dir, sample_nudge_payload):
        """Test snoozing a nudge."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        snooze_result = nudge_store.snooze("user123", nudge_id, minutes=30, write_protect=False)

        assert snooze_result["ok"] is True
        assert snooze_result["bundle"]["status"] == "inbox_snoozed"
        assert snooze_result["bundle"]["snoozed_minutes"] == 30
        assert snooze_result["bundle"]["resume_at"] is not None

    def test_resume_snoozed_nudge(self, temp_data_dir, sample_nudge_payload):
        """Test resuming a snoozed nudge."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        # Snooze then resume
        nudge_store.snooze("user123", nudge_id, minutes=30, write_protect=False)
        resume_result = nudge_store.resume("user123", nudge_id, write_protect=False)

        assert resume_result["ok"] is True
        assert resume_result["bundle"]["status"] == "inbox"
        assert resume_result["bundle"]["resume_at"] is None


class TestNudgeTTL:
    """Test TTL (time-to-live) functionality."""

    def test_ttl_default_value(self, temp_data_dir, sample_nudge_payload):
        """Test that default TTL is applied when not specified."""
        payload = {**sample_nudge_payload}
        del payload["ttl_minutes"]

        result = nudge_store.add_bundle("user123", payload, write_protect=False)
        bundle = result["bundle"]

        # Should use default from env or constant
        assert bundle["ttl_minutes"] > 0
        assert bundle["expires_at"] is not None

    def test_ttl_custom_value(self, temp_data_dir, sample_nudge_payload):
        """Test setting a custom TTL."""
        payload = {**sample_nudge_payload, "ttl_minutes": 120}

        result = nudge_store.add_bundle("user123", payload, write_protect=False)
        bundle = result["bundle"]

        assert bundle["ttl_minutes"] == 120

    def test_expired_nudge_marked_expired(self, temp_data_dir, sample_nudge_payload):
        """Test that expired nudges are marked as expired."""
        # Create nudge with very short TTL
        payload = {**sample_nudge_payload, "ttl_minutes": 0.001}  # ~6 seconds

        result = nudge_store.add_bundle("user123", payload, write_protect=False)

        # Wait for expiry
        time.sleep(0.1)

        # List inbox should mark it expired
        inbox = nudge_store.list_inbox("user123", write_protect=False)
        assert len(inbox) == 1
        assert inbox[0]["expired"] is True

    def test_dismiss_expired_batch(self, temp_data_dir, sample_nudge_payload):
        """Test batch dismissal of expired nudges."""
        # Add multiple nudges with short TTL
        payload = {**sample_nudge_payload, "ttl_minutes": 0.001}

        for i in range(3):
            modified_payload = {**payload}
            modified_payload["items"] = [{**payload["items"][0], "text": f"Message {i}"}]
            nudge_store.add_bundle("user123", modified_payload, write_protect=False)

        time.sleep(0.1)

        # Dismiss all expired
        result = nudge_store.dismiss_expired("user123", write_protect=False)

        assert result["ok"] is True
        assert len(result["dismissed"]) == 3


class TestCohorts:
    """Test cohort functionality."""

    def test_cohort_a_assignment(self, temp_data_dir, sample_nudge_payload):
        """Test assigning nudge to cohort A."""
        payload = {**sample_nudge_payload, "cohort": "A"}

        result = nudge_store.add_bundle("user123", payload, write_protect=False)
        assert result["bundle"]["cohort"] == "A"

    def test_cohort_b_assignment(self, temp_data_dir, sample_nudge_payload):
        """Test assigning nudge to cohort B."""
        payload = {**sample_nudge_payload, "cohort": "B"}

        result = nudge_store.add_bundle("user123", payload, write_protect=False)
        assert result["bundle"]["cohort"] == "B"

    def test_invalid_cohort_normalized(self, temp_data_dir, sample_nudge_payload):
        """Test that invalid cohorts are normalized to None."""
        payload = {**sample_nudge_payload, "cohort": "invalid"}

        result = nudge_store.add_bundle("user123", payload, write_protect=False)
        assert result["bundle"]["cohort"] is None

    def test_cohort_case_insensitive(self, temp_data_dir, sample_nudge_payload):
        """Test that cohort assignment is case-insensitive."""
        payload = {**sample_nudge_payload, "cohort": "a"}

        result = nudge_store.add_bundle("user123", payload, write_protect=False)
        assert result["bundle"]["cohort"] == "A"


class TestOpsScheduling:
    """Test ops scheduling functionality."""

    def test_load_empty_ops(self, temp_data_dir):
        """Test loading ops config when none exists."""
        config = nudge_store.load_ops("user123", write_protect=False)

        assert config["schema_version"] == 1
        assert config["entries"] == []

    def test_upsert_ops_entry(self, temp_data_dir):
        """Test creating/updating an ops entry."""
        entry = {
            "id": "schedule_1",
            "persona_id": "photo_coach",
            "label": "Daily Photo Check",
            "weekdays": [1, 3, 5],  # Tue, Thu, Sat
            "hour": 9,
            "minute": 30,
        }

        result = nudge_store.upsert_ops_entry("user123", entry, write_protect=False)

        assert result["id"] == "schedule_1"
        assert result["persona_id"] == "photo_coach"
        assert result["weekdays"] == [1, 3, 5]
        assert result["hour"] == 9
        assert result["minute"] == 30
        assert result["next_run_ts"] is not None

    def test_delete_ops_entry(self, temp_data_dir):
        """Test deleting an ops entry."""
        entry = {
            "id": "schedule_1",
            "persona_id": "photo_coach",
            "weekdays": [0, 1, 2, 3, 4],
            "hour": 10,
            "minute": 0,
        }

        nudge_store.upsert_ops_entry("user123", entry, write_protect=False)
        nudge_store.delete_ops_entry("user123", "schedule_1", write_protect=False)

        config = nudge_store.load_ops("user123", write_protect=False)
        assert len(config["entries"]) == 0

    def test_mark_ops_run_updates_timestamps(self, temp_data_dir):
        """Test that marking an ops run updates last_run and next_run."""
        entry = {
            "id": "schedule_1",
            "persona_id": "photo_coach",
            "weekdays": list(range(7)),
            "hour": 10,
            "minute": 0,
        }

        nudge_store.upsert_ops_entry("user123", entry, write_protect=False)

        updated = nudge_store.mark_ops_run("user123", "schedule_1", write_protect=False)

        assert updated is not None
        assert updated["last_run_ts"] is not None
        assert updated["next_run_ts"] is not None

    def test_compute_next_run(self, temp_data_dir):
        """Test next run computation."""
        entry = {
            "weekdays": [1, 3, 5],  # Tue, Thu, Sat
            "hour": 14,
            "minute": 30,
        }

        next_run = nudge_store.compute_next_run(entry)

        assert next_run is not None
        # Parse and verify it's in the future
        next_dt = datetime.fromisoformat(next_run)
        assert next_dt > datetime.now(timezone.utc)


class TestRateLimit:
    """Test rate limiting functionality."""

    def test_rate_limit_enforcement(self, temp_data_dir):
        """Test that rate limiting prevents excessive actions."""
        limit = 3

        # First 3 actions should pass
        for i in range(limit):
            result = nudge_store.enforce_rate_limit(
                "user123",
                "enqueue",
                limit_per_minute=limit,
                write_protect=False,
            )
            assert result["ok"] is True
            nudge_store._record_rate_action("user123", write_protect=False)

        # 4th action should fail
        result = nudge_store.enforce_rate_limit(
            "user123",
            "enqueue",
            limit_per_minute=limit,
            write_protect=False,
        )
        assert result["ok"] is False
        assert "retry_in" in result


class TestFeedback:
    """Test feedback logging functionality."""

    def test_log_feedback_helpful(self, temp_data_dir, sample_nudge_payload):
        """Test logging helpful feedback."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        result = nudge_store.log_feedback(
            user_id="user123",
            nudge_id=nudge_id,
            persona_id="photo_coach",
            rating="helpful",
            note="This was great!",
            traits=[{"container": "PhotoPreferences", "trait_id": "lighting_style"}],
            write_protect=False,
        )

        assert result["ok"] is True
        assert result["record"]["rating"] == "helpful"

    def test_log_feedback_not_helpful(self, temp_data_dir, sample_nudge_payload):
        """Test logging not helpful feedback."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        result = nudge_store.log_feedback(
            user_id="user123",
            nudge_id=nudge_id,
            persona_id="photo_coach",
            rating="not_helpful",
            write_protect=False,
        )

        assert result["ok"] is True
        assert result["record"]["rating"] == "not_helpful"

    def test_load_feedback_entries(self, temp_data_dir, sample_nudge_payload):
        """Test loading feedback entries."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        nudge_store.log_feedback(
            user_id="user123",
            nudge_id=nudge_id,
            persona_id="photo_coach",
            rating="helpful",
            write_protect=False,
        )

        entries = nudge_store.load_feedback_entries(
            user_id="user123",
            write_protect=False,
        )

        assert len(entries) == 1
        assert entries[0]["rating"] == "helpful"

    def test_feedback_aggregates(self, temp_data_dir, sample_nudge_payload):
        """Test feedback aggregation by trait."""
        add_result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)
        nudge_id = add_result["bundle"]["id"]

        traits = [{"container": "PhotoPreferences", "trait_id": "lighting_style"}]

        # Log helpful feedback
        nudge_store.log_feedback(
            user_id="user123",
            nudge_id=nudge_id,
            persona_id="photo_coach",
            rating="helpful",
            traits=traits,
            write_protect=False,
        )

        # Log not_helpful feedback
        nudge_store.log_feedback(
            user_id="user123",
            nudge_id=f"{nudge_id}_2",
            persona_id="photo_coach",
            rating="not_helpful",
            traits=traits,
            write_protect=False,
        )

        aggregates = nudge_store.load_feedback_aggregates(
            user_id="user123",
            write_protect=False,
        )

        path = "PhotoPreferences.lighting_style"
        assert path in aggregates
        assert aggregates[path]["helpful"] == 1
        assert aggregates[path]["not_helpful"] == 1
        assert aggregates[path]["score"] == 0.0  # (1 - 1) / 2


class TestWriteProtectMode:
    """Test write_protect mode (dry-run) functionality."""

    def test_write_protect_add_bundle(self, temp_data_dir, sample_nudge_payload):
        """Test that write_protect prevents disk writes."""
        result = nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=True)

        assert result["duplicate"] is False

        # Verify nothing written to disk
        inbox_path = temp_data_dir["mailbox"] / "user123" / "inbox.json"
        assert not inbox_path.exists()

        # But cache should have it
        inbox = nudge_store.list_inbox("user123", write_protect=True)
        assert len(inbox) == 1

    def test_write_protect_feedback(self, temp_data_dir):
        """Test that write_protect prevents feedback from being written to disk."""
        result = nudge_store.log_feedback(
            user_id="user123",
            nudge_id="test_nudge",
            persona_id="photo_coach",
            rating="helpful",
            write_protect=True,
        )

        assert result["ok"] is True
        assert result.get("dry_run") is True

        # Verify log file doesn't exist
        log_path = temp_data_dir["logs"] / nudge_store.FEEDBACK_LOG_NAME
        assert not log_path.exists()


class TestExport:
    """Test export functionality."""

    def test_export_visible_csv_json(self, temp_data_dir, sample_nudge_payload):
        """Test exporting nudges as CSV and JSON."""
        nudge_store.add_bundle("user123", sample_nudge_payload, write_protect=False)

        bundles = nudge_store.list_inbox("user123", write_protect=False)

        csv_bytes, json_bytes = nudge_store.export_visible("user123", bundles)

        # Verify CSV
        csv_text = csv_bytes.decode("utf-8")
        assert "nudge_id" in csv_text
        assert "persona_id" in csv_text
        assert "photo_coach" in csv_text

        # Verify JSON
        json_data = json.loads(json_bytes.decode("utf-8"))
        assert isinstance(json_data, list)
        assert len(json_data) == 1


class TestHashingAndDedupe:
    """Test bundle hashing and deduplication."""

    def test_compute_bundle_hash_consistent(self, sample_nudge_payload):
        """Test that hash is consistent for same payload."""
        hash1 = nudge_store.compute_bundle_hash(sample_nudge_payload)
        hash2 = nudge_store.compute_bundle_hash(sample_nudge_payload)

        assert hash1 == hash2

    def test_compute_bundle_hash_different_for_different_content(self, sample_nudge_payload):
        """Test that different content produces different hash."""
        payload2 = {**sample_nudge_payload}
        payload2["items"] = [{**payload2["items"][0], "text": "Different text"}]

        hash1 = nudge_store.compute_bundle_hash(sample_nudge_payload)
        hash2 = nudge_store.compute_bundle_hash(payload2)

        assert hash1 != hash2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
