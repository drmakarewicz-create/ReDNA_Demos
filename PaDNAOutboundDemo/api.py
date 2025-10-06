"""FastAPI facade for the PaDNA outbound avatar renderer."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.vision.renderer_v2 import render_svg

app = FastAPI(title="PaDNA Outbound Renderer", version="0.2.0")


class RenderPayload(BaseModel):
    bundle: Dict[str, Any]
    width: Optional[int] = None
    height: Optional[int] = None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/render")
def post_render(payload: RenderPayload) -> Dict[str, Any]:
    try:
        result = render_svg(
            payload.bundle,
            width=payload.width or 1000,
            height=payload.height or 900,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to caller
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "svg": result["svg"],
        "data_url": result["data_url"],
        "palette": result["palette"],
        "apparel": result["apparel"],
        "posture": result["posture"],
        "tattoos": result.get("tattoos"),
        "config": result.get("config"),
        "debug": result.get("debug"),
    }


__all__ = ["app"]
