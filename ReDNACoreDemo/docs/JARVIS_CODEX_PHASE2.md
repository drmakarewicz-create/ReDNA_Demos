# Jarvis-Codex Phase 2 Guide

## Overview

Phase 2 expands the Jarvis-Codex platform from single-file, text-only edits into a
multi-file semantic refactoring pipeline. The release delivers:

- **Auto-review guardrails** with AST validation, token policy enforcement, diff caps, and risk scoring.
- **Multi-file bundles** with atomic apply and rollback.
- **REST API updates** exposing manifests, auto-review metadata, and bundle telemetry.
- **DevX UI improvements** for inspecting risk, per-file diffs, and performing rollbacks.
- **Regression test suite & operator documentation** to ensure safe rollout.

---

## Semantic vs. Text/Style Operations

### Supported Semantic Operations

| Operation            | Description                                                    | Default Limits                        |
|----------------------|----------------------------------------------------------------|--------------------------------------|
| `rename_prop`        | Rename JSX/TSX component props                                 | ≤20 occurrences / ≤3 files           |
| `wrap_node`          | Wrap a node with an allowed container (`div`, `section`, …)    | ≤5 nodes / ≤2 files                  |
| `reorder_siblings`   | Reorder sibling elements (stubbed for future AST expansion)    | ≤10 swaps / ≤2 files                 |
| `replace_style_class`| Map legacy utilities to design tokens                          | ≤30 replacements / ≤5 files          |
| `remap_token`        | Migrate between design tokens                                  | ≤50 replacements / ≤10 files         |

Text-only proposals (`text_replace`) remain available for quick copy edits.

### Choosing the Right Operation

- Use **semantic operations** whenever the intent affects component structure, props, or styling tokens.
- Reserve **text replacements** for literal copy changes (no structural impact).
- Each bundle may span **up to three files and five operations in total.**

---

## Design Token Policy

### Registry

The design-token registry lives at:

```
ReDNACoreDemo/core/jarvis_codex/design_tokens.json
```

It maps legacy utilities to semantic tokens across `color`, `spacing`, `typography`, and `layout`
categories. Example:

```json
{
  "color": {
    "text-gray-600": "text-foreground-muted",
    "bg-gray-100": "bg-surface-elevated"
  }
}
```

### Enforcement

The Phase 2 token validator blocks:

- Arbitrary values (`text-[#ff0000]`, `bg-[rgb(10,10,10)]`).
- Unregistered utilities that look like style classes (e.g. `text-custom-500`).
- Hex/RGB inline styles.

Valid operations must map from a legacy utility to a known token.

### Contributing Tokens

1. Add utility → token entries to `design_tokens.json`.
2. Include a short comment in the PR describing the design rationale.
3. Run `pytest ReDNACoreDemo/tests/test_jarvis_codex_phase2.py -k token` to confirm guardrails.

---

## Auto-Review Pipeline

### Checks

| Check         | Description                                                       | Required |
|---------------|-------------------------------------------------------------------|----------|
| `ast_parse`   | Reparse patched TS/TSX using semantic engine (balanced delimiters) | ✅       |
| `token_policy`| Ensure all style ops resolve to registered tokens                  | ✅       |
| `diff_limits` | Guardrails: ≤60 changed lines/file, ≤3 files, ≤5 operations total  | ✅       |
| `typecheck`   | `tsc --noEmit` best-effort (skipped if compiler unavailable)       | ⚪ Optional |

### Risk Scoring

Risk is aggregated from files touched, line deltas, and operation weights
(rename > wrap > reorder > token remap).

```
0.0 – 0.29  → Recommendation: approve
0.30 – 0.59 → Recommendation: manual_review
0.60 – 1.00 → Recommendation: reject
```

The auto-review result is attached to each proposal:

```json
"auto_review": {
  "status": "pass",
  "risk_score": 0.32,
  "checks": {
    "ast_parse": "pass",
    "token_policy": "pass",
    "diff_limits": "pass",
    "typecheck": "skipped"
  },
  "notes": [
    "AST parse passed for 2 file(s)",
    "Diff limits respected (2 file(s), 2 operation(s))"
  ],
  "recommendation": "manual_review"
}
```

### Failed Guardrails

- **Token policy fail** → proposal logged but apply blocked (API).
- **Diff caps fail** → auto-review `status=fail`; operators must adjust bundle.
- **Typecheck fail** → surfaced as `fail`; treat as blocking unless false positive.

---

## Multi-File Bundles & Atomic Rollback

### Lifecycle

1. **Proposal Creation**
   - `CodexAgent.propose_multi_file_change()` normalises operations, produces per-file diffs, and
     writes bundle artifacts under `data/codex_patches/<proposal_id>/`.
   - Manifest stored at `manifest.json` with `changes[]`, `summary`, `risk_score`.
2. **Auto-Review**
   - Runs immediately; results stored in proposal log (`prompts/insights/jarvis_codex_proposals.jsonl`).
3. **Apply**
   - `/jarvis_codex/apply` verifies `auto_review.status == "pass"` **or**
     `recommendation ∈ {"approve", "manual_review"}`.
   - Backups saved to `web/backups/<proposal_id>/<timestamp>/` with their own manifest.
   - Apply is **atomic**; failure restores originals and removes partial backups.
4. **Rollback**
   - `/jarvis_codex/rollback` restores the latest bundle manifest and marks proposal `rolled_back`.

### Manifest Structure

```json
{
  "proposal_id": "1234",
  "summary": { "insertions": 4, "deletions": 2, "files": 2 },
  "changes": [
    {
      "file": "web/src/components/Header.tsx",
      "operation": "rename_prop",
      "lines_changed": 3,
      "diff": "...",
      "diff_stats": { "added": 2, "removed": 1, "total": 3 },
      "after_path": "data/codex_patches/1234/00_Header_tsx_e4c6d.after"
    }
  ],
  "risk_score": 0.32,
  "created_at": "2025-10-10T01:23:45Z"
}
```

Telemetry entries (`prompts/insights/jarvis_codex_audit.jsonl`) append bundle details:

```json
{
  "ts": "2025-10-10T01:24:00Z",
  "proposal_id": "1234",
  "action": "applied",
  "user": "admin",
  "files": ["web/src/components/Header.tsx"],
  "operations": ["rename_prop"],
  "risk_score": 0.32,
  "auto_review_status": "pass",
  "backup_bundle": "web/backups/1234/20251010T0124"
}
```

---

## API Enhancements

### Endpoints

| Endpoint                         | Notes                                                                                       |
|---------------------------------|---------------------------------------------------------------------------------------------|
| `GET /jarvis_codex/proposals`   | Returns `auto_review`, `risk_score`, `manifest`, `file_manifest` for each proposal.         |
| `GET /jarvis_codex/proposals/{id}` | Returns manifest plus `diffs{file: diff}` map for UI diff tabs.                          |
| `POST /jarvis_codex/apply`      | Requires auto-review approval/manual review; responds with files, backup bundle metadata.   |
| `POST /jarvis_codex/rollback`   | Restores latest backup bundle; returns restored files + timestamps.                         |
| `POST /jarvis_codex/propose`    | Accepts `type: semantic` with `files[]`/`operations[]`; attaches auto-review to response.   |

### Sample Apply Response

```json
{
  "ok": true,
  "proposal_id": "1234",
  "status": "applied",
  "files": ["web/src/components/Header.tsx"],
  "backup_bundle": "web/backups/1234/20251010T0124",
  "time_ms": 47.1
}
```

---

## DevX UI Enhancements

Key improvements in `ReDNACoreDemo/devx/frontend/src/routes/jarvis-codex/JarvisCodexPanel.tsx`:

- **ProposalTypePill** distinguishes semantic vs. text proposals.
- **AutoReviewChip** surfaces guardrail status and risk percentage.
- **GuardrailsChecklist** visualises each auto-review check (pass / fail / skipped).
- **MultiFileViewer** (tabs + Monaco-ready diff view) lazily renders per-file diffs.
- **RollbackButton** allows operators to undo applied bundles in one click.
- **GuardrailsBadge** summarises files, line deltas, and operation counts.

Screenshot placeholders (update with actual captures after deployment):

- `docs/images/jarvis_codex_panel_overview.png`
- `docs/images/jarvis_codex_auto_review.png`
- `docs/images/jarvis_codex_multi_file_diff.png`

---

## Operating Guidelines

1. **Review auto-review output** before approving; follow recommendation tiers.
2. **Verify design tokens** exist before issuing token migrations.
3. **Use rollback** immediately if a bundle introduces regressions (restores all files atomically).
4. **Monitor telemetry** (`prompts/insights/jarvis_codex_audit.jsonl`) for audit trails.
5. **Run tests** with `pytest ReDNACoreDemo/tests/test_jarvis_codex_phase2.py -v` prior to deployment.

---

## Troubleshooting

| Issue                               | Likely Cause                               | Resolution                                  |
|-------------------------------------|---------------------------------------------|---------------------------------------------|
| Auto-review `token_policy` failure  | Missing/invalid token mapping               | Update registry or adjust operation         |
| Auto-review `diff_limits` failure   | Too many files/lines/operations             | Split proposal into smaller bundles         |
| Apply blocked by API                | Auto-review `status=fail` and recommendation `reject` | Address guardrail failures and re-propose |
| Rollback missing backups            | Proposal not yet applied                    | Apply before rollback; check audit log      |

---

_Last updated: {}_

""".format(datetime.utcnow().isoformat(timespec="seconds"))
