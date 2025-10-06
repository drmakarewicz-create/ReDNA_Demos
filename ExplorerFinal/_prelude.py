from __future__ import annotations

import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
PKG_DIR = THIS_FILE.parent
REPO_ROOT = PKG_DIR.parent

for candidate in (REPO_ROOT, PKG_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

__all__ = ["PKG_DIR", "REPO_ROOT"]
