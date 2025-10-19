#!/usr/bin/env python3
"""
Quick smoke script for the Life OS human intelligence endpoint.

Usage:
    python scripts/smoke_human_intel.py --core http://localhost:8015 --user USER1 --days 7
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    import requests
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit("requests must be installed to run this script") from exc


def _print(obj: Any) -> None:
    try:
        text = json.dumps(obj, indent=2, sort_keys=True)
    except (TypeError, ValueError):
        text = str(obj)
    print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test for /ui/hc/life/{user}/human_intel endpoint.")
    parser.add_argument("--core", default="http://localhost:8015", help="Core API base URL (default: %(default)s)")
    parser.add_argument("--user", default="USER1", help="Target user id (default: %(default)s)")
    parser.add_argument("--days", type=int, default=7, help="Window size in days (default: %(default)s)")
    args = parser.parse_args(argv)

    base = args.core.rstrip("/")
    url = f"{base}/ui/hc/life/{args.user}/human_intel"

    try:
        response = requests.get(url, params={"days": args.days}, timeout=6)
    except requests.RequestException as exc:  # pragma: no cover - network
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(f"GET {url}?days={args.days} -> HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        print(response.text)
        return 0 if response.ok else 1

    _print(payload)
    return 0 if response.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
