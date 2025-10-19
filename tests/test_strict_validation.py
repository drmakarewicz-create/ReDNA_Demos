"""
Tests for strict validation pipeline (Phase 1.3)

Verifies that EVIDENCE_STRICT and UCNRR_REQUIRED modes properly reject invalid
evidence and enforce UCNRR availability.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_evidence_validation_error_structure():
    """Test that EvidenceValidationError has correct attributes."""
    from ReDNACoreDemo.core.ingest.evidence_schema import EvidenceValidationError

    error = EvidenceValidationError(
        error_code="TEST_ERROR",
        message="Test message",
        evidence_sample={"foo": "bar"},
        suggestions=[{"hint": "Do this"}]
    )

    assert error.error_code == "TEST_ERROR"
    assert error.message == "Test message"
    assert error.evidence_sample == {"foo": "bar"}
    assert len(error.suggestions) == 1
    assert error.suggestions[0]["hint"] == "Do this"

    print("✓ EvidenceValidationError structure correct")


def test_strict_mode_rejects_missing_trait_id():
    """Test that strict mode raises error for missing trait_id."""
    from ReDNACoreDemo.core.ingest.evidence_schema import validate_and_fix, EvidenceValidationError

    invalid_evidence = {
        "value": {"enum": "blue"},
        "source": "test"
    }

    # Permissive mode should raise ValueError (legacy)
    with pytest.raises(ValueError):
        validate_and_fix(invalid_evidence, strict=False)

    # Strict mode should raise EvidenceValidationError
    with pytest.raises(EvidenceValidationError) as exc_info:
        validate_and_fix(invalid_evidence, strict=True)

    error = exc_info.value
    assert error.error_code == "MISSING_TRAIT_ID"
    assert "trait_id" in error.message.lower()
    assert len(error.suggestions) > 0

    print("✓ Strict mode rejects missing trait_id")


def test_strict_mode_rejects_missing_value():
    """Test that strict mode raises error for missing value."""
    from ReDNACoreDemo.core.ingest.evidence_schema import validate_and_fix, EvidenceValidationError

    invalid_evidence = {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "source": "test"
    }

    # Strict mode should raise EvidenceValidationError
    with pytest.raises(EvidenceValidationError) as exc_info:
        validate_and_fix(invalid_evidence, strict=True)

    error = exc_info.value
    assert error.error_code == "MISSING_VALUE"
    assert "value" in error.message.lower()
    assert len(error.suggestions) > 0

    print("✓ Strict mode rejects missing value")


def test_strict_mode_rejects_invalid_value_shape():
    """Test that strict mode validates value is properly typed."""
    from ReDNACoreDemo.core.ingest.evidence_schema import validate_and_fix, EvidenceValidationError

    # Value must be dict with enum/number/text
    invalid_evidence = {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": "blue",  # String, not dict
        "source": "test"
    }

    # This should actually pass because normalize_value converts it
    # Let me test with a dict that has wrong keys
    invalid_evidence2 = {
        "trait_id": "PaDNA.EyeDNA.IrisColor",
        "value": {"wrong_key": "blue"},
        "source": "test"
    }

    with pytest.raises(EvidenceValidationError) as exc_info:
        validate_and_fix(invalid_evidence2, strict=True)

    error = exc_info.value
    assert error.error_code == "INVALID_VALUE_SHAPE"
    assert "enum" in error.message or "number" in error.message or "text" in error.message

    print("✓ Strict mode rejects invalid value shape")


def test_ucnrr_required_error_structure():
    """Test that UCNRRRequiredError has correct attributes."""
    from ReDNACoreDemo.core.resolver.impl import UCNRRRequiredError

    original_error = Exception("Connection refused")
    error = UCNRRRequiredError(
        message="UCNRR unavailable",
        rr_error=original_error
    )

    assert error.message == "UCNRR unavailable"
    assert error.rr_error == original_error

    print("✓ UCNRRRequiredError structure correct")


def test_resolver_raises_ucnrr_required_error_when_ucnrr_down():
    """Test that resolver raises UCNRRRequiredError in UCNRR_REQUIRED mode."""
    from ReDNACoreDemo.core.resolver.impl import resolve_roundtrip, UCNRRRequiredError
    from ReDNACoreDemo.core.rr.client import score_ucn

    # Mock score_ucn to fail
    with patch("ReDNACoreDemo.core.rr.client.score_ucn") as mock_score:
        mock_score.side_effect = Exception("UCNRR connection failed")

        # Set UCNRR_REQUIRED mode
        with patch.dict(os.environ, {"UCNRR_REQUIRED": "true"}):
            evidence = [
                {
                    "trait_id": "PaDNA.EyeDNA.IrisColor",
                    "value": {"enum": "blue"},
                    "ucn_prior": 0.8,
                    "source": "test"
                }
            ]

            # Should raise UCNRRRequiredError
            with pytest.raises(UCNRRRequiredError) as exc_info:
                resolve_roundtrip("TEST_USER", evidence, "test")

            error = exc_info.value
            assert "unavailable" in error.message.lower() or "required" in error.message.lower()

    print("✓ Resolver raises UCNRRRequiredError when UCNRR down in required mode")


def test_resolver_falls_back_to_priors_in_permissive_mode():
    """Test that resolver uses priors when UCNRR down in permissive mode."""
    from ReDNACoreDemo.core.resolver.impl import resolve_roundtrip

    # Mock score_ucn to fail
    with patch("ReDNACoreDemo.core.rr.client.score_ucn") as mock_score:
        mock_score.side_effect = Exception("UCNRR connection failed")

        # Set permissive mode (UCNRR_REQUIRED=false)
        with patch.dict(os.environ, {"UCNRR_REQUIRED": "false"}, clear=False):
            evidence = [
                {
                    "trait_id": "PaDNA.EyeDNA.IrisColor",
                    "value": {"enum": "blue"},
                    "ucn_prior": 0.75,
                    "source": "test"
                }
            ]

            # Should NOT raise, should use fallback
            result = resolve_roundtrip("TEST_USER", evidence, "test")

            # Verify result structure
            assert "resolved" in result
            assert "rr_ok" in result
            assert result["rr_ok"] is False  # RR failed, used fallback

            # Verify UCN fell back to prior
            resolved = result["resolved"]
            if "PaDNA.EyeDNA.IrisColor" in resolved:
                ucn = resolved["PaDNA.EyeDNA.IrisColor"]["ucn"]
                assert 0.7 <= ucn <= 0.8, f"UCN should be near prior (0.75), got {ucn}"

    print("✓ Resolver falls back to priors in permissive mode")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # Run tests
    print("Running Strict Validation Tests\n")

    try:
        test_evidence_validation_error_structure()
        test_strict_mode_rejects_missing_trait_id()
        test_strict_mode_rejects_missing_value()
        test_strict_mode_rejects_invalid_value_shape()
        test_ucnrr_required_error_structure()
        test_resolver_raises_ucnrr_required_error_when_ucnrr_down()
        test_resolver_falls_back_to_priors_in_permissive_mode()

        print("\n✅ All strict validation tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
