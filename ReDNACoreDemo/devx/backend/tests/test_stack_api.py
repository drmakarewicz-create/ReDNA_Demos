import json
from typing import Any, Dict, List

import pytest

from devx.backend import stack_api


@pytest.mark.asyncio
async def test_get_stack_status_all_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_probe(service: stack_api.ServiceDefinition) -> stack_api.ServiceStatus:
        return stack_api.ServiceStatus(
            service=service.key,
            status="healthy",
            port=service.port,
            health={"status": "healthy", "version": "1.2.3"},
            last_check="2025-10-15T00:00:00Z",
            version="1.2.3",
            python="/usr/bin/python",
        )

    monkeypatch.setattr(stack_api, "_probe_service", fake_probe)
    result = await stack_api.get_stack_status()
    assert all(entry.status == "healthy" for entry in result.services)
    assert result.timestamp.endswith("Z")
    assert all(entry.python for entry in result.services)
    assert any(entry.version == "1.2.3" for entry in result.services)


@pytest.mark.asyncio
async def test_get_stack_status_one_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mixed_probe(service: stack_api.ServiceDefinition) -> stack_api.ServiceStatus:
        state = "down" if service.key == "ucnrr" else "healthy"
        payload = {"status": "healthy"} if state != "down" else None
        return stack_api.ServiceStatus(
            service=service.key,
            status=state,
            port=service.port,
            health=payload,
            last_check="ts",
            error=None if state != "down" else "connection refused",
            python=service.python_path,
        )

    monkeypatch.setattr(stack_api, "_probe_service", mixed_probe)
    result = await stack_api.get_stack_status()
    statuses = {entry.service: entry.status for entry in result.services}
    assert statuses["ucnrr"] == "down"
    assert statuses["core"] == "healthy"


@pytest.mark.asyncio
async def test_diagnose_port_in_use(monkeypatch: pytest.MonkeyPatch) -> None:
    service = stack_api.SERVICES["core"]

    def fake_listeners(_: stack_api.ServiceDefinition, __: int) -> List[stack_api.ListenerInfo]:
        return [stack_api.ListenerInfo(pid=9999, cmd="uvicorn core")]

    monkeypatch.setattr(stack_api, "_listeners_for", fake_listeners)
    monkeypatch.setattr(stack_api, "_read_pid", lambda _: 9999)
    monkeypatch.setattr(stack_api, "_pid_alive", lambda _: True)
    monkeypatch.setattr(stack_api, "_last_log_entry", lambda _: {"ts": "now", "event": "core_start"})

    response = await stack_api.post_diagnose(stack_api.DiagnoseRequest(service=service.key))
    assert not response.port_available
    assert response.process_running
    assert response.pid == 9999
    assert response.last_log_entry["event"] == "core_start"


@pytest.mark.asyncio
async def test_restart_service(monkeypatch: pytest.MonkeyPatch) -> None:
    called: Dict[str, Any] = {}

    async def fake_kill(service: stack_api.ServiceDefinition) -> None:
        called["killed"] = service.key

    async def fake_start(service: stack_api.ServiceDefinition, port: int) -> int:
        called["started"] = port
        return 4242

    async def fake_wait(service: stack_api.ServiceDefinition, port: int, attempts: int = 10, delay: float = 1.0) -> Dict[str, Any]:
        return {"status": "healthy", "port": port}

    monkeypatch.setattr(stack_api, "_kill_service", fake_kill)
    monkeypatch.setattr(stack_api, "_start_service", fake_start)
    monkeypatch.setattr(stack_api, "_wait_for_health", fake_wait)
    monkeypatch.setattr(stack_api, "_tail_json", lambda *_args, **_kwargs: [{"ts": "now", "event": "started"}])

    payload = stack_api.RestartRequest(service="core", port=8015)
    result = await stack_api.post_restart(payload)
    assert called["killed"] == "core"
    assert called["started"] == 8015
    assert result.health_check == "passed"
    assert result.pid == 4242
    assert result.startup_logs[0]["event"] == "started"


@pytest.mark.asyncio
async def test_selftest_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORE_PORT", "8123")
    service = stack_api.SERVICES["core"]

    class DummyResponse:
        def __init__(self, payload: Dict[str, Any]) -> None:
            self._payload = payload

        def json(self) -> Dict[str, Any]:
            return self._payload

    class DummyClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "DummyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: Dict[str, Any]) -> DummyResponse:
            assert url.endswith("/ui/chat/send")
            assert json["text"] == "I have blue eyes"
            payload = {"results": [{"evidence": [{"id": "PaDNA.EyeDNA.IrisColor"}]}]}
            return DummyResponse(payload)

    monkeypatch.setattr(stack_api.httpx, "AsyncClient", DummyClient)
    result = await stack_api._selftest_core(service)
    assert result.passed
    assert result.test == "blue_eyes_chat"


@pytest.mark.asyncio
async def test_logs_endpoint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_path = tmp_path / "core.jsonl"
    entries = [
        {"ts": "2025-10-15T00:00:00Z", "level": "INFO", "event": "start"},
        {"ts": "2025-10-15T00:00:05Z", "level": "ERROR", "event": "failure"},
    ]
    text = "\n".join(json.dumps(entry) for entry in entries) + "\n"
    log_path.write_text(text, encoding="utf-8")

    service = stack_api.SERVICES["core"]
    original_log = service.log_file
    original_legacy = service.legacy_log_file
    service.log_file = log_path
    service.legacy_log_file = log_path

    try:
        response = await stack_api.get_logs("core", lines=10, level="ERROR")
    finally:
        service.log_file = original_log
        service.legacy_log_file = original_legacy

    assert response.total_lines == 1
    assert response.lines[0].level == "ERROR"
    assert response.lines[0].event == "failure"
