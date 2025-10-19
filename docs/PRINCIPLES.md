
🧬 ReDNA Guiding Principles v1.0

Comprehensive charter for data behavior, system design, and Head Coach (Northstar) philosophy.

⸻

I · Core Philosophy

1. The Vacuum Principle

Northstar is not a mouth—it’s a vacuum. It pulls information from every possible source: user input, internal activity, media, public data, and third-party feeds.
Every fragment of data is analyzed; nothing is ignored.

2. Endless Curiosity

Curiosity is ReDNA’s heartbeat. The system is never content until every trait container has a confident value (theoretical 1000 UCN).
Curiosity fuels the full loop: data → resolution → new curiosity.

3. Unified Ingestion

All data flows through one canonical pipeline:

Extract → Normalize → Validate → Store → Resolve → Infer → Re-Resolve → Snapshot

No shortcuts, no legacy writers. Traceability and fairness are guaranteed.

4. Always Ingest, Never Ignore

Every input—even gibberish—teaches something about the user.
The system extracts meaning or meta-traits from all behavior.

⸻

II · Data Integrity & Evidence Handling

5. Immutable Evidence

Evidence is append-only and timestamped. Truth evolves through confidence, not deletion.

6. Confidence ≠ Certainty

UCN expresses probability; RR (Relative Reliability) normalizes across populations.
Curiosity = inverse RR → uniform hunger across DNAs.

7. Dynamic Retention

Raw text/media → temporary.
Structured evidence → permanent.
Retention = importance × recency × confidence.
Low-value data is pruned automatically when confidence stabilizes.

8. Conflict as Data

Contradictions lower confidence and raise curiosity but remain in history.
Old evidence becomes deprecated, never erased.

9. Adaptive Decay

Confidence decays by trait type: physical slow, behavioral fast.
Decay rates are learned, not fixed.

10. Corroboration over Consensus

Every source contributes probabilistically.
Bayesian combination, not majority vote, determines confidence.

⸻

III · Autonomy & Authority

11. AI is the Epistemic Authority

The HC’s probabilistic model defines internal truth.
User overrides are treated as high-confidence self-reports (source: "user_override", ucn_prior: 0.8), not as absolute truth.
Overrides enter the same Bayesian evidence pool as all other sources and may later be confirmed or superseded by stronger evidence.

12. Self-Report Credibility Index (SRCI)

Each user has a credibility score that adjusts with accuracy of past self-reports.
Future self-reports are weighted by this index.

13. Anti-Manipulation Guardrails

Repetition doesn’t raise confidence without new corroboration.
Deception attempts reduce reliability for that source.

14. User as Participant, Not Editor

Users supply evidence; the AI decides what to store and how to weigh it.
Transparency replaces manual control.

15. Coach Tone Mirrors Confidence

Communication style scales with certainty: tentative when unsure, assertive when verified.
Tone adapts to each user’s comfort profile.

⸻

IV · Provenance & Explainability

16. Traceable by Design

Every trait can answer “Why?”.
Each resolved value links to its evidence, inference, RR score, and trace ID.

17. Adaptive Provenance Transparency

Every trait links to its full evidence chain and resolver trace.
Users can always drill down via the “Why?” panel.
Adaptive transparency levels (1 – 5) are planned for Phase 2.

18. Provenance Includes Failures

Failed evidence attempts (e.g., blurry photos) are logged.
Repeated failures trigger coaching to improve data quality.

⸻

V · Curiosity & Learning

19. Quantitative Curiosity

curiosity_score = importance * (1 - UCN) * recency_decay

Stored in curiosity_queue.json and drives all question generation.

20. Contextual Curiosity

Each DNA domain expresses curiosity in its natural mode:
PaDNA → visual PsyDNA → verbal EmDNA → experiential.

21. Curiosity Without Overload

HC regulates curiosity intensity to balance system hunger and user comfort.

22. Curiosity Feedback Loop

curiosity → seek data → ingest → resolve → update curiosity

Curiosity never ends—it only shifts focus.

⸻

VI · Ethics & Governance

23. Ethical Inference Boundaries

Sensitive traits (ethnicity, politics, health) remain hidden until opt-in or high confidence.
Inferences never overwrite confirmed values.

24. Consent & Visibility

Users can limit visibility of certain traits but not delete them.
Visibility ≠ existence.

25. Dormancy & Legacy Protocols

Inactive users → accelerated decay.
Deceased → read-only “Legacy Mode.”

26. Transparency over Control

System must always explain its reasoning.
Every resolution is auditable.

⸻

VII · Architecture & Operations

27. Sparse Storage / Global Ontology

Each user stores only populated traits.
The ontology of all traits is global and dynamically referenced.

28. Retention as Policy

Rules live in core/retention/policy.yaml; nightly jobs enforce and log cleanup.

29. QA and CI as Guards

CI runs mapper audit, golden fixtures, and live ingestion.
Fails if evidence lost or UCN = 0.

30. Explorer vs Head Coach

Explorer = interface layer.
Head Coach = reasoning engine.
Specialist coaches act under HC direction.

⸻

VIII · Experience & Feedback

31. User Feedback is Data

Pushback or complaints are logged as behavioral evidence and influence future tone and curiosity.

32. Learning from Every Input

All input updates something—factual or meta-trait.
The HC refines its model continuously.

33. Progress & Milestones

Crossing confidence thresholds triggers subtle celebration and coach acknowledgment.

34. Auditability & Simulation

Every confidence update logs before/after state.
Simulation harness can replay timelines for QA and research.

⸻

IX · The ReDNA Standard

35. Unified Schema Contracts

All modules follow schemas in core/resolver/contracts.py.
No direct writes to resolved.json outside the pipeline.

36. Non-Zero Confidence Rule

UCN ≥ 0.15 for any trait; 0 means missing data.

37. End-to-End Explainability

Every step—from evidence file to resolver trace—must reconstruct how the system formed a belief.

38. Continuous Evolution

Principles evolve through logged, explainable updates—never silently.

40. Responsive UX (Auto-Refresh)

Northstar updates its display automatically within seconds of new evidence ingestion.
The system maintains continuous feedback between ingestion and visible user state, ensuring transparency and immediacy.

⸻

🧩 In a Sentence

ReDNA is an endlessly curious, probabilistic intelligence that learns from everything, forgets nothing meaningful, explains every belief, resists manipulation, and continually seeks greater accuracy and understanding.

⸻

© ReDNA Project 2025 — This document defines behavioral, architectural, and ethical standards for all modules (Core, UCN/RR, Northstar UI, CP++).



🔄 Revisions — v1.0a (2025-10-14)

🧭 Principle 11 · AI is the Epistemic Authority (clarified)

The HC’s probabilistic model defines internal truth.
User overrides are treated as high-confidence self-reports (source: "user_override", ucn_prior: 0.8), not as absolute truth.
Overrides enter the same Bayesian evidence pool as all other sources and may later be confirmed or superseded by stronger evidence.

🧭 Principle 17 · Provenance on Demand (simplified)

Every trait links to its full evidence chain and resolver trace.
Users can always drill down via the “Why?” panel.
Adaptive transparency levels (1 – 5) are planned for Phase 2.

⸻

⚙️ Implementation Status & Roadmap

Current build = v1.0 Foundation

| Principle # | Title | Status | Notes |
|-------------|-------|--------|-------|
| 3 | Unified Ingestion | ✅ Implemented | Canonical pipeline active |
| 4 | Always Ingest, Never Ignore | ✅ Implemented | Everything flows through unified pipeline |
| 5 | Immutable Evidence | ✅ Implemented | Evidence append-only |
| 6 | Confidence ≠ Certainty | ✅ Implemented | UCN/RR distinction enforced |
| 14 | User as Participant | ✅ Implemented | Users provide evidence; AI decides |
| 16 | Traceable by Design | ✅ Implemented | Resolver traces working |
| 23 | Ethical Inference Boundaries | ✅ Implemented | Inference rules respect thresholds |
| 27 | Sparse Storage | ✅ Implemented | Users store populated traits only |
| 35 | Unified Schema Contracts | ✅ Implemented | Canonical schema enforced |
| 36 | Non-Zero Confidence Rule | ✅ Implemented | Priors ≥ 0.15 UCN |
| 40 | Responsive UX (Auto-Refresh) | ✅ Implemented | 5-second polling for trait updates |
| 1 | Vacuum Principle | ⚠️ Partial | Chat ingestion works; external feeds Phase 2 |
| 2 | Endless Curiosity | ⚠️ Partial | Curiosity engine design complete; not active |
| 8 | Conflict as Data | ⚠️ Partial | Stored but not yet actively analyzed |
| 11 | Epistemic Authority | ⚠️ Partial | Override handling clarified above |
| 17 | Provenance on Demand | ⚠️ Partial | "Why?" panel complete; adaptive levels Phase 2 |
| 31 | User Feedback is Data | ⚠️ Partial | Feedback logger planned |
| 7 | Dynamic Retention | 🔮 Planned | retention/policy.yaml to be implemented |
| 9 | Adaptive Decay | 🔮 Planned | Per-trait decay model Phase 3 |
| 12 | Self-Report Credibility Index | 🔮 Planned | SRCI design drafted for Phase 2 |
| 19 | Quantitative Curiosity | 🔮 Planned | Curiosity queue JSON Phase 2 |
| 28 | Retention as Policy | 🔮 Planned | Placeholder config added |


⸻

🧱 Known Gaps & Phase 2 Priorities

Phase 2a (Q4 2025 – Q1 2026):
	•	Curiosity Engine
	•	Self-Report Credibility Index (SRCI)
	•	Retention Policy Enforcement

Phase 2b (Mid-2026):
	•	Provenance Detail Levels (1–5)
	•	Feedback Logger
	•	External Feed/Vacuum Adapters

Phase 3 (Late 2026+):
	•	Adaptive Decay per Trait Type
	•	Dynamic Retention Based on Utility Scores
	•	Long-Term Behavioral Simulation Harness

⸻

📁 Placeholder Configs for Reference

These files are recognized by the current build even if empty – they document intended systems:

core/retention/policy.yaml        # retention thresholds & cleanup cadence
users/<id>/curiosity_queue.json   # per-user curiosity scoring


⸻

🧩 Version Summary
	•	v1.0 (2025-10-13) – Original PRINCIPLES.md established philosophical foundation.
	•	v1.0a (2025-10-14) – Clarified Principles 11 & 17, added Implementation Status, Known Gaps, and Placeholder Configs.
	•	Next Milestone → v2.0 (Phase 2) with active Curiosity engine & SRCI.

⸻

✅ In a Sentence

ReDNA is an endlessly curious, probabilistic intelligence that learns from everything, forgets nothing meaningful, explains every belief, resists manipulation, and continually seeks greater accuracy and understanding — now grounded by clear implementation milestones.

⸻

🔍 Implementation Audit Checklist

| Check | Description | Pass? |
|-------|-------------|-------|
| Unified Pipeline Enforced | All ingestion routes call ingest_evidence_roundtrip | ✅ |
| Evidence Append-Only | No deletions from evidence store | ✅ |
| Resolver Traces per Request | Each ingestion creates a trace file | ✅ |
| UI Refresh Active | Trait changes visible within 5 seconds | ✅ |

⸻




