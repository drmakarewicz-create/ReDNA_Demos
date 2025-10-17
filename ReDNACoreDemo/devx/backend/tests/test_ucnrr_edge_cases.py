"""
Edge case tests for UCNRR warmup and cache under stress conditions.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from ReDNACoreDemo.devx.backend import supervisor_ucnrr
from UCN_RR_Demo import ucnrr_app


class TestUCNRREdgeCases:
    """Edge case tests for warmup and cache under unusual conditions."""

    def setup_method(self):
        """Reset cache state before each test."""
        ucnrr_app._last_selftest_ok_ts = 0.0
        ucnrr_app._last_selftest_ok_meta = {}

    def test_concurrent_selftest_calls(self):
        """Test that concurrent selftest calls don't corrupt cache."""
        mock_result = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.85,
        }]

        results = []
        errors = []

        def run_selftest():
            try:
                with patch.object(ucnrr_app, "ucn_score", return_value=mock_result):
                    with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                        result = ucnrr_app.ucnrr_selftest()
                        results.append(result)
            except Exception as e:
                errors.append(e)

        # Run 10 concurrent selftests
        threads = [threading.Thread(target=run_selftest) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0
        # All should succeed
        assert all(r["ok"] for r in results)
        # Cache should be populated
        assert ucnrr_app._last_selftest_ok_ts > 0

    def test_concurrent_health_checks_during_cache_refresh(self):
        """Test that concurrent health checks during refresh don't cause issues."""
        # Set cache near expiry to trigger refresh
        ucnrr_app._last_selftest_ok_ts = time.time() - 110  # 61% of 180s
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        results = []
        errors = []

        def check_health():
            try:
                with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
                    with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                        with patch.object(ucnrr_app, "_bg_refresh_selftest"):
                            result = ucnrr_app.api_health()
                            results.append(result)
            except Exception as e:
                errors.append(e)

        # Run 20 concurrent health checks
        threads = [threading.Thread(target=check_health) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0
        # All should return cached result
        assert all(r["selftest_cached"] is True for r in results)

    def test_warmup_timeout_recovery(self):
        """Test that warmup timeout doesn't block subsequent operations."""
        import httpx

        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        # First ensure with warmup timeout
        with patch("httpx.get", return_value=mock_health_response):
            with patch("httpx.post", side_effect=httpx.TimeoutException("Warmup timeout")):
                with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                    with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=None):
                            with patch.object(supervisor_ucnrr, "_start_ucnrr_process", return_value=12345):
                                with patch.object(supervisor_ucnrr, "stack_log"):
                                    result1 = supervisor_ucnrr.ensure_ucnrr()

        assert result1["status"] in ["started", "already_running"]

        # Second ensure should work normally
        mock_warmup_response = Mock()
        mock_warmup_response.status_code = 200

        with patch("httpx.get", return_value=mock_health_response):
            with patch("httpx.post", return_value=mock_warmup_response):
                with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                    with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=12345):
                            with patch.object(supervisor_ucnrr, "_pid_alive", return_value=True):
                                with patch.object(supervisor_ucnrr, "stack_log"):
                                    result2 = supervisor_ucnrr.ensure_ucnrr()

        assert result2["status"] in ["started", "already_running"]

    def test_cache_during_clock_skew(self):
        """Test that cache handles system clock adjustments gracefully."""
        # Populate cache
        ucnrr_app._last_selftest_ok_ts = time.time()
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        # Simulate clock skew (time goes backwards)
        with patch("time.time", return_value=time.time() - 100):
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
                with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                    with patch.object(ucnrr_app, "_bg_refresh_selftest"):
                        result = ucnrr_app.api_health()

        # Should handle gracefully (treat as stale or fresh depending on implementation)
        assert "selftest_cached" in result

    def test_very_slow_selftest_doesnt_block_health(self):
        """Test that very slow selftest doesn't block health endpoint."""
        # Empty cache
        ucnrr_app._last_selftest_ok_ts = 0.0

        # Health check should return quickly even with no cache
        start = time.time()
        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                with patch.object(ucnrr_app, "_bg_refresh_selftest"):
                    result = ucnrr_app.api_health()
        elapsed = time.time() - start

        # Should return quickly without blocking
        assert elapsed < 0.1  # 100ms max
        assert result["selftest_cached"] is False

    def test_rapid_ensure_calls_dont_spam_warmup(self):
        """Test that rapid ensure calls don't spam warmup requests."""
        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        mock_warmup_response = Mock()
        mock_warmup_response.status_code = 200

        warmup_call_count = 0

        def count_warmup(*args, **kwargs):
            nonlocal warmup_call_count
            if "/api/generate" in str(args):
                warmup_call_count += 1
            return mock_warmup_response

        # Call ensure 5 times rapidly
        for _ in range(5):
            with patch("httpx.get", return_value=mock_health_response):
                with patch("httpx.post", side_effect=count_warmup):
                    with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                            with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=12345):  # Already running
                                with patch.object(supervisor_ucnrr, "_pid_alive", return_value=True):
                                    with patch.object(supervisor_ucnrr, "stack_log"):
                                        supervisor_ucnrr.ensure_ucnrr()

        # Warmup should only be called once (or not at all if already running)
        # Since UCNRR is "already running", warmup may not be called
        assert warmup_call_count <= 1

    def test_cache_with_failed_then_successful_selftest(self):
        """Test cache behavior when selftest fails then succeeds."""
        # First selftest fails
        mock_result_fail = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.50,  # Out of range
        }]

        with patch.object(ucnrr_app, "ucn_score", return_value=mock_result_fail):
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                result1 = ucnrr_app.ucnrr_selftest()

        assert result1["ok"] is False
        assert ucnrr_app._last_selftest_ok_ts == 0.0  # Cache not updated

        # Second selftest succeeds
        mock_result_success = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.85,
        }]

        with patch.object(ucnrr_app, "ucn_score", return_value=mock_result_success):
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                result2 = ucnrr_app.ucnrr_selftest()

        assert result2["ok"] is True
        assert ucnrr_app._last_selftest_ok_ts > 0  # Cache now updated
        assert ucnrr_app._last_selftest_ok_meta["ucn"] == 0.85

    def test_warmup_with_empty_model_string(self):
        """Test that warmup handles empty model string gracefully."""
        import os

        original_model = os.getenv("UCNRR_LLM_MODEL")

        try:
            os.environ["UCNRR_LLM_MODEL"] = ""

            mock_health_response = Mock()
            mock_health_response.status_code = 200
            mock_health_response.json.return_value = {
                "status": "healthy",
                "llm_configured": True,
            }

            with patch("httpx.get", return_value=mock_health_response):
                with patch("httpx.post") as mock_post:
                    with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                            with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=None):
                                with patch.object(supervisor_ucnrr, "_start_ucnrr_process", return_value=12345):
                                    with patch.object(supervisor_ucnrr, "stack_log"):
                                        result = supervisor_ucnrr.ensure_ucnrr(config={"model": ""})

            # Warmup should be skipped (empty model)
            warmup_calls = [c for c in mock_post.call_args_list if "/api/generate" in str(c)]
            assert len(warmup_calls) == 0
            assert result["status"] in ["started", "already_running"]

        finally:
            if original_model:
                os.environ["UCNRR_LLM_MODEL"] = original_model
            elif "UCNRR_LLM_MODEL" in os.environ:
                del os.environ["UCNRR_LLM_MODEL"]

    def test_cache_age_calculation_accuracy(self):
        """Test that cache age is calculated accurately."""
        # Set cache to exactly 100 seconds ago
        cache_ts = time.time() - 100
        ucnrr_app._last_selftest_ok_ts = cache_ts
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                with patch.object(ucnrr_app, "_bg_refresh_selftest"):
                    result = ucnrr_app.api_health()

        # Age should be around 100 seconds (within 1 second tolerance)
        assert 99 <= result["selftest_cache_age_sec"] <= 101


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
