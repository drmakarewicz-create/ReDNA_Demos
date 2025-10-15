"""
Curiosity Engine

Integrates RR (Refinement Rating) system with DNA ontology to drive data collection priorities.

Key Formula: Curiosity = 100 - RR

High curiosity (low RR) traits get priority attention from AI coaches.
Curiosity scores propagate up the container hierarchy to identify knowledge gaps.

Integration Points:
- Per-trait curiosity: Direct from RR calculator
- Container curiosity: Aggregated from child traits
- Overall curiosity: Weighted across namespaces
- Agenda generation: Priority-sorted list of high-curiosity containers
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ReDNACoreDemo.core.rr_per_trait import PerTraitRRCalculator
from ReDNACoreDemo.core.rr_aggregation import ContainerRRAggregator


@dataclass
class CuriosityItem:
    """Represents a single curiosity hotspot."""
    path: str
    curiosity: float  # 0-100
    rr: float  # 0-100
    ucn: float  # 0-1000
    container_type: str  # "trait", "container", "namespace"
    priority_score: float  # Combined scoring for agenda
    reason: str  # Why this is curious
    children_count: int = 0  # How many child traits/containers
    missing_count: int = 0  # How many children are missing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "curiosity": round(self.curiosity, 2),
            "rr": round(self.rr, 2),
            "ucn": round(self.ucn, 2),
            "container_type": self.container_type,
            "priority_score": round(self.priority_score, 2),
            "reason": self.reason,
            "children_count": self.children_count,
            "missing_count": self.missing_count
        }


class CuriosityEngine:
    """Generates curiosity-driven agendas for data collection."""

    def __init__(
        self,
        data_dir: Path,
        distribution_dir: Path | None = None,
        registry_path: Path | None = None
    ):
        self.data_dir = Path(data_dir)
        self.distribution_dir = Path(distribution_dir) if distribution_dir else (self.data_dir / "population_distributions")
        self.registry_path = Path(registry_path) if registry_path else (self.data_dir.parent / "core" / "ontology" / "dna_registry.json")

        # Initialize RR calculators
        self.trait_calculator = PerTraitRRCalculator(
            distribution_dir=self.distribution_dir,
            k_min=50
        )

        self.container_aggregator = ContainerRRAggregator(
            distribution_dir=self.distribution_dir
        )

        # Load ontology registry
        self.registry: Dict[str, Any] = {}
        self.container_map: Dict[str, Dict] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load DNA container registry."""
        if not self.registry_path.exists():
            print(f"Warning: Registry not found at {self.registry_path}")
            return

        try:
            with open(self.registry_path) as f:
                self.registry = json.load(f)

            # Build path -> container map
            for container in self.registry.get("containers", []):
                path = container.get("path")
                if path:
                    self.container_map[path] = container
        except Exception as e:
            print(f"Warning: Failed to load registry: {e}")

    def generate_curiosity_agenda(
        self,
        user_id: str,
        top_n: int = 20,
        min_curiosity: float = 50.0,
        include_missing: bool = True
    ) -> List[CuriosityItem]:
        """
        Generate priority-ordered list of high-curiosity items for a user.

        Args:
            user_id: User to generate agenda for
            top_n: Maximum items to return
            min_curiosity: Minimum curiosity threshold (0-100)
            include_missing: Include containers with no data yet

        Returns:
            Sorted list of CuriosityItem objects (highest priority first)
        """
        from ReDNACoreDemo.core.storage import read_user_state

        resolved, _, _ = read_user_state(user_id)
        curiosity_items: List[CuriosityItem] = []

        # 1. Calculate trait-level curiosity
        for trait_path, trait_data in resolved.items():
            ucn = trait_data.get("ucn", 0)
            rr = trait_data.get("rr")

            # Calculate RR if missing
            if rr is None:
                rr_metadata = self.trait_calculator.calculate_rr_metadata(ucn, trait_path)
                rr = rr_metadata.get("rr")

            if rr is None:
                continue  # No distribution available

            curiosity = 100 - rr

            if curiosity >= min_curiosity:
                priority = self._calculate_priority(
                    curiosity=curiosity,
                    ucn=ucn,
                    path=trait_path,
                    container_type="trait"
                )

                reason = self._generate_curiosity_reason(
                    curiosity=curiosity,
                    rr=rr,
                    container_type="trait"
                )

                curiosity_items.append(CuriosityItem(
                    path=trait_path,
                    curiosity=curiosity,
                    rr=rr,
                    ucn=ucn,
                    container_type="trait",
                    priority_score=priority,
                    reason=reason
                ))

        # 2. Calculate container-level curiosity
        container_paths = self._get_container_paths(resolved)

        for container_path in container_paths:
            container_rr = self.container_aggregator.calculate_container_rr(
                user_id=user_id,
                container=container_path
            )

            if not container_rr:
                continue

            rr = container_rr["rr"]
            # Calculate average UCN from traits
            traits = container_rr.get("traits", [])
            ucn = sum(t.get("ucn", 0) for t in traits) / len(traits) if traits else 0
            curiosity = 100 - rr

            if curiosity >= min_curiosity:
                trait_count = container_rr["trait_count"]
                priority = self._calculate_priority(
                    curiosity=curiosity,
                    ucn=ucn,
                    path=container_path,
                    container_type="container",
                    children_count=trait_count
                )

                reason = self._generate_curiosity_reason(
                    curiosity=curiosity,
                    rr=rr,
                    container_type="container",
                    children_count=trait_count
                )

                curiosity_items.append(CuriosityItem(
                    path=container_path,
                    curiosity=curiosity,
                    rr=rr,
                    ucn=ucn,
                    container_type="container",
                    priority_score=priority,
                    reason=reason,
                    children_count=trait_count
                ))

        # 3. Identify missing containers (if enabled)
        if include_missing:
            missing_items = self._find_missing_containers(resolved, min_curiosity)
            curiosity_items.extend(missing_items)

        # 4. Sort by priority and return top N
        curiosity_items.sort(key=lambda x: x.priority_score, reverse=True)
        return curiosity_items[:top_n]

    def _get_container_paths(self, resolved: Dict[str, Any]) -> Set[str]:
        """Extract unique container prefixes from trait paths."""
        containers = set()

        for trait_path in resolved.keys():
            parts = trait_path.split(".")

            # Generate all container levels
            # e.g., "PaDNA.HairDNA.ColorDNA" -> ["PaDNA", "PaDNA.HairDNA"]
            for i in range(1, len(parts)):
                container = ".".join(parts[:i])
                containers.add(container)

        return containers

    def _find_missing_containers(
        self,
        resolved: Dict[str, Any],
        min_curiosity: float
    ) -> List[CuriosityItem]:
        """
        Find containers defined in registry but missing from user data.

        Missing containers get high curiosity scores.
        """
        missing_items = []

        # Get containers from registry
        for container_path, container_def in self.container_map.items():
            # Check if user has any traits under this container
            has_data = any(
                trait_path.startswith(container_path + ".")
                for trait_path in resolved.keys()
            )

            if not has_data:
                # This container is completely missing
                # Assign curiosity based on container importance
                curiosity = self._estimate_missing_curiosity(container_def)

                if curiosity >= min_curiosity:
                    priority = self._calculate_priority(
                        curiosity=curiosity,
                        ucn=0,  # No data yet
                        path=container_path,
                        container_type="missing",
                        is_missing=True
                    )

                    reason = self._generate_curiosity_reason(
                        curiosity=curiosity,
                        rr=0,
                        container_type="missing"
                    )

                    missing_items.append(CuriosityItem(
                        path=container_path,
                        curiosity=curiosity,
                        rr=0,
                        ucn=0,
                        container_type="missing",
                        priority_score=priority,
                        reason=reason,
                        missing_count=1
                    ))

        return missing_items

    def _estimate_missing_curiosity(self, container_def: Dict) -> float:
        """
        Estimate curiosity for a missing container based on its importance.

        Factors:
        - Namespace sensitivity
        - Status (stable > candidate > prototype)
        - UCN weight hint
        """
        # Base curiosity for missing data
        base_curiosity = 80.0

        # Adjust for status
        status = container_def.get("status", "prototype")
        status_weights = {
            "stable": 1.0,
            "candidate": 0.8,
            "prototype": 0.6,
            "deprecated": 0.2
        }
        status_factor = status_weights.get(status, 0.5)

        # Adjust for UCN weight
        ucn_weight = container_def.get("ucn_weight_hint", 0.01)
        weight_factor = min(1.0, ucn_weight * 100)  # 0.01 -> 1.0

        # Combined curiosity
        curiosity = base_curiosity * status_factor * (0.5 + 0.5 * weight_factor)

        return min(100.0, max(0.0, curiosity))

    def _calculate_priority(
        self,
        curiosity: float,
        ucn: float,
        path: str,
        container_type: str,
        children_count: int = 0,
        is_missing: bool = False
    ) -> float:
        """
        Calculate priority score for agenda ordering.

        Formula: priority = curiosity × depth_weight × type_weight × missing_boost

        Higher scores = higher priority
        """
        # Base priority from curiosity
        priority = curiosity

        # Depth weight (favor granular traits over broad containers)
        depth = len(path.split("."))
        depth_weight = 1.0 + (depth - 1) * 0.1  # Deeper = slightly higher priority

        # Type weight
        type_weights = {
            "trait": 1.2,  # Traits are actionable
            "container": 0.8,  # Containers are informational
            "missing": 1.5  # Missing data is high priority
        }
        type_weight = type_weights.get(container_type, 1.0)

        # Missing boost
        missing_boost = 1.3 if is_missing else 1.0

        # Combined priority
        priority = priority * depth_weight * type_weight * missing_boost

        return priority

    def _generate_curiosity_reason(
        self,
        curiosity: float,
        rr: float,
        container_type: str,
        children_count: int = 0
    ) -> str:
        """Generate human-readable reason for curiosity."""
        if container_type == "missing":
            return "No data collected yet - high priority for discovery"

        if curiosity >= 90:
            level = "Extremely low refinement"
        elif curiosity >= 75:
            level = "Very low refinement"
        elif curiosity >= 60:
            level = "Low refinement"
        else:
            level = "Below average refinement"

        if container_type == "container":
            return f"{level} across {children_count} traits - opportunity for deeper exploration"
        else:
            return f"{level} (RR: {rr:.1f}) - opportunity for more data"

    def export_curiosity_map(
        self,
        user_id: str,
        output_path: Path | None = None
    ) -> Dict[str, Any]:
        """
        Export complete curiosity map for UI visualization.

        Returns:
            Dict with agenda, stats, and visualization data
        """
        agenda = self.generate_curiosity_agenda(
            user_id=user_id,
            top_n=50,
            min_curiosity=0.0,  # Include all for complete map
            include_missing=True
        )

        # Group by namespace
        by_namespace = defaultdict(list)
        for item in agenda:
            namespace = item.path.split(".")[0]
            by_namespace[namespace].append(item.to_dict())

        # Calculate stats
        total_items = len(agenda)
        high_curiosity = sum(1 for item in agenda if item.curiosity >= 75)
        missing_containers = sum(1 for item in agenda if item.container_type == "missing")

        curiosity_map = {
            "user_id": user_id,
            "total_items": total_items,
            "high_curiosity_count": high_curiosity,
            "missing_containers_count": missing_containers,
            "top_priorities": [item.to_dict() for item in agenda[:20]],
            "by_namespace": dict(by_namespace),
            "stats": {
                "mean_curiosity": sum(item.curiosity for item in agenda) / total_items if total_items > 0 else 0,
                "mean_rr": sum(item.rr for item in agenda) / total_items if total_items > 0 else 0
            }
        }

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(curiosity_map, f, indent=2)

        return curiosity_map


def main():
    """CLI entry point for curiosity engine."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate curiosity agenda")
    parser.add_argument(
        "--user-id",
        required=True,
        help="User ID to generate agenda for"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Data directory path"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top items to show"
    )
    parser.add_argument(
        "--min-curiosity",
        type=float,
        default=50.0,
        help="Minimum curiosity threshold"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file (optional)"
    )

    args = parser.parse_args()

    engine = CuriosityEngine(data_dir=args.data_dir)

    print(f"Generating curiosity agenda for {args.user_id}...")
    agenda = engine.generate_curiosity_agenda(
        user_id=args.user_id,
        top_n=args.top_n,
        min_curiosity=args.min_curiosity
    )

    print("\n" + "=" * 80)
    print(f"CURIOSITY AGENDA - {args.user_id}")
    print("=" * 80)

    for i, item in enumerate(agenda, 1):
        print(f"\n{i}. {item.path}")
        print(f"   Curiosity: {item.curiosity:.1f} | RR: {item.rr:.1f} | UCN: {item.ucn:.1f}")
        print(f"   Type: {item.container_type} | Priority: {item.priority_score:.1f}")
        print(f"   Reason: {item.reason}")

    print("\n" + "=" * 80)

    if args.output:
        curiosity_map = engine.export_curiosity_map(args.user_id, args.output)
        print(f"\n✅ Curiosity map exported to {args.output}")


if __name__ == "__main__":
    main()
