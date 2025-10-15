"""
Container and Overall RR Aggregation

Calculates multi-level RR hierarchy:
- Per-Trait RR (handled by rr_per_trait.py)
- Container RR (e.g., PaDNA, ReDNA, HeritDNA)
- Overall User RR (global refinement score)

See: docs/RR_ARCHITECTURE_MULTILEVEL.md sections 1-3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ReDNACoreDemo.core.rr_per_trait import PerTraitRRCalculator
from ReDNACoreDemo.core.storage import read_user_state

logger = logging.getLogger(__name__)


class ContainerRRAggregator:
    """
    Aggregates per-trait RR into container-level and overall RR scores.

    Uses coverage-weighted averaging to balance:
    - Population quality (how many users have this trait)
    - Data quality (how confident we are in this user's value)
    """

    def __init__(
        self,
        distribution_dir: Path,
        k_min: int = 50,
        alpha: float = 0.5,
    ):
        """
        Args:
            distribution_dir: Path to population distributions
            k_min: Minimum population for RR calculation
            alpha: Coverage weight (0=all UCN, 1=all population size)
        """
        self.rr_calculator = PerTraitRRCalculator(
            distribution_dir=distribution_dir,
            k_min=k_min
        )
        self.alpha = alpha  # Coverage weight parameter

    def _calculate_coverage_weight(
        self,
        ucn: float,
        population_size: int
    ) -> float:
        """
        Calculate coverage weight for a trait.

        Weight = α × (population_size / 1000) + (1-α) × (ucn / 1000)

        This balances:
        - Population quality: More users = more reliable RR
        - Data quality: Higher UCN = more confident value

        Args:
            ucn: User's UCN for this trait (0-1000)
            population_size: Number of users with this trait

        Returns:
            Weight in [0, 1]
        """
        # Normalize population size (cap at 1000 users)
        pop_norm = min(1.0, population_size / 1000.0)

        # Normalize UCN
        ucn_norm = min(1.0, ucn / 1000.0)

        # Weighted combination
        weight = self.alpha * pop_norm + (1 - self.alpha) * ucn_norm

        return max(0.0, min(1.0, weight))

    def calculate_container_rr(
        self,
        user_id: str,
        container: str
    ) -> Optional[Dict]:
        """
        Calculate RR for a DNA container (e.g., PaDNA, ReDNA).

        Args:
            user_id: User to calculate for
            container: Container name (e.g., "PaDNA")

        Returns:
            Dictionary with:
            - rr: Container RR (0-100)
            - curiosity: Container curiosity (100 - RR)
            - trait_count: Number of traits in container
            - coverage: Total weight (sum of coverage weights)
            - traits: List of trait RRs with weights
        """
        try:
            resolved, _, _ = read_user_state(user_id)
            if not resolved:
                return None

            # Collect traits in this container
            container_traits: List[Tuple[str, float, float, int]] = []  # (path, rr, ucn, pop_size)

            for trait_path, entry in resolved.items():
                if not trait_path.startswith(container + "."):
                    continue

                ucn = entry.get("ucn")
                if ucn is None or not isinstance(ucn, (int, float)):
                    continue

                # Get RR metadata
                metadata = self.rr_calculator.calculate_rr_metadata(ucn, trait_path)
                rr = metadata["rr"]

                if rr is None:
                    continue

                population_size = metadata["population_size"]
                container_traits.append((trait_path, rr, float(ucn), population_size))

            if not container_traits:
                return None

            # Calculate weighted average RR
            total_weight = 0.0
            weighted_rr_sum = 0.0
            trait_details = []

            for trait_path, rr, ucn, pop_size in container_traits:
                weight = self._calculate_coverage_weight(ucn, pop_size)

                weighted_rr_sum += rr * weight
                total_weight += weight

                trait_details.append({
                    "trait_path": trait_path,
                    "rr": rr,
                    "ucn": ucn,
                    "population_size": pop_size,
                    "weight": round(weight, 4)
                })

            # Container RR
            if total_weight > 0:
                container_rr = weighted_rr_sum / total_weight
            else:
                container_rr = 0.0

            return {
                "container": container,
                "rr": round(container_rr, 2),
                "curiosity": round(100.0 - container_rr, 2),
                "trait_count": len(container_traits),
                "coverage": round(total_weight, 2),
                "traits": trait_details
            }

        except Exception as e:
            logger.error(f"Error calculating container RR for {user_id}/{container}: {e}")
            return None

    def calculate_overall_rr(
        self,
        user_id: str,
        containers: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Calculate overall user RR across all containers.

        Args:
            user_id: User to calculate for
            containers: List of containers to include, or None for all

        Returns:
            Dictionary with:
            - rr: Overall RR (0-100)
            - curiosity: Overall curiosity (100 - RR)
            - container_count: Number of containers
            - trait_count: Total number of traits
            - containers: List of container RRs with weights
        """
        # Default containers if not specified
        if containers is None:
            containers = [
                "PaDNA",    # Physical Appearance
                "ReDNA",    # Relationship
                "HeritDNA", # Heritage
                "FinDNA",   # Financial
                "HealthDNA",# Health
                "FamilyDNA",# Family
                "CareerDNA",# Career
                "HobbyDNA", # Hobbies
                "ValuesDNA",# Values
                "GoalsDNA"  # Goals
            ]

        container_results = []
        total_weight = 0.0
        weighted_rr_sum = 0.0
        total_traits = 0

        for container in containers:
            result = self.calculate_container_rr(user_id, container)

            if result is None:
                continue

            # Weight each container by its coverage
            weight = result["coverage"]

            weighted_rr_sum += result["rr"] * weight
            total_weight += weight
            total_traits += result["trait_count"]

            container_results.append({
                "container": container,
                "rr": result["rr"],
                "curiosity": result["curiosity"],
                "trait_count": result["trait_count"],
                "weight": round(weight, 2)
            })

        if not container_results:
            return None

        # Overall RR
        if total_weight > 0:
            overall_rr = weighted_rr_sum / total_weight
        else:
            overall_rr = 0.0

        return {
            "rr": round(overall_rr, 2),
            "curiosity": round(100.0 - overall_rr, 2),
            "container_count": len(container_results),
            "trait_count": total_traits,
            "total_weight": round(total_weight, 2),
            "containers": container_results
        }

    def calculate_all_levels(
        self,
        user_id: str,
        containers: Optional[List[str]] = None
    ) -> Dict:
        """
        Calculate RR at all three levels: trait, container, overall.

        Args:
            user_id: User to calculate for
            containers: List of containers to include

        Returns:
            Dictionary with:
            - overall: Overall RR summary
            - containers: Container-level RRs
            - per_trait: Per-trait RRs (optional, can be large)
        """
        overall = self.calculate_overall_rr(user_id, containers)

        if overall is None:
            return {
                "overall": None,
                "containers": [],
                "error": "No valid RR data for user"
            }

        # Get detailed container breakdowns
        container_details = []
        for container_summary in overall["containers"]:
            container = container_summary["container"]
            container_detail = self.calculate_container_rr(user_id, container)
            if container_detail:
                container_details.append(container_detail)

        return {
            "overall": {
                "rr": overall["rr"],
                "curiosity": overall["curiosity"],
                "container_count": overall["container_count"],
                "trait_count": overall["trait_count"]
            },
            "containers": container_details
        }


def calculate_user_rr_summary(
    user_id: str,
    distribution_dir: Path,
    k_min: int = 50,
    alpha: float = 0.5
) -> Dict:
    """
    Convenience function to calculate user RR at all levels.

    Args:
        user_id: User to calculate for
        distribution_dir: Path to population distributions
        k_min: Minimum population for RR calculation
        alpha: Coverage weight (0=all UCN, 1=all population)

    Returns:
        Multi-level RR summary
    """
    aggregator = ContainerRRAggregator(
        distribution_dir=distribution_dir,
        k_min=k_min,
        alpha=alpha
    )

    return aggregator.calculate_all_levels(user_id)


if __name__ == "__main__":
    import json
    import sys

    # CLI usage: python -m core.rr_aggregation <user_id>
    if len(sys.argv) < 2:
        print("Usage: python -m core.rr_aggregation <user_id>")
        sys.exit(1)

    user_id = sys.argv[1]
    distribution_dir = Path("data/population_distributions")

    summary = calculate_user_rr_summary(user_id, distribution_dir)

    print(json.dumps(summary, indent=2))
