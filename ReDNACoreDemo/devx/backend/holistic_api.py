"""
Holistic Results API
====================

Read-only endpoints to expose computed holistic review metrics.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from .batch_ops_api import (
    HOLISTIC_HISTORY_ROOT,
    HOLISTIC_RESULTS_ROOT,
    DATA_ROOT,
)

router = APIRouter()


def _ensure_paths() -> None:
    HOLISTIC_RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    HOLISTIC_HISTORY_ROOT.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to read {path.name}: {exc}") from exc


@router.get("/get")
def get_holistic_result(user_id: str = Query(..., description="User identifier")) -> Dict[str, Any]:
    """Return the latest holistic metrics for a user."""
    _ensure_paths()
    safe_user = user_id.strip()
    if not safe_user or any(part in safe_user for part in ("/", "\\")):
        raise HTTPException(status_code=400, detail="Invalid user_id.")

    result_path = HOLISTIC_RESULTS_ROOT / f"{safe_user}.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Holistic result not found.")
    return _load_json(result_path)


@router.get("/history")
def get_holistic_history(
    user_id: str = Query(..., description="User identifier"),
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    """Return the most recent holistic history snapshots."""
    _ensure_paths()
    safe_user = user_id.strip()
    if not safe_user or any(part in safe_user for part in ("/", "\\")):
        raise HTTPException(status_code=400, detail="Invalid user_id.")

    pattern = f"{safe_user}_*.json"
    paths = sorted(HOLISTIC_HISTORY_ROOT.glob(pattern), reverse=True)
    entries: List[Dict[str, Any]] = []
    for path in paths[:limit]:
        payload = _load_json(path)
        entries.append(
            {
                "generated_at": payload.get("generated_at"),
                "counts": payload.get("counts", {}),
                "rr": payload.get("rr", {}),
                "path": path.name,
            }
        )

    return {
        "user_id": safe_user,
        "entries": entries,
    }
