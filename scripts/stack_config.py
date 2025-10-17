#!/usr/bin/env python3
"""
Utility for retrieving the resolved stack configuration from DevX.

Usage:
    python scripts/stack_config.py --devx-base http://127.0.0.1:8100 --print=json
    python scripts/stack_config.py --devx-base http://127.0.0.1:8100 --print=env
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Iterable
from urllib.parse import urljoin

import httpx

CONFIG_PATH = "/devx/api/stack/config"
DEFAULT_CONNECT_TIMEOUT = 0.8
DEFAULT_READ_TIMEOUT = 2.5


def _fetch_config(devx_base: str, retries: int = 2) -> Dict[str, object]:
    """Fetch the stack config with a small retry loop."""
    devx_base = devx_base.rstrip("/")
    url = urljoin(f"{devx_base}/", CONFIG_PATH.lstrip("/"))
    timeout = httpx.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT,
        read=DEFAULT_READ_TIMEOUT,
        write=DEFAULT_READ_TIMEOUT,
        pool=DEFAULT_READ_TIMEOUT,
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Stack config payload was not a JSON object")
                return payload
        except Exception as exc:  # noqa: BLE001 - bubble after retries
            last_error = exc
            if attempt <= retries:
                continue
            raise RuntimeError(f"Failed to fetch stack config from {url}: {exc}") from exc
    raise RuntimeError("Unexpected retry state while fetching stack config")


def _emit_env_lines(config: Dict[str, object]) -> Iterable[str]:
    """Yield env style KEY=value lines from config mapping."""
    mapping = {
        "CORE_BASE": "core_base",
        "UCNRR_BASE": "ucnrr_base",
        "DEVX_BASE": "devx_base",
        "CORE_PORT": "core_port",
        "UCNRR_PORT": "ucnrr_port",
        "DEVX_PORT": "devx_port",
    }
    for env_key, json_key in mapping.items():
        value = config.get(json_key)
        yield f"{env_key}={value}"


def main(argv: Iterable[str]) -> int:
    parser = argparse.ArgumentParser(description="Fetch resolved stack configuration.")
    parser.add_argument(
        "--devx-base",
        required=True,
        help="Base URL for the DevX backend (e.g., http://127.0.0.1:8100)",
    )
    parser.add_argument(
        "--print",
        choices=("json", "env"),
        default="json",
        dest="print_mode",
        help="Output format",
    )
    args = parser.parse_args(argv)

    try:
        config = _fetch_config(args.devx_base)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.print_mode == "json":
        json.dump(config, sys.stdout)
        sys.stdout.write("\n")
        return 0

    for line in _emit_env_lines(config):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
