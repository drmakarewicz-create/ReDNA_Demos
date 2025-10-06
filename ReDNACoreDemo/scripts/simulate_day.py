"""Simulate a single demo day of RR/priority shifts.

The simulation follows four conceptual phases:

1. Self-report: RR climbs modestly as the user shares their perspective.
2. Corroboration: RR and confidence accelerate with supporting evidence.
3. Contradiction: A discovery forces a course correction and lowers RR.
4. Decay: Follow-up and time restore equilibrium and reduce urgency.

Outputs a CSV (and optional PNG plot when ``matplotlib`` is available)
under ``data/_sim`` capturing the RR/priority curves for the day.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "_sim"


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    ratio: float
    target_rr: float
    target_priority: float
    noise: float


PHASES: Sequence[PhaseSpec] = (
    PhaseSpec("self_report", 0.24, 60.0, 48.0, 0.35),
    PhaseSpec("corroboration", 0.26, 78.0, 38.0, 0.45),
    PhaseSpec("contradiction", 0.20, 50.0, 62.0, 0.65),
    PhaseSpec("decay", 0.30, 55.0, 52.0, 0.3),
)


Record = Dict[str, float | int | str]


def _resolve_phase_lengths(total_steps: int) -> List[int]:
    lengths: List[int] = []
    assigned = 0
    for index, phase in enumerate(PHASES):
        if index == len(PHASES) - 1:
            count = max(1, total_steps - assigned)
        else:
            count = max(1, int(round(total_steps * phase.ratio)))
        lengths.append(count)
        assigned += count

    delta = assigned - total_steps
    if delta != 0:
        # Adjust the last phase to match the requested step count exactly.
        lengths[-1] = max(1, lengths[-1] - delta)

    if sum(lengths) != total_steps:
        # As a final guard (in case of severe rounding issues), tweak the
        # last bucket so that the sum matches exactly.
        lengths[-1] += total_steps - sum(lengths)

    return lengths


def _soft_target_delta(current: float, target: float, remaining: int, noise: float, rng: random.Random) -> float:
    if remaining <= 0:
        remaining = 1
    deterministic = (target - current) / remaining
    jitter = rng.gauss(0.0, noise)
    return deterministic + jitter


def _time_label(minutes: float) -> str:
    minutes = max(0.0, minutes)
    hours = int(minutes // 60)
    mins = int(round(minutes % 60))
    if mins == 60:
        hours += 1
        mins = 0
    hours %= 24
    return f"{hours:02d}:{mins:02d}"


def simulate_day_curve(
    *,
    seed: int = 42,
    steps: int = 96,
    start_rr: float = 45.0,
    start_priority: float = 55.0,
) -> Tuple[List[Record], float, float]:
    rng = random.Random(seed)
    lengths = _resolve_phase_lengths(max(4, steps))
    minutes_per_step = (24 * 60) / steps

    records: List[Record] = []
    rr = float(start_rr)
    priority = float(start_priority)
    minute_cursor = 0.0

    total_steps = 0

    for phase_index, (phase, phase_len) in enumerate(zip(PHASES, lengths)):
        for step_in_phase in range(phase_len):
            remaining = phase_len - step_in_phase
            rr_delta = _soft_target_delta(rr, phase.target_rr, remaining, phase.noise, rng)
            priority_delta = _soft_target_delta(priority, phase.target_priority, remaining, phase.noise * 0.8, rng)

            rr = max(0.0, min(100.0, rr + rr_delta))
            priority = max(0.0, min(100.0, priority + priority_delta))

            note = ""
            if phase.name == "self_report" and step_in_phase == 0:
                note = "Session opened with fresh context from member."
            elif phase.name == "corroboration" and step_in_phase == 0:
                note = "Evidence corroborated; RR accelerating."
            elif phase.name == "contradiction" and step_in_phase == 0:
                note = "Contradiction surfaced; recalibrating plan."
            elif phase.name == "decay" and step_in_phase == 0:
                note = "Follow-ups scheduled; natural decay begins."

            record: Record = {
                "step": total_steps,
                "phase_index": phase_index,
                "phase": phase.name,
                "phase_step": step_in_phase,
                "minute": round(minute_cursor, 2),
                "time_label": _time_label(minute_cursor),
                "rr": round(rr, 3),
                "priority": round(priority, 3),
                "delta_rr": round(rr_delta, 3),
                "delta_priority": round(priority_delta, 3),
                "note": note,
            }
            records.append(record)

            minute_cursor += minutes_per_step
            total_steps += 1

    return records, rr, priority


def write_csv(path: Path, records: Iterable[Record]) -> None:
    fieldnames = [
        "step",
        "phase_index",
        "phase",
        "phase_step",
        "minute",
        "time_label",
        "rr",
        "priority",
        "delta_rr",
        "delta_priority",
        "note",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(row)


def write_plot(path: Path, records: Sequence[Record]) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    x = [row["minute"] for row in records]
    rr = [row["rr"] for row in records]
    priority = [row["priority"] for row in records]
    phases = [row["phase"] for row in records]

    plt.figure(figsize=(10, 4.5))
    plt.plot(x, rr, label="RR", color="#0ea5e9", linewidth=2)
    plt.plot(x, priority, label="Priority", color="#f97316", linewidth=2)

    phase_bounds: Dict[str, float] = {}
    for minute, phase in zip(x, phases):
        phase_bounds.setdefault(phase, minute)

    for phase, start_minute in phase_bounds.items():
        plt.axvline(start_minute, color="#334155", linestyle="--", linewidth=0.5)
        plt.text(start_minute + 5, max(rr) + 2, phase.replace("_", " ").title(), fontsize=8, color="#64748b")

    plt.title("Simulated Daily RR / Priority Curve")
    plt.xlabel("Minute of day")
    plt.ylabel("Score")
    plt.ylim(0, 100)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a single demo day of RR vs. priority dynamics.")
    parser.add_argument("--steps", type=int, default=96, help="Number of time steps across the simulated day (default: 96)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--start-rr", type=float, default=45.0, help="Starting RR score")
    parser.add_argument("--start-priority", type=float, default=55.0, help="Starting priority score")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for CSV/PNG outputs")
    parser.add_argument("--prefix", type=str, default="sim_day", help="Filename prefix for generated artifacts")
    parser.add_argument("--no-plot", action="store_true", help="Skip PNG generation even if matplotlib is available")
    args = parser.parse_args()

    records, final_rr, final_priority = simulate_day_curve(
        seed=args.seed,
        steps=args.steps,
        start_rr=args.start_rr,
        start_priority=args.start_priority,
    )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{args.prefix}_{timestamp}"
    csv_path = output_dir / f"{base_name}.csv"
    write_csv(csv_path, records)

    png_path = None
    if not args.no_plot:
        png_path = write_plot(output_dir / f"{base_name}.png", records)

    print(
        f"[simulate_day] wrote {csv_path.relative_to(BASE_DIR)}"
        + (f" and {png_path.relative_to(BASE_DIR)}" if png_path else "")
        + f" | final RR={final_rr:.2f} priority={final_priority:.2f}"
    )


if __name__ == "__main__":
    main()
