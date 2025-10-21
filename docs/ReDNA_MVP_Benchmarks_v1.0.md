# ReDNA MVP Benchmarks v1.0 (Consensus)

> Scope: Phase 8 "demo-ready" experience benchmarks. These are **not** backend milestones; they're **what a demo user can do/see**. Each has an observable outcome and a simple success SLA.

1) **Seamless Launch (Cold Start → Five Greens)**
- UX: From a cold start (all services down), CP++ shows **5 green lights** automatically.
- SLA: **≤ 30s** to all-green, then **stays green ≥ 30s** (no flicker).
- Proof: CP++ health shows continuous green window; readiness probe log downloadable with timestamp.

2) **Conversational Onboarding (Real-Time Trait Cards)**
- UX: User completes onboarding; **trait cards appear in real time** during chat (not only at the end).
- Success: **≥ 5 traits extracted**.
- SLA: Each captured trait appears in Snapshot **≤ 5s** and shows **provenance** (time, channel).

3) **Trait Promotion → Graph Visualization (Immediate)**
- UX: User says a trait ("I wake up early") → graph view **animates**: new **Observation** node and **evidence_for → TraitBelief** edge.
- SLA: Graph update visible **≤ 2s** from message send; animation/flash **≤ 3s**.
- Proof: Graph pane highlights the new observation and briefly flashes the target trait node.

4) **Explainability / Why-Card (Structured, Fast)**
- UX: Clicking a trait opens a **3-sentence Why-Card**:
  1) What was observed, 2) Why it was promoted, 3) What would increase confidence.
- SLA: Renders **≤ 2s**, includes **RR, UCN, top evidence snippet**.

5) **Curiosity Loop (Queue + Visibility)**
- UX: Within a minute of onboarding, Head Coach asks a **graph-driven** follow-up and the question appears in an **Open Questions** sidebar with a priority score.
- SLA: First curiosity question **≤ 60s** after onboarding completes.
- Proof: Sidebar shows the **gap** it is closing.

6) **Contradiction Awareness (Explicit UI + Logged Event)**
- UX: If the user conflicts ("I'm a night owl"), coach replies:
  *"That's interesting—you mentioned X earlier. Has that changed?"* and shows **[Keep Both | Update | Clarify]** buttons.
- Proof: A **contradiction badge/modal** appears **and** a **contradiction event** is logged with link to prior evidence.

7) **Snapshot & Report (Actionable, Sorted, Legible)**
- UX: Snapshot shows traits with **confidence heat bar**, UCN, RR, and **curiosity score**.
- Constraint: **Sorted by curiosity (desc)** so "what to learn next" is obvious.
- Interaction: Columns sortable; hover reveals provenance.

8) **Nuclear Diagnostics (Progressive Disclosure)**
- UX: Diagnostics shows a **one-line status** (e.g., "All Operational — Graph: 23 nodes / 44 edges") with **expandable detail**.
- Detail: **Node/edge counts**, **latest promotion timestamp**, **alert counters** (0 OK; >0 warn).
- Proof: Button to **download run log** for reuse.

9) **Cross-Coach Consistency (Reference, Not Just Storage)**
- UX: Photo Coach extracts **"blue eyes"** from a selfie; later, Head Coach references it:
  *"I remember you have blue eyes—does that affect your sunlight sensitivity?"*
- SLA: Cross-coach handoff **≤ 10s**, same value + provenance tag visible in the receiving coach.

10) **Replay / Continuity (Persistence Under Restart)**
- UX: After **full shutdown** (kill all services) and restart, the user's graph/traits reload.
- SLA: Same graph renders **≤ 15s** after services start.
- Proof: "Verify Continuity" compares pre/post **hashes** of traits + graph (match = pass).

11) **AI Readiness & Green-Gate (Operator Confidence)**
- UX: From CP++ click **AI Readiness → Run Probe** and see "**ALL-GREEN: Core Connected, Graph Healthy, LLM Ready**."
- Proof: Probe emits a **downloadable run log** and UI shows **last-pass timestamp**.

12) **Live 2-Minute Walkthrough (From Blank Slate)**
- UX: In one continuous live session (not a pre-recorded clip), the operator goes:
  **cold start → onboarding → 8 promoted traits → 1 Why-Card → 1 curiosity Q → diagnostics green.**
- Validation: An **automated harness** can replay the exact steps; deviations auto-flag.

13) **Graph-Driven Insight Surfacing (Reasoning, Not Storage)**
- UX: After **10+ traits**, system autonomously surfaces one **relational insight**, e.g.:
  *"You're a Morning Lark who drinks coffee—early risers often need less caffeine. Want to explore reducing intake?"*
- Proof: Insight cites graph nodes (and confidence levels) it drew on.

---

## Stretch (Wow Factor)

14) **Multi-Turn Clarification w/ Graph Context (LLM-Aware)**
- UX: User: *"I'm trying to sleep better."*
  Coach: *"You're a Morning Lark (high confidence) but wake at 6am (warming). Do you want to wake earlier, or is sleep quality the issue?"*
- Why it's wow: Demonstrates **graph memory retrieval**, **UCN-aware wording**, and **goal alignment** in real time.

---

## Notes for the Team
- All timings are **user-visible SLAs** (front-end measured where possible).
- "Downloadable logs" = attachable artifacts for stakeholders post-demo.
- These benchmarks double as a **demo script** and a **CI demo-gate** (optional later).
