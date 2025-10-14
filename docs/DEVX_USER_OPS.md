# DevX Batch User Operations

**Last updated:** 2025-10-08  
**Owner:** DevX Platform Team

---

## Overview

The DevX “User Ops (Batch)” module provides a safe, repeatable workflow for multi-user maintenance tasks. The initial release focuses on user deletion with a reversible quarantine flow and capability revocation hooks. The architecture is intentionally extensible so future bulk actions (holistic reviews, RR recomputations, capability revocations) can reuse the same job manifest system.

---

## UI Walkthrough

1. **Select users**  
   - Open *DevX → User Ops*.  
   - Use the search bar and paginator to locate users.  
   - Select via per-row checkboxes or “select all” on the current page.  
   - Each row surfaces vault size, last updated timestamp, and (if applicable) quarantine status plus review deadline.

2. **Dry run**  
   - Click **Dry Run Delete** to preview impact.  
   - The panel lists bytes to quarantine, top-level vault folders, consent capability counts (or warnings if the service is offline), and whether an existing ticket already exists.

3. **Delete (Quarantine)**  
   - Click **Delete (Quarantine)** to open the confirmation modal.  
   - Provide a reason, choose a grace period (default 7 days), and type the confirmation string `DELETE <N> USERS`.  
   - Submission creates a batch job, revokes capabilities via Consent Service, writes tickets under `data/purge_requests/<user_id>/`, and atomically moves the vault to `data/quarantine/<timestamp>/<user_id>/`. Successful jobs appear in the job history dropdown with a job id (e.g., `job_20251008T154301Z_ab12cd`).

4. **Undo & Purge**  
   - Select a job from the dropdown to view live status.  
   - **Undo** checkboxes appear for users still in quarantine and within the grace period. Enter `UNDO <N> USERS` to restore vaults back to `data/users/…`.  
   - **Purge** checkboxes activate once the review window has expired. Enter `PURGE <N> USERS` to permanently remove the quarantined data and mark tickets as `purged`.

> ⚠️ All destructive actions require confirmation strings. Undo and purge options automatically refresh after each operation.

---

## Backend Flow

1. **Listing & summaries**  
   - `GET /devx/api/users/list` scans `data/users/` to build lightweight summaries.  
   - `GET /devx/api/users/summary` aggregates evidence/derived/container counts and vault size.

2. **Dry run**  
   - `POST /devx/api/users/batch/dry-run` computes bytes, top-level paths, and consent capability counts. Failures (missing vaults, offline consent) return per-user warnings without persisting anything.

3. **Delete (quarantine request)**  
   - `POST /devx/api/users/batch/delete` revokes capabilities (or records a warning if Consent Service is offline), writes `ticket_<ts>.json` under `data/purge_requests/<user>/`, and renames the vault directory into `data/quarantine/<ts>/<user>/`.  
   - Job manifests are stored at `data/devx_jobs/job_<ts>_<rand>.json` with per-user statuses, warnings, and ticket paths.

4. **Undo / purge**  
   - `POST /devx/api/users/batch/undo` restores vaults if still within the grace period, updating ticket status to `restored`.  
   - `POST /devx/api/users/batch/purge` enforces the review deadline before recursively deleting quarantined data and updating tickets/job manifests to `purged`.

5. **Holistic (stub)**  
   - `POST /devx/api/users/batch/run-holistic` currently queues a no-op job file. Future releases can attach real compute to the stored manifest.

---

## Data Artifacts

```
data/
├── users/<user_id>/...                # Active vaults
├── quarantine/<timestamp>/<user_id>/  # Quarantined vaults
├── purge_requests/<user_id>/ticket_<timestamp>.json
└── devx_jobs/job_<timestamp>_<rand>.json
```

Example ticket (after submission):

```json
{
  "user_id": "U1",
  "requested_at": "2025-10-08T15:40:10.123456Z",
  "status": "quarantine",
  "review_until": "2025-10-15T15:40:10.123456Z",
  "reason": "PII removal request",
  "capabilities_revoked": 12,
  "warnings": [],
  "job_id": "job_20251008T154010Z_a1b2c3",
  "quarantine_path": "data/quarantine/20251008T154010Z/U1"
}
```

If Consent Service is unavailable, `capabilities_revoked` is set to `null` and a warning is appended for auditability.

---

## Capability Governance

Every deletion request attempts to revoke the user’s active capabilities via the Consent Service (`/consent/capabilities` + `/consent/revoke`). Failures do not block quarantine but are captured in ticket warnings and the job manifest. Undo and purge operations do not re-grant capabilities; follow-up actions must be handled by governance if a user is restored.

---

## Future Batch Actions

The batch jobs folder and job manifest schema are generic:

- `action`: identifies workflow (currently `delete` or `holistic`).  
- `users`: per-user status blocks (quarantine/restored/purged).  
- Future actions can append their own metadata (e.g., holistic review metrics, RR recompute statuses) without modifying existing endpoints.

---

## CLI & Testing

Run backend tests locally:

```bash
python3 -m pytest ReDNACoreDemo/tests/test_batch_user_ops.py -v
```

The test suite provisions sandboxed user vaults, exercises delete → undo → purge flows, and simulates Consent Service downtime to ensure warnings are recorded correctly.

---

## Frequently Asked Questions

**Q: Can I rerun deletion on a user already in quarantine?**  
Yes. The new request generates an additional ticket with a fresh timestamp. The previous ticket history remains for audit.

**Q: What happens if the move to quarantine fails?**  
The ticket records the error, the job manifest marks the user as `error`, and the API response lists the failure. No partial state is kept.

**Q: Does purge remove tickets?**  
No. Tickets stay under `data/purge_requests/<user_id>/` with updated status to preserve audit trails.

---

## Run Holistic Review Jobs

DevX now includes a non-destructive batch action for holistic reviews. Use the **Run Holistic Review** tab to queue work against the selected users:

```
POST /devx/api/users/batch/run-holistic
→ {
  "job_id": "holistic_20251009_000101",
  "status": "queued",
  "count": 5
}
```

Each request stores a job manifest at `data/devx_jobs/holistic/holistic_<timestamp>.json`, capturing the user list, queued timestamp, optional reason, and action type (`run_holistic`). These jobs do not move vault data and exist today as safe placeholders; future backend releases will trigger the actual holistic computation pipeline when a manifest is queued.

---

## Revoke All Capabilities

The **Revoke All Caps** tab bulk-revokes capabilities for the selected users by calling Consent Service for each active grant. A manifest is written to `data/devx_jobs/revoke_caps/` summarising counts and warnings.

```
POST /devx/api/users/batch/revoke-caps
→ {
  "job_id": "revoke_caps_20251009_001530",
  "status": "completed",
  "total_revoked": 4,
  "results": [
    {"user_id": "TEST", "revoked": 3, "warnings": []},
    {"user_id": "U2", "revoked": 1, "warnings": ["consent_list_failed:503"]}
  ]
}
```

Failures from Consent Service are captured as warnings so the job remains idempotent—subsequent runs simply append a fresh manifest.

---

## Export JSON (sanitized)

Click **Export JSON** to generate a minimal snapshot for each selected user. The backend writes `data/exports/<user_id>/export_<timestamp>.json` containing the user's metadata and per-container `path`/`rr` pairs (no evidence or PII):

```
POST /devx/api/privacy/export-json-batch
→ {
  "ts": "20251009_001540",
  "results": [
    {
      "user_id": "TEST",
      "status": "ready",
      "download": "/devx/api/privacy/download?file=TEST/export_20251009_001540.json"
    }
  ]
}
```

Download links stream the file back through the DevX backend after validating the relative path, keeping exports safe for local analysis.

---

## Related Docs

- `docs/DEVX_OVERVIEW.md` – architecture and module index  
- `docs/TRAIT_SEMANTICS_OVERVIEW.md` – trait semantics change requests  
- Consent Service documentation (internal)  
- PermCoach governance playbooks (internal)
