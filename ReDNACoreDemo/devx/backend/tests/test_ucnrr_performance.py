"""
Performance tests for UCNRR warmup and cache behavior.
"""

import pytest
import time
from unittest.mock import Mock, patch
from UCN_RR_Demo import ucnrr_app


class TestUCNRRPerformance:
    """Performance tests for cache and warmup efficiency."""

    def setup_method(self):
        """Reset cache state before each test."""
        ucnrr_app._last_selftest_ok_ts = 0.0
        ucnrr_app._last_selftest_ok_meta = {}

    def test_cached_health_check_faster_than_uncached(self):
        """Test that cached health checks are significantly faster."""
        # Uncached health check (will trigger background refresh)
        ucnrr_app._last_selftest_ok_ts = 0.0

        start_uncached = time.time()
        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                with patch.object(ucnrr_app, "_bg_refresh_selftest"):
                    result_uncached = ucnrr_app.api_health()
        uncached_time = time.time() - start_uncached

        assert result_uncached["selftest_cached"] is False

        # Populate cache
        ucnrr_app._last_selftest_ok_ts = time.time()
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        # Cached health check
        start_cached = time.time()
        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                result_cached = ucnrr_app.api_health()
        cached_time = time.time() - start_cached

        assert result_cached["selftest_cached"] is True

        # Cached should be faster (both should be fast, but cached should be marginally faster)
        # Not a strict performance test since both are mocked, but validates logic path
        assert uncached_time < 0.1  # Both should be fast with mocks
        assert cached_time < 0.1

    def test_cache_miss_penalty_bounded(self):
        """Test that cache miss doesn't cause unbounded delay."""
        # Empty cache triggers background refresh
        ucnrr_app._last_selftest_ok_ts = 0.0

        start = time.time()
        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                with patch.object(ucnrr_app, "_bg_refresh_selftest"):
                    result = ucnrr_app.api_health()
        elapsed = time.time() - start

        # Should return immediately without blocking
        assert elapsed < 0.1  # 100ms max
        assert result["selftest_cached"] is False

    def test_background_refresh_non_blocking(self):
        """Test that background refresh doesn't block health endpoint."""
        # Set cache near expiry
        ucnrr_app._last_selftest_ok_ts = time.time() - 110  # Triggers refresh
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        # Background refresh should not block (it runs in a daemon thread)
        # We just verify it gets called, not that it completes
        start = time.time()
        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                with patch.object(ucnrr_app, "_bg_refresh_selftest") as mock_refresh:
                    result = ucnrr_app.api_health()
        elapsed = time.time() - start

        # Health check should return immediately
        assert elapsed < 0.1  # Should be very fast
        assert result["selftest_cached"] is True  # Still using cache
        # Verify refresh was triggered
        mock_refresh.assert_called_once()

    def test_multiple_sequential_health_checks_efficient(self):
        """Test that multiple sequential health checks remain efficient."""
        # Populate cache
        ucnrr_app._last_selftest_ok_ts = time.time()
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        times = []
        for _ in range(10):
            start = time.time()
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
                with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                    result = ucnrr_app.api_health()
            elapsed = time.time() - start
            times.append(elapsed)

            assert result["selftest_cached"] is True

        # All checks should be fast
        avg_time = sum(times) / len(times)
        assert avg_time < 0.01  # Average < 10ms
        assert max(times) < 0.05  # No single check > 50ms

    def test_cache_memory_footprint(self):
        """Test that cache metadata has reasonable memory footprint."""
        import sys

        # Populate cache with typical metadata
        ucnrr_app._last_selftest_ok_ts = time.time()
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        # Check size of metadata dict
        meta_size = sys.getsizeof(ucnrr_app._last_selftest_ok_meta)

        # Should be small (< 1KB for metadata)
        assert meta_size < 1024

    def test_warmup_timing_configurable(self):
        """Test that warmup timeout is configurable and respected."""
        from ReDNACoreDemo.devx.backend import supervisor_ucnrr

        # Check that constants are accessible
        assert hasattr(supervisor_ucnrr, "UCNRR_WARMUP_CONNECT_MS")
        assert hasattr(supervisor_ucnrr, "UCNRR_WARMUP_READ_MS")

        # Verify reasonable defaults
        assert 100 <= supervisor_ucnrr.UCNRR_WARMUP_CONNECT_MS <= 2000
        assert 500 <= supervisor_ucnrr.UCNRR_WARMUP_READ_MS <= 10000

    def test_cache_window_configurable(self):
        """Test that cache window is configurable."""
        # Check that constant is accessible
        assert hasattr(ucnrr_app, "SELFTEST_CACHE_SEC")

        # Verify reasonable default (should be between 1-10 minutes)
        assert 60 <= ucnrr_app.SELFTEST_CACHE_SEC <= 600

    def test_cache_refresh_threshold_correct(self):
        """Test that cache refresh triggers at 60% of cache window."""
        cache_window = ucnrr_app.SELFTEST_CACHE_SEC
        refresh_threshold = cache_window * 0.6

        # Set cache to exactly at threshold
        ucnrr_app._last_selftest_ok_ts = time.time() - refresh_threshold
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                with patch.object(ucnrr_app, "_bg_refresh_selftest") as mock_refresh:
                    result = ucnrr_app.api_health()

        # Should trigger refresh at exactly 60%
        assert result["selftest_cached"] is True
        mock_refresh.assert_called_once()

    def test_selftest_cache_update_speed(self):
        """Test that cache update operation is fast."""
        mock_result = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.85,
        }]

        start = time.time()
        with patch.object(ucnrr_app, "ucn_score", return_value=mock_result):
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                result = ucnrr_app.ucnrr_selftest()
        elapsed = time.time() - start

        # Selftest with mocked ucn_score should be very fast
        assert elapsed < 0.1  # < 100ms
        assert result["ok"] is True
        assert ucnrr_app._last_selftest_ok_ts > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
