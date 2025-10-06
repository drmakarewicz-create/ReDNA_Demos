"""Developer Explorer tab modules."""

from __future__ import annotations

__all__ = [
    "render_observability_tab",
    "render_governance_tab",
    "render_analytics_tab",
]

try:
    from ExplorerDev.tabs.observability import render_observability_tab
except ImportError:  # pragma: no cover
    render_observability_tab = None  # type: ignore

try:
    from ExplorerDev.tabs.governance import render_governance_tab
except ImportError:  # pragma: no cover
    render_governance_tab = None  # type: ignore

try:
    from ExplorerDev.tabs.analytics import render_analytics_tab
except ImportError:  # pragma: no cover
    render_analytics_tab = None  # type: ignore
