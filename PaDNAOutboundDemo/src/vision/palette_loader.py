"""Palette loading helpers for PaDNA renderer themes."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml


@lru_cache(maxsize=1)
def load_palettes() -> Dict[str, Dict[str, Any]]:
    """Load shared palette ramps from palettes.yaml."""

    path = Path(__file__).resolve().parent / "palettes.yaml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def get_palette(section: str, key: str, *, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    palettes = load_palettes()
    section_data = palettes.get(section, {}) if isinstance(palettes, dict) else {}
    if not isinstance(section_data, dict):
        return default or {}
    entry = section_data.get(key)
    return entry if isinstance(entry, dict) else (default or {})


__all__ = ["load_palettes", "get_palette"]
