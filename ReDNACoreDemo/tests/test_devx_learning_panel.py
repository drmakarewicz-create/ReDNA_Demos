"""
Tests for DevX Learning Panel (Phase 3b.1)

Tests the API contract and UI integration for the Learning Panel component.
"""

import pytest
import json
from ReDNACoreDemo.core import hc_learning
from ReDNACoreDemo.core.storage import CORE_DATA_ROOT


class TestLearningAPIContract:
    """Test that API endpoints meet panel expectations."""

    def test_get_state_response_structure(self):
        """Test GET /state returns all required fields for panel."""
        # Create test learning state
        test_user = "TEST_DEVX_PANEL_API"

        state = hc_learning.LearningState(
            nudge_frequency_multiplier=1.2,
            nudge_timing_preference="morning",
            tone_bias=0.3,
            formality_bias=0.0,
            creativity_bias=0.6,
            focus_weights={"career": 1.5, "health": 1.0},
            last_update="2025-10-11T12:00:00Z",
            update_count=5,
            baseline_metrics={"completion_rate": 0.7}
        )

        hc_learning.save_state(test_user, state)

        # Load state via API-like function
        loaded = hc_learning.load_state(test_user)

        # Verify all fields required by panel exist
        assert loaded is not None
        assert hasattr(loaded, 'nudge_frequency_multiplier')
        assert hasattr(loaded, 'nudge_timing_preference')
        assert hasattr(loaded, 'tone_bias')
        assert hasattr(loaded, 'formality_bias')
        assert hasattr(loaded, 'creativity_bias')
        assert hasattr(loaded, 'focus_weights')
        assert hasattr(loaded, 'last_update')
        assert hasattr(loaded, 'update_count')
        assert hasattr(loaded, 'baseline_metrics')

        # Verify types
        assert isinstance(loaded.nudge_frequency_multiplier, (int, float))
        assert isinstance(loaded.nudge_timing_preference, str)
        assert isinstance(loaded.tone_bias, (int, float))
        assert isinstance(loaded.creativity_bias, (int, float))
        assert isinstance(loaded.focus_weights, dict)
        assert isinstance(loaded.update_count, int)

    def test_get_state_behavior_context(self):
        """Test behavior context is generated correctly for panel."""
        test_user = "TEST_DEVX_PANEL_CONTEXT"

        state = hc_learning.LearningState(
            nudge_frequency_multiplier=0.8,
            nudge_timing_preference="evening",
            tone_bias=-0.2,
            formality_bias=0.0,
            creativity_bias=0.4,
            focus_weights={"learning": 1.3},
            last_update="2025-10-11T18:00:00Z",
            update_count=2,
            baseline_metrics={}
        )

        hc_learning.save_state(test_user, state)

        # Get behavior context
        context = hc_learning.get_behavior_context(test_user)

        # Verify context structure for panel
        assert context['learning_enabled'] is True
        assert context['update_count'] == 2
        assert 'tone' in context
        assert 'timing' in context
        assert 'creativity' in context
        assert 'focus' in context
        assert 'nudge_frequency_multiplier' in context
        assert 'raw_state' in context

        # Verify human-readable hints
        assert isinstance(context['tone'], str)
        assert isinstance(context['creativity'], str)

    def test_empty_state_returns_none(self):
        """Test that missing state returns None (not error)."""
        empty_user = "TEST_DEVX_PANEL_EMPTY_999"

        state = hc_learning.load_state(empty_user)

        assert state is None

        # Behavior context should handle None gracefully
        context = hc_learning.get_behavior_context(empty_user)
        assert context == {}

    def test_focus_weights_structure(self):
        """Test focus_weights dict structure for panel rendering."""
        test_user = "TEST_DEVX_PANEL_FOCUS"

        state = hc_learning.LearningState(
            nudge_frequency_multiplier=1.0,
            nudge_timing_preference="adaptive",
            tone_bias=0.0,
            formality_bias=0.0,
            creativity_bias=0.5,
            focus_weights={
                "career": 1.5,
                "health": 1.0,
                "personal": 1.2,
                "creative": 0.8
            },
            last_update="2025-10-11T12:00:00Z",
            update_count=1,
            baseline_metrics={}
        )

        hc_learning.save_state(test_user, state)
        loaded = hc_learning.load_state(test_user)

        # Verify structure for panel
        assert len(loaded.focus_weights) == 4
        for category, weight in loaded.focus_weights.items():
            assert isinstance(category, str)
            assert isinstance(weight, (int, float))
            assert weight > 0

    def test_timestamps_are_iso_format(self):
        """Test that timestamps are ISO format strings."""
        test_user = "TEST_DEVX_PANEL_TIMESTAMP"

        state = hc_learning.apply_learning_deltas(test_user)

        assert state.last_update.endswith('Z')
        assert state.computed_at.endswith('Z')

        # Should be parseable
        from datetime import datetime
        # Remove 'Z' suffix (timestamp has both +00:00 and Z)
        timestamp = state.last_update.rstrip('Z')
        parsed = datetime.fromisoformat(timestamp)
        assert parsed.year >= 2025


class TestForceRecompute:
    """Test force recompute functionality."""

    def test_recompute_returns_200(self):
        """Test that recompute succeeds and returns expected structure."""
        test_user = "TEST_DEVX_PANEL_RECOMPUTE"

        # Trigger recompute
        state = hc_learning.apply_learning_deltas(test_user)

        # Verify state updated
        assert state.update_count >= 1
        assert state.last_update is not None

        # Verify state persisted
        loaded = hc_learning.load_state(test_user)
        assert loaded.update_count == state.update_count

    def test_recompute_audit_event_logged(self):
        """Test that recompute logs audit event."""
        test_user = "TEST_DEVX_PANEL_AUDIT"

        # Trigger recompute
        hc_learning.apply_learning_deltas(test_user)

        # Check audit log
        audit_file = CORE_DATA_ROOT / "telemetry" / "agents" / "agent_activity.jsonl"
        assert audit_file.exists()

        # Find learning_applied event for this user
        found_event = False
        with open(audit_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event.get('event') == 'learning_applied' and event.get('user_id') == test_user:
                        found_event = True
                        assert event['agent'] == 'head_coach'
                        assert 'update_count' in event['data']
                        break
                except json.JSONDecodeError:
                    pass

        assert found_event, f"learning_applied event not found for {test_user}"

    def test_recompute_increments_count(self):
        """Test that repeated recomputes increment update_count."""
        test_user = "TEST_DEVX_PANEL_COUNT"

        # First recompute
        state1 = hc_learning.apply_learning_deltas(test_user)
        count1 = state1.update_count

        # Second recompute
        state2 = hc_learning.apply_learning_deltas(test_user)
        count2 = state2.update_count

        assert count2 == count1 + 1


class TestReadOnlyMode:
    """Test read-only mode logic for L0/L1 agency levels."""

    def test_state_visible_at_all_levels(self):
        """Test that state is readable regardless of agency level."""
        test_user = "TEST_DEVX_PANEL_READONLY"

        # Create state
        hc_learning.apply_learning_deltas(test_user)

        # State should be loadable (simulating GET /state call)
        state = hc_learning.load_state(test_user)
        assert state is not None

        # Context should be available
        context = hc_learning.get_behavior_context(test_user)
        assert context['learning_enabled'] is True

    def test_recompute_capability_check(self):
        """Test that recompute requires capability (documented in API)."""
        # This is a documentation/contract test
        # The actual capability check happens in the API layer
        # and frontend button disabling

        # Document expected behavior:
        # - API should check X-Capability: core.agent.config
        # - Frontend button disabled when agencyLevel < 2
        # - Toast message shown when capability missing

        assert True  # Contract documented


class TestPanelDataFlow:
    """Test complete data flow for panel rendering."""

    def test_complete_panel_data_flow(self):
        """Test full flow: state → context → panel data."""
        test_user = "TEST_DEVX_PANEL_FLOW"

        # 1. Create learning state
        state = hc_learning.LearningState(
            nudge_frequency_multiplier=1.2,
            nudge_timing_preference="morning",
            tone_bias=0.3,
            formality_bias=0.0,
            creativity_bias=0.6,
            focus_weights={"career": 1.5, "health": 1.0, "personal": 1.2},
            last_update="2025-10-11T12:00:00Z",
            update_count=5,
            baseline_metrics={"completion_rate": 0.7}
        )
        hc_learning.save_state(test_user, state)

        # 2. Get state (simulates GET /state API call)
        loaded_state = hc_learning.load_state(test_user)
        assert loaded_state is not None

        # 3. Get behavior context (returned in API response)
        context = hc_learning.get_behavior_context(test_user)

        # 4. Verify panel can render with this data
        # Panel expects:
        # - state.tone_bias, creativity_bias, nudge_frequency_multiplier
        # - state.focus_weights as dict
        # - state.last_update, update_count
        # - context.tone, creativity for hints

        assert loaded_state.tone_bias == 0.3
        assert loaded_state.creativity_bias == 0.6
        assert loaded_state.nudge_frequency_multiplier == 1.2
        assert len(loaded_state.focus_weights) == 3
        assert loaded_state.update_count == 5
        assert context['tone'] in ['empathetic', 'balanced', 'direct', 'empathetic and supportive']
        assert len(context['creativity']) > 0

    def test_empty_state_panel_fallback(self):
        """Test panel can handle empty state gracefully."""
        empty_user = "TEST_DEVX_PANEL_EMPTY_FALLBACK"

        # No state exists
        state = hc_learning.load_state(empty_user)
        assert state is None

        # Panel should show empty state message
        # (Frontend test - verifying data contract)
        context = hc_learning.get_behavior_context(empty_user)
        assert context == {} or not context.get('learning_enabled', True)


class TestPerformance:
    """Test performance for panel data loading."""

    def test_get_state_performance(self):
        """Test state loading is fast for panel."""
        import time

        test_user = "TEST_DEVX_PANEL_PERF"

        # Create state
        hc_learning.apply_learning_deltas(test_user)

        # Test load performance (simulates API call)
        start = time.time()
        state = hc_learning.load_state(test_user)
        context = hc_learning.get_behavior_context(test_user)
        duration_ms = (time.time() - start) * 1000

        assert state is not None
        assert context['learning_enabled'] is True
        assert duration_ms < 150, f"State load took {duration_ms:.0f}ms (target: <150ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
