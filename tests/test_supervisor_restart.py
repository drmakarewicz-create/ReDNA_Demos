import pathlib
import sys
import time

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ReDNACoreDemo.devx.backend import supervisor


@pytest.fixture(autouse=True)
def isolate_state(monkeypatch, tmp_path):
    state_dir = tmp_path / "supervisor"
    state_dir.mkdir()
    log_dir = state_dir / "logs"
    log_dir.mkdir()
    state_path = state_dir / "state.json"

    monkeypatch.setattr(supervisor, "SUPERVISOR_DIR", state_dir)
    monkeypatch.setattr(supervisor, "LOG_DIR", log_dir)
    monkeypatch.setattr(supervisor, "STATE_PATH", state_path)

    # Seed empty state
    supervisor._save_state(supervisor._load_state())


def test_supervisor_restart_and_rate_limit(monkeypatch):
    started = {"core": 0, "ucnrr": 0}

    def fake_start(service, state, reason):
        started[service] += 1
        pid = started[service]
        meta = state["services"][service]
        meta["pid"] = pid
        meta["last_restart"] = "2025-01-01T00:00:00Z"
        supervisor._record_restart_timestamp(meta, time.time())
        supervisor._append_history(state, supervisor._history_entry(service, "restarted", reason, False, pid))
        return pid

    def fake_stop(service, state):
        state["services"][service]["pid"] = None

    monkeypatch.setattr(supervisor, "_start_service_locked", fake_start)
    monkeypatch.setattr(supervisor, "_stop_service_locked", fake_stop)
    monkeypatch.setattr(supervisor, "restart_grace_seconds", lambda: 5)
    monkeypatch.setattr(supervisor, "max_restarts_per_hour", lambda: 2)

    result = supervisor.restart_services(["core"], reason="initial", force=True, eligible_services={"core"})
    assert result["restarted"] == [{"service": "core", "status": "restarted", "pid": 1}]

    history = supervisor.get_restart_history()
    assert history
    assert history[-1]["reason"] == "initial"

    # Second restart within limit succeeds when eligible
    result = supervisor.restart_services(["core"], reason="second", force=False, eligible_services={"core"})
    assert result["restarted"][0]["status"] == "restarted"

    # Third restart exceeds rate limit
    monkeypatch.setattr(supervisor, "max_restarts_per_hour", lambda: 2)
    result = supervisor.restart_services(["core"], reason="rate_check", force=False, eligible_services={"core"})
    assert result["rate_limited"][0]["service"] == "core"

    # Not eligible skip
    skipped = supervisor.restart_services(["ucnrr"], reason="skip", force=False, eligible_services=set())
    assert skipped["skipped"][0]["status"] == "not_eligible"
