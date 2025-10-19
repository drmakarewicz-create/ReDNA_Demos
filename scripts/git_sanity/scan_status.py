#!/usr/bin/env python3
"""Scan the repository for git status noise and persist a concise report."""

from __future__ import annotations

import collections
import datetime as _dt
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = REPO_ROOT / "docs" / "ops"
REPORT_PATH = OPS_DIR / "GIT_STATUS_REPORT.md"


def run_git_status() -> list[str]:
    """Return porcelain git status entries, one per path."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        print("Failed to execute git status", file=sys.stderr)
        raise SystemExit(exc.returncode)

    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        entry = line[3:]
        if " -> " in entry:
            # Handle renames; we care about the destination path in the noise report.
            entry = entry.split(" -> ", 1)[1]
        paths.append(entry.strip())
    return paths


def top_prefixes(paths: Iterable[str], limit: int = 30) -> list[tuple[str, int]]:
    """Group paths by their first three components to spotlight noisy areas."""
    counter: collections.Counter[str] = collections.Counter()
    for path in paths:
        parts = Path(path).parts
        prefix = "/".join(parts[: min(3, len(parts))]) if parts else "."
        counter[prefix] += 1
    return counter.most_common(limit)


def du_for_directories(directories: Iterable[Path], limit: int = 20) -> list[tuple[str, str]]:
    """Return disk usage (human readable) for the supplied directories."""
    dirs = [d for d in directories if d.exists()]
    if not dirs:
        return []

    try:
        proc = subprocess.run(
            ["du", "-sk"] + [str(d) for d in dirs],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        print("Failed to compute disk usage for telemetry directories", file=sys.stderr)
        raise SystemExit(exc.returncode)

    usage: list[tuple[int, str]] = []
    for line in proc.stdout.splitlines():
        size_kb, path = line.split("\t", 1)
        try:
            size = int(size_kb)
        except ValueError:
            continue
        usage.append((size, os.path.relpath(path, REPO_ROOT)))

    usage.sort(reverse=True, key=lambda item: item[0])
    top_usage = usage[:limit]
    return [
        (path, f"{size // 1024:,} MB" if size >= 1024 else f"{size} KB")
        for size, path in top_usage
    ]


def build_report(paths: list[str]) -> str:
    total = len(paths)
    prefixes = top_prefixes(paths)
    directories = {Path(path).parent for path in paths}
    du_entries = du_for_directories(directories)
    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        "# Git Status Report",
        "",
        f"- Generated: {timestamp}",
        f"- Total tracked/untracked entries: {total}",
        "",
        "## Top Noisy Paths (≤ 3 levels)",
    ]

    if prefixes:
        report_lines.append("| Rank | Prefix | Count |")
        report_lines.append("| --- | --- | --- |")
        for idx, (prefix, count) in enumerate(prefixes, start=1):
            report_lines.append(f"| {idx} | `{prefix}` | {count} |")
    else:
        report_lines.append("_No active changes detected._")

    report_lines.extend(["", "## Disk Usage Hotspots"])
    if du_entries:
        report_lines.append("| Rank | Directory | Size |")
        report_lines.append("| --- | --- | --- |")
        for idx, (path, size) in enumerate(du_entries, start=1):
            report_lines.append(f"| {idx} | `{path}` | {size} |")
    else:
        report_lines.append("_No directories to report._")

    report_lines.append("")
    return "\n".join(report_lines)


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    paths = run_git_status()
    report = build_report(paths)

    print(report)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
