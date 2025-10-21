#!/usr/bin/env python3
"""
CLI tool for recomputing RR values using reference population (Phase 10.2).

Usage:
    python tools/recompute_rr.py --user ai_ready_probe
    python tools/recompute_rr.py --all --limit 10
    python tools/recompute_rr.py --all --dry-run

When RR_PREFER_REFERENCE_OVER_SCORE=true:
- Traits with UCN will use reference population
- Legacy rr_score archived in rr_meta.legacy_rr_score
- Method tracked in rr_meta.method
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ReDNACoreDemo.core.graph.normalize_egress import normalize_trait_dict


def get_users_dir() -> Path:
    """Get the users data directory."""
    users_dir_env = os.getenv("USERS_DIR")
    if users_dir_env:
        return Path(users_dir_env)

    # Default to data/users relative to project root
    return project_root / "data" / "users"


def recompute_user_rr(user_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Recompute RR for all traits of a single user.

    Args:
        user_id: User identifier
        dry_run: If True, preview changes without writing

    Returns:
        Dict with statistics
    """
    users_dir = get_users_dir()
    user_dir = users_dir / user_id
    resolved_path = user_dir / "resolved.json"

    if not resolved_path.exists():
        raise FileNotFoundError(f"User {user_id} not found (no resolved.json)")

    # Load resolved.json
    with open(resolved_path, 'r') as f:
        resolved = json.load(f)

    traits_processed = 0
    traits_updated = 0
    traits_using_reference = 0
    traits_using_legacy = 0
    changes = []

    # Process each trait
    updated_resolved = {}
    for trait_id, trait_data in resolved.items():
        traits_processed += 1

        if not isinstance(trait_data, dict):
            # Skip non-dict values
            updated_resolved[trait_id] = trait_data
            continue

        # Build trait dict for normalization
        trait_dict = {
            "trait_id": trait_id,
            **trait_data
        }

        # Normalize using reference preference logic
        normalized = normalize_trait_dict(trait_dict, user_id)

        # Check if RR changed
        old_rr = trait_data.get("rr")
        new_rr = normalized.get("rr")

        if old_rr != new_rr:
            traits_updated += 1
            changes.append({
                "trait_id": trait_id,
                "old_rr": old_rr,
                "new_rr": new_rr,
                "method": normalized.get("rr_meta", {}).get("method")
            })

        # Track method used
        method = normalized.get("rr_meta", {}).get("method")
        if method == "reference":
            traits_using_reference += 1
        elif method in ["legacy_score", "curiosity_inverse"]:
            traits_using_legacy += 1

        # Update trait data (remove trait_id key we added)
        normalized_data = {k: v for k, v in normalized.items() if k != "trait_id"}
        updated_resolved[trait_id] = normalized_data

    # Write updated resolved.json (unless dry run)
    if not dry_run:
        # Backup original
        backup_path = user_dir / "resolved.json.bak"
        with open(backup_path, 'w') as f:
            json.dump(resolved, f, indent=2)

        # Write updated
        with open(resolved_path, 'w') as f:
            json.dump(updated_resolved, f, indent=2)

        print(f"✓ Backup saved: {backup_path}")
        print(f"✓ Updated: {resolved_path}")

    return {
        "user_id": user_id,
        "traits_processed": traits_processed,
        "traits_updated": traits_updated,
        "traits_using_reference": traits_using_reference,
        "traits_using_legacy": traits_using_legacy,
        "changes": changes,
        "dry_run": dry_run
    }


def recompute_all_users(limit: Optional[int] = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Batch recompute RR for all users.

    Args:
        limit: Maximum users to process (for testing)
        dry_run: If True, preview changes without writing

    Returns:
        Dict with batch statistics
    """
    users_dir = get_users_dir()

    if not users_dir.exists():
        raise FileNotFoundError(f"Users directory not found: {users_dir}")

    # Find all user directories
    user_dirs = [
        d for d in users_dir.iterdir()
        if d.is_dir() and (d / "resolved.json").exists()
    ]

    if limit:
        user_dirs = user_dirs[:limit]

    print(f"Processing {len(user_dirs)} users...")

    users_processed = 0
    total_traits_updated = 0
    total_traits_using_reference = 0
    errors = []
    user_results = []

    for user_dir in user_dirs:
        user_id = user_dir.name
        try:
            result = recompute_user_rr(user_id, dry_run=dry_run)
            user_results.append(result)
            users_processed += 1
            total_traits_updated += result["traits_updated"]
            total_traits_using_reference += result["traits_using_reference"]

            print(f"  {user_id}: {result['traits_updated']} updated, {result['traits_using_reference']} using reference")

        except Exception as e:
            error_msg = f"{user_id}: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ {error_msg}")

    return {
        "users_processed": users_processed,
        "total_traits_updated": total_traits_updated,
        "total_traits_using_reference": total_traits_using_reference,
        "errors": errors,
        "user_results": user_results,
        "dry_run": dry_run
    }


def main():
    parser = argparse.ArgumentParser(
        description="Recompute RR values using reference population"
    )

    parser.add_argument(
        "--user",
        help="User ID to recompute (single user mode)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Recompute for all users (batch mode)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum users to process (batch mode only)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files"
    )

    parser.add_argument(
        "--show-changes",
        action="store_true",
        help="Show detailed RR changes"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.user and not args.all:
        parser.error("Must specify either --user <id> or --all")

    if args.user and args.all:
        parser.error("Cannot use both --user and --all")

    if args.limit and not args.all:
        parser.error("--limit only works with --all")

    # Display configuration
    from ReDNACoreDemo.core.graph.normalize_egress import (
        RR_PREFER_REFERENCE_OVER_SCORE,
        REFERENCE_POP_ENABLED,
        REFERENCE_POP_SOURCE
    )

    print("=" * 60)
    print("RR Recomputation Tool (Phase 10.2)")
    print("=" * 60)
    print(f"RR_PREFER_REFERENCE_OVER_SCORE: {RR_PREFER_REFERENCE_OVER_SCORE}")
    print(f"REFERENCE_POP_ENABLED: {REFERENCE_POP_ENABLED}")
    print(f"REFERENCE_POP_SOURCE: {REFERENCE_POP_SOURCE}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)
    print()

    try:
        if args.user:
            # Single user mode
            result = recompute_user_rr(args.user, dry_run=args.dry_run)

            print(f"\nResults for {args.user}:")
            print(f"  Traits processed: {result['traits_processed']}")
            print(f"  Traits updated: {result['traits_updated']}")
            print(f"  Using reference: {result['traits_using_reference']}")
            print(f"  Using legacy: {result['traits_using_legacy']}")

            if args.show_changes and result['changes']:
                print(f"\nDetailed changes:")
                for change in result['changes']:
                    print(f"  {change['trait_id']}:")
                    print(f"    Old RR: {change['old_rr']}")
                    print(f"    New RR: {change['new_rr']}")
                    print(f"    Method: {change['method']}")

        else:
            # Batch mode
            result = recompute_all_users(limit=args.limit, dry_run=args.dry_run)

            print(f"\nBatch Results:")
            print(f"  Users processed: {result['users_processed']}")
            print(f"  Total traits updated: {result['total_traits_updated']}")
            print(f"  Total using reference: {result['total_traits_using_reference']}")

            if result['errors']:
                print(f"\nErrors ({len(result['errors'])}):")
                for error in result['errors']:
                    print(f"  ✗ {error}")

        print()
        if args.dry_run:
            print("✓ Dry run complete (no files modified)")
        else:
            print("✓ Recomputation complete")

        sys.exit(0)

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
