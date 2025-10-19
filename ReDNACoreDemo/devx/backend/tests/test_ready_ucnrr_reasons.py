"""
Tests for UCNRR reason codes in stack ready endpoint.
"""

import pytest
from unittest.mock import Mock, patch
from ReDNACoreDemo.devx.backend.stack_api import _compute_readiness


class TestReadyUCNRRReasons:
    """Tests for UCNRR reason codes in readiness computation."""

    def test_ucnrr_unreachable(self):
        """Test that ucnrr_unreachable is added when UCNRR is not reachable."""
        inputs = {
            "health": {
                "status": "healthy",
                "rr_mode": "degraded",
                "features": {"ucnrr_enabled": True},
            },
            "metrics": {
                "uptime_seconds": 60,
                "rolling_window": {
                    "window_seconds": 300,
                    "requests_window_5m": 10,
                    "errors_5xx_window_5m": 0,
                    "latency_p95_ms_window_5m": 100,
                    "warming": False,
                },
                "counters": {
                    "http.requests.total": 100,
                    "http.requests.errors": 0,
                },
                "timers": {
                    "http.latency_ms": {"p95": 100},
                },
            },
        }

        mock_ucnrr_status = {
            "alive": False,
            "llm_configured": False,
            "reason": "conn_refused",
            "restarts_last_10m": 0,
            "restart_capped": False,
            "backoff_sec_remaining": 0,
        }

        with patch("ReDNACoreDemo.devx.backend.supervisor_ucnrr.get_ucnrr_status", return_value=mock_ucnrr_status):
            analysis, _ = _compute_readiness(inputs)

        assert "ucnrr_unreachable" in analysis["fail_conditions"]
        assert any("unreachable" in reason.lower() for reason in analysis["reasons"])

    def test_ucnrr_llm_disabled(self):
        """Test that ucnrr_llm_disabled is added when LLM is not configured."""
        inputs = {
            "health": {
                "status": "healthy",
                "rr_mode": "degraded",
                "features": {"ucnrr_enabled": True},
            },
            "metrics": {
                "uptime_seconds": 60,
                "rolling_window": {
                    "window_seconds": 300,
                    "requests_window_5m": 10,
                    "errors_5xx_window_5m": 0,
                    "latency_p95_ms_window_5m": 100,
                    "warming": False,
                },
                "counters": {
                    "http.requests.total": 100,
                    "http.requests.errors": 0,
                },
                "timers": {
                    "http.latency_ms": {"p95": 100},
                },
            },
        }

        mock_ucnrr_status = {
            "alive": True,
            "llm_configured": False,
            "reason": "bad_llm",
            "restarts_last_10m": 0,
            "restart_capped": False,
            "backoff_sec_remaining": 0,
        }

        with patch("ReDNACoreDemo.devx.backend.supervisor_ucnrr.get_ucnrr_status", return_value=mock_ucnrr_status):
            analysis, _ = _compute_readiness(inputs)

        assert "ucnrr_llm_disabled" in analysis["fail_conditions"]
        assert any("llm" in reason.lower() for reason in analysis["reasons"])

    def test_ucnrr_restart_capped(self):
        """Test that ucnrr_restart_capped is added when restart cap is exceeded."""
        inputs = {
            "health": {
                "status": "healthy",
                "rr_mode": "degraded",
                "features": {"ucnrr_enabled": True},
            },
            "metrics": {
                "uptime_seconds": 60,
                "rolling_window": {
                    "window_seconds": 300,
                    "requests_window_5m": 10,
                    "errors_5xx_window_5m": 0,
                    "latency_p95_ms_window_5m": 100,
                    "warming": False,
                },
                "counters": {
                    "http.requests.total": 100,
                    "http.requests.errors": 0,
                },
                "timers": {
                    "http.latency_ms": {"p95": 100},
                },
            },
        }

        mock_ucnrr_status = {
            "alive": False,
            "llm_configured": False,
            "reason": "conn_refused",
            "restarts_last_10m": 3,
            "restart_capped": True,
            "backoff_sec_remaining": 0,
        }

        with patch("ReDNACoreDemo.devx.backend.supervisor_ucnrr.get_ucnrr_status", return_value=mock_ucnrr_status):
            analysis, _ = _compute_readiness(inputs)

        assert "ucnrr_restart_capped" in analysis["fail_conditions"]
        assert any("restart" in reason.lower() and "rate limit" in reason.lower() for reason in analysis["reasons"])

    def test_ucnrr_backoff_active(self):
        """Test that ucnrr_backoff_active is added during backoff."""
        inputs = {
            "health": {
                "status": "healthy",
                "rr_mode": "degraded",
                "features": {"ucnrr_enabled": True},
            },
            "metrics": {
                "uptime_seconds": 60,
                "rolling_window": {
                    "window_seconds": 300,
                    "requests_window_5m": 10,
                    "errors_5xx_window_5m": 0,
                    "latency_p95_ms_window_5m": 100,
                    "warming": False,
                },
                "counters": {
                    "http.requests.total": 100,
                    "http.requests.errors": 0,
                },
                "timers": {
                    "http.latency_ms": {"p95": 100},
                },
            },
        }

        mock_ucnrr_status = {
            "alive": False,
            "llm_configured": False,
            "reason": "timeout",
            "restarts_last_10m": 2,
            "restart_capped": False,
            "backoff_sec_remaining": 10,
        }

        with patch("ReDNACoreDemo.devx.backend.supervisor_ucnrr.get_ucnrr_status", return_value=mock_ucnrr_status):
            analysis, _ = _compute_readiness(inputs)

        assert "ucnrr_backoff_active" in analysis["fail_conditions"]
        assert any("backoff" in reason.lower() for reason in analysis["reasons"])

    def test_recovery_suggestions_ensure_ucnrr(self):
        """Test that ensure_ucnrr suggestion is provided for unreachable UCNRR."""
        inputs = {
            "health": {
                "status": "healthy",
                "rr_mode": "degraded",
                "features": {"ucnrr_enabled": True},
            },
            "metrics": {
                "uptime_seconds": 60,
                "rolling_window": {
                    "window_seconds": 300,
                    "requests_window_5m": 10,
                    "errors_5xx_window_5m": 0,
                    "latency_p95_ms_window_5m": 100,
                    "warming": False,
                },
                "counters": {
                    "http.requests.total": 100,
                    "http.requests.errors": 0,
                },
                "timers": {
                    "http.latency_ms": {"p95": 100},
                },
            },
        }

        mock_ucnrr_status = {
            "alive": False,
            "llm_configured": False,
            "reason": "conn_refused",
            "restarts_last_10m": 0,
            "restart_capped": False,
            "backoff_sec_remaining": 0,
        }

        with patch("ReDNACoreDemo.devx.backend.supervisor_ucnrr.get_ucnrr_status", return_value=mock_ucnrr_status):
            analysis, _ = _compute_readiness(inputs)

        suggestions = analysis["recovery_suggestions"]
        ucnrr_suggestion = next((s for s in suggestions if s["service"] == "ucnrr"), None)

        assert ucnrr_suggestion is not None
        assert ucnrr_suggestion["action"] == "ensure_ucnrr"
        assert "hint" in ucnrr_suggestion

    def test_recovery_suggestions_start_ollama(self):
        """Test that start_ollama suggestion is provided for LLM disabled."""
        inputs = {
            "health": {
                "status": "healthy",
                "rr_mode": "degraded",
                "features": {"ucnrr_enabled": True},
            },
            "metrics": {
                "uptime_seconds": 60,
                "rolling_window": {
                    "window_seconds": 300,
                    "requests_window_5m": 10,
                    "errors_5xx_window_5m": 0,
                    "latency_p95_ms_window_5m": 100,
                    "warming": False,
                },
                "counters": {
                    "http.requests.total": 100,
                    "http.requests.errors": 0,
                },
                "timers": {
                    "http.latency_ms": {"p95": 100},
                },
            },
        }

        mock_ucnrr_status = {
            "alive": True,
            "llm_configured": False,
            "reason": "bad_llm",
            "restarts_last_10m": 0,
            "restart_capped": False,
            "backoff_sec_remaining": 0,
        }

        with patch("ReDNACoreDemo.devx.backend.supervisor_ucnrr.get_ucnrr_status", return_value=mock_ucnrr_status):
            analysis, _ = _compute_readiness(inputs)

        suggestions = analysis["recovery_suggestions"]
        ucnrr_suggestion = next((s for s in suggestions if s["service"] == "ucnrr"), None)

        assert ucnrr_suggestion is not None
        assert ucnrr_suggestion["action"] == "start_ollama"
        assert "ollama" in ucnrr_suggestion["hint"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
