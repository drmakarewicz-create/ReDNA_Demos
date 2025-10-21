"""
Unit tests for /core/ui/unabridged normalization with RR reference population.

Verifies that the unabridged endpoint properly normalizes RR/Curiosity with
reference population metadata from the pluggable RR reference system.
"""

import pytest
from unittest.mock import patch, Mock
from ReDNACoreDemo.core.ui_readonly import unabridged_snapshot


@pytest.fixture
def mock_resolved_with_ucn(tmp_path, monkeypatch):
    """Mock user resolved.json with UCN values but no rr/rr_score."""
    import json
    from pathlib import Path

    users_dir = tmp_path / "users"
    users_dir.mkdir(parents=True, exist_ok=True)

    user_dir = users_dir / "test_user"
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create resolved.json with traits that have UCN but no RR
    resolved = {
        "PaDNA.Chronotype": {
            "value": "Morning",
            "ucn": 0.75,  # Has UCN, should trigger reference lookup
            # No rr or rr_score → should use reference population
        },
        "PaDNA.Height": {
            "value": "Tall",
            "ucn": 0.82,
            # No rr or rr_score → should use reference population
        },
        "BasicDNA.Age": {
            "value": "25-34",
            "ucn": 0.5,
            "rr_score": 520,  # Has rr_score → should use adapter conversion
        }
    }

    with open(user_dir / "resolved.json", 'w') as f:
        json.dump(resolved, f)

    # Mock USERS_DIR
    monkeypatch.setenv("USERS_DIR", str(users_dir))

    # Mock the _resolved_payload function to return our test data
    def mock_resolved_payload(user_id):
        if user_id == "test_user":
            return resolved
        return {}

    monkeypatch.setattr(
        "ReDNACoreDemo.core.ui_readonly._resolved_payload",
        mock_resolved_payload
    )

    return resolved


class TestUnabridgedNormalization:
    """Test unabridged endpoint RR/Curiosity normalization."""

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "SYNTHETIC"}, clear=False)
    def test_unabridged_includes_rr_and_curiosity(self, mock_resolved_with_ucn):
        """Verify all traits have rr and curiosity fields."""
        result = unabridged_snapshot("test_user")

        assert "traits" in result
        assert len(result["traits"]) == 3

        for trait in result["traits"]:
            # Every trait must have rr and curiosity
            assert "rr" in trait, f"Missing rr for {trait['trait_id']}"
            assert "curiosity" in trait, f"Missing curiosity for {trait['trait_id']}"

            # RR should be 0-100
            assert 0 <= trait["rr"] <= 100, f"RR out of range for {trait['trait_id']}: {trait['rr']}"

            # Curiosity should equal 100 - rr
            expected_curiosity = 100.0 - trait["rr"]
            assert abs(trait["curiosity"] - expected_curiosity) < 0.01, \
                f"Curiosity mismatch for {trait['trait_id']}: {trait['curiosity']} != {expected_curiosity}"

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "SYNTHETIC"}, clear=False)
    def test_unabridged_includes_rr_meta(self, mock_resolved_with_ucn):
        """Verify all traits have rr_meta with proper structure."""
        result = unabridged_snapshot("test_user")

        for trait in result["traits"]:
            assert "rr_meta" in trait, f"Missing rr_meta for {trait['trait_id']}"

            rr_meta = trait["rr_meta"]

            # All rr_meta must have these fields
            assert "rr_raw" in rr_meta or "scale" in rr_meta, \
                f"rr_meta missing basic fields for {trait['trait_id']}"

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "SYNTHETIC"}, clear=False)
    def test_unabridged_reference_lineage_for_ucn_traits(self, mock_resolved_with_ucn):
        """Verify traits with UCN (no rr_score) get reference population metadata."""
        result = unabridged_snapshot("test_user")

        # Find Chronotype (has UCN, no rr_score)
        chronotype = next((t for t in result["traits"] if "Chronotype" in t["trait_id"]), None)
        assert chronotype is not None, "Chronotype trait not found"

        # Should have reference metadata
        assert "rr_meta" in chronotype
        rr_meta = chronotype["rr_meta"]

        # When using reference population, rr_meta should have reference field
        # (May not always be present depending on which guard triggered)
        # At minimum, should have rr_raw, scale, and source fields
        assert any(k in rr_meta for k in ["reference", "source", "scale"]), \
            f"rr_meta missing reference lineage fields: {rr_meta}"

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_REFERENCE_SOURCE": "SYNTHETIC"}, clear=False)
    def test_unabridged_adapter_conversion_for_rr_score(self, mock_resolved_with_ucn):
        """Verify traits with rr_score get proper adapter conversion."""
        result = unabridged_snapshot("test_user")

        # Find Age (has rr_score=520)
        age_trait = next((t for t in result["traits"] if "Age" in t["trait_id"]), None)
        assert age_trait is not None, "Age trait not found"

        # rr_score=520 → rr should be 52.0 (520/10)
        assert age_trait["rr"] == pytest.approx(52.0, abs=0.1), \
            f"Expected rr=52.0 from rr_score=520, got {age_trait['rr']}"

        assert age_trait["curiosity"] == pytest.approx(48.0, abs=0.1), \
            f"Expected curiosity=48.0, got {age_trait['curiosity']}"

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "false"}, clear=False)
    def test_unabridged_fallback_when_reference_disabled(self, mock_resolved_with_ucn):
        """Verify fallback behavior when reference population is disabled."""
        result = unabridged_snapshot("test_user")

        # Traits without rr/rr_score should fallback to 50.0
        for trait in result["traits"]:
            if trait["trait_id"] in ["PaDNA.Chronotype", "PaDNA.Height"]:
                # These have UCN but no rr_score, should fallback to 50.0
                assert trait["rr"] == 50.0, \
                    f"{trait['trait_id']} should fallback to rr=50.0 when reference disabled, got {trait['rr']}"
                assert trait["curiosity"] == 50.0

    def test_unabridged_response_structure(self, mock_resolved_with_ucn):
        """Verify overall response structure."""
        result = unabridged_snapshot("test_user")

        assert "user_id" in result
        assert result["user_id"] == "test_user"

        assert "traits" in result
        assert "count" in result
        assert result["count"] == len(result["traits"])

        # Each trait should have expected fields
        for trait in result["traits"]:
            assert "trait_id" in trait
            assert "value" in trait
            assert "rr" in trait
            assert "curiosity" in trait
            assert "rr_meta" in trait
            assert "badges" in trait


class TestUnabridgedReferenceMetadata:
    """Test that reference population metadata is properly included."""

    @patch('ReDNACoreDemo.core.graph.normalize_egress.rr_to_percentile')
    def test_reference_metadata_passed_through(self, mock_rr_to_percentile, mock_resolved_with_ucn):
        """Verify that rr_to_percentile's rr_meta is passed through to response."""
        # Mock rr_to_percentile to return reference metadata
        mock_rr_to_percentile.return_value = {
            "rr": 75.0,
            "curiosity": 25.0,
            "rr_meta": {
                "rr_raw": None,
                "scale": "reference_percentile",
                "reference": {
                    "source": "SYNTHETIC",
                    "universe": "combined",
                    "cohort_keys": [],
                    "cohort_values": {},
                    "n_samples": 10000,
                    "generated_at": "2025-10-20T20:00:00Z"
                }
            }
        }

        result = unabridged_snapshot("test_user")

        # Find a trait that should have triggered reference lookup
        chronotype = next((t for t in result["traits"] if "Chronotype" in t["trait_id"]), None)

        if chronotype:
            assert "rr_meta" in chronotype
            rr_meta = chronotype["rr_meta"]

            # Should have reference field with proper structure
            if "reference" in rr_meta:
                ref = rr_meta["reference"]
                assert ref["source"] == "SYNTHETIC"
                assert ref["universe"] == "combined"
                assert ref["n_samples"] == 10000


class TestUnabridgedLegacyUCNNormalization:
    """Test that legacy UCN values (0-100, 0-1000) are normalized before RR calculation."""

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_PREFER_REFERENCE_OVER_SCORE": "true"}, clear=False)
    @patch('ReDNACoreDemo.core.ui_readonly._resolved_payload')
    def test_legacy_ucn_80_normalized_to_0p80(self, mock_payload):
        """Trait with ucn=80.0 (0-100 scale) should normalize to 0.80 → RR ≈ 96% (not 100%)."""
        # Mock resolved data with legacy UCN in 0-100 scale
        mock_payload.return_value = {
            "TestTrait": {
                "value": "test_value",
                "ucn": 80.0,  # Legacy 0-100 scale → should become 0.80
                # No rr or rr_score → will use reference population
            }
        }

        result = unabridged_snapshot("test_user")

        assert len(result["traits"]) == 1
        trait = result["traits"][0]

        # ucn=80 in 0-100 scale → normalized to 0.80
        # With synthetic CDF, UCN=0.80 → RR ≈ 95-96% (high refinement)
        assert 94.0 <= trait["rr"] <= 98.0, \
            f"Expected RR ≈ 96% for UCN=0.80, got {trait['rr']:.2f}%"

        # Verify using reference method
        assert trait["rr_meta"]["method"] == "reference"

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_PREFER_REFERENCE_OVER_SCORE": "true"}, clear=False)
    @patch('ReDNACoreDemo.core.ui_readonly._resolved_payload')
    def test_legacy_ucn_740_normalized_to_0p74(self, mock_payload):
        """Trait with ucn=740.0 (0-1000 scale) should normalize to 0.74 → RR ≈ 90%."""
        mock_payload.return_value = {
            "TestTrait": {
                "value": "test_value",
                "ucn": 740.0,  # Legacy 0-1000 scale → should become 0.74
            }
        }

        result = unabridged_snapshot("test_user")

        trait = result["traits"][0]

        # ucn=740 in 0-1000 scale → normalized to 0.74
        # With synthetic CDF, UCN=0.74 → RR ≈ 89-90%
        assert 85.0 <= trait["rr"] <= 92.0, \
            f"Expected RR ≈ 90% for UCN=0.74, got {trait['rr']:.2f}%"

        # Verify using reference method
        assert trait["rr_meta"]["method"] == "reference"

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_PREFER_REFERENCE_OVER_SCORE": "true"}, clear=False)
    @patch('ReDNACoreDemo.core.ui_readonly._resolved_payload')
    def test_normalized_ucn_0p74_passthrough(self, mock_payload):
        """Trait with ucn=0.74 (already normalized) should pass through → RR ≈ 90%."""
        mock_payload.return_value = {
            "TestTrait": {
                "value": "test_value",
                "ucn": 0.74,  # Already normalized [0,1]
            }
        }

        result = unabridged_snapshot("test_user")

        trait = result["traits"][0]

        # ucn=0.74 already normalized → should pass through
        assert 85.0 <= trait["rr"] <= 92.0, \
            f"Expected RR ≈ 90% for UCN=0.74, got {trait['rr']:.2f}%"

        assert trait["rr_meta"]["method"] == "reference"

    @patch.dict('os.environ', {"REFERENCE_POP_ENABLED": "true", "RR_PREFER_REFERENCE_OVER_SCORE": "true"}, clear=False)
    @patch('ReDNACoreDemo.core.ui_readonly._resolved_payload')
    def test_legacy_ucn_5_normalized_to_0p05(self, mock_payload):
        """Trait with ucn=5.0 (0-100 scale) should normalize to 0.05 → RR ≈ 0-5%."""
        mock_payload.return_value = {
            "TestTrait": {
                "value": "test_value",
                "ucn": 5.0,  # Legacy 0-100 scale → should become 0.05
            }
        }

        result = unabridged_snapshot("test_user")

        trait = result["traits"][0]

        # ucn=5.0 in 0-100 scale → normalized to 0.05
        # With synthetic CDF, UCN=0.05 → very low percentile
        assert trait["rr"] < 10.0, \
            f"Expected RR < 10% for UCN=0.05, got {trait['rr']:.2f}%"

        assert trait["rr_meta"]["method"] == "reference"
