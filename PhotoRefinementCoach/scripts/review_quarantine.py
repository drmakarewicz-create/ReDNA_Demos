#!/usr/bin/env python3
"""
Quarantine Review Tool

CLI tool for reviewing, categorizing, and promoting quarantined trait paths.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quarantine_tracker import QuarantineTracker


def main():
    parser = argparse.ArgumentParser(
        description="Review and manage quarantined trait paths",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View statistics
  python review_quarantine.py stats

  # List all pending paths
  python review_quarantine.py list

  # List pending paths by category
  python review_quarantine.py list --category Behavioral

  # Export pending paths for review
  python review_quarantine.py export review.json

  # Export by category
  python review_quarantine.py export review_behavioral.json --category Behavioral

  # Import reviewed decisions
  python review_quarantine.py import review.json

  # Mark a specific path
  python review_quarantine.py mark "BehavioralDNA.Posture" --status mapped --mapping "PaDNA.MovementDNA.Posture" --notes "Mapped to movement"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Stats command
    subparsers.add_parser("stats", help="Show quarantine statistics")

    # List command
    list_parser = subparsers.add_parser("list", help="List pending quarantined paths")
    list_parser.add_argument("--category", help="Filter by category")
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum paths to show")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export pending paths for review")
    export_parser.add_argument("output", help="Output file path")
    export_parser.add_argument("--category", help="Filter by category")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import review decisions")
    import_parser.add_argument("input", help="Review file with decisions")

    # Mark command
    mark_parser = subparsers.add_parser("mark", help="Mark a specific path")
    mark_parser.add_argument("path", help="Path to mark")
    mark_parser.add_argument("--status", required=True, choices=["mapped", "promoted", "rejected", "pending"], help="New status")
    mark_parser.add_argument("--mapping", help="Suggested canonical path mapping")
    mark_parser.add_argument("--notes", help="Notes about the decision")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear resolved paths from registry")
    clear_parser.add_argument("--confirm", action="store_true", help="Confirm the action")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    tracker = QuarantineTracker()

    if args.command == "stats":
        return cmd_stats(tracker)
    elif args.command == "list":
        return cmd_list(tracker, args.category, args.limit)
    elif args.command == "export":
        return cmd_export(tracker, args.output, args.category)
    elif args.command == "import":
        return cmd_import(tracker, args.input)
    elif args.command == "mark":
        return cmd_mark(tracker, args.path, args.status, args.mapping, args.notes)
    elif args.command == "clear":
        return cmd_clear(tracker, args.confirm)

    return 0


def cmd_stats(tracker: QuarantineTracker) -> int:
    """Show quarantine statistics."""
    stats = tracker.data.get("statistics", {})

    print("\n=== QUARANTINE STATISTICS ===\n")
    print(f"Total unique paths: {stats.get('total_unique_paths', 0)}")
    print(f"Total occurrences:  {stats.get('total_occurrences', 0)}")

    print("\n--- Paths by Category ---")
    for category, count in sorted(stats.get("paths_by_category", {}).items()):
        print(f"  {category:15} {count:>5}")

    print("\n--- Paths by Status ---")
    for status, count in sorted(stats.get("paths_by_status", {}).items()):
        print(f"  {status:15} {count:>5}")

    most_frequent = stats.get("most_frequent", [])
    if most_frequent:
        print("\n--- Top 10 Most Frequent ---")
        for i, item in enumerate(most_frequent[:10], 1):
            path = item["path"]
            count = item["count"]
            category = item.get("category", "Other")
            print(f"  {i:2}. [{category:12}] {path:40} ({count} occurrences)")

    last_updated = tracker.data.get("last_updated")
    if last_updated:
        print(f"\nLast updated: {last_updated}")

    print()
    return 0


def cmd_list(tracker: QuarantineTracker, category: Optional[str], limit: int) -> int:
    """List pending quarantined paths."""
    pending = tracker.get_pending_paths(category=category)

    if not pending:
        print("No pending quarantined paths found.")
        return 0

    print(f"\n=== PENDING QUARANTINED PATHS ({len(pending)}) ===\n")

    if category:
        print(f"Filtered by category: {category}\n")

    for i, path_data in enumerate(pending[:limit], 1):
        path = path_data["path"]
        cat = path_data.get("category", "Other")
        count = path_data.get("occurrence_count", 0)
        examples = path_data.get("example_values", [])

        print(f"{i:3}. [{cat:12}] {path}")
        print(f"     Occurrences: {count}")
        if examples:
            example = examples[0]
            if len(example) > 60:
                example = example[:57] + "..."
            print(f"     Example: {example}")
        print()

    if len(pending) > limit:
        print(f"... and {len(pending) - limit} more (use --limit to show more)")

    return 0


def cmd_export(tracker: QuarantineTracker, output: str, category: Optional[str]) -> int:
    """Export pending paths for review."""
    output_path = Path(output)

    try:
        tracker.export_for_review(output_path, category=category)
        print(f"✅ Exported pending paths to: {output_path}")

        # Show preview
        with output_path.open("r") as f:
            data = json.load(f)

        print(f"\nExported {data['total_pending_paths']} paths for review")
        if category:
            print(f"Category filter: {category}")

        print("\n📝 Next steps:")
        print(f"   1. Open {output_path} in your editor")
        print("   2. Review each path and update the 'decision' section:")
        print("      - status: mapped | promoted | rejected")
        print("      - suggested_mapping: (if status=mapped)")
        print("      - notes: explanation")
        print(f"   3. Run: python review_quarantine.py import {output}")

        return 0
    except Exception as exc:
        print(f"❌ Failed to export: {exc}")
        return 1


def cmd_import(tracker: QuarantineTracker, input_file: str) -> int:
    """Import review decisions."""
    input_path = Path(input_file)

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return 1

    try:
        count = tracker.import_review_decisions(input_path)
        print(f"✅ Imported decisions for {count} paths")

        # Show updated stats
        stats = tracker.data.get("statistics", {})
        by_status = stats.get("paths_by_status", {})

        print("\nUpdated status counts:")
        for status, count in sorted(by_status.items()):
            print(f"  {status:12} {count:>5}")

        return 0
    except Exception as exc:
        print(f"❌ Failed to import: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_mark(
    tracker: QuarantineTracker,
    path: str,
    status: str,
    mapping: Optional[str],
    notes: Optional[str]
) -> int:
    """Mark a specific path."""
    success = tracker.mark_path_status(path, status, notes, mapping)

    if success:
        print(f"✅ Updated path: {path}")
        print(f"   Status: {status}")
        if mapping:
            print(f"   Mapping: {mapping}")
        if notes:
            print(f"   Notes: {notes}")
        return 0
    else:
        print(f"❌ Path not found: {path}")
        return 1


def cmd_clear(tracker: QuarantineTracker, confirm: bool) -> int:
    """Clear resolved paths from registry."""
    if not confirm:
        print("⚠️  This will remove all mapped, promoted, and rejected paths from the registry.")
        print("   To confirm, run with --confirm")
        return 1

    paths = tracker.data.get("quarantined_paths", {})
    to_remove = [
        path for path, data in paths.items()
        if data.get("status") in ["mapped", "promoted", "rejected"]
    ]

    if not to_remove:
        print("No resolved paths to clear.")
        return 0

    for path in to_remove:
        del paths[path]

    tracker._update_statistics()
    tracker._save_registry()

    print(f"✅ Cleared {len(to_remove)} resolved paths from registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
