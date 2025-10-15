"""Core package public surface area.

The original module eagerly imported FastAPI dependencies which makes it
impossible to reuse utility modules (e.g. redna_core) in lightweight contexts
like offline QA harnesses where FastAPI isn't installed.  To keep the public
API stable while avoiding the hard dependency, we lazily import the web app
construction helper the first time it is requested.
"""

from __future__ import annotations

from typing import Any


def build_app(*args: Any, **kwargs: Any):  # pragma: no cover - thin passthrough
    from .api import build_app as _build_app

    return _build_app(*args, **kwargs)


__all__ = ["build_app"]
