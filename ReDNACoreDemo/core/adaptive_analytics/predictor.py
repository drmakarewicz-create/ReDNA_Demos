"""
Phase 10 adaptive analytics predictor.

Produces ranked curiosity targets by blending ontology usage, persona
correlations, and Life OS learning velocity.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .insight_aggregator import InsightAggregator
from .metrics_engine import MetricsEngine, MetricsSnapshot


@dataclass
class PredictionResult:
    target: str
    persona: str
    score: float
    ontology_weight: float
    correlation_weight: float
    life_os_weight: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "target": self.target,
            "persona": self.persona,
            "score": round(self.score, 4),
            "sources": {
                "ontology": round(self.ontology_weight, 4),
                "correlation": round(self.correlation_weight, 4),
                "life_os": round(self.life_os_weight, 4),
            },
        }


class TraitPredictor:
    """
    Predictive analytics orchestrator for adaptive focus areas.

    Combines insights from MetricsEngine and InsightAggregator to generate
    proactive suggestions for curiosity expansion.
    """

    def __init__(self, metrics_engine: MetricsEngine, insight_aggregator: InsightAggregator):
        self._metrics_engine = metrics_engine
        self._aggregator = insight_aggregator
        self._model_loaded = False

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def load_model(self, path: str | None = None) -> None:
        """
        Placeholder model loader.

        For now, marks internal state as ready. When a serialized model is
        available we can load weights or parameters here.
        """
        self._model_loaded = True

    # ------------------------------------------------------------------
    # Prediction helpers
    # ------------------------------------------------------------------

    def _ensure_model(self) -> None:
        if not self._model_loaded:
            self.load_model()

    def _normalize(self, values: List[float]) -> List[float]:
        """Normalize a list of values to 0..1 range."""
        if not values:
            return []
        max_value = max(values)
        if max_value == 0:
            return [0.0 for _ in values]
        return [min(1.0, v / max_value) for v in values]

    def _life_os_signal(self, snapshot: MetricsSnapshot) -> float:
        """Compute life OS contribution signal."""
        rolling_avg = snapshot.life_os.rolling_7d_average
        # Normalize to 0..1 using soft saturation.
        return math.tanh(rolling_avg / 5.0)

    def _ontology_candidates(self, snapshot: MetricsSnapshot, limit: int = 10) -> List[Tuple[str, float]]:
        """Return top ontology containers for a user."""
        items = list(snapshot.container_totals.items())
        items.sort(key=lambda item: item[1], reverse=True)
        return items[:limit]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_next_focus(self, user_id: str, limit: int = 5) -> List[Dict[str, object]]:
        """
        Predict next curiosity targets for a user.

        Returns:
            List of predictions sorted by descending score.
        """
        start = time.perf_counter()
        self._ensure_model()

        snapshot = self._metrics_engine.snapshot(user_id)
        if not snapshot:
            return []

        ontology_candidates = self._ontology_candidates(snapshot, limit=limit * 2)
        if not ontology_candidates:
            return []

        ontology_scores = self._normalize([score for _, score in ontology_candidates])
        life_os_score = self._life_os_signal(snapshot)
        persona_correlations = self._aggregator.persona_correlations()

        predictions: List[PredictionResult] = []
        for (container, raw_score), normalized in zip(ontology_candidates, ontology_scores):
            persona_counts = snapshot.container_persona_counts.get(container, {})
            if not persona_counts:
                persona_counts = snapshot.persona_totals or {"unspecified": 1.0}

            best_persona = max(persona_counts.items(), key=lambda item: item[1])[0]
            correlation_peers = self._aggregator.related_personas(best_persona, limit=3)
            correlation_score = 0.0
            if correlation_peers:
                correlation_score = max(0.0, max(value for _, value in correlation_peers))
            else:
                # Fall back to persona strength if no correlations exist.
                correlation_score = abs(persona_correlations.get((best_persona, best_persona), 0.0))

            total_score = (
                0.55 * normalized +
                0.25 * correlation_score +
                0.20 * life_os_score
            )

            predictions.append(
                PredictionResult(
                    target=container,
                    persona=best_persona,
                    score=total_score,
                    ontology_weight=normalized,
                    correlation_weight=correlation_score,
                    life_os_weight=life_os_score,
                )
            )

        predictions.sort(key=lambda item: item.score, reverse=True)

        # Ensure latency target (<200ms) by short-circuiting if evaluation drifts.
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > 180 and len(predictions) > limit:
            # Trim to requested limit immediately.
            predictions = predictions[:limit]

        return [prediction.to_dict() for prediction in predictions[:limit]]


__all__ = [
    "TraitPredictor",
    "PredictionResult",
]
