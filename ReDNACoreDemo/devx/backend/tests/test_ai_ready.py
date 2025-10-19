"""
Tests for AI Readiness Probe

Tests the /devx/api/ingestion/ai_ready endpoint across various scenarios:
- Happy path: all services green
- UCNRR offline: ucnrr=red, result=NEEDS-FIX
- Core unavailable: core=red
- E2E disabled: no e2e test
- Timeouts: clean error handling
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import Response, TimeoutException

from ReDNACoreDemo.devx.backend.ai_ready import (
    probe_devx_health,
    probe_ucnrr_health,
    probe_core_health,
    probe_core_e2e,
    run_ai_readiness_probe,
    diagnose_devx_layer,
    diagnose_ucnrr_layer,
    diagnose_core_layer,
    diagnose_core_e2e_layer,
    AiReadyLight,
    AiReadyResponse,
    LayerDiagnosticResponse,
)


# Happy Path Tests

@pytest.mark.asyncio
async def test_probe_devx_health_green():
    """Test DevX health probe returns green when healthy."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await probe_devx_health()

        assert result.status == "green"
        assert result.details == {"status": "healthy"}
        assert result.reason is None


@pytest.mark.asyncio
async def test_probe_ucnrr_health_green():
    """Test UCNRR health probe returns green when LLM configured."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "llm_configured": True,
        "llm_provider": "ollama",
        "llm_model": "phi3:mini"
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await probe_ucnrr_health()

        assert result.status == "green"
        assert result.details["llm_configured"] is True
        assert result.details["llm_provider"] == "ollama"
        assert result.details["llm_model"] == "phi3:mini"
        assert result.reason is None


@pytest.mark.asyncio
async def test_probe_core_health_green():
    """Test Core health probe returns green when online and UCNRR enabled."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "rr_mode": "online",
        "features": {"ucnrr_enabled": True}
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await probe_core_health()

        assert result.status == "green"
        assert result.details["rr_mode"] == "online"
        assert result.details["ucnrr_enabled"] is True
        assert result.reason is None


# Red Status Tests

@pytest.mark.asyncio
async def test_probe_ucnrr_health_red_not_configured():
    """Test UCNRR health probe returns red when LLM not configured."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "llm_configured": False,
        "llm_provider": "none",
        "llm_model": "none"
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await probe_ucnrr_health()

        assert result.status == "red"
        assert result.details["llm_configured"] is False
        assert result.reason == "UCNRR is not LLM-configured (llm_configured=false)"


@pytest.mark.asyncio
async def test_probe_core_health_red_offline():
    """Test Core health probe returns red when rr_mode offline."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "rr_mode": "offline",
        "features": {"ucnrr_enabled": True}
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await probe_core_health()

        assert result.status == "red"
        assert result.details["rr_mode"] == "offline"
        assert "rr_mode is 'offline'" in result.reason


@pytest.mark.asyncio
async def test_probe_core_health_red_ucnrr_disabled():
    """Test Core health probe returns red when UCNRR disabled."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "rr_mode": "online",
        "features": {"ucnrr_enabled": False}
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await probe_core_health()

        assert result.status == "red"
        assert result.details["ucnrr_enabled"] is False
        assert "ucnrr_enabled is false" in result.reason


# Timeout Tests

@pytest.mark.asyncio
async def test_probe_devx_health_timeout():
    """Test DevX health probe handles timeout gracefully."""
    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=TimeoutException("Timeout"))

        result = await probe_devx_health()

        assert result.status == "red"
        assert "timeout" in result.reason.lower()


@pytest.mark.asyncio
async def test_probe_ucnrr_health_timeout():
    """Test UCNRR health probe handles timeout gracefully."""
    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=TimeoutException("Timeout"))

        result = await probe_ucnrr_health()

        assert result.status == "red"
        assert "timeout" in result.reason.lower()


# E2E Probe Tests

@pytest.mark.asyncio
async def test_probe_core_e2e_disabled():
    """Test E2E probe when disabled via environment variable."""
    with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_ENABLE_E2E", False):
        result = await probe_core_e2e()

        assert result.status == "red"
        assert result.details["enabled"] is False
        assert "disabled" in result.reason.lower()


@pytest.mark.asyncio
async def test_probe_core_e2e_no_write_mode():
    """Test E2E probe in no-write mode."""
    with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_NO_WRITE", True):
        with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_ENABLE_E2E", True):
            result = await probe_core_e2e()

            assert result.status == "green"
            assert result.details["no_write_mode"] is True
            assert result.details["skipped"] is True


@pytest.mark.asyncio
async def test_probe_core_e2e_green():
    """Test E2E probe returns green when promotion and Why-Card work."""
    # Mock ingest_text response
    ingest_response = AsyncMock(spec=Response)
    ingest_response.status_code = 200
    ingest_response.json.return_value = {
        "rescore": {
            "rr_by_trait": {
                "BehaviorDNA.Sleep.Chronotype": 800.0
            }
        }
    }

    # Mock why-card response
    why_response = AsyncMock(spec=Response)
    why_response.status_code = 200
    why_response.json.return_value = {
        "why": "Promotion threshold met (rr=800.0) from text: I am a morning person, up before sunrise."
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_http = mock_client.return_value.__aenter__.return_value
        mock_http.post = AsyncMock(return_value=ingest_response)
        mock_http.get = AsyncMock(return_value=why_response)

        with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_ENABLE_E2E", True):
            with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_NO_WRITE", False):
                result = await probe_core_e2e()

                assert result.status == "green"
                assert result.details["rescore_rr"] == 800.0
                assert "why_excerpt" in result.details
                assert result.reason is None


@pytest.mark.asyncio
async def test_probe_core_e2e_red_no_chronotype():
    """Test E2E probe returns red when Chronotype not in rescore."""
    ingest_response = AsyncMock(spec=Response)
    ingest_response.status_code = 200
    ingest_response.json.return_value = {
        "rescore": {
            "rr_by_trait": {}  # No Chronotype
        }
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=ingest_response)

        with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_ENABLE_E2E", True):
            with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_NO_WRITE", False):
                result = await probe_core_e2e()

                assert result.status == "red"
                assert "Chronotype not found" in result.reason


@pytest.mark.asyncio
async def test_probe_core_e2e_red_empty_why():
    """Test E2E probe returns red when Why-Card is empty."""
    ingest_response = AsyncMock(spec=Response)
    ingest_response.status_code = 200
    ingest_response.json.return_value = {
        "rescore": {
            "rr_by_trait": {
                "BehaviorDNA.Sleep.Chronotype": 800.0
            }
        }
    }

    why_response = AsyncMock(spec=Response)
    why_response.status_code = 200
    why_response.json.return_value = {"why": ""}  # Empty Why-Card

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_http = mock_client.return_value.__aenter__.return_value
        mock_http.post = AsyncMock(return_value=ingest_response)
        mock_http.get = AsyncMock(return_value=why_response)

        with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_ENABLE_E2E", True):
            with patch("ReDNACoreDemo.devx.backend.ai_ready.AI_READY_NO_WRITE", False):
                result = await probe_core_e2e()

                assert result.status == "red"
                assert "Why-Card is empty" in result.reason


# Integration Test

@pytest.mark.asyncio
async def test_run_ai_readiness_probe_all_green():
    """Test full AI readiness probe when all services are green."""
    # Mock all health checks to return green
    with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_devx_health") as mock_devx:
        with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_ucnrr_health") as mock_ucnrr:
            with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_core_health") as mock_core:
                with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_core_e2e") as mock_e2e:
                    mock_devx.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")
                    mock_ucnrr.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")
                    mock_core.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")
                    mock_e2e.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")

                    result = await run_ai_readiness_probe()

                    assert result.result == "ALL-GOOD"
                    assert result.hc_devx.status == "green"
                    assert result.ucnrr.status == "green"
                    assert result.core.status == "green"


@pytest.mark.asyncio
async def test_run_ai_readiness_probe_ucnrr_red():
    """Test full AI readiness probe when UCNRR is red."""
    with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_devx_health") as mock_devx:
        with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_ucnrr_health") as mock_ucnrr:
            with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_core_health") as mock_core:
                mock_devx.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")
                mock_ucnrr.return_value = AiReadyLight(
                    status="red",
                    ts="2025-01-01T00:00:00",
                    reason="UCNRR not LLM-configured"
                )
                mock_core.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")

                result = await run_ai_readiness_probe()

                assert result.result == "NEEDS-FIX"
                assert result.ucnrr.status == "red"
                assert "UCNRR not LLM-configured" in result.ucnrr.reason


@pytest.mark.asyncio
async def test_run_ai_readiness_probe_core_unavailable():
    """Test full AI readiness probe when Core is unavailable."""
    with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_devx_health") as mock_devx:
        with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_ucnrr_health") as mock_ucnrr:
            with patch("ReDNACoreDemo.devx.backend.ai_ready.probe_core_health") as mock_core:
                mock_devx.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")
                mock_ucnrr.return_value = AiReadyLight(status="green", ts="2025-01-01T00:00:00")
                mock_core.return_value = AiReadyLight(
                    status="red",
                    ts="2025-01-01T00:00:00",
                    reason="Core health check timeout"
                )

                result = await run_ai_readiness_probe()

                assert result.result == "NEEDS-FIX"
                assert result.core.status == "red"
                assert "timeout" in result.core.reason.lower()


# Layer-Specific Diagnostic Tests

@pytest.mark.asyncio
async def test_diagnose_devx_layer_green():
    """Test DevX layer diagnostic returns green when healthy."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}
    mock_response.elapsed.total_seconds.return_value = 0.05

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await diagnose_devx_layer(verbose=True)

        assert result.layer == "devx"
        assert result.status == "green"
        assert result.details["status"] == "healthy"
        assert len(result.suggestions) == 0
        assert result.verbose_data is not None
        assert "response_time_ms" in result.verbose_data


@pytest.mark.asyncio
async def test_diagnose_devx_layer_fallback_to_health():
    """Test DevX layer diagnostic falls back to /health when /devx/api/health fails."""
    mock_response_fallback = AsyncMock(spec=Response)
    mock_response_fallback.status_code = 200
    mock_response_fallback.json.return_value = {"status": "healthy"}
    mock_response_fallback.elapsed.total_seconds.return_value = 0.05

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        async def mock_get(url, **kwargs):
            if "/devx/api/health" in url:
                raise TimeoutException("Timeout")
            return mock_response_fallback

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=mock_get)

        result = await diagnose_devx_layer(verbose=True)

        assert result.status == "green"
        assert result.verbose_data["used_fallback_endpoint"] is True


@pytest.mark.asyncio
async def test_diagnose_ucnrr_layer_green_with_ollama():
    """Test UCNRR layer diagnostic returns green and includes Ollama probe in verbose mode."""
    mock_health_response = AsyncMock(spec=Response)
    mock_health_response.status_code = 200
    mock_health_response.json.return_value = {
        "status": "healthy",
        "llm_configured": True,
        "llm_provider": "ollama",
        "llm_model": "phi3:mini",
        "ollama_base_url": "http://127.0.0.1:11434"
    }
    mock_health_response.elapsed.total_seconds.return_value = 0.05

    mock_tags_response = AsyncMock(spec=Response)
    mock_tags_response.status_code = 200
    mock_tags_response.json.return_value = {
        "models": [
            {"name": "phi3:mini"},
            {"name": "llama3.1:8b"}
        ]
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        async def mock_get(url, **kwargs):
            if "/api/tags" in url:
                return mock_tags_response
            return mock_health_response

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=mock_get)

        result = await diagnose_ucnrr_layer(verbose=True)

        assert result.layer == "ucnrr"
        assert result.status == "green"
        assert result.details["llm_configured"] is True
        assert result.verbose_data["ollama_tags_ok"] is True
        assert "phi3:mini" in result.verbose_data["ollama_models"]
        assert len(result.suggestions) == 0


@pytest.mark.asyncio
async def test_diagnose_ucnrr_layer_red_not_configured():
    """Test UCNRR layer diagnostic returns red with suggestions when LLM not configured."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "llm_configured": False,
        "llm_provider": "none"
    }
    mock_response.elapsed.total_seconds.return_value = 0.05

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await diagnose_ucnrr_layer(verbose=False)

        assert result.status == "red"
        assert "not LLM-configured" in result.reason
        assert len(result.suggestions) > 0
        assert any("LLM_PROVIDER" in s for s in result.suggestions)


@pytest.mark.asyncio
async def test_diagnose_core_layer_green_with_promotion_state():
    """Test Core layer diagnostic returns green and includes promotion_state in verbose mode."""
    mock_health_response = AsyncMock(spec=Response)
    mock_health_response.status_code = 200
    mock_health_response.json.return_value = {
        "status": "healthy",
        "rr_mode": "online",
        "features": {"ucnrr_enabled": True}
    }
    mock_health_response.elapsed.total_seconds.return_value = 0.05

    mock_promo_response = AsyncMock(spec=Response)
    mock_promo_response.status_code = 200
    mock_promo_response.json.return_value = {
        "policies": [
            {"trait_id": "BehaviorDNA.Sleep.Chronotype", "threshold": 700.0, "enabled": True}
        ]
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        async def mock_get(url, **kwargs):
            if "promotion_state" in url:
                return mock_promo_response
            return mock_health_response

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=mock_get)

        result = await diagnose_core_layer(verbose=True)

        assert result.layer == "core"
        assert result.status == "green"
        assert result.details["rr_mode"] == "online"
        assert result.verbose_data is not None
        assert "promotion_state" in result.verbose_data


@pytest.mark.asyncio
async def test_diagnose_core_layer_red_offline():
    """Test Core layer diagnostic returns red with suggestions when rr_mode is offline."""
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "rr_mode": "offline",
        "features": {"ucnrr_enabled": True}
    }
    mock_response.elapsed.total_seconds.return_value = 0.05

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await diagnose_core_layer(verbose=False)

        assert result.status == "red"
        assert "offline" in result.reason
        assert len(result.suggestions) > 0
        assert any("RR_MODE=online" in s for s in result.suggestions)


@pytest.mark.asyncio
async def test_diagnose_core_e2e_layer_green_with_timing():
    """Test Core E2E layer diagnostic returns green and includes timing breakdown in verbose mode."""
    mock_ingest_response = AsyncMock(spec=Response)
    mock_ingest_response.status_code = 200
    mock_ingest_response.json.return_value = {
        "rescore": {
            "rr_by_trait": {"BehaviorDNA.Sleep.Chronotype": 800.0}
        }
    }

    mock_why_response = AsyncMock(spec=Response)
    mock_why_response.status_code = 200
    mock_why_response.json.return_value = {
        "why": "Promotion threshold met (rr=800.0) from test phrase"
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        async def mock_post_get(url, **kwargs):
            if "ingest_text" in url:
                return mock_ingest_response
            return mock_why_response

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_ingest_response)
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_why_response)

        result = await diagnose_core_e2e_layer(verbose=True, no_write=False)

        assert result.layer == "core_e2e"
        assert result.status == "green"
        assert result.details["rescore_rr"] == 800.0
        assert result.verbose_data is not None
        assert "ingest_duration_ms" in result.verbose_data
        assert "why_full_text" in result.verbose_data


@pytest.mark.asyncio
async def test_diagnose_core_e2e_layer_red_no_chronotype():
    """Test Core E2E layer diagnostic returns red with suggestions when Chronotype not extracted."""
    mock_ingest_response = AsyncMock(spec=Response)
    mock_ingest_response.status_code = 200
    mock_ingest_response.json.return_value = {
        "rescore": {
            "rr_by_trait": {}
        }
    }

    with patch("ReDNACoreDemo.devx.backend.ai_ready.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_ingest_response)

        result = await diagnose_core_e2e_layer(verbose=False, no_write=False)

        assert result.status == "red"
        assert "Chronotype" in result.reason
        assert len(result.suggestions) > 0
        assert any("UCNRR" in s for s in result.suggestions)
