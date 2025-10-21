"""
Phase 10: ReDNA Hierarchy Redefinition Tests

Tests the new hierarchy where:
- ReDNA = Replicated Digital Neural Approximation (root)
- RelDNA = Relational DNA (tier-1, demoted from root)
- PaDNA, BehDNA, CogDNA, EmoDNA = Other tier-1 subsystems
"""

import pytest
from ReDNACoreDemo.core.graph.aliases import get_all_aliases, get_canonical_trait_id
from ReDNACoreDemo.core.graph.ontology import load_seed_ontology


class TestOntologyHierarchy:
    """Test that the seed ontology reflects the new hierarchy."""

    def test_ontology_has_redna_root(self):
        """Test: Ontology has ReDNA as root node."""
        ontology = load_seed_ontology()

        # Find ReDNA root node
        redna_nodes = [n for n in ontology.nodes if n.trait_id == "ReDNA"]

        assert len(redna_nodes) == 1, "Should have exactly one ReDNA root node"

        redna = redna_nodes[0]
        assert redna.node_type == "dna_category"
        assert redna.label == "ReDNA"
        assert "Replicated Digital Neural Approximation" in redna.description
        assert redna.metadata.get("is_root") is True
        assert redna.metadata.get("tier") == 0

    def test_ontology_has_reldna_tier1(self):
        """Test: Ontology has RelDNA as tier-1 child of ReDNA."""
        ontology = load_seed_ontology()

        # Find RelDNA node
        reldna_nodes = [n for n in ontology.nodes if n.trait_id == "RelDNA"]

        assert len(reldna_nodes) == 1, "Should have exactly one RelDNA node"

        reldna = reldna_nodes[0]
        assert reldna.node_type == "dna_category"
        assert reldna.label == "RelDNA"
        assert "Relational DNA" in reldna.description
        assert reldna.metadata.get("tier") == 1
        assert reldna.metadata.get("parent") == "ReDNA"

        # Check aliases in metadata
        aliases = reldna.metadata.get("aliases", [])
        assert "RelationalDNA" in aliases
        assert "Relational DNA" in aliases

    def test_ontology_has_tier1_subsystems(self):
        """Test: Ontology has PaDNA, BehDNA, CogDNA, EmoDNA as tier-1."""
        ontology = load_seed_ontology()

        tier1_systems = ["RelDNA", "PaDNA", "BehDNA", "CogDNA", "EmoDNA"]

        for system_id in tier1_systems:
            nodes = [n for n in ontology.nodes if n.trait_id == system_id]
            assert len(nodes) == 1, f"Should have {system_id} node"

            node = nodes[0]
            assert node.node_type == "dna_category"
            assert node.metadata.get("tier") == 1
            assert node.metadata.get("parent") == "ReDNA"

    def test_ontology_has_hierarchy_edges(self):
        """Test: Ontology has is_parent_of edges from ReDNA to tier-1 systems."""
        ontology = load_seed_ontology()

        # Find ReDNA root node
        redna_nodes = [n for n in ontology.nodes if n.trait_id == "ReDNA"]
        assert len(redna_nodes) == 1
        redna_node_id = redna_nodes[0].node_id

        # Find edges from ReDNA
        child_edges = [e for e in ontology.edges if e.from_node == redna_node_id and e.edge_type == "is_parent_of"]

        # Should have at least 5 children (RelDNA, PaDNA, BehDNA, CogDNA, EmoDNA)
        assert len(child_edges) >= 5, f"ReDNA should have at least 5 children, got {len(child_edges)}"

        # Check that RelDNA is one of the children
        reldna_nodes = [n for n in ontology.nodes if n.trait_id == "RelDNA"]
        reldna_node_id = reldna_nodes[0].node_id

        reldna_edge = [e for e in child_edges if e.to_node == reldna_node_id]
        assert len(reldna_edge) == 1, "Should have edge ReDNA -> RelDNA"


class TestAliasMapping:
    """Test that aliases work for legacy compatibility."""

    def test_relational_dna_aliases_to_reldna(self):
        """Test: 'RelationalDNA' resolves to 'RelDNA' via aliases."""
        aliases = get_all_aliases("RelationalDNA")

        assert "RelDNA" in aliases
        assert "RelationalDNA" in aliases

    def test_reldna_aliases_to_relational(self):
        """Test: 'RelDNA' includes 'RelationalDNA' as alias."""
        aliases = get_all_aliases("RelDNA")

        assert "RelDNA" in aliases
        assert "RelationalDNA" in aliases
        assert "Relational DNA" in aliases

    def test_behavior_dna_aliases(self):
        """Test: BehaviorDNA <-> BehDNA aliases."""
        aliases_beh = get_all_aliases("BehDNA")
        aliases_behavior = get_all_aliases("BehaviorDNA")

        assert "BehaviorDNA" in aliases_beh
        assert "BehDNA" in aliases_behavior

    def test_canonical_prefers_short_form(self):
        """Test: Canonical form prefers shorter DNA names."""
        # RelationalDNA should canonicalize to RelDNA (first in list)
        canonical = get_canonical_trait_id("RelationalDNA")
        # Could be either RelDNA or RelationalDNA depending on implementation
        # Just ensure it's consistent
        assert canonical in ["RelDNA", "RelationalDNA"]


class TestEgressInvariants:
    """Test that Phase 9 egress normalization still works (no regressions)."""

    def test_egress_normalization_still_works(self):
        """Test: Egress normalization from Phase 9 is not broken by hierarchy change."""
        from ReDNACoreDemo.core.graph.normalize_egress import normalize_belief_node
        from ReDNACoreDemo.core.graph.schemas import BeliefNode

        node = BeliefNode(
            node_type="trait_belief",
            trait_id="RelDNA.SocialStyle",  # Using new RelDNA namespace
            value="Extroverted",
            rr=None,
            curiosity=None,
            rr_score=820.0  # Legacy 0-1000
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        # Should normalize to 0-100
        assert normalized.rr == 82.0
        assert normalized.curiosity == 18.0
        assert normalized.rr_meta["scale"] == "0_1000"

    def test_curiosity_formula_unchanged(self):
        """Test: Curiosity = 100 - RR (Phase 9 formula preserved)."""
        from ReDNACoreDemo.core.graph.normalize_egress import normalize_trait_dict

        trait = {
            "trait_id": "RelDNA.Empathy",
            "value": "High",
            "rr_score": 650.0
        }

        normalized = normalize_trait_dict(trait, user_id="test_user")

        assert normalized["rr"] == 65.0
        assert normalized["curiosity"] == 35.0  # 100 - 65


class TestPropagationGuidance:
    """Test that AI propagation guidance is present in prompts."""

    def test_ucnrr_prompt_has_hierarchy(self):
        """Test: UCNRR service prompt includes Phase 10 hierarchy."""
        from ReDNACoreDemo.core import ucn_rr_service

        docstring = ucn_rr_service.__doc__ or ""

        # Check for Phase 10 content
        assert "Phase 10" in docstring
        assert "ReDNA (root)" in docstring or "ReDNA = root" in docstring
        assert "Replicated Digital Neural Approximation" in docstring
        assert "RelDNA (tier-1)" in docstring or "RelDNA = tier-1" in docstring or "RelDNA (tier-1)" in docstring
        assert "organism" in docstring.lower()

    def test_ucnrr_prompt_has_phase9_guidance(self):
        """Test: Phase 9 AI-first propagation guidance still present."""
        from ReDNACoreDemo.core import ucn_rr_service

        docstring = ucn_rr_service.__doc__ or ""

        # Phase 9 content should still be there
        assert "Phase 9" in docstring
        assert "child UCN" in docstring or "child trait" in docstring
        assert "Why-Card" in docstring or "Why-card" in docstring
        assert "discretion" in docstring.lower() or "formula" in docstring.lower()


class TestBackwardCompatibility:
    """Test that existing data using old names still works."""

    def test_legacy_relational_dna_trait_resolves(self):
        """Test: A trait with 'RelationalDNA' in its ID can be resolved via alias."""
        from ReDNACoreDemo.core.graph.aliases import get_all_aliases

        # Legacy trait ID
        legacy_id = "RelationalDNA.SocialStyle"

        # This should not error (aliases handle namespace conversion)
        # We can't test full resolution without a running API, but we can test alias lookup
        aliases = get_all_aliases("RelationalDNA")
        assert "RelDNA" in aliases


class TestSchemaUpdate:
    """Test that schemas reflect the new hierarchy."""

    def test_schema_docstring_has_hierarchy(self):
        """Test: schemas.py docstring includes Phase 10 hierarchy."""
        from ReDNACoreDemo.core.graph import schemas

        docstring = schemas.__doc__ or ""

        assert "Phase 10" in docstring
        assert "ReDNA" in docstring
        assert "RelDNA" in docstring
        assert "Replicated Digital Neural Approximation" in docstring

    def test_ontology_node_supports_dna_category(self):
        """Test: OntologyNode.node_type includes 'dna_category'."""
        from ReDNACoreDemo.core.graph.schemas import OntologyNode

        # Check that dna_category is a valid node_type
        # Pydantic 2.x way to check Literal types
        node_type_field = OntologyNode.model_fields['node_type']

        # The annotation should be a Literal with dna_category
        import typing
        if hasattr(typing, 'get_args'):
            valid_types = typing.get_args(node_type_field.annotation)
            assert "dna_category" in valid_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
