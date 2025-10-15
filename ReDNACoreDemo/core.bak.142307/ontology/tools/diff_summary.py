#!/usr/bin/env python3
"""Compare two registries and show diff."""
import json
import sys
from pathlib import Path
from collections import Counter


def main(old_path, new_path):
    with open(old_path) as f:
        old_data = json.load(f)
    with open(new_path) as f:
        new_data = json.load(f)

    old_ids = {c["id"] for c in old_data.get("containers", [])}
    new_ids = {c["id"] for c in new_data.get("containers", [])}

    added = new_ids - old_ids
    removed = old_ids - new_ids

    print(f"Diff Summary: {old_path} → {new_path}")
    print(f"Added: {len(added)} containers")
    print(f"Removed: {len(removed)} containers")
    print(f"Net change: {len(new_ids) - len(old_ids):+d}")

    if added:
        namespaces = Counter(id.split(".")[0] for id in added)
        print("\nAdded by namespace:")
        for ns, count in namespaces.most_common():
            print(f"  {ns}: +{count}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
