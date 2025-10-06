"""
Adaptive Decay Engine

Manages confidence decay rates for traits over time.
Principle: "Confidence decays, not the trait itself"

Decay rates are adaptive - they learn optimal half-lives per trait based on:
- Observed volatility (how often the trait changes)
- Stability patterns (traits that remain consistent)
- Metadata (user's age, life stage, etc.)
- Exception patterns (traits that buck general trends)
"""

import re
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from pathlib import Path
import yaml


class DecayEngine:
    """Manages adaptive decay rates for trait confidence."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize decay engine with default decay rates."""
        if config_path is None:
            config_path = Path(__file__).parent / "config" / "decay_defaults.yaml"

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.defaults = self.config  # Full config including DNA-specific defaults
        self.metadata_modifiers = self.config.get('metadata_modifiers', {})
        self.adaptive_config = self.config.get('adaptive_learning', {})

        # Learned decay rates (adjusted over time)
        # Format: {trait_path: adjusted_half_life_days}
        self.learned_decay_rates: Dict[str, float] = {}

        # Trait observation history (for learning)
        # Format: {trait_path: [{'timestamp': datetime, 'value': Any, 'changed': bool}, ...]}
        self.trait_history: Dict[str, List[Dict[str, Any]]] = {}

    def get_default_decay_half_life(self, trait_path: str) -> float:
        """
        Get default decay half-life for a trait path.

        Args:
            trait_path: Full trait path (e.g., "PaDNA.HairDNA.Color")

        Returns:
            Half-life in days (float('inf') for permanent traits)
        """
        # Parse trait path: DNA.SubDNA.Trait
        parts = trait_path.split('.')

        if len(parts) < 2:
            # Invalid path, return conservative default
            return 365.0

        dna_type = parts[0]  # e.g., "PaDNA"
        sub_dna = parts[1] if len(parts) > 1 else None  # e.g., "HairDNA"
        trait_name = parts[2] if len(parts) > 2 else None  # e.g., "Color"

        # Navigate config structure
        dna_config = self.defaults.get(dna_type, {})
        if sub_dna and sub_dna in dna_config:
            sub_config = dna_config[sub_dna]
            if trait_name and trait_name in sub_config:
                half_life = sub_config[trait_name]
                # Handle "permanent" special value
                if half_life == "permanent":
                    return float('inf')
                return float(half_life)

        # Fallback: try direct lookup (e.g., for single-level traits)
        if trait_name and trait_name in dna_config:
            half_life = dna_config[trait_name]
            if half_life == "permanent":
                return float('inf')
            return float(half_life)

        # Conservative default if not found
        return 365.0

    def get_metadata_modifier(
        self,
        trait_path: str,
        user_metadata: Dict[str, Any]
    ) -> float:
        """
        Get metadata-based decay rate modifier.

        Args:
            trait_path: Full trait path
            user_metadata: User metadata (age, marital_status, etc.)

        Returns:
            Modifier multiplier (0.25-4.0, default 1.0)
        """
        modifier = 1.0

        # Check each metadata modifier condition
        for condition, modifications in self.metadata_modifiers.items():
            # Parse condition (e.g., "age_over_60", "marital_status_married")
            if self._matches_metadata_condition(condition, user_metadata):
                # Apply modifications for matching traits
                for trait_pattern, adjustment in modifications.items():
                    if self._matches_trait_pattern(trait_pattern, trait_path):
                        modifier *= adjustment

        return modifier

    def _matches_metadata_condition(
        self,
        condition: str,
        user_metadata: Dict[str, Any]
    ) -> bool:
        """Check if user metadata matches a condition."""
        # Parse condition format: "key_operator_value"
        # Examples: "age_over_60", "marital_status_married"

        if condition == "age_over_60":
            age = user_metadata.get('age', 0)
            return age > 60

        if condition == "age_18_25":
            age = user_metadata.get('age', 0)
            return 18 <= age <= 25

        if condition == "marital_status_married":
            marital_status = user_metadata.get('marital_status', '')
            return marital_status.lower() in ['married', 'partnership']

        if condition == "chronic_condition":
            chronic_conditions = user_metadata.get('chronic_conditions', [])
            return len(chronic_conditions) > 0

        if condition == "college_student":
            student_status = user_metadata.get('student_status', '')
            return student_status.lower() in ['undergraduate', 'graduate', 'college']

        # Unknown condition
        return False

    def _matches_trait_pattern(self, pattern: str, trait_path: str) -> bool:
        """
        Check if trait path matches a pattern.

        Patterns support wildcards: "PsyDNA.Opinions.*"
        """
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
        return bool(re.match(f'^{regex_pattern}$', trait_path))

    def get_adaptive_decay_half_life(
        self,
        trait_path: str,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Get adaptive decay half-life for a trait.

        Combines default, learned adjustments, and metadata modifiers.

        Args:
            trait_path: Full trait path
            user_metadata: User metadata (optional)

        Returns:
            Adjusted half-life in days
        """
        # Start with default
        default_half_life = self.get_default_decay_half_life(trait_path)

        # Check if permanent
        if default_half_life == float('inf'):
            return float('inf')

        # Apply learned adjustment (if any)
        if trait_path in self.learned_decay_rates:
            half_life = self.learned_decay_rates[trait_path]
        else:
            half_life = default_half_life

        # Apply metadata modifiers (if enabled and metadata provided)
        if user_metadata:
            metadata_modifier = self.get_metadata_modifier(trait_path, user_metadata)
            half_life *= metadata_modifier

        # Clamp to adjustment range
        adjustment_range = self.adaptive_config.get('adjustment_range', [0.25, 4.0])
        min_half_life = default_half_life * adjustment_range[0]
        max_half_life = default_half_life * adjustment_range[1]
        half_life = max(min_half_life, min(max_half_life, half_life))

        return half_life

    def record_observation(
        self,
        trait_path: str,
        value: Any,
        timestamp: datetime
    ) -> None:
        """
        Record a trait observation for adaptive learning.

        Args:
            trait_path: Full trait path
            value: Observed trait value
            timestamp: Observation timestamp
        """
        if trait_path not in self.trait_history:
            self.trait_history[trait_path] = []

        history = self.trait_history[trait_path]

        # Determine if value changed from previous observation
        changed = False
        if history:
            last_value = history[-1]['value']
            changed = (value != last_value)

        history.append({
            'timestamp': timestamp,
            'value': value,
            'changed': changed
        })

        # Trigger learning if enough observations accumulated
        if self.adaptive_config.get('enabled', True):
            min_observations = self.adaptive_config.get('min_observations', 5)
            if len(history) >= min_observations:
                self._learn_decay_rate(trait_path)

    def _learn_decay_rate(self, trait_path: str) -> None:
        """
        Learn optimal decay rate for a trait based on observation history.

        Adaptive learning rules:
        1. If trait stable (5+ observations, no changes over 2+ years) → slower decay (2x)
        2. If trait volatile (3+ changes in 6 months) → faster decay (0.5x)
        3. If trait shows exception pattern (usually volatile but stable recently) → slower decay (1.5x)
        """
        history = self.trait_history.get(trait_path, [])
        if not history:
            return

        # Get current default and learned rates
        default_half_life = self.get_default_decay_half_life(trait_path)
        if default_half_life == float('inf'):
            # Don't learn for permanent traits
            return

        current_half_life = self.learned_decay_rates.get(trait_path, default_half_life)

        # Analyze observation window
        observation_window = self.adaptive_config.get('observation_window', 730)  # days
        now = datetime.now()
        cutoff_date = now - timedelta(days=observation_window)

        recent_history = [
            obs for obs in history
            if obs['timestamp'] >= cutoff_date
        ]

        if len(recent_history) < 2:
            # Not enough recent data
            return

        # Count changes
        num_changes = sum(1 for obs in recent_history if obs['changed'])
        time_span_days = (recent_history[-1]['timestamp'] - recent_history[0]['timestamp']).days

        # Rule 1: Stable trait (no changes over long period)
        if num_changes == 0 and time_span_days >= 730:  # 2+ years
            multiplier = self.adaptive_config.get('stable_trait_multiplier', 2.0)
            new_half_life = current_half_life * multiplier

        # Rule 2: Volatile trait (frequent changes)
        elif num_changes >= 3 and time_span_days <= 180:  # 3+ changes in 6 months
            multiplier = self.adaptive_config.get('volatile_trait_multiplier', 0.5)
            new_half_life = current_half_life * multiplier

        # Rule 3: Exception pattern (was volatile, now stable)
        elif num_changes == 0 and len(history) >= 10:
            # Check if trait was volatile in distant past
            older_history = [obs for obs in history if obs['timestamp'] < cutoff_date]
            older_changes = sum(1 for obs in older_history if obs['changed'])

            if older_changes >= 3:
                # Was volatile, now stable
                exception_period = self.adaptive_config.get('exception_monitoring_period', 90)
                if time_span_days >= exception_period:
                    multiplier = self.adaptive_config.get('exception_multiplier', 1.5)
                    new_half_life = current_half_life * multiplier
                else:
                    # Still monitoring
                    return
            else:
                # Already stable, no change
                return
        else:
            # No clear pattern, no adjustment
            return

        # Apply learning rate (gradual adjustment)
        learning_rate = self.adaptive_config.get('learning_rate', 0.1)
        adjusted_half_life = current_half_life + learning_rate * (new_half_life - current_half_life)

        # Clamp to adjustment range
        adjustment_range = self.adaptive_config.get('adjustment_range', [0.25, 4.0])
        min_half_life = default_half_life * adjustment_range[0]
        max_half_life = default_half_life * adjustment_range[1]
        adjusted_half_life = max(min_half_life, min(max_half_life, adjusted_half_life))

        # Store learned decay rate
        self.learned_decay_rates[trait_path] = adjusted_half_life

    def get_decay_info(
        self,
        trait_path: str,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get detailed decay information for a trait.

        Returns:
            Dictionary with default_half_life, learned_half_life, metadata_modifier, final_half_life
        """
        default_half_life = self.get_default_decay_half_life(trait_path)
        learned_half_life = self.learned_decay_rates.get(trait_path, default_half_life)
        metadata_modifier = 1.0

        if user_metadata and default_half_life != float('inf'):
            metadata_modifier = self.get_metadata_modifier(trait_path, user_metadata)

        final_half_life = self.get_adaptive_decay_half_life(trait_path, user_metadata)

        return {
            'trait_path': trait_path,
            'default_half_life_days': default_half_life,
            'learned_half_life_days': learned_half_life,
            'metadata_modifier': metadata_modifier,
            'final_half_life_days': final_half_life,
            'is_permanent': default_half_life == float('inf'),
            'num_observations': len(self.trait_history.get(trait_path, []))
        }
