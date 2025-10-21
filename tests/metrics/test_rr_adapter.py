"""
Tests for RR adapter (Phase 9 RR Normalization).
"""

import pytest
from ReDNACoreDemo.core.metrics.rr_adapter import rr_to_percentile, clamp


def test_clamp():
    """Test clamp utility function."""
    assert clamp(50, 0, 100) == 50
    assert clamp(-10, 0, 100) == 0
    assert clamp(150, 0, 100) == 100
    assert clamp(0, 0, 100) == 0
    assert clamp(100, 0, 100) == 100


def test_rr_adapter_0_1000_scale():
    """Test normalization from 0-1000 scale."""
    result = rr_to_percentile(
        rr_raw=800.0,
        rr_scale="0_1000",
        trait_id="PaDNA.Chronotype",
        user_id="test_user"
    )

    assert result["rr"] == 80.0
    assert result["curiosity"] == 20.0
    assert result["rr_meta"]["rr_raw"] == 800.0
    assert result["rr_meta"]["scale"] == "0_1000"


def test_rr_adapter_0_100_scale():
    """Test normalization from 0-100 scale (already normalized)."""
    result = rr_to_percentile(
        rr_raw=63.0,
        rr_scale="0_100",
        trait_id="PaDNA.EyeColor",
        user_id="test_user"
    )

    assert result["rr"] == 63.0
    assert result["curiosity"] == 37.0
    assert result["rr_meta"]["rr_raw"] == 63.0
    assert result["rr_meta"]["scale"] == "0_100"


def test_rr_adapter_boundary_clamps():
    """Test clamping at boundaries."""
    # Below 0 (0-1000 scale)
    result = rr_to_percentile(
        rr_raw=-100.0,
        rr_scale="0_1000",
        trait_id="test",
        user_id="test_user"
    )
    assert result["rr"] == 0.0
    assert result["curiosity"] == 100.0

    # Above 1000 (0-1000 scale)
    result = rr_to_percentile(
        rr_raw=1200.0,
        rr_scale="0_1000",
        trait_id="test",
        user_id="test_user"
    )
    assert result["rr"] == 100.0
    assert result["curiosity"] == 0.0

    # Above 100 (0-100 scale)
    result = rr_to_percentile(
        rr_raw=150.0,
        rr_scale="0_100",
        trait_id="test",
        user_id="test_user"
    )
    assert result["rr"] == 100.0
    assert result["curiosity"] == 0.0


def test_rr_adapter_none_value():
    """Test handling of None values."""
    result = rr_to_percentile(
        rr_raw=None,
        rr_scale="0_100",
        trait_id="test",
        user_id="test_user"
    )

    # Should fallback to 50.0
    assert result["rr"] == 50.0
    assert result["curiosity"] == 50.0


def test_curiosity_equals_100_minus_rr():
    """Test that curiosity is always 100 - rr."""
    test_cases = [
        (800, "0_1000", 80, 20),
        (200, "0_1000", 20, 80),
        (63, "0_100", 63, 37),
        (25, "0_100", 25, 75),
        (1000, "0_1000", 100, 0),
        (0, "0_1000", 0, 100),
    ]

    for rr_raw, scale, expected_rr, expected_curiosity in test_cases:
        result = rr_to_percentile(
            rr_raw=rr_raw,
            rr_scale=scale,
            trait_id="test",
            user_id="test_user"
        )
        assert result["rr"] == expected_rr, f"Failed for rr_raw={rr_raw}, scale={scale}"
        assert result["curiosity"] == expected_curiosity, f"Failed for rr_raw={rr_raw}, scale={scale}"
        assert result["rr"] + result["curiosity"] == 100.0


def test_rr_meta_structure():
    """Test that rr_meta contains expected fields."""
    result = rr_to_percentile(
        rr_raw=750.0,
        rr_scale="0_1000",
        trait_id="PaDNA.Chronotype",
        user_id="ai_ready_probe"
    )

    assert "rr_meta" in result
    meta = result["rr_meta"]

    assert "rr_raw" in meta
    assert "scale" in meta
    assert "source" in meta
    assert "trait_id" in meta
    assert "user_id" in meta

    assert meta["rr_raw"] == 750.0
    assert meta["scale"] == "0_1000"
    assert meta["trait_id"] == "PaDNA.Chronotype"
    assert meta["user_id"] == "ai_ready_probe"
