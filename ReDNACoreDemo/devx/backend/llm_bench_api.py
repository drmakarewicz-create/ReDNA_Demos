"""
LLM Benchmark API
=================

DevX API endpoints for Alt-LLM benchmarking system.

Phase 1: Read-only access to backlog & reports (no execution).
"""

import json
import logging
import os
import re
import datetime as dt
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter()

REPORT_PATTERNS = (
    "altllm_batch_*.md",
    "local_*.md",
    "llm_costs_*.md",
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-\.]+\.md$")

# Paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKLOG_MD = PROJECT_ROOT / "docs" / "AltLLM_Benchmark_Backlog.md"
BACKLOG_JSON = PROJECT_ROOT / "tests" / "llm_benchmarks" / "backlog_seed.json"
REPORTS_DIR = PROJECT_ROOT / "docs" / "reports"


def _find_reports_dir() -> Path:
    """
    Walk up from this file until we find a 'docs/reports' folder.
    Avoids CWD and sandbox issues.
    """
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "docs" / "reports"
        if candidate.is_dir():
            return candidate
    env = os.getenv("REDNA_REPORTS_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    return Path.cwd() / "docs" / "reports"


def parse_backlog_markdown() -> List[Dict[str, Any]]:
    """
    Parse docs/AltLLM_Benchmark_Backlog.md table into structured rows.

    Returns list of dicts with keys:
        id, category, user_message, expected_trait_ids, expected_values,
        notes, risk, score_local, score_alt, last_run, model, cost_usd
    """
    if not BACKLOG_MD.exists():
        logger.warning(f"Backlog markdown not found: {BACKLOG_MD}")
        return []

    content = BACKLOG_MD.read_text(encoding="utf-8")

    # Find the table section
    # Table starts after "## Benchmark Cases" and before next "###" or "---"
    table_section_match = re.search(
        r"## Benchmark Cases\s*\n(.*?)(\n###|\n---|\Z)",
        content,
        re.DOTALL
    )

    if not table_section_match:
        logger.warning("Could not find Benchmark Cases table in markdown")
        return []

    table_text = table_section_match.group(1)

    # Parse markdown table rows
    rows = []
    lines = table_text.strip().split("\n")

    # Skip header and separator rows
    data_lines = [l for l in lines if l.strip() and not l.strip().startswith("|--")]
    if len(data_lines) < 2:
        return []

    # Skip header row
    data_lines = data_lines[2:]

    for line in data_lines:
        # Split by pipe and strip whitespace
        cols = [c.strip() for c in line.split("|")]

        # Filter out empty first/last elements from leading/trailing pipes
        cols = [c for c in cols if c]

        if len(cols) < 11:
            continue  # Skip malformed rows

        row = {
            "id": cols[0].strip("*"),  # Remove markdown bold markers
            "category": cols[1],
            "user_message": cols[2].strip('"'),
            "expected_trait_ids": [t.strip() for t in cols[3].split(",") if t.strip() != "(none)" and t.strip()],
            "expected_values": [v.strip() for v in cols[4].split(",") if v.strip() and v.strip() != "-"],
            "notes": cols[5],
            "risk": cols[6],
            "score_local": cols[7],
            "score_alt": cols[8] if cols[8] != "-" else None,
            "last_run": cols[9] if cols[9] != "-" else None,
            "model": cols[10] if cols[10] != "-" else None,
            "cost_usd": float(cols[11]) if len(cols) > 11 and cols[11] != "-" else None,
        }
        rows.append(row)

    return rows


def load_backlog_json() -> List[Dict[str, Any]]:
    """Load backlog from JSON seed file."""
    if not BACKLOG_JSON.exists():
        logger.warning(f"Backlog JSON not found: {BACKLOG_JSON}")
        return []

    with open(BACKLOG_JSON, "r") as f:
        return json.load(f)


@router.get("/llm-bench/backlog")
async def get_backlog(
    category: Optional[str] = Query(None, description="Filter by category"),
    risk: Optional[str] = Query(None, description="Filter by risk level (low/med/high)"),
    limit: int = Query(100, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    GET /devx/api/llm-bench/backlog

    Returns structured backlog of LLM benchmark test cases.

    Query params:
        - category: Filter by category (direct_fact, behavior, etc.)
        - risk: Filter by risk level (low, med, high)
        - limit: Max results (default 100)
        - offset: Pagination offset (default 0)
    """
    try:
        # Try JSON first (faster), fall back to markdown
        cases = load_backlog_json()
        if not cases:
            cases = parse_backlog_markdown()

        # Apply filters
        if category:
            cases = [c for c in cases if c.get("category") == category]

        if risk:
            cases = [c for c in cases if c.get("risk") == risk]

        # Pagination
        total = len(cases)
        cases = cases[offset:offset + limit]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "cases": cases
        }

    except Exception as e:
        logger.error(f"Error loading backlog: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load backlog: {str(e)}")


@router.get("/llm-bench/reports")
async def list_reports(limit: int = 100) -> list[dict]:
    """
    GET /devx/api/llm-bench/reports

    Returns list of recent benchmark reports with lightweight metadata.
    """
    reports_dir = _find_reports_dir()
    paths: list[Path] = []
    for pat in REPORT_PATTERNS:
        paths.extend(
            sorted(
                reports_dir.glob(pat),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        )
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in paths:
        if p.name in seen:
            continue
        seen.add(p.name)
        uniq.append(p)
    out: list[dict] = []
    for p in uniq[:limit]:
        name = p.name
        mtime = dt.datetime.utcfromtimestamp(p.stat().st_mtime).isoformat() + "Z"
        provider = (
            "ollama"
            if "local" in name
            else (
                "openai"
                if "openai" in name
                else ("anthropic" if "anthropic" in name else None)
            )
        )
        out.append(
            {
                "filename": name,
                "path": str(p),
                "modified": mtime,
                "provider": provider,
            }
        )
    return out


@router.get("/llm-bench/report/{filename}")
async def get_report_content(filename: str):
    """
    GET /devx/api/llm-bench/report/{filename}

    Returns full markdown content of a specific report.

    Path params:
        - filename: Report filename (e.g., altllm_batch_20251016_195530.md)
    """
    if not SAFE_NAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid report filename")
    reports_dir = _find_reports_dir()
    path = reports_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return Response(path.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/llm-bench/status")
async def get_model_status():
    """
    GET /devx/api/llm-bench/status

    Returns current UCNRR LLM provider and model configuration.
    Read-only endpoint for Phase 1 - displays current model status.
    """
    import os

    provider = os.getenv("UCNRR_LLM_PROVIDER", "ollama")
    model = os.getenv("UCNRR_LLM_MODEL", "llama3.1:8b")

    # Determine source (env, config, or fallback)
    source = "env"
    if not os.getenv("UCNRR_LLM_PROVIDER"):
        source = "fallback"

    return {
        "provider": provider.lower(),
        "model": model,
        "source": source
    }


@router.get("/llm-bench/costs")
async def get_monthly_costs(
    month: str = Query(default=None, regex=r"^\d{4}-\d{2}$", description="Month in YYYY-MM format (default: current month)")
):
    """
    GET /devx/api/llm-bench/costs?month=YYYY-MM

    Returns monthly cost aggregates from ~/.redna/llm_costs.jsonl.
    Read-only endpoint for Phase 1.5 - displays cost tracking data.
    """
    import os
    import sys
    from pathlib import Path
    from datetime import datetime

    # Add scripts directory to path
    project_root = Path(__file__).parent.parent.parent.parent
    scripts_dir = project_root / "scripts"
    sys.path.insert(0, str(scripts_dir))

    try:
        from llm_costs import aggregate_month
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Cost aggregator not available (llm_costs.py not found)"
        )

    # Default to current month if not specified
    if not month:
        month = datetime.utcnow().strftime("%Y-%m")

    # Validate month format (already done by regex in Query, but double-check)
    if not month or len(month) != 7:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

    try:
        # Aggregate costs for the month
        data = aggregate_month(month)

        # Include monthly cap if set
        monthly_cap_usd = os.getenv("ALTLLM_MONTHLY_CAP_USD")
        if monthly_cap_usd:
            try:
                data["monthly_cap_usd"] = float(monthly_cap_usd)
            except ValueError:
                pass

        return data

    except Exception as e:
        logger.error(f"Error aggregating costs for {month}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to aggregate costs: {str(e)}"
        )


# Phase 2: Local Execution Endpoints
# ============================================================================

ALLOWED_LOCAL_MODELS = ["phi3:mini", "llama3.1:8b", "mistral:7b", "gemma2:9b"]
LOGS_DIR = Path("/tmp")


@router.post("/llm-bench/run-local")
async def run_local_benchmark(
    model: str = Query(default="phi3:mini", description="Ollama model to use"),
    limit: int = Query(default=10, ge=1, le=50, description="Number of test cases"),
    dry_run: bool = Query(default=True, description="Dry run mode (no actual execution)")
):
    """
    POST /devx/api/llm-bench/run-local

    Execute a local Ollama benchmark batch via run_alt_llm_benchmark.py.
    Phase 2: Local execution only (free, no API keys required).

    Safety:
    - Ollama provider only (local models, zero cost)
    - Model must be in allow-list
    - Auto-reverts config after run
    - Cost logged as $0.00
    """
    import asyncio
    import subprocess
    import shlex
    from datetime import datetime

    # Validate model
    if model not in ALLOWED_LOCAL_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model}' not allowed. Must be one of: {ALLOWED_LOCAL_MODELS}"
        )

    # Generate batch ID
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
    batch_id = f"localdevx_{timestamp}"

    # Build command
    runner_script = PROJECT_ROOT / "scripts" / "run_alt_llm_benchmark.py"
    if not runner_script.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Benchmark runner not found: {runner_script}"
        )

    cmd_parts = [
        "python",
        str(runner_script),
        "--provider", "ollama",
        "--model", model,
        "--limit", str(limit),
        "--max_cost_usd", "0",
        "--batch-name", batch_id,
    ]

    if not dry_run:
        # Actual run (no --dry_run flag)
        pass
    else:
        # Dry run mode
        cmd_parts.append("--dry_run")

    # Log file
    log_file = LOGS_DIR / f"llm_bench_{timestamp}.log"

    try:
        # Execute subprocess
        logger.info(f"Starting local benchmark: {' '.join(cmd_parts)}")

        with open(log_file, "w") as log_fp:
            process = subprocess.Popen(
                cmd_parts,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                cwd=PROJECT_ROOT,
                text=True
            )

            # Wait for completion (with timeout)
            try:
                return_code = process.wait(timeout=600)  # 10 min max
            except subprocess.TimeoutExpired:
                process.kill()
                raise HTTPException(
                    status_code=500,
                    detail="Benchmark run timed out after 10 minutes"
                )

        # Check return code
        if return_code != 0:
            # Read error from log
            error_log = log_file.read_text() if log_file.exists() else "Unknown error"
            raise HTTPException(
                status_code=500,
                detail=f"Benchmark run failed (exit code {return_code}): {error_log[-500:]}"
            )

        # Find latest report
        reports = sorted(REPORTS_DIR.glob(f"altllm_batch_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        latest_report = reports[0] if reports else None

        response = {
            "status": "ok",
            "batch_id": batch_id,
            "model": model,
            "limit": limit,
            "dry_run": dry_run,
            "cost_usd": 0.0,
            "log_file": str(log_file),
        }

        if latest_report:
            response["report_path"] = str(latest_report.relative_to(PROJECT_ROOT))

        logger.info(f"Local benchmark completed: {batch_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running local benchmark: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run benchmark: {str(e)}"
        )


@router.get("/llm-bench/progress")
async def get_benchmark_progress():
    """
    GET /devx/api/llm-bench/progress

    Returns the latest benchmark run log (last 50 lines).
    Useful for showing live progress in the UI.
    """
    # Find latest log file
    log_files = sorted(LOGS_DIR.glob("llm_bench_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not log_files:
        return {
            "status": "no_logs",
            "message": "No benchmark logs found",
            "lines": []
        }

    latest_log = log_files[0]

    try:
        # Read last 50 lines
        with open(latest_log, "r") as f:
            lines = f.readlines()
            tail_lines = lines[-50:] if len(lines) > 50 else lines

        return {
            "status": "ok",
            "log_file": str(latest_log),
            "lines": [line.rstrip() for line in tail_lines],
            "total_lines": len(lines)
        }

    except Exception as e:
        logger.error(f"Error reading progress log: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read progress: {str(e)}"
        )


# Phase 3: Guarded Paid Execution
# ============================================================================

# Cost rate table (USD per 1M tokens)
COST_RATES = {
    "openai": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
    },
    "anthropic": {
        "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    },
    "ollama": {
        "*": {"input": 0.0, "output": 0.0}  # All Ollama models are free
    }
}

# Audit log path
AUDIT_LOG = Path.home() / ".redna" / "audit_llm_bench.jsonl"
COST_LOG = Path.home() / ".redna" / "llm_costs.jsonl"


def get_monthly_cap() -> Optional[float]:
    """Get monthly cap from environment variable."""
    cap_str = os.getenv("ALTLLM_MONTHLY_CAP_USD")
    if cap_str:
        try:
            return float(cap_str)
        except ValueError:
            logger.warning(f"Invalid ALTLLM_MONTHLY_CAP_USD: {cap_str}")
    return None


def get_mtd_total() -> float:
    """Calculate month-to-date total spend from cost log."""
    if not COST_LOG.exists():
        return 0.0

    current_month = datetime.utcnow().strftime("%Y-%m")
    total = 0.0

    try:
        with open(COST_LOG, "r") as f:
            for line in f:
                entry = json.loads(line.strip())
                if entry.get("month") == current_month:
                    total += entry.get("cost_usd", 0.0)
    except Exception as e:
        logger.error(f"Error reading cost log: {e}")

    return total


def estimate_cost(provider: str, model: str, limit: int) -> float:
    """
    Estimate cost for a benchmark run.

    Uses heuristics:
    - Average 100 tokens input per case
    - Average 200 tokens output per case
    """
    if provider not in COST_RATES:
        return 0.0

    rates = COST_RATES[provider].get(model) or COST_RATES[provider].get("*", {"input": 0.0, "output": 0.0})

    # Heuristic: 100 tokens in, 200 tokens out per case
    input_tokens = limit * 100
    output_tokens = limit * 200

    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]

    return input_cost + output_cost


def check_api_key(provider: str) -> bool:
    """Check if API key is present for the provider (without logging it)."""
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    elif provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    return True  # Ollama doesn't need API key


def write_audit_log(entry: Dict[str, Any]):
    """Append audit log entry to ~/.redna/audit_llm_bench.jsonl"""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


@router.get("/llm-bench/cost-precheck")
async def cost_precheck(
    provider: str = Query(default="ollama"),
    model: str = Query(default="phi3:mini"),
    limit: int = Query(default=10, ge=1, le=50)
):
    """
    GET /devx/api/llm-bench/cost-precheck

    Estimate cost for a benchmark run and check monthly budget.

    Returns:
        - est_cost_usd: Estimated cost for this run
        - mtd_total_usd: Month-to-date total spend
        - monthly_cap_usd: Monthly cap (if set)
        - remaining_usd: Remaining budget (if cap is set)
        - can_run: Whether the run would exceed cap
    """
    est_cost = estimate_cost(provider, model, limit)
    mtd_total = get_mtd_total()
    monthly_cap = get_monthly_cap()

    response = {
        "est_cost_usd": round(est_cost, 4),
        "mtd_total_usd": round(mtd_total, 4),
        "monthly_cap_usd": monthly_cap,
    }

    if monthly_cap is not None:
        remaining = monthly_cap - mtd_total
        can_run = (est_cost <= remaining)
        response["remaining_usd"] = round(remaining, 4)
        response["can_run"] = can_run
    else:
        response["remaining_usd"] = None
        response["can_run"] = True  # No cap set

    return response


@router.post("/llm-bench/run")
async def run_benchmark_paid(
    request: Request,
    provider: Literal["ollama", "openai", "anthropic"] = Query(default="ollama"),
    model: str = Query(default="phi3:mini"),
    limit: int = Query(default=10, ge=1, le=50),
    run: bool = Query(default=False),
    allow_paid: bool = Query(default=False),
    ack_paid: Optional[str] = Query(default=None),
    max_cost_usd: float = Query(default=0.0),
    batch_name: Optional[str] = Query(default=None),
    reason: Optional[str] = Query(default=None),
):
    """
    POST /devx/api/llm-bench/run

    Execute a benchmark batch with strict safety checks for paid runs.

    Phase 3: Guarded paid execution (OpenAI/Anthropic) with:
    - Double confirmation required
    - Monthly cap enforcement
    - Per-run budget cap
    - Auto-revert guarantee
    - Audit logging

    Safety gates for paid providers:
    - run must be True
    - allow_paid must be True
    - ack_paid must be exactly "I understand costs"
    - max_cost_usd must be > 0
    - API key must be present
    - Monthly cap must not be exceeded
    """
    import subprocess
    import shlex
    from datetime import datetime

    # Safety checks for paid providers
    if provider in ["openai", "anthropic"]:
        # Check all required flags
        if not run:
            raise HTTPException(
                status_code=400,
                detail="Paid runs require run=true (no dry-run for paid providers)"
            )

        if not allow_paid:
            raise HTTPException(
                status_code=403,
                detail="Paid runs require allow_paid=true"
            )

        if ack_paid != "I understand costs":
            raise HTTPException(
                status_code=403,
                detail='Paid runs require ack_paid="I understand costs" (exact match)'
            )

        if max_cost_usd <= 0:
            raise HTTPException(
                status_code=400,
                detail="Paid runs require max_cost_usd > 0"
            )

        # Check API key presence (without logging it)
        if not check_api_key(provider):
            raise HTTPException(
                status_code=403,
                detail=f"API key for {provider} not found in environment"
            )

        # Check monthly cap
        monthly_cap = get_monthly_cap()
        if monthly_cap is not None:
            mtd_total = get_mtd_total()
            est_cost = estimate_cost(provider, model, limit)

            if (mtd_total + est_cost) > monthly_cap:
                raise HTTPException(
                    status_code=403,
                    detail=f"Monthly cap would be exceeded: ${mtd_total:.4f} + ${est_cost:.4f} > ${monthly_cap:.2f}"
                )

    # Generate batch ID
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
    if not batch_name:
        prefix = "paid" if provider in ["openai", "anthropic"] else "local"
        batch_name = f"{prefix}_{timestamp}"

    # Build command
    runner_script = PROJECT_ROOT / "scripts" / "run_alt_llm_benchmark.py"
    if not runner_script.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Benchmark runner not found: {runner_script}"
        )

    cmd_parts = [
        "python",
        str(runner_script),
        "--provider", provider,
        "--model", model,
        "--limit", str(limit),
        "--max_cost_usd", str(max_cost_usd),
        "--batch-name", batch_name,
    ]

    # Add paid flags for non-Ollama
    if provider in ["openai", "anthropic"]:
        cmd_parts.extend([
            "--allow-paid",
            "--ack-paid", "I understand costs",
            "--use-switcher",  # Auto-revert
        ])

    # Only add --dry_run flag if NOT running
    # (actual runs have no flag, they just execute)
    if not run:
        cmd_parts.append("--dry_run")

    # Log file
    log_file = LOGS_DIR / f"llm_bench_{timestamp}.log"

    try:
        # Execute subprocess
        logger.info(f"Starting benchmark: {' '.join(cmd_parts)}")

        with open(log_file, "w") as log_fp:
            process = subprocess.Popen(
                cmd_parts,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                cwd=PROJECT_ROOT,
                text=True
            )

            # Wait for completion (with timeout)
            try:
                return_code = process.wait(timeout=600)  # 10 min max
            except subprocess.TimeoutExpired:
                process.kill()
                raise HTTPException(
                    status_code=500,
                    detail="Benchmark run timed out after 10 minutes"
                )

        # Check return code
        if return_code != 0:
            error_log = log_file.read_text() if log_file.exists() else "Unknown error"

            # Write audit log for failure
            audit_entry = {
                "ts": datetime.utcnow().isoformat(),
                "user": "devx",  # TODO: get from auth
                "provider": provider,
                "model": model,
                "limit": limit,
                "max_cost_usd": max_cost_usd,
                "reason": reason,
                "result": "error",
                "cost_est": estimate_cost(provider, model, limit),
                "batch_id": batch_name,
                "error": error_log[-500:]
            }
            write_audit_log(audit_entry)

            raise HTTPException(
                status_code=500,
                detail=f"Benchmark run failed (exit code {return_code}): {error_log[-500:]}"
            )

        # Find latest report
        reports = sorted(REPORTS_DIR.glob(f"altllm_batch_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        latest_report = reports[0] if reports else None

        # Get actual cost from cost log (most recent entry)
        actual_cost = estimate_cost(provider, model, limit)  # Fallback to estimate
        if COST_LOG.exists():
            try:
                with open(COST_LOG, "r") as f:
                    lines = f.readlines()
                    if lines:
                        last_entry = json.loads(lines[-1].strip())
                        if last_entry.get("batch_id") == batch_name:
                            actual_cost = last_entry.get("cost_usd", actual_cost)
            except Exception:
                pass

        response = {
            "status": "ok",
            "provider": provider,
            "model": model,
            "batch_id": batch_name,
            "limit": limit,
            "cost_usd": round(actual_cost, 4),
            "log_file": str(log_file),
        }

        if latest_report:
            response["report_path"] = str(latest_report.relative_to(PROJECT_ROOT))

        # Write audit log for success
        audit_entry = {
            "ts": datetime.utcnow().isoformat(),
            "user": "devx",  # TODO: get from auth
            "provider": provider,
            "model": model,
            "limit": limit,
            "max_cost_usd": max_cost_usd,
            "reason": reason,
            "result": "ok",
            "cost_est": estimate_cost(provider, model, limit),
            "cost_actual": actual_cost,
            "batch_id": batch_name,
            "report": str(latest_report.relative_to(PROJECT_ROOT)) if latest_report else None
        }
        write_audit_log(audit_entry)

        logger.info(f"Benchmark completed: {batch_name}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running benchmark: {e}")

        # Write audit log for exception
        audit_entry = {
            "ts": datetime.utcnow().isoformat(),
            "user": "devx",
            "provider": provider,
            "model": model,
            "limit": limit,
            "max_cost_usd": max_cost_usd,
            "reason": reason,
            "result": "error",
            "cost_est": estimate_cost(provider, model, limit),
            "batch_id": batch_name,
            "error": str(e)
        }
        write_audit_log(audit_entry)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to run benchmark: {str(e)}"
        )


@router.get("/metrics/roundtrip")
async def get_roundtrip_metrics():
    """
    GET /devx/api/metrics/roundtrip

    Returns hop timing metrics for the ingest pipeline roundtrip.
    Wrapper over Core /core/api/metrics, extracting hop_ms.* fields.

    Returns:
        - window_seconds: Rolling window duration
        - ingest: Request and error counts
        - hop_ms: Timing breakdown with p50/p95 for each hop
          - preprocess: Canonicalization, validation, storage
          - ucnrr: UCNRR resolver call
          - resolve: Inference + second resolve pass
          - total: Complete end-to-end roundtrip
    """
    import os
    import httpx

    core_base = os.getenv("CORE_BASE", "http://127.0.0.1:8004")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{core_base}/core/api/metrics")
            resp.raise_for_status()
            core_metrics = resp.json()

        # Extract hop timing stats from Core metrics
        timers = core_metrics.get("timers", {})
        counters = core_metrics.get("counters", {})

        # Build hop breakdown
        hop_ms = {}
        for hop_name in ["preprocess", "ucnrr", "resolve", "total"]:
            metric_key = f"hop_ms.{hop_name}"
            stats = timers.get(metric_key, {})
            if stats.get("count", 0) > 0:
                hop_ms[hop_name] = {
                    "count": stats.get("count", 0),
                    "p50": round(stats.get("p50", 0), 1),
                    "p95": round(stats.get("p95", 0), 1),
                    "p99": round(stats.get("p99", 0), 1),
                    "mean": round(stats.get("mean", 0), 1),
                }
            else:
                hop_ms[hop_name] = None

        # Extract ingest stats
        ingest_requests = counters.get("ingest.requests", 0)
        ingest_errors = counters.get("ingest.errors", 0)

        # Extract rolling window info if available
        rolling = core_metrics.get("rolling_window", {})
        window_seconds = rolling.get("window_seconds", 300)

        return {
            "ok": True,
            "window_seconds": window_seconds,
            "ingest": {
                "requests": ingest_requests,
                "errors": ingest_errors,
            },
            "hop_ms": hop_ms,
            "timestamp": core_metrics.get("timestamp"),
        }

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch Core metrics: {e}")
        raise HTTPException(
            status_code=503,
            detail="Core metrics endpoint unavailable"
        )
    except Exception as e:
        logger.error(f"Error fetching roundtrip metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch roundtrip metrics: {str(e)}"
        )
