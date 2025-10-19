from __future__ import annotations

from fastapi.testclient import TestClient

from ReDNACoreDemo.devx.backend import api, config_resolver


def test_stack_config_endpoint_reports_resolved_values(monkeypatch):
    monkeypatch.setenv("CORE_BASE", "http://config-core:9101")
    monkeypatch.setenv("UCNRR_BASE", "http://config-ucnrr:9102")
    monkeypatch.setenv("DEVX_BASE", "http://config-devx:9103")
    monkeypatch.setenv("CORE_PORT", "9101")
    monkeypatch.setenv("UCNRR_PORT", "9102")
    monkeypatch.setenv("DEVX_PORT", "9103")
    config_resolver.clear_env_cache()

    client = TestClient(api.app)
    response = client.get("/devx/api/stack/config")
    assert response.status_code == 200

    payload = response.json()
    assert payload["core_base"] == "http://config-core:9101"
    assert payload["ucnrr_base"] == "http://config-ucnrr:9102"
    assert payload["devx_base"] == "http://config-devx:9103"
    assert payload["core_port"] == 9101
    assert payload["ucnrr_port"] == 9102
    assert payload["devx_port"] == 9103
    assert payload["warnings"] == []
    assert payload["source"]["core_base"] == "ENV"
    assert payload["source"]["devx_port"] == "ENV"
