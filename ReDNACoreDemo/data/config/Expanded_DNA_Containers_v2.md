# Expanded DNA Containers v2
_Last updated: 2025-09-28_

Purpose: Extend ReDNA Core trait schema with additional containers to broaden coverage, including finer-grained PaDNA (Physical Appearance DNA) and new Interaction-Derived traits observed during Head Coach ↔ User exchanges.  

Defaults: seed with ucn=0, curiosity=1.0. Sensitive containers flagged; show greyed 🔒 in Explorer unless thresholds are met and governance allows.  

Operational notes: Both PaDNA granular metrics and observational traits seed the same curiosity defaults so existing bundles do not change on disk until an operator requests persistence. Explorer renders 🔒 icons via the updated catalog metadata.

---

## PaDNA – Advanced (granular)
- Facial Landmarks (interpupillary distance, facial symmetry ratios)  **sensitive:true**
- Eye Metrics (blink frequency, gaze steadiness)  **sensitive:true**
- Hair Micro-Traits (root vs shaft color, curl index, sheen)
- Skin Micro-Traits (undertone, freckling density, redness index)
- Gait & Posture (stride length, postural lean)  **sensitive:true**
- Voice Fine-Grain (F0 range, jitter/shimmer, prosody)  **sensitive:true**
- Cosmetics & Self-Presentation (makeup frequency, typical patterns)
- Accessories & Signals (eyewear, jewelry, wearables)
- Contextual Appearance Profiles (work vs casual vs sport styles)

Implementation notes: Instrumented through the PaDNA mapper so ingest can file granular biometric observations without requiring new bundle formats. Capture routines downsample high-frequency metrics to protect users, and the UI surfaces 🔒 gates when context peaks. Ops teams can disable any sub-container by config if governance pauses collection.

---

## Conversational Dynamics
- Response Latency (fast vs thoughtful)
- Turn Length (words per response)
- Clarification Need (frequency of “could you clarify?”)
- Topic Stickiness (linger vs shift quickly)
- Repair Patterns (how user fixes mistakes)

Implementation notes: Derived from Head Coach conversational telemetry. Metrics fold into `conversation.*` traits with decay tuned for session recency so older exchanges gently retire. Backfill scripts populate defaults (ucn=0, curiosity=1.0) when the schema upgrades.

---

## Tone & Affect in Communication
- Formality Gradient (casual ↔ formal)
- Sentiment Polarity (positivity/negativity bias)
- Humor Style (dry, sarcastic, playful, punning)
- Aggression / Assertiveness
- Politeness Strategies (hedges, indirectness)

Implementation notes: Tone signals combine sentiment, assertiveness, and hedge detectors, then normalize to a 0–1 curiosity scale. Explorer shows inline tooltips explaining how each trait is inferred, keeping users aware of observed behaviors.

---

## Interaction Preferences
- Cadence Preference (rapid volley vs slow reflection)
- Aversive Triggers (topics/phrases avoided)
- Preferred Framing (abstract vs concrete, examples vs summaries)
- Closure Preference (neat endings vs open-ended)

Implementation notes: Interaction preferences aggregate cadence, re-engagement latency, and explicit opt-outs. Defaults stay neutral until the system has at least three high-confidence observations, preventing premature labeling.

---

## Cognitive & Pragmatic Signatures
- Exploration Depth (how often they probe with “why?”)
- Satisficing vs Optimizing
- Tolerance for Repetition
- Contradiction Handling Style
- Consistency of Answers

Implementation notes: Pragmatic signatures examine contradictions detected by Core’s inference engine plus answer variance tracked session-by-session. Curiosity weight remains 1.0 but adaptive_weight:true lets future heuristics rebalance emphasis without migrations.

---

## Relational / Rapport Markers
- Self-Disclosure Tendency
- Boundary Signaling (“that’s private”)
- Reciprocity Patterns (answering after being asked)
- Empathy Signals (acknowledgment, concern)
- Attachment Signals (how they address the Head Coach)

Implementation notes: Rapport markers lean on lexical cues (e.g., honorifics, nicknames) and frequency of positive acknowledgments. Traits roll up into coaching personas so Relationship Coach can adapt boundaries while keeping governance logging intact.

---

## Meta-Interaction Habits
- Correction Behavior (“I meant X”)
- Patience Window (stickiness with bad answers)
- Instruction Style (step-by-step vs broad)
- Control Orientation (steering vs following)
- Trust Calibration (adopt vs reject suggestions quickly)

Implementation notes: Meta-interaction habits fuse session command history with suggestion acceptance telemetry. Head Coach captures switch commands to ensure personas respect manual overrides while still learning long-term trust posture.

---

## Governance Notes
- All biometric-adjacent traits (PaDNA advanced, gait, voice, facial metrics) flagged **sensitive:true**.  
- Observational traits (conversation, tone, preferences) are not sensitive by default but should be transparently surfaced to users (e.g., “I’ve noticed you prefer shorter answers”).  

Implementation checklist:
- Update `core_config/trait_schema.yaml` with the new containers (ucn defaults, curiosity, adaptive_weight:true) and flag sensitive entries, matching this doc.
- Ensure Head Coach runtime captures observational metrics into `conversation.*`, `tone.*`, and related trait paths with decay tuned for recency.
- Extend Explorer Dev Container Studio filters so analysts can toggle observational vs PaDNA, and expose 🔒 badges inline for sensitive groupings.
- Seed default curiosity/ucn values in memory for existing users before writing to disk; only persist when WRITE_PROTECT is false and an explicit save occurs.
- Add acceptance QA: run `python3 -m compileall ReDNACoreDemo ExplorerDev ExplorerFinal` and spot-check Explorer Final Head Coach → Unabridged flows for the new labels.

Migration reminders:
- Legacy resolved bundles without these traits remain valid; curiosity_engine seeds them in-memory.
- If governance pauses any PaDNA stream, drop the container via config and rerun curiosity seeding—Explorer treats missing traits as neutral.
- Document transparent messaging in Explorer (“observed preference”) before enabling the conversational container for production tenants.
