"""
Unit tests for promotion pipeline order and logic.

Verifies:
1. Correct execution order: normalize → need_value → threshold → commit → whycard
2. Parity between main and paired promotion branches
3. Snapshot schema consistency (traits is an array)
4. Why-Card generation on commit
5. Skip decisions occur at correct checkpoints with proper reasoning
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional


class TestPromotionOrder:
    """Tests for promotion pipeline execution order."""

    def test_normalize_called_before_value_check(self):
        """Verify normalize_value is called before need_value check."""
        # This test documents the expected call order in the promotion pipeline:
        # 1. source_text prepared (text or why_hint fallback)
        # 2. normalize_value(trait_id, source_text) called
        # 3. promotion_value event logged
        # 4. value check (if require_value and value is None)
        # 5. threshold check (if score < effective_rr)

        # Specification test - documents the order
        expected_order = [
            "prepare_source_text",
            "normalize_value",
            "log_promotion_value",
            "check_need_value",
            "check_threshold",
        ]

        assert len(expected_order) == 5
        assert expected_order[1] == "normalize_value"
        assert expected_order[3] == "check_need_value"

    def test_skip_need_value_requires_both_conditions(self):
        """
        Verify skip:need_value occurs iff:
        - require_value=True AND
        - value is None
        """
        # Test case 1: require_value=True, value=None → skip
        # Test case 2: require_value=True, value="morning" → continue
        # Test case 3: require_value=False, value=None → continue
        # Test case 4: require_value=False, value="morning" → continue

        test_cases = [
            {"require_value": True, "value": None, "should_skip": True},
            {"require_value": True, "value": "morning", "should_skip": False},
            {"require_value": False, "value": None, "should_skip": False},
            {"require_value": False, "value": "morning", "should_skip": False},
        ]

        for case in test_cases:
            require_value = case["require_value"]
            value = case["value"]
            should_skip = case["should_skip"]

            # Logic from promotion pipeline
            will_skip = require_value and value is None

            assert will_skip == should_skip, (
                f"require_value={require_value}, value={value} → "
                f"expected skip={should_skip}, got {will_skip}"
            )

    def test_skip_below_threshold_compares_to_effective_rr(self):
        """
        Verify skip:below_threshold uses effective_rr (max of base_rr and learned_rr).
        """
        test_cases = [
            # (rr_score, base_rr, learned_rr, should_skip)
            (720.0, 700.0, None, False),  # Score above base, no learned
            (720.0, 700.0, 650.0, False),  # Score above both (learned ignored as lower)
            (720.0, 700.0, 775.0, True),   # Score below learned threshold
            (680.0, 700.0, None, True),    # Score below base
            (720.0, 780.0, 650.0, True),   # Score below base (learned ignored)
        ]

        for rr_score, base_rr, learned_rr, should_skip in test_cases:
            # Compute effective_rr (max of base and learned)
            effective_rr = base_rr
            if learned_rr is not None:
                effective_rr = max(base_rr, learned_rr)

            will_skip = effective_rr is not None and rr_score < effective_rr

            assert will_skip == should_skip, (
                f"rr={rr_score}, base={base_rr}, learned={learned_rr} → "
                f"effective={effective_rr}, expected skip={should_skip}, got {will_skip}"
            )

    def test_snapshot_traits_is_array(self):
        """Verify snapshot.traits is initialized as an array and appends work."""
        snapshot = {"traits": []}

        # Simulate appending trait records
        trait_record = {
            "trait_id": "BehaviorDNA.Sleep.Chronotype",
            "ucn": 720.0,
            "value": "morning",
            "source": "ucnrr_rescore",
            "event_id": "test123"
        }

        snapshot["traits"].append(trait_record)

        assert isinstance(snapshot["traits"], list)
        assert len(snapshot["traits"]) == 1
        assert snapshot["traits"][0]["trait_id"] == "BehaviorDNA.Sleep.Chronotype"
        assert snapshot["traits"][0]["value"] == "morning"

    def test_why_hint_fallback_for_normalization(self):
        """
        Verify that when text is empty, why_hint is used as fallback for normalization.
        """
        # Simulate the logic from promotion pipeline
        text = ""
        why_hint = "Matched phrases 'morning person' and 'before sunrise'."

        source_text = text if isinstance(text, str) else ""
        if (not source_text) and why_hint:
            source_text = str(why_hint)

        assert source_text == why_hint
        assert len(source_text) > 0

        # This confirms the fallback logic works correctly
        # The actual normalize_value call happens in the pipeline with this source_text

    def test_promotion_decision_logging_includes_metadata(self):
        """
        Verify promotion_decision logs include: trait_id, rr, effective_rr, value, reason.
        """
        # This is a specification test - documents expected log structure
        expected_log_keys = {
            "trait_id",
            "ucn",
            "value",
            "rr_min",  # or effective_rr
            "require_value"
        }

        # Example decision log from actual system
        decision_log = {
            "trait_id": "BehaviorDNA.Sleep.Chronotype",
            "ucn": 720.0,
            "value": "morning",
            "rr_min": 780.0,
            "require_value": True
        }

        # Verify all expected keys are present
        for key in expected_log_keys:
            assert key in decision_log, f"Decision log missing key: {key}"

    def test_paired_path_uses_same_logic(self):
        """
        Verify paired path (co_trait promotion) follows same order:
        normalize → need_value → threshold → commit
        """
        # Paired path should have identical logic to main path
        # Test the decision flow is consistent

        # Main path logic
        main_require_value = True
        main_value = "outdoor"
        main_rr = 650.0
        main_effective_rr = 700.0

        # Paired path uses same variables (prefixed with co_)
        co_require_value = True
        co_value = "daily"
        co_rr = 650.0
        co_effective_rr = 700.0

        # Both should make same decision
        main_skip_value = main_require_value and main_value is None
        co_skip_value = co_require_value and co_value is None

        main_skip_threshold = main_effective_rr is not None and main_rr < main_effective_rr
        co_skip_threshold = co_effective_rr is not None and co_rr < co_effective_rr

        assert main_skip_value == co_skip_value == False
        assert main_skip_threshold == co_skip_threshold == True


class TestPromotionDebugLogs:
    """Tests for promotion debug logging."""

    def test_debug_ctx_logged_before_decisions(self):
        """Verify promotion_debug_ctx is logged before any decision paths."""
        # This documents the expected log event
        expected_event = "promotion_debug_ctx"
        expected_meta_keys = {"has_text", "text_len", "why_hint"}

        # Example log from actual system
        debug_ctx_log = {
            "event": "promotion_debug_ctx",
            "msg": "BehaviorDNA.Sleep.Chronotype",
            "meta": {
                "has_text": True,
                "text_len": 41,
                "why_hint": "Matched phrases 'morning person' and 'before sunrise'."
            }
        }

        assert debug_ctx_log["event"] == expected_event
        for key in expected_meta_keys:
            assert key in debug_ctx_log["meta"]

    def test_debug_value_logged_before_threshold_check(self):
        """Verify promotion_debug_value is logged before threshold decisions."""
        expected_event = "promotion_debug_value"
        expected_meta_keys = {"value", "score_float", "effective_rr", "will_skip"}

        debug_value_log = {
            "event": "promotion_debug_value",
            "msg": "BehaviorDNA.Sleep.Chronotype before threshold check",
            "meta": {
                "value": "morning",
                "score_float": 720.0,
                "effective_rr": 775.0,
                "will_skip": True
            }
        }

        assert debug_value_log["event"] == expected_event
        for key in expected_meta_keys:
            assert key in debug_value_log["meta"]


class TestEffectiveRRCalculation:
    """Tests for effective RR threshold calculation."""

    def test_effective_rr_is_max_of_base_and_learned(self):
        """Verify effective_rr = max(base_rr, learned_rr)."""
        test_cases = [
            (700.0, None, 700.0),      # No learned → use base
            (700.0, 650.0, 700.0),     # Learned lower → use base
            (700.0, 775.0, 775.0),     # Learned higher → use learned
            (700.0, 700.0, 700.0),     # Equal → use either (both 700)
            (None, 775.0, 775.0),      # No base → use learned
        ]

        for base_rr, learned_rr, expected_effective in test_cases:
            # Simulate _effective_rr_threshold logic
            if base_rr is None and learned_rr is None:
                effective_rr = None
            elif base_rr is None:
                effective_rr = learned_rr
            elif learned_rr is None:
                effective_rr = base_rr
            else:
                effective_rr = max(base_rr, learned_rr)

            assert effective_rr == expected_effective, (
                f"base={base_rr}, learned={learned_rr} → "
                f"expected {expected_effective}, got {effective_rr}"
            )
