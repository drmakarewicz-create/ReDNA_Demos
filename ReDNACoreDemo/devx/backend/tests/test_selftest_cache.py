"""
Tests for UCNRR selftest cache behavior.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from UCN_RR_Demo import ucnrr_app


class TestSelftestCache:
    """Tests for UCNRR selftest caching mechanism."""

    def setup_method(self):
        """Reset cache state before each test."""
        ucnrr_app._last_selftest_ok_ts = 0.0
        ucnrr_app._last_selftest_ok_meta = {}

    def test_cache_populates_on_successful_selftest(self):
        """Test that cache is populated when selftest succeeds."""
        # Mock the ucn_score function to return valid result
        mock_result = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.85,
        }]

        with patch.object(ucnrr_app, "ucn_score", return_value=mock_result):
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                result = ucnrr_app.ucnrr_selftest()

        assert result["ok"] is True
        assert ucnrr_app._last_selftest_ok_ts > 0
        assert "model" in ucnrr_app._last_selftest_ok_meta
        assert "provider" in ucnrr_app._last_selftest_ok_meta
        assert "ucn" in ucnrr_app._last_selftest_ok_meta
        assert ucnrr_app._last_selftest_ok_meta["ucn"] == 0.85

    def test_cache_not_populated_on_failed_selftest(self):
        """Test that cache is NOT populated when selftest fails."""
        # Mock the ucn_score function to return out-of-range result
        mock_result = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.50,  # Outside expected range
        }]

        initial_ts = ucnrr_app._last_selftest_ok_ts

        with patch.object(ucnrr_app, "ucn_score", return_value=mock_result):
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                result = ucnrr_app.ucnrr_selftest()

        assert result["ok"] is False
        assert ucnrr_app._last_selftest_ok_ts == initial_ts  # Not updated

    def test_health_returns_cached_result_when_fresh(self):
        """Test that api_health returns cached selftest when cache is fresh."""
        # Populate cache
        ucnrr_app._last_selftest_ok_ts = time.time()
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                result = ucnrr_app.api_health()

        assert result["selftest_cached"] is True
        assert result["selftest_cache_age_sec"] < 5  # Should be very recent
        assert result["model"] == "phi3:mini"
        assert result["provider"] == "ollama"
        assert result["ucn"] == 0.85

    def test_health_indicates_stale_when_cache_expired(self):
        """Test that api_health indicates stale cache when expired."""
        # Populate cache with old timestamp
        ucnrr_app._last_selftest_ok_ts = time.time() - 200  # 200 seconds ago (cache is 180s)

        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                with patch.object(ucnrr_app, "_bg_refresh_selftest"):  # Don't actually refresh
                    result = ucnrr_app.api_health()

        assert result["selftest_cached"] is False
        assert result["selftest_cache_age_sec"] > 180

    def test_health_triggers_background_refresh_near_expiry(self):
        """Test that api_health triggers background refresh at 60% cache age."""
        # Populate cache at 65% of cache window (117 seconds for 180s window)
        ucnrr_app._last_selftest_ok_ts = time.time() - 117
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

        # Should trigger background refresh
        mock_refresh.assert_called_once()
        assert result["selftest_cached"] is True

    def test_cache_thread_safety(self):
        """Test that cache updates are thread-safe."""
        import threading

        # Simulate concurrent selftest calls
        mock_result = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.85,
        }]

        results = []

        def run_selftest():
            with patch.object(ucnrr_app, "ucn_score", return_value=mock_result):
                with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                    result = ucnrr_app.ucnrr_selftest()
                    results.append(result)

        threads = [threading.Thread(target=run_selftest) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert all(r["ok"] for r in results)
        # Cache should be populated
        assert ucnrr_app._last_selftest_ok_ts > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
