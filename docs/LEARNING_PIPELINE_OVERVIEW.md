# Learning Pipeline Overview

**Last updated:** 2025-10-09  
**Owner:** DevX / Holistic Insights

---

## Purpose

Phase 2 of the Holistic Review Engine brings real computation to the previously stubbed batch flow. The goal is to provide a lightweight, idempotent summary of a user's vault so operators can spot low-RR problem areas without running the full Core stack.

---

## Data Flow

1. **Queue job** – DevX User Ops issues `POST /devx/api/users/batch/run-holistic` to register a job manifest in `data/devx_jobs/holistic/`.
2. **Process job** – `POST /devx/api/users/batch/run-holistic/process` iterates each user, reads the vault, computes metrics, and writes results.
3. **View results** – `GET /devx/api/holistic/get` returns the latest snapshot; `GET /devx/api/holistic/history` lists previous generations.
4. **Monitor** – The Holistic Summary tab visualises the snapshot (overall RR, domain RR, low-RR paths) and exposes history cards for quick diffs.

---

## Vault Inputs

For each user:

- `data/users/<user_id>/resolved.json` – container registry with per-path RR values.
- `data/users/<user_id>/evidence/` – evidence artefacts (counted only).
- `data/users/<user_id>/derived/` – derived files (counted only).

The processor does not mutate the vault; it only reads counts and RR values.

---

## Result Schema

`data/holistic/<user_id>.json` and history files (`data/holistic/history/<user_id>_<timestamp>.json`) follow this structure:

```json
{
  "user_id": "TEST",
  "generated_at": "2025-10-09T02:10:00Z",
  "counts": {
    "containers": 123,
    "evidence": 45,
    "derived": 12
  },
  "rr": {
    "overall_rr": 64.5,
    "by_domain": {
      "SkillDNA": 72.3,
      "ProfDNA": 61.2,
      "PsyDNA": 53.9
    }
  },
  "top_low_rr_paths": [
    {"path": "PsyDNA.PersonalityDNA.AgreeablenessDNA", "rr": 31.0},
    {"path": "SkillDNA.PresentationSkillDNA", "rr": 28.0}
  ],
  "notes": "Phase2 baseline"
}
```

- **Counts** – container, evidence, and derived file counts (basic telemetry).
- **RR metrics** – overall RR is the median of container RRs; domain RR values are per-domain averages.
- **Top low RR paths** – lowest five container paths to highlight areas needing review.
- **Notes** – free-form context, currently the job's reason or “Phase2 baseline”.

---

## Endpoint Summary

| Endpoint | Description |
|----------|-------------|
| `POST /devx/api/users/batch/run-holistic` | Queue a holistic job (manifest only). |
| `POST /devx/api/users/batch/run-holistic/process` | Execute the job, compute metrics, and persist results. |
| `GET /devx/api/holistic/get` | Fetch the latest snapshot for a user. |
| `GET /devx/api/holistic/history` | List recent snapshots with timestamps. |

All writes are atomic (`.tmp` → `rename`) and auto-create the necessary directories under `data/holistic/`.

---

## Safeguards

- Missing vaults or malformed JSON result in an error entry for that user but do not abort the job.
- History is append-only; the latest snapshot always reflects `data/holistic/<user>.json`.
- Results are small JSON payloads suitable for git diffing or downstream ingestion.

---

## Next Steps

Future phases can enrich the RR metrics with Core-derived signals or integrate directly with the learning dashboards. The current implementation intentionally keeps computation light so it can run on developer machines without the full Core stack.
