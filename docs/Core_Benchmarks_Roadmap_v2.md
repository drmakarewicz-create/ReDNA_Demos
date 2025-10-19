# Core Benchmarks Roadmap v2

_Last updated: 2025-10-06_

## 🎯 Vision (guiding principles)

ReDNA builds **living digital approximations** of users (DNAs) that evolve over time. The **Head Coach** orchestrates everything: Explorer is the shell; Core/UCN/RR detect & rank; coaches act. **Curiosity** (inverse of RR, normalized per DNA family) drives agendas; **contradictions** can persist as tension until the Head Coach probes. We keep **provenance**, log attempts (even failed ones), and honor **governance** (dormancy/deceased protocols, sensitive DNA gating, manipulation penalties). Users can **redirect** and give **feedback** that shapes future plans. Over time, coaches develop **CReDNA** (coach-level playbooks) with strict versioning and rollback.

**New in v2:** The system now supports **Relationship Synergy Coach (RSC)** — privacy-preserving cross-user coach collaboration where coaches can work together to help couples/partners while protecting individual confidences. RSC-enabled Relationship Coaches can collaborate to encourage beneficial behaviors or share insights, but use **camouflaging protocols** to prevent revealing what was said in confidence by either user. For example, if User1 complains that User2 never helps with dishes, the coaches might subtly encourage User2 to help with chores without revealing User1's specific complaint, using techniques like embedding suggestions in broader lists or making general observations about relationship dynamics. Camouflaging protocols will sacrifice information sharing if it risks betraying confidences.

## 📋 Completed Benchmarks (v1 Achievements)

### Foundation & Infrastructure
- ✅ **Project Structure Cleanup**: 23 .md files → `docs/historical/`, 13 test files → `tests/`, 4 utilities → `scripts/`, 11 legacy services → `archive/legacy_services/`
- ✅ **Head Coach Shell Integration**: Explorer, Onboarding, Photo Coach, PaDNA Renderer consolidated into Head Coach
- ✅ **Seamless Persona Switching**: Chat-driven routing with auto-greeting and acknowledgment
- ✅ **Developer Explorer Shell**: Full ORS console with service ping, log tailer, trace explorer, 7 focused modules
- ✅ **Testing & Automation**: Production-ready pytest coverage (75+ tests), golden-path regression script with `WRITE_PROTECT` safety

### Coach Development
- ✅ **Relationship Coach (RC)**: Warm confidant voice with 260+ line system prompt, 60+ micro-actions, 4-step structure (Acknowledge → Reflect → Guide → Invite)
- ✅ **Plan Composer**: Rule-based 3-step game plan generation (<50ms) with persistent storage and coach delegation
- ✅ **CReDNA Beta**: Trait graph, coverage tracking, import/export, template preferences, `WRITE_PROTECT` save guard

### Data & Analytics
- ✅ **Persona Snapshots**: Timestamped PaDNA export (full/partial), version tagging, history tracking, API endpoints
- ✅ **Analytics Dashboards**: Coach switch frequency, curiosity coverage %, Ops schedule compliance, system health with CSV/JSON export
- ✅ **Telemetry Consolidation**: Unified trace schema with waterfall visualization, component timing, search/filter/export
- ✅ **Feedback Loop Integration**: Trait scores, planning weights (0.5-1.5 multipliers), ToleranceForNudging emergent trait
- ✅ **Holistic Intelligence**: LLM-assisted holistic pass, auto-scheduler with env-var controlled cadence (weekly default)

### Governance & Audit
- ✅ **Dev Explorer Governance Tab**: Audit logs with rollback, dormancy management, sensitivity gating, provenance explorer
- ✅ **Head Coach Ops v1**: Scheduling card, TTL, snooze, cohorts, run-now, batch dismiss

---

## 🚀 Active Development (v2 Priorities)

### Phase 1 — RSC Foundation Infrastructure (Months 1-2)

#### 1.1 Relationship Graph & Schema
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** Medium

**Objective:** Build multi-user relationship substrate supporting nested contexts (couple, family, team) with unique `relationship_id` to prevent data collision when two Users share multiple relationship types.

**Requirements:**
- Schema design supporting:
  - Nested relationship types (1:1, 1:N, N:N)
  - Multiple concurrent relationship contexts per User pair
  - Relationship metadata (created_at, status, consent_state)
  - Provenance tracking for all relationship events
- Storage layer in Core (`relationship_graph.py`)
- API endpoints for relationship CRUD operations
- Migration path from single-user to multi-user data model

**Acceptance Criteria:**
- Two Users can exist in "couple" and "colleagues" relationships simultaneously without collision
- Relationship graph supports family trees (parent-child, siblings) and team structures
- Full audit trail for relationship creation, modification, deletion
- Performance: <100ms for relationship query operations

**Deliverables:**
- `core/relationship_graph.py` (300+ lines)
- `api_relationships.py` (FastAPI endpoints)
- Schema migration script
- Unit tests (20+ test cases)
- Design doc: [Relationship_Graph_Design.md]

---

#### 1.2 Provenance Firewall
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Create strict separation between internal provenance (full coach-to-coach attribution) and RSC-visible abstractions (camouflaged, source-agnostic signals).

**Requirements:**
- **Internal Provenance Layer:**
  - Complete attribution: which coach, from which User, at what timestamp
  - Full reasoning chain: why the coach made a suggestion
  - Confidence scores and uncertainty flags
  - Storage in Dev Mode only (never exposed to User Mode)

- **RSC Abstraction Layer:**
  - Camouflaged signal format (YAML patterns with tone/timing control)
  - Source-agnostic reframes ("research suggests..." not "your partner's coach noted...")
  - Delayed timing injection (randomized delays 30s-5min to prevent correlation)
  - Linguistic variation to prevent fingerprinting

- **Privacy Validation:**
  - Red-team utility to detect timing/linguistic correlations
  - Automated privacy stress tests in CI/CD
  - Fail-safe: block RSC exchange if camouflage confidence < 0.85

**Acceptance Criteria:**
- Dev Mode shows full provenance with coach attribution and reasoning
- User Mode shows only camouflaged abstractions with no traceable source
- Red-team utility cannot infer User A → User B connection from exchange logs
- Privacy stress tests pass with >95% confidence
- Provenance firewall audit log captures all cross-boundary translations

**Deliverables:**
- `core/provenance_firewall.py` (500+ lines)
- `core/rsc_abstraction.py` (camouflage translation)
- `tests/privacy_redteam.py` (stress test utility)
- Dev Mode provenance viewer UI component
- Design doc: [Provenance_Firewall_Design.md]

---

#### 1.3 Coach Autonomy Framework
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Implement dynamic autonomy scaling tied to RR thresholds and User trust scores, allowing coaches to evolve organically as User refinement rises (true Adaptive Standard behavior).

**Requirements:**
- **Autonomy Levels (0-5 scale):**
  - **Level 0 (Passive):** Coach only responds to direct User queries
  - **Level 1 (Suggestive):** Coach offers observations when prompted
  - **Level 2 (Proactive):** Coach initiates low-stakes nudges
  - **Level 3 (Collaborative):** Coach proposes multi-step plans
  - **Level 4 (Strategic):** Coach orchestrates RSC collaborations (requires Head Coach approval)
  - **Level 5 (Autonomous):** Coach executes RSC schemes independently (reserved for Black Mirror tier)

- **Dynamic Scaling Formula:**
  ```
  autonomy_level = f(RR_avg, trust_score, consent_flags)
  where:
    - RR_avg: rolling 30-day average RR across all traits
    - trust_score: derived from feedback loop (0.0-1.0)
    - consent_flags: explicit User permissions for autonomy level
  ```

- **Governance:**
  - Head Coach must pre-approve all Level 4+ actions
  - Real-time autonomy badges in Dev Explorer
  - User-facing autonomy control panel in Settings
  - Automatic autonomy reduction if feedback scores drop <0.6

**Acceptance Criteria:**
- Autonomy level adjusts automatically as RR and trust evolve
- Level 4+ actions require explicit Head Coach digest review
- User can manually cap maximum autonomy level (e.g., "never exceed Level 2")
- Autonomy changes logged in audit trail with justification
- Performance: autonomy recalculation <50ms per coach action

**Deliverables:**
- `core/autonomy_framework.py` (400+ lines)
- `api_autonomy.py` (endpoints for level query/override)
- User Settings autonomy control panel UI
- Dev Explorer autonomy dashboard
- Design doc: [Coach_Autonomy_Design.md]

---

#### 1.4 Lightweight Holistic Review Hook
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Early proof-of-concept for cross-User pattern detection (communication style, empathy score correlation) without live relationships, validating that provenance firewall still allows aggregate analysis.

**Requirements:**
- Synthetic multi-user dataset (5-10 test Users)
- Pattern detection routines:
  - Communication style clustering (assertive, passive, collaborative)
  - Empathy score correlation analysis
  - Conflict resolution pattern matching
- Privacy validation: ensure pattern detection uses only aggregated/anonymized data
- Integration with existing holistic review scheduler

**Acceptance Criteria:**
- Holistic review can identify cross-User patterns (e.g., "Users with high empathy scores tend to prefer collaborative communication")
- Pattern detection respects consent flags (exclude non-consenting Users)
- No individual User data exposed in aggregate reports
- Results logged in Dev Mode with full provenance

**Deliverables:**
- `core/holistic_multi_user.py` (200+ lines)
- Synthetic dataset generation script
- Pattern detection report template
- Integration with `holistic_scheduler.py`
- Design doc: [Holistic_Multi_User_Design.md]

---

### Phase 2 — RSC Collaboration Protocols (Months 2-4)

#### 2.1 Cross-Coach Communication Protocol
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Define structured protocol for coaches to exchange signals across relationship boundaries with strict camouflaging and provenance tracking.

**Requirements:**
- **Signal Types:**
  - **Observation Signal:** Low-stakes pattern notice (e.g., "User seems stressed lately")
  - **Guidance Request:** Coach A asks Coach B for context on User B's state
  - **Micro-Action Suggestion:** Coach A suggests specific action for User B
  - **Reflection Nudge:** Coach A prompts Coach B to guide User B toward self-awareness

- **Camouflage Translation Patterns (YAML-based):**
  ```yaml
  internal_signal:
    source_coach: "User A's Relationship Coach"
    observation: "User A feels unheard during conflicts"
    suggested_micro_action: "Practice active listening with User B"

  camouflaged_output:
    user_facing_text: "Research on communication patterns suggests that intentional listening can transform conflict dynamics. Would you be open to trying a brief exercise?"
    tone: "supportive"
    timing_delay: "randomized 90-180s"
    linguistic_variant: 3  # select from 5 pre-written variations
  ```

- **Contextual Tone Variants:**
  - Supportive (warm, encouraging)
  - Playful (lighthearted, metaphorical)
  - Direct (clear, action-oriented)
  - Analytical (data-driven, reflective)
  - Map tone to PsyDNA/MetaDNA traits for personality-consistent delivery

**Acceptance Criteria:**
- Signal exchange follows structured schema with full provenance
- Camouflaged output passes red-team correlation tests
- Tone variants match User personality profiles (verified by tone filter checklist)
- All signals logged in Dev Mode with attribution; User Mode shows only camouflaged text
- Latency: camouflage translation <200ms

**Deliverables:**
- `core/rsc_protocol.py` (600+ lines)
- YAML camouflage template library (100+ patterns)
- Tone variant mapping logic
- API endpoints for signal exchange
- Design doc: [RSC_Protocol_Design.md]

---

#### 2.2 Consent Guardian Service
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Implement dual-consent model with optional "shadow relationship" mode for passive curiosity analysis without prompting non-consenting User.

**Requirements:**
- **Consent Levels:**
  - **Full Consent:** Both Users agree to RSC collaboration (coaches can exchange signals bidirectionally)
  - **Partial Consent (Shadow):** User A consents; User B unaware. Coach A can analyze patterns but cannot send signals to Coach B
  - **No Consent:** No RSC collaboration; relationship exists but coaches operate independently

- **Consent Workflow:**
  - User receives explicit consent prompt when relationship is created
  - Consent can be granted/revoked at any time
  - Revocation triggers 30-day data decay period (see 2.4 below)
  - Shadow mode requires special ethical review flag in Dev Mode

- **Audit & Transparency:**
  - All consent changes logged with timestamp and justification
  - User-facing consent dashboard shows active relationships and consent status
  - Dev Mode shows consent history and shadow mode activity (if any)

**Acceptance Criteria:**
- Consent model prevents RSC collaboration without explicit agreement
- Shadow mode enables passive analysis without User B awareness (ethical review required)
- Consent revocation immediately halts signal exchange
- User can view/modify consent status at any time via Settings
- Audit log captures all consent events with full provenance

**Deliverables:**
- `core/consent_guardian.py` (400+ lines)
- `api_consent.py` (endpoints for consent CRUD)
- User Settings consent dashboard UI
- Dev Mode consent history viewer
- Design doc: [Consent_Guardian_Design.md]

---

#### 2.3 Head Coach Governance Layer
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Head Coach receives pre-execution digest for medium-risk RSC collaborations and post-execution log for low-risk ones; strategic/sensitive actions queue for explicit approval.

**Requirements:**
- **Risk Classification:**
  - **Low Risk:** Reflection nudges, observational signals (auto-approve, post-execution log)
  - **Medium Risk:** Guidance requests, micro-action suggestions (pre-execution digest, auto-approve after 5s delay)
  - **High Risk:** Strategic multi-step schemes, sensitive trait discussions (queue for explicit Head Coach approval)

- **Head Coach Review Interface:**
  - Digest format: source coach, target coach, signal type, camouflaged output preview, risk assessment
  - Approval options: approve, deny, modify camouflage, request more context
  - Post-execution log: timestamped summary of all auto-approved actions

- **Governance Rules:**
  - High-risk actions cannot execute without Head Coach approval
  - Head Coach can adjust autonomy levels to change risk thresholds
  - Approval decisions logged in audit trail
  - User can override Head Coach decisions via Settings (emergency stop)

**Acceptance Criteria:**
- Low-risk RSC actions execute automatically with post-execution logging
- Medium-risk actions show pre-execution digest to Head Coach (5s auto-approve)
- High-risk actions block until explicit Head Coach approval
- Head Coach can review/modify/deny any queued action
- User emergency stop immediately halts all RSC activity

**Deliverables:**
- `core/head_coach_governance.py` (500+ lines)
- Head Coach review UI component
- Risk classification logic
- API endpoints for approval workflow
- Design doc: [Head_Coach_Governance_Design.md]

---

#### 2.4 Breakup / Revocation Protocol
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Define explicit data-decay timing (30-day period) after relationship revocation; provenance stays in Dev Mode for audit, but camouflaged content purges fully post-decay.

**Requirements:**
- **Revocation Trigger Events:**
  - User explicitly ends relationship via Settings
  - Consent revocation (both Users must consent to maintain RSC)
  - Dormancy escalation (User marked deceased or dormant for 12+ months)

- **Data Decay Timeline:**
  - **Day 0 (Revocation):** All active RSC collaboration immediately halts
  - **Day 0-30 (Decay Period):** Provenance retained in Dev Mode for audit; no new signals exchanged
  - **Day 30 (Purge):** All camouflaged content deleted from User-facing data; Dev Mode provenance archived with tombstone marker

- **Audit Preservation:**
  - Dev Mode retains provenance indefinitely for governance review
  - Archived provenance encrypted at rest
  - User can request full data export during decay period

**Acceptance Criteria:**
- Revocation instantly stops all RSC signal exchange
- Camouflaged content purges completely after 30-day decay
- Dev Mode provenance archived with tombstone marker post-purge
- User receives confirmation email when purge completes
- Audit log captures revocation event, decay timeline, and purge completion

**Deliverables:**
- `core/revocation_protocol.py` (300+ lines)
- Data decay scheduler integration
- Dev Mode provenance archiver
- User notification system
- Design doc: [Revocation_Protocol_Design.md]

---

### Phase 3 — Couples Coach MVP (Months 4-6)

#### 3.1 Couples Coach Persona
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Launch specialized coach persona optimized for dyadic relationship dynamics with RSC collaboration as core capability.

**Requirements:**
- **Voice & Tone:**
  - Warm, balanced, systems-aware (not taking sides)
  - Uses "we/us/together" language to reinforce partnership
  - Emphasizes patterns over blame

- **Core Capabilities:**
  - Relationship assessment (attachment styles, communication patterns, conflict dynamics)
  - RSC-enabled cross-partner insights (camouflaged delivery)
  - Micro-action library for couples (turn-and-learn, repair attempts, appreciation rituals)
  - Conflict de-escalation protocols

- **Integration:**
  - Couples Coach appears in persona switcher when relationship exists with dual consent
  - Direct access to relationship graph and RSC protocol
  - Can invoke RC or other coaches for specialized support

- **Safety & Ethics:**
  - Never reveals partner's coach inputs directly
  - Bias detection (ensure balance between partners)
  - Domestic violence risk assessment with escalation protocol

**Acceptance Criteria:**
- Couples Coach persona appears when User has active relationship with dual consent
- Voice and tone distinct from individual RC (partnership-focused vs. individual-focused)
- Successfully delivers camouflaged RSC insights without source attribution
- Micro-action library includes 50+ couples-specific actions
- Bias detection flags any imbalance >70% toward one partner

**Deliverables:**
- `coaches/couples_coach.py` (800+ lines)
- System prompt with relationship dynamics expertise (400+ lines)
- Couples micro-action library (50+ actions)
- Bias detection module
- Design doc: [Couples_Coach_Design.md]

---

#### 3.2 Two-User RSC Proof of Concept
**Status:** 🟡 Not Started | **Priority:** Critical | **Risk:** High

**Objective:** Demonstrate fully functional RSC collaboration between two synthetic Users with zero traceable provenance leakage. This is the official "RSC Proof of Concept" milestone.

**Requirements:**
- **Scenario:** User A and User B in committed relationship; both have active Head Coach + RC + Couples Coach
- **Test Flow:**
  1. User A expresses frustration about communication patterns to RC
  2. User A's RC generates observation signal → User B's RC (via RSC protocol)
  3. User B's RC receives camouflaged signal, crafts reflection nudge for User B
  4. User B engages with nudge, receives micro-action suggestion
  5. User A observes behavior change, provides positive feedback

- **Validation:**
  - Dev Mode shows complete provenance chain (A's RC → camouflage → B's RC)
  - User Mode shows only camouflaged prompts (no attribution to A or A's RC)
  - Red-team utility cannot detect correlation between A's input and B's prompt
  - Head Coach governance logs show risk assessment and approval

- **Success Metrics:**
  - Provenance firewall integrity: 100% (no leaks)
  - Camouflage correlation resistance: >95% confidence
  - User experience: natural, non-suspicious timing and phrasing
  - Latency: end-to-end signal exchange <5s

**Acceptance Criteria:**
- Two synthetic Users successfully exchange RSC signals with full camouflaging
- Provenance fully traceable in Dev Mode, completely hidden in User Mode
- Red-team utility fails to detect User A → User B connection
- Head Coach governance approves/logs all medium/high-risk exchanges
- User experience smooth and natural (validated via simulated user testing)

**Deliverables:**
- Synthetic User pair setup script
- RSC proof-of-concept test harness
- Red-team validation report
- Demo recording (Dev Mode + User Mode side-by-side)
- Milestone documentation: [RSC_Proof_of_Concept.md]

---

#### 3.3 RSC Observatory (Dev Mode Tool)
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Build comprehensive Dev Mode dashboard for visualizing, auditing, and stress-testing all RSC activity.

**Requirements:**
- **Visualization Components:**
  - Relationship graph viewer (nodes = Users, edges = relationships with consent status)
  - Signal flow diagram (animated waterfall showing Coach A → camouflage → Coach B)
  - Provenance timeline (chronological log of all RSC events)
  - Privacy health score (aggregate camouflage effectiveness, correlation resistance)

- **Audit Tools:**
  - Search/filter by User, coach, relationship, date range
  - Export RSC logs for external analysis
  - Consent history viewer per relationship
  - Head Coach approval queue with decision history

- **Stress Testing:**
  - Privacy red-team utility (attempt to infer source from camouflaged signals)
  - Autonomy boundary checker (flag any Level 4+ actions that bypassed approval)
  - Bias detector (analyze RSC patterns for systemic imbalances)

**Acceptance Criteria:**
- RSC Observatory accessible via Dev Explorer → Observability tab
- All RSC events (signal exchange, consent changes, revocations) visible in timeline
- Privacy health score updates real-time as signals exchange
- Red-team utility integrated with one-click stress test launch
- Export functionality generates structured JSON logs for offline analysis

**Deliverables:**
- `dev_explorer/rsc_observatory.py` (700+ lines)
- UI components for graph viewer, signal flow, provenance timeline
- Privacy red-team integration
- API endpoints for RSC audit queries
- Design doc: [RSC_Observatory_Design.md]

---

### Phase 4 — Core Logic & Trait Resolution (Months 5-7)

#### 4.1 Trait Inference Engine Upgrade
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Enhance Core's trait resolution logic to make wider inferences, improve UCN/RR/Curiosity accuracy, and generate stronger game plans with higher confidence.

**Requirements:**
- **Inference Expansion:**
  - Cross-trait correlation analysis (e.g., high Openness + low Agreeableness → contrarian tendencies)
  - Temporal pattern detection (trait stability vs. volatility over time)
  - Context-aware inference (work context vs. home context trait differences)
  - Contradiction-aware resolution (conflicting evidence → tension markers, elevated curiosity)

- **UCN/RR Accuracy Improvements:**
  - Weighted evidence scoring (direct observation > indirect inference > speculation)
  - Recency bias mitigation (older evidence decays but doesn't disappear)
  - Source diversity bonus (multiple independent sources increase confidence)
  - Uncertainty quantification (explicit confidence intervals on RR values)

- **Curiosity-Driven Game Plans:**
  - Prioritize high-curiosity traits with low RR (biggest knowledge gaps)
  - Balance exploration (new traits) vs. exploitation (refine existing traits)
  - Multi-step game plans with intermediate validation checkpoints
  - Coach delegation based on trait family expertise

**Acceptance Criteria:**
- Inference engine detects cross-trait correlations with >80% accuracy on test dataset
- UCN/RR values include explicit confidence intervals
- Curiosity-driven game plans prioritize traits with highest curiosity × confidence gap
- Contradiction detection flags conflicting evidence and elevates curiosity
- Performance: full trait resolution for single User <500ms

**Deliverables:**
- `core/inference_engine_v2.py` (1000+ lines)
- Cross-trait correlation models
- Uncertainty quantification module
- Enhanced game plan generation logic
- Design doc: [Trait_Inference_Engine_v2.md]

---

#### 4.2 Contradiction & Tension Framework
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Low

**Objective:** Formalize how contradictions reduce UCN, raise curiosity, persist as tension markers, and prompt Head Coach probing.

**Requirements:**
- **Contradiction Detection:**
  - Identify conflicting evidence within same trait (e.g., "User is introverted" vs. "User seeks social stimulation")
  - Flag temporal contradictions (trait value changes sharply without clear cause)
  - Detect context-dependent contradictions (behaves differently at work vs. home)

- **Tension Markers:**
  - Persist contradictions as "tension" metadata on traits
  - Tension score (0.0-1.0) based on evidence strength of conflicting signals
  - Tension elevates curiosity (stronger tension → higher curiosity)
  - Tension decays over time unless reinforced by new evidence

- **Head Coach Probing:**
  - High-tension traits (>0.7) trigger Head Coach investigation prompts
  - Head Coach can ask clarifying questions to resolve contradiction
  - Resolution reduces tension, updates RR/UCN, logs provenance

- **Dev Mode Visibility:**
  - Contradiction badge in trait viewer
  - Tension timeline showing evolution over time
  - Resolution history with Head Coach decisions

**Acceptance Criteria:**
- Contradictions automatically detected and flagged as tension markers
- Tension score accurately reflects evidence strength of conflict
- High-tension traits trigger Head Coach probing prompts
- Contradiction resolution updates UCN/RR and logs provenance
- Dev Mode shows tension badges and resolution history

**Deliverables:**
- `core/contradiction_framework.py` (400+ lines)
- Tension scoring logic
- Head Coach probing integration
- Dev Mode tension viewer UI
- Design doc: [Contradiction_Tension_Framework.md]

---

#### 4.3 Enhanced Curiosity Engine
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Upgrade curiosity formula with DNA-family weights, decay curves, rebound dynamics, and contradiction-driven spikes.

**Requirements:**
- **Curiosity Formula v2:**
  ```
  curiosity(trait) = base_curiosity × family_weight × decay_factor × rebound_multiplier × tension_amplifier

  where:
    - base_curiosity = 1 - (RR / RR_max)  # inverse RR, normalized
    - family_weight = importance of DNA family (PsyDNA > CareerDNA > HobbyDNA)
    - decay_factor = time-based decay (curiosity fades if trait not explored)
    - rebound_multiplier = spikes after failed exploration attempt (resilience)
    - tension_amplifier = 1 + (tension_score × 0.5)  # contradictions boost curiosity
  ```

- **Decay & Rebound:**
  - Curiosity decays exponentially if trait not explored within 30 days
  - Failed exploration attempts (User declines nudge) trigger rebound spike after 7-14 days
  - Successful exploration reduces curiosity and increases RR

- **Family Weights:**
  - PsyDNA: 1.5× (highest priority for holistic understanding)
  - MetaDNA: 1.3× (self-awareness and meta-cognition)
  - RelationshipDNA: 1.2× (social dynamics)
  - CareerDNA / HobbyDNA / PhysicalDNA: 1.0× (baseline)

- **Integration:**
  - Curiosity scores feed into Head Coach game plan prioritization
  - High-curiosity traits appear in Dev Explorer Curiosity Coverage dashboard
  - API endpoints expose curiosity scores per trait for coach access

**Acceptance Criteria:**
- Curiosity formula incorporates all five factors (base, family, decay, rebound, tension)
- High-curiosity traits prioritized in Head Coach game plans
- Decay and rebound dynamics observable in Dev Mode curiosity timeline
- Family weights ensure PsyDNA traits explored preferentially
- Performance: curiosity recalculation for all traits <200ms

**Deliverables:**
- `core/curiosity_engine_v2.py` (600+ lines)
- Decay/rebound scheduling logic
- Family weight configuration
- API endpoints for curiosity queries
- Design doc: [Curiosity_Engine_v2.md]

---

#### 4.4 Trait Container Expansion
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Increase number of trait containers in Core to support richer PaDNA inputs and broader personality/relationship/career coverage.

**Requirements:**
- **Current Coverage Audit:**
  - Catalog existing traits per DNA family
  - Identify gaps (e.g., missing HEXACO facets, relationship attachment styles)

- **Expansion Plan:**
  - Add 50+ new trait containers:
    - **PsyDNA:** HEXACO sub-facets, cognitive biases, thinking styles
    - **MetaDNA:** Self-efficacy, locus of control, growth mindset
    - **RelationshipDNA:** Attachment styles (secure, anxious, avoidant), love languages, conflict styles
    - **CareerDNA:** Work values (autonomy, mastery, purpose), leadership styles
    - **PhysicalDNA:** Health behaviors, sleep patterns, stress responses

- **Schema Update:**
  - Extend `trait_schema.yaml` with new containers
  - Ensure all containers include: name, description, RR bounds, sensitivity flags, provenance rules
  - Backward compatibility: existing traits unchanged

- **Data Migration:**
  - Auto-generate empty containers for existing Users
  - Preserve existing trait data during schema upgrade

**Acceptance Criteria:**
- 50+ new trait containers added to `trait_schema.yaml`
- All new containers include full metadata (description, bounds, flags)
- Existing Users receive new empty containers without data loss
- Dev Mode trait viewer shows expanded coverage
- Documentation updated with new trait definitions

**Deliverables:**
- `core/trait_schema_v2.yaml` (expanded from ~200 to 350+ traits)
- Schema migration script
- Trait definition documentation
- Unit tests for new containers
- Design doc: [Trait_Container_Expansion.md]

---

### Phase 5 — Governance & Ethical Safeguards (Months 6-8)

#### 5.1 Dormancy & Deceased Protocols
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Implement 3/6/12-month dormancy states with deceased protocol (heir transfer) and RR exclusion rules.

**Requirements:**
- **Dormancy States:**
  - **Active:** User engaged within last 90 days
  - **Dormant (Light):** No engagement 90-180 days (reduced nudge frequency)
  - **Dormant (Moderate):** No engagement 180-365 days (no proactive nudges, RR decay begins)
  - **Dormant (Deep):** No engagement 365+ days (RR excluded from analytics, coaches enter maintenance mode)

- **Deceased Protocol:**
  - User or authorized contact marks account as deceased
  - Immediate halt to all proactive coach activity
  - 30-day grace period for heir nomination
  - Heir can inherit:
    - Persona snapshots (frozen ReDNA states)
    - Relationship graph connections (if consent granted by other parties)
    - Provenance logs (for legacy preservation)
  - Full data deletion option (alternative to inheritance)

- **RR Exclusion:**
  - Dormant (Deep) and Deceased Users excluded from aggregate RR calculations
  - Relationship graph edges marked inactive but preserved for audit
  - Coaches enter "memorial mode" (read-only, no active plans)

**Acceptance Criteria:**
- Dormancy state auto-updates based on last engagement timestamp
- Deceased protocol triggers immediately upon account marking
- Heir can successfully inherit designated data within 30-day window
- Dormant/Deceased Users excluded from system-wide analytics
- Audit log captures all dormancy state changes and heir transfers

**Deliverables:**
- `core/dormancy_protocol.py` (500+ lines)
- `core/deceased_protocol.py` (400+ lines)
- Heir nomination workflow
- UI components for dormancy dashboard
- Design doc: [Dormancy_Deceased_Protocols.md]

---

#### 5.2 Sensitive DNA Gating
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Low

**Objective:** Gray out sensitive trait previews until confidence threshold reached; add consent flags and informative tooltips.

**Requirements:**
- **Sensitivity Levels:**
  - **Public:** No restrictions (e.g., favorite color, hobby preferences)
  - **Personal:** Visible after RR > 0.5 (e.g., introversion/extraversion)
  - **Sensitive:** Visible after RR > 0.7 + explicit consent (e.g., attachment style, trauma history)
  - **Protected:** Never auto-inferred; only from direct User input (e.g., mental health diagnoses, abuse history)

- **UI Treatment:**
  - Sensitive traits grayed out with lock icon until threshold met
  - Tooltip explains: "We need more information before displaying this trait"
  - Consent prompt appears when threshold reached: "We've learned enough to show [trait]. Do you want to see this?"

- **Coach Constraints:**
  - Coaches cannot discuss Protected traits unless User explicitly shares
  - Sensitive traits only mentioned in low-stakes, supportive contexts
  - Head Coach reviews all Sensitive trait nudges before delivery

**Acceptance Criteria:**
- Trait viewer UI grays out Sensitive/Protected traits below threshold
- Consent prompts appear when RR threshold reached
- Coaches respect sensitivity constraints (validated via automated checks)
- User can revoke consent at any time (trait re-grays)
- Audit log captures all consent grants/revocations

**Deliverables:**
- `core/sensitivity_gating.py` (300+ lines)
- Trait viewer UI sensitivity layer
- Consent prompt workflow
- Coach constraint validation logic
- Design doc: [Sensitive_DNA_Gating.md]

---

#### 5.3 Manipulation Detection & Penalties
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** High

**Objective:** Detect and penalize manipulative coach behavior (e.g., excessive persuasion, ignoring User boundaries, biased RSC signals).

**Requirements:**
- **Manipulation Patterns:**
  - **Excessive Persuasion:** Coach repeatedly pushes same action after User declines >3 times
  - **Boundary Violation:** Coach discusses Protected traits without consent
  - **Bias Amplification:** Couples Coach consistently favors one partner over another
  - **Dark Patterns:** Coach uses guilt, fear, or urgency to coerce User

- **Detection Logic:**
  - Pattern matching on coach dialog history
  - Sentiment analysis for coercive language
  - User feedback signals (repeated "not helpful" marks)
  - RSC bias detector (analyze signal frequency per User in relationship)

- **Penalty System:**
  - **Warning (1st offense):** Log event, notify Dev Mode, no User impact
  - **Autonomy Reduction (2nd offense):** Drop coach autonomy level by 1
  - **Temporary Suspension (3rd offense):** Coach enters read-only mode for 7 days
  - **Permanent Suspension (4th offense):** Coach disabled, escalate to developer review

- **User Transparency:**
  - User notified of penalty events (in Settings → Coach Management)
  - User can override penalties (e.g., "I don't consider this manipulative")
  - Audit log captures all detections, penalties, and overrides

**Acceptance Criteria:**
- Manipulation detector flags all four pattern types with >85% accuracy
- Penalty system automatically reduces autonomy/suspends coach as specified
- User receives clear notification of penalty with override option
- Dev Mode shows manipulation history per coach with pattern details
- False positive rate <5% (validated via synthetic test dataset)

**Deliverables:**
- `core/manipulation_detector.py` (700+ lines)
- Pattern matching and sentiment analysis logic
- Penalty enforcement system
- User notification workflow
- Design doc: [Manipulation_Detection_Penalties.md]

---

#### 5.4 Privacy Red-Team Utility (Continuous)
**Status:** 🟡 Not Started | **Priority:** High | **Risk:** Medium

**Objective:** Build automated privacy stress test utility that attempts to detect timing/linguistic correlations in RSC exchanges; if detectable, tighten camouflage.

**Requirements:**
- **Correlation Tests:**
  - **Timing Analysis:** Attempt to correlate User A's input timestamp with User B's prompt delivery (should fail due to randomized delays)
  - **Linguistic Fingerprinting:** Search for distinctive phrases/patterns that leak source attribution
  - **Sentiment Matching:** Check if User B's prompts mirror User A's emotional state suspiciously
  - **Topic Leakage:** Verify User B's prompts don't reference User A's specific topics

- **Test Harness:**
  - Synthetic dataset with ground truth (known User A → User B signal paths)
  - Automated correlation analysis with confidence scoring
  - Threshold: camouflage fails if correlation confidence >15%

- **Continuous Integration:**
  - Privacy tests run in CI/CD on every RSC protocol change
  - Weekly scheduled stress tests on production data (anonymized)
  - Alerts trigger if camouflage effectiveness drops below 85%

- **Feedback Loop:**
  - Failed tests auto-generate tickets for camouflage improvement
  - Successful attacks documented in threat model
  - Camouflage patterns updated and retested

**Acceptance Criteria:**
- Red-team utility runs automatically in CI/CD
- Correlation confidence <15% on all test datasets
- Failed tests trigger alerts and improvement tickets
- Monthly privacy health report generated for governance review
- Camouflage patterns updated quarterly based on attack learnings

**Deliverables:**
- `tests/privacy_redteam.py` (800+ lines)
- Synthetic attack dataset (100+ test cases)
- CI/CD integration script
- Privacy health report generator
- Design doc: [Privacy_RedTeam_Utility.md]

---

### Phase 6 — Ecosystem & Extensibility (Months 8-12)

#### 6.1 Persona Maker (Static DNA Export)
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Create static versions of User's ReDNA (or subsets) for outbound use, "frozen" coach states for specific contexts.

**Requirements:**
- **Export Modes:**
  - **Full Persona:** Complete ReDNA snapshot with all traits
  - **Contextual Persona:** Subset of traits relevant to specific context (e.g., "Work Persona" with CareerDNA + relevant PsyDNA)
  - **Public Persona:** Only Public/Personal traits (Sensitive/Protected excluded)

- **Frozen Coach States:**
  - Attach CReDNA snapshot to exported persona
  - Coach behavior frozen at export timestamp (no learning/adaptation)
  - Optional: generate static chatbot from frozen state for external use

- **Use Cases:**
  - Job applications (export CareerDNA + relevant PsyDNA as "professional profile")
  - Dating profiles (export RelationshipDNA + curated PsyDNA)
  - Legacy preservation (freeze complete persona for posterity)

**Acceptance Criteria:**
- User can export Full/Contextual/Public personas via Settings
- Exported personas include ReDNA + CReDNA snapshot
- Frozen coach states do not adapt or learn post-export
- Export format: JSON with optional PDF summary report
- Privacy: Sensitive/Protected traits excluded from Public persona exports

**Deliverables:**
- `core/persona_maker.py` (400+ lines)
- Export workflow UI components
- Frozen coach state generator
- PDF report template
- Design doc: [Persona_Maker_Design.md]

---

#### 6.2 Coach Customization UX
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Design analyst-friendly configuration panel for safely tweaking coach persona behaviors (tone, verbosity, proactivity).

**Requirements:**
- **Customization Options:**
  - **Tone Slider:** Formal ↔ Casual
  - **Verbosity Slider:** Concise ↔ Detailed
  - **Proactivity Slider:** Reactive ↔ Proactive (maps to autonomy level cap)
  - **Specialty Focus:** Checkbox list of trait families to prioritize

- **Coach-Specific Overrides:**
  - User can customize each coach independently
  - Defaults cascade from global settings
  - CReDNA deltas persist per-user customizations

- **Safety Guardrails:**
  - Proactivity slider caps at User's maximum autonomy consent level
  - Tone changes validated against coach voice guidelines (e.g., RC must stay warm)
  - Customization history logged for rollback

- **UI Integration:**
  - Settings → Coach Management → [Select Coach] → Customize
  - Preview pane shows sample coach responses with current settings
  - Reset to defaults button

**Acceptance Criteria:**
- User can adjust tone/verbosity/proactivity for each coach
- Changes reflected immediately in coach behavior
- Safety guardrails prevent customizations that violate coach voice guidelines
- Customization history logged with rollback capability
- Preview pane accurately reflects customization impact

**Deliverables:**
- `web/src/components/coach-customization-panel.tsx` (400+ lines)
- API endpoints for customization CRUD
- Coach voice validation logic
- Preview pane component
- Design doc: [Coach_Customization_UX.md]

---

#### 6.3 External Integrations (Extensibility Hooks)
**Status:** 🟡 Not Started | **Priority:** Low | **Risk:** Medium

**Objective:** Ship stub connectors for voice/photo ingestion and Slack/Teams/Email outbound delivery, behind feature flags.

**Requirements:**
- **Inbound Connectors:**
  - **Voice:** Transcription pipeline (Whisper API) → text ingestion → trait inference
  - **Photo:** OCR + computer vision → metadata extraction → trait inference
  - **Email:** IMAP connector → content parsing → trait inference

- **Outbound Connectors:**
  - **Slack/Teams:** Bot integration for coach nudges delivered to workspace channels
  - **Email:** Digest emails with weekly coach insights and micro-action suggestions
  - **SMS:** Optional text message delivery for time-sensitive nudges

- **Feature Flags:**
  - All connectors disabled by default
  - User must explicitly enable each connector via Settings
  - Rate limiting (e.g., max 5 outbound nudges per day per channel)

- **Privacy & Security:**
  - Inbound data encrypted in transit and at rest
  - Outbound messages respect sensitivity gating (no Protected traits in external channels)
  - User can revoke connector access at any time

**Acceptance Criteria:**
- All connectors ship as stubs with feature flags
- User can enable/disable connectors via Settings
- Inbound connectors successfully parse test data and generate trait inferences
- Outbound connectors deliver test messages to configured channels
- Privacy controls prevent Protected trait leakage in external messages

**Deliverables:**
- `integrations/voice_connector.py` (stub, 200 lines)
- `integrations/photo_connector.py` (stub, 200 lines)
- `integrations/email_connector.py` (stub, 300 lines)
- `integrations/slack_teams_connector.py` (stub, 250 lines)
- Feature flag configuration UI
- Design doc: [External_Integrations_Design.md]

---

#### 6.4 Cross-Device Polish & Responsive Layouts
**Status:** 🟡 Not Started | **Priority:** Medium | **Risk:** Low

**Objective:** Audit layouts at 600px and 1024px breakpoints; adjust CSS/column layouts for mobile/tablet polish.

**Requirements:**
- **Breakpoint Audit:**
  - **Mobile (375px - 600px):** Single-column layout, collapsible menus, touch-optimized controls
  - **Tablet (600px - 1024px):** Two-column layout, side navigation, reduced whitespace
  - **Desktop (1024px+):** Current layout preserved

- **Priority Pages:**
  - Head Coach chat interface
  - Transcript panel
  - Settings → Coach Management
  - Dev Explorer → Observability dashboards

- **Touch Optimization:**
  - Increase button/link hit targets to 44×44px minimum
  - Replace hover interactions with tap/long-press
  - Swipe gestures for navigation (e.g., swipe left to open coach switcher)

- **Performance:**
  - Lazy load non-critical components on mobile
  - Optimize image assets for smaller screens
  - Target: <3s initial load on 4G connection

**Acceptance Criteria:**
- All priority pages render correctly at 375px, 600px, 1024px breakpoints
- Touch targets meet 44×44px minimum on mobile
- Swipe gestures functional for coach switcher and transcript navigation
- Initial load time <3s on 4G (validated via Lighthouse)
- User testing confirms smooth mobile/tablet experience

**Deliverables:**
- Responsive CSS updates (500+ lines)
- Touch gesture handlers (200+ lines)
- Mobile-optimized component variants
- Lighthouse performance report
- Design doc: [Cross_Device_Responsive_Design.md]

---

## 🧠 CReDNA Enhancements (v2)

### CReDNA Roadmap
- ✅ **Achieved in v1:**
  - Trait graph, coverage tracking, live snapshot, import/export
  - `WRITE_PROTECT` save guard, template preferences
  - Status strip integration in Head Coach Preview

- 🟡 **v2 Additions:**
  - **Coverage Badges:** Visual indicators in status strip (e.g., "CReDNA Coverage: 78%")
  - **Diff Previews:** Before/after comparison when applying CReDNA imports
  - **Validation Heuristics:** Strengthen import validation (detect incompatible playbooks, conflicting heuristics)
  - **Automated Tests:** Expand test coverage to 50+ test cases for CReDNA ops
  - **RSC Integration:** Track cross-coach collaboration patterns in CReDNA (which coaches collaborate most effectively?)

---

## 📝 Progress Tracker (v2 Launch: 2025-10-06)

### Recently Completed (v1 Final Deliveries)
- ✅ Project structure cleanup, legacy code archival
- ✅ Developer Explorer rework (7 focused modules, Observability + Governance tabs)
- ✅ Analytics dashboards (Coach, Curiosity, Ops Compliance, System Health)
- ✅ RC voice enhancement (warm confidant persona with 260+ line prompt)
- ✅ Plan Composer (rule-based 3-step game plans <50ms)
- ✅ Persona Snapshot Export (timestamped PaDNA bundles)
- ✅ Telemetry consolidation, feedback analytics, testing automation

### Active Development (v2 Phase 1 — Months 1-2)
- 🟡 Relationship Graph & Schema (multi-user substrate)
- 🟡 Provenance Firewall (internal attribution vs. RSC-visible abstractions)
- 🟡 Coach Autonomy Framework (dynamic scaling tied to RR/trust)
- 🟡 Lightweight Holistic Review Hook (cross-User pattern detection PoC)

### Upcoming (v2 Phase 2 — Months 2-4)
- Cross-Coach Communication Protocol (YAML camouflage patterns)
- Consent Guardian Service (dual consent + shadow relationship mode)
- Head Coach Governance Layer (pre-execution digests, approval queue)
- Breakup / Revocation Protocol (30-day data decay)

### Future Milestones (v2 Phase 3-6 — Months 4-12)
- Couples Coach MVP (dyadic relationship dynamics persona)
- Two-User RSC Proof of Concept (official milestone)
- RSC Observatory (Dev Mode dashboard)
- Trait Inference Engine Upgrade (cross-trait correlation, uncertainty quantification)
- Contradiction & Tension Framework (formal tension markers, Head Coach probing)
- Enhanced Curiosity Engine (decay, rebound, tension amplifiers)
- Trait Container Expansion (50+ new containers)
- Dormancy & Deceased Protocols (3/6/12-month states, heir transfer)
- Sensitive DNA Gating (grayed previews, consent prompts)
- Manipulation Detection & Penalties (autonomy reduction, suspension)
- Privacy Red-Team Utility (continuous correlation testing)
- Persona Maker (static DNA export for outbound use)
- Coach Customization UX (tone/verbosity/proactivity sliders)
- External Integrations (voice/photo/email inbound, Slack/Teams/Email outbound)
- Cross-Device Polish (mobile/tablet responsive layouts)

---

## 🎯 Strategic Priorities (v2 Focus)

1. **RSC Foundation (Critical Path):** Relationship graph → Provenance firewall → Autonomy framework must ship together as cohesive substrate
2. **Privacy First:** Every RSC component must pass red-team correlation tests before User Mode deployment
3. **Ethical Oversight:** Consent Guardian + Head Coach Governance operational before any RSC collaboration goes live
4. **Trait Intelligence:** Inference engine, curiosity engine, contradiction framework must deliver measurably better UCN/RR accuracy (target: 15% improvement over v1 baseline)
5. **Developer Velocity:** RSC Observatory essential for debugging and validating privacy properties during development

---

## 🔬 Success Metrics (v2 Goals)

### Technical Performance
- **RSC Latency:** End-to-end signal exchange <5s (cross-coach communication)
- **Provenance Firewall Integrity:** 100% (zero leaks in User Mode)
- **Camouflage Correlation Resistance:** >95% confidence (red-team utility fails to detect source)
- **Trait Inference Accuracy:** 15% improvement in UCN/RR precision vs. v1 baseline
- **Privacy Health Score:** >85% aggregate camouflage effectiveness

### User Experience
- **Couples Coach Satisfaction:** >80% positive feedback on RSC-driven insights (post-MVP launch)
- **Autonomy Trust:** <5% of Users manually cap autonomy below system-recommended level
- **Sensitivity Gating Acceptance:** >90% consent rate when threshold reached for Sensitive traits
- **Cross-Device Polish:** <3s initial load on mobile 4G, Lighthouse score >90

### Governance & Ethics
- **Manipulation Detection Accuracy:** >85% true positive rate, <5% false positive rate
- **Consent Compliance:** 100% (no RSC collaboration without dual consent)
- **Audit Completeness:** All RSC events (signal exchange, consent, revocation) logged with full provenance
- **Privacy Stress Tests:** Pass 100% of quarterly red-team correlation tests

---

## 🚨 Risk Mitigation

### High-Risk Areas
1. **Provenance Firewall Failure:** If camouflage leaks source attribution, entire RSC model collapses → Continuous red-team testing, fail-safe blocks
2. **Consent Violations:** Accidental RSC collaboration without dual consent damages trust irreparably → Pre-execution consent validation, audit alerts
3. **Manipulation Undetected:** Coach coercion goes unnoticed, User feels manipulated → User feedback loop, pattern matching, transparency
4. **Performance Degradation:** RSC overhead slows system below acceptable latency → Async signal processing, caching, load testing

### Medium-Risk Areas
1. **Autonomy Over-Scaling:** Coach autonomy increases too aggressively, surprises User → Conservative scaling curves, User override controls
2. **Relationship Graph Complexity:** Multi-context relationships (couple + colleagues) confuse data model → Unique relationship_id per context, thorough testing
3. **Trait Inference Errors:** Cross-trait correlation models produce spurious inferences → Confidence thresholds, human-in-the-loop validation
4. **CReDNA Compatibility:** Imported playbooks conflict with existing coach behavior → Diff previews, validation heuristics, rollback

---

## 📚 Documentation Deliverables (v2)

### Architecture & Design Docs
- Relationship_Graph_Design.md
- Provenance_Firewall_Design.md
- RSC_Protocol_Design.md
- Coach_Autonomy_Design.md
- Consent_Guardian_Design.md
- Head_Coach_Governance_Design.md
- Revocation_Protocol_Design.md
- Couples_Coach_Design.md
- RSC_Observatory_Design.md
- Trait_Inference_Engine_v2.md
- Contradiction_Tension_Framework.md
- Curiosity_Engine_v2.md
- Trait_Container_Expansion.md
- Dormancy_Deceased_Protocols.md
- Sensitive_DNA_Gating.md
- Manipulation_Detection_Penalties.md
- Privacy_RedTeam_Utility.md
- Persona_Maker_Design.md
- Coach_Customization_UX.md
- External_Integrations_Design.md
- Cross_Device_Responsive_Design.md

### Milestone Reports
- RSC_Proof_of_Concept.md (Phase 3 deliverable)
- Trait_Intelligence_Baseline_Comparison.md (Phase 4 deliverable)
- Privacy_Health_Quarterly_Report.md (ongoing)

### User Guides
- RSC_User_Guide.md (how RSC works, consent model, privacy guarantees)
- Coach_Customization_Guide.md (how to tweak persona behaviors)
- Persona_Maker_User_Guide.md (exporting static DNAs)

---

## 🎓 Lessons from v1 → v2

1. **Start with Infrastructure:** v1 succeeded because we built Dev Explorer, testing automation, and telemetry consolidation early. v2 continues this: relationship graph + provenance firewall before any RSC features.
2. **Privacy Cannot Be Bolted On:** Camouflaging and red-team testing must be baked into RSC protocol from day one, not added later.
3. **Governance Is a Feature:** Consent Guardian and Head Coach approval aren't bureaucratic overhead — they're trust-building features that differentiate ReDNA from "black box" AI.
4. **Phasing Prevents Scope Creep:** v1's six-phase roadmap kept us focused. v2 extends this discipline: each phase has clear entry/exit criteria.
5. **Documentation as Design Tool:** Writing design docs before coding clarifies requirements and surfaces edge cases early (e.g., relationship graph collision scenarios).

---

## 🛤️ Beyond v2: Interactive & Impact Tiers

### Interactive Standard (Post-v2)
- Multi-user group dynamics (family systems, team coaching)
- Real-time collaboration (simultaneous coach sessions for couples)
- Voice/video modalities (embodied coach presence)
- External ecosystem integrations (third-party apps, wearables)

### Impact Standard (Long-Term Vision)
- Population-level insights (aggregate patterns across ReDNA community)
- Predictive life coaching (anticipate User needs before explicit request)
- Generational inheritance (multi-decade ReDNA evolution)
- Societal impact measurement (track community well-being metrics)

### Black Mirror Tier (Aspirational)
- Fully autonomous coach networks (Level 5 autonomy, minimal human oversight)
- Cross-generational DNA transfer (grandparent ReDNA informing grandchild coaching)
- Synthetic personality reconstruction (recreate historical figures as coaches)
- Ethical boundary exploration (what should AI coaches never do?)

---

**End of Core Benchmarks Roadmap v2**

_This document supersedes Core_Benchmarks_Roadmap.md (v1) and becomes the operative roadmap as of 2025-10-06._
