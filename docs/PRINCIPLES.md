
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

The HC’s probabilistic model defines truth internally.
Users cannot delete or override traits; self-reports are evidence, not fact.

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

Five levels of detail (1 opaque → 5 forensic).
HC auto-adjusts level based on user curiosity and behavior.

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

⸻

🧩 In a Sentence

ReDNA is an endlessly curious, probabilistic intelligence that learns from everything, forgets nothing meaningful, explains every belief, resists manipulation, and continually seeks greater accuracy and understanding.

⸻

© ReDNA Project 2025 — This document defines behavioral, architectural, and ethical standards for all modules (Core, UCN/RR, Northstar UI, CP++).


