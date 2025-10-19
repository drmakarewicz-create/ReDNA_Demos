"""
AI Readiness Probe

Checks if all three AI ingestion layers are operational:
1. HC/DevX Backend (Northstar intake)
2. UCNRR Processing (LLM configured & responding)
3. Core Processing (resolver online, promotion + Why-Card)

Returns traffic-light status (green/red) for each layer with diagnostic details.
"""

import os
import time
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel
import httpx


# Configuration from environment
AI_READY_PROBE_USER = os.getenv("AI_READY_PROBE_USER", "ai_ready_probe")
AI_READY_PROBE_TEXT = os.getenv("AI_READY_PROBE_TEXT", "I am a morning person, up before sunrise.")
AI_READY_TIMEOUT_MS = int(os.getenv("AI_READY_TIMEOUT_MS", "1500"))
AI_READY_ENABLE_E2E = os.getenv("AI_READY_ENABLE_E2E", "true").lower() in ("true", "1", "yes")
AI_READY_NO_WRITE = os.getenv("AI_READY_NO_WRITE", "false").lower() in ("true", "1", "yes")

# Service URLs
CORE_BASE = os.getenv("DEVX_CORE_BASE", "http://127.0.0.1:8004")
UCNRR_BASE = os.getenv("DEVX_UCNRR_BASE", "http://127.0.0.1:8017")
DEVX_BASE = os.getenv("DEVX_BASE", "http://127.0.0.1:8012")

# Timeout for HTTP requests (in seconds)
TIMEOUT_SEC = AI_READY_TIMEOUT_MS / 1000.0


class AiReadyLight(BaseModel):
    """Traffic light indicator for a service layer."""
    status: Literal["green", "red"]
    details: Optional[Dict[str, Any]] = None
    ts: str
    reason: Optional[str] = None  # Why it's red (if applicable)


class AiReadyResponse(BaseModel):
    """Complete AI readiness probe response."""
    hc_devx: AiReadyLight
    ucnrr: AiReadyLight
    core: AiReadyLight
    result: Literal["ALL-GOOD", "NEEDS-FIX"]
    probe_duration_ms: int
    ts: str


async def probe_devx_health() -> AiReadyLight:
    """
    Probe DevX backend health (HC/DevX intake layer).

    Since this function runs inside the DevX backend itself, it assumes the service
    is healthy if the code is executing. This is the Northstar intake layer.

    Returns:
        Always green (if this code is running, DevX is operational)
    """
    # Phase 7: DevX backend checks itself - if we're executing, we're healthy
    # No self-referential HTTP calls needed
    return AiReadyLight(
        status="green",
        details={
            "status": "healthy",
            "service": "devx-backend",
            "note": "Self-check: service is operational"
        },
        ts=datetime.now().isoformat()
    )


async def probe_ucnrr_health() -> AiReadyLight:
    """
    Probe UCNRR health and LLM configuration.

    Returns:
        Green if llm_configured=true
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            resp = await client.get(f"{UCNRR_BASE}/health")

            if resp.status_code == 200:
                data = resp.json()
                llm_configured = data.get("llm_configured", False)
                llm_provider = data.get("llm_provider", "unknown")
                llm_model = data.get("llm_model", "unknown")

                details = {
                    "llm_configured": llm_configured,
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                    "status": data.get("status", "unknown")
                }

                if llm_configured:
                    return AiReadyLight(
                        status="green",
                        details=details,
                        ts=datetime.now().isoformat()
                    )
                else:
                    return AiReadyLight(
                        status="red",
                        details=details,
                        ts=datetime.now().isoformat(),
                        reason="UCNRR is not LLM-configured (llm_configured=false)"
                    )
            else:
                return AiReadyLight(
                    status="red",
                    details={"http_status": resp.status_code},
                    ts=datetime.now().isoformat(),
                    reason=f"UCNRR health check returned HTTP {resp.status_code}"
                )

    except httpx.TimeoutException:
        return AiReadyLight(
            status="red",
            details={},
            ts=datetime.now().isoformat(),
            reason=f"UCNRR health check timeout ({TIMEOUT_SEC}s)"
        )
    except Exception as e:
        return AiReadyLight(
            status="red",
            details={"error": str(e)},
            ts=datetime.now().isoformat(),
            reason=f"UCNRR health check failed: {str(e)}"
        )


async def probe_core_health() -> AiReadyLight:
    """
    Probe Core service health.

    Returns:
        Green if rr_mode="online" and ucnrr_enabled=true
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            resp = await client.get(f"{CORE_BASE}/health")

            if resp.status_code == 200:
                data = resp.json()
                rr_mode = data.get("rr_mode", "unknown")
                features = data.get("features", {})
                ucnrr_enabled = features.get("ucnrr_enabled", False)

                details = {
                    "rr_mode": rr_mode,
                    "ucnrr_enabled": ucnrr_enabled,
                    "status": data.get("status", "unknown")
                }

                # Green if both conditions met
                if rr_mode == "online" and ucnrr_enabled:
                    return AiReadyLight(
                        status="green",
                        details=details,
                        ts=datetime.now().isoformat()
                    )
                else:
                    reasons = []
                    if rr_mode != "online":
                        reasons.append(f"rr_mode is '{rr_mode}', expected 'online'")
                    if not ucnrr_enabled:
                        reasons.append("ucnrr_enabled is false")

                    return AiReadyLight(
                        status="red",
                        details=details,
                        ts=datetime.now().isoformat(),
                        reason="; ".join(reasons)
                    )
            else:
                return AiReadyLight(
                    status="red",
                    details={"http_status": resp.status_code},
                    ts=datetime.now().isoformat(),
                    reason=f"Core health check returned HTTP {resp.status_code}"
                )

    except httpx.TimeoutException:
        return AiReadyLight(
            status="red",
            details={},
            ts=datetime.now().isoformat(),
            reason=f"Core health check timeout ({TIMEOUT_SEC}s)"
        )
    except Exception as e:
        return AiReadyLight(
            status="red",
            details={"error": str(e)},
            ts=datetime.now().isoformat(),
            reason=f"Core health check failed: {str(e)}"
        )


async def probe_core_e2e() -> AiReadyLight:
    """
    End-to-end probe: ingest test phrase and verify promotion + Why-Card.

    Returns:
        Green if Chronotype is promoted and Why-Card is generated
    """
    if not AI_READY_ENABLE_E2E:
        return AiReadyLight(
            status="red",
            details={"enabled": False},
            ts=datetime.now().isoformat(),
            reason="E2E probe disabled (AI_READY_ENABLE_E2E=false)"
        )

    if AI_READY_NO_WRITE:
        # In no-write mode, we skip the E2E test
        return AiReadyLight(
            status="green",
            details={"no_write_mode": True, "skipped": True},
            ts=datetime.now().isoformat(),
            reason="E2E probe skipped (AI_READY_NO_WRITE=true)"
        )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC * 2) as client:  # Allow more time for E2E
            # Step 1: Ingest test text
            ingest_resp = await client.post(
                f"{CORE_BASE}/core/api/ingest_text",
                json={
                    "user_id": AI_READY_PROBE_USER,
                    "text": AI_READY_PROBE_TEXT,
                    "source": "ai_ready_probe"
                }
            )

            if ingest_resp.status_code != 200:
                return AiReadyLight(
                    status="red",
                    details={"http_status": ingest_resp.status_code},
                    ts=datetime.now().isoformat(),
                    reason=f"Ingest failed with HTTP {ingest_resp.status_code}"
                )

            ingest_data = ingest_resp.json()
            rescore = ingest_data.get("rescore", {})
            rr_by_trait = rescore.get("rr_by_trait", {})

            # Check if Chronotype was rescored
            chronotype_rr = rr_by_trait.get("BehaviorDNA.Sleep.Chronotype")

            if chronotype_rr is None:
                return AiReadyLight(
                    status="red",
                    details={"rescore_rr": None, "rr_by_trait": list(rr_by_trait.keys())},
                    ts=datetime.now().isoformat(),
                    reason="Chronotype not found in rescore response"
                )

            # Step 2: Check Why-Card
            why_resp = await client.get(
                f"{CORE_BASE}/core/api/traits/BehaviorDNA.Sleep.Chronotype/why",
                params={"user_id": AI_READY_PROBE_USER}
            )

            if why_resp.status_code != 200:
                return AiReadyLight(
                    status="red",
                    details={"rescore_rr": chronotype_rr, "why_status": why_resp.status_code},
                    ts=datetime.now().isoformat(),
                    reason=f"Why-Card retrieval failed with HTTP {why_resp.status_code}"
                )

            why_data = why_resp.json()
            why_text = why_data.get("why", "")

            if not why_text or len(why_text.strip()) == 0:
                return AiReadyLight(
                    status="red",
                    details={"rescore_rr": chronotype_rr, "why_empty": True},
                    ts=datetime.now().isoformat(),
                    reason="Why-Card is empty"
                )

            # Success: both rescore and Why-Card working
            return AiReadyLight(
                status="green",
                details={
                    "rescore_rr": chronotype_rr,
                    "why_excerpt": why_text[:80] + ("..." if len(why_text) > 80 else "")
                },
                ts=datetime.now().isoformat()
            )

    except httpx.TimeoutException:
        return AiReadyLight(
            status="red",
            details={},
            ts=datetime.now().isoformat(),
            reason=f"E2E probe timeout ({TIMEOUT_SEC * 2}s)"
        )
    except Exception as e:
        return AiReadyLight(
            status="red",
            details={"error": str(e)},
            ts=datetime.now().isoformat(),
            reason=f"E2E probe failed: {str(e)}"
        )


async def run_ai_readiness_probe() -> AiReadyResponse:
    """
    Run complete AI readiness probe across all layers.

    Returns:
        AiReadyResponse with traffic light status for each layer
    """
    start_time = time.time()

    # Probe all layers concurrently
    import asyncio
    hc_devx, ucnrr, core = await asyncio.gather(
        probe_devx_health(),
        probe_ucnrr_health(),
        probe_core_health()
    )

    # Run E2E probe if Core is green
    if core.status == "green" and AI_READY_ENABLE_E2E:
        e2e = await probe_core_e2e()
    else:
        e2e = AiReadyLight(
            status="red",
            details={"skipped": True},
            ts=datetime.now().isoformat(),
            reason="Skipped (Core not green or E2E disabled)"
        )

    # Attach E2E status to Core
    core_with_e2e = AiReadyLight(
        status=core.status,
        details={**(core.details or {}), "e2e": e2e.model_dump()},
        ts=core.ts,
        reason=core.reason
    )

    # Determine overall result
    all_green = (
        hc_devx.status == "green" and
        ucnrr.status == "green" and
        core.status == "green" and
        (e2e.status == "green" if AI_READY_ENABLE_E2E and core.status == "green" else True)
    )

    result = "ALL-GOOD" if all_green else "NEEDS-FIX"

    duration_ms = int((time.time() - start_time) * 1000)

    return AiReadyResponse(
        hc_devx=hc_devx,
        ucnrr=ucnrr,
        core=core_with_e2e,
        result=result,
        probe_duration_ms=duration_ms,
        ts=datetime.now().isoformat()
    )


def get_top_reason(response: AiReadyResponse) -> Optional[str]:
    """
    Extract the most critical failure reason from probe response.

    Priority: HC/DevX > UCNRR > Core > E2E
    """
    if response.hc_devx.status == "red":
        return f"HC/DevX: {response.hc_devx.reason}"

    if response.ucnrr.status == "red":
        return f"UCNRR: {response.ucnrr.reason}"

    if response.core.status == "red":
        return f"Core: {response.core.reason}"

    # Check E2E status (nested in core.details)
    if response.core.details:
        e2e = response.core.details.get("e2e", {})
        if isinstance(e2e, dict) and e2e.get("status") == "red":
            return f"E2E: {e2e.get('reason', 'Unknown')}"

    return None


# ============================================================================
# Per-Layer Diagnostics (Verbose Mode)
# ============================================================================

class LayerDiagnosticResponse(BaseModel):
    """Detailed diagnostic response for a single layer."""
    layer: Literal["devx", "ucnrr", "core", "core_e2e"]
    status: Literal["green", "red"]
    ts: str
    details: Dict[str, Any]
    reason: Optional[str] = None
    suggestions: list[str] = []
    verbose_data: Optional[Dict[str, Any]] = None


async def diagnose_devx_layer(verbose: bool = False) -> LayerDiagnosticResponse:
    """
    Detailed diagnostics for DevX backend layer.

    Verbose mode includes:
    - Fallback detection (if /devx/api/health not available)
    - Response time
    - Raw health payload
    """
    suggestions = []
    verbose_data = {}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            # Try /devx/api/health first
            try:
                resp = await client.get(f"{DEVX_BASE}/devx/api/health")
                used_fallback = False
            except (httpx.HTTPStatusError, httpx.RequestError):
                # Fallback to /health
                resp = await client.get(f"{DEVX_BASE}/health")
                used_fallback = True

            if verbose:
                verbose_data["http_status"] = resp.status_code
                verbose_data["used_fallback_endpoint"] = used_fallback
                verbose_data["response_time_ms"] = int(resp.elapsed.total_seconds() * 1000) if hasattr(resp, 'elapsed') else None

            if resp.status_code == 200:
                data = resp.json()
                status_value = data.get("status", "unknown")

                if verbose:
                    verbose_data["raw_payload"] = data

                if status_value == "healthy":
                    return LayerDiagnosticResponse(
                        layer="devx",
                        status="green",
                        ts=datetime.now().isoformat(),
                        details={"status": status_value, "used_fallback": used_fallback},
                        verbose_data=verbose_data if verbose else None
                    )
                else:
                    suggestions.append("Check DevX backend logs for errors")
                    suggestions.append("Restart DevX backend: ./scripts/dev_up.sh")

                    return LayerDiagnosticResponse(
                        layer="devx",
                        status="red",
                        ts=datetime.now().isoformat(),
                        details={"status": status_value},
                        reason=f"DevX status is '{status_value}', expected 'healthy'",
                        suggestions=suggestions,
                        verbose_data=verbose_data if verbose else None
                    )
            else:
                suggestions.append(f"DevX returned HTTP {resp.status_code}")
                suggestions.append("Check if DevX backend is running on port 8012")

                return LayerDiagnosticResponse(
                    layer="devx",
                    status="red",
                    ts=datetime.now().isoformat(),
                    details={"http_status": resp.status_code},
                    reason=f"DevX health check returned HTTP {resp.status_code}",
                    suggestions=suggestions,
                    verbose_data=verbose_data if verbose else None
                )

    except httpx.TimeoutException:
        suggestions.append(f"DevX health check timed out after {TIMEOUT_SEC}s")
        suggestions.append("Check if DevX backend is running: curl http://127.0.0.1:8012/health")

        return LayerDiagnosticResponse(
            layer="devx",
            status="red",
            ts=datetime.now().isoformat(),
            details={},
            reason=f"DevX health check timeout ({TIMEOUT_SEC}s)",
            suggestions=suggestions
        )
    except Exception as e:
        suggestions.append("Check DevX backend logs")
        suggestions.append(f"Error: {str(e)}")

        return LayerDiagnosticResponse(
            layer="devx",
            status="red",
            ts=datetime.now().isoformat(),
            details={"error": str(e)},
            reason=f"DevX health check failed: {str(e)}",
            suggestions=suggestions
        )


async def diagnose_ucnrr_layer(verbose: bool = False) -> LayerDiagnosticResponse:
    """
    Detailed diagnostics for UCNRR layer.

    Verbose mode includes:
    - Ollama tags probe
    - Ollama generate probe (minimal)
    - Response times
    """
    suggestions = []
    verbose_data = {}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            resp = await client.get(f"{UCNRR_BASE}/health")

            if verbose:
                verbose_data["http_status"] = resp.status_code
                verbose_data["response_time_ms"] = int(resp.elapsed.total_seconds() * 1000) if hasattr(resp, 'elapsed') else None

            if resp.status_code == 200:
                data = resp.json()
                llm_configured = data.get("llm_configured", False)
                llm_provider = data.get("llm_provider", "unknown")
                llm_model = data.get("llm_model", "unknown")

                if verbose:
                    verbose_data["raw_payload"] = data

                    # Probe Ollama if provider is ollama
                    if llm_provider == "ollama":
                        ollama_base = data.get("llm_base_url", "http://127.0.0.1:11434")
                        try:
                            tags_resp = await client.get(f"{ollama_base}/api/tags", timeout=2.0)
                            verbose_data["ollama_tags_ok"] = tags_resp.status_code == 200
                            if tags_resp.status_code == 200:
                                tags_data = tags_resp.json()
                                verbose_data["ollama_models"] = [m.get("name") for m in tags_data.get("models", [])]
                        except Exception as e:
                            verbose_data["ollama_tags_ok"] = False
                            verbose_data["ollama_error"] = str(e)

                details = {
                    "llm_configured": llm_configured,
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                    "status": data.get("status", "unknown")
                }

                if llm_configured:
                    return LayerDiagnosticResponse(
                        layer="ucnrr",
                        status="green",
                        ts=datetime.now().isoformat(),
                        details=details,
                        verbose_data=verbose_data if verbose else None
                    )
                else:
                    suggestions.append("Set LLM_PROVIDER in UCNRR .env (e.g., LLM_PROVIDER=ollama)")
                    suggestions.append("Set LLM_MODEL in UCNRR .env (e.g., LLM_MODEL=phi3:mini)")
                    suggestions.append("Restart UCNRR service")

                    return LayerDiagnosticResponse(
                        layer="ucnrr",
                        status="red",
                        ts=datetime.now().isoformat(),
                        details=details,
                        reason="UCNRR is not LLM-configured (llm_configured=false)",
                        suggestions=suggestions,
                        verbose_data=verbose_data if verbose else None
                    )
            else:
                suggestions.append(f"UCNRR returned HTTP {resp.status_code}")
                suggestions.append("Check if UCNRR is running: curl http://127.0.0.1:8017/health")

                return LayerDiagnosticResponse(
                    layer="ucnrr",
                    status="red",
                    ts=datetime.now().isoformat(),
                    details={"http_status": resp.status_code},
                    reason=f"UCNRR health check returned HTTP {resp.status_code}",
                    suggestions=suggestions,
                    verbose_data=verbose_data if verbose else None
                )

    except httpx.TimeoutException:
        suggestions.append(f"UCNRR health check timed out after {TIMEOUT_SEC}s")
        suggestions.append("Check if UCNRR is running on port 8017")

        return LayerDiagnosticResponse(
            layer="ucnrr",
            status="red",
            ts=datetime.now().isoformat(),
            details={},
            reason=f"UCNRR health check timeout ({TIMEOUT_SEC}s)",
            suggestions=suggestions
        )
    except Exception as e:
        suggestions.append("Check UCNRR logs")
        suggestions.append(f"Error: {str(e)}")

        return LayerDiagnosticResponse(
            layer="ucnrr",
            status="red",
            ts=datetime.now().isoformat(),
            details={"error": str(e)},
            reason=f"UCNRR health check failed: {str(e)}",
            suggestions=suggestions
        )


async def diagnose_core_layer(verbose: bool = False) -> LayerDiagnosticResponse:
    """
    Detailed diagnostics for Core layer.

    Verbose mode includes:
    - Promotion state
    - Feature flags
    - Response times
    """
    suggestions = []
    verbose_data = {}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            resp = await client.get(f"{CORE_BASE}/health")

            if verbose:
                verbose_data["http_status"] = resp.status_code
                verbose_data["response_time_ms"] = int(resp.elapsed.total_seconds() * 1000) if hasattr(resp, 'elapsed') else None

                # Fetch promotion state
                try:
                    promo_resp = await client.get(f"{CORE_BASE}/core/api/debug/promotion_state", timeout=2.0)
                    if promo_resp.status_code == 200:
                        verbose_data["promotion_state"] = promo_resp.json()
                except Exception as e:
                    verbose_data["promotion_state_error"] = str(e)

            if resp.status_code == 200:
                data = resp.json()
                rr_mode = data.get("rr_mode", "unknown")
                features = data.get("features", {})
                ucnrr_enabled = features.get("ucnrr_enabled", False)

                if verbose:
                    verbose_data["raw_payload"] = data

                details = {
                    "rr_mode": rr_mode,
                    "ucnrr_enabled": ucnrr_enabled,
                    "status": data.get("status", "unknown")
                }

                # Green if both conditions met
                if rr_mode == "online" and ucnrr_enabled:
                    return LayerDiagnosticResponse(
                        layer="core",
                        status="green",
                        ts=datetime.now().isoformat(),
                        details=details,
                        verbose_data=verbose_data if verbose else None
                    )
                else:
                    if rr_mode != "online":
                        suggestions.append(f"Set RR_MODE=online in Core .env (currently: {rr_mode})")
                    if not ucnrr_enabled:
                        suggestions.append("Set UCNRR_BASE in Core .env (e.g., UCNRR_BASE=http://127.0.0.1:8017)")
                    suggestions.append("Restart Core service")

                    reasons = []
                    if rr_mode != "online":
                        reasons.append(f"rr_mode is '{rr_mode}', expected 'online'")
                    if not ucnrr_enabled:
                        reasons.append("ucnrr_enabled is false")

                    return LayerDiagnosticResponse(
                        layer="core",
                        status="red",
                        ts=datetime.now().isoformat(),
                        details=details,
                        reason="; ".join(reasons),
                        suggestions=suggestions,
                        verbose_data=verbose_data if verbose else None
                    )
            else:
                suggestions.append(f"Core returned HTTP {resp.status_code}")
                suggestions.append("Check if Core is running: curl http://127.0.0.1:8004/health")

                return LayerDiagnosticResponse(
                    layer="core",
                    status="red",
                    ts=datetime.now().isoformat(),
                    details={"http_status": resp.status_code},
                    reason=f"Core health check returned HTTP {resp.status_code}",
                    suggestions=suggestions,
                    verbose_data=verbose_data if verbose else None
                )

    except httpx.TimeoutException:
        suggestions.append(f"Core health check timed out after {TIMEOUT_SEC}s")
        suggestions.append("Check if Core is running on port 8004")

        return LayerDiagnosticResponse(
            layer="core",
            status="red",
            ts=datetime.now().isoformat(),
            details={},
            reason=f"Core health check timeout ({TIMEOUT_SEC}s)",
            suggestions=suggestions
        )
    except Exception as e:
        suggestions.append("Check Core logs")
        suggestions.append(f"Error: {str(e)}")

        return LayerDiagnosticResponse(
            layer="core",
            status="red",
            ts=datetime.now().isoformat(),
            details={"error": str(e)},
            reason=f"Core health check failed: {str(e)}",
            suggestions=suggestions
        )


async def diagnose_core_e2e_layer(verbose: bool = False, no_write: bool = False) -> LayerDiagnosticResponse:
    """
    Detailed diagnostics for Core E2E layer.

    Verbose mode includes:
    - Full ingest response
    - Complete Why-Card text
    - Timing breakdown
    """
    suggestions = []
    verbose_data = {}

    if not AI_READY_ENABLE_E2E:
        return LayerDiagnosticResponse(
            layer="core_e2e",
            status="red",
            ts=datetime.now().isoformat(),
            details={"enabled": False},
            reason="E2E probe disabled (AI_READY_ENABLE_E2E=false)",
            suggestions=["Set AI_READY_ENABLE_E2E=true to enable E2E testing"]
        )

    if no_write or AI_READY_NO_WRITE:
        return LayerDiagnosticResponse(
            layer="core_e2e",
            status="green",
            ts=datetime.now().isoformat(),
            details={"no_write_mode": True, "skipped": True},
            reason="E2E probe skipped (no-write mode)",
            suggestions=[]
        )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC * 2) as client:
            # Step 1: Ingest
            ingest_start = time.time()
            ingest_resp = await client.post(
                f"{CORE_BASE}/core/api/ingest_text",
                json={
                    "user_id": AI_READY_PROBE_USER,
                    "text": AI_READY_PROBE_TEXT,
                    "source": "ai_ready_probe"
                }
            )
            ingest_duration = (time.time() - ingest_start) * 1000

            if verbose:
                verbose_data["ingest_duration_ms"] = int(ingest_duration)
                verbose_data["ingest_http_status"] = ingest_resp.status_code

            if ingest_resp.status_code != 200:
                suggestions.append(f"Ingest failed with HTTP {ingest_resp.status_code}")
                suggestions.append("Check Core logs for errors")

                return LayerDiagnosticResponse(
                    layer="core_e2e",
                    status="red",
                    ts=datetime.now().isoformat(),
                    details={"http_status": ingest_resp.status_code},
                    reason=f"Ingest failed with HTTP {ingest_resp.status_code}",
                    suggestions=suggestions,
                    verbose_data=verbose_data if verbose else None
                )

            ingest_data = ingest_resp.json()
            if verbose:
                verbose_data["ingest_response"] = ingest_data

            rescore = ingest_data.get("rescore", {})
            rr_by_trait = rescore.get("rr_by_trait", {})
            chronotype_rr = rr_by_trait.get("BehaviorDNA.Sleep.Chronotype")

            if chronotype_rr is None:
                suggestions.append("Chronotype not extracted by UCNRR")
                suggestions.append("Check UCNRR LLM configuration")
                suggestions.append("Test UCNRR directly: curl POST /api/rescore with test phrase")

                return LayerDiagnosticResponse(
                    layer="core_e2e",
                    status="red",
                    ts=datetime.now().isoformat(),
                    details={"rescore_rr": None, "rr_by_trait": list(rr_by_trait.keys())},
                    reason="Chronotype not found in rescore response",
                    suggestions=suggestions,
                    verbose_data=verbose_data if verbose else None
                )

            # Step 2: Check Why-Card
            why_start = time.time()
            why_resp = await client.get(
                f"{CORE_BASE}/core/api/traits/BehaviorDNA.Sleep.Chronotype/why",
                params={"user_id": AI_READY_PROBE_USER}
            )
            why_duration = (time.time() - why_start) * 1000

            if verbose:
                verbose_data["why_duration_ms"] = int(why_duration)
                verbose_data["why_http_status"] = why_resp.status_code

            if why_resp.status_code != 200:
                suggestions.append(f"Why-Card retrieval failed with HTTP {why_resp.status_code}")
                suggestions.append("Check Core Why-Card API")

                return LayerDiagnosticResponse(
                    layer="core_e2e",
                    status="red",
                    ts=datetime.now().isoformat(),
                    details={"rescore_rr": chronotype_rr, "why_status": why_resp.status_code},
                    reason=f"Why-Card retrieval failed with HTTP {why_resp.status_code}",
                    suggestions=suggestions,
                    verbose_data=verbose_data if verbose else None
                )

            why_data = why_resp.json()
            why_text = why_data.get("why", "")

            if verbose:
                verbose_data["why_response"] = why_data
                verbose_data["why_full_text"] = why_text

            if not why_text or len(why_text.strip()) == 0:
                suggestions.append("Why-Card is empty")
                suggestions.append("Check Core Why-Card generation logic")

                return LayerDiagnosticResponse(
                    layer="core_e2e",
                    status="red",
                    ts=datetime.now().isoformat(),
                    details={"rescore_rr": chronotype_rr, "why_empty": True},
                    reason="Why-Card is empty",
                    suggestions=suggestions,
                    verbose_data=verbose_data if verbose else None
                )

            # Success
            return LayerDiagnosticResponse(
                layer="core_e2e",
                status="green",
                ts=datetime.now().isoformat(),
                details={
                    "rescore_rr": chronotype_rr,
                    "why_excerpt": why_text[:80] + ("..." if len(why_text) > 80 else "")
                },
                verbose_data=verbose_data if verbose else None
            )

    except httpx.TimeoutException:
        suggestions.append(f"E2E probe timed out after {TIMEOUT_SEC * 2}s")
        suggestions.append("Check Core and UCNRR response times")

        return LayerDiagnosticResponse(
            layer="core_e2e",
            status="red",
            ts=datetime.now().isoformat(),
            details={},
            reason=f"E2E probe timeout ({TIMEOUT_SEC * 2}s)",
            suggestions=suggestions
        )
    except Exception as e:
        suggestions.append("E2E probe encountered an error")
        suggestions.append(f"Error: {str(e)}")

        return LayerDiagnosticResponse(
            layer="core_e2e",
            status="red",
            ts=datetime.now().isoformat(),
            details={"error": str(e)},
            reason=f"E2E probe failed: {str(e)}",
            suggestions=suggestions
        )
