from __future__ import annotations

from typing import Dict

import pytest
from fastapi.testclient import TestClient

from devx.backend import api, stack_api
from scripts import cppp_bootstrap


@pytest.mark.parametrize("interactive", [False])
def test_bootstrap_script(monkeypatch: pytest.MonkeyPatch, interactive: bool) -> None:
    service_pids: Dict[str, int] = {}

    async def fake_health(service: stack_api.ServiceDefinition, port: int, attempts: int = 10, delay: float = 1.0) -> Dict[str, str]:
        return {"status": "healthy", "port": port}

    def fake_start(service: stack_api.ServiceDefinition, port: int) -> int:
        pid = 1000 + hash(service.key) % 100
        service_pids[service.key] = pid
        return pid

    monkeypatch.setattr(cppp_bootstrap, '_ensure_port', lambda svc: svc.port)
    monkeypatch.setattr(cppp_bootstrap.stack_api, '_start_service_sync', fake_start)
    monkeypatch.setattr(cppp_bootstrap, '_await_health', fake_health)

    rc = cppp_bootstrap.bootstrap_stack(interactive=interactive)
    assert rc == 0
    assert set(service_pids) == {'ucnrr', 'core', 'devx'}


def test_restart_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_kill(service: stack_api.ServiceDefinition) -> None:
        return None

    async def fake_start(service: stack_api.ServiceDefinition, port: int) -> int:
        return 4321

    async def fake_wait(service: stack_api.ServiceDefinition, port: int, attempts: int = 10, delay: float = 1.0) -> Dict[str, str]:
        return {"status": "healthy"}

    monkeypatch.setattr(stack_api, '_kill_service', fake_kill)
    monkeypatch.setattr(stack_api, '_start_service', fake_start)
    monkeypatch.setattr(stack_api, '_wait_for_health', fake_wait)
    monkeypatch.setattr(stack_api, '_tail_json', lambda *_args, **_kwargs: [])

    client = TestClient(api.app)
    response = client.post("/devx/api/stack/restart", json={"service": "core", "port": 8015})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["pid"] == 4321
