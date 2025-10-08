#!/usr/bin/env python3
"""
Fix consent flag warnings in DNA registry.

This script automatically remediates containers that are marked as sensitive
but missing the consent_required flag, ensuring compliance with privacy guidelines.

Usage:
    python3 fix_consent_flags.py <input_registry.json> <output_registry.json>
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def fix_consent_flags(registry_path: str, output_path: str) -> dict:
    """
    Fix consent flags for sensitive containers.

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
        'sensitive_containers': 0,
        'missing_consent': 0,
        'fixed': 0,
        'already_compliant': 0,
        'fixes': []
    }

    # Process each container
    for container in registry['containers']:
        if container.get('sensitive', False):
            stats['sensitive_containers'] += 1

            if not container.get('consent_required', False):
                # Missing consent flag - fix it
                stats['missing_consent'] += 1
                container['consent_required'] = True
                container['updated_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

                # Add changelog entry
                if 'changelog' not in container:
                    container['changelog'] = []

                container['changelog'].append({
                    'version': container['version'],
                    'timestamp': container['updated_at'],
                    'changes': 'Auto-remediation: Added consent_required flag for sensitive container',
                    'author': 'fix_consent_flags.py'
                })

                stats['fixed'] += 1
                stats['fixes'].append({
                    'id': container['id'],
                    'path': container['path'],
                    'namespace': container['namespace']
                })
            else:
                stats['already_compliant'] += 1

    # Write fixed registry
    with open(output_path, 'w') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    return stats


def main():
    if len(sys.argv) != 3:
        print("Usage: fix_consent_flags.py <input_registry.json> <output_registry.json>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    if not Path(input_path).exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"🔧 Fixing consent flags in {input_path}...")
    stats = fix_consent_flags(input_path, output_path)

    print(f"\n✅ Remediation Complete")
    print(f"  Total containers: {stats['total_containers']}")
    print(f"  Sensitive containers: {stats['sensitive_containers']}")
    print(f"  Missing consent flag: {stats['missing_consent']}")
    print(f"  Fixed: {stats['fixed']}")
    print(f"  Already compliant: {stats['already_compliant']}")
    print(f"\n📝 Output written to: {output_path}")

    if stats['fixes']:
        print(f"\nFixed containers (first 10):")
        for fix in stats['fixes'][:10]:
            print(f"  - {fix['id']}")
        if len(stats['fixes']) > 10:
            print(f"  ... and {len(stats['fixes']) - 10} more")

    print(f"\n🎯 Expected linter warning reduction: {stats['fixed']} warnings")


if __name__ == '__main__':
    main()
