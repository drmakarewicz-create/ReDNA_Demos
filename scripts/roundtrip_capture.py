#!/usr/bin/env python3
"""
Roundtrip Performance Capture

Polls Core and DevX metrics every 60 seconds and appends the hop timing
summary to docs/reports/roundtrip_timeseries.csv. Intended to run in a tmux
or screen session during the 24h baseline window.
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_CSV = PROJECT_ROOT / "docs" / "reports" / "roundtrip_timeseries.csv"

CORE_URL = os.getenv("CORE_BASE", "http://127.0.0.1:8004")
DEVX_URL = os.getenv("DEVX_BASE", "http://127.0.0.1:8012")


def fetch_json(url: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.RequestException:
        return None


def ensure_csv_header() -> None:
    if OUTPUT_CSV.exists():
        return
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "timestamp_utc",
                "hop_ms_p50",
                "hop_ms_p95",
                "hop_ms_p99",
                "ingest_requests",
                "ingest_errors",
                "rr_mode",
                "ucnrr_status",
            ]
        )


def extract_hop_metrics(metrics: Dict[str, Any]) -> Dict[str, float]:
    timers = metrics.get("timers", {})
    hop_total = timers.get("hop_ms.total", {})
    return {
        "p50": float(hop_total.get("p50", 0.0) or 0.0),
        "p95": float(hop_total.get("p95", 0.0) or 0.0),
        "p99": float(hop_total.get("p99", 0.0) or 0.0),
    }


def extract_ingest_counters(metrics: Dict[str, Any]) -> Dict[str, int]:
    counters = metrics.get("counters", {})
    return {
        "requests": int(counters.get("ingest.requests", 0) or 0),
        "errors": int(counters.get("ingest.errors", 0) or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture roundtrip metrics over time.")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds (default 60)")
    parser.add_argument("--core-base", default=CORE_URL, help="Core base URL (default http://127.0.0.1:8004)")
    parser.add_argument("--devx-base", default=DEVX_URL, help="DevX base URL (default http://127.0.0.1:8012)")
    args = parser.parse_args()

    core_base = args.core_base.rstrip("/")
    devx_base = args.devx_base.rstrip("/")

    ensure_csv_header()
    print(f"Writing metrics to {OUTPUT_CSV}")
    print(f"Polling every {args.interval} seconds. Ctrl+C to stop.")

    try:
        while True:
            timestamp = datetime.now(timezone.utc).isoformat()

            metrics = fetch_json(f"{core_base}/metrics")
            health = fetch_json(f"{core_base}/health")
            ucnrr_status = fetch_json(f"{devx_base}/devx/api/stack/ucnrr/status")

            if not metrics:
                print(f"[{timestamp}] Failed to fetch Core metrics.")
                time.sleep(args.interval)
                continue

            hop = extract_hop_metrics(metrics)
            ingest = extract_ingest_counters(metrics)
            rr_mode = ""
            if health:
                rr_mode = str(health.get("rr_mode", "")).lower()
            ucnrr_mode = ""
            if ucnrr_status:
                ucnrr_mode = str(ucnrr_status.get("status", "")).lower()

            with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        timestamp,
                        f"{hop['p50']:.2f}",
                        f"{hop['p95']:.2f}",
                        f"{hop['p99']:.2f}",
                        ingest["requests"],
                        ingest["errors"],
                        rr_mode,
                        ucnrr_mode,
                    ]
                )

            print(
                f"[{timestamp}] hop_ms p50={hop['p50']:.1f} p95={hop['p95']:.1f} p99={hop['p99']:.1f} | "
                f"ingest req={ingest['requests']} err={ingest['errors']} | rr_mode={rr_mode} "
                f"ucnrr={ucnrr_mode}"
            )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nCapture stopped by user.")


if __name__ == "__main__":
    main()
