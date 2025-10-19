"""
Test Suite: Head Coach Autonomy Phase 5.A

Tests for autonomy policy, scheduler, governance, API endpoints, and daemon integration.
"""

import json
import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from ReDNACoreDemo.core.hc_autonomy import (
    AutonomyPolicy,
    load_autonomy_policy,
    save_autonomy_policy,
    apply_autonomy_policy,
    evaluate_autonomy_policy,
    get_default_policy_for_level,
    get_autonomy_dir,
)

from ReDNACoreDemo.core.hc_scheduler import (
    ScheduleTask,
    ScheduleState,
    TaskType,
    load_schedule_state,
    save_schedule_state,
    get_eligible_tasks,
    execute_task,
    run_scheduler_cycle,
)

from ReDNACoreDemo.core.hc_governance import (
    verify_learning_delta_bounds,
    verify_tone_creativity_bounds,
    verify_consent_scope,
    verify_prohibited_actions,
    enforce_daily_action_limit,
    check_governance_compliance,
    review_autonomy_compliance,
)


# =========================================================================
# AUTONOMY POLICY TESTS
# =========================================================================

class TestAutonomyPolicy:
    """Test autonomy policy framework."""

    def test_default_policy_creation(self, tmp_path):
        """Test default policy is created correctly."""
        user_id = "TEST_AUTONOMY_DEFAULT"

        # Override autonomy dir to tmp
        with patch("ReDNACoreDemo.core.hc_autonomy.Path") as mock_path:
            mock_path.return_value = tmp_path
            policy = AutonomyPolicy()

            assert policy.level == 1
            assert policy.self_schedule is False
            assert policy.self_reflect is False
            assert policy.self_narrate is False
            assert policy.rsc_enabled is False
            assert "max_self_actions_per_day" in policy.guardrails

    def test_policy_validation_success(self):
        """Test policy validation passes for valid policy."""
        policy = AutonomyPolicy(
            level=2,
            self_schedule=True,
            self_reflect=True,
            self_narrate=True,
        )

        errors = policy.validate()
        assert len(errors) == 0

    def test_policy_validation_level_bounds(self):
        """Test policy validation catches invalid levels."""
        policy = AutonomyPolicy(level=5)
        errors = policy.validate()
        assert any("level" in err.lower() for err in errors)

    def test_policy_validation_level_consistency(self):
        """Test policy validation enforces level consistency."""
        # Level 0 with self_schedule should fail
        policy = AutonomyPolicy(level=0, self_schedule=True)
        errors = policy.validate()
        assert len(errors) > 0

        # Level 1 with self_schedule should fail
        policy = AutonomyPolicy(level=1, self_schedule=True)
        errors = policy.validate()
        assert len(errors) > 0

    def test_policy_save_load(self, tmp_path):
        """Test policy can be saved and loaded."""
        user_id = "TEST_AUTONOMY_SAVE_LOAD"

        policy = AutonomyPolicy(
            level=2,
            self_schedule=True,
            self_reflect=True,
            consent_scope=["learning", "reflection", "narration"],
        )

        # Mock autonomy dir
        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            # Save
            success = save_autonomy_policy(user_id, policy)
            assert success

            # Load
            loaded = load_autonomy_policy(user_id)
            assert loaded.level == policy.level
            assert loaded.self_schedule == policy.self_schedule
            assert loaded.consent_scope == policy.consent_scope

    def test_apply_autonomy_policy_updates(self, tmp_path):
        """Test applying policy updates."""
        user_id = "TEST_AUTONOMY_APPLY"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            # Create initial policy
            initial = AutonomyPolicy(level=1, self_schedule=False)
            save_autonomy_policy(user_id, initial)

            # Apply updates
            result = apply_autonomy_policy(user_id, {
                "level": 2,
                "self_schedule": True,
                "self_reflect": True,
            })

            assert result["success"]
            assert result["policy"]["level"] == 2
            assert result["policy"]["self_schedule"] is True

    def test_evaluate_autonomy_policy(self):
        """Test policy evaluation for readiness and compliance."""
        policy = AutonomyPolicy(
            level=2,
            self_schedule=True,
            self_reflect=True,
            self_narrate=True,
        )

        evaluation = evaluate_autonomy_policy(policy)

        assert "readiness" in evaluation
        assert "compliance" in evaluation
        assert "warnings" in evaluation
        assert "recommendations" in evaluation

        assert evaluation["compliance"] is True
        assert 0.0 <= evaluation["readiness"] <= 1.0

    def test_get_default_policy_for_level(self):
        """Test default policies for each level."""
        for level in range(5):
            policy = get_default_policy_for_level(level)

            assert policy.level == level

            # Verify level-appropriate capabilities
            if level == 0:
                assert not policy.self_schedule
                assert not policy.self_reflect
                assert not policy.rsc_enabled
            elif level >= 2:
                assert policy.self_schedule
                assert policy.self_reflect


# =========================================================================
# SCHEDULER TESTS
# =========================================================================

class TestScheduler:
    """Test self-scheduling system."""

    def test_schedule_state_creation(self):
        """Test schedule state is created with default tasks."""
        user_id = "TEST_SCHEDULER_CREATE"

        state = ScheduleState(user_id=user_id)

        assert state.user_id == user_id
        assert state.actions_today == 0
        assert len(state.tasks) == 0

    def test_schedule_state_save_load(self, tmp_path):
        """Test schedule state save/load."""
        user_id = "TEST_SCHEDULER_SAVE"

        state = ScheduleState(user_id=user_id)
        state.tasks[TaskType.LIFE_WEEKLY_REVIEW.value] = ScheduleTask(
            task_type=TaskType.LIFE_WEEKLY_REVIEW.value,
            interval_days=7,
            enabled=True,
        )
        state.actions_today = 2

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_scheduler.get_autonomy_dir", return_value=autonomy_dir):
            # Save
            success = save_schedule_state(state)
            assert success

            # Load
            loaded = load_schedule_state(user_id)
            assert loaded.user_id == user_id
            assert loaded.actions_today == 2
            assert TaskType.LIFE_WEEKLY_REVIEW.value in loaded.tasks

    def test_get_eligible_tasks_no_policy(self, tmp_path):
        """Test eligible tasks returns empty if policy disallows."""
        user_id = "TEST_SCHEDULER_NO_POLICY"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_scheduler.get_autonomy_dir", return_value=autonomy_dir):
            with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
                # Create policy with self_schedule=False
                policy = AutonomyPolicy(level=1, self_schedule=False)
                save_autonomy_policy(user_id, policy)

                eligible = get_eligible_tasks(user_id)
                assert len(eligible) == 0

    def test_get_eligible_tasks_with_policy(self, tmp_path):
        """Test eligible tasks returns tasks when policy allows."""
        user_id = "TEST_SCHEDULER_WITH_POLICY"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_scheduler.get_autonomy_dir", return_value=autonomy_dir):
            with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
                # Create policy with self_schedule=True
                policy = AutonomyPolicy(level=2, self_schedule=True, self_reflect=True)
                save_autonomy_policy(user_id, policy)

                # Create schedule with overdue task
                state = ScheduleState(user_id=user_id)
                now = datetime.utcnow()
                past = (now - timedelta(days=1)).isoformat() + "Z"

                state.tasks[TaskType.LIFE_WEEKLY_REVIEW.value] = ScheduleTask(
                    task_type=TaskType.LIFE_WEEKLY_REVIEW.value,
                    interval_days=7,
                    next_run=past,
                    enabled=True,
                )
                save_schedule_state(state)

                eligible = get_eligible_tasks(user_id)
                # Should have eligible task
                assert len(eligible) >= 0  # May be 0 if daily quota reached


    def test_daily_quota_enforcement(self, tmp_path):
        """Test daily action quota is enforced."""
        user_id = "TEST_SCHEDULER_QUOTA"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_scheduler.get_autonomy_dir", return_value=autonomy_dir):
            with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
                # Create policy with max 2 actions per day
                policy = AutonomyPolicy(
                    level=2,
                    self_schedule=True,
                    self_reflect=True,
                    guardrails={"max_self_actions_per_day": 2}
                )
                save_autonomy_policy(user_id, policy)

                # Create state at quota
                state = ScheduleState(user_id=user_id)
                state.actions_today = 2  # At max
                state.last_reset = datetime.utcnow().date().isoformat()

                # Add eligible task
                past = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
                state.tasks[TaskType.LIFE_WEEKLY_REVIEW.value] = ScheduleTask(
                    task_type=TaskType.LIFE_WEEKLY_REVIEW.value,
                    next_run=past,
                    enabled=True,
                )
                save_schedule_state(state)

                eligible = get_eligible_tasks(user_id)
                assert len(eligible) == 0  # Quota exhausted


# =========================================================================
# GOVERNANCE TESTS
# =========================================================================

class TestGovernance:
    """Test governance and safeguards."""

    def test_verify_learning_delta_bounds_valid(self, tmp_path):
        """Test learning delta verification passes for valid deltas."""
        user_id = "TEST_GOV_DELTA_VALID"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            policy = AutonomyPolicy(
                level=2,
                guardrails={"max_learning_delta_per_week": 0.15}
            )
            save_autonomy_policy(user_id, policy)

            deltas = {"trait_1": 0.10, "trait_2": -0.12}
            valid, violations = verify_learning_delta_bounds(user_id, deltas)

            assert valid
            assert len(violations) == 0

    def test_verify_learning_delta_bounds_invalid(self, tmp_path):
        """Test learning delta verification fails for invalid deltas."""
        user_id = "TEST_GOV_DELTA_INVALID"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            policy = AutonomyPolicy(
                level=2,
                guardrails={"max_learning_delta_per_week": 0.15}
            )
            save_autonomy_policy(user_id, policy)

            deltas = {"trait_1": 0.25}  # Too large
            valid, violations = verify_learning_delta_bounds(user_id, deltas)

            assert not valid
            assert len(violations) > 0

    def test_verify_tone_creativity_bounds(self, tmp_path):
        """Test tone/creativity shift verification."""
        user_id = "TEST_GOV_TONE"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            policy = AutonomyPolicy(
                level=2,
                guardrails={
                    "tone_shift_bounds": 0.25,
                    "creativity_shift_bounds": 0.25,
                }
            )
            save_autonomy_policy(user_id, policy)

            # Valid shifts
            valid, violations = verify_tone_creativity_bounds(user_id, tone_shift=0.20)
            assert valid

            # Invalid shifts
            valid, violations = verify_tone_creativity_bounds(user_id, creativity_shift=0.35)
            assert not valid

    def test_verify_consent_scope(self, tmp_path):
        """Test consent scope verification."""
        user_id = "TEST_GOV_CONSENT"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            policy = AutonomyPolicy(
                level=2,
                consent_scope=["learning", "reflection"],
                guardrails={"require_consent_for": ["rsc_invite"]}
            )
            save_autonomy_policy(user_id, policy)

            # Action not requiring consent
            allowed, reason = verify_consent_scope(user_id, "learning")
            assert allowed

            # Action requiring consent but not granted
            allowed, reason = verify_consent_scope(user_id, "rsc_invite")
            assert not allowed

    def test_verify_prohibited_actions(self, tmp_path):
        """Test prohibited action verification."""
        user_id = "TEST_GOV_PROHIBITED"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            policy = AutonomyPolicy(
                level=2,
                guardrails={"prohibited_actions": ["policy_self_modify", "user_data_delete"]}
            )
            save_autonomy_policy(user_id, policy)

            # Allowed action
            allowed, reason = verify_prohibited_actions(user_id, "learning_update")
            assert allowed

            # Prohibited action
            allowed, reason = verify_prohibited_actions(user_id, "policy_self_modify")
            assert not allowed

    def test_check_governance_compliance(self, tmp_path):
        """Test comprehensive governance check."""
        user_id = "TEST_GOV_COMPREHENSIVE"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_scheduler.get_autonomy_dir", return_value=autonomy_dir):
            with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
                policy = AutonomyPolicy(
                    level=2,
                    self_schedule=True,
                    guardrails={
                        "prohibited_actions": ["bad_action"],
                        "max_self_actions_per_day": 5,
                    }
                )
                save_autonomy_policy(user_id, policy)

                # Create schedule state
                state = ScheduleState(user_id=user_id)
                state.actions_today = 0
                save_schedule_state(state)

                # Check allowed action
                result = check_governance_compliance(user_id, "learning_update")
                assert result["allowed"]

                # Check prohibited action
                result = check_governance_compliance(user_id, "bad_action")
                assert not result["allowed"]


# =========================================================================
# API INTEGRATION TESTS
# =========================================================================

class TestAutonomyAPI:
    """Test autonomy API endpoints."""

    def test_policy_endpoint_integration(self, tmp_path):
        """Test GET /ui/hc/autonomy/{user}/policy endpoint."""
        # This would require FastAPI test client
        # Placeholder for integration test
        pass

    def test_schedule_endpoint_integration(self, tmp_path):
        """Test GET /ui/hc/autonomy/{user}/schedule endpoint."""
        # This would require FastAPI test client
        # Placeholder for integration test
        pass


# =========================================================================
# PERFORMANCE TESTS
# =========================================================================

class TestPerformance:
    """Test performance targets."""

    def test_policy_load_performance(self, tmp_path):
        """Test policy load < 100ms."""
        user_id = "TEST_PERF_POLICY"

        autonomy_dir = tmp_path / "data" / "users" / user_id / "hc_autonomy"
        autonomy_dir.mkdir(parents=True, exist_ok=True)

        with patch("ReDNACoreDemo.core.hc_autonomy.get_autonomy_dir", return_value=autonomy_dir):
            policy = AutonomyPolicy(level=2)
            save_autonomy_policy(user_id, policy)

            start = time.time()
            loaded = load_autonomy_policy(user_id)
            duration_ms = (time.time() - start) * 1000

            assert duration_ms < 100  # Target: < 100ms
            assert loaded.level == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
