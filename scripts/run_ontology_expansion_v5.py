#!/usr/bin/env python3
"""
Run Ontology Expansion v5 - Generate 8,000-10,000 new containers.

Phase 8A: Expansion Core
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ReDNACoreDemo.core.ontology.expansion_engine import run_expansion, create_expansion_engine


def main():
    """Run the expansion pipeline."""
    print("=" * 70)
    print("  ReDNA Ontology Expansion v5.0")
    print("  Phase 8A: Expansion Core")
    print("=" * 70)
    print()

    # Configuration
    TARGET_COUNT = 8000  # Target number of NEW containers
    print(f"Target: Generate {TARGET_COUNT} new containers")
    print()

    # Create engine and run expansion
    print("Initializing expansion engine...")
    engine, stats = run_expansion(target_count=TARGET_COUNT)

    # Display stats
    print()
    print("=" * 70)
    print("  Expansion Complete")
    print("=" * 70)
    print()
    print(f"Generated:       {stats['generated']:,} containers")
    print(f"Duplicates:      {stats['duplicates']:,} skipped")
    print(f"Collisions:      {stats['collisions']:,} path conflicts")
    print(f"Duration:        {stats.get('duration_seconds', 0):.2f} seconds")
    print()

    # Run validation
    print("Running validation...")
    validation = engine.validate()

    print()
    print("Validation Results:")
    print(f"  Total containers:  {validation['total_containers']:,}")
    print(f"  Unique IDs:        {validation['unique_ids']:,}")
    print(f"  Unique paths:      {validation['unique_paths']:,}")
    print(f"  Semantic hashes:   {validation['unique_semantic_hashes']:,}")
    print()

    print("Namespace Distribution:")
    for namespace, count in sorted(validation['namespace_distribution'].items()):
        print(f"  {namespace:20} {count:>6,} containers")
    print()

    if validation['errors']:
        print("❌ ERRORS:")
        for error in validation['errors']:
            print(f"  - {error}")
        print()

    if validation['warnings']:
        print("⚠️  WARNINGS:")
        for warning in validation['warnings']:
            print(f"  - {warning}")
        print()

    if validation['valid']:
        print("✅ Validation passed!")
    else:
        print("❌ Validation failed!")
        return 1

    # Save registry
    print()
    print("Saving v5 registry...")
    registry_path = engine.save_registry_v5()
    print(f"✅ Saved to: {registry_path}")

    # Save validation report
    validation_path = registry_path.parent / "validation_report.json"
    with open(validation_path, 'w') as f:
        json.dump({
            'stats': stats,
            'validation': validation,
        }, f, indent=2)
    print(f"✅ Validation report: {validation_path}")

    print()
    print("=" * 70)
    print("  Phase 8A Complete!")
    print("=" * 70)
    print()
    print(f"Total containers in v5 registry: {validation['total_containers']:,}")
    print(f"  Base (v4):  {len(engine.existing_containers):,}")
    print(f"  New (v5):   {len(engine.generated_containers):,}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
