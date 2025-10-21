"""
DevX API Server
===============

FastAPI application for DevX backend services.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from datetime import datetime, timezone
from typing import Literal

from .config import (
    DEVX_BACKEND_PORT,
    DEVX_HOST,
    DEVX_CORE_BASE,
    DEVX_UCNRR_BASE,
    PROJECT_ROOT,
    resolved_stack_config,
)
from .routers import traits
from . import (
    privacy_dashboard_api,
    conflict_api,
    semantics_api,
    batch_ops_api,
    health_api,
    stack_api,
    holistic_api,
    coach_api,
    agent_api,
    rsc_api,
    trigger_api,
    adaptive_analytics_api,
    llm_bench_api,
    stack_ucnrr_api,
)
from .ai_ready import (
    run_ai_readiness_probe,
    AiReadyResponse,
    LayerDiagnosticResponse,
    diagnose_devx_layer,
    diagnose_ucnrr_layer,
    diagnose_core_layer,
    diagnose_core_e2e_layer,
)

logger = logging.getLogger(__name__)
PROBE_TIMEOUT = httpx.Timeout(read=2.0, write=2.0, connect=2.0, pool=2.0)
CORE_PROXY_TIMEOUT = httpx.Timeout(read=5.0, connect=3.0, write=5.0, pool=5.0)

RR_REFERENCE_CONFIG_PATH = PROJECT_ROOT / "config" / "rr_reference.json"
RR_REFERENCE_RESTART_HINT = "Restart Core via CP++ Nuclear to apply."
DEFAULT_REFERENCE_CONFIG: Dict[str, Any] = {
    "source": "SYNTHETIC",
    "universe": "combined",
    "cohort_keys": [],
}


class ReferenceConfigPayload(BaseModel):
    source: Literal["SYNTHETIC", "ACTUAL"] = Field(..., description="Reference population source")
    universe: Optional[Literal["combined", "low", "medium", "high"]] = Field(
        default="combined",
        description="Synthetic universe selection",
    )
    cohort_keys: Optional[List[str]] = Field(
        default_factory=list,
        description="Cohort key filters for ACTUAL source",
    )

    @validator("cohort_keys", pre=True)
    def _cohort_keys_from_any(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple, set)):
            clean: List[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    clean.append(text)
            return clean
        raise ValueError("cohort_keys must be a string or list of strings")

    @validator("universe", always=True)
    def _ensure_universe(cls, value: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        if values.get("source") == "SYNTHETIC":
            return value or "combined"
        return value

    def normalized(self) -> Dict[str, Any]:
        payload = DEFAULT_REFERENCE_CONFIG.copy()
        payload.update(
            {
                "source": self.source,
                "universe": self.universe or "combined",
                "cohort_keys": sorted(set(self.cohort_keys or [])),
            }
        )
        if payload["source"] != "ACTUAL":
            payload["cohort_keys"] = []
        return payload


def _ensure_config_parent() -> None:
    RR_REFERENCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_reference_config() -> Dict[str, Any]:
    """Load RR reference configuration, returning defaults on failure."""
    result = DEFAULT_REFERENCE_CONFIG.copy()
    _ensure_config_parent()
    if RR_REFERENCE_CONFIG_PATH.exists():
        try:
            with RR_REFERENCE_CONFIG_PATH.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                source = str(raw.get("source", result["source"])).upper()
                if source in {"SYNTHETIC", "ACTUAL"}:
                    result["source"] = source
                universe = raw.get("universe") or result["universe"]
                if isinstance(universe, str) and universe in {"combined", "low", "medium", "high"}:
                    result["universe"] = universe
                cohort = raw.get("cohort_keys", [])
                if isinstance(cohort, str):
                    cohort = [part.strip() for part in cohort.split(",") if part.strip()]
                elif isinstance(cohort, (list, tuple, set)):
                    cohort = [str(item).strip() for item in cohort if str(item).strip()]
                else:
                    cohort = []
                result["cohort_keys"] = sorted(set(cohort)) if result["source"] == "ACTUAL" else []
                if "updated_at" in raw:
                    result["updated_at"] = raw["updated_at"]
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse rr_reference config: %s", exc)
        except OSError as exc:
            logger.warning("Unable to load rr_reference config: %s", exc)
    result.setdefault("updated_at", None)
    return result


def save_reference_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Persist RR reference configuration to disk."""
    normalized = DEFAULT_REFERENCE_CONFIG.copy()
    raw_cohort = [
        str(item).strip()
        for item in (data.get("cohort_keys") or [])
        if str(item).strip()
    ]
    normalized.update(
        {
            "source": data.get("source", DEFAULT_REFERENCE_CONFIG["source"]),
            "universe": data.get("universe", DEFAULT_REFERENCE_CONFIG["universe"]),
            "cohort_keys": sorted(set(raw_cohort)),
        }
    )
    if normalized["source"] != "ACTUAL":
        normalized["cohort_keys"] = []
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    normalized["updated_at"] = timestamp

    _ensure_config_parent()
    try:
        with RR_REFERENCE_CONFIG_PATH.open("w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, sort_keys=True)
    except OSError as exc:
        logger.error("Failed to write rr_reference config: %s", exc)
        raise HTTPException(status_code=500, detail=f"Unable to persist configuration: {exc}") from exc

    return normalized


def _bool_query(value: Any) -> bool:
    """Best-effort conversion of query params to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "force"}
    return False


def _compose_probe_url(base: str, path: str) -> str:
    base_clean = base.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_clean}{path}"


async def _core_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Proxy a GET request to the Core service."""
    base = DEVX_CORE_BASE.rstrip("/")
    url = f"{base}{path if path.startswith('/') else f'/{path}'}"
    async with httpx.AsyncClient(timeout=CORE_PROXY_TIMEOUT) as client:
        try:
            response = await client.get(url, params=params or None, headers={"Cache-Control": "no-cache"})
        except httpx.RequestError as exc:
            logger.error("Core proxy request failed for %s: %s", url, exc)
            raise HTTPException(status_code=502, detail=f"Core request failed: {exc}") from exc

    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except ValueError:
            detail = response.text or f"HTTP {response.status_code}"
        message = detail if isinstance(detail, str) else detail.get("detail") if isinstance(detail, dict) else detail
        raise HTTPException(status_code=response.status_code, detail=message or "Core request failed")

    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            return response.json()
        except ValueError:
            logger.warning("Core response was not JSON despite JSON content-type: %s", url)
            return response.text
    return response.text


async def _core_post(
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
) -> Any:
    """Proxy a POST request to the Core service."""
    base = DEVX_CORE_BASE.rstrip("/")
    url = f"{base}{path if path.startswith('/') else f'/{path}'}"
    async with httpx.AsyncClient(timeout=CORE_PROXY_TIMEOUT) as client:
        try:
            response = await client.post(
                url,
                params=params or None,
                json=json_body if json_body is not None else None,
                headers={"Cache-Control": "no-cache"},
            )
        except httpx.RequestError as exc:
            logger.error("Core proxy POST failed for %s: %s", url, exc)
            raise HTTPException(status_code=502, detail=f"Core request failed: {exc}") from exc

    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except ValueError:
            detail = response.text or f"HTTP {response.status_code}"
        message: Optional[str] = None
        if isinstance(detail, dict):
            message = (
                detail.get("detail")
                or detail.get("error")
                or detail.get("message")
            )
        elif isinstance(detail, str):
            message = detail
        raise HTTPException(status_code=response.status_code, detail=message or "Core request failed")

    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            return response.json()
        except ValueError:
            logger.warning("Core response was not JSON despite JSON content-type: %s", url)
            return response.text
    return response.text


async def _probe_service(
    client: httpx.AsyncClient,
    *,
    name: str,
    url: str,
    checked_at: str,
    force: bool,
) -> Dict[str, Any]:
    """
    Execute a health probe against *url* and normalize the result.
    """
    params = {"force": "1"} if force else None
    headers = {"Cache-Control": "no-cache"}

    result: Dict[str, Any] = {
        "service": name,
        "status": "red",
        "ok": False,
        "checked_at": checked_at,
        "url": url,
    }

    start = perf_counter()
    try:
        response = await client.get(url, params=params, headers=headers)
        latency_ms = round((perf_counter() - start) * 1000, 2)
        result["latency_ms"] = latency_ms
        result["ms"] = latency_ms
        result["http_status"] = response.status_code

        try:
            body: Any = response.json()
            result["payload"] = body
        except ValueError:
            body = response.text

        reported = ""
        warning_text = None
        detail_text = None
        if isinstance(body, dict):
            reported = str(body.get("status", "")).lower()
            warning_text = body.get("warning")
            detail_text = warning_text or body.get("detail")
            # Preserve full payload for debugging
            if detail_text is None:
                detail_text = body.get("summary")
        else:
            detail_text = str(body)

        status_color = "red"
        ok = False

        if response.status_code == 200:
            if reported == "healthy":
                status_color = "green"
                ok = True
                detail_text = detail_text or "Healthy"
            elif reported == "degraded":
                status_color = "yellow"
                ok = False
                detail_text = detail_text or "Degraded"
                if warning_text:
                    result["warning"] = warning_text
            elif reported == "error":
                status_color = "red"
                ok = False
                detail_text = detail_text or "Error reported"
                if warning_text:
                    result["warning"] = warning_text
                result["error"] = detail_text
            elif reported in {"green", "yellow", "amber"}:
                status_color = "yellow" if reported != "green" else "green"
                ok = status_color == "green"
            elif reported:
                status_color = "yellow"
                detail_text = detail_text or f"Status: {reported}"
            else:
                status_color = "yellow"
                detail_text = detail_text or "Unknown status payload"
        else:
            detail_text = detail_text or f"HTTP {response.status_code}"
            result["error"] = detail_text

        if warning_text and status_color == "yellow":
            result["warning"] = warning_text
        result["status"] = status_color
        result["ok"] = ok
        result["reported_status"] = reported or None
        result["detail"] = detail_text

    except httpx.TimeoutException:
        result["error"] = "timeout"
        result["detail"] = "Health probe timed out"
        result["status"] = "red"
        result["ok"] = False
    except httpx.RequestError as exc:
        error_detail = f"{type(exc).__name__}: {exc}"
        result["error"] = "request_error"
        result["detail"] = error_detail
        result["status"] = "red"
        result["ok"] = False

    if force:
        result["force"] = True

    result.setdefault("latency_ms", None)
    result.setdefault("ms", result.get("latency_ms"))
    result.setdefault("detail", "Unreachable")
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    stack_cfg = resolved_stack_config()
    logger.info(
        "DevX backend starting with stack_config=%s",
        {
            "core_base": stack_cfg["core_base"],
            "ucnrr_base": stack_cfg["ucnrr_base"],
            "devx_base": stack_cfg["devx_base"],
            "core_port": stack_cfg["core_port"],
            "ucnrr_port": stack_cfg["ucnrr_port"],
            "devx_port": stack_cfg["devx_port"],
            "warnings": stack_cfg.get("warnings", []),
            "sources": stack_cfg.get("source"),
        },
    )
    yield
    logger.info("DevX backend shutting down...")


# Create FastAPI app
app = FastAPI(
    title="DevX API",
    description="Developer Experience API for ReDNA",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - allow frontend to connect
frontend_ports = list(range(3000, 3011)) + list(range(3100, 3111))
allow_origins = {
    f"http://localhost:{port}" for port in frontend_ports
} | {
    f"http://127.0.0.1:{port}" for port in frontend_ports
} | {
    f"http://{DEVX_HOST}:{port}" for port in frontend_ports
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "devx-backend",
        "version": "1.0.0"
    }


@app.get("/devx/api/health")
async def devx_health_alias(response: Response, force: Optional[str] = None):
    """
    DevX health alias that also surfaces Core & Consent probe results.

    Query Parameters:
        force: When truthy, append ?force=1 and Cache-Control:no-cache to downstream probes.
    """
    force_flag = _bool_query(force)
    response.headers["Cache-Control"] = "no-cache"

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    core_url = _compose_probe_url(DEVX_CORE_BASE, "/health")
    consent_url = _compose_probe_url(DEVX_CORE_BASE, "/core/consent/health")

    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
        core_result, consent_result = await asyncio.gather(
            _probe_service(
                client,
                name="core",
                url=core_url,
                checked_at=timestamp,
                force=force_flag,
            ),
            _probe_service(
                client,
                name="consent",
                url=consent_url,
                checked_at=timestamp,
                force=force_flag,
            ),
        )

    service_map = {
        "core": core_result,
        "consent": consent_result,
    }

    overall_status = "green"
    if any(entry["status"] == "red" for entry in service_map.values()):
        overall_status = "red"
    elif any(entry["status"] not in {"green"} for entry in service_map.values()):
        overall_status = "yellow"

    payload: Dict[str, Any] = {
        "status": "healthy",
        "service": "devx-backend",
        "version": "1.0.0",
        "checked_at": timestamp,
        "overall_status": overall_status,
        "services": service_map,
    }

    if force_flag:
        payload["force"] = True

    return payload


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "DevX API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# Include routers
app.include_router(traits.router, prefix="/devx/api/traits", tags=["traits"])
app.include_router(privacy_dashboard_api.router, prefix="/devx/api", tags=["privacy"])
app.include_router(conflict_api.router, prefix="/devx/api", tags=["conflicts"])
app.include_router(semantics_api.router, prefix="/devx/api/semantics", tags=["semantics"])
app.include_router(batch_ops_api.router, prefix="/devx/api", tags=["batch-ops"])
app.include_router(health_api.router, prefix="/devx/api", tags=["health"])
app.include_router(holistic_api.router, prefix="/devx/api/holistic", tags=["holistic"])
app.include_router(coach_api.router, tags=["coach-workshop"])
app.include_router(agent_api.router, tags=["agents"])
app.include_router(agent_api.user_router, tags=["agents"])
app.include_router(rsc_api.router, tags=["rsc"])
app.include_router(agent_api.capability_router, tags=["capability"])
app.include_router(trigger_api.router, tags=["triggers"])
app.include_router(adaptive_analytics_api.router, tags=["adaptive-analytics"])
app.include_router(stack_api.router, prefix="/devx/api", tags=["stack"])
app.include_router(llm_bench_api.router, prefix="/devx/api", tags=["llm-bench"])
app.include_router(stack_ucnrr_api.router, prefix="/devx/api/stack", tags=["stack", "ucnrr"])


@app.get("/devx/api/ingestion/ai_ready", tags=["ai-readiness"])
async def get_ai_readiness(
    layer: Optional[str] = None,
    verbose: int = 0,
    no_write: int = 0
):
    """
    AI Readiness Probe - Traffic Light Status for All Ingestion Layers

    Checks if the three AI ingestion layers are operational:
    1. HC/DevX Backend (Northstar intake)
    2. UCNRR Processing (LLM configured & responding)
    3. Core Processing (resolver online, promotion + Why-Card)

    **Query Parameters:**
    - `layer`: Optional layer-specific diagnostic ("devx", "ucnrr", "core", "core_e2e")
    - `verbose`: Enable verbose mode (1=true, 0=false)
    - `no_write`: Skip E2E writes (1=true, 0=false)

    **Response Schema (Summary Mode):**
    - `hc_devx`: DevX backend health
    - `ucnrr`: UCNRR LLM configuration status
    - `core`: Core resolver status + E2E promotion test
    - `result`: "ALL-GOOD" if all green, "NEEDS-FIX" otherwise

    **Response Schema (Layer Mode):**
    - `layer`: Layer name
    - `status`: "green" | "red"
    - `details`: Layer-specific details
    - `reason`: Failure reason (if red)
    - `suggestions`: Remediation steps
    - `verbose_data`: Additional diagnostic data (if verbose=1)

    **Configuration:**
    - `AI_READY_PROBE_USER`: User ID for E2E test (default: "ai_ready_probe")
    - `AI_READY_PROBE_TEXT`: Test phrase (default: "I am a morning person...")
    - `AI_READY_TIMEOUT_MS`: HTTP timeout (default: 1500ms)
    - `AI_READY_ENABLE_E2E`: Enable E2E test (default: true)
    - `AI_READY_NO_WRITE`: Skip E2E writes (default: false)

    **Examples:**
    - Summary: `GET /devx/api/ingestion/ai_ready`
    - Layer diagnostic: `GET /devx/api/ingestion/ai_ready?layer=ucnrr&verbose=1`
    - No-write E2E: `GET /devx/api/ingestion/ai_ready?no_write=1`
    """
    from typing import Optional, Union

    verbose_bool = bool(verbose)
    no_write_bool = bool(no_write)

    # Layer-specific diagnostic
    if layer:
        if layer == "devx":
            return await diagnose_devx_layer(verbose=verbose_bool)
        elif layer == "ucnrr":
            return await diagnose_ucnrr_layer(verbose=verbose_bool)
        elif layer == "core":
            return await diagnose_core_layer(verbose=verbose_bool)
        elif layer == "core_e2e":
            return await diagnose_core_e2e_layer(verbose=verbose_bool, no_write=no_write_bool)
        else:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Invalid layer: {layer}. Must be one of: devx, ucnrr, core, core_e2e")

    # Summary mode
    return await run_ai_readiness_probe()


@app.get("/devx/api/rr/reference/config")
async def get_rr_reference_config() -> Dict[str, Any]:
    """
    Retrieve the current RR reference configuration used by Core.
    """
    config = load_reference_config()
    return {
        "config": config,
        "restart_hint": RR_REFERENCE_RESTART_HINT,
        "config_path": str(RR_REFERENCE_CONFIG_PATH),
    }


@app.post("/devx/api/rr/reference/config")
async def set_rr_reference_config(payload: ReferenceConfigPayload) -> Dict[str, Any]:
    """
    Persist RR reference configuration changes.

    Clients must restart Core via CP++ Nuclear to apply the updates.
    """
    normalized = payload.normalized()
    persisted = save_reference_config(normalized)
    return {
        "ok": True,
        "config": persisted,
        "restart_hint": RR_REFERENCE_RESTART_HINT,
        "config_path": str(RR_REFERENCE_CONFIG_PATH),
        "message": "Reference configuration updated. Restart Core via CP++ Nuclear to apply.",
    }


@app.get("/devx/api/rr/reference/status")
async def rr_reference_status(trait_id: str, cohort: Optional[str] = None) -> Dict[str, Any]:
    """
    Proxy Core RR reference status for a trait.
    """
    trait = (trait_id or "").strip()
    if not trait:
        raise HTTPException(status_code=400, detail="trait_id is required")

    params: Dict[str, Any] = {"trait_id": trait}
    if cohort:
        params["cohort"] = cohort

    core_payload = await _core_get("/core/rr/reference/status", params=params)
    return {
        "trait_id": trait,
        "core": core_payload,
        "config": load_reference_config(),
    }


@app.get("/devx/api/rr/reference/samples")
async def rr_reference_samples(trait_id: str) -> Dict[str, Any]:
    """
    Retrieve reference sample statistics for a trait.
    """
    trait = (trait_id or "").strip()
    if not trait:
        raise HTTPException(status_code=400, detail="trait_id is required")

    core_payload = await _core_get("/core/rr/reference/samples", params={"trait_id": trait})
    response: Dict[str, Any] = {
        "trait_id": trait,
        "config": load_reference_config(),
    }
    if isinstance(core_payload, dict):
        response.update(core_payload)
    else:
        response["core"] = core_payload
    return response


class RecomputeRRResponse(BaseModel):
    ok: bool = True
    traits_updated: Optional[int] = None
    legacy_scores_archived: Optional[int] = None
    detail: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


@app.post("/devx/api/rr/recompute")
async def recompute_rr(
    user_id: Optional[str] = None,
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Trigger RR recomputation for a user (or scope) via Core admin endpoint.
    """
    if scope is None and not user_id:
        raise HTTPException(status_code=400, detail="user_id is required unless scope=all")

    params: Dict[str, Any] = {}
    if scope:
        params["scope"] = scope
    if user_id:
        params["user_id"] = user_id

    core_payload = await _core_post("/core/admin/recompute_rr", params=params)

    if isinstance(core_payload, str):
        try:
            core_payload = json.loads(core_payload)
        except json.JSONDecodeError:
            core_payload = {"message": core_payload}

    if not isinstance(core_payload, dict):
        core_payload = {"detail": core_payload}

    summary = RecomputeRRResponse(
        ok=bool(core_payload.get("ok", True)),
        traits_updated=core_payload.get("traits_updated")
        or core_payload.get("updated_traits")
        or core_payload.get("updated")
        or core_payload.get("count"),
        legacy_scores_archived=core_payload.get("legacy_scores_archived")
        or core_payload.get("legacy_archived"),
        detail=core_payload.get("detail") or core_payload.get("message"),
        raw=core_payload,
    )
    return summary.dict()


@app.get("/devx/api/synthetic/traits")
async def get_synthetic_traits(shape: str = "skill_profile"):
    """
    Provide synthetic trait data for DevX demos.

    This allows the DevX UI to render realistic data when capabilities
    are unavailable. Data is non-identifying and safe for demos.
    """
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if shape == "skill_profile":
        return {
            "user_id": "SYNTH",
            "generated_at": now_iso,
            "containers": [
                {
                    "path": "SkillDNA/software_engineering",
                    "label": "Software Engineering",
                    "rr": 82,
                    "curiosity": 46,
                    "ucn": 712,
                    "last_evidence": "2024-09-12T18:22:00Z",
                },
                {
                    "path": "SkillDNA/product_thinking",
                    "label": "Product Thinking",
                    "rr": 74,
                    "curiosity": 58,
                    "ucn": 655,
                    "last_evidence": "2024-08-30T15:10:00Z",
                },
                {
                    "path": "SkillDNA/data_storytelling",
                    "label": "Data Storytelling",
                    "rr": 68,
                    "curiosity": 62,
                    "ucn": 601,
                    "last_evidence": "2024-07-05T09:40:00Z",
                },
                {
                    "path": "ProfDNA/collaboration_style",
                    "label": "Collaboration Style",
                    "rr": 79,
                    "curiosity": 35,
                    "ucn": 688,
                    "last_evidence": "2024-09-01T12:05:00Z",
                },
            ],
            "metadata": {
                "source": "synthetic",
                "notes": "Masked demo data generated for DevX UI previews.",
            },
        }

    return {
        "user_id": "SYNTH",
        "generated_at": now_iso,
        "containers": [],
        "metadata": {
            "source": "synthetic",
            "notes": f"No synthetic shape registered for '{shape}'.",
        },
    }


if __name__ == "__main__":
    import uvicorn

    from .config import get_backend_port

    port = get_backend_port()
    logger.info(
        "Starting DevX backend on %s:%s (core_base=%s, ucnrr_base=%s)",
        DEVX_HOST,
        port,
        DEVX_CORE_BASE,
        DEVX_UCNRR_BASE,
    )

    uvicorn.run(
        "ReDNACoreDemo.devx.backend.api:app",
        host=DEVX_HOST,
        port=port,
        reload=True,
        log_level="info"
    )
