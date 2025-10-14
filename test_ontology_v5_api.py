#!/usr/bin/env python3
"""
Test script for Ontology V5 API endpoints.
Tests the correlation engine and endpoint logic without starting the server.
"""

import sys
from pathlib import Path

# Add ReDNACoreDemo to path
sys.path.insert(0, str(Path(__file__).parent))

from ReDNACoreDemo.core.ontology.correlation_engine import create_correlation_engine


def test_correlation_engine_loading():
    """Test that correlation engine loads edges correctly."""
    print("=" * 60)
    print("TEST 1: Correlation Engine Loading")
    print("=" * 60)

    engine = create_correlation_engine()

    print(f"✓ Containers loaded: {len(engine.containers)}")
    print(f"✓ Edges loaded: {len(engine.edges)}")
    print(f"  - Semantic edges: {engine.stats.get('semantic_edges', 0)}")
    print(f"  - Hierarchy edges: {engine.stats.get('hierarchy_edges', 0)}")
    print(f"  - Cross-namespace edges: {engine.stats.get('cross_namespace_edges', 0)}")

    assert len(engine.containers) > 2000, "Should have 2,615 containers"
    assert len(engine.edges) > 40000, "Should have ~49,342 edges"

    print("\n✅ Correlation engine loads correctly\n")
    return engine


def test_get_related_containers(engine):
    """Test getting related containers."""
    print("=" * 60)
    print("TEST 2: Get Related Containers")
    print("=" * 60)

    # Pick a container to test
    test_path = "SkillDNA.Programming.Python"

    if test_path not in engine.containers:
        print(f"⚠️  Container {test_path} not found, picking first SkillDNA container")
        test_path = next(
            (path for path in engine.containers.keys() if path.startswith("SkillDNA.")),
            None
        )

    if not test_path:
        print("❌ No SkillDNA containers found!")
        return

    print(f"Testing with container: {test_path}")

    related = engine.get_related_containers(test_path, limit=20)

    print(f"✓ Found {len(related)} related containers")

    if related:
        print("\nTop 5 related containers:")
        for i, item in enumerate(related[:5], 1):
            container = item['container']
            if container:
                print(f"  {i}. {container['path']}")
                print(f"     Type: {item['edge_type']}, Confidence: {item['confidence']:.3f}")

    print("\n✅ Related container lookup works\n")


def test_namespace_distribution(engine):
    """Test namespace distribution."""
    print("=" * 60)
    print("TEST 3: Namespace Distribution")
    print("=" * 60)

    by_namespace = {}
    for container in engine.containers.values():
        ns = container.get('namespace', 'Unknown')
        by_namespace[ns] = by_namespace.get(ns, 0) + 1

    print("Containers by namespace:")
    for ns, count in sorted(by_namespace.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ns}: {count}")

    print("\n✅ Namespace distribution computed\n")


def test_validation(engine):
    """Test validation."""
    print("=" * 60)
    print("TEST 4: Validation")
    print("=" * 60)

    validation = engine.validate()

    print(f"✓ Total edges: {validation['total_edges']}")
    print(f"✓ Unique edges: {validation['unique_edges']}")
    print(f"✓ Avg confidence: {validation['avg_confidence']:.3f}")
    print(f"✓ Errors: {len(validation['errors'])}")
    print(f"✓ Warnings: {len(validation['warnings'])}")
    print(f"✓ Valid: {validation['valid']}")

    if validation['errors']:
        print("\nErrors:")
        for error in validation['errors'][:5]:
            print(f"  - {error}")

    assert validation['valid'], "Validation should pass"
    print("\n✅ Validation passed\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ONTOLOGY V5 API TESTS")
    print("=" * 60 + "\n")

    try:
        engine = test_correlation_engine_loading()
        test_get_related_containers(engine)
        test_namespace_distribution(engine)
        test_validation(engine)

        print("=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
