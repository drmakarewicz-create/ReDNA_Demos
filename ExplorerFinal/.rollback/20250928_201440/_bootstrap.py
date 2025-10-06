"""Explorer bootstrap to ensure repo root is importable."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _ensure_repo_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    repo_str = str(repo_root)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)
    return repo_root


REPO_ROOT = _ensure_repo_root()

_SPEC = importlib.util.find_spec("shared.persona_schema")
if _SPEC is None:
    instructions = (
        "Explorer could not import 'shared.persona_schema'.\n\n"
        "Add the repository root to PYTHONPATH before launching Streamlit. For example:\n"
        f"    cd {REPO_ROOT}\n"
        "    export PYTHONPATH=\"$(pwd)\"\n"
        "    streamlit run ExplorerFinal/explorer_final.py\n"
    )
    try:  # pragma: no cover - UI feedback when Streamlit is available
        import streamlit as st

        st.error(instructions)
    except Exception:  # pragma: no cover - fallback for non-Streamlit contexts
        sys.stderr.write(instructions + "\n")
    raise ModuleNotFoundError(
        "shared.persona_schema not found. Ensure the repo root is on PYTHONPATH before running Explorer."
    )


__all__ = ["REPO_ROOT"]
