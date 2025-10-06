"""
Trait Container Discovery and Registry
========================================

Dynamically discovers and registers new trait containers from HC conversations.

Instead of manually defining every possible trait container, this system:
1. Observes what preferences/facts emerge from conversations
2. Auto-registers new container categories
3. Tracks usage and confidence over time
4. Integrates with existing ReDNA schema

Example:
- User says "I love comedies" → Discovers container: preferences.entertainment.tv_genres
- User says "I prefer Italian food" → Discovers container: preferences.food.cuisine_types
- User says "I'm introverted" → Discovers container: personality.social_preferences
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from . import storage

logger = logging.getLogger(__name__)


class TraitContainerRegistry:
    """
    Registry for dynamically discovered trait containers.

    Maintains a catalog of all observed trait categories and their metadata.
    """

    def __init__(self, data_root: Optional[Path] = None):
        """Initialize the registry."""
        if data_root is None:
            data_root = storage.CORE_DATA_ROOT

        self.data_root = Path(data_root)
        self.registry_path = self.data_root / "config" / "discovered_trait_containers.json"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._containers: Dict[str, Dict[str, Any]] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path) as f:
                    data = json.load(f)
                    self._containers = data.get("containers", {})
                    logger.info(f"Loaded {len(self._containers)} trait containers from registry")
            except Exception as e:
                logger.error(f"Failed to load trait container registry: {e}")
                self._containers = {}
        else:
            # Initialize with base containers from static schema
            self._seed_base_containers()

    def _seed_base_containers(self) -> None:
        """Seed registry with base containers from existing schema."""
        base_containers = {
            # PaDNA (from Expanded_DNA_Containers_v2.md)
            "padna.facial": {
                "category": "PaDNA",
                "subcategory": "Facial Features",
                "description": "Facial landmarks and characteristics",
                "sensitive": True,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },
            "padna.hair": {
                "category": "PaDNA",
                "subcategory": "Hair",
                "description": "Hair color, texture, style",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },
            "padna.skin": {
                "category": "PaDNA",
                "subcategory": "Skin",
                "description": "Skin tone, undertone, features",
                "sensitive": True,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },
            "padna.voice": {
                "category": "PaDNA",
                "subcategory": "Voice",
                "description": "Voice characteristics",
                "sensitive": True,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },

            # Conversational (from v2 schema)
            "conversation.dynamics": {
                "category": "Conversational",
                "subcategory": "Dynamics",
                "description": "Response patterns and cadence",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },
            "conversation.tone": {
                "category": "Conversational",
                "subcategory": "Tone & Affect",
                "description": "Communication style and sentiment",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },

            # Preferences (dynamically extended)
            "preferences.entertainment": {
                "category": "Preferences",
                "subcategory": "Entertainment",
                "description": "TV, movies, books, music preferences",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },
            "preferences.food": {
                "category": "Preferences",
                "subcategory": "Food & Dining",
                "description": "Food, cuisine, dining preferences",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },
            "preferences.lifestyle": {
                "category": "Preferences",
                "subcategory": "Lifestyle",
                "description": "Daily habits, routines, choices",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },

            # Personality
            "personality.traits": {
                "category": "Personality",
                "subcategory": "Core Traits",
                "description": "Big 5, MBTI-like traits",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },

            # Social
            "social.relationships": {
                "category": "Social",
                "subcategory": "Relationships",
                "description": "Relationship patterns and preferences",
                "sensitive": False,
                "source": "static_schema",
                "first_observed": datetime.now(timezone.utc).isoformat(),
                "observation_count": 0,
            },
        }

        self._containers = base_containers
        self._save_registry()
        logger.info(f"Seeded {len(base_containers)} base trait containers")

    def _save_registry(self) -> None:
        """Save registry to disk."""
        try:
            data = {
                "version": "1.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "containers": self._containers,
            }

            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved trait container registry with {len(self._containers)} containers")
        except Exception as e:
            logger.error(f"Failed to save trait container registry: {e}")

    def discover_container(
        self,
        trait_path: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        sensitive: bool = False,
    ) -> bool:
        """
        Discover and register a new trait container from an observed trait path.

        Args:
            trait_path: Full trait path like "preferences.entertainment.tv_genres.comedy"
            category: High-level category (Preferences, PaDNA, Personality, etc.)
            description: Human-readable description
            sensitive: Whether this contains sensitive data

        Returns:
            True if new container was discovered, False if already existed
        """
        # Extract container path (everything except the leaf)
        parts = trait_path.split(".")

        if len(parts) < 2:
            # Not hierarchical enough to be a container
            return False

        # Try different container granularities
        # E.g., for "preferences.entertainment.tv_genres.comedy":
        # - preferences.entertainment.tv_genres
        # - preferences.entertainment
        # - preferences

        discovered_new = False

        for depth in range(2, len(parts)):
            container_path = ".".join(parts[:depth])

            if container_path not in self._containers:
                # New container discovered!
                logger.info(f"🔍 Discovered new trait container: {container_path}")

                # Infer category from path
                if category is None:
                    category = self._infer_category(parts[0])

                # Infer subcategory
                subcategory = " ".join(parts[1:depth]).replace("_", " ").title()

                # Infer description
                if description is None:
                    description = f"{subcategory} related traits"

                self._containers[container_path] = {
                    "category": category,
                    "subcategory": subcategory,
                    "description": description,
                    "sensitive": sensitive,
                    "source": "discovered_from_conversation",
                    "first_observed": datetime.now(timezone.utc).isoformat(),
                    "observation_count": 1,
                    "example_traits": [trait_path],
                }

                discovered_new = True
            else:
                # Existing container - increment count and add example
                container = self._containers[container_path]
                container["observation_count"] = container.get("observation_count", 0) + 1

                examples = container.get("example_traits", [])
                if trait_path not in examples:
                    examples.append(trait_path)
                    container["example_traits"] = examples[:10]  # Keep max 10 examples

        if discovered_new:
            self._save_registry()

        return discovered_new

    def _infer_category(self, first_part: str) -> str:
        """Infer high-level category from first path part."""
        category_map = {
            "preferences": "Preferences",
            "padna": "PaDNA",
            "personality": "Personality",
            "social": "Social",
            "conversation": "Conversational",
            "professional": "Professional",
            "attributes": "Physical Attributes",
            "motivations": "Motivations & Goals",
            "habits": "Habits & Routines",
        }

        return category_map.get(first_part.lower(), first_part.title())

    def get_all_containers(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered containers."""
        return dict(self._containers)

    def get_containers_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """Get all containers in a specific category."""
        return {
            path: meta
            for path, meta in self._containers.items()
            if meta.get("category") == category
        }

    def get_container_stats(self) -> Dict[str, Any]:
        """Get statistics about discovered containers."""
        total = len(self._containers)
        by_category = defaultdict(int)
        by_source = defaultdict(int)
        sensitive_count = 0

        for meta in self._containers.values():
            by_category[meta.get("category", "Unknown")] += 1
            by_source[meta.get("source", "unknown")] += 1
            if meta.get("sensitive", False):
                sensitive_count += 1

        return {
            "total_containers": total,
            "by_category": dict(by_category),
            "by_source": dict(by_source),
            "sensitive_containers": sensitive_count,
            "discovery_enabled": True,
        }


# Global registry instance
_registry: Optional[TraitContainerRegistry] = None


def get_registry() -> TraitContainerRegistry:
    """Get or create the global registry instance."""
    global _registry
    if _registry is None:
        _registry = TraitContainerRegistry()
    return _registry


def discover_from_trait_path(
    trait_path: str,
    category: Optional[str] = None,
    description: Optional[str] = None,
    sensitive: bool = False,
) -> bool:
    """
    Convenience function to discover a container from a trait path.

    Args:
        trait_path: Full trait path
        category: Optional category override
        description: Optional description
        sensitive: Whether container is sensitive

    Returns:
        True if new container discovered
    """
    registry = get_registry()
    return registry.discover_container(trait_path, category, description, sensitive)


def get_all_containers() -> Dict[str, Dict[str, Any]]:
    """Convenience function to get all containers."""
    registry = get_registry()
    return registry.get_all_containers()


def get_container_stats() -> Dict[str, Any]:
    """Convenience function to get container stats."""
    registry = get_registry()
    return registry.get_container_stats()
