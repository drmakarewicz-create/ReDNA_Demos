"""Bootstrap smoke tests for Dev Explorer."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from ExplorerDev.bootstrap import ensure_repo_root


@pytest.mark.parametrize(
    "module_name",
    ["shared.persona_schema", "ReDNACoreDemo.core.holistic"],
)
def test_bootstrap_enables_imports(module_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    repo_str = str(repo_root)
    # Remove existing repo root entries to simulate a bare ExplorerDev launch.
    stripped_sys_path = [p for p in sys.path if Path(p).resolve() != repo_root]
    monkeypatch.setattr(sys, "path", stripped_sys_path, raising=False)

    ensure_repo_root()

    module = importlib.import_module(module_name)
    assert module is not None
