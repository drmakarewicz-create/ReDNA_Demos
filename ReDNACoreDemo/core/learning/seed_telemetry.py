"""
Telemetry Seeder
================

Utility to append a minimal telemetry record to empty coach logs so the
self-improvement loop has baseline data to analyze.

Usage:
    python -m ReDNACoreDemo.core.learning.seed_telemetry head_coach chatdna_coach
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
INSIGHTS_DIR = REPO_ROOT / "prompts" / "insights"


def ensure_insights_dir() -> None:
    """Ensure the insights directory exists."""
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)


def telemetry_path(coach_id: str) -> Path:
    """Return the JSONL path for a coach."""
    sanitized = coach_id.strip()
    if not sanitized:
        raise ValueError("Coach identifier cannot be empty.")
    return INSIGHTS_DIR / f"{sanitized}.jsonl"


def has_content(path: Path) -> bool:
    """Check whether the telemetry file already contains non-empty lines."""
    if not path.exists():
        return False

    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    return True
    except FileNotFoundError:
        return False

    return False


def build_entry(coach_id: str) -> dict:
    """Construct the minimal telemetry entry."""
    now_iso = datetime.now(timezone.utc).isoformat()
    data_block = {
        "features": {},
        "hints": {},
        "outcome": {"length": 0, "sentiment": "neutral"},
    }
    return {
        "ts": now_iso,
        "coach_id": coach_id,
        "kind": "telemetry",
        "user_id": "seed_user",
        "active_coach_id": coach_id,
        "context_version": "seed:v1",
        "sentiment": "neutral",
        "tokens": 0,
        "build_ms": 0,
        "features": data_block["features"],
        "hints": data_block["hints"],
        "data": data_block,
    }


def seed_coach(coach_id: str) -> bool:
    """Append a seed entry if the telemetry file is empty."""
    ensure_insights_dir()
    path = telemetry_path(coach_id)

    if has_content(path):
        return False

    entry = build_entry(coach_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return True


def run(coach_ids: Iterable[str]) -> int:
    """Seed specified coach telemetry files."""
    seeded = 0
    skipped = 0

    for coach_id in coach_ids:
        try:
            if seed_coach(coach_id):
                print(f"✅ Seeded telemetry for '{coach_id}'")
                seeded += 1
            else:
                print(f"ℹ️  Skipped '{coach_id}' (already populated)")
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Failed to seed '{coach_id}': {exc}")
            return 1

    summary = f"Seeded {seeded} file(s)"
    if skipped:
        summary += f", skipped {skipped}"
    print(summary)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python -m ReDNACoreDemo.core.learning.seed_telemetry <coach_id> [<coach_id> ...]")
        return 1
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
