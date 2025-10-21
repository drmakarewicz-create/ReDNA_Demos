"""
Utilities for reading and parsing the ReDNA workspace manifest.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import webbrowser
from pathlib import Path
from typing import Dict, List, Union

DEFAULT_MANIFEST_PATH = Path("docs/ReDNA_Workspace_Manifest.md")
REQUIRED_HEADINGS = [
    "# ReDNA Workspace Manifest (v1.0)",
    "## 1. Project Overview",
    "## 2. Services & Ports",
    "## 3. Key Directories",
    "## 4. Hierarchy Model",
    "## 5. Data Pipeline",
    "## 6. API Surface",
    "## 7. AI Prompt Files",
    "## 8. Phase & Version History",
    "## 9. Flags / Environment Variables",
    "## 10. Tests & Coverage",
    "## 11. Known TODOs / LEGACY Markers",
    "## 12. Recent Changelogs & Key Docs",
]


def read_manifest(path: Union[str, Path] = "docs/ReDNA_Workspace_Manifest.md") -> Dict[str, object]:
    """Load manifest text from disk."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {"error": f"Manifest not found at {manifest_path.resolve()}"}
    return {"text": manifest_path.read_text(encoding="utf-8")}


def extract_services_table(md_text: str) -> Dict[str, object]:
    """
    Extract the first markdown table that appears beneath the
    `## 2. Services & Ports` heading.
    """
    sections = re.split(r"^## 2\. Services & Ports\s*$", md_text, flags=re.M)
    if len(sections) < 2:
        return {"error": "Section not found: ## 2. Services & Ports"}

    tail = sections[1].strip()
    match = re.search(
        r"^\|.*\|\s*\n^\|[-| ]+\|\s*\n(?:^\|.*\|\s*\n)+",
        tail,
        flags=re.M,
    )
    if not match:
        return {"error": "No table found in Services & Ports"}

    table = match.group(0).strip()
    rows = [row.strip() for row in table.splitlines()]
    if len(rows) < 3:
        return {"error": "Services table does not contain data rows"}

    headers = [header.strip() for header in rows[0].strip("|").split("|")]
    data: List[Dict[str, str]] = []
    for row in rows[2:]:
        columns = [col.strip() for col in row.strip("|").split("|")]
        if len(columns) != len(headers):
            continue
        data.append(dict(zip(headers, columns)))

    return {"headers": headers, "rows": data, "raw_table": table}


def open_manifest(path: Union[str, Path] = DEFAULT_MANIFEST_PATH) -> int:
    """Attempt to open the manifest in the user's default viewer."""
    manifest_path = Path(path).resolve()
    print(f"Opening: {manifest_path}")
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 1
    try:
        opened = webbrowser.open(f"file://{manifest_path}")
        if not opened:
            print(f"Viewer did not report success. Path: {manifest_path}")
            return 0
    except Exception as exc:  # pragma: no cover - best effort
        print(f"Open failed: {exc}\nPath: {manifest_path}")
        return 0
    return 0


def check_manifest(path: Union[str, Path] = DEFAULT_MANIFEST_PATH) -> int:
    """Validate that the manifest includes the expected headings."""
    result = read_manifest(path)
    if "error" in result:
        print(result["error"])
        return 1

    text = str(result["text"])
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    if missing:
        print("WARN: Missing expected headings:")
        for heading in missing:
            print(f" - {heading}")
        return 1

    print("OK: All expected headings present.")
    return 0


def dump_services(path: Union[str, Path] = DEFAULT_MANIFEST_PATH) -> int:
    """Print the services & ports table as JSON."""
    manifest = read_manifest(path)
    if "error" in manifest:
        print(manifest["error"])
        return 1

    parsed = extract_services_table(str(manifest["text"]))
    if "error" in parsed:
        print(parsed["error"])
        return 1

    print(json.dumps(parsed.get("rows", []), indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workspace manifest utilities.")
    sub = parser.add_subparsers(dest="command")

    open_cmd = sub.add_parser("open", help="Open the manifest in the default viewer.")
    open_cmd.add_argument("path", nargs="?", default=str(DEFAULT_MANIFEST_PATH))

    check_cmd = sub.add_parser("check", help="Validate standard manifest headings.")
    check_cmd.add_argument("path", nargs="?", default=str(DEFAULT_MANIFEST_PATH))

    ports_cmd = sub.add_parser("ports", help="Print the Services & Ports table as JSON.")
    ports_cmd.add_argument("path", nargs="?", default=str(DEFAULT_MANIFEST_PATH))

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "open":
        return open_manifest(args.path)
    if args.command == "check":
        return check_manifest(args.path)
    if args.command == "ports":
        return dump_services(args.path)

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
def preferred_health_user(default: str = "ai_ready_probe") -> str:
    """Return the default health user id, favoring env override."""
    return os.environ.get("REDNA_HEALTH_USER", default)
