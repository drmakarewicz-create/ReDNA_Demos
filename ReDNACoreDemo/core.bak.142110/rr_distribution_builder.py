"""
Population Distribution Builder

Builds trait-level population distributions from all user data.
Supports versioning, privacy guarantees, and incremental updates.

See: docs/RR_IMPLEMENTATION_REFINEMENTS.md section 3
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.rr_histogram import TraitDistributionHistogram, build_distribution_from_users
from core.storage import list_users, read_user_state

logger = logging.getLogger(__name__)


class PopulationDistributionBuilder:
    """
    Builds and maintains population distributions for RR calculation.

    Features:
    - Incremental updates (add new users without full rebuild)
    - Versioning with timestamps
    - Privacy guarantees (k-anonymity)
    - Outlier protection (winsorization)
    """

    def __init__(
        self,
        output_dir: Path,
        k_min: int = 5,
        num_bins: int = 100,
        winsorize_percentiles: tuple[float, float] = (1.0, 99.0)
    ):
        self.output_dir = Path(output_dir)
        self.k_min = k_min
        self.num_bins = num_bins
        self.winsorize_percentiles = winsorize_percentiles

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track which users are included in current distributions
        self.manifest_path = self.output_dir / "manifest.json"
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict:
        """Load distribution manifest tracking what's been built."""
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {
            "version": 1,
            "last_updated": None,
            "users_included": [],
            "trait_counts": {},
            "build_history": []
        }

    def _save_manifest(self):
        """Save updated manifest."""
        self.manifest["last_updated"] = datetime.utcnow().isoformat()
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2))

    def build_full_distributions(self, force_rebuild: bool = False) -> Dict[str, int]:
        """
        Build distributions for all traits across all users.

        Args:
            force_rebuild: If True, rebuild even if up-to-date

        Returns:
            Dictionary of {trait_path: user_count}
        """
        logger.info("Starting full distribution build...")

        # Get all users
        all_user_entries = list_users()
        all_user_ids = [u.get("id") for u in all_user_entries if u.get("id")]

        # Check if rebuild needed
        if not force_rebuild:
            existing_users = set(self.manifest.get("users_included", []))
            if existing_users == set(all_user_ids):
                logger.info("Distributions already up-to-date")
                return self.manifest.get("trait_counts", {})

        # Collect all trait UCNs across all users
        trait_ucns: Dict[str, Dict[str, float]] = {}  # {trait_path: {user_id: ucn}}

        for user_id in all_user_ids:
            try:
                resolved, _, _ = read_user_state(user_id)
                if not resolved:
                    continue

                for trait_path, entry in resolved.items():
                    ucn = entry.get("ucn")
                    if ucn is not None and isinstance(ucn, (int, float)):
                        if trait_path not in trait_ucns:
                            trait_ucns[trait_path] = {}
                        trait_ucns[trait_path][user_id] = float(ucn)

            except Exception as e:
                logger.warning(f"Error reading user {user_id}: {e}")
                continue

        # Build histogram for each trait
        trait_counts = {}
        distributions_built = 0

        for trait_path, user_ucn_map in trait_ucns.items():
            try:
                # Only build if we have enough users for privacy
                if len(user_ucn_map) < self.k_min:
                    logger.warning(
                        f"Skipping {trait_path}: only {len(user_ucn_map)} users "
                        f"(k_min={self.k_min})"
                    )
                    continue

                # Build distribution
                hist = build_distribution_from_users(
                    trait_path=trait_path,
                    user_traits=user_ucn_map,
                    output_dir=self.output_dir,
                    k_min=self.k_min
                )

                # Validate privacy
                privacy = hist.validate_privacy()
                if not privacy["valid"]:
                    logger.error(
                        f"Privacy violation for {trait_path}: {privacy['message']}"
                    )
                    continue

                trait_counts[trait_path] = len(user_ucn_map)
                distributions_built += 1

            except Exception as e:
                logger.error(f"Error building distribution for {trait_path}: {e}")
                continue

        # Update manifest
        self.manifest["users_included"] = all_user_ids
        self.manifest["trait_counts"] = trait_counts
        self.manifest["build_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "full_rebuild",
            "users": len(all_user_ids),
            "traits": distributions_built
        })
        self._save_manifest()

        logger.info(
            f"Built {distributions_built} distributions from {len(all_user_ids)} users"
        )

        return trait_counts

    def update_incremental(self, new_user_ids: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Incrementally update distributions with new users.

        Args:
            new_user_ids: Specific users to add, or None to auto-detect new users

        Returns:
            Dictionary of {trait_path: updated_user_count}
        """
        # Determine which users are new
        all_user_entries = list_users()
        all_user_ids = {u.get("id") for u in all_user_entries if u.get("id")}
        included_users = set(self.manifest.get("users_included", []))

        if new_user_ids is None:
            new_users = all_user_ids - included_users
        else:
            new_users = set(new_user_ids) & all_user_ids  # Only valid users

        if not new_users:
            logger.info("No new users to add")
            return self.manifest.get("trait_counts", {})

        logger.info(f"Incrementally updating with {len(new_users)} new users...")

        # Collect UCNs from new users
        new_trait_ucns: Dict[str, Dict[str, float]] = {}

        for user_id in new_users:
            try:
                resolved, _, _ = read_user_state(user_id)
                if not resolved:
                    continue

                for trait_path, entry in resolved.items():
                    ucn = entry.get("ucn")
                    if ucn is not None and isinstance(ucn, (int, float)):
                        if trait_path not in new_trait_ucns:
                            new_trait_ucns[trait_path] = {}
                        new_trait_ucns[trait_path][user_id] = float(ucn)

            except Exception as e:
                logger.warning(f"Error reading user {user_id}: {e}")
                continue

        # Update existing distributions
        updated_traits = {}

        for trait_path, new_ucns in new_trait_ucns.items():
            try:
                # Load existing distribution
                hist_path = self.output_dir / f"{trait_path.replace('.', '_')}.json"

                if hist_path.exists():
                    # Incremental update
                    hist = TraitDistributionHistogram.load(hist_path)

                    # Add new UCNs
                    hist.add_ucns(
                        list(new_ucns.values()),
                        winsorize=True,
                        winsorize_percentiles=self.winsorize_percentiles
                    )

                    # Validate privacy
                    privacy = hist.validate_privacy()
                    if not privacy["valid"]:
                        logger.error(
                            f"Privacy violation for {trait_path}: {privacy['message']}"
                        )
                        continue

                    # Save updated distribution
                    hist.save(self.output_dir)
                    updated_traits[trait_path] = hist.total_count

                else:
                    # New trait - check if we have enough users
                    if len(new_ucns) >= self.k_min:
                        hist = build_distribution_from_users(
                            trait_path=trait_path,
                            user_traits=new_ucns,
                            output_dir=self.output_dir,
                            k_min=self.k_min
                        )
                        updated_traits[trait_path] = hist.total_count

            except Exception as e:
                logger.error(f"Error updating distribution for {trait_path}: {e}")
                continue

        # Update manifest
        self.manifest["users_included"] = list(all_user_ids)
        self.manifest["trait_counts"].update(updated_traits)
        self.manifest["build_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "incremental",
            "new_users": list(new_users),
            "traits_updated": len(updated_traits)
        })
        self._save_manifest()

        logger.info(f"Updated {len(updated_traits)} trait distributions")

        return updated_traits

    def get_distribution_stats(self) -> Dict:
        """Get statistics about current distributions."""
        trait_counts = self.manifest.get("trait_counts", {})

        if not trait_counts:
            return {
                "total_traits": 0,
                "total_users": 0,
                "last_updated": None
            }

        return {
            "total_traits": len(trait_counts),
            "total_users": len(self.manifest.get("users_included", [])),
            "last_updated": self.manifest.get("last_updated"),
            "trait_counts": trait_counts,
            "min_population": min(trait_counts.values()) if trait_counts else 0,
            "max_population": max(trait_counts.values()) if trait_counts else 0,
            "avg_population": sum(trait_counts.values()) / len(trait_counts) if trait_counts else 0
        }

    def remove_user(self, user_id: str) -> bool:
        """
        Remove a user from distributions (requires full rebuild).

        Note: For privacy reasons, we cannot surgically remove a user.
        This marks the user for removal and triggers a full rebuild.
        """
        included = set(self.manifest.get("users_included", []))

        if user_id not in included:
            return False

        # Trigger full rebuild without this user
        logger.info(f"Removing user {user_id}, triggering full rebuild...")
        self.manifest["users_included"] = [u for u in included if u != user_id]
        self._save_manifest()

        return self.build_full_distributions(force_rebuild=True)


def build_all_distributions(
    output_dir: Path,
    k_min: int = 5,
    force_rebuild: bool = False
) -> Dict[str, int]:
    """
    Convenience function to build all distributions.

    Args:
        output_dir: Where to save distribution files
        k_min: Minimum users required for privacy
        force_rebuild: Rebuild even if up-to-date

    Returns:
        Dictionary of {trait_path: user_count}
    """
    builder = PopulationDistributionBuilder(
        output_dir=output_dir,
        k_min=k_min
    )

    return builder.build_full_distributions(force_rebuild=force_rebuild)


if __name__ == "__main__":
    import sys

    # CLI usage: python -m core.rr_distribution_builder [--force]
    force = "--force" in sys.argv

    output_dir = Path("data/population_distributions")

    stats_before = PopulationDistributionBuilder(output_dir).get_distribution_stats()
    print(f"Before: {stats_before['total_traits']} traits, {stats_before['total_users']} users")

    trait_counts = build_all_distributions(output_dir, force_rebuild=force)

    print(f"\nBuilt {len(trait_counts)} distributions:")
    for trait_path, count in sorted(trait_counts.items()):
        print(f"  {trait_path}: {count} users")
