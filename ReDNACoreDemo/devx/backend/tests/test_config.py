from __future__ import annotations

import importlib

import pytest

from ReDNACoreDemo.devx.backend import config as config_module


@pytest.fixture
def reload_config(monkeypatch: pytest.MonkeyPatch):
    def _reload(core_base: str | None = None, ucnrr_base: str | None = None):
        monkeypatch.delenv("DEVX_CORE_BASE", raising=False)
        monkeypatch.delenv("DEVX_UCNRR_BASE", raising=False)
        if core_base is not None:
            monkeypatch.setenv("DEVX_CORE_BASE", core_base)
        if ucnrr_base is not None:
            monkeypatch.setenv("DEVX_UCNRR_BASE", ucnrr_base)
        return importlib.reload(config_module)

    yield _reload
    importlib.reload(config_module)


def test_config_defaults(reload_config):
    module = reload_config()
    assert module.DEVX_CORE_BASE == "http://127.0.0.1:8001"
    assert module.DEVX_UCNRR_BASE == "http://127.0.0.1:8011"


def test_config_overrides(reload_config):
    module = reload_config(core_base="https://core.example.com:1234/", ucnrr_base="ucn.example.com:5555")
    assert module.DEVX_CORE_BASE == "https://core.example.com:1234"
    assert module.DEVX_UCNRR_BASE == "http://ucn.example.com:5555"
