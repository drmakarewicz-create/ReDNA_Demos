import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ReDNACoreDemo.devx.backend import stack_api


@pytest.fixture(autouse=True)
def stub_rate_limit(monkeypatch):
    monkeypatch.setattr(stack_api.supervisor, "get_rate_limit_status", lambda: {"core": {"rate_limited": False, "recent_restarts": 0, "remaining": 6}, "ucnrr": {"rate_limited": False, "recent_restarts": 0, "remaining": 6}})
    monkeypatch.setattr(stack_api.supervisor, "max_restarts_per_hour", lambda: 6)
    stack_api.WARMUP_FALLBACK_LOGGED = False


def test_readiness_ready_state(monkeypatch):
    metrics = {
        "rolling_window": {
            "window_seconds": 300,
            "requests_window_5m": 12,
            "errors_5xx_window_5m": 0,
            "latency_p95_ms_window_5m": 210,
            "warming": False,
        }
    }
    inputs = {
        "metrics": metrics,
        "health": {"status": "healthy", "rr_mode": "online"},
        "ucnrr_selftest": {"ok": True},
    }

    analysis, eligible = stack_api._compute_readiness(inputs)
    assert analysis["ready"] is True
    assert analysis["status"] == "ready"
    assert analysis["fail_conditions"] == []
    assert analysis["recovery_suggestions"] == []
    assert eligible == []


def test_readiness_detects_high_error_rate():
    metrics = {
        "rolling_window": {
            "window_seconds": 300,
            "requests_window_5m": 20,
            "errors_5xx_window_5m": 2,
            "latency_p95_ms_window_5m": 400,
            "warming": False,
        }
    }
    inputs = {
        "metrics": metrics,
        "health": {"status": "healthy", "rr_mode": "online"},
        "ucnrr_selftest": {"ok": True},
    }

    analysis, eligible = stack_api._compute_readiness(inputs)
    assert analysis["ready"] is False
    assert analysis["status"] == "unready"
    assert "core_error_rate_high" in analysis["fail_conditions"]
    assert any(suggestion["service"] == "core" for suggestion in analysis["recovery_suggestions"])
    assert eligible == ["core"]


def test_readiness_warming_state():
    metrics = {
        "rolling_window": {
            "window_seconds": 300,
            "requests_window_5m": 0,
            "errors_5xx_window_5m": 0,
            "latency_p95_ms_window_5m": None,
            "warming": True,
        }
    }
    inputs = {
        "metrics": metrics,
        "health": {"status": "healthy", "rr_mode": "online"},
        "ucnrr_selftest": {"ok": True},
    }

    analysis, eligible = stack_api._compute_readiness(inputs)
    assert analysis["ready"] is False
    assert analysis["status"] == "warming"
    assert analysis["fail_conditions"] == ["metrics_warming"]
    assert analysis["recovery_suggestions"] == []
    assert eligible == []


def test_readiness_accepts_degraded_rr_mode():
    metrics = {
        "rolling_window": {
            "window_seconds": 300,
            "requests_window_5m": 5,
            "errors_5xx_window_5m": 0,
            "latency_p95_ms_window_5m": 120,
            "warming": False,
        }
    }
    inputs = {
        "metrics": metrics,
        "health": {"status": "healthy", "rr_mode": "degraded"},
        "ucnrr_selftest": {"ok": True},
    }

    analysis, eligible = stack_api._compute_readiness(inputs)
    assert analysis["ready"] is True
    assert analysis["status"] == "ready"
    assert eligible == []


def test_readiness_warmup_fallback(monkeypatch):
    stack_api.WARMUP_FALLBACK_LOGGED = False
    monkeypatch.setattr(stack_api, "READINESS_WARMUP_SEC", 0.0)
    monkeypatch.setattr(stack_api, "READINESS_ERROR_RATE_MAX", 0.02)
    monkeypatch.setattr(stack_api, "READINESS_P95_MAX_MS", 750.0)

    events = []

    def capture_log(*args, **kwargs):
        events.append((args, kwargs))

    monkeypatch.setattr(stack_api, "stack_log", capture_log)

    metrics = {
        "rolling_window": {
            "window_seconds": 300,
            "requests_window_5m": 0,
            "errors_5xx_window_5m": 0,
            "latency_p95_ms_window_5m": None,
            "warming": True,
        },
        "uptime_seconds": 45,
        "counters": {
            "http.requests.total": 0,
            "http.requests.errors": 0,
        },
        "timers": {
            "http.latency_ms": {"p95": 200.0},
        },
    }
    inputs = {
        "metrics": metrics,
        "health": {"status": "healthy", "rr_mode": "online"},
        "ucnrr_selftest": {"ok": True},
    }

    analysis, eligible = stack_api._compute_readiness(inputs)
    assert analysis["ready"] is True
    assert analysis["status"] == "ready"
    assert analysis["warmup_fallback_used"] is True
    assert analysis["fail_conditions"] == []
    assert eligible == []
    assert any(args[2] == "readiness_warmup_fallback" for args, _ in events)
    stack_api.WARMUP_FALLBACK_LOGGED = False
