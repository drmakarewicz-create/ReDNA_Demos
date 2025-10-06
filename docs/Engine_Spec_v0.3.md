# Engine Spec v0.3 — UCN, RR, Curiosity Contract

_Last updated: 2025-02-06_

This document is the enforceable agreement for how Core, Explorer/Head Coach (HC), and downstream coaches talk about confidence, contradictions, decay, onboarding tone, and provenance. Use it in reviews; treat every "must" as a blocker.

## 1. Vision & Roles

- **Explorer shells the Head Coach.** Explorer’s only job is to present HC and route to persona/tab experiences. No direct Core calls bypass HC orchestration.
- **Head Coach orchestrates.** HC owns persona routing, cadence, and how coach personas consume Core signals. HC exposes RR-derived bands to users, never raw UCN/Curiosity.
- **Users see RR bands, not internals.** Public UI surfaces RR as qualitative states (e.g., tentative/balanced/confident). UCN and Curiosity remain internal coach metrics.
- **UCN vs. RR vs. Curiosity**
  - **UCN (Underlying Confidence Number)** – internal trust score per trait inference. Persisted in Core, never exposed directly. Range `[0, 1]` float.
  - **RR (Reliability Rating)** – user-facing normalized view of confidence, scaled 0–1000 for presentation. HC translates UCN to RR bands before UI.
  - **Curiosity** – internal driver that prioritizes evidence gathering. Derived from inverse(RR) with cross-DNA normalization (see §2). Curiosity never surfaces directly to users.
- **Coach personas consume normalized metrics.** Persona prompts use RR bands plus Curiosity magnitude; they do not request raw UCN.

## 2. Confidence Math & Priority Signal

- **UCN storage.** Every trait inference stores `ucn` (float 0–1) in Core.
- **RR translation.** RR = `round(ucn * 1000)`, clamped `[0, 1000]`. HC converts to tone bands for users (Tentative `<200`, Balanced `200–600`, Confident `>600`).
- **Curiosity definition.**
  - Base curiosity raw = `1 - ucn`.
  - Normalize by DNA family weight: `curiosity = (1 - ucn) * importance_weight[dna_family]`.
  - Importance weights live in `data/config/trait_importance.yaml`; defaults to `1.0` per family.
  - Curiosity is capped to `[0, 1]` and logged for coach consumption only.
- **Trait importance multiplier.** Each trait inherits a `trait_importance` in `[0, 1]` that scales curiosity and coach priority (high importance → higher curiosity).
- **Coach priority score.**
  - `priority = clamp((1 - ucn) * (0.5 + 0.5 * trait_importance) + contradiction_bonus, 0, 1)`.
  - `contradiction_bonus = 0.1` when an active contradiction exists, else `0`.
  - Stored under `metrics.priority` in ingest/chat event payloads (coach-only field).

## 3. Contradiction Policy

- **Skeptical intake.** Conflicts between new evidence and resolved trait values are treated as Bayesian negatives: they lower UCN, raise curiosity, and demand validation.
- **Detection rules.** When ingest sees a new signal:
  - Compare `source_value` to `resolved_value`.
  - Use severity tiers: `minor` (semantic drift), `moderate` (diametric but low-trust source), `critical` (diametric high-trust).
  - Severity multiplies UCN reduction and curiosity bump.
- **Effect on metrics.**
  - Reduce UCN by `severity_factor * (1 - source_trust)`, clamped `[0, 1]`.
  - Push `needs_validation = true` for the affected trait.
  - Increase `metrics.priority` via contradiction bonus.
- **Cadence owned by HC.** HC is responsible for follow-up timing. Core only flags contradictions; HC ensures no spam by gating follow-up nudges.
- **Logging.** Every contradiction event logs:
  - `conflict.severity`, `source_trust`, `resolved_value`, `incoming_value`, `computed_delta`, `needs_validation` flag.

## 4. Decay Policy

- **UCN decays, traits do not.** Core reduces UCN confidence over time; the trait value remains the best-known truth until superseded.
- **Per-DNA half-life registry.**
  - Config file: `data/config/decay_registry.json`.
  - Format: `{ "PaDNA": { "half_life_days": 180 }, ... }`.
  - During nightly maintenance, apply exponential decay: `ucn *= 0.5 ** (elapsed_days / half_life_days)`.
- **Learning override channel.** If `data/config/decay_overrides.json` exists, its entries supersede registry values. Intended for Ops hot fixes.
- **Audit record.** Each decay run logs before/after UCN in audit (see §6) with reason `decay` and the half-life reference.
- **Coach hints.** HC uses Curiosity increase after decay to prioritize refresh prompts but respects user cadence limits.

## 5. Onboarding Tone & Flow

- **Button-first default.** User flow begins with a primary button: “Use smart defaults.” This seeds baseline personas without jargon.
- **Trust walkthrough as optional fork.** Secondary action: “Walk me through trust & privacy.” Simple bullets explaining data usage, provenance, and opt-outs in plain language (max 4 points).
- **WYR kickoff.** Upon completion (either path), HC asks a “Would you rather…” prompt selected from a curated set to warm up tone and gather personality signals.
- **Language guidelines.** Avoid acronyms, cite HC identity, and set expectation: “You can always change this later."
- **Data write-through.** Onboarding persists to the existing `onboarding.json` schema. Nothing extra is required by Core beyond the existing endpoint.

## 6. Provenance & Audit Requirements

- **Log everything, even failures.** Every ingest attempt writes an audit line, including rejected inputs (e.g., blurry photos) with `status: ignored` and `reason`.
- **Audit fields for UCN changes.** When UCN changes (ingest, contradiction, decay, manual override), record JSON containing:
  - `timestamp`
  - `user_id`
  - `trait_id`
  - `before_ucn`
  - `after_ucn`
  - `evidence_type` (`self`, `partner`, `device`, `app`)
  - `source_trust`
  - `decay_applied` (bool)
  - `contradiction` (bool)
  - `reason` (coach-readable sentence)
  - `provenance_ref` (file path or payload pointer)
- **Storage location.** Append to `users/<user_id>/events/ucn_<timestamp>.json`.
- **Access.** Coach tooling may read audit entries. User-facing UI receives only summarized RR bands and optional textual explanations (“Updated from your partner’s check-in yesterday”).

## 7. Dormancy, Deceased, and Artifact Handling

- **Dormancy tiers.**
  - `3 months`: mark user as “Dormant – check-in suggested.” HC reduces proactive nudges.
  - `6 months`: freeze outbound nudges except trust/welfare pings; raise curiosity for reactivation plan.
  - `12 months`: move to `Dormant+` status; HC requires explicit user reactivation before active coaching resumes.
- **Deceased protocol.**
  - Upon confirmed deceased status, freeze UCN growth. Curiosity resets to 0 unless an heir explicitly transfers stewardship.
  - Allow curated artifact browsing (read-only) guided by HC persona.
  - Transfer flow: heir identity verified via Ops (CP++); HC walks heir through memorial mode content.
- **Logging.** Dormancy/Deceased transitions recorded in audit with `reason` and operator ID when applicable.

## 8. Sensitive DNA Gating

- **Confidence requirement.** Sensitive DNA families (e.g., Medical, PsyDNA, Legal) remain hidden until UCN ≥ 0.98 (RR ≥ 980) sustained for 3 consecutive refresh cycles.
- **Gating behavior.** UI shows greyed cards with tooltips: “Locked until high confidence.” No content leakage.
- **Allowlist for power users.** CP++ manages `data/config/sensitive_allowlist.json` (user IDs). Allowlisted users bypass the 0.98 gate but are flagged in audit.
- **Coach prompts.** When gated, HC prompts persona to collect corroborating evidence gently, respecting cadence rules.
- **Enforcement.** Backend checks gate state on every sensitive trait read; attempts are logged with `access_denied` reason if gate remains closed.

## 9. Implementation Guardrails

- **No raw UCN/RR/Curiosity in UI responses.** APIs invoked by Explorer must redact internal numbers, exposing only qualitative text.
- **Consistency checks.** CI should fail if new Core endpoints ship without provenance logging hooks when they mutate UCN.
- **Feature flags.** Any experiment tweaking curiosity math must be behind a flag and include a rollback path referencing this spec.
- **PR review checklist.** Confirm:
  1. UCN changes write audit entries (§6).
  2. Sensitive DNA gating honored (§8).
  3. Contradiction severity applied (§3).
  4. Decay uses registry/override (§4).
  5. Onboarding copy stays plain language (§5).

---

Use this spec as the canonical reference. Deviations require an explicit RFC with Ops + Builder approval.
