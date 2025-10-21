"""
Tests for RR adapter reference population integration (Phase 10.2 Hotfix).

Verifies:
1. UCN values in [0,1] are used directly for reference_percentile mode
2. Legacy rr_raw values (0-100, 0-1000) are coerced correctly
3. Out-of-range values are clamped and warned
4. Actual CDF lookups produce expected percentiles
"""

import pytest
from unittest.mock import patch, MagicMock
from ReDNACoreDemo.core.metrics.rr_adapter import (
    rr_to_percentile,
    _coerce_legacy_rr_raw_to_ucn,
    _normalize_ucn_for_reference,
)
from ReDNACoreDemo.core.metrics.reference_source import ReferenceCDF


@pytest.fixture
def mock_synthetic_cdf():
    """Create a mock synthetic CDF matching generic.json stats."""
    # Simulate the actual distribution from generic.json
    # Mean ~0.49, P5 ~0.17, P71 ~0.74
    samples = [i / 100.0 for i in range(101)]  # Uniform 0.00-1.00 for testing

    cdf = ReferenceCDF(
        samples=samples,
        n_samples=len(samples),
        source="SYNTHETIC",
        universe="combined",
        cohort_keys=[],
        cohort_values={},
        generated_at="2025-10-21T00:00:00Z",
        metadata={"test": "fixture"}
    )
    return cdf


class TestNormalizeUCNForReference:
    """Test _normalize_ucn_for_reference() helper for reference_percentile mode."""

    def test_none_returns_default(self):
        """None should return 0.5 (default)."""
        assert _normalize_ucn_for_reference(None) == 0.5

    def test_normalized_ucn_passthrough(self):
        """UCN in [0,1] should pass through unchanged."""
        assert _normalize_ucn_for_reference(0.0) == 0.0
        assert _normalize_ucn_for_reference(0.17) == 0.17
        assert _normalize_ucn_for_reference(0.5) == 0.5
        assert _normalize_ucn_for_reference(0.74) == 0.74
        assert _normalize_ucn_for_reference(1.0) == 1.0

    def test_legacy_percentage_divided_by_100(self):
        """Values in (1, 100] should be treated as percentage and divided by 100."""
        assert _normalize_ucn_for_reference(50.0) == 0.5
        assert _normalize_ucn_for_reference(80.0) == 0.80
        assert _normalize_ucn_for_reference(100.0) == 1.0

    def test_legacy_score_divided_by_1000(self):
        """Values in (100, 1000] should be treated as 0-1000 score and divided by 1000."""
        assert _normalize_ucn_for_reference(132.0) == 0.132
        assert _normalize_ucn_for_reference(500.0) == 0.5
        assert _normalize_ucn_for_reference(780.0) == 0.78
        assert _normalize_ucn_for_reference(1000.0) == 1.0

    def test_out_of_range_clamped_and_warned(self, caplog):
        """Values > 1000 should be clamped to [0,1] and logged with reference-specific message."""
        result = _normalize_ucn_for_reference(1500.0)
        assert 0.0 <= result <= 1.0
        assert "reference: unexpected rr_raw=1500.00" in caplog.text
        assert "clamped to UCN" in caplog.text

    def test_negative_clamped_and_warned(self, caplog):
        """Negative values should be clamped to 0.0 and logged."""
        result = _normalize_ucn_for_reference(-10.0)
        assert result == 0.0
        assert "reference: unexpected rr_raw=-10.00" in caplog.text


class TestCoerceLegacyRRRawToUCN:
    """Test _coerce_legacy_rr_raw_to_ucn() helper."""

    def test_none_returns_default(self):
        """None should return 0.5 (default)."""
        assert _coerce_legacy_rr_raw_to_ucn(None) == 0.5

    def test_normalized_ucn_passthrough(self):
        """UCN in [0,1] should pass through unchanged."""
        assert _coerce_legacy_rr_raw_to_ucn(0.0) == 0.0
        assert _coerce_legacy_rr_raw_to_ucn(0.17) == 0.17
        assert _coerce_legacy_rr_raw_to_ucn(0.5) == 0.5
        assert _coerce_legacy_rr_raw_to_ucn(0.74) == 0.74
        assert _coerce_legacy_rr_raw_to_ucn(1.0) == 1.0

    def test_percentage_0_100_divided_by_100(self):
        """Values in (1, 100] should be treated as percentage and divided by 100."""
        assert _coerce_legacy_rr_raw_to_ucn(50.0) == 0.5
        assert _coerce_legacy_rr_raw_to_ucn(62.0) == 0.62
        assert _coerce_legacy_rr_raw_to_ucn(100.0) == 1.0

    def test_legacy_score_0_1000_divided_by_1000(self):
        """Values in (100, 1000] should be treated as 0-1000 score and divided by 1000."""
        assert _coerce_legacy_rr_raw_to_ucn(500.0) == 0.5
        assert _coerce_legacy_rr_raw_to_ucn(780.0) == 0.78
        assert _coerce_legacy_rr_raw_to_ucn(1000.0) == 1.0

    def test_out_of_range_clamped_and_warned(self, caplog):
        """Values > 1000 should be clamped to [0,1] and logged."""
        result = _coerce_legacy_rr_raw_to_ucn(1500.0)
        assert 0.0 <= result <= 1.0
        assert "Unexpected rr_raw=1500.00" in caplog.text
        assert "coerced to UCN" in caplog.text

    def test_negative_clamped_and_warned(self, caplog):
        """Negative values should be clamped to 0.0 and logged."""
        result = _coerce_legacy_rr_raw_to_ucn(-10.0)
        assert result == 0.0
        assert "Unexpected rr_raw=-10.00" in caplog.text


class TestRRToPercentileReferenceMode:
    """Test rr_to_percentile() with reference_percentile mode."""

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_ucn_0p17_reference(self, mock_get_cdf, mock_synthetic_cdf):
        """UCN=0.17 should produce RR≈17% (using uniform CDF for testing)."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=0.17,
            rr_scale="reference_percentile",
            trait_id="PaDNA.Chronotype",
            user_id="test_user",
            use_reference=True
        )

        assert result["rr"] == pytest.approx(17.0, abs=1.0)  # ±1pp tolerance
        assert result["curiosity"] == pytest.approx(83.0, abs=1.0)
        assert result["rr_meta"]["scale"] == "reference_percentile"
        assert result["rr_meta"]["reference"]["source"] == "SYNTHETIC"
        assert result["rr_meta"]["reference"]["universe"] == "combined"

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_ucn_0p74_reference(self, mock_get_cdf, mock_synthetic_cdf):
        """UCN=0.74 should produce RR≈74% (using uniform CDF for testing)."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=0.74,
            rr_scale="reference_percentile",
            trait_id="BehaviorDNA.Sleep.Chronotype",
            user_id="test_user",
            use_reference=True
        )

        assert result["rr"] == pytest.approx(74.0, abs=1.0)
        assert result["curiosity"] == pytest.approx(26.0, abs=1.0)
        assert result["rr_meta"]["scale"] == "reference_percentile"
        assert result["rr_meta"]["reference"]["source"] == "SYNTHETIC"

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_ucn_0p50_reference_median(self, mock_get_cdf, mock_synthetic_cdf):
        """UCN=0.50 should produce RR≈50% (median)."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=0.50,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        assert result["rr"] == pytest.approx(50.0, abs=1.0)

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_legacy_percent_62_reference_via_coercion(self, mock_get_cdf, mock_synthetic_cdf):
        """Legacy rr_raw=62 (percentage) should be coerced to 0.62 when scale=None."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        # When rr_scale is None (not "reference_percentile"), use coercion
        result = rr_to_percentile(
            rr_raw=62.0,
            rr_scale=None,
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # 62.0 → coerced to 0.62 → CDF lookup → ~62%
        assert result["rr"] == pytest.approx(62.0, abs=2.0)

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_legacy_score_780_reference_via_coercion(self, mock_get_cdf, mock_synthetic_cdf):
        """Legacy rr_raw=780 (0-1000 score) should be coerced to 0.78 when scale=None."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=780.0,
            rr_scale=None,
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # 780.0 → coerced to 0.78 → CDF lookup → ~78%
        assert result["rr"] == pytest.approx(78.0, abs=2.0)

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_out_of_range_clamped_and_warned(self, mock_get_cdf, mock_synthetic_cdf, caplog):
        """rr_raw > 1000 should be clamped and warned."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=1500.0,
            rr_scale=None,
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # Should be clamped to valid range
        assert 0.0 <= result["rr"] <= 100.0
        assert "Unexpected rr_raw=1500.00" in caplog.text

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_reference_percentile_legacy_80_becomes_0p80(self, mock_get_cdf, mock_synthetic_cdf):
        """rr_raw=80.0 with scale='reference_percentile' should be treated as percentage → 0.80."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=80.0,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # 80.0 is > 1.0, so treated as percentage: 80.0 / 100 = 0.80 UCN
        # With uniform CDF [0-1], UCN=0.80 → ~80th percentile
        assert result["rr"] == pytest.approx(80.0, abs=2.0)
        assert result["rr_meta"]["scale"] == "reference_percentile"

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_reference_percentile_legacy_100_becomes_1p0(self, mock_get_cdf, mock_synthetic_cdf):
        """rr_raw=100.0 with scale='reference_percentile' should be treated as percentage → 1.0."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=100.0,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # 100.0 / 100 = 1.0 UCN → ~99-100th percentile
        assert result["rr"] == pytest.approx(100.0, abs=2.0)

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_reference_percentile_legacy_132_becomes_0p132(self, mock_get_cdf, mock_synthetic_cdf):
        """rr_raw=132.0 with scale='reference_percentile' should be treated as 0.132."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=132.0,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # 132.0 → 0.132 UCN → ~13th percentile
        assert result["rr"] == pytest.approx(13.2, abs=1.0)

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_reference_percentile_normalized_0p74_passthrough(self, mock_get_cdf, mock_synthetic_cdf):
        """rr_raw=0.74 with scale='reference_percentile' should pass through as 0.74."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=0.74,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # 0.74 → 0.74 UCN → ~74th percentile
        assert result["rr"] == pytest.approx(74.0, abs=1.0)

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_reference_percentile_out_of_range_warned(self, mock_get_cdf, mock_synthetic_cdf, caplog):
        """Out-of-range values should use reference-specific warning message."""
        mock_get_cdf.return_value = (mock_synthetic_cdf, None)

        result = rr_to_percentile(
            rr_raw=2000.0,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # Should be clamped and warned
        assert 0.0 <= result["rr"] <= 100.0
        assert "reference: unexpected rr_raw=2000.00" in caplog.text


class TestRRToPercentileLegacyModes:
    """Test rr_to_percentile() with legacy 0_100 and 0_1000 scales."""

    def test_0_1000_scale_divides_by_10(self):
        """rr_scale=0_1000 should divide by 10."""
        result = rr_to_percentile(
            rr_raw=800.0,
            rr_scale="0_1000",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=False
        )

        assert result["rr"] == 80.0
        assert result["curiosity"] == 20.0
        assert result["rr_meta"]["scale"] == "0_1000"

    def test_0_100_scale_passthrough(self):
        """rr_scale=0_100 should pass through (with clamping)."""
        result = rr_to_percentile(
            rr_raw=75.0,
            rr_scale="0_100",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=False
        )

        assert result["rr"] == 75.0
        assert result["curiosity"] == 25.0
        assert result["rr_meta"]["scale"] == "0_100"


class TestRRToPercentileFallbackBehavior:
    """Test fallback behavior when reference is disabled or fails."""

    @patch("ReDNACoreDemo.core.metrics.rr_adapter.REFERENCE_POP_ENABLED", False)
    def test_reference_disabled_uses_fallback(self):
        """When REFERENCE_POP_ENABLED=False, should use legacy fallback."""
        result = rr_to_percentile(
            rr_raw=0.74,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # Fallback treats rr_raw as 0-100 percentage
        assert result["rr"] == 0.74  # Clamped to valid range
        assert result["rr_meta"]["source"] == "adapter"

    @patch("ReDNACoreDemo.core.metrics.reference_source.get_reference_cdf")
    def test_cdf_exception_uses_fallback(self, mock_get_cdf):
        """When get_reference_cdf raises exception, should fallback gracefully."""
        mock_get_cdf.side_effect = Exception("CDF load failed")

        result = rr_to_percentile(
            rr_raw=0.74,
            rr_scale="reference_percentile",
            trait_id="TestDNA.Trait",
            user_id="test_user",
            use_reference=True
        )

        # Should fallback to treating rr_raw as percentage
        assert 0.0 <= result["rr"] <= 100.0
        assert "error" in result["rr_meta"]


class TestRRToPercentileRealCDFIntegration:
    """Integration tests with actual synthetic CDF files."""

    @patch.dict("os.environ", {"REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "SYNTHETIC"}, clear=False)
    def test_real_cdf_ucn_0p17_generic(self):
        """Test with actual generic.json CDF for UCN=0.17."""
        from ReDNACoreDemo.core.metrics.reference_source import get_reference_cdf

        # This will load the real generic.json
        cdf, _ = get_reference_cdf("UnknownTrait", cohort_values=None)

        # Compute percentile for UCN=0.17
        rr = cdf.percentile_for_ucn(0.17)

        # Based on generic.json, UCN=0.17 should be around 5th percentile
        assert 0.0 <= rr <= 10.0, f"Expected RR≈5%, got {rr:.2f}%"

    @patch.dict("os.environ", {"REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "SYNTHETIC"}, clear=False)
    def test_real_cdf_ucn_0p74_generic(self):
        """Test with actual generic.json CDF for UCN=0.74."""
        from ReDNACoreDemo.core.metrics.reference_source import get_reference_cdf

        cdf, _ = get_reference_cdf("UnknownTrait", cohort_values=None)
        rr = cdf.percentile_for_ucn(0.74)

        # Based on generic.json, UCN=0.74 should be around 89th percentile
        # (the actual CDF is not uniform)
        assert 85.0 <= rr <= 92.0, f"Expected RR≈89%, got {rr:.2f}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
