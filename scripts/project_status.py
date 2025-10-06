#!/usr/bin/env python3
"""Generate Project Status Pack v2 (markdown + JSON)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ExplorerDev import snapshot_utils  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate project status snapshot pack.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not persist files; print the markdown preview instead.",
    )
    args = parser.parse_args()

    context = SimpleNamespace(write_protect=bool(args.dry_run))
    result = snapshot_utils.generate_project_status(
        write_context=context,
        persist=not args.dry_run,
    )

    data = result.get("data", {})
    diff = data.get("diff", {})
    json_path = result.get("json_path")
    md_path = result.get("markdown_path")

    print("Project Status Pack v2")
    print(f"Generated at: {data.get('generated_at')}")
    print(f"Write-protect: {data.get('write_protect')}")
    if json_path:
        print(f"JSON saved to: {json_path}")
    if md_path:
        print(f"Markdown saved to: {md_path}")
    if not json_path and not md_path:
        print("(dry-run; files not written)")
    print(
        "Diff → flags: {fc}, modules: {mc}, data_dirs: {dc}".format(
            fc=len(diff.get("flags_changed", [])),
            mc=len(diff.get("modules_added", [])),
            dc=len(diff.get("data_changes", [])),
        )
    )

    if args.dry_run:
        print("\n--- Markdown Preview ---\n")
        print(result.get("markdown", ""))


if __name__ == "__main__":
    main()
