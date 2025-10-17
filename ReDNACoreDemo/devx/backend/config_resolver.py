"""
Unified stack configuration resolver.

Provides a single source of truth for Core, UCNRR, and DevX base URLs
and ports by applying consistent precedence rules:
CLI overrides > environment variables > .env file > defaults.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping
from urllib.parse import urlparse

from dotenv import dotenv_values


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE_PATH = REPO_ROOT / ".env"

DEFAULT_BASES: Dict[str, str] = {
    "core_base": "http://127.0.0.1:8001",
    "ucnrr_base": "http://127.0.0.1:8011",
    "devx_base": "http://127.0.0.1:8100",
}

DEFAULT_PORTS: Dict[str, int] = {
    "core_port": 8001,
    "ucnrr_port": 8011,
    "devx_port": 8100,
}

# Environment variable lookup order per field
ENV_VAR_KEYS: Dict[str, tuple[str, ...]] = {
    "core_base": ("CORE_BASE", "DEVX_CORE_BASE"),
    "ucnrr_base": ("UCNRR_BASE", "DEVX_UCNRR_BASE"),
    "devx_base": ("DEVX_BASE",),
    "core_port": ("CORE_PORT",),
    "ucnrr_port": ("UCNRR_PORT",),
    "devx_port": ("DEVX_PORT", "DEVX_BACKEND_PORT"),
}

WARNING_CODES = {
    "core": "core_base_port_mismatch",
    "ucnrr": "ucnrr_base_port_mismatch",
    "devx": "devx_base_port_mismatch",
}


class StackConfig(Dict[str, Any]):
    """Typed alias for resolved stack configuration dictionary."""


def _normalize_base(value: Any, default: str) -> str:
    candidate = str(value).strip() if value is not None else ""
    if not candidate:
        candidate = default
    if "://" not in candidate:
        candidate = f"http://{candidate}"
    return candidate.rstrip("/")


def _normalize_port(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        port = int(text, 10)
        if 0 < port < 65536:
            return port
    except ValueError:
        pass
    return default


def _port_from_url(url: str, default: int) -> int:
    parsed = urlparse(url)
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    if parsed.scheme == "http":
        return 80
    return default


def _normalize_override_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _normalize_overrides(overrides: Mapping[str, Any] | None) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if not overrides:
        return normalized
    for raw_key, value in overrides.items():
        if raw_key is None:
            continue
        key = _normalize_override_key(str(raw_key))
        if key in DEFAULT_BASES or key in DEFAULT_PORTS:
            normalized[key] = value
    return normalized


@lru_cache(maxsize=1)
def _load_env_file() -> MutableMapping[str, str]:
    if not ENV_FILE_PATH.exists():
        return {}
    values = dotenv_values(str(ENV_FILE_PATH))
    return {key: value for key, value in values.items() if isinstance(key, str) and value is not None}


def _resolve_value(
    field: str,
    overrides: Mapping[str, Any],
    env_values: Mapping[str, str],
    env_file_values: Mapping[str, str],
) -> tuple[Any, str]:
    if field in overrides:
        return overrides[field], "CLI"

    for env_key in ENV_VAR_KEYS.get(field, ()):  # type: ignore[arg-type]
        if env_key in env_values and env_values[env_key].strip():
            return env_values[env_key], "ENV"

    for env_key in ENV_VAR_KEYS.get(field, ()):  # type: ignore[arg-type]
        if env_key in env_file_values and env_file_values[env_key].strip():
            return env_file_values[env_key], "ENVFILE"

    default_pool = DEFAULT_BASES if field in DEFAULT_BASES else DEFAULT_PORTS
    return default_pool[field], "DEFAULT"


def resolve_stack_config(overrides: Mapping[str, Any] | None = None) -> StackConfig:
    """
    Resolve stack configuration applying CLI/ENV/.env/default precedence.

    Args:
        overrides: Optional mapping containing CLI-provided overrides.

    Returns:
        StackConfig dictionary with resolved bases, ports, sources, and warnings.
    """
    env_values = os.environ
    env_file_values = _load_env_file()
    normalized_overrides = _normalize_overrides(overrides)

    result: StackConfig = StackConfig()
    sources: Dict[str, str] = {}
    warnings: list[str] = []

    for key in ("core_base", "ucnrr_base", "devx_base"):
        raw_value, source = _resolve_value(key, normalized_overrides, env_values, env_file_values)
        value = _normalize_base(raw_value, DEFAULT_BASES[key])
        result[key] = value
        sources[key] = source

    for key in ("core_port", "ucnrr_port", "devx_port"):
        raw_value, source = _resolve_value(key, normalized_overrides, env_values, env_file_values)
        value = _normalize_port(raw_value, DEFAULT_PORTS[key])
        result[key] = value
        sources[key] = source

    # Detect mismatches between *_BASE URLs and *_PORT integers.
    base_port_pairs = (
        ("core", result["core_base"], result["core_port"]),
        ("ucnrr", result["ucnrr_base"], result["ucnrr_port"]),
        ("devx", result["devx_base"], result["devx_port"]),
    )
    for service, base_url, explicit_port in base_port_pairs:
        base_port = _port_from_url(base_url, explicit_port)
        if base_port != explicit_port:
            warnings.append(WARNING_CODES[service])

    result["source"] = sources
    result["warnings"] = warnings
    return result


def clear_env_cache() -> None:
    """Clear cached .env values (useful for tests)."""
    _load_env_file.cache_clear()


__all__ = [
    "resolve_stack_config",
    "StackConfig",
    "DEFAULT_BASES",
    "DEFAULT_PORTS",
    "clear_env_cache",
]
