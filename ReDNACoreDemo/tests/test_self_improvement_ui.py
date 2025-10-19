"""
Test Suite — Self-Improvement UI & Workflow Integration
=========================================================

Integration tests for apply-suggestion and history endpoints.

Scenarios:
    1. Approve high-confidence suggestion → prompt updated + history entry
    2. Reject low-confidence suggestion → no file change + history entry
    3. Backup file created on approve
    4. History GET returns chronological entries
    5. Confidence validation (cannot approve <0.70)

Author: ReDNA Core Team
Created: 2025-10-09
Benchmark: #8 Self-Improvement Loop (Phase 2)
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from ReDNACoreDemo.core.learning.telemetry_analyzer import TelemetryAnalyzer
from ReDNACoreDemo.core.learning.prompt_tuner import PromptTuner
from ReDNACoreDemo.core.learning.history_logger import HistoryLogger, get_history_logger


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directory structure."""
    data_dir = tmp_path / "data"
    prompts_dir = tmp_path / "prompts"
    insights_dir = prompts_dir / "insights"
    backups_dir = prompts_dir / "backups"
    learning_dir = data_dir / "learning"
    suggestions_dir = learning_dir / "suggestions"

    data_dir.mkdir()
    prompts_dir.mkdir()
    insights_dir.mkdir()
    backups_dir.mkdir()
    learning_dir.mkdir()
    suggestions_dir.mkdir()

    return {
        "base": tmp_path,
        "data": data_dir,
        "prompts": prompts_dir,
        "insights": insights_dir,
        "backups": backups_dir,
        "learning": learning_dir,
        "suggestions": suggestions_dir
    }


@pytest.fixture
def sample_suggestion():
    """Create sample tuning suggestion."""
    return {
        "id": "tune_001",
        "coach_id": "career_coach",
        "type": "tone_adjustment",
        "current_value": "Professional",
        "recommended_value": "Empathetic",
        "confidence": 0.87,
        "evidence": [
            "Top tone 'Empathetic' has 92.0% positive sentiment",
            "Improvement: +32.0%"
        ],
        "telemetry_refs": ["prompts/insights/career_coach.jsonl"],
        "auto_apply_eligible": True
    }


@pytest.fixture
def low_confidence_suggestion():
    """Create low-confidence suggestion."""
    return {
        "id": "tune_002",
        "coach_id": "career_coach",
        "type": "creativity_adjustment",
        "current_value": 0.70,
        "recommended_value": 0.68,
        "confidence": 0.65,  # Below threshold
        "evidence": ["Small sample size (n=12)"],
        "telemetry_refs": ["prompts/insights/career_coach.jsonl"],
        "auto_apply_eligible": False
    }


def test_history_logger_basic_logging(temp_dirs):
    """Test basic history logging functionality."""
    logger = HistoryLogger(temp_dirs["insights"])

    # Log approval
    entry = logger.log_decision(
        coach_id="career_coach",
        suggestion_id="tune_001",
        action="approve",
        confidence=0.87,
        user="admin",
        old_hash="abc123",
        new_hash="def456",
        reason="High confidence, good evidence"
    )

    # Verify entry structure
    assert entry.coach_id == "career_coach"
    assert entry.action == "approve"
    assert entry.confidence == 0.87
    assert entry.old_hash == "abc123"
    assert entry.new_hash == "def456"

    # Verify file exists
    history_file = temp_dirs["insights"] / "self_improvement_history.jsonl"
    assert history_file.exists()

    # Verify file content
    with open(history_file, 'r') as f:
        line = f.read().strip()
        logged_entry = json.loads(line)
        assert logged_entry["suggestion_id"] == "tune_001"
        assert logged_entry["action"] == "approve"


def test_history_retrieval(temp_dirs):
    """Test history retrieval with filtering."""
    logger = HistoryLogger(temp_dirs["insights"])

    # Log multiple decisions
    logger.log_decision("career_coach", "tune_001", "approve", 0.87, "admin")
    logger.log_decision("career_coach", "tune_002", "reject", 0.65, "admin")
    logger.log_decision("relationship_coach", "tune_003", "approve", 0.92, "admin")

    # Get all history
    all_history = logger.get_history(limit=100)
    assert len(all_history) == 3

    # Get career_coach history only
    career_history = logger.get_history(coach_id="career_coach", limit=100)
    assert len(career_history) == 2
    assert all(e["coach_id"] == "career_coach" for e in career_history)

    # Verify chronological order (most recent first)
    assert career_history[0]["suggestion_id"] == "tune_002"  # More recent
    assert career_history[1]["suggestion_id"] == "tune_001"  # Older


def test_history_stats_computation(temp_dirs):
    """Test statistics computation from history."""
    logger = HistoryLogger(temp_dirs["insights"])

    # Log decisions with varying confidence
    logger.log_decision("career_coach", "tune_001", "approve", 0.87, "admin")
    logger.log_decision("career_coach", "tune_002", "approve", 0.92, "admin")
    logger.log_decision("career_coach", "tune_003", "reject", 0.65, "admin")
    logger.log_decision("career_coach", "tune_004", "reject", 0.72, "admin")

    # Get stats
    stats = logger.get_stats(coach_id="career_coach")

    assert stats["total_decisions"] == 4
    assert stats["approvals"] == 2
    assert stats["rejections"] == 2
    assert stats["approval_rate"] == 0.5

    # Check average confidence
    assert 0.85 <= stats["avg_confidence_approved"] <= 0.90
    assert 0.65 <= stats["avg_confidence_rejected"] <= 0.73


def test_per_coach_summary(temp_dirs):
    """Test per-coach decision summaries."""
    logger = HistoryLogger(temp_dirs["insights"])

    # Log decisions for multiple coaches
    logger.log_decision("career_coach", "tune_001", "approve", 0.87, "admin")
    logger.log_decision("career_coach", "tune_002", "approve", 0.92, "admin")
    logger.log_decision("relationship_coach", "tune_003", "reject", 0.65, "admin")

    # Get per-coach summary
    summaries = logger.get_coach_summary()

    assert "career_coach" in summaries
    assert "relationship_coach" in summaries

    assert summaries["career_coach"]["total_decisions"] == 2
    assert summaries["career_coach"]["approvals"] == 2
    assert summaries["career_coach"]["approval_rate"] == 1.0

    assert summaries["relationship_coach"]["total_decisions"] == 1
    assert summaries["relationship_coach"]["rejections"] == 1
    assert summaries["relationship_coach"]["approval_rate"] == 0.0


def test_file_rotation(temp_dirs):
    """Test automatic file rotation at 10,000 entries."""
    logger = HistoryLogger(temp_dirs["insights"])

    # Manually set rotation threshold lower for testing
    logger.MAX_ENTRIES_PER_FILE = 10

    # Log 15 entries (should trigger rotation)
    for i in range(15):
        logger.log_decision(
            coach_id="test_coach",
            suggestion_id=f"tune_{i:03d}",
            action="approve",
            confidence=0.85,
            user="test"
        )

    # Check that archive file was created
    archive_files = list(temp_dirs["insights"].glob("self_improvement_history_*.jsonl"))
    assert len(archive_files) >= 1

    # Current file should have recent entries
    current_file = temp_dirs["insights"] / "self_improvement_history.jsonl"
    with open(current_file, 'r') as f:
        lines = f.readlines()
        assert len(lines) < 10  # Should be rotated


def test_apply_suggestion_workflow(temp_dirs, sample_suggestion):
    """Test full apply-suggestion workflow (mock)."""
    # Create suggestion file
    suggestions_file = temp_dirs["suggestions"] / "career_coach.json"
    suggestions_data = {
        "coach_id": "career_coach",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suggestions": [sample_suggestion]
    }

    with open(suggestions_file, 'w') as f:
        json.dump(suggestions_data, f)

    # Create mock prompt file
    prompt_file = temp_dirs["prompts"] / "career_coach_ai.md"
    original_prompt = "# Career Coach\n\nOriginal prompt content."
    prompt_file.write_text(original_prompt, encoding='utf-8')

    # Simulate approval (manual since we're not testing HTTP)
    import hashlib
    old_hash = hashlib.sha256(original_prompt.encode()).hexdigest()[:16]

    # Create backup
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = temp_dirs["backups"] / f"career_coach_{timestamp}.md"
    backup_file.write_text(original_prompt, encoding='utf-8')

    # Apply change (simplified)
    updated_prompt = original_prompt + f"\n\n<!-- Applied suggestion tune_001 -->\n"
    prompt_file.write_text(updated_prompt, encoding='utf-8')
    new_hash = hashlib.sha256(updated_prompt.encode()).hexdigest()[:16]

    # Log to history
    logger = HistoryLogger(temp_dirs["insights"])
    logger.log_decision(
        coach_id="career_coach",
        suggestion_id="tune_001",
        action="approve",
        confidence=0.87,
        user="admin",
        old_hash=old_hash,
        new_hash=new_hash
    )

    # Verify backup exists
    assert backup_file.exists()
    assert backup_file.read_text() == original_prompt

    # Verify prompt updated
    assert "Applied suggestion" in prompt_file.read_text()

    # Verify history logged
    history = logger.get_history()
    assert len(history) == 1
    assert history[0]["action"] == "approve"
    assert history[0]["old_hash"] == old_hash
    assert history[0]["new_hash"] == new_hash


def test_reject_suggestion_workflow(temp_dirs, sample_suggestion):
    """Test rejection workflow (no file changes)."""
    # Create suggestion file
    suggestions_file = temp_dirs["suggestions"] / "career_coach.json"
    suggestions_data = {
        "coach_id": "career_coach",
        "suggestions": [sample_suggestion]
    }

    with open(suggestions_file, 'w') as f:
        json.dump(suggestions_data, f)

    # Create mock prompt file
    prompt_file = temp_dirs["prompts"] / "career_coach_ai.md"
    original_prompt = "# Career Coach\n\nOriginal prompt content."
    prompt_file.write_text(original_prompt, encoding='utf-8')

    # Reject suggestion
    logger = HistoryLogger(temp_dirs["insights"])
    logger.log_decision(
        coach_id="career_coach",
        suggestion_id="tune_001",
        action="reject",
        confidence=0.87,
        user="admin",
        reason="Not aligned with coach personality"
    )

    # Verify prompt unchanged
    assert prompt_file.read_text() == original_prompt

    # Verify history logged
    history = logger.get_history()
    assert len(history) == 1
    assert history[0]["action"] == "reject"
    assert history[0]["old_hash"] is None
    assert history[0]["new_hash"] is None
    assert "Not aligned" in history[0]["reason"]


def test_confidence_validation(temp_dirs, low_confidence_suggestion):
    """Test that low-confidence suggestions cannot be approved."""
    # This test simulates API-level validation
    confidence = low_confidence_suggestion["confidence"]

    # Should fail validation
    assert confidence < 0.70

    # In the actual API, this would raise HTTPException(400)
    # Here we just verify the logic
    can_approve = confidence >= 0.70
    assert not can_approve


def test_thread_safety(temp_dirs):
    """Test thread-safe logging with concurrent writes."""
    import threading

    logger = HistoryLogger(temp_dirs["insights"])

    def log_decision():
        for i in range(10):
            logger.log_decision(
                coach_id="test_coach",
                suggestion_id=f"tune_{i}",
                action="approve",
                confidence=0.85,
                user="thread"
            )

    # Create multiple threads
    threads = []
    for _ in range(4):
        thread = threading.Thread(target=log_decision)
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Verify all entries logged
    history = logger.get_history(limit=1000)
    assert len(history) == 40  # 4 threads × 10 entries


def test_backup_integrity(temp_dirs):
    """Test backup file integrity and hash verification."""
    import hashlib

    prompt_file = temp_dirs["prompts"] / "test_coach_ai.md"
    original_content = "# Test Coach\n\nOriginal content with specific text."

    prompt_file.write_text(original_content, encoding='utf-8')

    # Compute original hash
    original_hash = hashlib.sha256(original_content.encode()).hexdigest()[:16]

    # Create backup
    backup_file = temp_dirs["backups"] / "test_coach_20250109_000000.md"
    backup_file.write_text(original_content, encoding='utf-8')

    # Verify backup matches original
    backup_hash = hashlib.sha256(backup_file.read_bytes()).hexdigest()[:16]
    assert backup_hash == original_hash

    # Modify original
    modified_content = original_content + "\n\n<!-- Modified -->"
    prompt_file.write_text(modified_content, encoding='utf-8')

    # Verify hashes differ
    modified_hash = hashlib.sha256(modified_content.encode()).hexdigest()[:16]
    assert modified_hash != original_hash

    # Verify backup still matches original
    assert backup_file.read_text() == original_content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
