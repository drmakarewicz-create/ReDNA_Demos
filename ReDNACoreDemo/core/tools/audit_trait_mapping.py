#!/usr/bin/env python3
"""
Trait ID Mapping Audit Tool

Scans user evidence files and identifies trait_ids that weren't mapped
to canonical IDs. Helps detect mapping drift and missing entries in
trait_id_map.json.

Usage:
    python audit_trait_mapping.py <user_id> [data_root]

Example:
    python ReDNACoreDemo/core/tools/audit_trait_mapping.py USER123
    python ReDNACoreDemo/core/tools/audit_trait_mapping.py USER123 /path/to/data
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from collections import Counter
from typing import Optional


def to_canonical_safe(trait_id: str) -> str:
    """
    Safely attempt to canonicalize a trait_id.

    Returns the canonical ID if mapping exists, otherwise returns the input.
    """
    try:
        # Try importing the mapper
        from ReDNACoreDemo.core.traits.trait_id_mapper import to_canonical
        return to_canonical(trait_id)
    except ImportError:
        # If mapper doesn't exist yet, we can't map
        return trait_id
    except Exception:
        # Any other error, return as-is
        return trait_id


def audit_user(user_id: str, data_root: Path) -> tuple[Counter, list[Path]]:
    """
    Audit a user's evidence files for unmapped trait_ids.

    Args:
        user_id: User identifier
        data_root: Root data directory

    Returns:
        Tuple of (unmapped_counts, checked_files)
    """
    user_dir = data_root / "users" / user_id

    # Check multiple possible evidence locations
    evidence_locations = [
        user_dir / "evidence.json",  # Single file
        user_dir / "evidence",       # Directory of files
        user_dir / "checkpoints" / "events",  # Event files
    ]

    unmapped_counts = Counter()
    checked_files = []

    for location in evidence_locations:
        if not location.exists():
            continue

        # Handle single file
        if location.is_file():
            checked_files.append(location)
            _scan_file(location, unmapped_counts)

        # Handle directory
        elif location.is_dir():
            for file_path in location.glob("*.json"):
                checked_files.append(file_path)
                _scan_file(file_path, unmapped_counts)

    return unmapped_counts, checked_files


def _scan_file(file_path: Path, unmapped_counts: Counter) -> None:
    """Scan a single JSON file for unmapped trait_ids."""
    try:
        data = json.loads(file_path.read_text())
    except Exception:
        return

    # Handle different evidence file formats
    evidence_items = []

    if isinstance(data, list):
        evidence_items = data
    elif isinstance(data, dict):
        # Could be {"items": [...]} or {"evidence": [...]}
        evidence_items = data.get("items", []) or data.get("evidence", [])
        if not evidence_items and "trait_id" in data:
            # Single evidence object
            evidence_items = [data]

    for ev in evidence_items:
        if not isinstance(ev, dict):
            continue

        trait_id = ev.get("trait_id")
        if not trait_id:
            continue

        canonical = to_canonical_safe(trait_id)

        # If mapping worked, canonical will be different from input
        if trait_id != canonical:
            # Successfully mapped, skip
            continue

        # Unmapped - check if it looks like a legacy ID
        if (trait_id.startswith("attributes.") or
            trait_id.startswith("preferences.") or
            trait_id.startswith("interests.") or
            trait_id.startswith("personality.")):
            unmapped_counts[trait_id] += 1


def audit_all_users(data_root: Path, limit: Optional[int] = None) -> dict[str, Counter]:
    """
    Audit all users in the data directory.

    Args:
        data_root: Root data directory
        limit: Optional limit on number of users to scan

    Returns:
        Dict mapping user_id to unmapped trait counts
    """
    users_dir = data_root / "users"
    if not users_dir.exists():
        return {}

    results = {}
    count = 0

    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue
        if user_dir.name.startswith(".") or user_dir.name.startswith("_"):
            continue

        user_id = user_dir.name
        unmapped, _ = audit_user(user_id, data_root)

        if unmapped:
            results[user_id] = unmapped

        count += 1
        if limit and count >= limit:
            break

    return results


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse arguments
    user_id = sys.argv[1]

    if user_id == "--all":
        # Audit all users
        data_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data")
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else None

        print(f"Auditing all users in {data_root}...")
        results = audit_all_users(data_root, limit)

        if not results:
            print("✅ No unmapped trait_ids found in any users.")
            return

        print(f"\n⚠️ Found unmapped trait_ids in {len(results)} users:\n")

        # Collect global counts
        global_counts = Counter()
        for unmapped in results.values():
            global_counts.update(unmapped)

        print("Most common unmapped trait_ids:")
        for trait_id, count in global_counts.most_common(20):
            print(f"  {trait_id:<50}  ({count} total occurrences)")

        print(f"\n👉 Add these to core/traits/trait_id_map.json")
        return

    # Single user audit
    data_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data")

    if not (data_root / "users" / user_id).exists():
        print(f"❌ User not found: {user_id}")
        print(f"   Looked in: {data_root / 'users' / user_id}")
        sys.exit(1)

    print(f"Auditing trait_id mappings for user: {user_id}")
    print(f"Data root: {data_root}\n")

    unmapped, checked_files = audit_user(user_id, data_root)

    print(f"Checked {len(checked_files)} files")

    if not unmapped:
        print("✅ No unmapped trait_ids found.")
        return

    print(f"\n⚠️ Found {len(unmapped)} unmapped trait_ids:\n")

    for trait_id, count in unmapped.most_common():
        print(f"  {trait_id:<50}  ({count} occurrences)")

    print(f"\n👉 Add these to core/traits/trait_id_map.json")
    print(f"   Example:")

    # Show example mapping for first unmapped ID
    first_id = unmapped.most_common(1)[0][0]
    print(f'   "{first_id}": "PaDNA.CategoryDNA.TraitName"')


if __name__ == "__main__":
    main()
