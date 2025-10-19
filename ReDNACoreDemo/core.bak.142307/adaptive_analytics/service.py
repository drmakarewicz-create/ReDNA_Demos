"""
Adaptive Analytics Service
==========================

Coordinates metrics ingestion, insight aggregation, and predictive focus
generation for DevX dashboards and API consumers.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .metrics_engine import MetricsEngine, MetricsSnapshot
from .insight_aggregator import InsightAggregator
from .predictor import TraitPredictor


@dataclass
class AdaptiveOverviewItem:
    user_id: str
    rolling_avg_7d: float
    top_focus: List[Dict[str, object]]
    confidence: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "user_id": self.user_id,
            "rolling_avg_7d": round(self.rolling_avg_7d, 4),
            "top_focus": self.top_focus,
            "confidence": round(self.confidence, 4),
        }


class AdaptiveAnalyticsService:
    """Central orchestrator for adaptive analytics."""

    def __init__(self, metrics_engine: Optional[MetricsEngine] = None, insight_aggregator: Optional[InsightAggregator] = None):
        self.metrics_engine = metrics_engine or MetricsEngine()
        self.insight_aggregator = insight_aggregator or InsightAggregator()
        self.predictor = TraitPredictor(self.metrics_engine, self.insight_aggregator)
        self.predictor.load_model()

        self._overview_cache: Dict[str, AdaptiveOverviewItem] = {}
        self._user_cache: Dict[str, Dict[str, object]] = {}
        self._last_refresh: Optional[datetime] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Refresh cycle
    # ------------------------------------------------------------------

    def refresh(self, force: bool = False) -> None:
        """
        Refresh cached analytics.

        Uses a lightweight lock to avoid concurrent rebuilds when invoked from
        multiple threads (e.g., API requests + background refresh).
        """
        with self._lock:
            if not force and self._last_refresh:
                if (datetime.now(timezone.utc) - self._last_refresh).total_seconds() < 5:
                    return

            start = time.perf_counter()
            snapshots = self.metrics_engine.refresh(force=force)

            self.insight_aggregator.reset()
            for snapshot in snapshots.values():
                self.insight_aggregator.ingest(snapshot)

            self._overview_cache.clear()
            self._user_cache.clear()

            for user_id, snapshot in snapshots.items():
                predictions = self.predictor.predict_next_focus(user_id, limit=5)
                confidence = self._compute_confidence(snapshot, predictions)

                overview_item = AdaptiveOverviewItem(
                    user_id=user_id,
                    rolling_avg_7d=snapshot.life_os.rolling_7d_average,
                    top_focus=predictions[:3],
                    confidence=confidence,
                )
                self._overview_cache[user_id] = overview_item

                self._user_cache[user_id] = self._build_user_payload(snapshot, predictions, confidence, start_time=start)

            self._last_refresh = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def overview(self) -> List[Dict[str, object]]:
        """Return overview data for all users."""
        self.refresh()
        return [item.to_dict() for item in self._overview_cache.values()]

    def user_view(self, user_id: str) -> Dict[str, object]:
        """Return detailed adaptive analytics for a single user."""
        self.refresh()
        if user_id not in self._user_cache:
            snapshot = self.metrics_engine.snapshot(user_id)
            if not snapshot:
                return {
                    "user_id": user_id,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "learning_velocity": {
                        "daily": [],
                        "rolling_avg_7d": 0.0,
                    },
                    "predictions": [],
                    "confidence": {
                        "value": 0.0,
                        "sources": {},
                    },
                    "latency_ms": 0,
                }

            predictions = self.predictor.predict_next_focus(user_id, limit=5)
            confidence = self._compute_confidence(snapshot, predictions)
            payload = self._build_user_payload(snapshot, predictions, confidence)
            self._user_cache[user_id] = payload
            return payload

        return self._user_cache[user_id]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_confidence(self, snapshot: MetricsSnapshot, predictions: List[Dict[str, object]]) -> float:
        """Compute adaptive confidence based on learning velocity and prediction coherence."""
        if not predictions:
            return 0.0

        avg_prediction = sum(pred["score"] for pred in predictions) / len(predictions)
        velocity = snapshot.life_os.rolling_7d_average

        # Blend normalized velocity with prediction average.
        velocity_component = min(1.0, velocity / 5.0)
        confidence = 0.6 * avg_prediction + 0.4 * velocity_component
        return max(0.0, min(1.0, confidence))

    def _build_user_payload(
        self,
        snapshot: MetricsSnapshot,
        predictions: List[Dict[str, object]],
        confidence: float,
        start_time: Optional[float] = None,
    ) -> Dict[str, object]:
        """Build JSON payload for user analytics."""
        latency_ms = 0
        if start_time is not None:
            latency_ms = int((time.perf_counter() - start_time) * 1000)

        sources_summary = {}
        if predictions:
            sources_summary = {
                "ontology": round(sum(p["sources"]["ontology"] for p in predictions) / len(predictions), 4),
                "correlation": round(sum(p["sources"]["correlation"] for p in predictions) / len(predictions), 4),
                "life_os": round(sum(p["sources"]["life_os"] for p in predictions) / len(predictions), 4),
            }

        return {
            "user_id": snapshot.user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "learning_velocity": {
                "daily": snapshot.serialize_learning_velocity(),
                "rolling_avg_7d": round(snapshot.life_os.rolling_7d_average, 4),
                "goal_confidence_avg": round(snapshot.life_os.goal_confidence_avg, 4),
                "goals_total": snapshot.life_os.goals_total,
            },
            "predictions": predictions,
            "confidence": {
                "value": round(confidence, 4),
                "sources": sources_summary,
            },
            "latency_ms": latency_ms,
        }


__all__ = [
    "AdaptiveAnalyticsService",
    "AdaptiveOverviewItem",
]
