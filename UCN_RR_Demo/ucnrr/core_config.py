# ucnrr/core_config.py
from __future__ import annotations

def default_decay_map() -> dict[str, float]:
    """
    Default half-lives by DNA path (days). Most specific key wins.
    """
    return {
        # Highly stable
        "PaDNA.AgeDNA": 36500.0,  # ~100 years
        "SpDNA": 3650.0,
        "PsyDNA.EDNA": 3650.0,

        # Moderately stable
        "PsyDNA.Personality": 1825.0,
        "IntDNA": 730.0,
        "PaDNA.LooksDNA": 1095.0,

        # Dynamic
        "EmDNA": 30.0,
        "PsyDNA.TechDNA": 180.0,
        "IntDNA.RoDNA": 180.0,

        # Very volatile
        "EmDNA.MoodDNA": 3.0,
    }

def default_importance_map() -> dict[str, float]:
    """
    Relative importance weights in 0..1 used for gap ranking.
    Most specific key wins.
    """
    return {
        # Top-level guidance
        "IntDNA": 0.9,
        "PaDNA": 0.8,
        "PsyDNA": 0.8,
        "EmDNA": 0.7,
        "SpDNA": 0.6,

        # Examples (override as you like)
        "PaDNA.AgeDNA": 1.0,
        "PaDNA.LooksDNA": 0.7,
        "IntDNA.RoDNA": 0.9,
        "EmDNA.MoodDNA": 0.6,
        "PsyDNA.Personality": 0.9,
    }