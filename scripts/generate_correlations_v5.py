#!/usr/bin/env python3
"""
Generate Correlation Network v5
Creates 50,000+ weighted edges between containers.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ReDNACoreDemo.core.ontology.correlation_engine import create_correlation_engine

def main():
    print("=" * 70)
    print("  ReDNA Correlation Network Generation v5")
    print("  Phase 8B: Correlation Network")
    print("=" * 70)
    print()

    # Configuration
    TARGET_EDGES = 50000
    print(f"Target: Generate {TARGET_EDGES:,} edges")
    print()

    # Create engine
    print("Initializing correlation engine...")
    engine = create_correlation_engine()
    print(f"  Loaded: {len(engine.containers):,} containers")
    print(f"  Namespaces: {len(engine.containers_by_namespace)}")
    print()

    # Run correlation
    print("Generating edges...")
    stats = engine.run_correlation(target_edges=TARGET_EDGES)

    # Display stats
    print()
    print("=" * 70)
    print("  Generation Complete")
    print("=" * 70)
    print(f"Total Edges:              {stats['total_edges']:,}")
    print(f"  Semantic:               {stats['semantic_edges']:,}")
    print(f"  Hierarchy:              {stats['hierarchy_edges']:,}")
    print(f"  Cross-namespace:        {stats['cross_namespace_edges']:,}")
    print(f"Duration:                 {stats.get('duration_seconds', 0):.2f}s")
    print()

    # Validate
    print("Validating edges...")
    validation = engine.validate()

    print()
    print("Validation Results:")
    print(f"  Total edges:      {validation['total_edges']:,}")
    print(f"  Unique edges:     {validation['unique_edges']:,}")
    print(f"  Avg confidence:   {validation['avg_confidence']:.3f}")
    print()

    print("Confidence Distribution:")
    for range_key, count in validation['confidence_distribution'].items():
        pct = (count / validation['total_edges'] * 100) if validation['total_edges'] > 0 else 0
        print(f"  {range_key:10} {count:>8,} ({pct:>5.1f}%)")
    print()

    print("Edge Types:")
    for edge_type, count in validation['edge_types'].items():
        print(f"  {edge_type:20} {count:>8,}")
    print()

    if validation['errors']:
        print("❌ ERRORS:")
        for error in validation['errors'][:10]:
            print(f"  - {error}")
        if len(validation['errors']) > 10:
            print(f"  ... and {len(validation['errors']) - 10} more")
        print()

    if validation['valid']:
        print("✅ Validation passed!")
    else:
        print("❌ Validation failed!")
        return 1

    # Save
    print()
    print("Saving edges...")
    edges_path = engine.save_edges()
    print(f"✅ Saved to: {edges_path}")

    # Save validation report
    val_path = edges_path.parent / "correlation_validation.json"
    with open(val_path, 'w') as f:
        json.dump({'stats': stats, 'validation': validation}, f, indent=2)
    print(f"✅ Validation report: {val_path}")

    print()
    print("=" * 70)
    print(f"✅ Phase 8B Complete! Generated {validation['total_edges']:,} edges")
    print("=" * 70)

    return 0

if __name__ == "__main__":
    sys.exit(main())
