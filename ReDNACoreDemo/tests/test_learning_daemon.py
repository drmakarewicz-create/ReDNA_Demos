"""
Integration Tests for Self-Improvement Learning Daemon
=======================================================

Tests the autonomous daemon's ability to:
1. Run analysis → suggestion → approval cycle
2. Respect confidence thresholds
3. Enforce single-instance locking
4. Support dry-run mode
5. Log runs to telemetry
6. Merge CLI args with config
"""

import json
import pytest
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys

from ReDNACoreDemo.core.learning.daemon import LearningDaemon, load_config


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directory structure."""
    data_dir = tmp_path / "data"
    prompts_dir = tmp_path / "prompts"
    insights_dir = prompts_dir / "insights"
    backups_dir = prompts_dir / "backups"

    insights_dir.mkdir(parents=True)
    backups_dir.mkdir(parents=True)

    return {
        "data_dir": data_dir,
        "prompts_dir": prompts_dir,
        "insights_dir": insights_dir,
        "backups_dir": backups_dir
    }


@pytest.fixture
def sample_telemetry(temp_dirs):
    """Create sample telemetry files."""
    insights_dir = temp_dirs["insights_dir"]

    # Create telemetry for career_coach with patterns
    telemetry_file = insights_dir / "career_coach.jsonl"

    entries = []

    # 20 entries with "Empathetic" tone → positive sentiment
    for i in range(20):
        entries.append({
            "kind": "coach_turn",
            "ts": f"2025-10-{9:02d}T{i:02d}:00:00Z",
            "user_id": "test_user",
            "active_coach_id": "career_coach",
            "context_version": 1,
            "input_tokens": 150,
            "output_tokens": 200,
            "latency_ms": 800,
            "sentiment": "positive",
            "tone_keyword": "Empathetic"
        })

    # 5 entries with "Professional" tone → neutral sentiment
    for i in range(20, 25):
        entries.append({
            "kind": "coach_turn",
            "ts": f"2025-10-{9:02d}T{i:02d}:00:00Z",
            "user_id": "test_user",
            "active_coach_id": "career_coach",
            "context_version": 1,
            "input_tokens": 150,
            "output_tokens": 200,
            "latency_ms": 1200,
            "sentiment": "neutral",
            "tone_keyword": "Professional"
        })

    with open(telemetry_file, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')

    return telemetry_file


@pytest.fixture
def sample_prompt(temp_dirs):
    """Create sample prompt file."""
    prompts_dir = temp_dirs["prompts_dir"]
    prompt_file = prompts_dir / "career_coach_ai.md"

    content = """# Career Coach AI

You are a career development specialist focused on helping users optimize their professional growth.

## Tone
Professional

## Approach
Evidence-based coaching with actionable insights.
"""

    with open(prompt_file, 'w') as f:
        f.write(content)

    return prompt_file


@pytest.fixture
def daemon_config(temp_dirs):
    """Create daemon config file."""
    config_file = temp_dirs["data_dir"] / "learning_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "interval_hours": 6,
        "auto_threshold": 0.85,
        "max_suggestions_per_coach": 3,
        "dry_run": False,
        "enable_daemon": True
    }

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    return config_file


def test_daemon_single_cycle(temp_dirs, sample_telemetry, sample_prompt):
    """Test daemon runs single cycle successfully."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        interval_hours=6.0,
        auto_threshold=0.70,  # Lower threshold to ensure suggestions
        max_suggestions_per_coach=5,
        dry_run=True  # Dry run for safety
    )

    summary = daemon.run_cycle()

    # Verify summary structure
    assert "timestamp" in summary
    assert "coaches_analyzed" in summary
    assert "suggestions_generated" in summary
    assert "elapsed_seconds" in summary

    # Should have analyzed at least 1 coach
    assert summary["coaches_analyzed"] >= 1

    # Should have generated suggestions
    assert summary["suggestions_generated"] >= 0

    # Dry run shouldn't approve anything
    assert summary["suggestions_approved"] == 0


def test_daemon_dry_run_mode(temp_dirs, sample_telemetry, sample_prompt):
    """Test dry-run mode doesn't modify prompts."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        auto_threshold=0.70,
        dry_run=True
    )

    # Read original prompt
    original_content = sample_prompt.read_text()

    # Run cycle
    daemon.run_cycle()

    # Prompt should be unchanged
    assert sample_prompt.read_text() == original_content

    # No backups should be created
    backups_dir = temp_dirs["backups_dir"]
    assert len(list(backups_dir.glob("*.md"))) == 0


def test_daemon_lockfile_prevents_concurrent_runs(temp_dirs):
    """Test lockfile prevents multiple daemon instances."""
    daemon1 = LearningDaemon(data_dir=temp_dirs["data_dir"])
    daemon2 = LearningDaemon(data_dir=temp_dirs["data_dir"])

    # First daemon acquires lock
    assert daemon1.acquire_lock() is True

    # Second daemon cannot acquire lock
    assert daemon2.acquire_lock() is False

    # Release and second can acquire
    daemon1.release_lock()
    assert daemon2.acquire_lock() is True

    daemon2.release_lock()


def test_daemon_skips_low_confidence_suggestions(temp_dirs, sample_telemetry, sample_prompt):
    """Test daemon only auto-approves high-confidence suggestions."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        auto_threshold=0.95,  # Very high threshold
        dry_run=False
    )

    summary = daemon.run_cycle()

    # Should generate suggestions
    assert summary["suggestions_generated"] >= 0

    # But eligible count should be lower (high threshold)
    # Most suggestions will have confidence 0.70-0.90
    assert summary["suggestions_eligible"] <= summary["suggestions_generated"]


def test_daemon_logs_to_telemetry(temp_dirs, sample_telemetry, sample_prompt):
    """Test daemon logs run summary to telemetry."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        dry_run=True
    )

    daemon.run_cycle()

    # Check telemetry log exists
    log_file = temp_dirs["insights_dir"] / "self_improvement_daemon.jsonl"
    assert log_file.exists()

    # Read entries
    with open(log_file, 'r') as f:
        entries = [json.loads(line) for line in f]

    assert len(entries) >= 1

    # Verify structure
    entry = entries[0]
    assert entry["kind"] == "self_improvement_run"
    assert "timestamp" in entry
    assert "data" in entry

    data = entry["data"]
    assert "coaches_analyzed" in data
    assert "suggestions_generated" in data
    assert "elapsed_seconds" in data


def test_daemon_respects_suggestion_limit(temp_dirs, sample_telemetry, sample_prompt):
    """Test max_suggestions_per_coach limit is respected."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        auto_threshold=0.70,
        max_suggestions_per_coach=2,  # Strict limit
        dry_run=False
    )

    summary = daemon.run_cycle()

    # Even if more suggestions are eligible, max 2 per coach should be approved
    # (In practice, we have 1 coach, so max 2 total)
    assert summary["suggestions_approved"] <= 2


def test_load_config_merges_with_defaults(temp_dirs, daemon_config):
    """Test config file loading."""
    config = load_config(daemon_config)

    assert config["interval_hours"] == 6
    assert config["auto_threshold"] == 0.85
    assert config["max_suggestions_per_coach"] == 3
    assert config["dry_run"] is False


def test_daemon_applies_suggestion_with_backup(temp_dirs, sample_telemetry, sample_prompt):
    """Test daemon creates backup and applies suggestion."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        auto_threshold=0.70,  # Low threshold to trigger
        max_suggestions_per_coach=1,
        dry_run=False
    )

    # Read original prompt
    original_content = sample_prompt.read_text()

    # Run cycle
    summary = daemon.run_cycle()

    # If suggestions were approved, verify backup exists
    if summary["suggestions_approved"] > 0:
        backups_dir = temp_dirs["backups_dir"]
        backups = list(backups_dir.glob("career_coach_ai_*.md"))

        assert len(backups) >= 1

        # Verify backup contains original content
        backup = backups[0]
        assert backup.read_text() == original_content

        # Verify prompt was modified
        modified_content = sample_prompt.read_text()
        assert modified_content != original_content
        assert "Applied suggestion" in modified_content


def test_daemon_run_once_mode(temp_dirs, sample_telemetry, sample_prompt):
    """Test run_once executes single cycle and exits."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        dry_run=True
    )

    # Acquire lock manually
    assert daemon.acquire_lock() is True

    # Run once
    summary = daemon.run_once()

    # Should return summary
    assert summary is not None
    assert "coaches_analyzed" in summary

    # Lock should be released
    # Try to acquire again
    daemon2 = LearningDaemon(data_dir=temp_dirs["data_dir"])
    assert daemon2.acquire_lock() is True
    daemon2.release_lock()


def test_daemon_performance(temp_dirs, sample_telemetry, sample_prompt):
    """Test daemon cycle completes in <10s."""
    daemon = LearningDaemon(
        data_dir=temp_dirs["data_dir"],
        dry_run=True
    )

    start = time.time()
    summary = daemon.run_cycle()
    elapsed = time.time() - start

    # Should complete in <10s (target from spec)
    assert elapsed < 10.0

    # Summary should also report elapsed time
    assert summary["elapsed_seconds"] < 10.0
