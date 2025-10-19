"""
Phase 10 adaptive analytics insight aggregator.

Aggregates container usage across personas and computes cross-persona
correlations to guide predictive focus selection.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Tuple

from .metrics_engine import MetricsSnapshot


def _pearson(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient between two vectors."""
    if len(x) != len(y) or not x:
        return 0.0

    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if denom_x == 0 or denom_y == 0:
        return 0.0

    return numerator / (denom_x * denom_y)


class InsightAggregator:
    """
    Aggregates persona/container usage and calculates correlations.

    The aggregator ingests metrics snapshots and exposes summary statistics
    for downstream predictive components.
    """

    def __init__(self) -> None:
        self._container_persona: DefaultDict[str, DefaultDict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._persona_totals: DefaultDict[str, float] = defaultdict(float)
        self._correlation_cache: Dict[Tuple[str, str], float] = {}

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset aggregated state."""
        self._container_persona.clear()
        self._persona_totals.clear()
        self._correlation_cache.clear()

    def ingest(self, snapshot: MetricsSnapshot) -> None:
        """Ingest metrics snapshot into aggregation buffers."""
        for persona, total in snapshot.persona_totals.items():
            self._persona_totals[persona] += float(total)

        for container, persona_counts in snapshot.container_persona_counts.items():
            for persona, count in persona_counts.items():
                self._container_persona[container][persona] += float(count)

        self._correlation_cache.clear()

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    def persona_strength(self, persona: str) -> float:
        """Return aggregate strength for a persona across all users."""
        return self._persona_totals.get(persona, 0.0)

    def top_containers(self, persona: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Return top containers associated with a persona."""
        scored: List[Tuple[str, float]] = []
        for container, persona_counts in self._container_persona.items():
            value = persona_counts.get(persona)
            if value:
                scored.append((container, value))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def persona_correlations(self) -> Dict[Tuple[str, str], float]:
        """Compute and cache persona-to-persona correlations."""
        if self._correlation_cache:
            return self._correlation_cache

        personas = sorted({persona for counts in self._container_persona.values() for persona in counts})
        if not personas:
            self._correlation_cache = {}
            return self._correlation_cache

        # Build per-container vectors for each persona
        persona_vectors: Dict[str, List[float]] = {persona: [] for persona in personas}
        for container in sorted(self._container_persona.keys()):
            counts = self._container_persona[container]
            for persona in personas:
                persona_vectors[persona].append(counts.get(persona, 0.0))

        correlations: Dict[Tuple[str, str], float] = {}
        for i, persona_a in enumerate(personas):
            for persona_b in personas[i + 1:]:
                corr = _pearson(persona_vectors[persona_a], persona_vectors[persona_b])
                correlations[(persona_a, persona_b)] = corr
                correlations[(persona_b, persona_a)] = corr

        self._correlation_cache = correlations
        return correlations

    def related_personas(self, persona: str, limit: int = 3) -> List[Tuple[str, float]]:
        """Return personas most correlated with the provided persona."""
        correlations = self.persona_correlations()
        scored = [
            (other, value)
            for (p_a, other), value in correlations.items()
            if p_a == persona and other != persona
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def focus_candidates(self, limit: int = 10) -> List[Tuple[str, str, float]]:
        """
        Return global focus candidates as (container, persona, score).

        Score is derived from persona totals and container association strength.
        """
        candidates: List[Tuple[str, str, float]] = []
        for container, persona_counts in self._container_persona.items():
            for persona, count in persona_counts.items():
                persona_strength = self._persona_totals.get(persona, 1.0)
                score = count * math.log1p(persona_strength)
                candidates.append((container, persona, score))

        candidates.sort(key=lambda item: item[2], reverse=True)
        return candidates[:limit]


__all__ = [
    "InsightAggregator",
]
