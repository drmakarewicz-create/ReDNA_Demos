"""
Quarantine Tracker - Collects and analyzes unmapped trait paths for schema evolution.

This module tracks traits that couldn't be mapped to PaDNA paths during import,
providing insights for:
1. Creating new PaDNA containers
2. Adding path aliases
3. Understanding user data patterns
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

QUARANTINE_REGISTRY = Path(__file__).parent.parent / "data" / "quarantine_registry.json"


class QuarantineTracker:
    """Tracks and analyzes quarantined trait paths."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or QUARANTINE_REGISTRY
        self.data = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load the quarantine registry from disk."""
        if not self.registry_path.exists():
            return {
                "schema_version": "1.0",
                "description": "Registry of quarantined trait paths",
                "last_updated": None,
                "statistics": {
                    "total_unique_paths": 0,
                    "total_occurrences": 0,
                    "paths_by_category": {}
                },
                "quarantined_paths": {},
            }

        try:
            with self.registry_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Failed to load quarantine registry: {exc}")
            return {"quarantined_paths": {}, "statistics": {}}

    def _save_registry(self) -> None:
        """Save the quarantine registry to disk."""
        self.data["last_updated"] = datetime.now().isoformat()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self.registry_path.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"Failed to save quarantine registry: {exc}")

    def record_quarantined_items(
        self,
        items: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        source: Optional[str] = None
    ) -> None:
        """
        Record quarantined items from an import.

        Args:
            items: List of quarantined items with raw_path, raw_value, reasons
            user_id: Optional user identifier
            source: Optional source identifier (e.g., filename)
        """
        if not items:
            return

        quarantined_paths = self.data.setdefault("quarantined_paths", {})
        timestamp = datetime.now().isoformat()

        for item in items:
            raw_path = str(item.get("raw_path", ""))
            if not raw_path:
                continue

            reasons = item.get("reasons", [])
            raw_value = item.get("raw_value")

            # Only track unmapped paths (not other errors)
            if not any("unmapped" in str(r).lower() for r in reasons):
                continue

            # Initialize or retrieve path entry
            if raw_path not in quarantined_paths:
                quarantined_paths[raw_path] = {
                    "path": raw_path,
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "occurrence_count": 0,
                    "example_values": [],
                    "sources": [],
                    "users": set(),
                    "status": "pending",  # pending, mapped, promoted, rejected
                    "notes": "",
                    "suggested_mapping": None,
                    "category": self._categorize_path(raw_path),
                }

            entry = quarantined_paths[raw_path]
            entry["last_seen"] = timestamp
            entry["occurrence_count"] += 1

            # Add example value if not already present
            if len(entry["example_values"]) < 5:
                value_str = self._serialize_value(raw_value)
                if value_str not in entry["example_values"]:
                    entry["example_values"].append(value_str)

            # Track sources
            if source and source not in entry["sources"]:
                entry["sources"].append(source)

            # Track users (convert set to list for JSON serialization)
            if user_id:
                users_set = set(entry["users"]) if isinstance(entry["users"], list) else entry["users"]
                users_set.add(user_id)
                entry["users"] = list(users_set)

        self._update_statistics()
        self._save_registry()
        logger.info(f"Recorded {len(items)} quarantined paths to registry")

    def _categorize_path(self, path: str) -> str:
        """Categorize a path based on its prefix or structure."""
        if not isinstance(path, str):
            return "unknown"

        path_lower = path.lower()

        # Known namespaces
        if path.startswith("PaDNA."):
            return "PaDNA"
        elif "behavioral" in path_lower or "behavior" in path_lower:
            return "Behavioral"
        elif "style" in path_lower or "fashion" in path_lower or "era" in path_lower:
            return "Style"
        elif "personality" in path_lower or "social" in path_lower:
            return "Personality"
        elif "movement" in path_lower or "posture" in path_lower:
            return "Movement"
        elif "context" in path_lower or "setting" in path_lower:
            return "Context"
        else:
            return "Other"

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value for storage as an example."""
        if isinstance(value, str):
            return value[:100]  # Truncate long strings
        elif isinstance(value, (list, dict)):
            try:
                return json.dumps(value, ensure_ascii=False)[:100]
            except:
                return str(value)[:100]
        else:
            return str(value)[:100]

    def _update_statistics(self) -> None:
        """Update statistics based on current quarantined paths."""
        paths = self.data.get("quarantined_paths", {})

        stats = {
            "total_unique_paths": len(paths),
            "total_occurrences": sum(p.get("occurrence_count", 0) for p in paths.values()),
            "paths_by_category": defaultdict(int),
            "paths_by_status": defaultdict(int),
            "most_frequent": [],
        }

        for path_data in paths.values():
            category = path_data.get("category", "Other")
            status = path_data.get("status", "pending")
            stats["paths_by_category"][category] += 1
            stats["paths_by_status"][status] += 1

        # Convert defaultdict to regular dict for JSON serialization
        stats["paths_by_category"] = dict(stats["paths_by_category"])
        stats["paths_by_status"] = dict(stats["paths_by_status"])

        # Top 20 most frequent paths
        sorted_paths = sorted(
            paths.items(),
            key=lambda x: x[1].get("occurrence_count", 0),
            reverse=True
        )
        stats["most_frequent"] = [
            {
                "path": path,
                "count": data.get("occurrence_count", 0),
                "category": data.get("category", "Other")
            }
            for path, data in sorted_paths[:20]
        ]

        self.data["statistics"] = stats

    def get_pending_paths(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all pending (unresolved) quarantined paths.

        Args:
            category: Optional filter by category

        Returns:
            List of path entries with status "pending"
        """
        paths = self.data.get("quarantined_paths", {})
        pending = [
            p for p in paths.values()
            if p.get("status") == "pending"
        ]

        if category:
            pending = [p for p in pending if p.get("category") == category]

        return sorted(pending, key=lambda x: x.get("occurrence_count", 0), reverse=True)

    def mark_path_status(
        self,
        path: str,
        status: str,
        notes: Optional[str] = None,
        suggested_mapping: Optional[str] = None
    ) -> bool:
        """
        Update the status of a quarantined path.

        Args:
            path: The quarantined path
            status: New status (pending, mapped, promoted, rejected)
            notes: Optional notes about the decision
            suggested_mapping: Optional canonical path mapping

        Returns:
            True if successful
        """
        paths = self.data.get("quarantined_paths", {})
        if path not in paths:
            logger.warning(f"Path not found in registry: {path}")
            return False

        paths[path]["status"] = status
        if notes:
            paths[path]["notes"] = notes
        if suggested_mapping:
            paths[path]["suggested_mapping"] = suggested_mapping

        self._update_statistics()
        self._save_registry()
        return True

    def export_for_review(self, output_path: Path, category: Optional[str] = None) -> None:
        """
        Export pending paths to a human-readable file for review.

        Args:
            output_path: Path to write the review file
            category: Optional filter by category
        """
        pending = self.get_pending_paths(category=category)

        review_data = {
            "generated_at": datetime.now().isoformat(),
            "category_filter": category,
            "total_pending_paths": len(pending),
            "instructions": [
                "Review each path below and decide:",
                "1. PROMOTE: Create a new PaDNA container for this trait",
                "2. MAP: Create an alias to an existing PaDNA path",
                "3. REJECT: Ignore this path (not relevant)",
                "",
                "For each decision, fill in the 'status', 'suggested_mapping', and 'notes' fields.",
            ],
            "paths": [
                {
                    "path": p["path"],
                    "category": p.get("category", "Other"),
                    "occurrence_count": p.get("occurrence_count", 0),
                    "example_values": p.get("example_values", []),
                    "first_seen": p.get("first_seen"),
                    "last_seen": p.get("last_seen"),
                    "decision": {
                        "status": "pending",  # Change to: mapped, promoted, or rejected
                        "suggested_mapping": None,  # e.g., "PaDNA.MovementDNA.Posture"
                        "notes": ""  # Explanation of decision
                    }
                }
                for p in pending
            ]
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(review_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(pending)} pending paths to {output_path}")

    def import_review_decisions(self, review_file: Path) -> int:
        """
        Import decisions from a review file and update the registry.

        Args:
            review_file: Path to the review file with decisions

        Returns:
            Number of paths updated
        """
        with review_file.open("r", encoding="utf-8") as f:
            review_data = json.load(f)

        updated = 0
        for path_entry in review_data.get("paths", []):
            decision = path_entry.get("decision", {})
            status = decision.get("status")

            if status and status != "pending":
                path = path_entry["path"]
                notes = decision.get("notes", "")
                mapping = decision.get("suggested_mapping")

                if self.mark_path_status(path, status, notes, mapping):
                    updated += 1

        logger.info(f"Imported decisions for {updated} paths from review file")
        return updated


# Global instance
_tracker: Optional[QuarantineTracker] = None


def get_tracker() -> QuarantineTracker:
    """Get or create the global quarantine tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = QuarantineTracker()
    return _tracker


def record_quarantine(
    items: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    source: Optional[str] = None
) -> None:
    """Convenience function to record quarantined items."""
    if items:
        get_tracker().record_quarantined_items(items, user_id, source)
