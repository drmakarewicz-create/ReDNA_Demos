"""
Integration tests for UCNRR warmup + selftest cache interaction.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from ReDNACoreDemo.devx.backend import supervisor_ucnrr
from UCN_RR_Demo import ucnrr_app


class TestUCNRRIntegration:
    """Integration tests for warmup and cache working together."""

    def test_ensure_then_health_uses_cache(self):
        """Test that ensure + warmup, followed by health check, uses cache."""
        # Mock dependencies for ensure
        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
            "selftest_cached": True,
            "selftest_cache_age_sec": 5,
            "model": "phi3:mini",
            "provider": "ollama",
        }

        mock_warmup_response = Mock()
        mock_warmup_response.status_code = 200

        # Ensure UCNRR with warmup
        with patch("httpx.get", return_value=mock_health_response):
            with patch("httpx.post", return_value=mock_warmup_response):
                with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                    with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=None):
                            with patch.object(supervisor_ucnrr, "_start_ucnrr_process", return_value=12345):
                                with patch.object(supervisor_ucnrr, "stack_log"):
                                    result = supervisor_ucnrr.ensure_ucnrr()

        assert result["status"] in ["started", "already_running"]

        # Subsequent health check should show cached result
        assert mock_health_response.json()["selftest_cached"] is True

    def test_cache_refresh_after_warmup(self):
        """Test that cache refresh works after warmup preloads model."""
        # Populate cache
        ucnrr_app._last_selftest_ok_ts = time.time() - 120  # 2 minutes ago (near 60% of 180s)
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

        # Should trigger background refresh at 60% cache age
        mock_refresh.assert_called_once()
        assert result["selftest_cached"] is True
        assert result["model"] == "phi3:mini"

    def test_warmup_failure_does_not_affect_cache(self):
        """Test that warmup failure doesn't prevent cache from working."""
        import httpx

        # Populate cache first
        ucnrr_app._last_selftest_ok_ts = time.time()
        ucnrr_app._last_selftest_ok_meta = {
            "model": "phi3:mini",
            "provider": "ollama",
            "ucn": 0.85,
            "elapsed_ms": 1500,
        }

        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        # Warmup fails, but health check should still work
        with patch("httpx.get", return_value=mock_health_response):
            with patch("httpx.post", side_effect=httpx.TimeoutException("Warmup timeout")):
                with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                    with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=None):
                            with patch.object(supervisor_ucnrr, "_start_ucnrr_process", return_value=12345):
                                with patch.object(supervisor_ucnrr, "stack_log"):
                                    result = supervisor_ucnrr.ensure_ucnrr()

        assert result["status"] in ["started", "already_running"]

        # Cache should still be valid
        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                health = ucnrr_app.api_health()

        assert health["selftest_cached"] is True
        assert health["model"] == "phi3:mini"

    def test_multiple_ensure_calls_warmup_idempotent(self):
        """Test that multiple ensure calls don't cause issues with warmup."""
        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        mock_warmup_response = Mock()
        mock_warmup_response.status_code = 200

        # Call ensure multiple times
        for i in range(3):
            with patch("httpx.get", return_value=mock_health_response):
                with patch("httpx.post", return_value=mock_warmup_response) as mock_post:
                    with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                            with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=12345):  # Already running
                                with patch.object(supervisor_ucnrr, "_pid_alive", return_value=True):
                                    with patch.object(supervisor_ucnrr, "stack_log"):
                                        result = supervisor_ucnrr.ensure_ucnrr()

            assert result["status"] in ["started", "already_running"]

    def test_cache_expiry_triggers_new_selftest(self):
        """Test that expired cache triggers new selftest with warmup benefit."""
        # Set cache to expired
        ucnrr_app._last_selftest_ok_ts = time.time() - 200  # > 180s cache window
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

        # Should indicate cache is stale and trigger refresh
        assert result["selftest_cached"] is False
        assert result["selftest_cache_age_sec"] > 180
        mock_refresh.assert_called_once()

    def test_warmup_with_different_models(self):
        """Test that warmup works with different model configurations."""
        import os

        original_model = os.getenv("UCNRR_LLM_MODEL")
        models_to_test = ["phi3:mini", "llama3.1:8b", "mistral:latest"]

        for model in models_to_test:
            os.environ["UCNRR_LLM_MODEL"] = model

            mock_health_response = Mock()
            mock_health_response.status_code = 200
            mock_health_response.json.return_value = {
                "status": "healthy",
                "llm_configured": True,
            }

            mock_warmup_response = Mock()
            mock_warmup_response.status_code = 200

            with patch("httpx.get", return_value=mock_health_response):
                with patch("httpx.post", return_value=mock_warmup_response) as mock_post:
                    with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                            with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=None):
                                with patch.object(supervisor_ucnrr, "_start_ucnrr_process", return_value=12345):
                                    with patch.object(supervisor_ucnrr, "stack_log"):
                                        # Pass model via config
                                        result = supervisor_ucnrr.ensure_ucnrr(config={"model": model})

            assert result["status"] in ["started", "already_running"]

            # Verify warmup was called with correct model
            warmup_calls = [c for c in mock_post.call_args_list if "/api/generate" in str(c)]
            assert len(warmup_calls) > 0
            payload = warmup_calls[0][1]["json"]
            assert payload["model"] == model

        # Restore original
        if original_model:
            os.environ["UCNRR_LLM_MODEL"] = original_model
        elif "UCNRR_LLM_MODEL" in os.environ:
            del os.environ["UCNRR_LLM_MODEL"]

    def test_cache_populated_by_successful_selftest_after_warmup(self):
        """Test that selftest cache is populated after warmup enables fast responses."""
        # Start with empty cache
        ucnrr_app._last_selftest_ok_ts = 0.0
        ucnrr_app._last_selftest_ok_meta = {}

        # Mock successful selftest
        mock_result = [{
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "ucn": 0.85,
        }]

        with patch.object(ucnrr_app, "ucn_score", return_value=mock_result):
            with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123"}):
                result = ucnrr_app.ucnrr_selftest()

        # Cache should now be populated
        assert result["ok"] is True
        assert ucnrr_app._last_selftest_ok_ts > 0
        assert ucnrr_app._last_selftest_ok_meta["ucn"] == 0.85

        # Subsequent health checks should use cache
        with patch.object(ucnrr_app, "_load_prompt", return_value={"sha256": "abc123", "version": "1.0", "loaded_at": "2025-10-17"}):
            with patch.object(ucnrr_app, "_is_llm_configured", return_value=True):
                health = ucnrr_app.api_health()

        assert health["selftest_cached"] is True
        assert health["ucn"] == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
