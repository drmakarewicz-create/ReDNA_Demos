"""
DevX API Server
===============

FastAPI application for DevX backend services.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime, timezone

from .config import DEVX_BACKEND_PORT, DEVX_HOST
from .routers import traits
from . import (
    privacy_dashboard_api,
    conflict_api,
    semantics_api,
    batch_ops_api,
    health_api,
    holistic_api,
    coach_api,
    agent_api,
    rsc_api,
    trigger_api,
    adaptive_analytics_api,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    logger.info("DevX backend starting...")
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
frontend_ports = range(3100, 3111)
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
    logger.info(f"Starting DevX backend on {DEVX_HOST}:{port}")

    uvicorn.run(
        "devx.backend.api:app",
        host=DEVX_HOST,
        port=port,
        reload=True,
        log_level="info"
    )
