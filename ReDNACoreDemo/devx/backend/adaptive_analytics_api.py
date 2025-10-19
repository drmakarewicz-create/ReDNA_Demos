"""Adaptive Analytics DevX API."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from ReDNACoreDemo.core.adaptive_analytics import AdaptiveAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devx/api/adaptive-analytics", tags=["adaptive-analytics"])

adaptive_service = AdaptiveAnalyticsService()


def _refresh_timestamp(service: AdaptiveAnalyticsService) -> Optional[str]:
    stamp = getattr(service, "_last_refresh", None)
    return stamp.isoformat() if stamp else None


@router.get("/overview")
async def get_overview():
    """Return adaptive analytics overview for all users."""
    try:
        data = adaptive_service.overview()
        return {
            "generated_at": _refresh_timestamp(adaptive_service),
            "users": data,
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to compute adaptive analytics overview")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/user/{user_id}")
async def get_user_view(user_id: str):
    """Return adaptive analytics for a single user."""
    try:
        payload = adaptive_service.user_view(user_id)
        payload["refresh_epoch"] = _refresh_timestamp(adaptive_service)
        return payload
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to compute adaptive analytics view for %s", user_id)
        raise HTTPException(status_code=500, detail=str(exc))
