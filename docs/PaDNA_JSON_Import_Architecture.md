# PaDNA JSON Import Architecture

## Overview

The Photo Coach JSON importer delivers PaDNA observations that were authored outside the live vision pipeline into the Core service while preserving the Explorer/Head Coach flow. The import workflow spans three major components:

1. **PhotoRefinementCoach importer helpers** – parse, normalize, and validate uploaded bundles.
2. **Explorer Photo coach tab** – Streamlit UI that orchestrates uploads, previews, user decisions, and Core ingest.
3. **ReDNA Core ingestion path** – accepts the normalized observations, applies RR/Curiosity policy, and persists them for the Explorer apps.

The goal is to allow human-authored or GPT-generated PaDNA observations to behave identically to live vision output with minimal risk to existing functionality.

## Component Breakdown

### PhotoRefinementCoach (`src/importer.py`)

The `load_and_validate` entry point accepts raw bytes from the Streamlit uploader and performs the following steps:

1. **Decoding / JSON parse** – ensures UTF-8 text, returning syntax errors early.
2. **Schema detection** – supports two shapes:
   - `observations` map (`{"PaDNA.Path": {...}}`)
   - `traits` list (`[{"path": "Hair.Color", ...}]`)
3. **Flattening (`flatten_schema`)** – produces a canonical map of path → observation payload. The helper understands grouped observations, legacy aliases, and enforces unique string keys.
4. **Canonicalisation (`_canonicalize_path`)** – converts free-form names (e.g. `Hair.Color`, `Clothing.Top.Color`) into the expected `PaDNA.*` hierarchy so downstream Explorer code does not need separate alias handling.
5. **Trait normalisation (`_normalize_trait`)** – guarantees each trait object contains a `resolved_value` and coerces optional fields:
   - Numeric coercion for `ucn`, `rr`, `curiosity`
   - List coercion for `reasons`, `flags`
   - Wrapping scalar notes/provenance into dict containers
   - Automatic wrapping of bare scalars into `{resolved_value: scalar, ucn: 80.0}`
6. **Reporting and warnings** – collects per-section results for the UI status panel: user_id present, trait count, provenance fields, image references, duplicates, etc.
7. **Preview data (`preview_rows`)** – generates a light-weight table with `path`, `resolved_value`, `ucn`, `rr`, `curiosity`, `source`, `status`. Complex values (lists/dicts) are JSON-stringified to keep Streamlit/Arrow happy.

The importer returns `(normalized_payload, report, errors)`. The normalized payload includes:

- `user_id`
- `default_provenance`
- `observations` (canonical trait map)
- `warnings`, `duplicates`, `trait_count`
- `image_filenames`
- `needs_large_confirmation`

### Explorer Photo Tab (`ui/coach_orchestrator.py`)

The Photo tab now renders an “Import JSON” card before the legacy vision uploader.

1. **File upload** – uses `PhotoRefinementCoach/src/importer.load_and_validate`. Deduplicates uploads via an SHA-1 digest so reruns do not rebuild state unnecessarily.
2. **State management** – extends the per-tab state with importer fields (`import_payload`, `import_report`, `import_errors`, `import_warnings`, `import_preview`, `import_status`, `import_digest`, etc.) and separate widget keys to avoid Streamlit state conflicts.
3. **Automatic user handling** –
   - If no active user is selected, the `user_id` from the JSON auto-populates Explorer’s active user.
   - If an active user is already selected, the JSON’s `user_id` is ignored; ingestion always targets the active user.
4. **Validation report** – renders per-section ✅/❌ status from the importer report, followed by explicit errors/warnings (duplicates, numeric coercions, confirmation prompts for >500 traits).
5. **Preview** – displays the normalized trait table using the importer’s metadata.
6. **User controls** –
   - “Compute RR/Curiosity in Core” toggle (default ON)
   - “Use inbound RR/Curiosity values” toggle (enabled when inbound data contains rr/curiosity values)
   - Confirmation checkbox for large bundles
7. **Provenance enrichment** – merges default provenance, adds `{"source": "photo-coach", "from": "manual-import", "mode": "manual-import", "ts": <iso8601>}` and deduplicated image names.
8. **Ingest** – builds the payload and POSTs to `CORE_BASE/ingest_from_ucnrr`:
   ```json
   {
     "user_id": <active user>,
     "observations": {<canonical PaDNA path>: {...}},
     "options": {"compute_rr_curiosity": false}  // omitted when RR recompute is desired
   }
   ```
   Inbound RR/curiosity are stripped when recomputation is requested. Core responses are surfaced inline; the status block stores the target `user_id` for clarity.

The legacy photo refinement flow (vision adapters, snapshots, ingestion via canonical lines) remains untouched and available alongside the new import feature.

### ReDNA Core (`app.py`)

We introduced optional RR recomputation control via the request payload:

- `options.compute_rr_curiosity` (default `True`) is read inside `ingest_from_ucnrr`.
- `_apply_rr_notes_and_stats` now accepts a `compute_rr` flag; when `False`, it only timestamps entries without modifying RR/Curiosity values.

Everything else remains consistent with the previous UCN/RR handoff contract.

## Data Flow Summary

```
JSON file (GPT authored)         Explorer Photo tab            Core service
─────────────────────────┐       ┌────────────────────────┐     ┌────────────────────────┐
                         │ 1 ──► │ load_and_validate(...) │     │                        │
                         │       │  canonicalize + preview│     │                        │
                         │       └────────────────────────┘     │                        │
                         │                │                     │                        │
                         │                │ 2 Preview/validate  │                        │
                         │                ▼                     │                        │
                         │       ┌────────────────────────┐     │                        │
                         │       │ User toggles & ingest  │────▶│ `/ingest_from_ucnrr`   │
                         │       └────────────────────────┘     │  (rr options respected)│
                         │                ▲                     │                        │
                         │                │                     │                        │
                         └────────────────┴─────────────────────┴────────────────────────┘
```

Resulting Core state is immediately visible to downstream Explorer tabs (Head Coach, PaDNA Coach, etc.) because the canonical trait paths match the existing UI expectations.

## Design Considerations

1. **Safety and isolation** – All changes are additive. The legacy vision refinement path still exists, and the importer uses canonical helper functions from the Photo coach repo without changing Core schemas.
2. **Non-destructive defaults** –
   - RR/Curiosity recompute is enabled by default to mirror live behavior.
   - Inbound RR values are only preserved when explicitly requested.
3. **User-target accuracy** – Active Explorer user always wins. The JSON `user_id` only seeds the picker when no user is set, preventing accidental imports to the wrong account.
4. **Alias handling & warnings** – By canonicalizing paths during validation we keep Core clean and the PaDNA coach instantly functional, while still surfacing duplicate or ambiguous entries as warnings.
5. **Preview robustness** – Complex resolved values are serialized for display so Streamlit/Arrow can render without type errors.
6. **Large bundle guardrails** – Imports over 500 traits require explicit confirmation to reduce accidental bulk writes.

## Current Status & Next Steps

- ✅ JSON import available in Photo Coach tab (Explorer).
- ✅ Canonical PaDNA traits appear in Core and propagate to PaDNA coach.
- ✅ RR recompute toggle respects manual values when desired.
- ✅ Latest workspace snapshot archived under `snapshots/2025-09-23_14-45-38.zip`; Vision diagnostics tab removed from the UI.

Potential follow-up improvements:

1. **Delta preview** – Compare normalized traits against Core’s current resolved map to label additions/updates before ingest.
2. **Batch imports** – accept multiple JSON files in a queue with aggregate reporting.
3. **Evidence archival** – optionally persist uploaded JSON under `data/storage/users/<id>/evidence/photo_imports/<ts>.json` similar to live analyzer artifacts.
4. **Unit tests** – add importer-focused tests covering alias canonicalization and mixed-value previews.

This document should give downstream collaborators (and future ChatGPT sessions) enough context to troubleshoot, extend, or integrate the PaDNA import pipeline.
