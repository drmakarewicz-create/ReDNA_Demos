"""
Ontology Service - Provides access to the ReDNA Ontology V2 registry.

This module loads and queries the 2000+ container ontology system.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Path to ontology registry
ONTOLOGY_REGISTRY_PATH = Path(__file__).parent / "ontology" / "dna_registry.json"


class OntologyService:
    """Service for querying the ReDNA Ontology V2 registry."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or ONTOLOGY_REGISTRY_PATH
        self._registry = None
        self._load_registry()

    def _load_registry(self):
        """Load the ontology registry from disk."""
        try:
            with open(self.registry_path) as f:
                self._registry = json.load(f)
            logger.info(f"Loaded ontology registry with {len(self._registry['containers'])} containers")
        except Exception as e:
            logger.error(f"Failed to load ontology registry: {e}")
            self._registry = {"metadata": {}, "containers": []}

    def get_all_containers(self) -> List[Dict[str, Any]]:
        """Get all containers in the registry."""
        return self._registry.get("containers", [])

    def get_container_by_id(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific container by ID."""
        for container in self._registry.get("containers", []):
            if container.get("id") == container_id:
                return container
        return None

    def search_containers(
        self,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_term: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search containers with filters.

        Args:
            namespace: Filter by namespace (e.g., "BehDNA", "PaDNA")
            tags: Filter by tags (must have all specified tags)
            search_term: Search in ID, description, or path
            limit: Maximum number of results

        Returns:
            List of matching containers
        """
        containers = self._registry.get("containers", [])
        results = []

        for container in containers:
            # Filter by namespace
            if namespace and container.get("namespace") != namespace:
                continue

            # Filter by tags
            if tags:
                container_tags = container.get("tags", [])
                if not all(tag in container_tags for tag in tags):
                    continue

            # Filter by search term
            if search_term:
                search_lower = search_term.lower()
                searchable = " ".join([
                    container.get("id", ""),
                    container.get("description", ""),
                    container.get("path", "")
                ]).lower()

                if search_lower not in searchable:
                    continue

            results.append(container)

            if len(results) >= limit:
                break

        return results

    def get_namespaces(self) -> Dict[str, int]:
        """Get all namespaces with container counts."""
        containers = self._registry.get("containers", [])
        namespaces = {}

        for container in containers:
            ns = container.get("namespace", "unknown")
            namespaces[ns] = namespaces.get(ns, 0) + 1

        return dict(sorted(namespaces.items()))

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        containers = self._registry.get("containers", [])
        metadata = self._registry.get("metadata", {})

        # Count by status
        status_counts = {}
        for container in containers:
            status = container.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count sensitive/camouflage
        sensitive_count = sum(1 for c in containers if c.get("sensitive", False))
        camouflage_count = sum(1 for c in containers if c.get("camouflage", False))
        consent_count = sum(1 for c in containers if c.get("consent_required", False))

        return {
            "total_containers": len(containers),
            "namespaces": self.get_namespaces(),
            "status_breakdown": status_counts,
            "sensitive_containers": sensitive_count,
            "camouflage_containers": camouflage_count,
            "consent_required": consent_count,
            "metadata": metadata
        }


# Singleton instance
_service_instance = None


def get_ontology_service() -> OntologyService:
    """Get the singleton ontology service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = OntologyService()
    return _service_instance
