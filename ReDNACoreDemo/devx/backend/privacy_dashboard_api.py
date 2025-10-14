"""
DevX Privacy Dashboard API

Proxy endpoints for the Privacy Dashboard UI to interact with:
- Consent Service (capabilities, ledger)
- Permission Coach (audits, explanations)
- User preferences (refinement toggle)

This module provides a clean API for the DevX frontend to display and
manage user privacy settings, consent, and capabilities.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Consent Service URL (read from port log)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_ROOT = Path(os.environ.get("DEVX_DATA_ROOT", PROJECT_ROOT / "data"))
CONSENT_PORT_LOG = DATA_ROOT / "consent" / "consent_port.log"


def get_consent_service_url() -> str:
    """Get Consent Service URL from port log."""
    try:
        if CONSENT_PORT_LOG.exists():
            with open(CONSENT_PORT_LOG, "r") as f:
                port = f.read().strip()
            return f"http://127.0.0.1:{port}"
        else:
            logger.warning("Consent Service port log not found, using default 8200")
            return "http://127.0.0.1:8200"
    except Exception as e:
        logger.error(f"Failed to read Consent Service port log: {e}")
        return "http://127.0.0.1:8200"


# User directories
PREFS_DIR = DATA_ROOT / "users"
USERS_ROOT = DATA_ROOT / "users"
EXPORTS_ROOT = DATA_ROOT / "exports"
EXPORTS_ROOT.mkdir(parents=True, exist_ok=True)


def safe_json_dump(path: Path, payload: Dict[str, Any]) -> None:
    """Atomically write JSON payload to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def sanitize_user_id(user_id: str) -> str:
    sanitized = (user_id or "").strip()
    if not sanitized or any(sep in sanitized for sep in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail=f"Invalid user id '{user_id}'")
    return sanitized


@router.get("/privacy/capabilities")
async def list_user_capabilities(
    user_id: str = Query(..., description="User ID"),
    grantee_id: Optional[str] = Query(None, description="Filter by grantee"),
):
    """
    List all active capabilities for a user.

    Args:
        user_id: User ID
        grantee_id: Optional grantee filter

    Returns:
        List of capability summaries with metadata
    """
    try:
        consent_url = get_consent_service_url()

        async with httpx.AsyncClient() as client:
            params = {"user_id": user_id}
            if grantee_id:
                params["grantee_id"] = grantee_id

            response = await client.get(
                f"{consent_url}/consent/capabilities",
                params=params,
                timeout=10.0
            )

            if response.status_code == 200:
                capabilities = response.json()
                logger.info(f"Retrieved {len(capabilities)} capabilities for user {user_id}")
                return {
                    "user_id": user_id,
                    "capabilities": capabilities,
                    "total": len(capabilities),
                }
            else:
                logger.error(f"Consent Service error: {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Consent Service error: {response.text}"
                )

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Consent Service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Consent Service unavailable. Please ensure it is running."
        )


@router.get("/privacy/ledger")
async def get_consent_ledger(
    user_id: str = Query(..., description="User ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type (grant, revoke, use, deny)"),
    limit: int = Query(100, description="Max number of events to return"),
):
    """
    Get consent ledger events for a user.

    Args:
        user_id: User ID
        event_type: Optional event type filter
        limit: Max number of events

    Returns:
        List of ledger events (most recent first)
    """
    try:
        consent_url = get_consent_service_url()

        async with httpx.AsyncClient() as client:
            params = {"user_id": user_id}
            if event_type:
                params["event_type"] = event_type

            response = await client.get(
                f"{consent_url}/consent/ledger",
                params=params,
                timeout=10.0
            )

            if response.status_code == 200:
                events = response.json()

                # Sort by timestamp (most recent first)
                events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

                # Apply limit
                events = events[:limit]

                logger.info(f"Retrieved {len(events)} ledger events for user {user_id}")
                return {
                    "user_id": user_id,
                    "events": events,
                    "total": len(events),
                }
            else:
                logger.error(f"Consent Service error: {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Consent Service error: {response.text}"
                )

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Consent Service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Consent Service unavailable. Please ensure it is running."
        )


@router.post("/privacy/revoke")
async def revoke_capability(
    cap_id: str = Body(..., embed=True),
    reason: str = Body("User revoked via Privacy Dashboard", embed=True),
):
    """
    Revoke a capability.

    Args:
        cap_id: Capability ID to revoke
        reason: Reason for revocation

    Returns:
        Revocation confirmation
    """
    try:
        consent_url = get_consent_service_url()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{consent_url}/consent/revoke",
                json={"cap_id": cap_id, "reason": reason},
                timeout=10.0
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Capability revoked: {cap_id}")
                return result
            else:
                logger.error(f"Revocation failed: {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Revocation failed: {response.text}"
                )

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Consent Service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Consent Service unavailable. Please ensure it is running."
        )


@router.get("/privacy/audit")
@router.post("/privacy/audit")
async def audit_user_capabilities(
    user_id: str = Query(..., description="User ID"),
):
    """
    Run capability audit for a user.

    Args:
        user_id: User ID

    Returns:
        Audit report with anomalies and recommendations
    """
    try:
        # Import here to avoid circular dependency
        from core.permission_coach.permcoach_audit import audit_user

        audit_report = await audit_user(user_id)
        logger.info(f"Audit complete for user {user_id}: {len(audit_report.get('anomalies', []))} anomalies")

        return audit_report

    except Exception as e:
        logger.error(f"Audit failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Audit failed: {str(e)}"
        )


@router.get("/privacy/preferences")
async def get_privacy_preferences(
    user_id: str = Query(..., description="User ID"),
):
    """
    Get user privacy preferences.

    Args:
        user_id: User ID

    Returns:
        Privacy preferences (refinement toggle, etc.)
    """
    prefs_file = PREFS_DIR / user_id / "privacy_prefs.json"

    # Default preferences
    default_prefs = {
        "refinement_enabled": True,  # Allow refinement by default
        "auto_approve_low_risk": False,  # Don't auto-approve by default
        "audit_notifications": True,  # Enable audit notifications
        "export_warning": True,  # Warn on export requests
    }

    if not prefs_file.exists():
        logger.debug(f"No privacy prefs for user {user_id}, returning defaults")
        return {
            "user_id": user_id,
            "preferences": default_prefs,
        }

    try:
        with open(prefs_file, "r") as f:
            prefs = json.load(f)

        logger.debug(f"Retrieved privacy prefs for user {user_id}")
        return {
            "user_id": user_id,
            "preferences": prefs,
        }

    except Exception as e:
        logger.error(f"Failed to read privacy prefs: {e}")
        return {
            "user_id": user_id,
            "preferences": default_prefs,
        }


@router.post("/privacy/preferences")
async def update_privacy_preferences(
    user_id: str = Body(...),
    preferences: Dict[str, Any] = Body(...),
):
    """
    Update user privacy preferences.

    Args:
        user_id: User ID
        preferences: New preference values

    Returns:
        Updated preferences
    """
    user_dir = PREFS_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    prefs_file = user_dir / "privacy_prefs.json"

    try:
        with open(prefs_file, "w") as f:
            json.dump(preferences, f, indent=2)

        logger.info(f"Updated privacy prefs for user {user_id}")

        return {
            "user_id": user_id,
            "preferences": preferences,
            "status": "updated",
        }

    except Exception as e:
        logger.error(f"Failed to update privacy prefs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update preferences: {str(e)}"
        )


@router.post("/privacy/export-json-batch")
async def export_json_batch(user_ids: List[str] = Body(..., embed=True)):
    """
    Create sanitized JSON exports for the provided users.

    Each export includes user metadata plus container path and RR only.
    """
    if not isinstance(user_ids, list) or not user_ids:
        raise HTTPException(status_code=400, detail="user_ids must be a non-empty list.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results: List[Dict[str, Any]] = []

    for raw_id in sorted({uid for uid in user_ids if uid}):
        user_id = sanitize_user_id(raw_id)
        export_dir = EXPORTS_ROOT / user_id
        export_path = export_dir / f"export_{timestamp}.json"

        try:
            resolved_path = USERS_ROOT / user_id / "resolved.json"
            resolved: Dict[str, Any] = {}
            if resolved_path.exists():
                resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
            containers = resolved.get("containers", [])
            export_obj = {
                "user_id": user_id,
                "metadata": resolved.get("metadata", {}),
                "containers": [
                    {"path": entry.get("path"), "rr": entry.get("rr")}
                    for entry in containers
                    if isinstance(entry, dict)
                ],
            }
            safe_json_dump(export_path, export_obj)
            results.append(
                {
                    "user_id": user_id,
                    "status": "ready",
                    "download": f"/devx/api/privacy/download?file={user_id}/export_{timestamp}.json",
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to export user %s", user_id)
            results.append({"user_id": user_id, "status": "error", "reason": str(exc)})

    return {"ts": timestamp, "results": results}


@router.get("/privacy/download")
async def download_export(file: str = Query(..., description="Relative path to export file")):
    """
    Download a previously generated export. Paths are constrained to data/exports.
    """
    requested = Path(file)
    if requested.is_absolute() or ".." in requested.parts or len(requested.parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid export path.")

    user_segment, filename = requested.parts
    sanitize_user_id(user_segment)
    if not filename.startswith("export_") or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid export filename.")

    full_path = (EXPORTS_ROOT / requested).resolve()
    exports_root_resolved = EXPORTS_ROOT.resolve()
    if not str(full_path).startswith(str(exports_root_resolved)):
        raise HTTPException(status_code=400, detail="Invalid export path.")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Export not found.")

    return FileResponse(
        full_path,
        media_type="application/json",
        filename=full_path.name,
    )


@router.post("/privacy/export-request")
async def request_data_export(
    user_id: str = Body(..., embed=True),
    format: str = Body("json", embed=True),  # json, csv, pdf
):
    """
    Request user data export.

    Args:
        user_id: User ID
        format: Export format (json, csv, pdf)

    Returns:
        Export request confirmation
    """
    # TODO: Implement actual export logic
    # For now, log request and return pending status

    logger.info(f"Data export requested for user {user_id}, format={format}")

    return {
        "status": "pending",
        "user_id": user_id,
        "format": format,
        "message": "Export request received. You will be notified when ready for download.",
        "estimated_time_minutes": 5,
    }


@router.post("/privacy/purge-request")
async def request_data_purge(
    user_id: str = Body(..., embed=True),
    confirmation: str = Body(..., embed=True),  # Must match user_id
):
    """
    Request complete data purge (GDPR right to deletion).

    Args:
        user_id: User ID
        confirmation: Confirmation string (must match user_id)

    Returns:
        Purge request confirmation
    """
    if confirmation != user_id:
        raise HTTPException(
            status_code=400,
            detail="Confirmation does not match user_id. Purge request denied."
        )

    # TODO: Implement actual purge logic (with safeguards!)
    # For now, log request and return pending status

    logger.warning(f"⚠️  Data purge requested for user {user_id}")

    return {
        "status": "pending_review",
        "user_id": user_id,
        "message": "Purge request received and is under review. This action is irreversible.",
        "review_period_days": 7,  # Grace period before actual deletion
    }


@router.get("/privacy/summary")
async def get_privacy_summary(
    user_id: str = Query(..., description="User ID"),
):
    """
    Get comprehensive privacy summary for dashboard overview.

    Args:
        user_id: User ID

    Returns:
        Summary with capabilities, recent activity, audit status
    """
    consent_url = get_consent_service_url()

    try:
        async with httpx.AsyncClient() as client:
            caps_response = await client.get(
                f"{consent_url}/consent/capabilities",
                params={"user_id": user_id},
                timeout=10.0,
            )

            if caps_response.status_code != 200:
                logger.error(f"Consent Service capabilities error: {caps_response.status_code}")
                raise HTTPException(
                    status_code=caps_response.status_code,
                    detail=f"Consent Service error: {caps_response.text}",
                )

            try:
                capabilities = caps_response.json()
            except Exception as e:
                logger.error(f"Invalid capabilities payload from Consent Service: {e}")
                raise HTTPException(
                    status_code=502,
                    detail="Consent Service returned invalid capability data.",
                )

            ledger_response = await client.get(
                f"{consent_url}/consent/ledger",
                params={"user_id": user_id},
                timeout=10.0,
            )

            if ledger_response.status_code != 200:
                logger.error(f"Consent Service ledger error: {ledger_response.status_code}")
                raise HTTPException(
                    status_code=ledger_response.status_code,
                    detail=f"Consent Service error: {ledger_response.text}",
                )

            try:
                ledger_events = ledger_response.json()
            except Exception as e:
                logger.error(f"Invalid ledger payload from Consent Service: {e}")
                raise HTTPException(
                    status_code=502,
                    detail="Consent Service returned invalid ledger data.",
                )

        capability_totals = {
            "total": len(capabilities),
            "revoked": len([cap for cap in capabilities if cap.get("revoked")]),
            "export_enabled": len(
                [
                    cap
                    for cap in capabilities
                    if cap.get("export_allowed") and not cap.get("revoked")
                ]
            ),
        }

        ledger_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        recent_events = ledger_events[:10]

        event_counts = {
            "grant": len([e for e in ledger_events if e.get("event_type") == "grant"]),
            "revoke": len([e for e in ledger_events if e.get("event_type") == "revoke"]),
            "use": len([e for e in ledger_events if e.get("event_type") == "use"]),
            "deny": len([e for e in ledger_events if e.get("event_type") == "deny"]),
        }

        prefs_file = PREFS_DIR / user_id / "privacy_prefs.json"
        if prefs_file.exists():
            try:
                with open(prefs_file, "r") as f:
                    prefs = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read privacy prefs for {user_id}: {e}")
                prefs = {
                    "refinement_enabled": True,
                    "auto_approve_low_risk": False,
                    "audit_notifications": True,
                    "export_warning": True,
                }
        else:
            prefs = {
                "refinement_enabled": True,
                "auto_approve_low_risk": False,
                "audit_notifications": True,
                "export_warning": True,
            }

        return {
            "user_id": user_id,
            "summary": {
                "active_capabilities": len(capabilities),
                "total_grants": event_counts["grant"],
                "total_revocations": event_counts["revoke"],
                "total_uses": event_counts["use"],
                "total_denials": event_counts["deny"],
                "recent_activity": recent_events,
                "preferences": prefs,
            },
            "managed_by": "PermCoach",
            "capability_totals": capability_totals,
        }

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Consent Service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Consent Service unavailable. Please ensure it is running.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get privacy summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get privacy summary: {str(e)}",
        )
