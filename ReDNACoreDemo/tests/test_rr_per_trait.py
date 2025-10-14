"""
Tests for per-trait RR calculator.

Tests cover:
- Tie handling with mid-rank percentile
- Small-N blending with fictional prior
- Histogram k-anonymity
- Edge cases (missing data, outliers, etc.)

See: docs/RR_IMPLEMENTATION_REFINEMENTS.md section 10
"""

import pytest
import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory

from core.rr_histogram import TraitDistributionHistogram, build_distribution_from_users
from core.rr_per_trait import PerTraitRRCalculator, calculate_trait_rr


class TestTieHandling:
    """Test mid-rank percentile calculation with ties."""

    def test_mid_rank_with_ties(self):
        """Test mid-rank percentile when multiple users have same UCN."""
        # Population: 10 users, 3 with same UCN as test user
        population = [100, 200, 300, 400, 400, 400, 500, 600, 700, 800]
        user_ucn = 400

        calculator = PerTraitRRCalculator(
            distribution_dir=Path("temp"),
            k_min=50  # Small-N will trigger, but we test tie logic
        )

        rr = calculator.calculate_rr_with_ties(user_ucn, population)

        # 3 below (100, 200, 300), 3 equal (400, 400, 400), 4 above
        # Mid-rank: 3 + 1.5 = 4.5 below → RR = 45
        # Note: Small-N blending will adjust this slightly
        assert 40 <= rr <= 50, f"Expected RR ~45 with ties, got {rr}"

    def test_no_ties(self):
        """Test percentile without ties."""
        population = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        user_ucn = 450

        calculator = PerTraitRRCalculator(
            distribution_dir=Path("temp"),
            k_min=50
        )

        rr = calculator.calculate_rr_with_ties(user_ucn, population)

        # 4 below (100, 200, 300, 400), 0 equal, 6 above
        # Empirical: 4/10 = 40%
        # Small-N blending will adjust toward prior (~46% for UCN 450)
        assert 35 <= rr <= 50, f"Expected RR ~40-46, got {rr}"

    def test_all_ties(self):
        """Test when all users have same UCN."""
        population = [500] * 10
        user_ucn = 500

        calculator = PerTraitRRCalculator(
            distribution_dir=Path("temp"),
            k_min=50
        )

        rr = calculator.calculate_rr_with_ties(user_ucn, population)

        # All equal: effective_below = 0 + 10/2 = 5 → RR = 50
        # This is correct: user is at median when all are equal
        assert 45 <= rr <= 55, f"Expected RR ~50 when all equal, got {rr}"


class TestSmallNBlending:
    """Test small-N protection with fictional prior."""

    def test_small_population_blending(self):
        """Test blending when n < k_min."""
        # Only 10 users (n < k_min=50)
        population = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        user_ucn = 350

        calculator = PerTraitRRCalculator(
            distribution_dir=Path("temp"),
            k_min=50,
            prior_mean=500,
            prior_std=150
        )

        rr = calculator.calculate_rr_with_ties(user_ucn, population)

        # Empirical: 3/10 = 30%
        # Prior: UCN 350 vs mean 500 → z=-1.0 → ~16%
        # Blend: lambda=10/50=0.2 → RR = 0.2*30 + 0.8*16 = 18.8%

        assert 15 <= rr <= 25, f"Expected RR ~18.8 with blending, got {rr}"

    def test_large_population_no_blending(self):
        """Test that blending is NOT applied when n >= k_min."""
        # 100 users (n >= k_min=50)
        population = list(range(100, 1000, 9))  # 100 evenly spaced values
        user_ucn = 500

        calculator = PerTraitRRCalculator(
            distribution_dir=Path("temp"),
            k_min=50
        )

        rr = calculator.calculate_rr_with_ties(user_ucn, population)

        # Should be close to empirical (no blending)
        # UCN 500 is ~middle of 100-1000 range → ~40-60 percentile
        assert 35 <= rr <= 65, f"Expected empirical RR ~40-60, got {rr}"

    def test_zero_population(self):
        """Test edge case with no population data."""
        population = []
        user_ucn = 500

        calculator = PerTraitRRCalculator(
            distribution_dir=Path("temp"),
            k_min=50
        )

        rr = calculator.calculate_rr_with_ties(user_ucn, population)

        assert rr == 0.0, f"Expected RR=0 with no population, got {rr}"


class TestHistogramPrivacy:
    """Test k-anonymity enforcement in histogram."""

    def test_k_anonymity_enforcement(self):
        """Test that bins with count < k_min are merged."""
        # Create population with sparse bins
        ucns = [100] * 2 + [200] * 8 + [300] * 3 + [500] * 20

        hist = TraitDistributionHistogram(
            trait_path="test_trait",
            num_bins=50,
            k_min=5
        )

        hist.add_ucns(ucns, winsorize=False)

        # Validate privacy
        privacy = hist.validate_privacy()

        assert privacy["valid"], f"K-anonymity violated: {privacy['message']}"

        # Check that no non-zero bin has count < k_min
        for count in hist.bin_counts:
            if count > 0:
                assert count >= 5, f"Found bin with count {count} < k_min=5"

    def test_privacy_validation(self):
        """Test privacy validation method."""
        hist = TraitDistributionHistogram(
            trait_path="test_trait",
            num_bins=10,
            k_min=5
        )

        # Manually set bins to violate k-anonymity
        hist.bin_counts = np.array([10, 3, 8, 2, 12, 0, 0, 0, 0, 0])
        hist.total_count = sum(hist.bin_counts)

        privacy = hist.validate_privacy()

        assert not privacy["valid"], "Should detect k-anonymity violation"
        assert len(privacy["violations"]) == 2, "Should find 2 violations (counts 3 and 2)"


class TestHistogramPerformance:
    """Test histogram-based percentile calculation."""

    def test_histogram_percentile_accuracy(self):
        """Test histogram percentile matches expected value."""
        # Create uniform distribution
        ucns = list(range(0, 1000, 1))  # 1000 evenly spaced values

        hist = TraitDistributionHistogram(
            trait_path="test_trait",
            num_bins=100,
            k_min=5
        )

        hist.add_ucns(ucns, winsorize=False)

        # Test known percentiles
        test_cases = [
            (100, 10),   # UCN 100 should be ~10th percentile
            (500, 50),   # UCN 500 should be ~50th percentile
            (900, 90),   # UCN 900 should be ~90th percentile
        ]

        for ucn, expected_percentile in test_cases:
            actual = hist.get_percentile(ucn)
            # Allow 5% tolerance due to binning
            assert abs(actual - expected_percentile) < 5, \
                f"UCN {ucn}: expected ~{expected_percentile}%, got {actual}%"

    def test_outlier_winsorization(self):
        """Test that outliers are clipped at P1/P99."""
        # Population with extreme outliers
        ucns = [50] * 100 + [500] * 800 + [9999] * 100

        hist = TraitDistributionHistogram(
            trait_path="test_trait",
            num_bins=100,
            k_min=5
        )

        hist.add_ucns(ucns, winsorize=True, winsorize_percentiles=(1, 99))

        # Verify that distribution stats don't include extreme outlier
        assert hist.mean_ucn < 1000, \
            f"Mean should be < 1000 after winsorization, got {hist.mean_ucn}"

        # P99 should be much less than 9999
        assert hist.quantiles[99] < 9999, \
            f"P99 should be < 9999 after winsorization, got {hist.quantiles[99]}"


class TestMissingTraits:
    """Test handling of missing traits."""

    def test_missing_distribution(self):
        """Test that missing distribution returns None."""
        with TemporaryDirectory() as temp_dir:
            calculator = PerTraitRRCalculator(
                distribution_dir=Path(temp_dir),
                k_min=50
            )

            rr = calculator.calculate_rr(500.0, "NonExistentTrait")

            assert rr is None, "Should return None when distribution doesn't exist"

    def test_curiosity_for_missing_rr(self):
        """Test that missing RR results in curiosity=100."""
        calculator = PerTraitRRCalculator(
            distribution_dir=Path("temp"),
            k_min=50
        )

        curiosity = calculator.calculate_curiosity(None)

        assert curiosity == 100.0, "Missing RR should result in max curiosity"

    def test_metadata_for_missing_distribution(self):
        """Test metadata when distribution doesn't exist."""
        with TemporaryDirectory() as temp_dir:
            calculator = PerTraitRRCalculator(
                distribution_dir=Path(temp_dir),
                k_min=50
            )

            metadata = calculator.calculate_rr_metadata(500.0, "NonExistentTrait")

            assert metadata["rr"] is None
            assert metadata["curiosity"] == 100.0
            assert metadata["method"] == "no_distribution"
            assert metadata["population_size"] == 0


class TestHistogramSerialization:
    """Test histogram save/load functionality."""

    def test_save_and_load(self):
        """Test that histogram can be saved and loaded."""
        ucns = [float(i) for i in range(100, 900, 10)]

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create and save histogram
            hist_original = TraitDistributionHistogram(
                trait_path="TestTrait",
                num_bins=100,
                k_min=5
            )
            hist_original.add_ucns(ucns)

            filepath = hist_original.save(temp_path)

            # Load histogram
            hist_loaded = TraitDistributionHistogram.load(filepath)

            # Verify data matches
            assert hist_loaded.trait_path == hist_original.trait_path
            assert hist_loaded.total_count == hist_original.total_count
            assert abs(hist_loaded.mean_ucn - hist_original.mean_ucn) < 0.1
            assert np.array_equal(hist_loaded.bin_counts, hist_original.bin_counts)

            # Verify percentile calculation matches
            test_ucn = 500.0
            original_percentile = hist_original.get_percentile(test_ucn)
            loaded_percentile = hist_loaded.get_percentile(test_ucn)

            assert abs(original_percentile - loaded_percentile) < 0.01


class TestIntegration:
    """Integration tests for full RR calculation pipeline."""

    def test_end_to_end_rr_calculation(self):
        """Test complete flow: build distribution → calculate RR."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Build population distribution
            user_traits = {
                f"user{i}": float(100 + i * 10)
                for i in range(100)  # 100 users, UCNs from 100 to 1090
            }

            trait_path = "PaDNA.TestTrait"

            hist = build_distribution_from_users(
                trait_path=trait_path,
                user_traits=user_traits,
                output_dir=temp_path,
                k_min=5
            )

            # Calculate RR for test user
            test_ucn = 550.0  # Should be ~45th percentile
            rr = calculate_trait_rr(test_ucn, trait_path, temp_path, k_min=50)

            # Verify RR is in valid range and roughly correct
            assert rr is not None, "RR should not be None"
            assert 0 <= rr <= 100, f"RR must be in [0, 100], got {rr}"
            assert 40 <= rr <= 55, f"Expected RR ~45 for UCN 550, got {rr}"

    def test_rr_with_metadata(self):
        """Test RR calculation with full metadata."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Build small distribution (triggers blending)
            user_traits = {f"user{i}": float(100 + i * 50) for i in range(10)}

            trait_path = "PaDNA.SmallPopulation"

            build_distribution_from_users(
                trait_path=trait_path,
                user_traits=user_traits,
                output_dir=temp_path,
                k_min=5
            )

            # Calculate with metadata
            calculator = PerTraitRRCalculator(
                distribution_dir=temp_path,
                k_min=50  # Population is 10, so blending will occur
            )

            metadata = calculator.calculate_rr_metadata(300.0, trait_path)

            # Verify metadata structure
            assert "rr" in metadata
            assert "curiosity" in metadata
            assert "method" in metadata
            assert "distribution_version" in metadata
            assert "population_size" in metadata
            assert "blending_applied" in metadata

            # Verify small-N blending was applied
            assert metadata["population_size"] == 10
            assert metadata["blending_applied"] is True
            assert metadata["lambda_blend"] is not None
            assert 0 < metadata["lambda_blend"] < 1  # Partial blending


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
