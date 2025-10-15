"""
Prompt Tuner — Self-Improvement Loop Foundation
===============================================

Generates evidence-based prompt improvement suggestions from telemetry analysis.

Architecture:
    - Analyzes correlations from telemetry metrics
    - Generates tuning suggestions with confidence scores
    - Evidence tracing (links back to specific telemetry entries)
    - Confidence calibration: ≥0.85 auto-eligible, 0.70-0.84 review-worthy

Author: ReDNA Core Team
Created: 2025-10-09
Benchmark: #8 Self-Improvement Loop
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict


@dataclass
class TuningSuggestion:
    """Single prompt tuning suggestion."""
    id: str
    coach_id: str
    type: str  # tone_adjustment, creativity_adjustment, behavior_hint
    current_value: Any
    recommended_value: Any
    confidence: float
    evidence: List[str]
    telemetry_refs: List[str]
    auto_apply_eligible: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class PromptTuner:
    """Generate prompt improvement suggestions from telemetry analysis."""

    # Confidence thresholds (ChatGPT recommendation)
    CONFIDENCE_AUTO_APPLY = 0.85
    CONFIDENCE_REVIEW_WORTHY = 0.70

    # Minimum sample size for reliable suggestions
    MIN_SAMPLE_SIZE = 10

    def __init__(self, analysis_report: Dict[str, Any]):
        """
        Initialize prompt tuner with analysis report.

        Args:
            analysis_report: Output from TelemetryAnalyzer
        """
        self.report = analysis_report
        self.suggestions = []
        self._suggestion_counter = 0

    def generate_suggestions(self) -> List[Dict[str, Any]]:
        """
        Generate all tuning suggestions from analysis report.

        Returns:
            List of suggestion dictionaries
        """
        all_suggestions = []

        for coach_id, metrics in self.report.get("coaches", {}).items():
            # Generate suggestions for this coach
            coach_suggestions = self._generate_coach_suggestions(coach_id, metrics)
            all_suggestions.extend(coach_suggestions)

        self.suggestions = all_suggestions
        return all_suggestions

    def _generate_coach_suggestions(
        self,
        coach_id: str,
        metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate suggestions for a single coach.

        Args:
            coach_id: Coach identifier
            metrics: Coach metrics from analysis

        Returns:
            List of suggestions for this coach
        """
        suggestions = []

        # 1. Tone adjustment suggestions
        tone_suggestion = self._suggest_tone_adjustment(coach_id, metrics)
        if tone_suggestion:
            suggestions.append(tone_suggestion.to_dict())

        # 2. Creativity adjustment suggestions
        creativity_suggestion = self._suggest_creativity_adjustment(coach_id, metrics)
        if creativity_suggestion:
            suggestions.append(creativity_suggestion.to_dict())

        # 3. Sentiment-based behavioral hints
        behavior_suggestion = self._suggest_behavior_hints(coach_id, metrics)
        if behavior_suggestion:
            suggestions.append(behavior_suggestion.to_dict())

        return suggestions

    def _suggest_tone_adjustment(
        self,
        coach_id: str,
        metrics: Dict[str, Any]
    ) -> Optional[TuningSuggestion]:
        """
        Suggest tone adjustment based on correlation analysis.

        Args:
            coach_id: Coach identifier
            metrics: Coach metrics

        Returns:
            TuningSuggestion or None
        """
        tone_correlation = metrics.get("tone_correlation", {})
        top_tone = tone_correlation.get("top_tone")
        top_tone_score = tone_correlation.get("top_tone_score", 0.0)
        tone_scores = tone_correlation.get("tone_scores", {})

        # Need sufficient data
        if not top_tone or len(tone_scores) < 2:
            return None

        # Check if top tone is significantly better than average
        avg_score = sum(tone_scores.values()) / len(tone_scores)
        improvement = top_tone_score - avg_score

        # Only suggest if improvement > 10%
        if improvement < 0.10:
            return None

        # Compute confidence based on sample size and improvement magnitude
        entries_analyzed = metrics.get("entries_analyzed", 0)
        sample_confidence = min(entries_analyzed / 100, 1.0)  # Caps at 100 entries
        improvement_confidence = min(improvement * 2, 1.0)  # Higher improvement = higher confidence
        confidence = round((sample_confidence + improvement_confidence) / 2, 2)

        # Build evidence
        evidence = [
            f"Top tone '{top_tone}' has {top_tone_score:.1%} positive sentiment",
            f"Average sentiment across all tones: {avg_score:.1%}",
            f"Improvement: +{improvement:.1%}"
        ]

        return TuningSuggestion(
            id=self._next_suggestion_id(),
            coach_id=coach_id,
            type="tone_adjustment",
            current_value="auto-detected from current sessions",
            recommended_value=top_tone,
            confidence=confidence,
            evidence=evidence,
            telemetry_refs=[f"prompts/insights/{coach_id}.jsonl"],
            auto_apply_eligible=(confidence >= self.CONFIDENCE_AUTO_APPLY)
        )

    def _suggest_creativity_adjustment(
        self,
        coach_id: str,
        metrics: Dict[str, Any]
    ) -> Optional[TuningSuggestion]:
        """
        Suggest creativity bias adjustment.

        Args:
            coach_id: Coach identifier
            metrics: Coach metrics

        Returns:
            TuningSuggestion or None
        """
        creativity_analysis = metrics.get("creativity_analysis", {})
        optimal_creativity = creativity_analysis.get("optimal_creativity")
        sample_size = creativity_analysis.get("sample_size", 0)

        # Need sufficient data
        if optimal_creativity is None or sample_size < self.MIN_SAMPLE_SIZE:
            return None

        # Check if optimal differs from default (0.7)
        default_creativity = 0.7
        delta = abs(optimal_creativity - default_creativity)

        # Only suggest if delta > 0.05
        if delta < 0.05:
            return None

        # Compute confidence based on sample size and delta
        sample_confidence = min(sample_size / 50, 1.0)  # Caps at 50 samples
        delta_confidence = min(delta * 5, 1.0)  # Larger delta = higher confidence
        confidence = round((sample_confidence + delta_confidence) / 2, 2)

        # Check latency impact
        latency = metrics.get("latency_percentiles", {})
        latency_evidence = f"p95 latency: {latency.get('p95', 0)}ms" if latency else "No latency data"

        evidence = [
            f"Optimal creativity based on {sample_size} positive outcomes: {optimal_creativity}",
            f"Current default: {default_creativity}",
            latency_evidence
        ]

        return TuningSuggestion(
            id=self._next_suggestion_id(),
            coach_id=coach_id,
            type="creativity_adjustment",
            current_value=default_creativity,
            recommended_value=optimal_creativity,
            confidence=confidence,
            evidence=evidence,
            telemetry_refs=[f"prompts/insights/{coach_id}.jsonl"],
            auto_apply_eligible=(confidence >= self.CONFIDENCE_AUTO_APPLY)
        )

    def _suggest_behavior_hints(
        self,
        coach_id: str,
        metrics: Dict[str, Any]
    ) -> Optional[TuningSuggestion]:
        """
        Suggest behavior hints based on sentiment trends.

        Args:
            coach_id: Coach identifier
            metrics: Coach metrics

        Returns:
            TuningSuggestion or None
        """
        sentiment_trend = metrics.get("sentiment_trend", {})
        positive_rate = sentiment_trend.get("positive", 0.0)
        negative_rate = sentiment_trend.get("negative", 0.0)

        # If negative rate is high (>15%), suggest more empathetic hints
        if negative_rate > 0.15:
            confidence = round(min(negative_rate * 2, 0.90), 2)  # Higher negative = higher confidence

            evidence = [
                f"Negative sentiment rate: {negative_rate:.1%}",
                f"Positive sentiment rate: {positive_rate:.1%}",
                "Recommend increasing empathetic tone and supportive language"
            ]

            return TuningSuggestion(
                id=self._next_suggestion_id(),
                coach_id=coach_id,
                type="behavior_hint",
                current_value="standard",
                recommended_value="empathetic_boost",
                confidence=confidence,
                evidence=evidence,
                telemetry_refs=[f"prompts/insights/{coach_id}.jsonl"],
                auto_apply_eligible=(confidence >= self.CONFIDENCE_AUTO_APPLY)
            )

        # If positive rate is very high (>85%), coach is already optimal
        if positive_rate > 0.85:
            confidence = round(positive_rate, 2)

            evidence = [
                f"Positive sentiment rate: {positive_rate:.1%}",
                "Current behavior hints are optimal - no changes recommended"
            ]

            return TuningSuggestion(
                id=self._next_suggestion_id(),
                coach_id=coach_id,
                type="behavior_hint",
                current_value="current",
                recommended_value="maintain_current",
                confidence=confidence,
                evidence=evidence,
                telemetry_refs=[f"prompts/insights/{coach_id}.jsonl"],
                auto_apply_eligible=False  # Maintenance suggestions aren't auto-applied
            )

        return None

    def _next_suggestion_id(self) -> str:
        """Generate next suggestion ID."""
        self._suggestion_counter += 1
        return f"tune_{self._suggestion_counter:03d}"

    def save_suggestions(self, suggestions: List[Dict[str, Any]]) -> Dict[str, Path]:
        """
        Save suggestions to JSON files (one per coach).

        Args:
            suggestions: List of suggestion dictionaries

        Returns:
            Dictionary mapping coach_id to output file path
        """
        output_dir = Path("data/learning/suggestions")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Group by coach
        by_coach = {}
        for suggestion in suggestions:
            coach_id = suggestion["coach_id"]
            if coach_id not in by_coach:
                by_coach[coach_id] = []
            by_coach[coach_id].append(suggestion)

        # Save per-coach files
        output_paths = {}
        for coach_id, coach_suggestions in by_coach.items():
            output_file = output_dir / f"{coach_id}.json"

            report = {
                "coach_id": coach_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "suggestion_count": len(coach_suggestions),
                "auto_apply_eligible": sum(1 for s in coach_suggestions if s["auto_apply_eligible"]),
                "suggestions": coach_suggestions
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)

            output_paths[coach_id] = output_file

        print(f"✅ Suggestions saved for {len(output_paths)} coaches")

        # Print summary
        total_suggestions = sum(len(s) for s in by_coach.values())
        auto_eligible = sum(1 for s in suggestions if s["auto_apply_eligible"])

        print(f"   📝 {total_suggestions} total suggestions")
        print(f"   ⚡ {auto_eligible} auto-apply eligible (confidence ≥ {self.CONFIDENCE_AUTO_APPLY})")

        return output_paths

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of generated suggestions.

        Returns:
            Summary dictionary
        """
        if not self.suggestions:
            return {"total": 0, "by_confidence": {}, "by_type": {}}

        # Count by confidence level
        high_confidence = sum(1 for s in self.suggestions if s["confidence"] >= self.CONFIDENCE_AUTO_APPLY)
        medium_confidence = sum(1 for s in self.suggestions
                               if self.CONFIDENCE_REVIEW_WORTHY <= s["confidence"] < self.CONFIDENCE_AUTO_APPLY)
        low_confidence = sum(1 for s in self.suggestions if s["confidence"] < self.CONFIDENCE_REVIEW_WORTHY)

        # Count by type
        by_type = {}
        for s in self.suggestions:
            suggestion_type = s["type"]
            by_type[suggestion_type] = by_type.get(suggestion_type, 0) + 1

        return {
            "total": len(self.suggestions),
            "by_confidence": {
                "high (≥0.85)": high_confidence,
                "medium (0.70-0.84)": medium_confidence,
                "low (<0.70)": low_confidence
            },
            "by_type": by_type,
            "auto_apply_eligible": sum(1 for s in self.suggestions if s["auto_apply_eligible"])
        }


def main():
    """CLI entry point for prompt tuning."""
    # Load analysis report
    report_path = Path("data/learning/analysis_report.json")

    if not report_path.exists():
        print("❌ Analysis report not found. Run telemetry_analyzer.py first.")
        return

    with open(report_path, 'r', encoding='utf-8') as f:
        analysis_report = json.load(f)

    # Generate suggestions
    print("🔧 Generating prompt tuning suggestions...")
    tuner = PromptTuner(analysis_report)
    suggestions = tuner.generate_suggestions()

    # Save suggestions
    tuner.save_suggestions(suggestions)

    # Print summary
    summary = tuner.get_summary()
    print("\n📊 Suggestion Summary:")
    print(f"   Total: {summary['total']}")
    print(f"   By confidence: {summary['by_confidence']}")
    print(f"   By type: {summary['by_type']}")


if __name__ == "__main__":
    main()
