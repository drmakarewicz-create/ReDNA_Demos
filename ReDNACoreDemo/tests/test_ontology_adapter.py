"""
Test suite for OntologyAdapter
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ontology_adapter import get_ontology_adapter


def test_initialization():
    """Test adapter initialization."""
    print("Test 1: Initialization")
    adapter = get_ontology_adapter()
    stats = adapter.get_stats()

    assert stats['total_containers'] == 2000, f"Expected 2000 containers, got {stats['total_containers']}"
    assert stats['total_edges'] == 200, f"Expected 200 edges, got {stats['total_edges']}"
    assert stats['namespaces'] == 14, f"Expected 14 namespaces, got {stats['namespaces']}"

    print(f"  ✅ Initialized with {stats['total_containers']} containers, {stats['total_edges']} edges")
    print(f"  ✅ Network density: {stats['network_density']:.3f}")


def test_container_lookup():
    """Test container retrieval."""
    print("\nTest 2: Container Lookup")
    adapter = get_ontology_adapter()

    # Test get_container
    container = adapter.get_container("PsyDNA.GritPersistenceDNA")
    assert container is not None, "Failed to find PsyDNA.GritPersistenceDNA"
    assert container['namespace'] == 'PsyDNA'

    print(f"  ✅ Found container: {container['path']}")

    # Test namespace lookup
    psy_containers = adapter.get_containers_by_namespace("PsyDNA")
    assert len(psy_containers) == 180, f"Expected 180 PsyDNA containers, got {len(psy_containers)}"

    print(f"  ✅ Retrieved {len(psy_containers)} containers from PsyDNA namespace")


def test_cross_links():
    """Test cross-link queries."""
    print("\nTest 3: Cross-Link Queries")
    adapter = get_ontology_adapter()

    # Find a container with edges
    test_path = "PsyDNA.GritPersistenceDNA.FailureRecoveryDNA"
    related = adapter.get_related_containers(test_path)

    if related:
        print(f"  ✅ Found {len(related)} related containers for {test_path}")
        print(f"     Top relation: {related[0][0]['path']} ({related[0][1]}, conf: {related[0][2]:.2f})")
    else:
        print(f"  ⚠️  No relations found for {test_path}")


def test_semantic_neighbors():
    """Test semantic neighbor traversal."""
    print("\nTest 4: Semantic Neighbor Traversal")
    adapter = get_ontology_adapter()

    test_path = "PsyDNA.PersonalityDNA.BigFiveDNA.ConscientiousnessDNA"
    neighbors = adapter.get_semantic_neighbors(test_path, max_depth=2)

    print(f"  ✅ Found {len(neighbors)} semantic neighbors within 2 hops")
    if neighbors:
        namespaces = set(n['namespace'] for n in neighbors[:5])
        print(f"     Neighbor namespaces: {', '.join(namespaces)}")


def test_awareness_context():
    """Test awareness context generation."""
    print("\nTest 5: Awareness Context Generation")
    adapter = get_ontology_adapter()

    # Mock user traits
    user_traits = {
        "PsyDNA.GritPersistenceDNA.FailureRecoveryDNA": 85,
        "BehDNA.ProductivityWorkflowDNA.TaskPrioritizationMethodDNA": 75,
        "CogDNA.CognitiveStyleDNA.SystematicAnalyticalDNA": 25,
    }

    context = adapter.get_awareness_context(user_traits)

    print(f"  ✅ Generated awareness context:")
    print(f"     High RR traits: {len(context['high_rr_traits'])}")
    print(f"     Low RR traits: {len(context['low_rr_traits'])}")
    print(f"     Related concepts: {len(context['related_concepts'])}")


def test_exploration_suggestions():
    """Test exploration path suggestions."""
    print("\nTest 6: Exploration Path Suggestions")
    adapter = get_ontology_adapter()

    suggestions = adapter.suggest_exploration_paths("PsyDNA.MotivationDNA.GoalOrientationDNA", limit=3)

    print(f"  ✅ Generated {len(suggestions)} exploration suggestions")
    for sug in suggestions:
        print(f"     → {sug['path']} (via {sug['edge_type']}, conf: {sug['confidence']:.2f})")


def test_jpi_coverage():
    """Test JPI ontology coverage calculation."""
    print("\nTest 7: JPI Ontology Coverage")
    adapter = get_ontology_adapter()

    # Mock user data
    user_data = {
        "PsyDNA.GritPersistenceDNA.FailureRecoveryDNA": 85,
        "BehDNA.ProductivityWorkflowDNA.TaskPrioritizationMethodDNA": 75,
        "CogDNA.CognitiveStyleDNA.SystematicAnalyticalDNA": 25,
    }

    coverage = adapter.get_jpi_ontology_coverage(user_data)

    print(f"  ✅ JPI Coverage Metrics:")
    print(f"     Overall coverage: {coverage['overall_coverage']*100:.1f}%")
    print(f"     Populated containers: {coverage['populated_containers']}/{coverage['total_containers']}")

    # Show top namespaces by coverage
    ns_cov = sorted(coverage['namespace_coverage'].items(), key=lambda x: x[1]['coverage'], reverse=True)
    print(f"     Top namespace coverage:")
    for ns, cov in ns_cov[:3]:
        print(f"       {ns}: {cov['coverage']*100:.1f}% ({cov['populated']}/{cov['total']})")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Ontology Adapter Test Suite")
    print("=" * 60)

    try:
        test_initialization()
        test_container_lookup()
        test_cross_links()
        test_semantic_neighbors()
        test_awareness_context()
        test_exploration_suggestions()
        test_jpi_coverage()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
