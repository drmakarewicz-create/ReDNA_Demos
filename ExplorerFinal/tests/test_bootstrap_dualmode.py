from __future__ import annotations

import importlib
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = ROOT / "ExplorerFinal"
PAGES_DIR = PKG_DIR / "pages"
PAGE_FILE = PAGES_DIR / "05_Head_Coach.py"


def _clear_explorer_modules() -> None:
    for name in list(sys.modules):
        if name == "ExplorerFinal" or name.startswith("ExplorerFinal."):
            sys.modules.pop(name, None)


def test_dual_mode_bootstrap(monkeypatch):
    # Script-style execution (Streamlit worker cwd inside ExplorerFinal/)
    _clear_explorer_modules()
    monkeypatch.chdir(PKG_DIR)
    monkeypatch.setattr(sys, "path", [str(PKG_DIR)], raising=False)
    runpy.run_path(str(PAGE_FILE), run_name="__main__")

    # Package-style import from repo root
    _clear_explorer_modules()
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(sys, "path", [str(ROOT)], raising=False)
    module = importlib.import_module("ExplorerFinal.explorer_final")
    assert hasattr(module, "UCNRR_BASE")
