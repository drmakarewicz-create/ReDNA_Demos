"""
UCNRR Stack Control API
========================

API endpoints for controlling and monitoring UCNRR connectivity,
including ensure, restart, status, and logs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from . import supervisor_ucnrr


router = APIRouter(prefix="/ucnrr", tags=["stack", "ucnrr"])


class EnsureRequest(BaseModel):
    """Request to ensure UCNRR is running."""
    model: Optional[str] = Field(None, description="LLM model to use (e.g. phi3:mini)")
    provider: Optional[str] = Field(None, description="LLM provider (ollama, anthropic, etc)")
    force_restart: bool = Field(False, description="Force restart if already running")


class EnsureResponse(BaseModel):
    """Response from ensure endpoint."""
    status: Literal["started", "already_running", "failed"]
    reason: str
    pid: Optional[int]
    model: str
    provider: str
    alive: Optional[bool] = None
    llm_configured: Optional[bool] = None
    hint: Optional[str] = None


class StatusResponse(BaseModel):
    """UCNRR status response."""
    alive: bool
    llm_configured: bool
    reason: str
    restarts_last_10m: int
    restart_capped: bool
    backoff_sec_remaining: int
    last_check: Optional[str]
    pid: Optional[int]


class RestartResponse(BaseModel):
    """Response from restart endpoint."""
    status: Literal["scheduled", "capped"]
    reason: str
    pid: Optional[int]


@router.post("/ensure", response_model=EnsureResponse)
async def ensure_ucnrr_endpoint(request: EnsureRequest) -> EnsureResponse:
    """
    Ensure UCNRR is running.

    Validates environment, checks Ollama, and starts UCNRR if needed.
    Returns status, PID, and model/provider info.
    """
    config = {}
    if request.model:
        config["model"] = request.model
    if request.provider:
        config["provider"] = request.provider
    if request.force_restart:
        config["force_restart"] = True

    result = await asyncio.to_thread(supervisor_ucnrr.ensure_ucnrr, config)
    return EnsureResponse(**result)


@router.get("/status", response_model=StatusResponse)
async def get_ucnrr_status_endpoint() -> StatusResponse:
    """
    Get current UCNRR status.

    Returns health, restart count, backoff state, and cap status.
    """
    status = await asyncio.to_thread(supervisor_ucnrr.get_ucnrr_status)
    return StatusResponse(**status)


@router.post("/restart", response_model=RestartResponse)
async def restart_ucnrr_endpoint() -> RestartResponse:
    """
    Hard restart UCNRR with rate-limit check.

    Will fail if restart cap is exceeded.
    """
    # Check if capped
    if supervisor_ucnrr._check_restart_cap():
        return RestartResponse(
            status="capped",
            reason="restart_cap_exceeded",
            pid=None,
        )

    # Force restart
    result = await asyncio.to_thread(
        supervisor_ucnrr.ensure_ucnrr,
        {"force_restart": True}
    )

    return RestartResponse(
        status="scheduled",
        reason=result["reason"],
        pid=result.get("pid"),
    )


@router.get("/logs")
async def get_ucnrr_logs(tail: int = Query(150, ge=1, le=500)) -> Dict[str, Any]:
    """
    Get UCNRR logs (last N lines).

    Returns plain text log lines (safe-bounded tail).
    """
    log_path = supervisor_ucnrr.UCNRR_LOG_FILE

    if not log_path.exists():
        return {
            "log_file": str(log_path),
            "lines": [],
            "total_lines": 0,
        }

    lines: List[str] = []
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            all_lines = handle.readlines()
            lines = all_lines[-tail:] if len(all_lines) > tail else all_lines
            lines = [line.rstrip("\n") for line in lines]
    except OSError:
        pass

    return {
        "log_file": str(log_path),
        "lines": lines,
        "total_lines": len(lines),
    }
