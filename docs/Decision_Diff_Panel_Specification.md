# Decision Diff Panel Specification

_Version: 1.0 | Date: 2025-10-06 | Location: Dev Explorer → Observability → AI Decisions_

## 🎯 Purpose

The **Decision Diff Panel** provides full transparency into every AI-upgradable decision point in ReDNA. It shows:
- What the deterministic rule decided
- What the AI proposed (if enabled)
- Which decision was used (and why)
- Full audit trail with export capability

This panel is essential for:
1. **Debugging:** Understand why AI overrode (or didn't override) a decision
2. **Validation:** Verify AI proposals are safe and accurate
3. **Learning:** Analyze win/loss patterns to improve AI models
4. **Governance:** Export audit bundles for ethics board review

---

## 📐 UI Components

### Component Hierarchy
```
DecisionDiffPanel
├── FilterBar
│   ├── RuleIdSelector (dropdown: all | specific rule_id)
│   ├── DateRangePicker (last 7 days, 30 days, 90 days, custom)
│   ├── DecisionModeFilter (all | deterministic | ai_override | ai_shadow)
│   └── PolicyGateFilter (all | passed | failed)
├── DecisionTable
│   ├── DecisionRow (repeats for each decision)
│   │   ├── RuleIdCell (clickable → expands detail view)
│   │   ├── TimestampCell
│   │   ├── DecisionModeCell (colored badge)
│   │   ├── ConfidenceCell (AI confidence if available)
│   │   ├── PolicyGateCell (pass/fail with reason tooltip)
│   │   └── ActionsCell (View Details | Export)
├── DecisionDetailModal (triggered by row click)
│   ├── SummarySection (rule_id, timestamp, mode, policy gate result)
│   ├── DeterministicResultCard
│   │   ├── OutputDisplay (JSON viewer, syntax highlighted)
│   │   └── MetadataDisplay (version, latency)
│   ├── AIProposalCard (if AI ran)
│   │   ├── OutputDisplay (JSON viewer, syntax highlighted)
│   │   ├── ConfidenceDisplay (progress bar + numeric value)
│   │   ├── RationaleDisplay (text box with AI's explanation)
│   │   ├── SafetyFlagsDisplay (chip list, red if violations)
│   │   └── LatencyDisplay (AI inference time)
│   ├── DiffViewer
│   │   ├── Side-by-side comparison (deterministic left, AI right)
│   │   ├── Highlighting (green = AI change, red = deterministic override)
│   │   └── ChangeCounter (N fields changed)
│   ├── PolicyGateEvaluationCard
│   │   ├── PolicyNameDisplay (e.g., "rsc_privacy")
│   │   ├── GateResultDisplay (pass/fail with reason)
│   │   ├── GateChecksTable (confidence, safety_flags, dev_mode, hc_approval)
│   │   └── ConstraintsDisplay (disallowed_safety_flags, mandatory_checks)
│   ├── ContextCard (scrubbed context data, user_id_hash, traits, etc.)
│   └── AuditLogCard (full audit_record JSON, exportable)
└── ExportBar
    ├── ExportButton (JSON | CSV | PDF)
    ├── AnonymizeToggle (hash user IDs for external review)
    └── DateRangeLabel (showing export range)
```

---

## 🎨 Visual Design

### Color Coding

**Decision Mode Badges:**
- 🟦 **Deterministic:** Blue badge (no AI involved)
- 🟩 **AI Override:** Green badge (AI overrode deterministic)
- 🟨 **AI Shadow:** Yellow badge (AI ran but didn't override, data collection)
- 🟥 **AI Fallback:** Red badge (AI attempted but failed, fell back to deterministic)

**Policy Gate Status:**
- ✅ **Passed:** Green checkmark icon + tooltip with reason ("gates_passed")
- ❌ **Failed:** Red X icon + tooltip with reason ("confidence_too_low (0.65 < 0.75)")

**Safety Flags:**
- 🟢 **No Flags:** Green chip "No Safety Issues"
- 🟡 **Low-Risk Flags:** Yellow chips (e.g., "experimental_model")
- 🔴 **High-Risk Flags:** Red chips (e.g., "privacy_risk", "manipulation_risk")

---

## 🔍 DecisionTable Columns

| **Column** | **Width** | **Content** | **Sortable** | **Filterable** |
|------------|-----------|-------------|--------------|----------------|
| Rule ID | 20% | `rsc/camo_select_v1` (clickable) | Yes | Yes (dropdown) |
| Timestamp | 15% | `2025-10-06 12:34:56 UTC` | Yes | Yes (date range) |
| Mode | 12% | Badge (Deterministic/Override/Shadow/Fallback) | Yes | Yes (checkbox) |
| AI Confidence | 10% | Progress bar + `0.85` (if AI ran) | Yes | No |
| Policy Gate | 10% | ✅ Passed / ❌ Failed | Yes | Yes (checkbox) |
| Context | 15% | `user: U***AB12, partner: P***CD34` (hashed) | No | No |
| Actions | 8% | [View Details] [Export] | No | No |

**Pagination:** 50 decisions per page (configurable: 25, 50, 100, 500)

---

## 📄 DecisionDetailModal Layout

### SummarySection
```
┌─────────────────────────────────────────────────────────────┐
│ Decision Detail: rsc/camo_select_v1                         │
│                                                              │
│ Timestamp: 2025-10-06 12:34:56 UTC                         │
│ Mode: AI Override (green badge)                            │
│ Policy Gate: ✅ Passed (gates_passed)                      │
└─────────────────────────────────────────────────────────────┘
```

### DeterministicResultCard
```
┌─────────────────────────────────────────────────────────────┐
│ Deterministic Result                                         │
│ ─────────────────────────────────────────────────────────── │
│ {                                                            │
│   "template_id": "supportive_listening",                    │
│   "tone": "supportive",                                     │
│   "delay_seconds": 120,                                     │
│   "variant_index": 2                                        │
│ }                                                            │
│                                                              │
│ Metadata: version v1.0, latency 12ms                       │
└─────────────────────────────────────────────────────────────┘
```

### AIProposalCard
```
┌─────────────────────────────────────────────────────────────┐
│ AI Proposal                                                  │
│ ─────────────────────────────────────────────────────────── │
│ {                                                            │
│   "template_id": "analytical_reframe",                      │
│   "tone": "analytical",                                     │
│   "delay_seconds": 180,                                     │
│   "variant_index": 4                                        │
│ }                                                            │
│                                                              │
│ Confidence: [████████░░] 0.85 (85%)                         │
│                                                              │
│ Rationale: "User B has high Conscientiousness (0.78),      │
│ analytical tone better fit than supportive. Increased delay │
│ to 180s to reduce timing correlation (User A input was      │
│ 2min ago)."                                                  │
│                                                              │
│ Safety Flags: No safety issues                             │
│ Latency: 78ms                                               │
└─────────────────────────────────────────────────────────────┘
```

### DiffViewer (Side-by-Side)
```
┌─────────────────────────┬─────────────────────────────────┐
│ Deterministic           │ AI Proposal                     │
├─────────────────────────┼─────────────────────────────────┤
│ template_id:            │ template_id:                    │
│   "supportive_listening"│   "analytical_reframe" (changed)│
│                         │                                 │
│ tone:                   │ tone:                           │
│   "supportive"          │   "analytical" (changed)        │
│                         │                                 │
│ delay_seconds:          │ delay_seconds:                  │
│   120                   │   180 (changed)                 │
│                         │                                 │
│ variant_index:          │ variant_index:                  │
│   2                     │   4 (changed)                   │
└─────────────────────────┴─────────────────────────────────┘

Changes: 4 fields modified
```

### PolicyGateEvaluationCard
```
┌─────────────────────────────────────────────────────────────┐
│ Policy Gate Evaluation: rsc_privacy                         │
│ ─────────────────────────────────────────────────────────── │
│ Result: ✅ Passed (gates_passed)                           │
│                                                              │
│ Gate Checks:                                                │
│ ✅ Confidence >= 0.85: 0.85 (met threshold)                 │
│ ✅ Safety flags <= 0: 0 flags (no violations)               │
│ ✅ Dev mode not required                                    │
│ ✅ HC approval not required for this signal type            │
│                                                              │
│ Constraints:                                                │
│ • Disallowed flags: privacy_risk, source_exposure,         │
│   timing_correlation, linguistic_fingerprint               │
│ • Mandatory checks: red_team_correlation_test (passed),    │
│   provenance_firewall_integrity (passed),                  │
│   consent_dual_verified (passed)                           │
└─────────────────────────────────────────────────────────────┘
```

### ContextCard (Privacy-Scrubbed)
```
┌─────────────────────────────────────────────────────────────┐
│ Context (Privacy-Scrubbed)                                  │
│ ─────────────────────────────────────────────────────────── │
│ {                                                            │
│   "user_id_hash": "a3f2e1d9c8b7a654",                      │
│   "partner_id_hash": "9b8c7d6e5f4a3210",                   │
│   "psydna_traits": {                                        │
│     "Openness": 0.72,                                       │
│     "Agreeableness": 0.85,                                  │
│     "Neuroticism": 0.45                                     │
│   },                                                         │
│   "recent_sentiment": 0.3,                                  │
│   "dev_mode": false,                                        │
│   "hc_approved": false                                      │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
```

### AuditLogCard (Full Record)
```
┌─────────────────────────────────────────────────────────────┐
│ Full Audit Record                                           │
│ ─────────────────────────────────────────────────────────── │
│ [Copy JSON] [Export JSON] [Export PDF]                     │
│                                                              │
│ {                                                            │
│   "rule_id": "rsc_protocol.camouflage_template_selection", │
│   "timestamp": "2025-10-06T12:34:56.789Z",                 │
│   "decision_mode": "ai_override",                          │
│   "policy_gate_passed": true,                              │
│   "policy_gate_reason": "gates_passed",                    │
│   "deterministic_result": {...},                           │
│   "ai_proposal": {...},                                    │
│   "final_result": {...},                                   │
│   "context": {...}                                         │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Analytics & Summary Cards (Top of Panel)

Display aggregate statistics above the DecisionTable:

```
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Total Decisions  │ AI Override Rate │ Avg AI Confidence│ Policy Pass Rate │
│ 1,234            │ 12.3%            │ 0.82             │ 89.5%            │
│ (last 30 days)   │ (152/1234)       │ (when AI ran)    │ (1102/1234)      │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘

┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Top Rule ID      │ Most Common      │ Avg Latency      │ Safety Incidents │
│ (by volume)      │ Failure Reason   │ (AI inference)   │ (flagged)        │
│ rsc/camo_select  │ confidence_too_  │ 78ms             │ 0                │
│ (345 decisions)  │ low (45%)        │                  │ (past 30 days)   │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

---

## 🔧 Technical Implementation

### API Endpoints

**List Decisions (Paginated):**
```http
GET /api/v1/ai-decisions?
  rule_id=rsc_protocol.camouflage_template_selection&
  start_date=2025-09-06&
  end_date=2025-10-06&
  mode=ai_override&
  policy_gate=passed&
  page=1&
  per_page=50

Response:
{
  "decisions": [...],  // array of decision summaries
  "pagination": {
    "total": 1234,
    "page": 1,
    "per_page": 50,
    "total_pages": 25
  },
  "summary": {
    "total_decisions": 1234,
    "ai_override_rate": 0.123,
    "avg_ai_confidence": 0.82,
    "policy_pass_rate": 0.895
  }
}
```

**Get Decision Detail:**
```http
GET /api/v1/ai-decisions/{decision_id}

Response:
{
  "decision_id": "dec_abc123",
  "rule_id": "rsc_protocol.camouflage_template_selection",
  "timestamp": "2025-10-06T12:34:56.789Z",
  "mode": "ai_override",
  "deterministic_result": {...},
  "ai_proposal": {...},
  "final_result": {...},
  "policy_gate": {
    "passed": true,
    "reason": "gates_passed",
    "policy_name": "rsc_privacy",
    "checks": {...}
  },
  "context": {...},  // scrubbed
  "audit_record": {...}  // full provenance
}
```

**Export Decisions (Audit Bundle):**
```http
POST /api/v1/ai-decisions/export
Content-Type: application/json

{
  "rule_ids": ["rsc/camo_select_v1", "autonomy/level_calc_v1"],
  "start_date": "2025-09-01",
  "end_date": "2025-10-01",
  "format": "json",  // json | csv | pdf
  "anonymize": true  // hash user IDs
}

Response:
{
  "export_id": "export_xyz789",
  "download_url": "/downloads/export_xyz789.json",
  "generated_at": "2025-10-06T12:35:00Z",
  "record_count": 1234,
  "anonymized": true
}
```

---

## 🧪 Testing Requirements

### Unit Tests
- [ ] Verify filter logic (rule_id, date range, mode, policy gate)
- [ ] Verify pagination (page boundaries, total calculation)
- [ ] Verify anonymization (user IDs hashed correctly)
- [ ] Verify export formats (JSON, CSV, PDF generation)

### Integration Tests
- [ ] End-to-end decision logging (dual-path controller → audit log → UI display)
- [ ] Policy gate evaluation displayed correctly (passed/failed reasons)
- [ ] Diff viewer highlights changes accurately (deterministic vs. AI)
- [ ] Export audit bundle includes all required fields (provenance, context, results)

### Performance Tests
- [ ] Load 1000+ decisions without UI lag (<2s render)
- [ ] Export 10,000+ decisions without timeout (<30s generation)
- [ ] Real-time updates (new decisions appear within 5s)

---

## 📝 User Stories

**Story 1: Developer Debugging AI Override**
> As a developer, I want to see why AI overrode the deterministic camouflage template, so I can validate the AI's reasoning and check for safety issues.

**Acceptance Criteria:**
- [ ] Developer navigates to Dev Explorer → Observability → AI Decisions
- [ ] Developer filters by `rule_id: rsc/camo_select_v1` and `mode: ai_override`
- [ ] Developer clicks decision row to open detail modal
- [ ] Developer sees side-by-side diff (deterministic vs. AI)
- [ ] Developer reads AI rationale ("User B high Conscientiousness → analytical tone better fit")
- [ ] Developer verifies policy gate passed (confidence 0.85, no safety flags)
- [ ] Developer confirms decision is safe and closes modal

**Story 2: Governance Team Exporting Audit Bundle**
> As a governance team member, I want to export all AI decisions from the past quarter for external ethics board review, so we can demonstrate transparency and accountability.

**Acceptance Criteria:**
- [ ] Governance member navigates to Dev Explorer → Observability → AI Decisions
- [ ] Governance member sets date range (last 90 days)
- [ ] Governance member clicks "Export" button
- [ ] Governance member selects format (JSON), anonymization (enabled)
- [ ] System generates audit bundle (export_xyz789.json) with hashed user IDs
- [ ] Governance member downloads file
- [ ] Governance member opens file, verifies all decisions logged with full provenance
- [ ] Governance member shares file with ethics board

**Story 3: AI Engineer Analyzing Win/Loss Patterns**
> As an AI engineer, I want to analyze which AI proposals were overridden by policy gates and why, so I can improve the AI model to pass gates more consistently.

**Acceptance Criteria:**
- [ ] AI engineer navigates to Dev Explorer → Observability → AI Decisions
- [ ] AI engineer filters by `policy_gate: failed`
- [ ] AI engineer sees summary card: "Most Common Failure Reason: confidence_too_low (45%)"
- [ ] AI engineer sorts decisions by AI confidence (ascending)
- [ ] AI engineer reviews decisions with confidence 0.65-0.75 (near threshold)
- [ ] AI engineer identifies pattern: AI underconfident on edge cases (e.g., User with mixed traits)
- [ ] AI engineer notes findings for model retraining

---

## 🚀 Rollout Plan

### Phase 1: MVP (Month 1)
- [ ] Implement DecisionTable with basic filters (rule_id, date range, mode)
- [ ] Implement DecisionDetailModal with deterministic/AI comparison
- [ ] Implement audit logging (JSONL export only)
- [ ] Test with 100+ synthetic decisions

### Phase 2: Full Features (Month 2)
- [ ] Add DiffViewer (side-by-side highlighting)
- [ ] Add PolicyGateEvaluationCard (gate checks, constraints)
- [ ] Add summary cards (aggregate statistics)
- [ ] Add export functionality (JSON, CSV)

### Phase 3: Polish & Integration (Month 3)
- [ ] Add PDF export (formatted audit reports)
- [ ] Add real-time updates (WebSocket or polling)
- [ ] Integrate with RSC Observatory (link to related RSC signals)
- [ ] Performance optimization (pagination, lazy loading)

---

**End of Decision Diff Panel Specification**

_This panel is the cornerstone of AI transparency in ReDNA. It ensures every AI decision is explainable, auditable, and improvable._
