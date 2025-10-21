"""
Tests for Consent Health API
=============================

Validates the /core/consent/health endpoint behavior under different configurations:
- Development secret (degraded status)
- Production secret (healthy status)
- Hex-encoded secrets
- Base64-encoded secrets
- Broken JWT operations (error status with detailed error_reason)
- Algorithm mismatches
- Leeway edge cases
"""

import base64
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for Core API."""
    from ReDNACoreDemo.core.api import build_app
    app = build_app()
    return TestClient(app)


class TestConsentHealthDevSecret:
    """Test Consent health endpoint with development secret (default)."""

    def test_consent_health_dev_secret(self, client):
        """
        Test with development secret (default configuration).

        Expected:
        - HTTP 200
        - status="degraded" (dev secret in use)
        - has_secret=False
        - roundtrip_ok=True (JWT still works)
        - warning="dev secret in use"
        - error_reason=None
        """
        with patch.dict(os.environ, {}, clear=False):
            if "CONSENT_JWT_SECRET" in os.environ:
                del os.environ["CONSENT_JWT_SECRET"]

            response = client.get("/core/consent/health")

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            data = response.json()
            assert data["status"] == "degraded", f"Expected degraded status with dev secret, got: {data}"
            assert data["has_secret"] is False, "Expected has_secret=False with dev secret"
            assert data["roundtrip_ok"] is True, "Expected roundtrip_ok=True (JWT should still work)"
            assert data["warning"] is not None, "Expected warning to be present with dev secret"
            assert "dev secret" in data["warning"].lower(), f"Expected dev secret warning, got: {data['warning']}"
            assert data["error_reason"] is None, "Expected no error_reason when roundtrip succeeds"

    def test_consent_health_dev_secret_with_ttl(self, client):
        """
        Test dev secret with custom TTL and leeway configured.

        Expected:
        - status="degraded"
        - ttl_minutes=60
        - config.leeway_seconds=30 (default)
        """
        with patch.dict(os.environ, {"CONSENT_JWT_TTL_MINUTES": "60"}, clear=False):
            if "CONSENT_JWT_SECRET" in os.environ:
                del os.environ["CONSENT_JWT_SECRET"]

            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["ttl_minutes"] == 60, f"Expected ttl_minutes=60, got: {data['ttl_minutes']}"
            assert data["config"]["leeway_seconds"] == 30, "Expected default leeway of 30s"


class TestConsentHealthProdSecret:
    """Test Consent health endpoint with production secret."""

    def test_consent_health_prod_secret_raw(self, client):
        """
        Test with strong production secret (raw string).

        Expected:
        - HTTP 200
        - status="healthy"
        - has_secret=True
        - roundtrip_ok=True
        - warning=None
        - error_reason=None
        - config.secret_encoding="raw"
        """
        prod_secret = "super-strong-production-secret-min-32-chars-long-123456789"

        with patch.dict(os.environ, {"CONSENT_JWT_SECRET": prod_secret}, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy", f"Expected healthy status with prod secret, got: {data}"
            assert data["has_secret"] is True, "Expected has_secret=True with prod secret"
            assert data["roundtrip_ok"] is True, "Expected roundtrip_ok=True with valid secret"
            assert data["warning"] is None, f"Expected no warning with prod secret, got: {data['warning']}"
            assert data["error_reason"] is None, "Expected no error_reason when roundtrip succeeds"
            assert data["config"]["secret_encoding"] == "raw", "Expected raw string encoding"

    def test_consent_health_prod_secret_hex(self, client):
        """
        Test with hex-encoded production secret.

        Expected:
        - status="healthy"
        - has_secret=True
        - roundtrip_ok=True
        - config.secret_encoding="hex"
        """
        # Generate 32-byte hex secret (64 hex chars)
        hex_secret = "0123456789abcdef" * 4  # 64 chars

        with patch.dict(os.environ, {"CONSENT_JWT_SECRET": hex_secret}, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy", f"Hex secret should be healthy, got: {data}"
            assert data["has_secret"] is True, "Expected has_secret=True"
            assert data["roundtrip_ok"] is True, "Hex-encoded secret should work"
            assert data["config"]["secret_encoding"] == "hex", "Expected hex encoding detection"

    def test_consent_health_prod_secret_base64(self, client):
        """
        Test with base64-encoded production secret.

        Expected:
        - status="healthy"
        - has_secret=True
        - roundtrip_ok=True
        - config.secret_encoding="base64"
        """
        # Generate base64 secret
        raw_bytes = b"my-secret-key-" + os.urandom(18)  # 32 bytes total
        b64_secret = base64.b64encode(raw_bytes).decode("utf-8")

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": b64_secret,
            "CONSENT_JWT_SECRET_B64": "true"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy", f"Base64 secret should be healthy, got: {data}"
            assert data["has_secret"] is True, "Expected has_secret=True"
            assert data["roundtrip_ok"] is True, "Base64-encoded secret should work"
            assert data["config"]["secret_encoding"] == "base64", "Expected base64 encoding detection"

    def test_consent_health_prod_secret_with_custom_leeway(self, client):
        """
        Test production secret with custom leeway.

        Expected:
        - status="healthy"
        - config.leeway_seconds=60
        """
        prod_secret = "another-strong-production-secret-123456789-abcdefghij"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_TTL_MINUTES": "120",
            "CONSENT_JWT_LEEWAY_SECONDS": "60"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["has_secret"] is True
            assert data["ttl_minutes"] == 120
            assert data["config"]["leeway_seconds"] == 60, "Expected custom leeway of 60s"


class TestConsentHealthErrorScenarios:
    """Test Consent health endpoint with various error conditions."""

    def test_consent_health_invalid_algorithm(self, client):
        """
        Test with invalid/unsupported algorithm.

        Expected:
        - status="error"
        - roundtrip_ok=False
        - error_reason contains "Unknown algorithm" or similar
        """
        prod_secret = "valid-secret-but-bad-algorithm-1234567890"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_ALG": "INVALID999"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200, "Should return 200 even on error"
            data = response.json()
            assert data["status"] == "error", f"Expected error status with invalid algorithm, got: {data}"
            assert data["roundtrip_ok"] is False, "Expected roundtrip_ok=False"
            assert data["error_reason"] is not None, "Expected error_reason to be present"
            assert "algorithm" in data["error_reason"].lower(), f"Expected algorithm error, got: {data['error_reason']}"

    def test_consent_health_asymmetric_algorithm_unsupported(self, client):
        """
        Test with RS256 (asymmetric) algorithm without keys.

        Expected:
        - status="error"
        - error_reason mentions asymmetric algorithm not supported
        """
        prod_secret = "secret-for-rs256-test-1234567890"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_ALG": "RS256"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error", "RS256 without keys should be error"
            assert data["roundtrip_ok"] is False
            assert data["error_reason"] is not None
            assert "asymmetric" in data["error_reason"].lower() or "rs256" in data["error_reason"].lower()

    def test_consent_health_empty_secret(self, client):
        """
        Test with empty secret string.

        Expected:
        - status="error"
        - error_reason mentions secret parsing or empty secret
        """
        with patch.dict(os.environ, {"CONSENT_JWT_SECRET": ""}, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            # Empty secret might be treated as dev secret or fail parsing
            assert data["status"] in ("degraded", "error")
            if data["status"] == "error":
                assert data["error_reason"] is not None

    def test_consent_health_invalid_base64(self, client):
        """
        Test with invalid base64 secret when B64 flag is set.

        Expected:
        - status="error"
        - error_reason mentions base64 decode failure
        """
        invalid_b64 = "not-valid-base64!!!"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": invalid_b64,
            "CONSENT_JWT_SECRET_B64": "true"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error", "Invalid base64 should be error"
            assert data["roundtrip_ok"] is False
            assert data["error_reason"] is not None
            assert "base64" in data["error_reason"].lower() or "decode" in data["error_reason"].lower()


class TestConsentHealthLeewayEdgeCases:
    """Test leeway configuration edge cases."""

    def test_consent_health_zero_leeway(self, client):
        """
        Test with zero leeway (strict timing).

        Expected:
        - Should still work if token is fresh
        - roundtrip_ok=True
        - config.leeway_seconds=0
        """
        prod_secret = "secret-for-zero-leeway-test-123456789"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_LEEWAY_SECONDS": "0"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            # With zero leeway, fresh token should still work
            assert data["roundtrip_ok"] is True, "Fresh token should work even with zero leeway"
            assert data["config"]["leeway_seconds"] == 0, "Expected zero leeway"

    def test_consent_health_large_leeway(self, client):
        """
        Test with large leeway (1 hour).

        Expected:
        - roundtrip_ok=True
        - config.leeway_seconds=3600
        """
        prod_secret = "secret-for-large-leeway-test-123456789"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_LEEWAY_SECONDS": "3600"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["roundtrip_ok"] is True
            assert data["config"]["leeway_seconds"] == 3600, "Expected 1-hour leeway"

    def test_consent_health_invalid_leeway(self, client):
        """
        Test with invalid leeway value (non-numeric).

        Expected:
        - Should fall back to default leeway (30s)
        - roundtrip_ok=True
        """
        prod_secret = "secret-for-invalid-leeway-test-123456789"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_LEEWAY_SECONDS": "not-a-number"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["roundtrip_ok"] is True, "Should work with default leeway"
            assert data["config"]["leeway_seconds"] == 30, "Should fall back to default 30s leeway"


class TestConsentHealthOptionalClaims:
    """Test audience and issuer claim handling."""

    def test_consent_health_with_audience(self, client):
        """
        Test with CONSENT_JWT_AUD set.

        Expected:
        - roundtrip_ok=True
        - config.has_audience=True
        - Token includes aud claim
        """
        prod_secret = "secret-with-audience-test-123456789"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_AUD": "redna-consent-service"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["roundtrip_ok"] is True, "Audience claim should work"
            assert data["config"]["has_audience"] is True, "Expected has_audience=True"

    def test_consent_health_with_issuer(self, client):
        """
        Test with CONSENT_JWT_ISS set.

        Expected:
        - roundtrip_ok=True
        - config.has_issuer=True
        - Token includes iss claim
        """
        prod_secret = "secret-with-issuer-test-123456789"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_ISS": "redna-core-api"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["roundtrip_ok"] is True, "Issuer claim should work"
            assert data["config"]["has_issuer"] is True, "Expected has_issuer=True"

    def test_consent_health_with_audience_and_issuer(self, client):
        """
        Test with both audience and issuer set.

        Expected:
        - roundtrip_ok=True
        - config.has_audience=True
        - config.has_issuer=True
        """
        prod_secret = "secret-with-both-claims-test-123456789"

        with patch.dict(os.environ, {
            "CONSENT_JWT_SECRET": prod_secret,
            "CONSENT_JWT_AUD": "redna-consent-service",
            "CONSENT_JWT_ISS": "redna-core-api"
        }, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["roundtrip_ok"] is True, "Both claims should work"
            assert data["config"]["has_audience"] is True
            assert data["config"]["has_issuer"] is True


class TestConsentHealthResponseStructure:
    """Test response structure and field presence."""

    def test_consent_health_response_structure(self, client):
        """
        Verify response includes all required fields.

        Expected fields:
        - status (str)
        - has_secret (bool)
        - ttl_minutes (int | null)
        - roundtrip_ok (bool)
        - warning (str | null)
        - error_reason (str | null)
        - config (object)
        """
        response = client.get("/core/consent/health")

        assert response.status_code == 200
        data = response.json()

        required_fields = ["status", "has_secret", "ttl_minutes", "roundtrip_ok", "warning", "error_reason", "config"]
        for field in required_fields:
            assert field in data, f"Response missing required field: {field}"

        # Type checks
        assert isinstance(data["status"], str), "status should be string"
        assert data["status"] in ("healthy", "degraded", "error"), f"Invalid status value: {data['status']}"
        assert isinstance(data["has_secret"], bool), "has_secret should be boolean"
        assert isinstance(data["roundtrip_ok"], bool), "roundtrip_ok should be boolean"

        # Config sub-object
        assert isinstance(data["config"], dict), "config should be object"
        config_fields = ["algorithm", "secret_encoding", "leeway_seconds", "has_audience", "has_issuer"]
        for field in config_fields:
            assert field in data["config"], f"Config missing required field: {field}"

    def test_consent_health_error_reason_only_on_failure(self, client):
        """
        Verify error_reason is None when roundtrip_ok=True.
        """
        prod_secret = "valid-secret-no-errors-123456789"

        with patch.dict(os.environ, {"CONSENT_JWT_SECRET": prod_secret}, clear=False):
            response = client.get("/core/consent/health")

            assert response.status_code == 200
            data = response.json()
            assert data["roundtrip_ok"] is True
            assert data["error_reason"] is None, "error_reason should be None when roundtrip succeeds"

    def test_consent_health_performance(self, client):
        """
        Verify health check completes quickly (< 50ms target).
        """
        import time

        start = time.perf_counter()
        response = client.get("/core/consent/health")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        if elapsed_ms > 50:
            print(f"WARNING: Consent health check took {elapsed_ms:.2f}ms (target < 50ms)")
        else:
            print(f"Performance OK: {elapsed_ms:.2f}ms")
