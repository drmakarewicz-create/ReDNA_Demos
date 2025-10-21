"""
Debug API endpoints for RR/UCN audit and diagnostics (Phase 9) - STUB

NOTE: This file had indentation errors from recent edits.
Temporarily using stub to unblock service restart.
Full implementation pending.
"""

from __future__ import annotations
import logging
import os
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Debug configuration (required by api.py startup logging)
DEBUG_ROUTES_ENABLED = os.getenv("DEBUG_ROUTES_ENABLED", "true").lower() in ("true", "1", "yes")
DEBUG_TOKEN = os.getenv("X_REDNA_DEBUG_TOKEN", "")

# Create empty router to satisfy imports
router = APIRouter(prefix="/debug", tags=["debug"])

# TODO: Re-implement debug endpoints with proper auth guard
# - GET /rr_audit/{user_id}
# - GET /ucn_propagation/{user_id}
# - GET /health
