"""
Integration Tests for Head Coach Session Integrity
===================================================

Tests rapid mode switching, cancel token validation, and stale response protection.

Test scenarios:
1. Basic context building
2. Atomic mode switching
3. Cancel token validation
4. Rapid mode switching (race conditions)
5. Concurrent requests with stale token rejection
6. Telemetry logging
7. Context version incrementing
"""

import json
import pytest
import threading
import time
from pathlib import Path
from uuid import uuid4

from ReDNACoreDemo.core.head_coach.session_manager import (
    SessionManager,
    SessionState,
    get_session_manager,
    build_augmented_context,
    validate_request_token
)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create prompts directory with test mandates
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create head coach mandate
    hc_mandate = """
# Head Coach — Base Mandate

You are the Head Coach, a strategic guide for personal growth.

Your role:
- Guide users through self-discovery
- Focus on high-value insights
- Be concise and actionable
"""
    (prompts_dir / "head_coach_ai.md").write_text(hc_mandate)

    # Create photo coach augmentation
    photo_mandate = """
# Photo Coach — Augmented Mandate

role_type: augmentation
parent: head_coach

Mission:
Guide users in analyzing their physical appearance through photos.

Scope:
- Advise on photo-based trait extraction
- Focus on PaDNA domain
"""
    (prompts_dir / "photo_coach_ai.md").write_text(photo_mandate)

    return data_dir


@pytest.fixture
def session_manager(temp_data_dir):
    """Create session manager with temp data dir."""
    return SessionManager(temp_data_dir)


def test_session_state_serialization():
    """Test SessionState to_dict/from_dict roundtrip."""
    state = SessionState(
        active_coach_id="photo_coach",
        context_version=42,
        merged_hash="abc123",
        cancel_token="token-uuid",
        behavior_context={"hints": {"tone": "empathetic"}},
        built_at="2025-01-01T12:00:00Z"
    )

    data = state.to_dict()
    restored = SessionState.from_dict(data)

    assert restored.active_coach_id == "photo_coach"
    assert restored.context_version == 42
    assert restored.merged_hash == "abc123"
    assert restored.cancel_token == "token-uuid"
    assert restored.behavior_context["hints"]["tone"] == "empathetic"


def test_build_initial_context(session_manager, temp_data_dir):
    """Test building initial context for user."""
    user_id = "test_user_1"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build context
    context = session_manager.build_context(user_id, "head_coach")

    assert context["active_coach_id"] == "head_coach"
    assert context["context_version"] == 1  # First version
    assert "cancel_token" in context
    assert "merged_prompt" in context
    assert "behavior_context" in context
    assert context["telemetry"]["augmentations"] == []


def test_build_augmented_context(session_manager, temp_data_dir):
    """Test building augmented context with photo coach."""
    user_id = "test_user_2"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build augmented context
    context = session_manager.build_context(user_id, "photo_coach")

    assert context["active_coach_id"] == "photo_coach"
    assert context["context_version"] == 1
    assert context["telemetry"]["augmentations"] == ["photo_coach"]

    # Verify merged prompt contains both HC and augmentation
    assert "Head Coach" in context["merged_prompt"]
    assert "Photo Coach" in context["merged_prompt"]
    assert "AUGMENTED ROLE" in context["merged_prompt"]


def test_context_version_increments(session_manager, temp_data_dir):
    """Test that context_version increments on every build."""
    user_id = "test_user_3"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build context multiple times
    ctx1 = session_manager.build_context(user_id, "head_coach")
    assert ctx1["context_version"] == 1

    ctx2 = session_manager.build_context(user_id, "photo_coach", force_rebuild=True)
    assert ctx2["context_version"] == 2

    ctx3 = session_manager.build_context(user_id, "head_coach", force_rebuild=True)
    assert ctx3["context_version"] == 3


def test_cancel_token_validation(session_manager, temp_data_dir):
    """Test cancel token validation."""
    user_id = "test_user_4"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build initial context
    ctx1 = session_manager.build_context(user_id, "head_coach")
    token1 = ctx1["cancel_token"]

    # Token should be valid
    assert session_manager.validate_token(user_id, token1) is True

    # Build new context (invalidates old token)
    ctx2 = session_manager.build_context(user_id, "photo_coach", force_rebuild=True)
    token2 = ctx2["cancel_token"]

    # Old token should be invalid
    assert session_manager.validate_token(user_id, token1) is False

    # New token should be valid
    assert session_manager.validate_token(user_id, token2) is True


def test_rapid_mode_switching(session_manager, temp_data_dir):
    """Test rapid mode switching with concurrent requests."""
    user_id = "test_user_5"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Simulate rapid switching
    results = []

    def switch_mode(coach_id, delay=0):
        if delay:
            time.sleep(delay)
        ctx = session_manager.build_context(user_id, coach_id, force_rebuild=True)
        results.append(ctx)

    # Launch concurrent switches
    threads = [
        threading.Thread(target=switch_mode, args=("head_coach", 0)),
        threading.Thread(target=switch_mode, args=("photo_coach", 0.01)),
        threading.Thread(target=switch_mode, args=("head_coach", 0.02)),
        threading.Thread(target=switch_mode, args=("photo_coach", 0.03)),
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Verify all contexts were built
    assert len(results) == 4

    # Verify context versions incremented
    versions = [r["context_version"] for r in results]
    assert len(set(versions)) == 4  # All unique
    assert max(versions) >= 4

    # Verify only last token is valid
    final_session = session_manager.get_session(user_id)
    for result in results:
        token = result["cancel_token"]
        is_valid = session_manager.validate_token(user_id, token)

        # Only the final token should be valid
        if token == final_session.cancel_token:
            assert is_valid is True
        else:
            assert is_valid is False


def test_stale_response_protection(session_manager, temp_data_dir):
    """Test that stale responses can be detected and discarded."""
    user_id = "test_user_6"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build initial context
    ctx1 = session_manager.build_context(user_id, "head_coach")
    token1 = ctx1["cancel_token"]

    # Simulate user switching coaches mid-response
    ctx2 = session_manager.build_context(user_id, "photo_coach", force_rebuild=True)
    token2 = ctx2["cancel_token"]

    # Simulate response arriving with old token
    # In real system, this would be discarded
    assert session_manager.validate_token(user_id, token1) is False
    assert session_manager.validate_token(user_id, token2) is True


def test_single_augmentation_enforcement(session_manager, temp_data_dir):
    """Test that only ONE augmentation is active at a time."""
    user_id = "test_user_7"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build head coach context
    ctx1 = session_manager.build_context(user_id, "head_coach")
    assert ctx1["telemetry"]["augmentations"] == []

    # Build photo coach context
    ctx2 = session_manager.build_context(user_id, "photo_coach", force_rebuild=True)
    assert ctx2["telemetry"]["augmentations"] == ["photo_coach"]
    assert len(ctx2["telemetry"]["augmentations"]) == 1

    # Verify session shows only photo_coach
    session = session_manager.get_session(user_id)
    assert session.active_coach_id == "photo_coach"


def test_telemetry_logging(session_manager, temp_data_dir):
    """Test that telemetry is logged correctly."""
    user_id = "test_user_8"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Create insights directory
    insights_dir = temp_data_dir.parent / "prompts" / "insights"
    insights_dir.mkdir(parents=True)

    # Build context
    session_manager.build_context(user_id, "photo_coach")

    # Verify telemetry file exists
    telemetry_file = insights_dir / "session_integrity.jsonl"
    assert telemetry_file.exists()

    # Read telemetry
    with open(telemetry_file, 'r') as f:
        lines = f.readlines()

    assert len(lines) >= 1

    entry = json.loads(lines[-1])
    assert entry["user_id"] == user_id
    assert entry["active_coach_id"] == "photo_coach"
    assert entry["context_version"] == 1
    assert entry["augmentations"] == ["photo_coach"]
    assert "prompt_hash" in entry
    assert "build_ms" in entry


def test_behavior_context_injection(session_manager, temp_data_dir):
    """Test that behavior context is injected into merged prompt."""
    user_id = "test_user_9"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    feature_state_dir = user_dir / "feature_state"
    feature_state_dir.mkdir()

    # Create feature state with hints
    feature_state = {
        "values": {
            "tone": "Empathetic",
            "creativity": 70,
            "insights_enabled": True
        }
    }

    with open(feature_state_dir / "head_coach.json", 'w') as f:
        json.dump(feature_state, f)

    # Build context
    ctx = session_manager.build_context(user_id, "head_coach")

    # Verify behavior hints in merged prompt
    assert "RUNTIME BEHAVIOR CONTEXT" in ctx["merged_prompt"]
    assert "tone: empathetic" in ctx["merged_prompt"].lower()
    assert "creativity_bias: 0.7" in ctx["merged_prompt"].lower()
    assert "insights_enabled: true" in ctx["merged_prompt"].lower()


def test_persistence_across_instances(temp_data_dir):
    """Test that session state persists across manager instances."""
    user_id = "test_user_10"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Create first manager and build context
    mgr1 = SessionManager(temp_data_dir)
    ctx1 = mgr1.build_context(user_id, "photo_coach")
    version1 = ctx1["context_version"]
    token1 = ctx1["cancel_token"]

    # Create second manager instance (simulates restart)
    mgr2 = SessionManager(temp_data_dir)

    # Verify it loads existing session
    session = mgr2.get_session(user_id)
    assert session.active_coach_id == "photo_coach"
    assert session.context_version == version1
    assert session.cancel_token == token1

    # Build new context with second manager
    ctx2 = mgr2.build_context(user_id, "head_coach", force_rebuild=True)
    assert ctx2["context_version"] == version1 + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
