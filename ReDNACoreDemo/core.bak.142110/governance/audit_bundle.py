"""
Audit Bundle Export - Phase 6

Creates comprehensive audit bundles for GDPR/compliance requests.

Bundle contents:
- User data (all DNA containers)
- Consent timeline
- Capability history
- Agent activity logs
- Telemetry
- Provenance metadata

Format: ZIP archive with structured JSON files
Performance target: ≤ 5 seconds for typical user

Directory structure:
audit_bundle_{user_id}_{timestamp}.zip
├── metadata.json           (bundle metadata)
├── user_profile.json        (basic user data)
├── dna/
│   ├── skill_dna.json
│   ├── psy_dna.json
│   ├── belief_dna.json
│   └── ...
├── consent/
│   ├── timeline.json
│   └── active_capabilities.json
├── activity/
│   ├── agent_activity.jsonl
│   └── telemetry.jsonl
└── provenance.json          (data lineage)
"""

import json
import logging
import time
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditBundleMetadata(BaseModel):
    """Metadata for audit bundle."""

    bundle_id: str = Field(..., description="Unique bundle ID")
    user_id: str
    created_at: str = Field(..., description="ISO-8601 timestamp")
    requester: str = Field(..., description="Who requested the bundle")
    purpose: str = Field(default="gdpr_request", description="Purpose of export")
    files_included: List[str] = Field(
        default_factory=list, description="List of files in bundle"
    )
    total_size_bytes: int = Field(default=0, description="Total bundle size")
    generation_time_ms: int = Field(
        default=0, description="Time taken to generate bundle"
    )


def _collect_user_data(user_id: str) -> Dict[str, Any]:
    """
    Collect user profile data.

    Args:
        user_id: User ID

    Returns:
        Dictionary of user data
    """
    user_file = Path("data") / "users" / user_id / "user.json"

    if not user_file.exists():
        return {"user_id": user_id, "error": "User file not found"}

    try:
        with open(user_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load user data: {e}")
        return {"user_id": user_id, "error": str(e)}


def _collect_dna_containers(user_id: str) -> Dict[str, Any]:
    """
    Collect all DNA containers for user.

    Args:
        user_id: User ID

    Returns:
        Dictionary of DNA containers
    """
    dna_containers = {}
    user_dir = Path("data") / "users" / user_id

    # Common DNA file patterns
    dna_files = [
        "resolved.json",  # Main DNA container
        "observations.json",
        "preferences.json",
        "goals.json",
    ]

    for dna_file in dna_files:
        file_path = user_dir / dna_file
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    dna_containers[dna_file] = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {dna_file}: {e}")
                dna_containers[dna_file] = {"error": str(e)}

    return dna_containers


def _collect_consent_data(user_id: str) -> Dict[str, Any]:
    """
    Collect consent timeline and active capabilities.

    Args:
        user_id: User ID

    Returns:
        Dictionary with consent data
    """
    from .consent_timeline import ConsentTimeline

    timeline = ConsentTimeline(user_id)

    consent_data = {
        "timeline": [e.model_dump() for e in timeline.get_all_events()],
        "active_capabilities": timeline.get_active_capabilities(),
        "summary": timeline.get_summary(),
    }

    return consent_data


def _collect_activity_logs(user_id: str) -> Dict[str, Any]:
    """
    Collect agent activity and telemetry logs.

    Args:
        user_id: User ID

    Returns:
        Dictionary with activity logs
    """
    activity_data = {}
    user_dir = Path("data") / "users" / user_id

    # Agent activity
    agent_log = user_dir / "agent" / "agent_activity.jsonl"
    if agent_log.exists():
        activity_data["agent_activity"] = []
        try:
            with open(agent_log, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        activity_data["agent_activity"].append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to load agent activity: {e}")
            activity_data["agent_activity"] = {"error": str(e)}

    # Telemetry
    telemetry_dir = user_dir / "telemetry"
    if telemetry_dir.exists():
        activity_data["telemetry_files"] = []
        for tel_file in telemetry_dir.glob("*.jsonl"):
            try:
                with open(tel_file, "r", encoding="utf-8") as f:
                    events = [json.loads(line) for line in f if line.strip()]
                activity_data["telemetry_files"].append(
                    {"file": tel_file.name, "events": events}
                )
            except Exception as e:
                logger.error(f"Failed to load {tel_file}: {e}")

    return activity_data


def _collect_provenance(user_id: str) -> Dict[str, Any]:
    """
    Collect data provenance and lineage information.

    Args:
        user_id: User ID

    Returns:
        Dictionary with provenance metadata
    """
    provenance = {
        "user_id": user_id,
        "system": "ReDNA",
        "version": "1.0",
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "data_sources": [
            "user_profile",
            "dna_containers",
            "consent_timeline",
            "agent_activity",
            "telemetry",
        ],
        "retention_policy": "As per user consent",
        "privacy_level": "high",
    }

    return provenance


def create_audit_bundle(
    user_id: str,
    requester: str = "user",
    purpose: str = "gdpr_request",
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Create comprehensive audit bundle for user.

    Args:
        user_id: User ID to export
        requester: Who requested the bundle
        purpose: Purpose of the export
        output_dir: Output directory (default: data/audit/bundles/)

    Returns:
        Path to created ZIP file

    Raises:
        Exception: If bundle creation fails
    """
    start_time = time.time()

    # Setup output directory
    if output_dir is None:
        output_dir = Path("data") / "audit" / "bundles"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate bundle ID and filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bundle_id = f"audit_{user_id}_{timestamp}"
    zip_path = output_dir / f"{bundle_id}.zip"

    logger.info(f"Creating audit bundle for {user_id}: {bundle_id}")

    # Collect data
    try:
        user_data = _collect_user_data(user_id)
        dna_data = _collect_dna_containers(user_id)
        consent_data = _collect_consent_data(user_id)
        activity_data = _collect_activity_logs(user_id)
        provenance = _collect_provenance(user_id)
    except Exception as e:
        logger.error(f"Failed to collect data for audit bundle: {e}")
        raise

    # Create ZIP file
    files_included = []

    try:
        with zipfile.ZipFile(
            zip_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as zf:
            # Add user profile
            zf.writestr("user_profile.json", json.dumps(user_data, indent=2))
            files_included.append("user_profile.json")

            # Add DNA containers
            for dna_file, dna_content in dna_data.items():
                path = f"dna/{dna_file}"
                zf.writestr(path, json.dumps(dna_content, indent=2))
                files_included.append(path)

            # Add consent data
            zf.writestr(
                "consent/timeline.json", json.dumps(consent_data, indent=2)
            )
            files_included.append("consent/timeline.json")

            # Add activity logs
            if "agent_activity" in activity_data:
                zf.writestr(
                    "activity/agent_activity.json",
                    json.dumps(activity_data["agent_activity"], indent=2),
                )
                files_included.append("activity/agent_activity.json")

            if "telemetry_files" in activity_data:
                for tel_data in activity_data["telemetry_files"]:
                    path = f"activity/telemetry/{tel_data['file']}"
                    zf.writestr(path, json.dumps(tel_data["events"], indent=2))
                    files_included.append(path)

            # Add provenance
            zf.writestr("provenance.json", json.dumps(provenance, indent=2))
            files_included.append("provenance.json")

            # Add metadata
            generation_time_ms = int((time.time() - start_time) * 1000)
            metadata = AuditBundleMetadata(
                bundle_id=bundle_id,
                user_id=user_id,
                created_at=datetime.utcnow().isoformat() + "Z",
                requester=requester,
                purpose=purpose,
                files_included=files_included,
                total_size_bytes=zip_path.stat().st_size if zip_path.exists() else 0,
                generation_time_ms=generation_time_ms,
            )

            zf.writestr("metadata.json", metadata.model_dump_json(indent=2))

    except Exception as e:
        logger.error(f"Failed to create ZIP file: {e}")
        if zip_path.exists():
            zip_path.unlink()
        raise

    generation_time = time.time() - start_time
    logger.info(
        f"Audit bundle created: {zip_path} "
        f"(size: {zip_path.stat().st_size} bytes, "
        f"time: {generation_time:.2f}s)"
    )

    return zip_path


__all__ = ["create_audit_bundle", "AuditBundleMetadata"]
