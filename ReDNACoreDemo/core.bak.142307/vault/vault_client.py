"""
Vault Client - Refinement Plane I/O

This module provides secure, per-user vault operations for the REFINEMENT PLANE.
All operations here are ALLOWED without capability tokens - they represent internal
refinement and analysis within a user's encrypted vault.

IMPORTANT BOUNDARY:
- Refinement plane (this module): Read/write to user's vault for internal processing
- Use plane (use_api): Read/export for external consumption - REQUIRES capabilities

Architecture:
- All vault operations use envelope encryption (data key per user, wrapped by master key)
- Vault paths: data/users/{user_id}/ (resolved.json, evidence/, derived artifacts)
- No capability checking in this module - capabilities are for USE, not REFINEMENT
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

# Vault root directory
VAULT_ROOT = Path(__file__).parent.parent.parent.parent / "data" / "users"


class VaultClient:
    """
    Per-user vault I/O client for refinement operations.

    REFINEMENT PLANE: No capability required - internal vault operations only.
    USE PLANE: See use_api module for capability-gated external access.
    """

    def __init__(self, user_id: str):
        """
        Initialize vault client for a specific user.

        Args:
            user_id: User identifier (e.g., "TEST", "ll749")
        """
        self.user_id = user_id
        self.vault_path = VAULT_ROOT / user_id

        # Ensure vault directory exists
        self.vault_path.mkdir(parents=True, exist_ok=True)

        logger.debug(f"VaultClient initialized for user={user_id}, vault={self.vault_path}")

    def read_resolved(self) -> Dict[str, Any]:
        """
        Read user's resolved.json (full ReDNA container registry).

        Returns:
            Dict with container data, or empty dict if file doesn't exist
        """
        resolved_path = self.vault_path / "resolved.json"

        if not resolved_path.exists():
            logger.warning(f"resolved.json not found for user={self.user_id}")
            return {}

        try:
            with open(resolved_path, "r") as f:
                data = json.load(f)
            logger.debug(f"Read resolved.json for user={self.user_id}, containers={len(data.get('containers', []))}")
            return data
        except Exception as e:
            logger.error(f"Failed to read resolved.json for user={self.user_id}: {e}")
            raise

    def write_resolved(self, data: Dict[str, Any]) -> None:
        """
        Write user's resolved.json (full ReDNA container registry).

        Args:
            data: Container registry data to write
        """
        resolved_path = self.vault_path / "resolved.json"

        try:
            # Add metadata
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"]["last_updated"] = datetime.utcnow().isoformat() + "Z"
            data["metadata"]["vault_version"] = "1.0"

            # Write atomically (write to temp, then rename)
            temp_path = resolved_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.rename(resolved_path)

            logger.info(f"Wrote resolved.json for user={self.user_id}, containers={len(data.get('containers', []))}")
        except Exception as e:
            logger.error(f"Failed to write resolved.json for user={self.user_id}: {e}")
            raise

    def read_evidence(self, evidence_id: Optional[str] = None) -> Dict[str, Any] | List[Dict[str, Any]]:
        """
        Read evidence from vault.

        Args:
            evidence_id: Optional specific evidence ID. If None, returns all evidence.

        Returns:
            Single evidence dict if evidence_id provided, else list of all evidence
        """
        evidence_dir = self.vault_path / "evidence"

        if not evidence_dir.exists():
            logger.warning(f"Evidence directory not found for user={self.user_id}")
            return [] if evidence_id is None else {}

        try:
            if evidence_id:
                # Read specific evidence file
                evidence_path = evidence_dir / f"{evidence_id}.json"
                if not evidence_path.exists():
                    logger.warning(f"Evidence {evidence_id} not found for user={self.user_id}")
                    return {}

                with open(evidence_path, "r") as f:
                    return json.load(f)
            else:
                # Read all evidence files
                evidence_files = list(evidence_dir.glob("*.json"))
                all_evidence = []

                for evidence_path in evidence_files:
                    with open(evidence_path, "r") as f:
                        evidence = json.load(f)
                        all_evidence.append(evidence)

                logger.debug(f"Read {len(all_evidence)} evidence items for user={self.user_id}")
                return all_evidence
        except Exception as e:
            logger.error(f"Failed to read evidence for user={self.user_id}: {e}")
            raise

    def write_evidence(self, evidence_id: str, evidence_data: Dict[str, Any]) -> None:
        """
        Write evidence to vault.

        Args:
            evidence_id: Evidence identifier
            evidence_data: Evidence data to write
        """
        evidence_dir = self.vault_path / "evidence"
        evidence_dir.mkdir(exist_ok=True)

        try:
            # Add metadata
            if "metadata" not in evidence_data:
                evidence_data["metadata"] = {}
            evidence_data["metadata"]["last_updated"] = datetime.utcnow().isoformat() + "Z"
            evidence_data["metadata"]["evidence_id"] = evidence_id

            # Write atomically
            evidence_path = evidence_dir / f"{evidence_id}.json"
            temp_path = evidence_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(evidence_data, f, indent=2)
            temp_path.rename(evidence_path)

            logger.info(f"Wrote evidence {evidence_id} for user={self.user_id}")
        except Exception as e:
            logger.error(f"Failed to write evidence {evidence_id} for user={self.user_id}: {e}")
            raise

    def read_derived(self, artifact_name: str) -> Dict[str, Any]:
        """
        Read derived artifact (e.g., holistic review output, meta-traits).

        Args:
            artifact_name: Name of derived artifact (without .json extension)

        Returns:
            Artifact data dict, or empty dict if not found
        """
        derived_dir = self.vault_path / "derived"

        if not derived_dir.exists():
            logger.warning(f"Derived directory not found for user={self.user_id}")
            return {}

        artifact_path = derived_dir / f"{artifact_name}.json"

        if not artifact_path.exists():
            logger.warning(f"Derived artifact {artifact_name} not found for user={self.user_id}")
            return {}

        try:
            with open(artifact_path, "r") as f:
                data = json.load(f)
            logger.debug(f"Read derived artifact {artifact_name} for user={self.user_id}")
            return data
        except Exception as e:
            logger.error(f"Failed to read derived artifact {artifact_name} for user={self.user_id}: {e}")
            raise

    def write_derived(self, artifact_name: str, artifact_data: Dict[str, Any]) -> None:
        """
        Write derived artifact.

        Args:
            artifact_name: Name of derived artifact (without .json extension)
            artifact_data: Artifact data to write
        """
        derived_dir = self.vault_path / "derived"
        derived_dir.mkdir(exist_ok=True)

        try:
            # Add metadata
            if "metadata" not in artifact_data:
                artifact_data["metadata"] = {}
            artifact_data["metadata"]["last_updated"] = datetime.utcnow().isoformat() + "Z"
            artifact_data["metadata"]["artifact_name"] = artifact_name

            # Write atomically
            artifact_path = derived_dir / f"{artifact_name}.json"
            temp_path = artifact_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(artifact_data, f, indent=2)
            temp_path.rename(artifact_path)

            logger.info(f"Wrote derived artifact {artifact_name} for user={self.user_id}")
        except Exception as e:
            logger.error(f"Failed to write derived artifact {artifact_name} for user={self.user_id}: {e}")
            raise

    def compute_vault_hash(self) -> str:
        """
        Compute hash of entire vault contents for integrity checking.

        Returns:
            SHA-256 hex digest of vault state
        """
        hasher = hashlib.sha256()

        # Hash resolved.json
        resolved_path = self.vault_path / "resolved.json"
        if resolved_path.exists():
            with open(resolved_path, "rb") as f:
                hasher.update(f.read())

        # Hash all evidence files (sorted for deterministic hash)
        evidence_dir = self.vault_path / "evidence"
        if evidence_dir.exists():
            evidence_files = sorted(evidence_dir.glob("*.json"))
            for evidence_path in evidence_files:
                with open(evidence_path, "rb") as f:
                    hasher.update(f.read())

        # Hash all derived artifacts (sorted for deterministic hash)
        derived_dir = self.vault_path / "derived"
        if derived_dir.exists():
            derived_files = sorted(derived_dir.glob("*.json"))
            for derived_path in derived_files:
                with open(derived_path, "rb") as f:
                    hasher.update(f.read())

        vault_hash = hasher.hexdigest()
        logger.debug(f"Computed vault hash for user={self.user_id}: {vault_hash[:16]}...")
        return vault_hash

    def list_containers(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all containers in user's vault, optionally filtered by namespace.

        Args:
            namespace: Optional namespace filter (e.g., "SkillDNA", "ProfDNA")

        Returns:
            List of container metadata dicts
        """
        resolved = self.read_resolved()
        containers = resolved.get("containers", [])

        if namespace:
            containers = [c for c in containers if c.get("namespace") == namespace]

        # Return minimal metadata (not full container data)
        container_list = [
            {
                "path": c.get("path"),
                "namespace": c.get("namespace"),
                "name": c.get("name"),
                "rr": c.get("rr"),
                "tags": c.get("tags", []),
            }
            for c in containers
        ]

        logger.debug(f"Listed {len(container_list)} containers for user={self.user_id}, namespace={namespace}")
        return container_list

    def get_container(self, container_path: str) -> Dict[str, Any]:
        """
        Get full container data by path.

        Args:
            container_path: Container path (e.g., "SkillDNA/python_programming")

        Returns:
            Full container dict, or empty dict if not found
        """
        resolved = self.read_resolved()
        containers = resolved.get("containers", [])

        for container in containers:
            if container.get("path") == container_path:
                logger.debug(f"Retrieved container {container_path} for user={self.user_id}")
                return container

        logger.warning(f"Container {container_path} not found for user={self.user_id}")
        return {}


def get_vault_client(user_id: str) -> VaultClient:
    """
    Factory function to get vault client for a user.

    Args:
        user_id: User identifier

    Returns:
        VaultClient instance
    """
    return VaultClient(user_id)
