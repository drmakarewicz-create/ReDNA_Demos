"""
Per-trait RR calculator with robust edge case handling.

Key features:
- True population percentile calculation
- Mid-rank tie handling (Hazen/Cunnane method)
- Small-N protection with fictional prior blending
- Histogram-based for O(log b) performance
- Privacy-preserving (no raw UCN exposure)

Formula:
    Per-Trait RR = (users_with_trait_UCN_below / total_users_with_trait) × 100
    Curiosity = 100 - RR

See: docs/RR_IMPLEMENTATION_REFINEMENTS.md sections 1-2
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .rr_histogram import TraitDistributionHistogram


def _norm_cdf(x: float) -> float:
    """
    Approximate standard normal CDF using error function approximation.

    Accurate to ~0.3% which is sufficient for RR calculations.
    """
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class PerTraitRRCalculator:
    """
    Calculate per-trait RR (Refinement Rating) percentiles.

    Handles edge cases:
    - Ties (multiple users with same UCN)
    - Small populations (n < 50)
    - Missing distributions
    - Outliers
    """

    def __init__(
        self,
        distribution_dir: Path,
        k_min: int = 50,
        prior_mean: float = 500.0,
        prior_std: float = 150.0
    ):
        """
        Initialize per-trait RR calculator.

        Args:
            distribution_dir: Directory containing population distribution files
            k_min: Minimum population size for pure empirical RR (default 50)
            prior_mean: Mean UCN for fictional prior distribution (default 500)
            prior_std: Std dev for fictional prior distribution (default 150)
        """
        self.distribution_dir = Path(distribution_dir)
        self.distribution_dir.mkdir(parents=True, exist_ok=True)

        self.k_min = k_min
        self.prior_mean = prior_mean
        self.prior_std = prior_std

        # Cache loaded distributions
        self._cache: Dict[str, TraitDistributionHistogram] = {}

    def calculate_rr(
        self,
        user_ucn: float,
        trait_path: str,
        use_cache: bool = True
    ) -> Optional[float]:
        """
        Calculate RR for a specific trait.

        Args:
            user_ucn: User's UCN for this trait
            trait_path: Trait identifier (e.g., "PaDNA.HairDNA.Color")
            use_cache: If True, use cached distribution (faster)

        Returns:
            RR percentile (0-100), or None if no distribution available

        Example:
            rr = calculator.calculate_rr(450.0, "PaDNA.HairDNA.Color")
            # Returns: 30.0 (user is more refined than 30% of population)
        """
        # Load distribution
        hist = self._load_distribution(trait_path, use_cache)

        if hist is None:
            # No population data available
            return None

        # Get empirical percentile from histogram
        rr_empirical = hist.get_percentile(user_ucn)

        # Apply small-N protection if needed
        n = hist.total_count

        if n < self.k_min:
            # Blend with fictional prior
            rr_prior = self._calculate_prior_rr(user_ucn)
            lambda_blend = min(1.0, n / self.k_min)

            rr_final = lambda_blend * rr_empirical + (1 - lambda_blend) * rr_prior
        else:
            rr_final = rr_empirical

        return round(rr_final, 2)

    def calculate_rr_with_ties(
        self,
        user_ucn: float,
        population_ucns: List[float]
    ) -> float:
        """
        Calculate RR with explicit tie handling (mid-rank method).

        Use this when you have raw UCN values and need to handle ties precisely.

        Args:
            user_ucn: User's UCN for this trait
            population_ucns: All UCN values for this trait across population

        Returns:
            RR percentile (0-100) with mid-rank tie handling

        Algorithm (Mid-Rank):
            users_below = count(ucn < user_ucn)
            users_equal = count(ucn == user_ucn)
            effective_below = users_below + (users_equal / 2.0)
            rr_empirical = (effective_below / n) * 100

        Example:
            # Population: [100, 200, 300, 400, 400, 400, 500, 600, 700, 800]
            # User UCN: 400
            # 3 below (100, 200, 300), 3 equal (400, 400, 400), 4 above
            # Mid-rank: 3 + 1.5 = 4.5 below → RR = 45
        """
        n = len(population_ucns)

        if n == 0:
            return 0.0

        # Count ties with mid-rank method
        users_below = sum(1 for ucn in population_ucns if ucn < user_ucn)
        users_equal = sum(1 for ucn in population_ucns if ucn == user_ucn)

        # Mid-rank: count half of equal values as "below"
        effective_below = users_below + (users_equal / 2.0)

        rr_empirical = (effective_below / n) * 100

        # Apply small-N protection if needed
        if n < self.k_min:
            rr_prior = self._calculate_prior_rr(user_ucn)
            lambda_blend = min(1.0, n / self.k_min)

            rr_final = lambda_blend * rr_empirical + (1 - lambda_blend) * rr_prior
        else:
            rr_final = rr_empirical

        return round(rr_final, 2)

    def _calculate_prior_rr(self, ucn: float) -> float:
        """
        Calculate RR using fictional prior (normal distribution).

        Used for small populations to stabilize percentile.

        Args:
            ucn: User's UCN value

        Returns:
            RR percentile (0-100) from prior distribution

        Algorithm:
            z_score = (ucn - prior_mean) / prior_std
            percentile = Φ(z_score) * 100  # CDF of standard normal

        Example:
            ucn=675, prior_mean=500, prior_std=150
            z = (675 - 500) / 150 = 1.17
            percentile = Φ(1.17) * 100 ≈ 88%
        """
        z_score = (ucn - self.prior_mean) / self.prior_std
        percentile = _norm_cdf(z_score) * 100

        return max(0.0, min(100.0, percentile))

    def _load_distribution(
        self,
        trait_path: str,
        use_cache: bool = True
    ) -> Optional[TraitDistributionHistogram]:
        """
        Load population distribution for trait.

        Args:
            trait_path: Trait identifier
            use_cache: If True, return cached distribution if available

        Returns:
            TraitDistributionHistogram, or None if not found
        """
        # Check cache first
        if use_cache and trait_path in self._cache:
            return self._cache[trait_path]

        # Look for distribution file
        safe_trait_path = trait_path.replace("/", "_").replace("\\", "_")
        pattern = f"{safe_trait_path}_v*.json"

        files = sorted(self.distribution_dir.glob(pattern))

        if not files:
            # No distribution file found
            return None

        # Load most recent version (highest version number)
        filepath = files[-1]

        try:
            hist = TraitDistributionHistogram.load(filepath)

            # Cache for future lookups
            if use_cache:
                self._cache[trait_path] = hist

            return hist

        except Exception as e:
            print(f"⚠️  Failed to load distribution {filepath}: {e}")
            return None

    def get_population_stats(
        self,
        user_ucn: float,
        trait_path: str
    ) -> Optional[Dict[str, any]]:
        """
        Get detailed population statistics for trait.

        Args:
            user_ucn: User's UCN for this trait
            trait_path: Trait identifier

        Returns:
            Dict with population context, or None if no distribution

        Example return:
            {
                "total_users": 1000,
                "users_below": 850,
                "percentile": 85.0,
                "mean_ucn": 625.0,
                "median_ucn": 600.0,
                "std_dev": 148.7,
                "user_ucn": 950.0,
                "quantiles": {10: 250, 50: 500, 90: 750}
            }
        """
        hist = self._load_distribution(trait_path)

        if hist is None:
            return None

        return hist.get_population_stats(user_ucn)

    def calculate_curiosity(self, rr: Optional[float]) -> float:
        """
        Calculate curiosity from RR.

        Args:
            rr: RR percentile (0-100), or None

        Returns:
            Curiosity score (0-100)

        Formula:
            Curiosity = 100 - RR

        Edge cases:
            - If rr is None (no evidence), return 100.0 (maximum curiosity)
            - Always clamp to valid range [0, 100]
        """
        if rr is None:
            return 100.0  # No evidence = maximum curiosity

        return max(0.0, min(100.0, 100.0 - rr))

    def calculate_rr_metadata(
        self,
        user_ucn: float,
        trait_path: str
    ) -> Dict[str, any]:
        """
        Calculate RR with full metadata for audit trail.

        Args:
            user_ucn: User's UCN for this trait
            trait_path: Trait identifier

        Returns:
            {
                "rr": float,
                "curiosity": float,
                "method": str,
                "distribution_version": str,
                "population_size": int,
                "blending_applied": bool,
                "lambda_blend": Optional[float]
            }
        """
        hist = self._load_distribution(trait_path)

        if hist is None:
            return {
                "rr": None,
                "curiosity": 100.0,
                "method": "no_distribution",
                "distribution_version": None,
                "population_size": 0,
                "blending_applied": False,
                "lambda_blend": None
            }

        rr_empirical = hist.get_percentile(user_ucn)
        n = hist.total_count

        if n < self.k_min:
            # Small-N blending applied
            rr_prior = self._calculate_prior_rr(user_ucn)
            lambda_blend = min(1.0, n / self.k_min)
            rr_final = lambda_blend * rr_empirical + (1 - lambda_blend) * rr_prior

            method = "histogram_with_prior_blending"
            blending_applied = True
        else:
            rr_final = rr_empirical
            lambda_blend = 1.0
            method = "histogram_percentile"
            blending_applied = False

        return {
            "rr": round(rr_final, 2),
            "curiosity": self.calculate_curiosity(rr_final),
            "method": method,
            "distribution_version": hist.version,
            "population_size": n,
            "blending_applied": blending_applied,
            "lambda_blend": lambda_blend if blending_applied else None
        }


def calculate_trait_rr(
    user_ucn: float,
    trait_path: str,
    distribution_dir: Path,
    k_min: int = 50
) -> Optional[float]:
    """
    Convenience function to calculate per-trait RR.

    Args:
        user_ucn: User's UCN for this trait
        trait_path: Trait identifier (e.g., "PaDNA.HairDNA.Color")
        distribution_dir: Directory containing population distributions
        k_min: Minimum population size for pure empirical RR

    Returns:
        RR percentile (0-100), or None if no distribution

    Example:
        rr = calculate_trait_rr(450.0, "PaDNA.HairDNA.Color", Path("data/distributions"))
        # Returns: 30.0
    """
    calculator = PerTraitRRCalculator(
        distribution_dir=distribution_dir,
        k_min=k_min
    )

    return calculator.calculate_rr(user_ucn, trait_path)


__all__ = [
    "PerTraitRRCalculator",
    "calculate_trait_rr"
]
