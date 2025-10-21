"""
Tests for reference population percentiles (Phase 9).
"""

import pytest
import json
from pathlib import Path
from ReDNACoreDemo.core.reference_pop.reference_pop import (
    reference_percentile_for_ucn,
    load_distribution,
)


def test_load_chronotype_distribution():
    """Test loading Chronotype distribution."""
    samples = load_distribution("Chronotype")
    assert samples is not None
    assert len(samples) > 0
    # Verify sorted
    assert samples == sorted(samples)


def test_percentile_monotonic():
    """Test that percentiles increase monotonically with UCN."""
    trait_id = "Chronotype"

    # Test increasing UCN values should give increasing percentiles
    ucn_values = [0.1, 0.3, 0.5, 0.7, 0.9]
    percentiles = [reference_percentile_for_ucn(trait_id, ucn) for ucn in ucn_values]

    for i in range(len(percentiles) - 1):
        assert percentiles[i] <= percentiles[i + 1], (
            f"Percentiles not monotonic: {percentiles}"
        )


def test_percentile_boundaries():
    """Test 0th and 100th percentile edge cases."""
    trait_id = "Chronotype"

    # Minimum UCN should give low percentile
    p_min = reference_percentile_for_ucn(trait_id, 0.0)
    assert 0.0 <= p_min <= 10.0, f"Expected low percentile for UCN=0, got {p_min}"

    # Maximum UCN should give high percentile
    p_max = reference_percentile_for_ucn(trait_id, 1.0)
    assert 90.0 <= p_max <= 100.0, f"Expected high percentile for UCN=1, got {p_max}"


def test_percentile_range():
    """Test that percentiles are always in [0, 100]."""
    trait_id = "Chronotype"

    # Test various UCN values
    for ucn in [0.0, 0.25, 0.5, 0.75, 1.0]:
        p = reference_percentile_for_ucn(trait_id, ucn)
        assert 0.0 <= p <= 100.0, f"Percentile {p} out of range for UCN={ucn}"


def test_missing_distribution_fallback():
    """Test fallback for traits without distributions."""
    trait_id = "NonExistent.Trait"
    p = reference_percentile_for_ucn(trait_id, 0.5)

    # Should fallback to 50.0 (middle percentile)
    assert p == 50.0


def test_distribution_cache():
    """Test that distributions are cached."""
    trait_id = "Chronotype"

    # Load twice
    dist1 = load_distribution(trait_id)
    dist2 = load_distribution(trait_id)

    # Should be the same object (cached)
    assert dist1 is dist2
