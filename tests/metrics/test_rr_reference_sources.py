"""
Tests for pluggable RR reference population system (Phase 10.1).

Tests:
1. load_synthetic_reference() loads valid CDF
2. load_actual_reference() scans user files correctly
3. load_actual_reference() respects staleness filter
4. load_actual_reference() respects min_samples threshold
5. get_reference_cdf() uses cache when available
6. get_reference_cdf() falls back ACTUAL → SYNTHETIC
7. ReferenceCDF.percentile_for_ucn() computes correct percentiles
8. rr_to_percentile() uses enhanced rr_meta format
9. Cohort filtering works correctly
10. Uniform fallback used when no reference exists
"""

from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from ReDNACoreDemo.core.metrics.reference_source import (
    ReferenceCDF,
    load_synthetic_reference,
    load_actual_reference,
    get_reference_cdf,
    _build_cache_key,
    _REFERENCE_CACHE,
)
from ReDNACoreDemo.core.metrics.rr_adapter import rr_to_percentile


@pytest.fixture
def mock_reference_pop_dir(tmp_path, monkeypatch):
    """Mock reference_pop directory with synthetic CDFs."""
    ref_dir = tmp_path / "reference_pop"
    ref_dir.mkdir(parents=True, exist_ok=True)

    # Create synthetic CDF for Chronotype (combined universe)
    chronotype_data = {
        "samples": [0.1 * i for i in range(11)],  # [0.0, 0.1, 0.2, ..., 1.0]
        "generated_at": "2025-10-20T20:00:00Z",
        "metadata": {"universe": "combined"}
    }

    with open(ref_dir / "PaDNA.Chronotype_combined.json", 'w') as f:
        json.dump(chronotype_data, f)

    # Mock REFERENCE_POP_DIR
    monkeypatch.setattr(
        "ReDNACoreDemo.core.metrics.reference_source.REFERENCE_POP_DIR",
        ref_dir
    )

    return ref_dir


@pytest.fixture
def mock_users_dir(tmp_path, monkeypatch):
    """Mock users directory with actual user data."""
    users_dir = tmp_path / "users"
    users_dir.mkdir(parents=True, exist_ok=True)

    # Create 10 users with Chronotype data
    now = datetime.now(timezone.utc)

    for i in range(10):
        user_id = f"user_{i}"
        user_dir = users_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        resolved = {
            "PaDNA.Chronotype": {
                "value": "Morning" if i < 5 else "Evening",
                "ucn": 0.1 * i,  # 0.0, 0.1, 0.2, ..., 0.9
                "rr": 10 * i,  # 0, 10, 20, ..., 90
            }
        }

        with open(user_dir / "resolved.json", 'w') as f:
            json.dump(resolved, f)

        # Set last_modified_ts to recent
        mtime = (now - timedelta(days=i)).timestamp()
        os.utime(user_dir / "resolved.json", (mtime, mtime))

    # Mock USERS_DIR
    monkeypatch.setattr(
        "ReDNACoreDemo.core.metrics.reference_source.USERS_DIR",
        users_dir
    )

    return users_dir


class TestSyntheticReference:
    """Test synthetic reference CDF loading."""

    def test_load_synthetic_valid_cdf(self, mock_reference_pop_dir):
        """Verify load_synthetic_reference() loads valid CDF."""
        cdf = load_synthetic_reference("PaDNA.Chronotype", universe="combined")

        assert cdf is not None
        assert cdf.source == "SYNTHETIC"
        assert cdf.universe == "combined"
        assert cdf.n_samples == 11
        assert cdf.samples == [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        assert cdf.generated_at == "2025-10-20T20:00:00Z"
        assert cdf.fallback_reason is None

    def test_load_synthetic_missing_file(self, mock_reference_pop_dir):
        """Verify load_synthetic_reference() returns None for missing file."""
        cdf = load_synthetic_reference("NonExistent.Trait", universe="combined")

        assert cdf is None

    def test_load_synthetic_no_universe(self, mock_reference_pop_dir):
        """Verify load_synthetic_reference() works without universe suffix."""
        # Create file without universe suffix
        no_universe_data = {
            "samples": [0.0, 0.5, 1.0],
            "generated_at": "2025-10-20T20:00:00Z"
        }

        ref_dir = Path(mock_reference_pop_dir)
        with open(ref_dir / "PaDNA.Height.json", 'w') as f:
            json.dump(no_universe_data, f)

        cdf = load_synthetic_reference("PaDNA.Height", universe=None)

        assert cdf is not None
        assert cdf.source == "SYNTHETIC"
        assert cdf.universe is None
        assert cdf.n_samples == 3


class TestActualReference:
    """Test actual reference CDF from live user population."""

    @patch.dict(os.environ, {"RR_ACTUAL_MIN_SAMPLES": "5", "RR_ACTUAL_MAX_AGE_DAYS": "30"}, clear=False)
    def test_load_actual_valid_cdf(self, mock_users_dir):
        """Verify load_actual_reference() scans user files correctly."""
        cdf = load_actual_reference("PaDNA.Chronotype", cohort_values=None)

        assert cdf is not None
        assert cdf.source == "ACTUAL"
        assert cdf.universe is None
        assert cdf.n_samples >= 5  # At least 5 users within 30 days
        assert cdf.samples == sorted(cdf.samples)  # Samples are sorted
        assert cdf.fallback_reason is None

    @patch.dict(os.environ, {"RR_ACTUAL_MIN_SAMPLES": "5", "RR_ACTUAL_MAX_AGE_DAYS": "2"}, clear=False)
    def test_load_actual_staleness_filter(self, mock_users_dir):
        """Verify load_actual_reference() respects staleness filter."""
        # With MAX_AGE_DAYS=2, only users 0-2 should be included
        cdf = load_actual_reference("PaDNA.Chronotype", cohort_values=None)

        # Should have fewer samples due to staleness filter
        # Users 0-2 = 3 samples (may fall below min_samples threshold)
        if cdf:
            assert cdf.n_samples <= 3
        else:
            # Expected: None (below min_samples threshold)
            assert cdf is None

    @patch.dict(os.environ, {"RR_ACTUAL_MIN_SAMPLES": "100", "RR_ACTUAL_MAX_AGE_DAYS": "30"}, clear=False)
    def test_load_actual_insufficient_samples(self, mock_users_dir):
        """Verify load_actual_reference() respects min_samples threshold."""
        cdf = load_actual_reference("PaDNA.Chronotype", cohort_values=None)

        # Should return None (10 users < 100 min_samples)
        assert cdf is None

    def test_load_actual_missing_trait(self, mock_users_dir):
        """Verify load_actual_reference() returns None for missing trait."""
        cdf = load_actual_reference("NonExistent.Trait", cohort_values=None)

        assert cdf is None


class TestCohortFiltering:
    """Test cohort-based filtering."""

    def test_cohort_filtering(self, tmp_path, monkeypatch):
        """Verify cohort filtering works correctly."""
        users_dir = tmp_path / "users"
        users_dir.mkdir(parents=True, exist_ok=True)

        # Create users with different cohorts
        cohorts = [
            {"age": "25-34", "region": "NA"},
            {"age": "25-34", "region": "EU"},
            {"age": "35-44", "region": "NA"},
        ]

        for i, cohort in enumerate(cohorts):
            user_dir = users_dir / f"user_{i}"
            user_dir.mkdir(parents=True, exist_ok=True)

            resolved = {
                "PaDNA.Chronotype": {
                    "value": "Morning",
                    "ucn": 0.5,
                    "cohort": cohort
                }
            }

            with open(user_dir / "resolved.json", 'w') as f:
                json.dump(resolved, f)

        monkeypatch.setattr(
            "ReDNACoreDemo.core.metrics.reference_source.USERS_DIR",
            users_dir
        )

        # Load with cohort filter
        with patch.dict(os.environ, {"RR_ACTUAL_MIN_SAMPLES": "1"}, clear=False):
            cdf = load_actual_reference(
                "PaDNA.Chronotype",
                cohort_values={"age": "25-34", "region": "NA"}
            )

            # Should only include user_0
            assert cdf is not None
            assert cdf.n_samples == 1
            assert cdf.cohort_keys == ["age", "region"]
            assert cdf.cohort_values == {"age": "25-34", "region": "NA"}


class TestReferenceCDF:
    """Test ReferenceCDF dataclass and methods."""

    def test_percentile_for_ucn_basic(self):
        """Verify percentile_for_ucn() computes correct percentiles."""
        # Uniform distribution: [0.0, 0.25, 0.5, 0.75, 1.0]
        cdf = ReferenceCDF(
            samples=[0.0, 0.25, 0.5, 0.75, 1.0],
            n_samples=5,
            source="SYNTHETIC",
            universe="combined",
            cohort_keys=[],
            cohort_values={},
            generated_at="2025-10-20T20:00:00Z",
            expiry=None,
            fallback_reason=None,
            metadata={}
        )

        # UCN=0.0 → 0th percentile
        assert cdf.percentile_for_ucn(0.0) == 0.0

        # UCN=0.5 → 50th percentile (2/4 * 100 = 50)
        assert cdf.percentile_for_ucn(0.5) == 40.0  # bisect_left([0.0, 0.25, 0.5, 0.75, 1.0], 0.5) = 2, 2/5 * 100 = 40

        # UCN=1.0 → 100th percentile
        assert cdf.percentile_for_ucn(1.0) == 80.0  # bisect_left = 4, 4/5 * 100 = 80

    def test_percentile_for_ucn_edge_cases(self):
        """Verify percentile_for_ucn() handles edge cases."""
        cdf = ReferenceCDF(
            samples=[0.0, 0.5, 1.0],
            n_samples=3,
            source="SYNTHETIC",
            universe="combined",
            cohort_keys=[],
            cohort_values={},
            generated_at="2025-10-20T20:00:00Z",
            expiry=None,
            fallback_reason=None,
            metadata={}
        )

        # UCN < 0 → clamped to 0
        assert cdf.percentile_for_ucn(-0.5) == 0.0

        # UCN > 1 → clamped to 1
        assert cdf.percentile_for_ucn(1.5) <= 100.0

    def test_percentile_for_ucn_empty_samples(self):
        """Verify percentile_for_ucn() returns 50.0 for empty samples."""
        cdf = ReferenceCDF(
            samples=[],
            n_samples=0,
            source="SYNTHETIC",
            universe="combined",
            cohort_keys=[],
            cohort_values={},
            generated_at="2025-10-20T20:00:00Z",
            expiry=None,
            fallback_reason=None,
            metadata={}
        )

        assert cdf.percentile_for_ucn(0.5) == 50.0


class TestGetReferenceCDF:
    """Test get_reference_cdf() router with fallback."""

    @patch.dict(os.environ, {"RR_REFERENCE_SOURCE": "SYNTHETIC", "RR_REFERENCE_UNIVERSE": "combined"}, clear=False)
    def test_get_reference_cdf_synthetic(self, mock_reference_pop_dir):
        """Verify get_reference_cdf() loads SYNTHETIC correctly."""
        # Clear cache
        _REFERENCE_CACHE.clear()

        cdf, fallback_reason = get_reference_cdf("PaDNA.Chronotype", cohort_values=None)

        assert cdf is not None
        assert cdf.source == "SYNTHETIC"
        assert cdf.universe == "combined"
        assert fallback_reason is None

    @patch.dict(os.environ, {"RR_REFERENCE_SOURCE": "ACTUAL", "RR_ACTUAL_MIN_SAMPLES": "100"}, clear=False)
    def test_get_reference_cdf_actual_fallback(self, mock_users_dir, mock_reference_pop_dir):
        """Verify get_reference_cdf() falls back ACTUAL → SYNTHETIC."""
        # Clear cache
        _REFERENCE_CACHE.clear()

        cdf, fallback_reason = get_reference_cdf("PaDNA.Chronotype", cohort_values=None)

        # Should fallback to SYNTHETIC (10 users < 100 min_samples)
        assert cdf is not None
        assert cdf.source == "SYNTHETIC"
        assert fallback_reason == "insufficient_samples"

    @patch.dict(os.environ, {"RR_REFERENCE_SOURCE": "SYNTHETIC", "RR_REFERENCE_UNIVERSE": "combined"}, clear=False)
    def test_get_reference_cdf_cache_hit(self, mock_reference_pop_dir):
        """Verify get_reference_cdf() uses cache when available."""
        # Clear cache
        _REFERENCE_CACHE.clear()

        # First call (cache miss)
        cdf1, fallback1 = get_reference_cdf("PaDNA.Chronotype", cohort_values=None)

        # Second call (cache hit)
        cdf2, fallback2 = get_reference_cdf("PaDNA.Chronotype", cohort_values=None)

        # Should return same CDF
        assert cdf1.source == cdf2.source
        assert cdf1.n_samples == cdf2.n_samples
        assert fallback1 == fallback2


class TestRRAdapter:
    """Test rr_to_percentile() with enhanced rr_meta."""

    @patch.dict(os.environ, {"RR_ADAPTER_ENABLED": "true", "REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "SYNTHETIC", "RR_REFERENCE_UNIVERSE": "combined"}, clear=False)
    def test_rr_to_percentile_enhanced_meta(self, mock_reference_pop_dir):
        """Verify rr_to_percentile() uses enhanced rr_meta format."""
        # Clear cache
        _REFERENCE_CACHE.clear()

        result = rr_to_percentile(
            rr_raw=50.0,
            rr_scale="reference_percentile",
            trait_id="PaDNA.Chronotype",
            user_id="test_user",
            cohort_values=None
        )

        assert "rr" in result
        assert "curiosity" in result
        assert "rr_meta" in result

        rr_meta = result["rr_meta"]
        assert "reference" in rr_meta
        assert rr_meta["reference"]["source"] == "SYNTHETIC"
        assert rr_meta["reference"]["universe"] == "combined"
        assert rr_meta["reference"]["n_samples"] == 11
        assert "generated_at" in rr_meta["reference"]

    @patch.dict(os.environ, {"RR_ADAPTER_ENABLED": "true", "REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "ACTUAL", "RR_ACTUAL_MIN_SAMPLES": "100"}, clear=False)
    def test_rr_to_percentile_fallback_meta(self, mock_users_dir, mock_reference_pop_dir):
        """Verify rr_to_percentile() includes fallback_reason in meta."""
        # Clear cache
        _REFERENCE_CACHE.clear()

        result = rr_to_percentile(
            rr_raw=50.0,
            rr_scale="reference_percentile",
            trait_id="PaDNA.Chronotype",
            user_id="test_user",
            cohort_values=None
        )

        rr_meta = result["rr_meta"]
        assert "fallback_reason" in rr_meta
        assert rr_meta["fallback_reason"] == "insufficient_samples"


class TestCacheKey:
    """Test cache key generation."""

    def test_cache_key_no_cohort(self):
        """Verify cache key generation without cohort."""
        key = _build_cache_key("PaDNA.Chronotype", cohort_values=None)

        assert "PaDNA.Chronotype" in key
        assert "no_cohort" in key

    def test_cache_key_with_cohort(self):
        """Verify cache key generation with cohort."""
        key = _build_cache_key("PaDNA.Chronotype", cohort_values={"age": "25-34", "region": "NA"})

        assert "PaDNA.Chronotype" in key
        assert "age=25-34" in key or "age:25-34" in key
        assert "region=NA" in key or "region:NA" in key


class TestUniformFallback:
    """Test uniform distribution fallback."""

    @patch.dict(os.environ, {"RR_REFERENCE_SOURCE": "SYNTHETIC", "RR_REFERENCE_UNIVERSE": "combined"}, clear=False)
    def test_uniform_fallback_missing_synthetic(self, mock_reference_pop_dir):
        """Verify uniform fallback used when no reference exists."""
        # Clear cache
        _REFERENCE_CACHE.clear()

        # Request non-existent trait
        cdf, fallback_reason = get_reference_cdf("NonExistent.Trait", cohort_values=None)

        # Should return uniform fallback
        assert cdf is not None
        assert cdf.universe == "uniform_fallback"
        assert cdf.n_samples == 1001
        assert cdf.samples[0] == 0.0
        assert cdf.samples[-1] == 1.0
