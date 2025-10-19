"""
Tests for Coach Mode Switching System
"""
import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_coach_mode_manager_get_active_mode_default(temp_data_dir):
    """Test that default active mode is head_coach."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)
    active_mode = manager.get_active_mode("test_user")

    assert active_mode == "head_coach"


def test_coach_mode_manager_set_active_mode(temp_data_dir):
    """Test setting active coach mode."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Switch to photo mode
    success = manager.set_active_mode("test_user", "photo")
    assert success is True

    # Verify mode changed
    active_mode = manager.get_active_mode("test_user")
    assert active_mode == "photo"


def test_coach_mode_manager_invalid_mode(temp_data_dir):
    """Test that invalid mode is rejected."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Try invalid mode
    success = manager.set_active_mode("test_user", "invalid_mode")
    assert success is False

    # Mode should still be default
    active_mode = manager.get_active_mode("test_user")
    assert active_mode == "head_coach"


def test_coach_mode_manager_mode_history(temp_data_dir):
    """Test mode switching history tracking."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Make several mode switches
    manager.set_active_mode("test_user", "photo")
    manager.set_active_mode("test_user", "relationship")
    manager.set_active_mode("test_user", "head_coach")

    # Get history
    history = manager.get_mode_history("test_user", limit=10)

    assert len(history) == 3
    assert history[0]["from_mode"] == "head_coach"
    assert history[0]["to_mode"] == "photo"
    assert history[1]["from_mode"] == "photo"
    assert history[1]["to_mode"] == "relationship"
    assert history[2]["from_mode"] == "relationship"
    assert history[2]["to_mode"] == "head_coach"


def test_coach_mode_manager_mode_info(temp_data_dir):
    """Test getting mode information."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Get photo mode info
    info = manager.get_mode_info("photo")

    assert info["mode"] == "photo"
    assert info["display_name"] == "Photo Coach"
    assert info["emoji"] == "📸"
    assert info["valid"] is True
    assert "PaDNA" in info["namespaces"]


def test_coach_mode_manager_stats(temp_data_dir):
    """Test mode usage statistics."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Make mode switches
    manager.set_active_mode("test_user", "photo")
    manager.set_active_mode("test_user", "head_coach")
    manager.set_active_mode("test_user", "photo")
    manager.set_active_mode("test_user", "photo")
    manager.set_active_mode("test_user", "relationship")

    # Get stats
    stats = manager.get_mode_stats("test_user")

    assert stats["total_transitions"] == 5
    assert stats["current_mode"] == "relationship"
    assert stats["mode_counts"]["photo"] == 3
    assert stats["mode_counts"]["head_coach"] == 1
    assert stats["mode_counts"]["relationship"] == 1
    assert stats["most_used_mode"] == "photo"


def test_switch_mode_with_handoff(temp_data_dir):
    """Test complete mode switching with handoff."""
    from core.coach_mode_manager import switch_mode_with_handoff

    result = switch_mode_with_handoff(
        user_id="test_user",
        target_mode="photo",
        data_dir=temp_data_dir,
        delegation_id="test_delegation_123"
    )

    assert result["success"] is True
    assert result["previous_mode"] == "head_coach"
    assert result["new_mode"] == "photo"
    assert result["mode_info"]["display_name"] == "Photo Coach"
    assert result["no_change"] is False


def test_switch_mode_with_handoff_no_change(temp_data_dir):
    """Test switching to same mode (no-op)."""
    from core.coach_mode_manager import switch_mode_with_handoff, CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)
    manager.set_active_mode("test_user", "photo")

    result = switch_mode_with_handoff(
        user_id="test_user",
        target_mode="photo",
        data_dir=temp_data_dir
    )

    assert result["success"] is True
    assert result["previous_mode"] == "photo"
    assert result["new_mode"] == "photo"
    assert result["no_change"] is True


def test_delegation_triggers_mode_switch(temp_data_dir):
    """Test that delegation context is saved during mode switch."""
    from core.coach_mode_manager import switch_mode_with_handoff, CoachModeManager

    delegation_id = "delegation_abc123"

    result = switch_mode_with_handoff(
        user_id="test_user",
        target_mode="relationship",
        data_dir=temp_data_dir,
        delegation_id=delegation_id
    )

    assert result["success"] is True

    # Check that delegation context was saved
    manager = CoachModeManager(data_dir=temp_data_dir)
    history = manager.get_mode_history("test_user", limit=1)

    assert len(history) == 1
    assert history[0]["context"]["delegation_id"] == delegation_id
    assert history[0]["context"]["reason"] == "delegation"


def test_mode_file_persistence(temp_data_dir):
    """Test that mode state persists across manager instances."""
    from core.coach_mode_manager import CoachModeManager

    # Create first manager and set mode
    manager1 = CoachModeManager(data_dir=temp_data_dir)
    manager1.set_active_mode("test_user", "relationship")

    # Create second manager and verify mode persisted
    manager2 = CoachModeManager(data_dir=temp_data_dir)
    active_mode = manager2.get_active_mode("test_user")

    assert active_mode == "relationship"


def test_multiple_users_independent_modes(temp_data_dir):
    """Test that different users can have different active modes."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Set different modes for different users
    manager.set_active_mode("user1", "photo")
    manager.set_active_mode("user2", "relationship")
    manager.set_active_mode("user3", "head_coach")

    # Verify each user has correct mode
    assert manager.get_active_mode("user1") == "photo"
    assert manager.get_active_mode("user2") == "relationship"
    assert manager.get_active_mode("user3") == "head_coach"


def test_mode_history_limit(temp_data_dir):
    """Test that mode history respects limit parameter."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Make 20 mode switches
    for i in range(20):
        mode = "photo" if i % 2 == 0 else "relationship"
        manager.set_active_mode("test_user", mode)

    # Get limited history
    history = manager.get_mode_history("test_user", limit=5)

    assert len(history) == 5


def test_mode_history_max_100(temp_data_dir):
    """Test that mode history caps at 100 transitions."""
    from core.coach_mode_manager import CoachModeManager

    manager = CoachModeManager(data_dir=temp_data_dir)

    # Make 150 mode switches
    for i in range(150):
        mode = "photo" if i % 2 == 0 else "relationship"
        manager.set_active_mode("test_user", mode)

    # Load mode file directly
    mode_file = temp_data_dir / "users" / "test_user" / "coach_mode.json"
    with open(mode_file, "r") as f:
        data = json.load(f)

    # Should only keep last 100
    assert len(data["mode_history"]) == 100
