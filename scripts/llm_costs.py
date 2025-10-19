#!/usr/bin/env python3
"""
LLM Cost Tracking & Reporting

Aggregates cost records from ~/.redna/llm_costs.jsonl and generates monthly reports.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# Paths
COST_LOG_FILE = Path.home() / ".redna" / "llm_costs.jsonl"
REPORTS_DIR = Path(__file__).parent.parent / "docs" / "reports"


def read_costs(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Read all cost records from JSONL log.

    Args:
        path: Path to cost log (default: ~/.redna/llm_costs.jsonl)

    Returns:
        List of cost records
    """
    log_path = path or COST_LOG_FILE

    if not log_path.exists():
        return []

    records = []
    with open(log_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}")
                continue

    return records


def aggregate_month(month: str, path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Aggregate costs for a specific month.

    Args:
        month: Month in YYYY-MM format
        path: Path to cost log (default: ~/.redna/llm_costs.jsonl)

    Returns:
        Aggregated data dict with:
        - month: str
        - mtd_total_usd: float
        - by_provider: Dict[str, float]
        - by_model: Dict[str, float]
        - by_batch: Dict[str, Dict]
        - runs: List[Dict] (rollup per batch)
        - total_tokens: int
        - total_requests: int
        - error_count: int
    """
    records = read_costs(path)

    # Filter to month
    month_records = [
        r for r in records
        if r.get("ts", "").startswith(month)
    ]

    # Aggregates
    mtd_total = 0.0
    by_provider = defaultdict(float)
    by_model = defaultdict(float)
    by_batch = defaultdict(lambda: {
        "batch_id": "",
        "ts": "",
        "provider": "",
        "model": "",
        "cases": 0,
        "total_cost_usd": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "errors": 0,
    })

    total_tokens = 0
    total_requests = 0
    error_count = 0

    for record in month_records:
        cost = record.get("cost_usd", 0.0)
        provider = record.get("provider", "unknown")
        model = record.get("model", "unknown")
        batch_id = record.get("batch_id", "unknown")
        error = record.get("error")
        dry_run = record.get("dry_run", False)

        # Skip dry runs in totals
        if dry_run:
            continue

        # Totals
        mtd_total += cost
        by_provider[provider] += cost
        by_model[model] += cost

        # Batch aggregation
        batch = by_batch[batch_id]
        batch["batch_id"] = batch_id
        batch["provider"] = provider
        batch["model"] = model
        batch["cases"] += 1
        batch["total_cost_usd"] += cost

        if not batch["ts"] and record.get("ts"):
            batch["ts"] = record["ts"]

        # Tokens
        if record.get("prompt_tokens"):
            batch["prompt_tokens"] += record["prompt_tokens"]
            total_tokens += record["prompt_tokens"]
        if record.get("completion_tokens"):
            batch["completion_tokens"] += record["completion_tokens"]
            total_tokens += record["completion_tokens"]

        # Errors
        if error:
            batch["errors"] += 1
            error_count += 1
        else:
            total_requests += 1

    # Convert batches to list, sorted by timestamp
    runs = sorted(by_batch.values(), key=lambda x: x["ts"], reverse=True)

    return {
        "month": month,
        "mtd_total_usd": mtd_total,
        "by_provider": dict(by_provider),
        "by_model": dict(by_model),
        "by_batch": dict(by_batch),
        "runs": runs,
        "total_tokens": total_tokens,
        "total_requests": total_requests,
        "error_count": error_count,
    }


def write_monthly_report(
    month: str,
    data: Dict[str, Any],
    outdir: Optional[Path] = None
) -> Path:
    """
    Write monthly cost report to markdown.

    Args:
        month: Month in YYYY-MM format
        data: Aggregated data from aggregate_month()
        outdir: Output directory (default: docs/reports)

    Returns:
        Path to written report
    """
    report_dir = outdir or REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"llm_costs_{month}.md"

    # Generate report
    report = f"""# LLM Cost Report - {month}

**Generated**: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}

---

## Monthly Summary

| Metric | Value |
|--------|-------|
| **Month-to-Date Total** | ${data['mtd_total_usd']:.4f} |
| **Total Requests** | {data['total_requests']:,} |
| **Total Tokens** | {data['total_tokens']:,} |
| **Errors** | {data['error_count']} |

---

## Cost by Provider

| Provider | Total Cost |
|----------|------------|
"""

    # Provider breakdown
    for provider, cost in sorted(data['by_provider'].items(), key=lambda x: -x[1]):
        report += f"| {provider} | ${cost:.4f} |\n"

    if not data['by_provider']:
        report += "| *(no data)* | $0.00 |\n"

    report += "\n---\n\n## Cost by Model\n\n| Model | Total Cost |\n|-------|------------|\n"

    # Model breakdown
    for model, cost in sorted(data['by_model'].items(), key=lambda x: -x[1]):
        report += f"| {model} | ${cost:.4f} |\n"

    if not data['by_model']:
        report += "| *(no data)* | $0.00 |\n"

    report += "\n---\n\n## Recent Batch Runs (Last 10)\n\n"
    report += "| Batch ID | Date | Provider/Model | Cases | Cost | Tokens | Errors |\n"
    report += "|----------|------|----------------|-------|------|--------|--------|\n"

    # Recent batches (limit to 10)
    for run in data['runs'][:10]:
        ts = run.get("ts", "")
        date = ts[:10] if ts else "—"
        batch_id = run["batch_id"]
        provider_model = f"{run['provider']}/{run['model']}"
        cases = run["cases"]
        cost = run["total_cost_usd"]
        tokens = run["prompt_tokens"] + run["completion_tokens"]
        errors = run["errors"]

        report += f"| {batch_id} | {date} | {provider_model} | {cases} | ${cost:.4f} | {tokens:,} | {errors} |\n"

    if not data['runs']:
        report += "| *(no runs)* | — | — | — | $0.00 | — | — |\n"

    report += "\n---\n\n## Notes\n\n"
    report += "- **Ollama** (local models) have $0.00 cost but are still tracked for usage counts.\n"
    report += "- **Dry runs** are excluded from cost totals.\n"
    report += "- Token counts may be estimated when actual usage is unavailable.\n"
    report += f"- Cost data sourced from: `{COST_LOG_FILE}`\n"

    report += f"\n---\n\n*Generated by llm_costs.py*\n"

    # Write report
    with open(report_path, 'w') as f:
        f.write(report)

    return report_path


def get_mtd_total(month: Optional[str] = None) -> float:
    """
    Get month-to-date total cost.

    Args:
        month: Month in YYYY-MM format (default: current month)

    Returns:
        Total cost in USD
    """
    if not month:
        month = datetime.utcnow().strftime("%Y-%m")

    data = aggregate_month(month)
    return data["mtd_total_usd"]


def main():
    """CLI entry point for generating monthly reports."""
    import sys

    # Default to current month
    month = sys.argv[1] if len(sys.argv) > 1 else datetime.utcnow().strftime("%Y-%m")

    print(f"📊 Aggregating costs for {month}...")
    data = aggregate_month(month)

    print(f"💰 Month-to-date total: ${data['mtd_total_usd']:.4f}")
    print(f"   Requests: {data['total_requests']:,}")
    print(f"   Tokens: {data['total_tokens']:,}")
    print(f"   Errors: {data['error_count']}")

    print(f"\n📝 Writing monthly report...")
    report_path = write_monthly_report(month, data)

    print(f"✅ Report saved to: {report_path}")


if __name__ == "__main__":
    main()
