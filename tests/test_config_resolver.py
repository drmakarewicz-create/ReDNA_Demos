from __future__ import annotations

from pathlib import Path

import pytest

from ReDNACoreDemo.devx.backend import config_resolver


@pytest.fixture
def sandbox_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(config_resolver, "ENV_FILE_PATH", env_file)
    config_resolver.clear_env_cache()
    yield env_file
    config_resolver.clear_env_cache()


def test_env_precedence_over_env_file(monkeypatch: pytest.MonkeyPatch, sandbox_env_file: Path) -> None:
    sandbox_env_file.write_text("CORE_BASE=http://envfile-core:9001\n", encoding="utf-8")

    monkeypatch.setenv("CORE_BASE", "http://env-core:9101")
    config_resolver.clear_env_cache()

    config = config_resolver.resolve_stack_config()
    assert config["core_base"] == "http://env-core:9101"
    assert config["source"]["core_base"] == "ENV"

    monkeypatch.delenv("CORE_BASE", raising=False)
    config = config_resolver.resolve_stack_config()
    assert config["core_base"] == "http://envfile-core:9001"
    assert config["source"]["core_base"] == "ENVFILE"


def test_env_file_over_defaults(monkeypatch: pytest.MonkeyPatch, sandbox_env_file: Path) -> None:
    sandbox_env_file.write_text(
        "\n".join(
            [
                "UCNRR_BASE=http://envfile-ucnrr:8123",
                "DEVX_BASE=http://envfile-devx:8223",
                "DEVX_PORT=8400",
            ]
        ),
        encoding="utf-8",
    )
    config_resolver.clear_env_cache()
    config = config_resolver.resolve_stack_config()

    assert config["ucnrr_base"] == "http://envfile-ucnrr:8123"
    assert config["devx_base"] == "http://envfile-devx:8223"
    assert config["devx_port"] == 8400
    assert config["source"]["ucnrr_base"] == "ENVFILE"
    assert config["source"]["devx_port"] == "ENVFILE"


def test_warning_for_port_mismatch(monkeypatch: pytest.MonkeyPatch, sandbox_env_file: Path) -> None:
    sandbox_env_file.write_text("", encoding="utf-8")
    config_resolver.clear_env_cache()

    monkeypatch.setenv("UCNRR_BASE", "http://127.0.0.1:8017")
    monkeypatch.setenv("UCNRR_PORT", "8011")
    config = config_resolver.resolve_stack_config()

    assert "ucnrr_base_port_mismatch" in config["warnings"]
