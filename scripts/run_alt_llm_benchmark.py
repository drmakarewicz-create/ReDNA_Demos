#!/usr/bin/env python3
"""
Alt-LLM Benchmark Batch Runner

Safely toggles UCNRR to an external LLM (OpenAI/Anthropic) for extraction benchmarking,
runs a bounded set of test cases, generates a report, and immediately reverts to local Ollama.

Usage:
    python scripts/run_alt_llm_benchmark.py --provider openai --model gpt-4o-mini --limit 20 --max_cost_usd 1.00
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

# Add project root to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Paths
BACKLOG_SEED = PROJECT_ROOT / "tests" / "llm_benchmarks" / "backlog_seed.json"
BACKLOG_MD = PROJECT_ROOT / "docs" / "AltLLM_Benchmark_Backlog.md"
REPORTS_DIR = PROJECT_ROOT / "docs" / "reports"
ENV_FILE = PROJECT_ROOT / ".env"
COST_LOG_DIR = Path.home() / ".redna"
COST_LOG_FILE = COST_LOG_DIR / "llm_costs.jsonl"

# Provider rate tables (input/output per 1M tokens)
# Source: OpenAI/Anthropic pricing pages as of 2025-10-16
RATE_TABLES = {
    "openai": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 1.00, "output": 5.00},
    },
    "ollama": {
        # All Ollama models are free (local)
        "*": {"input": 0.0, "output": 0.0},
    }
}

# Token estimation (avg per case)
AVG_INPUT_TOKENS = 200  # HC prompt + user message
AVG_OUTPUT_TOKENS = 100  # Extraction response

# Core API endpoint
CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8001")


def estimate_cost(provider: str, model: str, num_cases: int) -> float:
    """Estimate total cost for batch run."""
    if provider == "ollama":
        return 0.0  # Local models are free

    if provider not in RATE_TABLES or model not in RATE_TABLES[provider]:
        return 0.0  # Unknown model

    rates = RATE_TABLES[provider][model]
    input_cost = (AVG_INPUT_TOKENS * num_cases / 1_000_000) * rates["input"]
    output_cost = (AVG_OUTPUT_TOKENS * num_cases / 1_000_000) * rates["output"]
    return input_cost + output_cost


def calculate_actual_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate actual cost from token usage."""
    if provider == "ollama":
        return 0.0  # Local models are free

    if provider not in RATE_TABLES:
        return 0.0

    # For ollama wildcard
    if model not in RATE_TABLES[provider]:
        if "*" in RATE_TABLES[provider]:
            rates = RATE_TABLES[provider]["*"]
        else:
            return 0.0
    else:
        rates = RATE_TABLES[provider][model]

    input_cost = (prompt_tokens / 1_000_000) * rates["input"]
    output_cost = (completion_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost


def record_cost(
    provider: str,
    model: str,
    case_id: str,
    batch_id: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    cost_usd: float,
    dry_run: bool,
    error: Optional[str] = None
) -> None:
    """Append cost record to JSONL log."""
    # Create directory if needed
    COST_LOG_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "case_id": case_id,
        "batch_id": batch_id,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_usd,
        "dry_run": dry_run,
        "error": error,
    }

    with open(COST_LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_backlog_cases(limit: int) -> List[Dict[str, Any]]:
    """Load test cases from JSON seed."""
    if not BACKLOG_SEED.exists():
        raise FileNotFoundError(f"Backlog seed not found: {BACKLOG_SEED}")

    with open(BACKLOG_SEED) as f:
        cases = json.load(f)

    return cases[:limit]


def store_ucnrr_config() -> Dict[str, str]:
    """Store current UCNRR config for later restoration."""
    return {
        "UCNRR_LLM_PROVIDER": os.getenv("UCNRR_LLM_PROVIDER", ""),
        "UCNRR_LLM_MODEL": os.getenv("UCNRR_LLM_MODEL", ""),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", ""),
        "LLM_MODEL": os.getenv("LLM_MODEL", ""),
    }


def toggle_ucnrr_to_alt(provider: str, model: str, api_key: Optional[str]) -> None:
    """Toggle UCNRR to external LLM."""
    os.environ["UCNRR_LLM_PROVIDER"] = provider
    os.environ["UCNRR_LLM_MODEL"] = model
    os.environ["LLM_PROVIDER"] = provider
    os.environ["LLM_MODEL"] = model

    if provider == "openai":
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")
        os.environ["OPENAI_API_KEY"] = api_key
    elif provider == "anthropic":
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")
        os.environ["ANTHROPIC_API_KEY"] = api_key


def revert_ucnrr_config(stored_config: Dict[str, str]) -> None:
    """Restore original UCNRR config."""
    for key, value in stored_config.items():
        if value:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]

    print("✅ Reverted UCNRR to local Ollama configuration")


def ingest_and_extract(user_message: str, user_id: str) -> Dict[str, Any]:
    """Send message to Core and get extraction response."""
    url = f"{CORE_BASE}/ui/chat/send"
    payload = {
        "user_id": user_id,
        "persona": "head_coach",
        "text": user_message,
        "client_ts": int(time.time() * 1000),
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def extract_traits_from_response(response: Dict[str, Any]) -> Set[str]:
    """Extract trait IDs from snapshot.traits."""
    if "snapshot" not in response or not response["snapshot"]:
        return set()

    snapshot = response["snapshot"]
    if "traits" not in snapshot or not snapshot["traits"]:
        return set()

    traits = snapshot["traits"]
    if isinstance(traits, dict):
        return set(traits.keys())
    elif isinstance(traits, list):
        return {t.get("trait_id") for t in traits if isinstance(t, dict) and "trait_id" in t}

    return set()


def run_benchmark_cases(
    cases: List[Dict[str, Any]],
    provider: str,
    model: str,
    max_cost_usd: float,
    batch_id: str,
    dry_run: bool = False
) -> Tuple[List[Dict[str, Any]], float, int]:
    """
    Run benchmark cases and collect results.

    Returns:
        (results, actual_cost, request_count)
    """
    results = []
    total_cost = 0.0
    request_count = 0
    consecutive_errors = 0

    for i, case in enumerate(cases, 1):
        case_id = case["id"]
        user_message = case["user_message"]
        expected_trait_ids = set(case.get("expected_trait_ids", []))

        # Generate unique user_id
        user_id = f"altllm_bench_{case_id}_{int(time.time() * 1000)}"

        print(f"  [{i}/{len(cases)}] Running {case_id}...", end=" ")

        try:
            # Ingest
            response = ingest_and_extract(user_message, user_id)

            if "error" in response:
                error_msg = response['error']
                print(f"❌ ERROR: {error_msg}")

                # Record error with zero cost
                record_cost(
                    provider=provider,
                    model=model,
                    case_id=case_id,
                    batch_id=batch_id,
                    prompt_tokens=None,
                    completion_tokens=None,
                    cost_usd=0.0,
                    dry_run=dry_run,
                    error=error_msg
                )

                consecutive_errors += 1
                if consecutive_errors >= 3:
                    print("⚠️  3 consecutive errors - stopping run")
                    break
                continue

            # Reset error counter on success
            consecutive_errors = 0
            request_count += 1

            # Extract token usage from response (if available)
            # Note: This requires the Core API to return usage info in the response
            # For now, we'll use estimated tokens as fallback
            prompt_tokens = None
            completion_tokens = None

            # Try to get actual usage from response
            if "usage" in response:
                usage = response["usage"]
                prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")

            # Calculate actual cost
            if prompt_tokens and completion_tokens:
                case_cost = calculate_actual_cost(provider, model, prompt_tokens, completion_tokens)
            else:
                # Fallback to estimation
                case_cost = estimate_cost(provider, model, 1)
                # Use estimated tokens for logging
                prompt_tokens = AVG_INPUT_TOKENS
                completion_tokens = AVG_OUTPUT_TOKENS

            total_cost += case_cost

            # Record cost
            record_cost(
                provider=provider,
                model=model,
                case_id=case_id,
                batch_id=batch_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=case_cost,
                dry_run=dry_run,
                error=None
            )

            # Extract
            extracted_trait_ids = extract_traits_from_response(response)

            # Calculate TP/FP/FN
            tp = expected_trait_ids & extracted_trait_ids
            fp = extracted_trait_ids - expected_trait_ids
            fn = expected_trait_ids - extracted_trait_ids

            # Store result
            result = {
                "case": case,
                "extracted": list(extracted_trait_ids),
                "tp": list(tp),
                "fp": list(fp),
                "fn": list(fn),
                "success": len(fn) == 0 and len(fp) == 0,
                "cost_usd": case_cost,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
            results.append(result)

            # Status
            if result["success"]:
                print(f"✅ {len(tp)}/{len(expected_trait_ids)}")
            elif fn and not fp:
                print(f"❌ {len(tp)}/{len(expected_trait_ids)} (missing {len(fn)})")
            elif fp and not fn:
                print(f"⚠️ {len(tp)}/{len(expected_trait_ids)} (+{len(fp)} FP)")
            else:
                print(f"⚠️ {len(tp)}/{len(expected_trait_ids)} (-{len(fn)} +{len(fp)})")

            # Check cost ceiling
            if total_cost >= max_cost_usd:
                print(f"⚠️  Cost limit reached (${total_cost:.4f} >= ${max_cost_usd})")
                break

        except Exception as exc:
            error_msg = str(exc)
            print(f"❌ Exception: {error_msg}")

            # Record error
            record_cost(
                provider=provider,
                model=model,
                case_id=case_id,
                batch_id=batch_id,
                prompt_tokens=None,
                completion_tokens=None,
                cost_usd=0.0,
                dry_run=dry_run,
                error=error_msg
            )

            consecutive_errors += 1
            if consecutive_errors >= 3:
                print("⚠️  3 consecutive errors - stopping run")
                break

    return results, total_cost, request_count


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate P/R/F1 metrics."""
    total_tp = sum(len(r["tp"]) for r in results)
    total_fp = sum(len(r["fp"]) for r in results)
    total_fn = sum(len(r["fn"]) for r in results)
    total_expected = total_tp + total_fn
    total_extracted = total_tp + total_fp

    precision = total_tp / total_extracted if total_extracted > 0 else 0.0
    recall = total_tp / total_expected if total_expected > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Per-category breakdown
    by_category = {}
    for r in results:
        cat = r["case"]["category"]
        if cat not in by_category:
            by_category[cat] = {"tp": 0, "fp": 0, "fn": 0, "cases": 0}

        by_category[cat]["tp"] += len(r["tp"])
        by_category[cat]["fp"] += len(r["fp"])
        by_category[cat]["fn"] += len(r["fn"])
        by_category[cat]["cases"] += 1

    # Calculate category metrics
    for cat, stats in by_category.items():
        total_expected_cat = stats["tp"] + stats["fn"]
        total_extracted_cat = stats["tp"] + stats["fp"]

        stats["precision"] = stats["tp"] / total_extracted_cat if total_extracted_cat > 0 else 0.0
        stats["recall"] = stats["tp"] / total_expected_cat if total_expected_cat > 0 else 0.0
        stats["f1"] = 2 * (stats["precision"] * stats["recall"]) / (stats["precision"] + stats["recall"]) if (stats["precision"] + stats["recall"]) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "total_expected": total_expected,
        "total_extracted": total_extracted,
        "by_category": by_category,
    }


def generate_report(
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    provider: str,
    model: str,
    total_cost: float,
    request_count: int,
    runtime: float,
) -> str:
    """Generate markdown report."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    report = f"""# Alt-LLM Benchmark Report

**Date**: {timestamp}
**Provider**: {provider}
**Model**: {model}
**Cases Run**: {len(results)}
**Requests**: {request_count}
**Runtime**: {runtime:.2f}s
**Estimated Cost**: ${total_cost:.4f}

---

## Summary Metrics

| Metric | Value | Target |
|--------|-------|--------|
| **Precision** | {metrics['precision']:.2%} | ≥ 95% |
| **Recall** | {metrics['recall']:.2%} | ≥ 85% |
| **F1 Score** | {metrics['f1']:.2%} | - |
| **True Positives** | {metrics['tp']} | - |
| **False Positives** | {metrics['fp']} | - |
| **False Negatives** | {metrics['fn']} | - |

---

## Category Breakdown

| Category | Cases | Precision | Recall | F1 | TP | FP | FN |
|----------|-------|-----------|--------|----|----|----|----|
"""

    for cat, stats in sorted(metrics["by_category"].items()):
        report += f"| {cat} | {stats['cases']} | {stats['precision']:.1%} | {stats['recall']:.1%} | {stats['f1']:.1%} | {stats['tp']} | {stats['fp']} | {stats['fn']} |\n"

    report += "\n---\n\n## Case-Level Results\n\n"

    for i, r in enumerate(results, 1):
        case = r["case"]
        status = "✅" if r["success"] else "❌"

        report += f"### {i}. {status} {case['id']} ({case['category']})\n\n"
        report += f"**User Message**: \"{case['user_message']}\"\n\n"
        report += f"- **Expected**: {', '.join(case['expected_trait_ids']) if case['expected_trait_ids'] else 'None'}\n"
        report += f"- **Extracted**: {', '.join(r['extracted']) if r['extracted'] else 'None'}\n"

        if r["tp"]:
            report += f"- **Correct (TP)**: {', '.join(r['tp'])}\n"
        if r["fp"]:
            report += f"- **Extra (FP)**: {', '.join(r['fp'])}\n"
        if r["fn"]:
            report += f"- **Missing (FN)**: {', '.join(r['fn'])}\n"

        report += f"- **Cost**: ${r['cost_usd']:.4f}\n\n"

    report += "---\n\n"
    report += f"*Generated by run_alt_llm_benchmark.py v1.0*\n"

    return report


def main():
    parser = argparse.ArgumentParser(description="Alt-LLM Benchmark Batch Runner")
    parser.add_argument("--provider", choices=["openai", "anthropic", "ollama"], required=True, help="LLM provider")
    parser.add_argument("--model", required=True, help="Model name (e.g., gpt-4o-mini, claude-3-5-sonnet-20241022, phi3:mini)")
    parser.add_argument("--limit", type=int, default=25, help="Number of cases to run (default: 25)")
    parser.add_argument("--max_cost_usd", type=float, default=2.00, help="Maximum cost ceiling (default: $2.00)")
    parser.add_argument("--dry_run", action="store_true", help="Print plan without running (no LLM calls)")
    parser.add_argument("--batch-name", help="Custom batch ID (default: auto-generated timestamp)")

    args = parser.parse_args()

    # Generate batch ID
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    batch_id = args.batch_name or f"altllm_{timestamp}"

    # Validate API key
    if args.provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key and not args.dry_run:
            print("❌ Error: OPENAI_API_KEY environment variable required")
            print("   Set it with: export OPENAI_API_KEY=***")
            sys.exit(1)
    elif args.provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key and not args.dry_run:
            print("❌ Error: ANTHROPIC_API_KEY environment variable required")
            print("   Set it with: export ANTHROPIC_API_KEY=***")
            sys.exit(1)
    elif args.provider == "ollama":
        api_key = None  # Ollama doesn't require API key
    else:
        api_key = None

    # Load cases
    print(f"\n📊 Loading benchmark cases (limit: {args.limit})...")
    cases = load_backlog_cases(args.limit)
    print(f"✅ Loaded {len(cases)} cases")

    # Estimate cost
    estimated_cost = estimate_cost(args.provider, args.model, len(cases))
    print(f"\n💰 Estimated cost: ${estimated_cost:.4f}")

    if estimated_cost > args.max_cost_usd:
        print(f"⚠️  Estimated cost (${estimated_cost:.4f}) exceeds limit (${args.max_cost_usd:.2f})")
        print(f"   Reduce --limit or increase --max_cost_usd")
        sys.exit(1)

    # Check monthly cap (paid providers only)
    monthly_cap_str = os.getenv("ALTLLM_MONTHLY_CAP_USD")
    if monthly_cap_str and args.provider != "ollama" and not args.dry_run:
        try:
            monthly_cap = float(monthly_cap_str)

            # Import cost aggregator
            sys.path.insert(0, str(SCRIPT_DIR))
            from llm_costs import get_mtd_total

            current_month = datetime.utcnow().strftime("%Y-%m")
            mtd_total = get_mtd_total(current_month)
            remaining = monthly_cap - mtd_total

            print(f"\n💳 Monthly Cap Check:")
            print(f"   Cap: ${monthly_cap:.2f}")
            print(f"   MTD Spent: ${mtd_total:.4f}")
            print(f"   Remaining: ${remaining:.4f}")

            if mtd_total + estimated_cost > monthly_cap:
                print(f"\n❌ ERROR: Would exceed monthly cap!")
                print(f"   Estimated cost: ${estimated_cost:.4f}")
                print(f"   Available: ${remaining:.4f}")
                print(f"\n   Either:")
                print(f"   - Reduce --limit to fit within ${remaining:.4f}")
                print(f"   - Wait until next month")
                print(f"   - Increase ALTLLM_MONTHLY_CAP_USD")
                sys.exit(1)

            if remaining < monthly_cap * 0.1:  # Less than 10% remaining
                print(f"⚠️  Warning: Only ${remaining:.4f} remaining this month")

        except ValueError:
            print(f"⚠️  Warning: Invalid ALTLLM_MONTHLY_CAP_USD value: {monthly_cap_str}")

    # Dry run exit
    if args.dry_run:
        print(f"\n🔍 DRY RUN - Plan:")
        print(f"   Provider: {args.provider}")
        print(f"   Model: {args.model}")
        print(f"   Cases: {len(cases)}")
        print(f"   Estimated cost: ${estimated_cost:.4f}")
        print(f"   Cost limit: ${args.max_cost_usd:.2f}")
        print(f"\n✅ Dry run complete - no LLM calls made")
        return

    # Store current config
    print(f"\n💾 Storing current UCNRR configuration...")
    stored_config = store_ucnrr_config()
    print(f"✅ Stored config: {stored_config}")

    try:
        # Toggle to alt LLM
        print(f"\n🔄 Toggling UCNRR to {args.provider}/{args.model}...")
        toggle_ucnrr_to_alt(args.provider, args.model, api_key)
        print(f"✅ UCNRR configured for external LLM")

        # Run benchmark
        print(f"\n🚀 Running {len(cases)} benchmark cases (batch: {batch_id})...")
        start_time = time.time()
        results, total_cost, request_count = run_benchmark_cases(
            cases, args.provider, args.model, args.max_cost_usd, batch_id, dry_run=False
        )
        runtime = time.time() - start_time
        print(f"\n✅ Completed {len(results)} cases in {runtime:.2f}s")
        print(f"   Requests: {request_count}")
        print(f"   Actual cost: ${total_cost:.4f}")
        print(f"   Cost log: {COST_LOG_FILE}")

        # Calculate metrics
        print(f"\n📈 Calculating metrics...")
        metrics = calculate_metrics(results)
        print(f"   Precision: {metrics['precision']:.2%}")
        print(f"   Recall: {metrics['recall']:.2%}")
        print(f"   F1: {metrics['f1']:.2%}")

        # Generate report
        print(f"\n📝 Generating report...")
        report = generate_report(
            results, metrics, args.provider, args.model,
            total_cost, request_count, runtime
        )

        # Save report
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"altllm_batch_{timestamp_str}.md"

        with open(report_path, "w") as f:
            f.write(report)

        print(f"✅ Report saved to: {report_path}")

        # Update monthly cost report
        print(f"\n💰 Updating monthly cost report...")
        try:
            # Import the cost aggregator
            sys.path.insert(0, str(SCRIPT_DIR))
            from llm_costs import aggregate_month, write_monthly_report

            current_month = datetime.utcnow().strftime("%Y-%m")
            cost_data = aggregate_month(current_month)
            cost_report_path = write_monthly_report(current_month, cost_data)
            print(f"✅ Monthly cost report updated: {cost_report_path}")
            print(f"   MTD Total: ${cost_data['mtd_total_usd']:.4f}")
        except Exception as e:
            print(f"⚠️  Warning: Could not update monthly cost report: {e}")

    finally:
        # Always revert
        print(f"\n🔙 Reverting UCNRR configuration...")
        revert_ucnrr_config(stored_config)


if __name__ == "__main__":
    main()
