# ucnrr/presets.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PopulationConfig:
    k: float  # steepness of the logistic curve
    x0: float # midpoint (0..1)

# Tuned-by-feel presets for mapping UCN (0..1000) -> RR% (0..100)
PRESETS = {
    "Easy":   PopulationConfig(k=12.0, x0=0.35),
    "Normal": PopulationConfig(k=14.0, x0=0.50),
    "Hard":   PopulationConfig(k=16.0, x0=0.60),
}