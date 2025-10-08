#!/usr/bin/env python3
"""
Align v1 container status to prototype.

This script converts all v1 containers from status=stable to status=prototype,
following the convention that v1 containers represent early versions and should
be marked as prototypes until they reach maturity (v2+).

Usage:
    python3 align_v1_status.py <input_registry.json> <output_registry.json>
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def align_v1_status(registry_path: str, output_path: str) -> dict:
    """
    Align v1 container status to prototype.

    Args:
        registry_path: Path to input DNA registry JSON
        output_path: Path to write fixed registry

    Returns:
        Dict with remediation statistics
    """
    # Load registry
    with open(registry_path) as f:
        registry = json.load(f)

    stats = {
        'total_containers': len(registry['containers']),
        'v1_containers': 0,
        'v1_non_prototype': 0,
        'fixed': 0,
        'already_aligned': 0,
        'fixes': []
    }

    # Process each container
    for container in registry['containers']:
        if container['id'].endswith('.v1'):
            stats['v1_containers'] += 1

            if container.get('status') != 'prototype':
                # Non-prototype v1 - fix it
                old_status = container.get('status', 'unknown')
                stats['v1_non_prototype'] += 1
                container['status'] = 'prototype'
                container['updated_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

                # Add changelog entry
                if 'changelog' not in container:
                    container['changelog'] = []

                container['changelog'].append({
                    'version': container['version'],
                    'timestamp': container['updated_at'],
                    'changes': f'Auto-remediation: Changed status from {old_status} to prototype (v1 convention)',
                    'author': 'align_v1_status.py'
                })

                stats['fixed'] += 1
                stats['fixes'].append({
                    'id': container['id'],
                    'path': container['path'],
                    'namespace': container['namespace'],
                    'old_status': old_status
                })
            else:
                stats['already_aligned'] += 1

    # Write fixed registry
    with open(output_path, 'w') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    return stats


def main():
    if len(sys.argv) != 3:
        print("Usage: align_v1_status.py <input_registry.json> <output_registry.json>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    if not Path(input_path).exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"🔧 Aligning v1 container status in {input_path}...")
    stats = align_v1_status(input_path, output_path)

    print(f"\n✅ Remediation Complete")
    print(f"  Total containers: {stats['total_containers']}")
    print(f"  V1 containers: {stats['v1_containers']}")
    print(f"  V1 non-prototype: {stats['v1_non_prototype']}")
    print(f"  Fixed: {stats['fixed']}")
    print(f"  Already aligned: {stats['already_aligned']}")
    print(f"\n📝 Output written to: {output_path}")

    if stats['fixes']:
        print(f"\nFixed containers (first 10):")
        for fix in stats['fixes'][:10]:
            print(f"  - {fix['id']} ({fix['old_status']} → prototype)")
        if len(stats['fixes']) > 10:
            print(f"  ... and {len(stats['fixes']) - 10} more")

    print(f"\n🎯 Expected linter warning reduction: {stats['fixed']} warnings")


if __name__ == '__main__':
    main()
