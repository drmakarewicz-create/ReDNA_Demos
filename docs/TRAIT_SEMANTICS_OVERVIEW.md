# Trait Semantics Authoring Overview

**Last updated:** 2025-10-08  
**Owner:** DevX / Ontology team

---

## Purpose

Trait semantics describe the canonical meaning, scope, and usage guidance for each trait path. This document outlines how semantics are stored, validated, and updated through the DevX change request (CR) flow.

---

## Storage Layout

Canonical semantics live alongside the ontology under `ReDNACoreDemo/core/ontology/trait_semantics/`.

```
trait_semantics/
├── registry.yaml                # Trait path → semantics mapping
├── CHANGELOG.md                 # Auto-appended on successful applies
└── schema/
    └── trait_semantics.schema.json
```

- **registry.yaml**: YAML map keyed by trait path. Each value is the most recently approved semantics document.
- **CHANGELOG.md**: Append-only log recording auto-applied change requests (timestamp, path, CR ID, notes).
- **schema/**: JSON Schema that must be satisfied by every semantics document (shared by backend and DevX UI).

> 🔁 The store is deliberately independent of `dna_registry.json`. All writes go through CR files to keep ontology changes auditable and reversible.

---

## Change Request Flow

Semantics edits are always mediated by CR artifacts. The DevX backend creates `CR_<timestamp>_<safe_path>.json` files in the same directory as the registry.

1. **Author draft (DevX UI)**  
   - Monaco JSON editor preloads the existing semantics or a scaffold for new traits.
   - Live AJV validation runs against `trait_semantics.schema.json`.

2. **Propose** (`POST /devx/api/semantics/propose`)  
   - Backend re-validates the draft with `jsonschema`.
  - On success, persists `CR_*.json` with metadata (`path`, `draft`, `notes`, `created_at`).
  - Returns `cr_id` for subsequent validation/apply steps. Invalid drafts echo the schema errors without writing a CR.

3. **Validate** (`GET /devx/api/semantics/validate?cr_id=`)  
   - Re-runs schema validation on the stored CR payload.
   - Returns `valid` and an error list, keeping the CR untouched.

4. **Apply (low-risk)** (`POST /devx/api/semantics/apply`)  
   - Loads the current registry entry and compares it with the CR draft.
   - Auto-applies when the diff is limited to documentation-only fields:  
     `definition`, `scope_notes`, and append-only changes to `examples` or `counterexamples`.
   - Any other change path returns `{"applied": false, "requires_approval": true}`. These require manual governance review before merging.
   - Successful applies overwrite the registry entry and append to `CHANGELOG.md`.

5. **Diagnostics** (`GET /devx/api/semantics/diagnostics`)  
   - Reports store location, existence of registry/schema files, and number of registered traits.

---

## Schema Highlights

File: `core/ontology/trait_semantics/schema/trait_semantics.schema.json`

Key requirements:
- `definition` *(string)* and `version` *(string)* are mandatory.
- Optional textual guidance: `scope_notes`, `inclusion_criteria`, `exclusion_criteria`.
- `operationalization` block captures evidence expectations (`temporal.kind`, `aggregation`, `window`, `context_model.required_fields`).
- `examples` / `counterexamples` accept arbitrary structured objects for flexibility.
- Review metadata fields (`last_reviewed`, `reviewers`) support audit trails but do not influence risk gating.

The DevX frontend consumes the exact same schema via `/devx/api/semantics/schema`, ensuring consistency between live editor warnings and backend enforcement.

---

## Risk Policy

| Change Type | Auto-Apply? | Notes |
|-------------|-------------|-------|
| Definition wordsmithing | ✅ | Plain-text updates to `definition`. |
| Scope clarifications | ✅ | `scope_notes` edits that keep structure intact. |
| Example additions | ✅ | Append-only changes to `examples` or `counterexamples`. |
| New sections / structural edits | ⛔️ | Requires approval. |
| Operationalization tweaks | ⛔️ | Potential behavioral impact. |
| Version bumps | ⛔️ | Requires governance review. |
| New trait semantics (no prior registry entry) | ⛔️ | Manual approval required for net-new traits. |

> When auto-apply is blocked, the CR remains on disk for manual review. Approvers can merge by updating `registry.yaml` directly (outside the DevX low-risk path) or extending the backend policy.

---

## Environment Overrides (Testing Only)

`REDNA_SEMANTICS_ROOT` can be set to redirect the backend to a temporary semantics store (used by automated tests). Do not rely on this override in production.

---

## Related Documentation

- `docs/DEVX_OVERVIEW.md` – DevX architecture and Trait Workshop overview.
- `core/ontology/dna_registry.json` – Canonical ontology containers (not modified by semantics CRs).
