# Conflict Resolver Overview

The conflict resolver formalises how we arbitrate contradictory signals across the ReDNA stack.  Refinement stays greedy, but the **Use plane** requires calibrated evidence before traits flip.

## Flow

1. **Detection** – modules emit `Evidence` records (core, UCN/RR, coaches, sensors, user assertions).
2. **Assembly** – evidence is bundled into a `Conflict` and logged via `core/conflict/detectors.make_conflict`.
3. **Routing** – `ConflictResolver` consults `policy/conflict_rules.yaml` to pick a strategy:
   - `auto_merge` for low-severity trait disputes
   - `hierarchical_resolution` delegates to Head Coach via `conflict_bridge`
   - `policy_gate` denies policy/permission attempts without capabilities
   - `escalation_required` holds sensitive flips pending corroboration
4. **Storage & Learning** – the result is appended to `data/users/<user>/conflict_log.jsonl` and indexed in `data/system_logs/conflicts/INDEX.json`.  Nightly jobs (`core/conflict/run_jobs.py`) mine the ledger to adjust self-report trust.

## Weighting

Every piece of evidence receives a weight `w_eff = w0 * f_consistency * f_cost * f_time * f_context * f_anonymity`.

- Base priors: behavioral `1.00`, third-party `0.85`, document `0.80`, sensor `0.75`, model inference `0.70`, user assertion `0.40`.
- User assertions clamp to `[0.20, 0.70]` and defer to calibration scores per user/domain.
- Modifiers are derived from provenance metadata (`consistency`, `cost_risk`, `time_decay`, `context_match`, `anonymity`).

Numeric conflicts resolve via weighted means.  Categorical conflicts apply a log-odds update using the weight and a `support` signal supplied in provenance (`-1.0`..`1.0`).

## Hysteresis

`policy/conflict_rules.yaml` enforces:

```yaml
flips:
  sensitive_paths:
    - "BeliefValueDNA.*"
    - "HealthDNA.*"
  min_distinct_sources: 2
  min_signals: 5
```

Sensitive traits refuse to flip until corroborated by *at least two* distinct sources and *five* signals.  Without corroboration the conflict is escalated for manual review.

## Outcomes & Audit

An `Outcome` captures the resolver, resolved value, UCN, and rationale.  Every resolution is appended to the per-user ledger and the system index so DevX dashboards can render it quickly.

## Learning Loop

`core/conflict/learning.run_nightly_learning` tallies conflict outcomes to adjust self-report calibration (stored in `data/system/self_report_calibration.json`).  The DevX API exposes these metrics via `/conflicts/learning-stats`.

