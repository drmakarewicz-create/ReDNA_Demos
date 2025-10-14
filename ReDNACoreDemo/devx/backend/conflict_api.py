"""DevX conflict dashboard API proxy."""

from __future__ import annotations

import os
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query, Response


router = APIRouter()

CORE_BASE_URL = os.getenv("REDNA_CORE_BASE", "http://127.0.0.1:8015")


async def _forward(request_method: str, path: str, *, params=None, json_body=None):
    url = f"{CORE_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.request(request_method, url, params=params, json=json_body)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    if response.content:
        return response.json()
    return {"status": "ok"}


@router.get("/conflicts/list")
async def list_conflicts(
    user_id: str | None = Query(None),
    status: str | None = Query(None),
    kind: str | None = Query(None),
):
    params = {"user_id": user_id, "status": status, "kind": kind}
    params = {k: v for k, v in params.items() if v is not None}
    return await _forward("GET", "/conflicts/list", params=params)


@router.get("/conflicts/detail")
async def conflict_detail(conflict_id: str):
    return await _forward("GET", "/conflicts/detail", params={"conflict_id": conflict_id})


@router.post("/conflicts/simulate")
async def simulate_conflict(payload: dict):
    return await _forward("POST", "/conflicts/simulate", json_body=payload)


@router.post("/conflicts/resolve")
async def resolve_conflict(payload: dict):
    return await _forward("POST", "/conflicts/resolve", json_body=payload)


@router.get("/conflicts/learning-stats")
async def learning_stats():
    return await _forward("GET", "/conflicts/learning-stats")


@router.get("/conflicts/export")
async def export_conflict_log(user_id: str):
    url = f"{CORE_BASE_URL}/conflicts/export"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params={"user_id": user_id})
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    content_disposition = response.headers.get("content-disposition", "attachment; filename=conflict_log.jsonl")
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "application/x-ndjson"),
        headers={"Content-Disposition": content_disposition},
    )


@router.post("/conflicts/seed")
async def seed_conflict():
    """Create a demo conflict for the TEST user via the core simulator."""
    payload = {
        "conflict": {
            "user_id": "TEST",
            "kind": "trait",
            "severity": "medium",
            "path": "SkillDNA.sample_trait",
        },
        "evidence": [
            {
                "evidence_id": f"seed-user-{os.urandom(4).hex()}",
                "source_type": "user_assertion",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "value": "user_claim",
                "provenance": {"support": 0.75},
            },
            {
                "evidence_id": f"seed-core-{os.urandom(4).hex()}",
                "source_type": "core",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "value": "system_dispute",
                "provenance": {"support": -0.6},
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{CORE_BASE_URL}/conflicts/simulate", json=payload)
        response.raise_for_status()
        return {
            "status": "ok",
            "core_status": response.status_code,
            "conflict_id": response.json().get("conflict_id"),
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to seed conflict: {exc}")
