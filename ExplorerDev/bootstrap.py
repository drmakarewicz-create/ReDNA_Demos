"""Bootstrap helpers so ExplorerDev modules work as scripts or packages."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict


def ensure_explorerdev_on_path() -> Dict[str, object]:
    """Ensure the repository root is on ``sys.path`` and return debug info."""

    pkg_dir = Path(__file__).resolve().parent
    parent = pkg_dir.parent
    parent_str = str(parent)
    try:
        index = sys.path.index(parent_str)
        added = False
    except ValueError:
        sys.path.insert(0, parent_str)
        index = 0
        added = True
    return {
        "ok": True,
        "path": parent_str,
        "pkg_dir": str(pkg_dir),
        "sys_path_index": index,
        "pkg_dir": str(pkg_dir),
        "sys_path": list(sys.path),
    }


def ensure_repo_root() -> Path:
    """Return repository root (parent of ExplorerDev) ensuring path insertion."""

    info = ensure_explorerdev_on_path()
    return Path(info["pkg_dir"]).parent  # type: ignore[arg-type]


__all__ = ["ensure_explorerdev_on_path", "ensure_repo_root"]
