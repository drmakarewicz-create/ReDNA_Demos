# Agent Daemon Diagnosis & Fix

**Date**: 2025-10-10
**Issue**: Agent daemon running but producing zero jobs (`executed: 0, proposed: 0`)
**Status**: ✅ **RESOLVED**

---

## Root Cause

The agent daemon (`core/agent_daemon.py`) was **designed correctly** but was missing **job provider implementations**.

The daemon accepts three pluggable provider functions:
- `curiosity_provider` – generates exploration jobs based on gap analysis
- `refinement_provider` – generates jobs for conflict resolution
- `improvement_provider` – generates self-improvement analysis jobs

When invoked via CLI (`python -m ReDNACoreDemo.core.agent_daemon`), these providers were all set to `default_provider`, which returns empty lists:

```python
def default_provider(_: str, __: agents.AgentPolicy, ___: agents.AgentState) -> Sequence[Dict[str, Any]]:
    return []  # ← Always empty!
```

**Result**: No jobs were ever proposed or executed, even though the daemon loop itself was functioning perfectly.

---

## Fix Applied

### 1. Created `core/agent_providers.py`

A new module that bridges the daemon to ReDNA's existing infrastructure:

- **`curiosity_provider`**: Connects to `CuriosityEngine` v2 to generate high-priority exploration nudges
- **`refinement_provider`**: Scans user's refinement queue and conflict log for pending work
- **`improvement_provider`**: Checks telemetry volume and proposes self-improvement analysis when sufficient data exists

### 2. Wired providers into daemon's `main()` function

Updated `agent_daemon.py` line 453-460 to import and inject the real providers:

```python
from ReDNACoreDemo.core import agent_providers

daemon = AgentDaemon(
    interval_minutes=args.interval,
    curiosity_provider=agent_providers.curiosity_provider,
    refinement_provider=agent_providers.refinement_provider,
    improvement_provider=agent_providers.improvement_provider,
)
```

---

## Verification

### Before Fix
```bash
$ python3 -m ReDNACoreDemo.core.agent_daemon --user USER1 --once
Agent hc_USER1 run summary {'executed': 0, 'proposed': 0, 'failures': 0, 'pending_after': 0}
```

### After Fix
```bash
$ python3 -m ReDNACoreDemo.core.agent_daemon --user USER1 --once
[INFO] Curiosity provider generated 3 jobs for USER1
[INFO] Refinement provider generated 0 jobs for USER1
[INFO] Agent hc_USER1 run summary {'executed': 3, 'proposed': 0, 'failures': 0, 'pending_after': 4}
```

### DevX API Confirmation
```bash
$ curl http://localhost:8100/devx/api/agents/USER1 | jq '.state | {run_count, executed: .job_counts.nudge}'
{
  "run_count": 4,
  "executed": 4
}
```

### Telemetry Confirmation
```bash
$ cat data/telemetry/agents/job_completed.jsonl | wc -l
4
```

All acceptance criteria met:
- ✅ `--once` logs non-zero executed jobs
- ✅ DevX `/agents/{user_id}` shows non-zero counts
- ✅ Telemetry files contain job completion events
- ✅ 🤖 Agents panel in DevX UI reflects active execution

---

## Architecture Notes

### Provider Pattern Design

The daemon uses a **provider pattern** for job generation, which allows:
- Testability: Tests inject mock providers (see `tests/test_agentic_hc_mvp.py`)
- Extensibility: New job sources can be added without modifying the daemon core
- Separation of concerns: Daemon handles scheduling/execution; providers handle domain logic

### Job Flow

1. **Inbox** → User-initiated or API-pushed jobs
2. **Curiosity** → Gap-driven exploration from `CuriosityEngine`
3. **Refinement** → Conflict resolution & trait refinement queue
4. **Improvement** → Self-improvement analysis when telemetry threshold met

### Autonomy Gating

Jobs have `required_autonomy` levels:
- `propose` (0): Must be approved manually
- `semi` (1): Executes if policy ≥ semi (default)
- `auto` (2): Executes only if policy = auto

Current USER1 policy is `semi`, so:
- Curiosity nudges (`semi`) → execute ✅
- Conflict resolution (`auto`) → would be proposed (awaiting manual) if policy were `propose`

---

## Files Modified

| File | Change |
|------|--------|
| `core/agent_providers.py` | ✨ **NEW** – Provider implementations |
| `core/agent_daemon.py` | 🔧 Updated `main()` to wire providers (lines 453-460) |

---

## Next Steps (Optional Enhancements)

1. **Improvement Provider Tuning**: Currently requires 5 telemetry events in 7 days; adjust threshold in `agent_providers.py` based on usage patterns

2. **Refinement Provider Enrichment**: Could connect to trait depth analysis or RR distribution anomalies

3. **Provider Logging**: Add more granular logging for provider decisions (e.g., "Skipped curiosity: no high-priority gaps")

4. **CLI Overrides**: Add flags like `--no-curiosity` or `--providers=curiosity,refinement` for selective execution

---

## Contact

For questions about this fix or the agentic HC architecture, see:
- `docs/AGENTIC_HC_MVP_PHASE5A.md`
- `tests/test_agentic_hc_mvp.py`
- DevX 🤖 Agents panel: http://localhost:3002

**Fix verified by**: Claude Code (Codex build)
**Handoff complete**: Ready for phase 5.B agent memory/learning integration
