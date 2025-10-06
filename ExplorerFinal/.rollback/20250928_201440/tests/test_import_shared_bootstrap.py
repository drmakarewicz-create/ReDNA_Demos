from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clear_shared_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    for name in list(sys.modules):
        if name.startswith("shared.") or name == "shared":
            sys.modules.pop(name, None)
    yield


def test_bootstrap_allows_shared_import(monkeypatch: pytest.MonkeyPatch):
    pages_dir = Path(__file__).resolve().parents[1] / "pages"
    monkeypatch.chdir(pages_dir)

    repo_root = Path(__file__).resolve().parents[2]
    repo_str = str(repo_root)
    if repo_str in sys.path:
        new_path = [p for p in sys.path if p != repo_str]
        monkeypatch.setattr(sys, "path", new_path, raising=False)

    if "ExplorerFinal._bootstrap" in sys.modules:
        sys.modules.pop("ExplorerFinal._bootstrap", None)

    import ExplorerFinal._bootstrap  # noqa: F401

    spec = importlib.util.find_spec("shared.persona_schema")
    assert spec is not None

    module = importlib.import_module("shared.persona_schema")
    assert hasattr(module, "validate_persona_config")
