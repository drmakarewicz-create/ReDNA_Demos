"""
RR (Refinement Rank) Calculator

Calculates user's Refinement Rank (0-100 percentile) by comparing their average UCN
across all traits to the population distribution of all living users.

RR is the PRIMARY user-facing metric showing profile completeness/refinement.
"""

import statistics
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import json


class RRCalculator:
    """Calculates Refinement Rank (RR) percentile for users."""

    def __init__(self, population_cache_path: Optional[Path] = None):
        """
        Initialize RR calculator.

        Args:
            population_cache_path: Path to cached population distribution
        """
        if population_cache_path is None:
            population_cache_path = Path(__file__).parent.parent / "data" / "population_ucn_distribution.json"

        self.population_cache_path = Path(population_cache_path)
        self.population_cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Load cached population distribution (if exists)
        self.population_distribution: List[float] = []
        self.cache_timestamp: Optional[datetime] = None
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached population distribution from disk."""
        if not self.population_cache_path.exists():
            return

        try:
            with open(self.population_cache_path, 'r') as f:
                data = json.load(f)

            self.population_distribution = data.get('distribution', [])
            cache_time_str = data.get('timestamp')
            if cache_time_str:
                self.cache_timestamp = datetime.fromisoformat(cache_time_str)

        except Exception as e:
            print(f"[RRCalculator] Failed to load cache: {e}")

    def _save_cache(self) -> None:
        """Save population distribution to disk."""
        try:
            data = {
                'distribution': self.population_distribution,
                'timestamp': datetime.now().isoformat(),
                'count': len(self.population_distribution)
            }

            with open(self.population_cache_path, 'w') as f:
                json.dump(data, f, indent=2)

            print(f"[RRCalculator] Saved population cache with {len(self.population_distribution)} users")

        except Exception as e:
            print(f"[RRCalculator] Failed to save cache: {e}")

    def calculate_average_ucn(self, user_traits: Dict[str, int]) -> float:
        """
        Calculate user's average UCN across all traits.

        Args:
            user_traits: Dictionary of {trait_path: ucn}

        Returns:
            Average UCN
        """
        if not user_traits:
            return 0.0

        ucn_values = list(user_traits.values())
        return statistics.mean(ucn_values)

    def calculate_rr(
        self,
        user_id: str,
        user_traits: Dict[str, int],
        min_traits: int = 10
    ) -> Optional[float]:
        """
        Calculate Refinement Rank (RR) percentile for user.

        Args:
            user_id: User ID
            user_traits: Dictionary of {trait_path: ucn}
            min_traits: Minimum number of traits required (default 10)

        Returns:
            RR percentile (0-100), or None if insufficient data
        """
        # Validate user has enough traits
        if len(user_traits) < min_traits:
            return None

        # Calculate user's average UCN
        user_avg_ucn = self.calculate_average_ucn(user_traits)

        # Check if population cache exists and is recent
        if not self.population_distribution or self._is_cache_stale():
            print(f"[RRCalculator] Population cache missing or stale. Using placeholder distribution.")
            # In production, this would trigger population distribution rebuild
            # For now, use a placeholder distribution
            self._build_placeholder_distribution()

        # Calculate percentile rank
        if not self.population_distribution:
            # No distribution available
            return None

        users_below = sum(1 for ucn in self.population_distribution if ucn < user_avg_ucn)
        total_users = len(self.population_distribution)

        if total_users == 0:
            return None

        rr_percentile = (users_below / total_users) * 100

        return round(rr_percentile, 2)

    def _is_cache_stale(self, max_age_hours: int = 24) -> bool:
        """Check if population cache is stale (older than max_age_hours)."""
        if self.cache_timestamp is None:
            return True

        age = datetime.now() - self.cache_timestamp
        return age > timedelta(hours=max_age_hours)

    def _build_placeholder_distribution(self) -> None:
        """
        Build placeholder population distribution for development/testing.

        In production, this would query the database for all users' average UCNs.
        """
        # Simulate population distribution (normal distribution centered around 500 UCN)
        # This is a placeholder - real implementation would query database
        import random

        random.seed(42)  # Consistent placeholder
        self.population_distribution = [
            max(0, min(1000, random.normalvariate(500, 150)))  # Mean 500, StdDev 150
            for _ in range(10000)  # Simulate 10,000 users
        ]

        self.cache_timestamp = datetime.now()
        self._save_cache()

    def rebuild_population_distribution(
        self,
        all_user_ucns: Dict[str, float],
        exclude_dormant_days: int = 90,
        exclude_deceased: bool = True,
        user_metadata: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """
        Rebuild population distribution from all users' UCNs.

        This should be called daily at 3 AM UTC.

        Args:
            all_user_ucns: Dictionary of {user_id: average_ucn}
            exclude_dormant_days: Exclude users inactive for N+ days
            exclude_deceased: Exclude deceased users
            user_metadata: Optional metadata for filtering (activity, deceased status)
        """
        now = datetime.now()
        distribution = []

        for user_id, avg_ucn in all_user_ucns.items():
            # Filter dormant users
            if user_metadata and exclude_dormant_days > 0:
                last_activity = user_metadata.get(user_id, {}).get('last_activity')
                if last_activity:
                    last_activity_date = datetime.fromisoformat(last_activity)
                    days_inactive = (now - last_activity_date).days
                    if days_inactive >= exclude_dormant_days:
                        continue

            # Filter deceased users
            if exclude_deceased and user_metadata:
                is_deceased = user_metadata.get(user_id, {}).get('deceased', False)
                if is_deceased:
                    continue

            distribution.append(avg_ucn)

        # Sort distribution for percentile calculations
        distribution.sort()

        self.population_distribution = distribution
        self.cache_timestamp = now
        self._save_cache()

        print(f"[RRCalculator] Rebuilt population distribution with {len(distribution)} users")

    def get_rr_info(
        self,
        user_id: str,
        user_traits: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Get detailed RR information for a user.

        Returns:
            Dictionary with RR, average UCN, trait count, percentile details
        """
        rr = self.calculate_rr(user_id, user_traits)
        avg_ucn = self.calculate_average_ucn(user_traits)

        # Get threshold gates
        gates_passed = []
        if rr is not None:
            if rr >= 98:
                gates_passed.append('sensitive_dna_unlock')
            if rr >= 85:
                gates_passed.append('advanced_personalization')
            if rr >= 70:
                gates_passed.append('reliable_coaching')
            if rr >= 50:
                gates_passed.append('basic_features')

        # Get milestone celebrations
        milestones_achieved = []
        if rr is not None:
            if rr >= 98:
                milestones_achieved.append('milestone_98')
            elif rr >= 90:
                milestones_achieved.append('milestone_90')
            elif rr >= 75:
                milestones_achieved.append('milestone_75')
            elif rr >= 50:
                milestones_achieved.append('milestone_50')
            elif rr >= 25:
                milestones_achieved.append('milestone_25')

        return {
            'user_id': user_id,
            'rr': rr,
            'average_ucn': round(avg_ucn, 2),
            'trait_count': len(user_traits),
            'gates_passed': gates_passed,
            'milestones_achieved': milestones_achieved,
            'population_size': len(self.population_distribution),
            'cache_age_hours': self._get_cache_age_hours()
        }

    def _get_cache_age_hours(self) -> Optional[float]:
        """Get age of population cache in hours."""
        if self.cache_timestamp is None:
            return None

        age = datetime.now() - self.cache_timestamp
        return age.total_seconds() / 3600


def calculate_rr(
    user_id: str,
    user_traits: Dict[str, int],
    min_traits: int = 10
) -> Optional[float]:
    """
    Convenience function to calculate RR without instantiating calculator.

    Args:
        user_id: User ID
        user_traits: Dictionary of {trait_path: ucn}
        min_traits: Minimum number of traits required

    Returns:
        RR percentile (0-100), or None if insufficient data
    """
    calculator = RRCalculator()
    return calculator.calculate_rr(user_id, user_traits, min_traits)
