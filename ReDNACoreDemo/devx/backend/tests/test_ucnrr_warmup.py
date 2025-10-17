"""
Tests for UCNRR model warmup functionality.
"""

import pytest
from unittest.mock import Mock, patch, call
from ReDNACoreDemo.devx.backend import supervisor_ucnrr


class TestUCNRRWarmup:
    """Tests for UCNRR model warmup behavior."""

    def test_warmup_called_after_successful_ensure(self):
        """Test that warmup is called after UCNRR is successfully started."""
        # Mock all dependencies
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
                                    result = supervisor_ucnrr.ensure_ucnrr()

        # Verify warmup was called
        assert result["status"] in ["started", "already_running"]
        warmup_calls = [c for c in mock_post.call_args_list if "/api/generate" in str(c)]
        assert len(warmup_calls) > 0

    def test_warmup_uses_correct_timeout(self):
        """Test that warmup uses configured timeout values."""
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
                                    supervisor_ucnrr.ensure_ucnrr()

        # Check that warmup was called with timeout
        warmup_calls = [c for c in mock_post.call_args_list if "/api/generate" in str(c)]
        if warmup_calls:
            call_kwargs = warmup_calls[0][1]
            assert "timeout" in call_kwargs
            timeout = call_kwargs["timeout"]
            assert timeout.connect == supervisor_ucnrr.UCNRR_WARMUP_CONNECT_MS / 1000
            assert timeout.read == supervisor_ucnrr.UCNRR_WARMUP_READ_MS / 1000

    def test_warmup_skipped_when_disabled(self):
        """Test that warmup is skipped when UCNRR_WARMUP_ENABLED is false."""
        original_enabled = supervisor_ucnrr.UCNRR_WARMUP_ENABLED
        supervisor_ucnrr.UCNRR_WARMUP_ENABLED = False

        try:
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
                                        supervisor_ucnrr.ensure_ucnrr()

            # Verify warmup was NOT called
            warmup_calls = [c for c in mock_post.call_args_list if "/api/generate" in str(c)]
            assert len(warmup_calls) == 0

        finally:
            supervisor_ucnrr.UCNRR_WARMUP_ENABLED = original_enabled

    def test_warmup_failure_does_not_block_ensure(self):
        """Test that warmup failure doesn't prevent ensure from succeeding."""
        import httpx

        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        # Warmup will fail with timeout
        with patch("httpx.get", return_value=mock_health_response):
            with patch("httpx.post", side_effect=httpx.TimeoutException("Warmup timeout")):
                with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                    with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=None):
                            with patch.object(supervisor_ucnrr, "_start_ucnrr_process", return_value=12345):
                                with patch.object(supervisor_ucnrr, "stack_log"):
                                    result = supervisor_ucnrr.ensure_ucnrr()

        # Ensure should still succeed despite warmup failure
        assert result["status"] in ["started", "already_running"]

    def test_warmup_sends_correct_payload(self):
        """Test that warmup sends correct request to Ollama API."""
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
                                    supervisor_ucnrr.ensure_ucnrr()

        # Check warmup payload
        warmup_calls = [c for c in mock_post.call_args_list if "/api/generate" in str(c)]
        if warmup_calls:
            call_kwargs = warmup_calls[0][1]
            assert "json" in call_kwargs
            payload = call_kwargs["json"]
            assert "model" in payload
            assert "prompt" in payload
            assert payload["prompt"] == "ok"
            assert payload.get("stream") is False

    def test_warmup_not_called_when_llm_not_configured(self):
        """Test that warmup is not called if LLM is not configured."""
        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "llm_configured": False,  # LLM not configured
        }

        with patch("httpx.get", return_value=mock_health_response):
            with patch("httpx.post") as mock_post:
                with patch.object(supervisor_ucnrr, "_validate_ollama", return_value=(True, None)):
                    with patch.object(supervisor_ucnrr, "_validate_port_available", return_value=(True, None)):
                        with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=None):
                            with patch.object(supervisor_ucnrr, "_start_ucnrr_process", return_value=12345):
                                with patch.object(supervisor_ucnrr, "stack_log"):
                                    supervisor_ucnrr.ensure_ucnrr()

        # Verify warmup was NOT called when LLM not configured
        warmup_calls = [c for c in mock_post.call_args_list if "/api/generate" in str(c)]
        assert len(warmup_calls) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
