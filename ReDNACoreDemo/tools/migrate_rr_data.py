#!/usr/bin/env python3
"""
RR Data Migration Script

Migrates user data from legacy RR format (raw UCN values) to new format
(true population percentiles 0-100).

This script:
1. Identifies invalid RR values (>100 or null)
2. Rebuilds population distributions
3. Recalculates correct RR for all users
4. Updates resolved.json files with correct RR/curiosity
5. Creates backup before migration

See: docs/RR_IMPLEMENTATION_REFINEMENTS.md section 11
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.rr_distribution_builder import PopulationDistributionBuilder
from core.rr_per_trait import PerTraitRRCalculator
from core.storage import list_users, read_user_state, write_user_state

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RRDataMigrator:
    """
    Migrates user RR data from legacy format to new percentile-based format.
    """

    def __init__(
        self,
        data_dir: Path,
        distribution_dir: Path,
        backup_dir: Optional[Path] = None,
        k_min: int = 50,
        dry_run: bool = False
    ):
        self.data_dir = Path(data_dir)
        self.distribution_dir = Path(distribution_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else self.data_dir / "backups" / f"rr_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.k_min = k_min
        self.dry_run = dry_run

        self.stats = {
            "users_scanned": 0,
            "users_with_invalid_rr": 0,
            "traits_migrated": 0,
            "traits_unchanged": 0,
            "errors": []
        }

    def analyze_current_state(self) -> Dict:
        """
        Analyze current RR data to identify issues.

        Returns:
            Statistics about current RR data quality
        """
        logger.info("Analyzing current RR data...")

        all_users = list_users()
        analysis = {
            "total_users": len(all_users),
            "users_with_traits": 0,
            "invalid_rr_patterns": {
                "rr_null": 0,
                "rr_greater_than_100": 0,
                "rr_negative": 0,
                "curiosity_null": 0,
                "curiosity_mismatch": 0  # curiosity != 100 - rr
            },
            "trait_distribution": {},
            "sample_invalid_users": []
        }

        for user_entry in all_users:
            user_id = user_entry.get("id")
            if not user_id:
                continue
            try:
                resolved_doc, evidence_doc, obs_doc = read_user_state(user_id)
                if not resolved_doc:
                    continue

                traits = resolved_doc
                if not traits:
                    continue

                analysis["users_with_traits"] += 1
                has_invalid = False

                for trait_path, entry in traits.items():
                    rr = entry.get("rr")
                    curiosity = entry.get("curiosity")

                    # Track trait
                    if trait_path not in analysis["trait_distribution"]:
                        analysis["trait_distribution"][trait_path] = {
                            "total": 0,
                            "valid_rr": 0,
                            "invalid_rr": 0
                        }
                    analysis["trait_distribution"][trait_path]["total"] += 1

                    # Check RR validity
                    if rr is None:
                        analysis["invalid_rr_patterns"]["rr_null"] += 1
                        analysis["trait_distribution"][trait_path]["invalid_rr"] += 1
                        has_invalid = True
                    elif not isinstance(rr, (int, float)):
                        analysis["trait_distribution"][trait_path]["invalid_rr"] += 1
                        has_invalid = True
                    elif rr > 100:
                        analysis["invalid_rr_patterns"]["rr_greater_than_100"] += 1
                        analysis["trait_distribution"][trait_path]["invalid_rr"] += 1
                        has_invalid = True
                    elif rr < 0:
                        analysis["invalid_rr_patterns"]["rr_negative"] += 1
                        analysis["trait_distribution"][trait_path]["invalid_rr"] += 1
                        has_invalid = True
                    else:
                        analysis["trait_distribution"][trait_path]["valid_rr"] += 1

                    # Check curiosity validity
                    if curiosity is None:
                        analysis["invalid_rr_patterns"]["curiosity_null"] += 1
                    elif rr is not None and isinstance(rr, (int, float)) and 0 <= rr <= 100:
                        expected_curiosity = round(100.0 - rr, 2)
                        if abs(curiosity - expected_curiosity) > 0.1:
                            analysis["invalid_rr_patterns"]["curiosity_mismatch"] += 1

                if has_invalid and len(analysis["sample_invalid_users"]) < 5:
                    analysis["sample_invalid_users"].append(user_id)

            except Exception as e:
                logger.warning(f"Error analyzing user {user_id}: {e}")
                continue

        logger.info(f"Analysis complete: {analysis['total_users']} users scanned")

        return analysis

    def create_backup(self) -> Path:
        """
        Create backup of all user data before migration.

        Returns:
            Path to backup directory
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would create backup at: %s", self.backup_dir)
            return self.backup_dir

        logger.info("Creating backup at: %s", self.backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        users_dir = self.data_dir / "users"
        if users_dir.exists():
            backup_users_dir = self.backup_dir / "users"
            shutil.copytree(users_dir, backup_users_dir)
            logger.info("Backed up %d users", len(list(backup_users_dir.iterdir())))

        # Save migration metadata
        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": str(self.data_dir),
            "k_min": self.k_min,
            "migration_type": "rr_percentile_conversion"
        }
        (self.backup_dir / "migration_metadata.json").write_text(
            json.dumps(metadata, indent=2)
        )

        return self.backup_dir

    def rebuild_distributions(self) -> Dict[str, int]:
        """
        Rebuild population distributions from current user data.

        Returns:
            Dictionary of {trait_path: user_count}
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would rebuild population distributions")
            return {}

        logger.info("Rebuilding population distributions...")

        builder = PopulationDistributionBuilder(
            output_dir=self.distribution_dir,
            k_min=5  # Use k_min=5 for distribution building
        )

        trait_counts = builder.build_full_distributions(force_rebuild=True)

        logger.info(f"Built {len(trait_counts)} distributions")

        return trait_counts

    def migrate_user_rr(self, user_id: str, calculator: PerTraitRRCalculator) -> Tuple[int, int]:
        """
        Migrate RR data for a single user.

        Args:
            user_id: User to migrate
            calculator: RR calculator instance

        Returns:
            (traits_migrated, traits_unchanged)
        """
        try:
            resolved_doc, evidence_doc, obs_doc = read_user_state(user_id)
            if not resolved_doc:
                return 0, 0

            traits = resolved_doc
            migrated = 0
            unchanged = 0
            updated = False

            for trait_path, entry in traits.items():
                ucn = entry.get("ucn")
                current_rr = entry.get("rr")

                # Skip if UCN is missing
                if ucn is None:
                    unchanged += 1
                    continue

                # Check if RR needs migration
                needs_migration = (
                    current_rr is None or
                    not isinstance(current_rr, (int, float)) or
                    current_rr > 100 or
                    current_rr < 0
                )

                if not needs_migration:
                    unchanged += 1
                    continue

                # Calculate new RR
                metadata = calculator.calculate_rr_metadata(ucn, trait_path)
                new_rr = metadata["rr"]
                new_curiosity = metadata["curiosity"]

                # Update entry
                if new_rr is not None:
                    entry["rr"] = new_rr
                    entry["curiosity"] = new_curiosity

                    # Add migration provenance
                    if "provenance" not in entry:
                        entry["provenance"] = {}
                    entry["provenance"]["rr_migrated"] = datetime.utcnow().isoformat()
                    entry["provenance"]["rr_method"] = metadata["method"]

                    migrated += 1
                    updated = True
                else:
                    # No distribution available - set to null but mark as attempted
                    entry["rr"] = None
                    entry["curiosity"] = 100.0
                    if "provenance" not in entry:
                        entry["provenance"] = {}
                    entry["provenance"]["rr_migration_attempted"] = datetime.utcnow().isoformat()
                    entry["provenance"]["rr_migration_status"] = "no_distribution"
                    unchanged += 1

            # Save updated resolved.json
            if updated and not self.dry_run:
                write_user_state(user_id, traits, evidence_doc, obs_doc)

            return migrated, unchanged

        except Exception as e:
            logger.error(f"Error migrating user {user_id}: {e}")
            self.stats["errors"].append(f"{user_id}: {str(e)}")
            return 0, 0

    def migrate_all(self) -> Dict:
        """
        Run complete migration process.

        Returns:
            Migration statistics
        """
        logger.info("=" * 60)
        logger.info("RR DATA MIGRATION")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("[DRY RUN MODE - No changes will be made]")

        # Step 1: Analyze current state
        logger.info("\n[1/5] Analyzing current state...")
        analysis = self.analyze_current_state()

        logger.info(f"  - Total users: {analysis['total_users']}")
        logger.info(f"  - Users with traits: {analysis['users_with_traits']}")
        logger.info(f"  - Invalid RR (null): {analysis['invalid_rr_patterns']['rr_null']}")
        logger.info(f"  - Invalid RR (>100): {analysis['invalid_rr_patterns']['rr_greater_than_100']}")
        logger.info(f"  - Invalid RR (negative): {analysis['invalid_rr_patterns']['rr_negative']}")

        # Step 2: Create backup
        logger.info("\n[2/5] Creating backup...")
        backup_path = self.create_backup()
        logger.info(f"  - Backup created at: {backup_path}")

        # Step 3: Rebuild distributions
        logger.info("\n[3/5] Rebuilding population distributions...")
        trait_counts = self.rebuild_distributions()
        logger.info(f"  - Built {len(trait_counts)} trait distributions")

        # Step 4: Migrate user data
        logger.info("\n[4/5] Migrating user RR data...")

        calculator = PerTraitRRCalculator(
            distribution_dir=self.distribution_dir,
            k_min=self.k_min
        )

        all_users = list_users()
        for i, user_entry in enumerate(all_users, 1):
            user_id = user_entry.get("id")
            if not user_id:
                continue

            migrated, unchanged = self.migrate_user_rr(user_id, calculator)

            self.stats["users_scanned"] += 1
            self.stats["traits_migrated"] += migrated
            self.stats["traits_unchanged"] += unchanged

            if migrated > 0:
                self.stats["users_with_invalid_rr"] += 1
                logger.info(f"  [{i}/{len(all_users)}] {user_id}: {migrated} traits migrated")
            elif i % 10 == 0:
                logger.info(f"  [{i}/{len(all_users)}] Progress...")

        # Step 5: Summary
        logger.info("\n[5/5] Migration complete!")
        logger.info("=" * 60)
        logger.info("SUMMARY:")
        logger.info(f"  - Users scanned: {self.stats['users_scanned']}")
        logger.info(f"  - Users with invalid RR: {self.stats['users_with_invalid_rr']}")
        logger.info(f"  - Traits migrated: {self.stats['traits_migrated']}")
        logger.info(f"  - Traits unchanged: {self.stats['traits_unchanged']}")
        logger.info(f"  - Errors: {len(self.stats['errors'])}")

        if self.stats["errors"]:
            logger.warning("\nErrors encountered:")
            for error in self.stats["errors"][:10]:  # Show first 10
                logger.warning(f"  - {error}")
            if len(self.stats["errors"]) > 10:
                logger.warning(f"  ... and {len(self.stats['errors']) - 10} more")

        logger.info(f"\nBackup saved to: {backup_path}")
        logger.info("=" * 60)

        return {
            "analysis": analysis,
            "stats": self.stats,
            "backup_path": str(backup_path)
        }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate RR data to new percentile format")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="User data directory (default: data/)"
    )
    parser.add_argument(
        "--distribution-dir",
        type=Path,
        default=Path("data/population_distributions"),
        help="Distribution output directory (default: data/population_distributions/)"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Backup directory (default: data/backups/rr_migration_<timestamp>/)"
    )
    parser.add_argument(
        "--k-min",
        type=int,
        default=50,
        help="Minimum population for RR calculation (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, don't make changes"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only run analysis, skip migration"
    )

    args = parser.parse_args()

    migrator = RRDataMigrator(
        data_dir=args.data_dir,
        distribution_dir=args.distribution_dir,
        backup_dir=args.backup_dir,
        k_min=args.k_min,
        dry_run=args.dry_run
    )

    if args.analyze_only:
        analysis = migrator.analyze_current_state()
        print(json.dumps(analysis, indent=2))
    else:
        result = migrator.migrate_all()
        print("\nMigration complete!")
        print(f"See backup at: {result['backup_path']}")


if __name__ == "__main__":
    main()
