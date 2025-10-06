"""FastAPI surface for the PhotoRefinementCoach analyze endpoint."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.service.analyzer import analyze_request

app = FastAPI(
    title="PhotoRefinementCoach Service",
    version="0.1.0",
    description="Run visual refinement over 1..N photos and return an explorer bundle.",
)


class ImageInput(BaseModel):
    id: Optional[str] = None
    b64: Optional[str] = Field(default=None, description="base64-encoded image bytes")
    path: Optional[str] = Field(default=None, description="Filesystem path to image (dev-only)")
    recency: Optional[str] = Field(default=None, description="RECENT | OLD | RETRO")
    ts: Optional[str] = Field(default=None, description="ISO timestamp of capture")
    filename: Optional[str] = None
    notes: Optional[str] = None


class AnalyzePayload(BaseModel):
    user_id: str
    snapshot_id: str
    images: List[ImageInput]
    notes: Optional[str] = None
    previous_bundle: Optional[Dict[str, Any]] = None
    model: Optional[str] = Field(default=None, description="Vision adapter name")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def post_analyze(payload: AnalyzePayload) -> Dict[str, Any]:
    try:
        result = analyze_request(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging happens upstream
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


__all__ = ["app"]
