"""
Telemetry Analyzer — Self-Improvement Loop Foundation
=====================================================

Parses existing JSONL telemetry and computes actionable metrics for prompt tuning.

Architecture:
    - Load telemetry from prompts/insights/*.jsonl
    - Schema validation before aggregation
    - Per-coach metrics: sentiment, tokens, latency, tone, creativity
    - Output: data/learning/analysis_report.json

Author: ReDNA Core Team
Created: 2025-10-09
Benchmark: #8 Self-Improvement Loop
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import statistics


class TelemetryAnalyzer:
    """Analyze telemetry data to compute coach performance metrics."""

    def __init__(self, data_dir: Path = Path("data"), tolerant_validation: bool = True):
        self.data_dir = Path(data_dir)
        self.prompts_dir = self.data_dir.parent / "prompts"
        self.insights_dir = self.prompts_dir / "insights"
        self.output_dir = self.data_dir / "learning"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Cache for file handles (performance optimization)
        self._file_cache = {}
        self.tolerant_validation = tolerant_validation
        self._run_stats = self._init_run_stats()

    @staticmethod
    def _init_run_stats() -> Dict[str, int]:
        return {
            "malformed_lines_skipped": 0,
            "defaults_injected": 0,
            "files_cleaned": 0,
        }

    def analyze_all_coaches(self) -> Dict[str, Any]:
        """
        Analyze telemetry for all coaches.

        Returns:
            Analysis report with per-coach metrics
        """
        start_time = time.time()

        # Reset run stats for this execution
        self._run_stats = self._init_run_stats()

        # Find all telemetry files
        telemetry_files = list(self.insights_dir.glob("*.jsonl"))

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "telemetry_files_analyzed": len(telemetry_files),
            "total_entries": 0,
            "coaches": {},
            "processing_time_ms": 0
        }

        for telemetry_file in telemetry_files:
            coach_id = telemetry_file.stem  # e.g., "career_coach" from "career_coach.jsonl"

            # Analyze this coach's telemetry
            coach_metrics = self._analyze_coach(telemetry_file, coach_id)

            if coach_metrics:
                report["coaches"][coach_id] = coach_metrics
                report["total_entries"] += coach_metrics["entries_analyzed"]

        # Compute processing time
        elapsed_ms = (time.time() - start_time) * 1000
        report["processing_time_ms"] = round(elapsed_ms, 2)
        report["malformed_lines_skipped"] = self._run_stats["malformed_lines_skipped"]
        report["defaults_injected"] = self._run_stats["defaults_injected"]
        report["files_cleaned"] = self._run_stats["files_cleaned"]

        return report

    def _analyze_coach(self, telemetry_file: Path, coach_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyze telemetry for a single coach.

        Args:
            telemetry_file: Path to JSONL telemetry file
            coach_id: Coach identifier

        Returns:
            Metrics dictionary or None if no valid entries
        """
        # Load and validate entries
        entries = self._load_telemetry(telemetry_file, coach_id=coach_id)

        if not entries:
            return None

        # Sanity check: validate first 100 entries (ChatGPT recommendation)
        sample_size = min(100, len(entries))
        valid_entries = []

        for i, entry in enumerate(entries):
            if self._validate_entry(entry):
                valid_entries.append(entry)
            elif i < sample_size:
                # Log validation failures in sample
                print(f"⚠️  Validation failed for {telemetry_file.name}:{i+1}")

        if not valid_entries:
            return None

        # Compute metrics
        metrics = {
            "coach_id": coach_id,
            "entries_analyzed": len(valid_entries),
            "entries_valid": len(valid_entries),
            "entries_invalid": len(entries) - len(valid_entries),
            "sentiment_trend": self._compute_sentiment_trend(valid_entries),
            "token_efficiency": self._compute_token_efficiency(valid_entries),
            "latency_percentiles": self._compute_latency_percentiles(valid_entries),
            "tone_correlation": self._compute_tone_correlation(valid_entries),
            "creativity_analysis": self._compute_creativity_analysis(valid_entries),
            "curiosity_gap_closure": self._compute_curiosity_metrics(valid_entries)
        }

        return metrics

    def _load_telemetry(self, telemetry_file: Path, coach_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Load JSONL telemetry file with error handling.

        Args:
            telemetry_file: Path to JSONL file
            coach_id: Coach identifier hint for default injection

        Returns:
            List of telemetry entries
        """
        entries: List[Dict[str, Any]] = []

        if not telemetry_file.exists():
            return entries

        malformed_before = self._run_stats["malformed_lines_skipped"]
        defaults_before = self._run_stats["defaults_injected"]
        mutated = False
        now_iso = datetime.now(timezone.utc).isoformat()
        coach_hint = coach_id or telemetry_file.stem

        try:
            with open(telemetry_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError as e:
                        if self.tolerant_validation:
                            self._run_stats["malformed_lines_skipped"] += 1
                            continue
                        raise ValueError(f"Malformed JSON in {telemetry_file}:{line_num}: {e}") from e

                    if not isinstance(entry, dict):
                        if self.tolerant_validation:
                            self._run_stats["malformed_lines_skipped"] += 1
                            continue
                        raise ValueError(
                            f"Invalid telemetry entry (expected object) in {telemetry_file}:{line_num}"
                        )

                    if self.tolerant_validation:
                        inserted = self._apply_schema_defaults(entry, coach_hint, now_iso)
                        if inserted:
                            mutated = True
                            self._run_stats["defaults_injected"] += inserted
                    else:
                        missing = [key for key in ("ts", "coach_id", "kind") if not entry.get(key)]
                        if missing:
                            raise ValueError(
                                f"Missing required fields {missing} in {telemetry_file}:{line_num}"
                            )

                    entries.append(entry)
        except ValueError:
            raise
        except Exception as e:
            print(f"❌ Error reading {telemetry_file}: {e}")

        if self.tolerant_validation:
            cleaned = (
                self._run_stats["malformed_lines_skipped"] > malformed_before
                or self._run_stats["defaults_injected"] > defaults_before
            )
            if cleaned or mutated:
                self._run_stats["files_cleaned"] += 1

        return entries

    @staticmethod
    def _apply_schema_defaults(entry: Dict[str, Any], coach_hint: str, now_iso: str) -> int:
        """
        Inject schema-lite defaults for missing keys.

        Returns:
            Number of field defaults inserted.
        """
        inserted = 0

        if not isinstance(entry.get("ts"), str) or not entry.get("ts"):
            entry["ts"] = now_iso
            inserted += 1

        if not isinstance(entry.get("kind"), str) or not entry.get("kind"):
            entry["kind"] = "telemetry"
            inserted += 1

        coach_value = entry.get("coach_id")
        if not isinstance(coach_value, str) or not coach_value.strip():
            entry["coach_id"] = coach_hint or "unknown"
            inserted += 1

        return inserted

    def _validate_entry(self, entry: Dict[str, Any]) -> bool:
        """
        Validate telemetry entry schema.

        Required fields: ts, user_id, active_coach_id, context_version

        Args:
            entry: Telemetry entry dictionary

        Returns:
            True if valid, False otherwise
        """
        if self.tolerant_validation:
            required_fields = ["ts", "coach_id", "kind"]
        else:
            required_fields = ["ts", "user_id", "active_coach_id", "context_version"]

        for field in required_fields:
            if field not in entry:
                return False

        return True

    def _compute_sentiment_trend(self, entries: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Compute sentiment distribution.

        Args:
            entries: List of telemetry entries

        Returns:
            Sentiment percentages (positive, neutral, negative)
        """
        sentiment_counts = defaultdict(int)
        total = 0

        for entry in entries:
            sentiment = entry.get("sentiment", "neutral")
            sentiment_counts[sentiment] += 1
            total += 1

        if total == 0:
            return {"positive": 0.0, "neutral": 0.0, "negative": 0.0}

        return {
            "positive": round(sentiment_counts.get("positive", 0) / total, 3),
            "neutral": round(sentiment_counts.get("neutral", 0) / total, 3),
            "negative": round(sentiment_counts.get("negative", 0) / total, 3)
        }

    def _compute_token_efficiency(self, entries: List[Dict[str, Any]]) -> float:
        """
        Compute average tokens per positive outcome.

        Args:
            entries: List of telemetry entries

        Returns:
            Average token efficiency
        """
        positive_entries = [e for e in entries if e.get("sentiment") == "positive"]

        if not positive_entries:
            return 0.0

        tokens = [e.get("tokens", 0) for e in positive_entries if "tokens" in e]

        if not tokens:
            return 0.0

        return round(statistics.mean(tokens), 1)

    def _compute_latency_percentiles(self, entries: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Compute latency percentiles (p50, p95, p99).

        Args:
            entries: List of telemetry entries

        Returns:
            Latency percentiles in milliseconds
        """
        latencies = [e.get("build_ms", 0) for e in entries if "build_ms" in e]

        if not latencies:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        return {
            "p50": round(latencies_sorted[int(n * 0.50)], 2),
            "p95": round(latencies_sorted[int(n * 0.95)], 2),
            "p99": round(latencies_sorted[int(n * 0.99)], 2)
        }

    def _compute_tone_correlation(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze which tone keywords correlate with best sentiment.

        Args:
            entries: List of telemetry entries

        Returns:
            Tone correlation analysis
        """
        tone_sentiment = defaultdict(lambda: {"positive": 0, "total": 0})

        for entry in entries:
            tone = entry.get("features", {}).get("tone", "neutral")
            sentiment = entry.get("sentiment", "neutral")

            tone_sentiment[tone]["total"] += 1
            if sentiment == "positive":
                tone_sentiment[tone]["positive"] += 1

        # Compute positive rate per tone
        tone_scores = {}
        for tone, counts in tone_sentiment.items():
            if counts["total"] > 0:
                tone_scores[tone] = round(counts["positive"] / counts["total"], 3)

        # Find top tone
        top_tone = max(tone_scores.items(), key=lambda x: x[1]) if tone_scores else ("neutral", 0.0)

        return {
            "top_tone": top_tone[0],
            "top_tone_score": top_tone[1],
            "tone_scores": tone_scores
        }

    def _compute_creativity_analysis(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze optimal creativity bias range.

        Args:
            entries: List of telemetry entries

        Returns:
            Creativity analysis
        """
        creativity_values = []

        for entry in entries:
            creativity = entry.get("hints", {}).get("creativity_bias")
            sentiment = entry.get("sentiment")

            if creativity is not None and sentiment == "positive":
                creativity_values.append(creativity)

        if not creativity_values:
            return {"optimal_creativity": 0.7, "sample_size": 0}

        return {
            "optimal_creativity": round(statistics.mean(creativity_values), 2),
            "creativity_range": {
                "min": round(min(creativity_values), 2),
                "max": round(max(creativity_values), 2)
            },
            "sample_size": len(creativity_values)
        }

    def _compute_curiosity_metrics(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute curiosity gap closure metrics.

        Args:
            entries: List of telemetry entries

        Returns:
            Curiosity metrics
        """
        # This is a placeholder - full implementation requires RR tracking
        # For now, return basic structure
        return {
            "gap_closures": 0,
            "avg_closure_rate": 0.0,
            "note": "Full RR tracking integration pending"
        }

    def save_report(self, report: Dict[str, Any]) -> Path:
        """
        Save analysis report to JSON file.

        Args:
            report: Analysis report dictionary

        Returns:
            Path to saved report
        """
        output_file = self.output_dir / "analysis_report.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        print(f"✅ Analysis report saved: {output_file}")
        print(f"   📊 {report['total_entries']} entries analyzed in {report['processing_time_ms']}ms")
        print(f"   🧠 {len(report['coaches'])} coaches analyzed")

        return output_file


def main():
    """CLI entry point for telemetry analysis."""
    analyzer = TelemetryAnalyzer()

    print("🔍 Starting telemetry analysis...")
    report = analyzer.analyze_all_coaches()

    output_path = analyzer.save_report(report)

    # Print summary
    print("\n📈 Summary by Coach:")
    for coach_id, metrics in report["coaches"].items():
        sentiment = metrics["sentiment_trend"]
        print(f"   {coach_id}: {metrics['entries_analyzed']} entries, "
              f"{sentiment['positive']:.1%} positive")


if __name__ == "__main__":
    main()
