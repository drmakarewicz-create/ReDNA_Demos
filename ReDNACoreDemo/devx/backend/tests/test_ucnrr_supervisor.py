"""
Tests for UCNRR supervisor module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from ReDNACoreDemo.devx.backend import supervisor_ucnrr


class TestUCNRRSupervisor:
    """Tests for UCNRR supervisor functions."""

    def test_check_ucnrr_healthy(self):
        """Test check_ucnrr when service is healthy."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        with patch("httpx.get", return_value=mock_response):
            result = supervisor_ucnrr.check_ucnrr()

        assert result["alive"] is True
        assert result["llm_configured"] is True
        assert result["reason"] == "ok"

    def test_check_ucnrr_llm_not_configured(self):
        """Test check_ucnrr when LLM is not configured."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "llm_configured": False,
        }

        with patch("httpx.get", return_value=mock_response):
            result = supervisor_ucnrr.check_ucnrr()

        assert result["alive"] is True
        assert result["llm_configured"] is False
        assert result["reason"] == "bad_llm"

    def test_check_ucnrr_connection_refused(self):
        """Test check_ucnrr when connection is refused."""
        import httpx

        with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
            result = supervisor_ucnrr.check_ucnrr()

        assert result["alive"] is False
        assert result["llm_configured"] is False
        assert result["reason"] == "conn_refused"

    def test_check_ucnrr_timeout(self):
        """Test check_ucnrr when request times out."""
        import httpx

        with patch("httpx.get", side_effect=httpx.TimeoutException("Timeout")):
            result = supervisor_ucnrr.check_ucnrr()

        assert result["alive"] is False
        assert result["llm_configured"] is False
        assert result["reason"] == "timeout"

    def test_validate_ollama_success(self):
        """Test _validate_ollama when Ollama is reachable."""
        mock_response = Mock()
        mock_response.status_code = 200

        with patch("httpx.get", return_value=mock_response):
            ok, reason = supervisor_ucnrr._validate_ollama("http://127.0.0.1:11434")

        assert ok is True
        assert reason is None

    def test_validate_ollama_conn_refused(self):
        """Test _validate_ollama when connection is refused."""
        import httpx

        with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
            ok, reason = supervisor_ucnrr._validate_ollama("http://127.0.0.1:11434")

        assert ok is False
        assert reason == "ollama_conn_refused"

    def test_validate_ollama_timeout(self):
        """Test _validate_ollama when request times out."""
        import httpx

        with patch("httpx.get", side_effect=httpx.TimeoutException("Timeout")):
            ok, reason = supervisor_ucnrr._validate_ollama("http://127.0.0.1:11434")

        assert ok is False
        assert reason == "ollama_timeout"

    def test_check_restart_cap_not_exceeded(self):
        """Test _check_restart_cap when cap is not exceeded."""
        supervisor_ucnrr._UCNRR_STATE.restart_timestamps = []
        assert supervisor_ucnrr._check_restart_cap() is False

    def test_check_restart_cap_exceeded(self):
        """Test _check_restart_cap when cap is exceeded."""
        import time
        now = time.time()
        # Simulate 3 restarts within the window
        supervisor_ucnrr._UCNRR_STATE.restart_timestamps = [
            now - 300,  # 5 minutes ago
            now - 200,  # 3.3 minutes ago
            now - 100,  # 1.6 minutes ago
        ]
        assert supervisor_ucnrr._check_restart_cap() is True

    def test_get_backoff_delay(self):
        """Test _get_backoff_delay returns correct delays."""
        supervisor_ucnrr._UCNRR_STATE.backoff_level = 0
        assert supervisor_ucnrr._get_backoff_delay() == 2

        supervisor_ucnrr._UCNRR_STATE.backoff_level = 1
        assert supervisor_ucnrr._get_backoff_delay() == 5

        supervisor_ucnrr._UCNRR_STATE.backoff_level = 2
        assert supervisor_ucnrr._get_backoff_delay() == 10

        supervisor_ucnrr._UCNRR_STATE.backoff_level = 3
        assert supervisor_ucnrr._get_backoff_delay() == 30

        # Test cap
        supervisor_ucnrr._UCNRR_STATE.backoff_level = 10
        assert supervisor_ucnrr._get_backoff_delay() == 30

    def test_ensure_ucnrr_already_running(self):
        """Test ensure_ucnrr when UCNRR is already running."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        with patch("httpx.get", return_value=mock_response):
            with patch.object(supervisor_ucnrr, "_read_pid_file", return_value=12345):
                with patch.object(supervisor_ucnrr, "_pid_alive", return_value=True):
                    result = supervisor_ucnrr.ensure_ucnrr()

        assert result["status"] == "already_running"
        assert result["pid"] == 12345

    def test_get_ucnrr_status(self):
        """Test get_ucnrr_status returns expected structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "llm_configured": True,
        }

        supervisor_ucnrr._UCNRR_STATE.pid = 12345
        supervisor_ucnrr._UCNRR_STATE.restart_timestamps = []
        supervisor_ucnrr._UCNRR_STATE.restart_capped = False

        with patch("httpx.get", return_value=mock_response):
            status = supervisor_ucnrr.get_ucnrr_status()

        assert "alive" in status
        assert "llm_configured" in status
        assert "reason" in status
        assert "restarts_last_10m" in status
        assert "restart_capped" in status
        assert "backoff_sec_remaining" in status
        assert status["pid"] == 12345


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
