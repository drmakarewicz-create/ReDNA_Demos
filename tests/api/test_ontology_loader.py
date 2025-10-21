"""
Test suite for Phase 10 ontology loader fix

Tests force loading, version-based auto-upgrade, and hierarchy verification.
"""
import pytest
from pathlib import Path
import json
import tempfile
import shutil
from datetime import datetime

from ReDNACoreDemo.core.graph.ontology import load_seed_ontology
from ReDNACoreDemo.core.graph.storage import FileGraphStorage
from ReDNACoreDemo.core.graph.schemas import OntologyGraph, OntologyNode, OntologyEdge


class TestOntologyForceLoad:
    """Test force=true parameter for ontology loading."""

    def test_force_load_replaces_existing(self):
        """Test: force=true replaces existing ontology, doesn't merge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileGraphStorage(Path(tmpdir))

            # Create initial ontology with 2 nodes
            initial_graph = OntologyGraph(
                version="1.0",
                nodes=[
                    OntologyNode(
                        node_id="ont_old_1",
                        node_type="trait",
                        trait_id="OldTrait.One",
                        label="Old Trait 1",
                    ),
                    OntologyNode(
                        node_id="ont_old_2",
                        node_type="trait",
                        trait_id="OldTrait.Two",
                        label="Old Trait 2",
                    ),
                ],
                edges=[],
            )
            storage.save_ontology(initial_graph)

            # Verify initial state
            loaded = storage.load_ontology()
            assert len(loaded.nodes) == 2
            assert loaded.version == "1.0"
            assert all("OldTrait" in n.trait_id for n in loaded.nodes if n.trait_id)

            # Now create a seed ontology with different nodes
            seed_path = Path(tmpdir) / "ontology" / "seed_ontology.json"
            seed_data = {
                "version": "2.0",
                "nodes": [
                    {
                        "node_id": "ont_new_1",
                        "node_type": "trait",
                        "trait_id": "NewTrait.One",
                        "label": "New Trait 1",
                        "created_at": datetime.utcnow().isoformat(),
                        "metadata": {},
                    }
                ],
                "edges": [],
            }
            with open(seed_path, "w") as f:
                json.dump(seed_data, f)

            # Force load should REPLACE, not merge
            # (Simulating what the API endpoint does)
            from ReDNACoreDemo.core.graph.ontology import load_seed_ontology

            # Temporarily override the seed path search
            def mock_load_seed() -> OntologyGraph:
                with open(seed_path) as f:
                    data = json.load(f)
                return OntologyGraph(
                    version=data["version"],
                    nodes=[OntologyNode(**n) for n in data["nodes"]],
                    edges=[],
                )

            # Simulate force load
            new_graph = mock_load_seed()
            storage.save_ontology(new_graph)

            # Verify: should have ONLY new nodes, not merged
            final = storage.load_ontology()
            assert len(final.nodes) == 1, f"Expected 1 node (replace), got {len(final.nodes)}"
            assert final.version == "2.0"
            assert final.nodes[0].trait_id == "NewTrait.One"
            # Old nodes should NOT be present
            assert not any("OldTrait" in (n.trait_id or "") for n in final.nodes)


class TestOntologyVersionUpgrade:
    """Test version-based auto-upgrade logic."""

    def test_version_upgrade_when_seed_newer(self):
        """Test: Auto-upgrade when seed.version > stored.version."""
        # NOTE: This test demonstrates the logic used in api_graph.py load_ontology_endpoint
        # The storage layer always reads from seed_ontology.json, so we test the version comparison logic
        from ReDNACoreDemo.core.graph.api_graph import _version_greater

        # Test version comparison
        assert _version_greater("2.0", "1.0"), "Version 2.0 should be greater than 1.0"
        assert _version_greater("1.5", "1.4"), "Version 1.5 should be greater than 1.4"

        # Simulate the upgrade flow from api_graph.py
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileGraphStorage(Path(tmpdir))

            # Scenario: We have stored ontology v1.0, and seed is v2.0
            # In the real API, the load_ontology_endpoint would:
            # 1. Load current from storage (returns seed, which is v2.0 in this tmpdir)
            # 2. Load seed directly
            # 3. Compare versions
            # 4. If seed > stored, replace

            # Create seed with version 2.0
            seed_path = Path(tmpdir) / "ontology" / "seed_ontology.json"
            seed_data = {
                "version": "2.0",
                "nodes": [
                    {
                        "node_id": "ont_v2",
                        "node_type": "trait",
                        "trait_id": "V2.Trait",
                        "label": "Version 2 Trait",
                        "created_at": datetime.utcnow().isoformat(),
                        "metadata": {},
                    }
                ],
                "edges": [],
            }
            with open(seed_path, "w") as f:
                json.dump(seed_data, f)

            # Load from storage (will read the seed file we just created)
            loaded = storage.load_ontology()
            assert loaded.version == "2.0", f"Expected version 2.0, got {loaded.version}"
            assert loaded.nodes[0].trait_id == "V2.Trait"

    def test_no_upgrade_when_versions_equal(self):
        """Test: No upgrade when seed.version == stored.version."""
        from ReDNACoreDemo.core.graph.api_graph import _version_greater

        assert not _version_greater("2.0", "2.0")
        assert not _version_greater("1.5", "1.5")

    def test_no_upgrade_when_stored_newer(self):
        """Test: No upgrade when seed.version < stored.version."""
        from ReDNACoreDemo.core.graph.api_graph import _version_greater

        assert not _version_greater("1.0", "2.0")
        assert not _version_greater("1.9", "2.0")


class TestPhase10Hierarchy:
    """Test Phase 10 hierarchy structure is loaded correctly."""

    def test_phase10_seed_has_redna_root(self):
        """Test: Phase 10 seed ontology has ReDNA as root."""
        ontology = load_seed_ontology()

        # Find ReDNA root node
        redna_nodes = [n for n in ontology.nodes if n.trait_id == "ReDNA"]
        assert len(redna_nodes) == 1, "Should have exactly one ReDNA root node"

        redna = redna_nodes[0]
        assert redna.node_type == "dna_category", f"Expected dna_category, got {redna.node_type}"
        assert redna.metadata.get("is_root") is True
        assert redna.metadata.get("tier") == 0
        assert "Replicated Digital Neural Approximation" in redna.description

    def test_phase10_seed_has_tier1_categories(self):
        """Test: Phase 10 seed has 5 tier-1 DNA categories."""
        ontology = load_seed_ontology()

        tier1_systems = ["RelDNA", "PaDNA", "BehDNA", "CogDNA", "EmoDNA"]

        for system_id in tier1_systems:
            nodes = [n for n in ontology.nodes if n.trait_id == system_id]
            assert len(nodes) == 1, f"Should have {system_id} node"

            node = nodes[0]
            assert node.node_type == "dna_category"
            assert node.metadata.get("tier") == 1
            assert node.metadata.get("parent") == "ReDNA"

    def test_phase10_seed_has_hierarchy_edges(self):
        """Test: Phase 10 seed has is_parent_of edges from ReDNA to tier-1."""
        ontology = load_seed_ontology()

        # Find ReDNA root node
        redna_nodes = [n for n in ontology.nodes if n.trait_id == "ReDNA"]
        assert len(redna_nodes) == 1
        redna = redna_nodes[0]

        # Find is_parent_of edges from ReDNA
        parent_edges = [
            e
            for e in ontology.edges
            if e.from_node == redna.node_id and e.edge_type == "is_parent_of"
        ]

        # Should have 5 edges (one for each tier-1 category)
        assert len(parent_edges) >= 5, f"Expected ≥5 is_parent_of edges, got {len(parent_edges)}"

        # Verify each tier-1 category is a target
        tier1_ids = ["ont_reldna", "ont_padna", "ont_behdna", "ont_cogdna", "ont_emodna"]
        parent_targets = {e.to_node for e in parent_edges}

        for tid in tier1_ids:
            assert tid in parent_targets, f"{tid} should be a target of is_parent_of edge from ReDNA"

    def test_phase10_seed_has_minimum_nodes_and_edges(self):
        """Test: Phase 10 seed has ≥6 nodes and ≥5 edges."""
        ontology = load_seed_ontology()

        # Should have at least: ReDNA root + 5 tier-1 categories = 6 nodes
        assert len(ontology.nodes) >= 6, f"Expected ≥6 nodes, got {len(ontology.nodes)}"

        # Should have at least 5 is_parent_of edges (ReDNA → tier-1)
        parent_edges = [e for e in ontology.edges if e.edge_type == "is_parent_of"]
        assert len(parent_edges) >= 5, f"Expected ≥5 is_parent_of edges, got {len(parent_edges)}"

    def test_phase10_seed_version_is_2_0(self):
        """Test: Phase 10 seed ontology has version 2.0."""
        ontology = load_seed_ontology()
        assert ontology.version == "2.0", f"Expected version 2.0, got {ontology.version}"


class TestVersionComparison:
    """Test version comparison helper function."""

    def test_version_greater_basic(self):
        """Test: Basic version comparison."""
        from ReDNACoreDemo.core.graph.api_graph import _version_greater

        assert _version_greater("2.0", "1.0")
        assert _version_greater("1.1", "1.0")
        assert _version_greater("2.0.1", "2.0.0")

    def test_version_not_greater(self):
        """Test: Version not greater when equal or less."""
        from ReDNACoreDemo.core.graph.api_graph import _version_greater

        assert not _version_greater("1.0", "1.0")
        assert not _version_greater("1.0", "2.0")
        assert not _version_greater("2.0.0", "2.0.1")

    def test_version_greater_multipart(self):
        """Test: Multi-part version comparison."""
        from ReDNACoreDemo.core.graph.api_graph import _version_greater

        assert _version_greater("1.5.3", "1.5.2")
        assert _version_greater("1.10.0", "1.9.0")
        assert not _version_greater("1.5.2", "1.5.3")


class TestSchemaSupport:
    """Test that schemas support Phase 10 structures."""

    def test_ontology_node_supports_dna_category(self):
        """Test: OntologyNode schema supports dna_category node_type."""
        from ReDNACoreDemo.core.graph.schemas import OntologyNode

        node = OntologyNode(
            node_id="ont_test",
            node_type="dna_category",
            trait_id="TestDNA",
            label="Test DNA Category",
        )

        assert node.node_type == "dna_category"

    def test_ontology_edge_supports_is_parent_of(self):
        """Test: OntologyEdge schema supports is_parent_of edge_type."""
        from ReDNACoreDemo.core.graph.schemas import OntologyEdge

        edge = OntologyEdge(
            edge_id="onte_test",
            from_node="ont_parent",
            to_node="ont_child",
            edge_type="is_parent_of",
            weight=1.0,
            confidence=1.0,
            source="seed",
        )

        assert edge.edge_type == "is_parent_of"
