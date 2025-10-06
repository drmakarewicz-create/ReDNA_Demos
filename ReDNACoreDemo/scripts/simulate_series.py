"""Multi-day RR/priority simulation harness.

Builds on ``simulate_day`` to stitch together a series of days, capturing how
RR and priority evolve with sustained coaching activity. Produces CSV curves
per step alongside a summary table. Generates a PNG overview when
``matplotlib`` is available.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from simulate_day import (  # type: ignore  # noqa: E402
    BASE_DIR,
    DEFAULT_OUTPUT_DIR,
    Record,
    simulate_day_curve,
    write_plot as write_day_plot,
)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_series_plot(path: Path, summary: Sequence[Dict[str, float]]) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    days = [item["day"] for item in summary]
    end_rr = [item["end_rr"] for item in summary]
    min_rr = [item["min_rr"] for item in summary]
    max_rr = [item["max_rr"] for item in summary]

    plt.figure(figsize=(8, 4.5))
    plt.plot(days, end_rr, marker="o", label="End-of-day RR", color="#0ea5e9")
    plt.plot(days, min_rr, marker="o", label="Min RR", color="#f97316", linestyle="--")
    plt.plot(days, max_rr, marker="o", label="Max RR", color="#22c55e", linestyle=":")
    plt.title("RR Trend Across Simulation Series")
    plt.xlabel("Day")
    plt.ylabel("RR")
    plt.ylim(0, 100)
    plt.grid(alpha=0.15)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate multiple days of RR/priority dynamics.")
    parser.add_argument("--days", type=int, default=7, help="Number of days to simulate (default: 7)")
    parser.add_argument("--steps", type=int, default=96, help="Steps per day (default: 96)")
    parser.add_argument("--seed", type=int, default=1234, help="Seed for inter-day randomness")
    parser.add_argument("--start-rr", type=float, default=45.0, help="Initial RR before day 1")
    parser.add_argument("--start-priority", type=float, default=55.0, help="Initial priority before day 1")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination for outputs")
    parser.add_argument("--prefix", type=str, default="sim_series", help="Filename prefix for generated artifacts")
    parser.add_argument("--no-plot", action="store_true", help="Skip PNG plot generation")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{args.prefix}_{timestamp}"

    aggregated_rows: List[Dict[str, object]] = []
    summary_rows: List[Dict[str, float]] = []

    current_rr = float(args.start_rr)
    current_priority = float(args.start_priority)

    global_step = 0

    for day in range(args.days):
        day_seed = args.seed + day * 37
        day_records, final_rr, final_priority = simulate_day_curve(
            seed=day_seed,
            steps=args.steps,
            start_rr=current_rr,
            start_priority=current_priority,
        )

        day_rr_values = [record["rr"] for record in day_records]

        for record in day_records:
            aggregated_rows.append(
                {
                    "global_step": global_step,
                    "day": day + 1,
                    "day_step": record["step"],
                    "phase": record["phase"],
                    "phase_step": record["phase_step"],
                    "minute": record["minute"],
                    "time_label": record["time_label"],
                    "rr": record["rr"],
                    "priority": record["priority"],
                    "delta_rr": record["delta_rr"],
                    "delta_priority": record["delta_priority"],
                    "note": record["note"],
                }
            )
            global_step += 1

        summary_rows.append(
            {
                "day": float(day + 1),
                "start_rr": round(current_rr, 3),
                "end_rr": round(final_rr, 3),
                "min_rr": round(min(day_rr_values), 3),
                "max_rr": round(max(day_rr_values), 3),
                "avg_rr": round(sum(day_rr_values) / len(day_rr_values), 3),
            }
        )

        baseline_rr = 52.0
        baseline_priority = 50.0
        current_rr = max(35.0, min(85.0, 0.65 * final_rr + 0.35 * baseline_rr + rng.uniform(-2.5, 2.5)))
        current_priority = max(30.0, min(80.0, 0.65 * final_priority + 0.35 * baseline_priority + rng.uniform(-2.0, 2.0)))

    csv_curve_path = output_dir / f"{base_name}.csv"
    write_csv(
        csv_curve_path,
        [
            "global_step",
            "day",
            "day_step",
            "phase",
            "phase_step",
            "minute",
            "time_label",
            "rr",
            "priority",
            "delta_rr",
            "delta_priority",
            "note",
        ],
        aggregated_rows,
    )

    summary_path = output_dir / f"{base_name}_summary.csv"
    write_csv(summary_path, ["day", "start_rr", "end_rr", "min_rr", "max_rr", "avg_rr"], summary_rows)

    png_path = None
    if not args.no_plot:
        png_path = write_series_plot(output_dir / f"{base_name}.png", summary_rows)

    message = f"[simulate_series] wrote {csv_curve_path.relative_to(BASE_DIR)} and {summary_path.relative_to(BASE_DIR)}"
    if png_path:
        message += f" (+ {png_path.relative_to(BASE_DIR)})"
    print(message)


if __name__ == "__main__":
    main()
