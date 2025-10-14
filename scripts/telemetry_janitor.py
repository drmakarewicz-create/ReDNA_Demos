#!/usr/bin/env python3
"""
Telemetry Janitor
=================

Cleans telemetry JSONL logs under prompts/insights so downstream learning
pipelines remain resilient. Supports dry-run inspection, optional backups,
and in-place fixes with light schema defaulting.

Typical usage:
    python scripts/telemetry_janitor.py --dry-run
    python scripts/telemetry_janitor.py --backup --fix
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSIGHTS_DIR = REPO_ROOT / "prompts" / "insights"
REQUIRED_KEYS = ("ts", "coach_id", "kind")
DEFAULT_KIND = "telemetry"
DEFAULT_COACH_ID = "unknown"


@dataclass
class FileSummary:
    """Aggregated statistics for a single telemetry file cleanup."""

    path: Path
    lines_total: int = 0
    lines_valid: int = 0
    lines_fixed: int = 0
    inserted_defaults: int = 0
    defaults_per_field: Dict[str, int] = field(default_factory=lambda: {key: 0 for key in REQUIRED_KEYS})
    errors_removed: int = 0
    bom_stripped: bool = False
    backup_created: bool = False

    def as_row(self) -> Tuple[str, int, int, int, int, int]:
        return (
            self.path.name,
            self.lines_total,
            self.lines_valid,
            self.lines_fixed,
            self.inserted_defaults,
            self.errors_removed,
        )


def discover_files(insights_dir: Path) -> List[Path]:
    """Find telemetry JSONL files under the insights directory."""
    if not insights_dir.exists():
        return []
    return sorted(p for p in insights_dir.glob("*.jsonl") if p.is_file())


def load_lines(path: Path) -> Tuple[List[str], bool]:
    """
    Read the raw file content, returning lines and whether a BOM was stripped.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    bom_stripped = False
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
        bom_stripped = True
    # Preserve EOF-newline semantics by splitlines; we don't keep trailing empty item
    lines = text.splitlines()
    return lines, bom_stripped


def derive_coach_id(path: Path) -> str:
    """Infer coach_id from filename, falling back to DEFAULT_COACH_ID."""
    stem = path.stem.strip()
    return stem or DEFAULT_COACH_ID


def apply_schema_defaults(entry: Dict, coach_id: str, now_iso: str, summary: FileSummary) -> bool:
    """
    Ensure required keys exist. Returns True if the entry was mutated.
    """
    changed = False

    ts = entry.get("ts")
    if not isinstance(ts, str) or not ts.strip():
        entry["ts"] = now_iso
        summary.defaults_per_field["ts"] += 1
        summary.inserted_defaults += 1
        changed = True

    kind = entry.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        entry["kind"] = DEFAULT_KIND
        summary.defaults_per_field["kind"] += 1
        summary.inserted_defaults += 1
        changed = True

    cid = entry.get("coach_id")
    if not isinstance(cid, str) or not cid.strip():
        entry["coach_id"] = coach_id or DEFAULT_COACH_ID
        summary.defaults_per_field["coach_id"] += 1
        summary.inserted_defaults += 1
        changed = True

    return changed


def clean_file(path: Path, fix: bool, backup: bool, now_iso: str) -> FileSummary:
    """
    Clean an individual telemetry JSONL file.
    """
    summary = FileSummary(path=path)
    raw_lines, bom_stripped = load_lines(path)
    summary.bom_stripped = bom_stripped

    coach_id_hint = derive_coach_id(path)

    cleaned_entries: List[str] = []

    for raw_line in raw_lines:
        summary.lines_total += 1
        line = raw_line.lstrip("\ufeff").strip()
        if not line:
            summary.errors_removed += 1
            continue

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            summary.errors_removed += 1
            continue

        if not isinstance(parsed, dict):
            summary.errors_removed += 1
            continue

        # Apply schema-lite defaults
        mutated = apply_schema_defaults(parsed, coach_id_hint, now_iso, summary)

        if mutated or line != json.dumps(parsed, ensure_ascii=False):
            summary.lines_fixed += 1

        cleaned_entries.append(json.dumps(parsed, ensure_ascii=False))
        summary.lines_valid += 1

    # If we are fixing and modifications are required, persist changes.
    if fix:
        output_text = "\n".join(cleaned_entries)
        if cleaned_entries:
            output_text += "\n"

        existing_text = path.read_text(encoding="utf-8", errors="replace")
        desired_text = output_text

        if existing_text != desired_text:
            if backup:
                backup_path = path.with_suffix(path.suffix + ".bak")
                if not backup_path.exists():
                    shutil.copy2(path, backup_path)
                    summary.backup_created = True
            path.write_text(desired_text, encoding="utf-8")

    return summary


def format_summary_table(summaries: Iterable[FileSummary]) -> str:
    """Format a summary table for CLI output."""
    headers = ["file", "lines_total", "lines_valid", "lines_fixed", "defaults_inserted", "errors_removed"]
    rows = [summ.as_row() for summ in summaries]
    widths = [max(len(str(row[idx])) for row in ([headers] + rows)) for idx in range(len(headers))]

    def format_row(row: Iterable) -> str:
        return "  ".join(str(cell).ljust(widths[idx]) for idx, cell in enumerate(row))

    lines = [format_row(headers)]
    lines.append(format_row(["-" * len(h) for h in headers]))
    for row in rows:
        lines.append(format_row(row))
    return "\n".join(lines)


def summarize_totals(summaries: Iterable[FileSummary]) -> Dict[str, int]:
    """Compute aggregate statistics across files."""
    totals = {
        "files": 0,
        "lines_total": 0,
        "lines_valid": 0,
        "lines_fixed": 0,
        "inserted_defaults": 0,
        "errors_removed": 0,
    }
    for summary in summaries:
        totals["files"] += 1
        totals["lines_total"] += summary.lines_total
        totals["lines_valid"] += summary.lines_valid
        totals["lines_fixed"] += summary.lines_fixed
        totals["inserted_defaults"] += summary.inserted_defaults
        totals["errors_removed"] += summary.errors_removed
    return totals


def run_janitor(args: argparse.Namespace) -> int:
    """Execute janitor for provided CLI arguments."""
    insights_dir = Path(args.insights_dir).expanduser().resolve()
    files = discover_files(insights_dir)

    if not files:
        print(f"ℹ️  No telemetry JSONL files found under {insights_dir}")
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    summaries: List[FileSummary] = []
    fix = bool(args.fix)
    backup = bool(args.backup)

    for path in files:
        summary = clean_file(path, fix=fix, backup=backup, now_iso=now_iso)
        summaries.append(summary)

    print(format_summary_table(summaries))

    totals = summarize_totals(summaries)
    print(
        "\nTotal: {files} files, {lines_total} lines scanned, "
        "{lines_valid} retained, {errors_removed} removed, "
        "{inserted_defaults} defaults inserted".format(**totals)
    )

    if not fix or args.dry_run:
        print("\n(No files modified; run with --fix to apply changes.)")
    else:
        touched = sum(1 for s in summaries if s.lines_total != s.lines_valid or s.lines_fixed or s.bom_stripped)
        print(f"\n✅ Cleaned telemetry logs ({touched} files touched).")

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean telemetry JSONL logs under prompts/insights.")
    parser.add_argument(
        "--insights-dir",
        default=str(DEFAULT_INSIGHTS_DIR),
        help=f"Directory containing telemetry JSONL files (default: {DEFAULT_INSIGHTS_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report issues without modifying files.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="When combined with --fix, create a .bak file before writing changes.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply cleaned output in-place.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Implicit dry-run unless explicitly fixing.
    if not args.fix:
        args.dry_run = True

    return run_janitor(args)


if __name__ == "__main__":
    sys.exit(main())
