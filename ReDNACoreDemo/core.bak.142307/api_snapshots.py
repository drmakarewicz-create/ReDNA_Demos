"""FastAPI endpoints for Persona Snapshot Export."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from . import snapshot_exporter

router = APIRouter(prefix="/snapshots", tags=["Persona Snapshots"])


class SnapshotMetaResponse(BaseModel):
    id: str
    user_id: str
    created_at: str
    scope: str
    families: List[str]
    size_bytes: int
    trait_count: int
    label: Optional[str] = None


class SnapshotResponse(BaseModel):
    id: str
    user_id: str
    created_at: str
    version: str
    scope: str
    families: List[str]
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class ExportRequest(BaseModel):
    user_id: str
    families: Optional[List[str]] = None
    label: Optional[str] = None


class DeleteRequest(BaseModel):
    user_id: str
    snapshot_id: str


@router.post("/export", response_model=SnapshotMetaResponse)
async def export_snapshot_endpoint(request: ExportRequest):
    """
    Export user's PaDNA as a timestamped snapshot.

    Args:
        request: ExportRequest with user_id, optional families, optional label

    Returns:
        SnapshotMetaResponse (lightweight metadata, not full data)
    """
    try:
        snapshot = snapshot_exporter.export_snapshot(
            user_id=request.user_id,
            families=request.families,
            label=request.label,
        )

        meta = snapshot.to_meta()

        return SnapshotMetaResponse(
            id=meta.id,
            user_id=meta.user_id,
            created_at=meta.created_at,
            scope=meta.scope,
            families=meta.families,
            size_bytes=meta.size_bytes,
            trait_count=meta.trait_count,
            label=meta.label,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot export failed: {exc}")


@router.get("/list/{user_id}", response_model=List[SnapshotMetaResponse])
async def list_snapshots_endpoint(user_id: str, limit: int = 20):
    """
    List snapshot metadata for user (most recent first).

    Args:
        user_id: User identifier
        limit: Max number of snapshots to return (default 20)

    Returns:
        List of SnapshotMetaResponse objects
    """
    try:
        metas = snapshot_exporter.list_snapshots(user_id=user_id, limit=limit)

        return [
            SnapshotMetaResponse(
                id=meta.id,
                user_id=meta.user_id,
                created_at=meta.created_at,
                scope=meta.scope,
                families=meta.families,
                size_bytes=meta.size_bytes,
                trait_count=meta.trait_count,
                label=meta.label,
            )
            for meta in metas
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {exc}")


@router.get("/{user_id}/{snapshot_id}")
async def load_snapshot_endpoint(user_id: str, snapshot_id: str):
    """
    Load full snapshot data (returns raw JSON for download).

    Args:
        user_id: User identifier
        snapshot_id: Snapshot ID

    Returns:
        Full snapshot JSON (for download)
    """
    try:
        snapshot = snapshot_exporter.load_snapshot(user_id=user_id, snapshot_id=snapshot_id)

        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")

        # Return as JSON for download
        return JSONResponse(content=snapshot.as_dict())

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load snapshot: {exc}")


@router.delete("/delete", response_model=Dict[str, bool])
async def delete_snapshot_endpoint(request: DeleteRequest):
    """
    Delete snapshot file and remove from index.

    Args:
        request: DeleteRequest with user_id and snapshot_id

    Returns:
        {"success": True} if deleted, error if not found
    """
    try:
        success = snapshot_exporter.delete_snapshot(
            user_id=request.user_id,
            snapshot_id=request.snapshot_id,
        )

        if not success:
            raise HTTPException(status_code=404, detail=f"Snapshot {request.snapshot_id} not found")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete snapshot: {exc}")


__all__ = ["router"]
