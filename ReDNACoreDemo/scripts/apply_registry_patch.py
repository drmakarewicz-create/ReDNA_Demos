#!/usr/bin/env python3
"""
Apply a patch of new containers to the registry.

Usage:
  python3 apply_registry_patch.py --registry dna_registry.json --patch pilot_patch.json --out dna_registry.json
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter


def apply_patch(registry_path: Path, patch_path: Path, output_path: Path):
    """Apply patch to registry."""
    # Load existing registry
    with open(registry_path) as f:
        registry = json.load(f)

    # Load patch
    with open(patch_path) as f:
        patch = json.load(f)

    existing_ids = {c["id"] for c in registry["containers"]}

    # Add new containers (skip duplicates)
    added_count = 0
    for container in patch.get("containers", []):
        if container["id"] not in existing_ids:
            registry["containers"].append(container)
            added_count += 1

    # Sort containers by path for deterministic output
    registry["containers"].sort(key=lambda c: c["path"])

    # Update metadata
    registry["metadata"]["total_containers"] = len(registry["containers"])
    registry["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Update namespace counts
    namespace_counts = Counter(c["namespace"] for c in registry["containers"])
    registry["metadata"]["namespace_counts"] = dict(namespace_counts)

    # Write output
    with open(output_path, 'w') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"✅ Applied patch: +{added_count} containers")
    print(f"   Total containers: {registry['metadata']['total_containers']}")


def main():
    parser = argparse.ArgumentParser(description="Apply container patch to registry")
    parser.add_argument("--registry", required=True, help="Path to dna_registry.json")
    parser.add_argument("--patch", required=True, help="Path to patch JSON")
    parser.add_argument("--out", required=True, help="Output path")
    args = parser.parse_args()

    apply_patch(Path(args.registry), Path(args.patch), Path(args.out))


if __name__ == "__main__":
    main()
