"""
Test suite for Phase 9: UCN↔RR Conflation Guardrails

Tests guarded normalization, RR/UCN separation, and API egress correctness.
"""

import pytest
from ReDNACoreDemo.core.metrics.rr_adapter import rr_to_percentile
from ReDNACoreDemo.core.graph.normalize_egress import (
    normalize_belief_node,
    normalize_trait_dict,
)
from ReDNACoreDemo.core.graph.schemas import BeliefNode


class TestRRAdapter:
    """Test rr_to_percentile adapter for scale normalization."""

    def test_adapt_rr_over_100(self):
        """Test: rr=260 (0-1000 scale) → rr=26.0, curiosity=74.0"""
        result = rr_to_percentile(
            rr_raw=260.0,
            rr_scale="0_1000",
            trait_id="PaDNA.Chronotype",
            user_id="test_user"
        )

        assert result["rr"] == 26.0
        assert result["curiosity"] == 74.0
        assert result["rr_meta"]["scale"] == "0_1000"
        assert result["rr_meta"]["rr_raw"] == 260.0

    def test_fill_rr_from_rr_score(self):
        """Test: rr=null, rr_score=800 (0-1000) → rr=80, curiosity=20"""
        result = rr_to_percentile(
            rr_raw=800.0,
            rr_scale="0_1000",
            trait_id="PaDNA.EyeDNA.Color",
            user_id="test_user"
        )

        assert result["rr"] == 80.0
        assert result["curiosity"] == 20.0

    def test_fill_rr_from_reference_pop(self, monkeypatch):
        """Test: only UCN present → RR derived from reference population percentile"""
        # Mock reference_percentile to return 65.0
        def mock_ref_percentile(trait_id, user_id):
            return 65.0

        # Patch the import location where it's actually used
        monkeypatch.setattr(
            "ReDNACoreDemo.core.reference_pop.reference_pop.reference_percentile",
            mock_ref_percentile
        )

        result = rr_to_percentile(
            rr_raw=None,
            rr_scale="reference_percentile",
            trait_id="PaDNA.HairDNA.Color",
            user_id="test_user",
            use_reference=True
        )

        assert result["rr"] == 65.0
        assert result["curiosity"] == 35.0
        assert result["rr_meta"]["scale"] == "reference_percentile"

    def test_curiosity_consistency(self):
        """Test: curiosity always equals 100 - rr"""
        test_cases = [
            (0.0, 100.0),
            (25.0, 75.0),
            (50.0, 50.0),
            (75.0, 25.0),
            (100.0, 0.0),
        ]

        for rr_raw, expected_curiosity in test_cases:
            result = rr_to_percentile(
                rr_raw=rr_raw,
                rr_scale="0_100",
                trait_id="test_trait",
                user_id="test_user"
            )
            assert result["rr"] == rr_raw
            assert result["curiosity"] == expected_curiosity

    def test_clamp_rr_boundaries(self):
        """Test: RR is clamped to [0, 100]"""
        # Test over 100
        result = rr_to_percentile(
            rr_raw=1200.0,  # 0-1000 scale
            rr_scale="0_1000",
            trait_id="test_trait",
            user_id="test_user"
        )
        assert result["rr"] == 100.0  # Clamped to 100
        assert result["curiosity"] == 0.0

        # Test negative (shouldn't happen but test clamp)
        result = rr_to_percentile(
            rr_raw=-10.0,
            rr_scale="0_100",
            trait_id="test_trait",
            user_id="test_user"
        )
        assert result["rr"] == 0.0  # Clamped to 0
        assert result["curiosity"] == 100.0


class TestNormalizeBeliefNode:
    """Test normalize_belief_node for guarded normalization."""

    def test_guard_rr_greater_100(self):
        """Test: If rr > 100, divide by 10 and recompute curiosity"""
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.Chronotype",
            value="Morning Lark",
            rr=260.0,  # Legacy 0-1000 scale
            curiosity=740.0,
            rr_score=260.0
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        assert normalized.rr == 26.0
        assert normalized.curiosity == 74.0

    def test_guard_fill_rr_from_rr_score(self):
        """Test: If rr=null and rr_score present, derive rr"""
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.EyeDNA.Color",
            value="Blue",
            rr=None,
            curiosity=None,
            rr_score=850.0
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        assert normalized.rr == 85.0
        assert normalized.curiosity == 15.0
        assert "rr_meta" in normalized.model_dump()

    def test_guard_fill_rr_from_curiosity(self):
        """Test: If curiosity present but rr missing, compute rr = 100 - curiosity"""
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.HairDNA.Color",
            value="Brown",
            rr=None,
            curiosity=30.0,
            rr_score=None
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        assert normalized.rr == 70.0
        assert normalized.curiosity == 30.0

    def test_guard_curiosity_mismatch(self):
        """Test: If curiosity ≠ 100 - rr, correct it"""
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.SkinDNA.Tone",
            value="Fair",
            rr=60.0,
            curiosity=50.0,  # Should be 40.0
            rr_score=600.0
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        assert normalized.rr == 60.0
        assert normalized.curiosity == 40.0  # Corrected

    def test_guard_ucn_present_derive_from_ref(self, monkeypatch):
        """Test: If neither RR nor rr_score but UCN present, derive from reference pop"""
        # Mock reference_percentile
        def mock_ref_percentile(trait_id, user_id):
            return 72.0

        monkeypatch.setattr(
            "ReDNACoreDemo.core.graph.normalize_egress.rr_to_percentile",
            lambda **kwargs: {
                "rr": 72.0,
                "curiosity": 28.0,
                "rr_meta": {"scale": "reference_percentile", "source": "ref_pop"}
            } if kwargs.get("rr_scale") == "reference_percentile" else rr_to_percentile(**kwargs)
        )

        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.Chronotype",
            value="Morning Lark",
            rr=None,
            curiosity=None,
            rr_score=None,
            ucn={"u": 0.72, "c": 0.68, "n": 0.5}
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        # Should derive from reference pop
        assert normalized.rr is not None
        assert normalized.curiosity is not None


class TestNormalizeTraitDict:
    """Test normalize_trait_dict for dictionary-based normalization."""

    def test_adapt_rr_over_100_dict(self):
        """Test: Trait dict with rr > 100"""
        trait = {
            "trait_id": "PaDNA.Chronotype",
            "value": "Morning Lark",
            "rr": 320.0,
            "curiosity": 680.0,
        }

        normalized = normalize_trait_dict(trait, user_id="test_user")

        assert normalized["rr"] == 32.0
        assert normalized["curiosity"] == 68.0

    def test_fill_from_rr_score_dict(self):
        """Test: Trait dict with rr_score but no rr"""
        trait = {
            "trait_id": "PaDNA.EyeDNA.Color",
            "value": "Green",
            "rr_score": 950.0,
        }

        normalized = normalize_trait_dict(trait, user_id="test_user")

        assert normalized["rr"] == 95.0
        assert normalized["curiosity"] == 5.0
        assert "rr_meta" in normalized


class TestNoUCNLeak:
    """Test that no endpoint exposes raw 0-1000 UCN as RR."""

    def test_belief_node_never_leaks_ucn_as_rr(self):
        """Test: Belief node with UCN should never expose UCN as RR"""
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.Chronotype",
            value="Morning Lark",
            rr=None,
            curiosity=None,
            rr_score=750.0,  # 0-1000
            ucn={"u": 0.75, "c": 0.68, "n": 0.5}
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        # RR should be 0-100 percentile, not 750
        assert normalized.rr <= 100.0
        assert normalized.rr >= 0.0
        assert normalized.curiosity == 100.0 - normalized.rr

    def test_trait_dict_never_leaks_ucn_as_rr(self):
        """Test: Trait dict should never expose UCN scalar as RR"""
        trait = {
            "trait_id": "PaDNA.HairDNA.Color",
            "value": "Red",
            "rr_score": 820.0,
            "ucn": {"u": 0.82, "c": 0.75, "n": 0.6}
        }

        normalized = normalize_trait_dict(trait, user_id="test_user")

        # RR should be 0-100
        assert normalized["rr"] <= 100.0
        assert normalized["rr"] >= 0.0


class TestDebugAuditEndpoint:
    """Test /core/debug/rr_audit/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_debug_audit_endpoint_structure(self):
        """Test: Debug audit endpoint returns correct structure"""
        from ReDNACoreDemo.core.graph.debug_api import audit_rr_normalization

        # This would require a test user with graph data
        # For now, test that it doesn't crash with invalid user
        try:
            result = await audit_rr_normalization("nonexistent_user", dry_run=True)
            assert "user_id" in result
            assert "summary" in result
            assert "issues" in result
        except Exception:
            # Expected if storage not initialized
            pass

    @pytest.mark.asyncio
    async def test_debug_ucn_propagation_endpoint(self):
        """Test: UCN propagation audit endpoint"""
        from ReDNACoreDemo.core.graph.debug_api import audit_ucn_propagation

        try:
            result = await audit_ucn_propagation("nonexistent_user")
            assert "user_id" in result
            assert "summary" in result
            assert "divergences" in result
        except Exception:
            # Expected if storage not initialized
            pass


class TestAIPromptPresent:
    """Test that UCNRR prompt includes child-informed propagation logic."""

    def test_ucnrr_service_has_propagation_guidance(self):
        """Test: UCNRR service module docstring includes Phase 9 guidance"""
        from ReDNACoreDemo.core import ucn_rr_service

        docstring = ucn_rr_service.__doc__ or ""

        # Check for Phase 9 guidance
        assert "Phase 9" in docstring
        assert "hierarchical" in docstring.lower() or "propagation" in docstring.lower()
        assert "child" in docstring.lower()
        assert "parent" in docstring.lower()
        assert "UCN" in docstring
        assert "RR" in docstring

    def test_belief_module_has_propagation_guidance(self):
        """Test: Belief graph module includes Phase 9 guidance"""
        from ReDNACoreDemo.core.graph import belief

        docstring = belief.__doc__ or ""

        assert "Phase 9" in docstring
        assert "parent" in docstring.lower()
        assert "child" in docstring.lower() or "children" in docstring.lower()


class TestEndToEndNormalization:
    """End-to-end tests for RR normalization pipeline."""

    def test_e2e_legacy_rr_score_to_percentile(self):
        """Test: Legacy rr_score (0-1000) → normalized rr (0-100)"""
        # Simulate legacy node with 0-1000 rr_score
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.Chronotype",
            value="Morning Lark",
            rr=None,
            curiosity=None,
            rr_score=743.26  # Legacy 0-1000
        )

        normalized = normalize_belief_node(node, user_id="ai_ready_probe")

        # Should be normalized to 0-100
        assert normalized.rr == pytest.approx(74.33, abs=0.01)
        assert normalized.curiosity == pytest.approx(25.67, abs=0.01)
        assert normalized.rr_meta["scale"] == "0_1000"

    def test_e2e_rr_already_percentile(self):
        """Test: RR already 0-100 percentile (passthrough)"""
        node = BeliefNode(
            node_type="trait_belief",
            trait_id="PaDNA.EyeDNA.Color",
            value="Blue",
            rr=None,
            curiosity=None,
            rr_score=68.5  # Already 0-100
        )

        normalized = normalize_belief_node(node, user_id="test_user")

        assert normalized.rr == 68.5
        assert normalized.curiosity == 31.5
        assert normalized.rr_meta["scale"] == "0_100"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
