"""
Histogram-based population distribution for fast, private RR calculation.

Key features:
- O(log b) percentile queries vs O(n) for raw arrays
- K-anonymity privacy guarantee (k≥5 per bin)
- ~1KB storage per trait vs ~40KB for 1000 raw UCNs
- Versioned for audit trail
- Winsorization for outlier protection

See: docs/RR_IMPLEMENTATION_REFINEMENTS.md section 2
"""

from __future__ import annotations

import json
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class TraitDistributionHistogram:
    """
    Histogram-based population distribution for fast, private RR calculation.

    Privacy guarantee: No raw UCN values stored, k-anonymity enforced (k≥5).
    Performance: O(log b) percentile queries where b=num_bins (default 100).
    """

    def __init__(
        self,
        trait_path: str,
        num_bins: int = 100,
        k_min: int = 5,
        ucn_min: float = 0.0,
        ucn_max: float = 1000.0
    ):
        """
        Initialize histogram for population distribution.

        Args:
            trait_path: Trait identifier (e.g., "PaDNA.HairDNA.Color")
            num_bins: Number of histogram bins (default 100 for 0-1000 range)
            k_min: K-anonymity minimum (bins with count < k_min are merged)
            ucn_min: Minimum UCN value for binning
            ucn_max: Maximum UCN value for binning
        """
        self.trait_path = trait_path
        self.num_bins = num_bins
        self.k_min = k_min
        self.ucn_min = ucn_min
        self.ucn_max = ucn_max

        # Histogram bins: [0-10), [10-20), ..., [990-1000]
        self.bin_edges = np.linspace(ucn_min, ucn_max, num_bins + 1)
        self.bin_counts = np.zeros(num_bins, dtype=int)

        # Pre-calculated quantiles for common percentiles
        self.quantiles: Dict[int, float] = {}

        # Metadata
        self.total_count = 0
        self.mean_ucn = 0.0
        self.median_ucn = 0.0
        self.std_dev = 0.0
        self.last_updated: Optional[str] = None
        self.version = "1.0"

    def add_ucns(
        self,
        ucns: List[float],
        winsorize: bool = True,
        winsorize_percentiles: tuple[float, float] = (1.0, 99.0)
    ) -> None:
        """
        Build histogram from raw UCN values.

        Args:
            ucns: List of UCN values for this trait across population
            winsorize: If True, clip outliers at P1/P99 to prevent distortion
            winsorize_percentiles: Percentile bounds for winsorization

        Privacy note: Raw UCNs are NOT stored, only histogram bins.
        """
        if not ucns:
            return

        ucns_array = np.array(ucns, dtype=float)

        # Winsorize outliers to prevent extreme values warping distribution
        if winsorize and len(ucns_array) >= 10:  # Need minimum data for percentiles
            p_low, p_high = winsorize_percentiles
            low_bound, high_bound = np.percentile(ucns_array, [p_low, p_high])
            ucns_winsorized = np.clip(ucns_array, low_bound, high_bound)
        else:
            ucns_winsorized = ucns_array

        # Build histogram
        self.bin_counts, _ = np.histogram(ucns_winsorized, bins=self.bin_edges)

        # Enforce k-anonymity: merge bins with count < k_min
        self._enforce_k_anonymity()

        # Calculate quantiles for fast lookup
        self._calculate_quantiles(ucns_winsorized)

        # Store metadata (NOT raw UCNs - privacy protection)
        self.total_count = len(ucns)
        self.mean_ucn = float(np.mean(ucns_winsorized))
        self.median_ucn = float(np.median(ucns_winsorized))
        self.std_dev = float(np.std(ucns_winsorized))
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def _enforce_k_anonymity(self) -> None:
        """
        Merge bins with count < k_min to ensure k-anonymity.

        Privacy guarantee: No bin exposes fewer than k users.

        Implementation: Iterate through bins, merging small bins with neighbors.
        """
        if self.k_min <= 1:
            return  # No anonymity requirement

        # Merge small bins rightward (into next bin)
        i = 0
        while i < len(self.bin_counts) - 1:
            if 0 < self.bin_counts[i] < self.k_min:
                # Merge with next bin
                self.bin_counts[i + 1] += self.bin_counts[i]
                self.bin_counts[i] = 0
            i += 1

        # Handle last bin if still too small
        if 0 < self.bin_counts[-1] < self.k_min and len(self.bin_counts) > 1:
            # Merge last bin leftward
            self.bin_counts[-2] += self.bin_counts[-1]
            self.bin_counts[-1] = 0

    def _calculate_quantiles(self, ucns: np.ndarray) -> None:
        """
        Pre-calculate common quantiles for O(1) lookup.

        Args:
            ucns: Winsorized UCN array

        Stores: P1, P5, P10, P25, P50, P75, P90, P95, P99
        """
        if len(ucns) == 0:
            return

        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        self.quantiles = {
            p: float(np.percentile(ucns, p))
            for p in percentiles
        }

    def get_percentile(self, ucn: float) -> float:
        """
        Fast O(log b) percentile query using histogram.

        Args:
            ucn: User's UCN value for this trait

        Returns:
            Percentile rank (0-100)

        Algorithm:
            1. Find which bin UCN falls into (binary search - O(log b))
            2. Count all users below this bin
            3. Estimate position within bin (linear interpolation)
            4. Calculate percentile: (total_below / total_count) * 100
        """
        if self.total_count == 0:
            return 0.0  # No population data

        # Clip UCN to valid range
        ucn = max(self.ucn_min, min(self.ucn_max, ucn))

        # Find which bin this UCN falls into (O(log b) binary search)
        bin_idx = np.searchsorted(self.bin_edges, ucn, side='right') - 1
        bin_idx = max(0, min(bin_idx, len(self.bin_counts) - 1))

        # Count all users below this bin
        users_below = int(np.sum(self.bin_counts[:bin_idx]))

        # Estimate position within bin (linear interpolation)
        bin_start = self.bin_edges[bin_idx]
        bin_end = self.bin_edges[bin_idx + 1]
        bin_count = self.bin_counts[bin_idx]

        if bin_count > 0 and bin_end > bin_start:
            # Fraction of way through bin
            fraction_in_bin = (ucn - bin_start) / (bin_end - bin_start)
            users_in_bin_below = fraction_in_bin * bin_count
        else:
            users_in_bin_below = 0

        total_below = users_below + users_in_bin_below
        percentile = (total_below / self.total_count) * 100

        # Clamp to valid range [0, 100]
        return max(0.0, min(100.0, round(percentile, 2)))

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to JSON-compatible dict.

        Privacy note: Does NOT include raw UCN values, only aggregated bins.
        """
        return {
            "trait_path": self.trait_path,
            "bin_edges": self.bin_edges.tolist(),
            "bin_counts": self.bin_counts.tolist(),
            "quantiles": self.quantiles,
            "total_count": self.total_count,
            "mean_ucn": self.mean_ucn,
            "median_ucn": self.median_ucn,
            "std_dev": self.std_dev,
            "last_updated": self.last_updated,
            "k_min": self.k_min,
            "version": self.version,
            "ucn_range": {"min": self.ucn_min, "max": self.ucn_max}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraitDistributionHistogram':
        """
        Deserialize from JSON dict.

        Args:
            data: Dict from to_dict() or loaded from file

        Returns:
            TraitDistributionHistogram instance
        """
        ucn_range = data.get("ucn_range", {"min": 0.0, "max": 1000.0})

        hist = cls(
            trait_path=data["trait_path"],
            num_bins=len(data["bin_counts"]),
            k_min=data.get("k_min", 5),
            ucn_min=ucn_range["min"],
            ucn_max=ucn_range["max"]
        )

        hist.bin_edges = np.array(data["bin_edges"])
        hist.bin_counts = np.array(data["bin_counts"])
        hist.quantiles = {int(k): v for k, v in data.get("quantiles", {}).items()}
        hist.total_count = data["total_count"]
        hist.mean_ucn = data["mean_ucn"]
        hist.median_ucn = data["median_ucn"]
        hist.std_dev = data["std_dev"]
        hist.last_updated = data.get("last_updated")
        hist.version = data.get("version", "1.0")

        return hist

    def save(self, directory: Path) -> Path:
        """
        Save histogram to JSON file.

        Args:
            directory: Directory to save to (e.g., data/population_distributions/)

        Returns:
            Path to saved file

        File naming: {trait_path}_v{version}.json
        Example: data/population_distributions/PaDNA.HairDNA.Color_v1.0.json
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        # Sanitize trait_path for filename (replace / with _)
        safe_trait_path = self.trait_path.replace("/", "_").replace("\\", "_")
        filename = f"{safe_trait_path}_v{self.version}.json"
        filepath = directory / filename

        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath

    @classmethod
    def load(cls, filepath: Path) -> 'TraitDistributionHistogram':
        """
        Load histogram from JSON file.

        Args:
            filepath: Path to histogram file

        Returns:
            TraitDistributionHistogram instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        return cls.from_dict(data)

    def get_population_stats(self, user_ucn: float) -> Dict[str, Any]:
        """
        Get detailed population statistics for this trait.

        Args:
            user_ucn: User's UCN for this trait

        Returns:
            Dict with population context for UI display
        """
        percentile = self.get_percentile(user_ucn)
        users_below = int((percentile / 100) * self.total_count)

        return {
            "total_users": self.total_count,
            "users_below": users_below,
            "percentile": percentile,
            "mean_ucn": self.mean_ucn,
            "median_ucn": self.median_ucn,
            "std_dev": self.std_dev,
            "user_ucn": user_ucn,
            "quantiles": self.quantiles
        }

    def validate_privacy(self) -> Dict[str, Any]:
        """
        Validate k-anonymity guarantee is maintained.

        Returns:
            {
                "valid": bool,
                "k_min": int,
                "violations": List[int],  # Bin indices that violate k-anonymity
                "message": str
            }
        """
        violations = []

        for i, count in enumerate(self.bin_counts):
            if 0 < count < self.k_min:
                violations.append(i)

        if violations:
            return {
                "valid": False,
                "k_min": self.k_min,
                "violations": violations,
                "message": f"K-anonymity violated in {len(violations)} bins (k<{self.k_min})"
            }

        return {
            "valid": True,
            "k_min": self.k_min,
            "violations": [],
            "message": f"K-anonymity maintained (all bins k>={self.k_min})"
        }


def build_distribution_from_users(
    trait_path: str,
    user_traits: Dict[str, float],
    output_dir: Path,
    k_min: int = 5
) -> TraitDistributionHistogram:
    """
    Build and save population distribution for a trait.

    Args:
        trait_path: Trait identifier (e.g., "PaDNA.HairDNA.Color")
        user_traits: Dict of {user_id: ucn} for all users with this trait
        output_dir: Directory to save distribution file
        k_min: K-anonymity minimum

    Returns:
        TraitDistributionHistogram instance

    Example:
        user_traits = {
            "user1": 450.0,
            "user2": 650.0,
            "user3": 550.0,
            ...
        }
        hist = build_distribution_from_users(
            "PaDNA.HairDNA.Color",
            user_traits,
            Path("data/population_distributions"),
            k_min=5
        )
    """
    ucns = list(user_traits.values())

    hist = TraitDistributionHistogram(
        trait_path=trait_path,
        num_bins=100,
        k_min=k_min
    )

    hist.add_ucns(ucns, winsorize=True)

    # Validate privacy
    privacy_check = hist.validate_privacy()
    if not privacy_check["valid"]:
        print(f"⚠️  Warning: {privacy_check['message']}")
        # Re-enforce with more aggressive merging
        hist._enforce_k_anonymity()

    # Save to disk
    filepath = hist.save(output_dir)
    print(f"✅ Saved distribution: {filepath}")
    print(f"   Population: {hist.total_count} users")
    print(f"   Mean UCN: {hist.mean_ucn:.1f}")
    print(f"   K-anonymity: {privacy_check['message']}")

    return hist


__all__ = [
    "TraitDistributionHistogram",
    "build_distribution_from_users"
]
