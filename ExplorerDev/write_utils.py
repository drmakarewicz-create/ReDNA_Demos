"""Shared write utilities for Dev Explorer."""

from __future__ import annotations

from typing import Protocol


class WriteProtectContext(Protocol):
    """Protocol for contexts that expose a write_protect flag."""

    write_protect: bool


def write_guard(context: WriteProtectContext, *, action: str) -> None:
    """Raise if writes are blocked for the given context."""

    if getattr(context, "write_protect", False):
        raise PermissionError(
            f"Write-protect ON — unable to {action}. Set `WRITE_PROTECT=false` to allow writes."
        )
