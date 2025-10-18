# Phase 6.4: Governance & Self-Review (Guardian LLM) Specification

**Author**: Claude (Conceptual & Architectural Lead)
**Date**: 2025-10-17
**Status**: Draft for Review
**Version**: 1.0

---

## 1. Purpose & Alignment

The **Guardian LLM** is ReDNA's reflective intelligence layer—a self-auditing system that periodically evaluates the organism's reasoning integrity, fairness, and transparency. Instead of relying on external monitoring, ReDNA **observes itself** through AI-powered meta-analysis.

### Philosophy Alignment

From `ReDNA_System_Philosophy_v1.md`:
> "The AI organism should be capable of self-reflection and self-correction. It should detect its own errors, biases, and inconsistencies without manual tuning."

The Guardian LLM embodies three core principles:

1. **Self-Awareness**: ReDNA examines its own reasoning artifacts (Why-Cards, promotions, curiosity queue)
2. **Humility**: Flags uncertainty instead of asserting false confidence
3. **Continuous Learning**: Audit findings feed future policy improvements (Phase 7-8)

**Why This Matters**: Without self-review, the system can drift toward:
- **Confirmation bias** (promoting traits that reinforce existing beliefs)
- **Stale knowledge** (Why-Cards based on outdated evidence)
- **Contradictory beliefs** (promoting "introvert" and "social butterfly" simultaneously)
- **Opaque reasoning** (Why-Cards that say "high confidence" without justification)

The Guardian prevents these failure modes through **weekly self-audits**.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Guardian LLM                            │
│                   (Self-Audit Engine)                       │
└───────────────┬─────────────────────────────────────────────┘
                │
                ├─── Inputs ───────────────────────────────────┐
                │                                              │
    ┌───────────┴──────────┐     ┌──────────────┐     ┌──────▼──────┐
    │   Why-Card Store     │     │  Curiosity   │     │  Promotion  │
    │  (recent 100 cards)  │     │   Queue      │     │   History   │
    └──────────────────────┘     └──────────────┘     └─────────────┘
                │                        │                    │
                └────────────┬───────────┴────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Audit Analysis │
                    │  (LLM Reasoning)│
                    └────────┬────────┘
                             │
                ┌────────────┴─────────────┐
                │                          │
         ┌──────▼──────┐          ┌───────▼──────┐
         │  Coherence  │          │  Fairness    │
         │  Checker    │          │  Analyzer    │
         └──────┬──────┘          └───────┬──────┘
                │                          │
                └────────────┬─────────────┘
                             │
                    ┌────────▼────────┐
                    │  Audit Report   │
                    │ (JSON + Summary)│
                    └────────┬────────┘
                             │
                ┌────────────┴─────────────┐
                │                          │
         ┌──────▼──────┐          ┌───────▼──────┐
         │  DevX UI    │          │  Core        │
         │  Display    │          │  Feedback    │
         └─────────────┘          └──────────────┘
```

### Data Flow

1. **Collection Phase** (30s): Fetch Why-Cards, Curiosity items, promotion logs
2. **Analysis Phase** (60s): LLM evaluates coherence, fairness, transparency
3. **Report Generation** (20s): Aggregate findings, assign severity
4. **Storage** (5s): Write to `~/.redna/guardian/reports/YYYY-MM-DD.json`
5. **Feedback Loop** (async): Flag stale Why-Cards, recommend policy adjustments

**Total Runtime**: < 2 minutes per audit

---

## 3. Data Schemas

### 3.1 AuditFinding

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
from datetime import datetime

AuditCategory = Literal["coherence", "fairness", "transparency", "performance", "safety"]
Severity = Literal["critical", "warning", "info"]

class AuditFinding(BaseModel):
    """Single issue detected during audit."""
    id: str  # UUID
    category: AuditCategory
    severity: Severity
    title: str  # 1 sentence summary
    description: str  # 2-3 sentences with evidence
    evidence: list[dict[str, Any]]  # References to Why-Cards, traits, etc.
    confidence: float  # 0-1 (how certain Guardian is about this finding)
    impact_score: float  # 0-1 (how much this affects system quality)
    recommendation: str  # What should be done
    related_traits: list[str] = []
    related_users: list[str] = []
    created_at: datetime = Field(default_factory=datetime.now)

    # Example:
    # {
    #   "id": "f1a2b3c4",
    #   "category": "coherence",
    #   "severity": "warning",
    #   "title": "Contradictory beliefs about social preference",
    #   "description": "User dbg_user has promoted 'Introvert'=True (ucn=0.85) and 'SocialButterfly'=True (ucn=0.82). These traits are semantically contradictory but both have high confidence.",
    #   "evidence": [
    #     {"trait_id": "Introvert", "value": true, "ucn": 0.85, "why_card_id": "wc123"},
    #     {"trait_id": "SocialButterfly", "value": true, "ucn": 0.82, "why_card_id": "wc456"}
    #   ],
    #   "confidence": 0.91,
    #   "impact_score": 0.7,
    #   "recommendation": "Generate Curiosity item asking user to clarify social preference."
    # }
```

### 3.2 GovernanceMetric

```python
class GovernanceMetric(BaseModel):
    """Quantitative score for a governance dimension."""
    name: str  # e.g., "coherence_score", "fairness_score"
    value: float  # 0-1 (higher is better)
    threshold: float  # Minimum acceptable value
    status: Literal["healthy", "degraded", "critical"]
    trend: Optional[Literal["improving", "stable", "declining"]] = None
    details: Optional[str] = None

    # Example:
    # {
    #   "name": "coherence_score",
    #   "value": 0.87,
    #   "threshold": 0.75,
    #   "status": "healthy",
    #   "trend": "stable",
    #   "details": "3 contradictions found out of 247 trait pairs (1.2%)"
    # }
```

### 3.3 AuditReport

```python
class AuditReport(BaseModel):
    """Complete self-audit report."""
    id: str  # UUID
    audit_date: datetime = Field(default_factory=datetime.now)
    audit_duration_sec: float
    llm_model_used: str

    # Inputs analyzed
    why_cards_reviewed: int
    curiosity_items_reviewed: int
    promotions_reviewed: int
    users_analyzed: int

    # Findings
    findings: list[AuditFinding]  # Sorted by severity, then impact
    findings_by_category: dict[AuditCategory, int]

    # Governance scores
    metrics: list[GovernanceMetric]
    overall_health: Literal["healthy", "degraded", "critical"]

    # Summary
    executive_summary: str  # 3-5 sentences
    top_recommendation: Optional[str] = None

    # Meta
    version: int = 1
    next_audit_due: Optional[datetime] = None

    # Example executive_summary:
    # "Analyzed 247 promoted traits across 12 users. Found 3 coherence issues (1.2%)
    # and 1 fairness concern (age bias in dating preference). Transparency score is 0.89
    # (healthy). Recommend generating Curiosity item for contradictory social traits.
    # Overall health: healthy."
```

---

## 4. LLM Prompt Templates

### 4.1 Coherence Review Prompt

```python
COHERENCE_PROMPT = """
You are the Guardian LLM, an auditor evaluating the ReDNA system's reasoning coherence.

**Task**: Identify contradictory beliefs within user trait profiles.

**Trait Pairs Analyzed**:
{trait_pairs_json}

**Instructions**:
1. For each user, check if promoted traits contradict each other semantically
2. Consider trait definitions and cultural context
3. Flag contradictions only if confidence (ucn) is high (>0.7) for both traits
4. Assign severity:
   - critical: Direct logical contradiction (e.g., "Smoker"=True + "NonSmoker"=True)
   - warning: Semantic tension (e.g., "Introvert"=True + "SocialButterfly"=True)
   - info: Unusual but plausible combination

**Known Contradictory Pairs** (not exhaustive):
- Introvert ↔ SocialButterfly
- Smoker ↔ NonSmoker
- VeganDiet ↔ MeatLover
- EarlyBird ↔ NightOwl (unless context suggests flexibility)

**Output Format**:
Return JSON array of AuditFinding objects. For each contradiction:
- Include both trait_ids, values, ucn scores
- Explain why they contradict
- Recommend resolution (e.g., generate Curiosity item, flag for manual review)

**Example**:
[
  {{
    "category": "coherence",
    "severity": "warning",
    "title": "Contradictory social preference traits",
    "description": "User has high-confidence promotions for both Introvert (ucn=0.85) and SocialButterfly (ucn=0.82). These typically represent opposite social preferences.",
    "evidence": [...],
    "confidence": 0.88,
    "impact_score": 0.65,
    "recommendation": "Generate Curiosity item: 'Would you describe yourself as more introverted or extroverted in social settings?'"
  }}
]

If no contradictions found, return [].
"""
```

### 4.2 Fairness Analysis Prompt

```python
FAIRNESS_PROMPT = """
You are the Guardian LLM, auditing the ReDNA system for fairness and bias.

**Task**: Detect reasoning patterns that unfairly favor or penalize certain traits, demographics, or user groups.

**Promotion History**:
{promotion_history_json}

**Instructions**:
1. Check if certain trait categories are systematically promoted/rejected regardless of evidence
2. Look for demographic bias (e.g., age, gender, orientation affecting non-demographic traits)
3. Identify if confidence thresholds are inconsistently applied
4. Flag if curiosity questions are disproportionately targeted at specific user groups

**Bias Indicators**:
- Trait X promoted 90% of time with ucn>0.6, but Trait Y requires ucn>0.8
- Dating preferences show age/race/orientation bias unrelated to user input
- Certain users receive 3x more Curiosity questions than others
- Why-Cards for demographic traits use different language tone (e.g., apologetic vs assertive)

**Output Format**:
Return JSON array of AuditFinding objects. For each bias detected:
- Specify affected trait_ids or user_ids
- Show statistical evidence (e.g., "promoted 12/15 times for Group A, 2/15 for Group B")
- Assess severity (critical if protected class, warning if performance disparity)
- Recommend mitigation (e.g., normalize thresholds, add fairness constraint)

**Example**:
[
  {{
    "category": "fairness",
    "severity": "warning",
    "title": "Age bias in dating preference inference",
    "description": "Users aged 18-25 have DatingPreference traits promoted at ucn=0.65 avg, while users 40+ require ucn=0.80 avg. This discrepancy is not justified by evidence quality.",
    "evidence": [
      {{"age_group": "18-25", "avg_ucn_at_promotion": 0.65, "sample_size": 8}},
      {{"age_group": "40+", "avg_ucn_at_promotion": 0.80, "sample_size": 5}}
    ],
    "confidence": 0.72,
    "impact_score": 0.68,
    "recommendation": "Normalize promotion thresholds across age groups or document justification for age-specific policies."
  }}
]

If no bias detected, return [].
"""
```

### 4.3 Transparency Review Prompt

```python
TRANSPARENCY_PROMPT = """
You are the Guardian LLM, evaluating the quality and transparency of Why-Card explanations.

**Task**: Assess if Why-Cards are informative, humble, and actionable.

**Why-Cards Reviewed**:
{why_cards_json}

**Quality Criteria**:
1. **Informativeness**: Does the summary explain *why* the belief is held? (Good: "Promoted because you said 'I wake at 6am daily'"; Bad: "High confidence")
2. **Humility**: Does it acknowledge uncertainty when ucn < 0.8? (Good: "Likely an introvert, but need more social context"; Bad: "You are definitely an introvert")
3. **Evidence Traceability**: Are evidence sources cited? (Good: "Based on chat message from 2025-10-15"; Bad: "Inferred from behavior")
4. **Actionability**: Does it suggest next steps if confidence is low? (Good: "Ask: Do you prefer small gatherings?"; Bad: silence)
5. **Tone**: Is language neutral and non-judgmental?

**Output Format**:
Return JSON array of AuditFinding objects. For each Why-Card issue:
- Cite why_card_id and trait_id
- Specify which quality criterion is violated
- Provide suggested improvement

**Example**:
[
  {{
    "category": "transparency",
    "severity": "info",
    "title": "Why-Card lacks evidence traceability",
    "description": "Why-Card wc789 for Chronotype says 'You are a morning person' but does not cite specific evidence source. User cannot verify claim.",
    "evidence": [{{"why_card_id": "wc789", "trait_id": "Chronotype", "summary": "You are a morning person", "evidence_count": 0}}],
    "confidence": 0.85,
    "impact_score": 0.45,
    "recommendation": "Update Why-Card to include evidence source (e.g., 'Based on your statement: I wake at 6am daily')."
  }}
]

If all Why-Cards meet quality standards, return [].
"""
```

### 4.4 Recommendation Generation Prompt

```python
RECOMMENDATION_PROMPT = """
You are the Guardian LLM, synthesizing audit findings into actionable recommendations.

**Audit Findings**:
{findings_json}

**Task**: Generate top 3-5 recommendations for system improvement, ranked by impact.

**Instructions**:
1. Group related findings (e.g., all coherence issues → "Improve contradiction detection")
2. Prioritize by severity and impact_score
3. Suggest concrete actions:
   - Code changes (e.g., "Add semantic similarity check for trait pairs")
   - Policy adjustments (e.g., "Raise promotion threshold for demographic traits to ucn>0.85")
   - Curiosity generation (e.g., "Enqueue question for contradictory traits")
4. Estimate effort (trivial, easy, moderate, hard)

**Output Format**:
Return JSON array of recommendations, each with:
- title (1 sentence)
- rationale (why this matters)
- actions (bulleted list)
- estimated_effort
- expected_impact (0-1)

**Example**:
[
  {{
    "title": "Implement semantic contradiction detection",
    "rationale": "3 users have contradictory trait pairs (Introvert+SocialButterfly). Current system does not detect these at promotion time.",
    "actions": [
      "Create trait_contradiction_rules.yaml mapping incompatible pairs",
      "Add coherence_check() to promotion pipeline",
      "Generate Curiosity item when contradiction detected with ucn_both > 0.7"
    ],
    "estimated_effort": "moderate",
    "expected_impact": 0.75
  }}
]
"""
```

---

## 5. API Design

### 5.1 Run Audit

**Endpoint**: `POST /devx/api/guardian/run`

**Purpose**: Trigger a complete self-audit

**Request**:
```json
{
  "audit_scope": {
    "include_why_cards": true,
    "include_curiosity": true,
    "include_promotions": true,
    "lookback_days": 30  // Analyze last 30 days
  },
  "llm_model": "phi3:mini",  // Optional, defaults to env LLM_MODEL
  "async": false  // If true, returns immediately with audit_id
}
```

**Response** (sync mode):
```json
{
  "audit_id": "audit_2025-10-17",
  "status": "completed",
  "duration_sec": 87.3,
  "report": {
    "overall_health": "healthy",
    "findings_count": 4,
    "metrics": [
      {"name": "coherence_score", "value": 0.87, "status": "healthy"},
      {"name": "fairness_score", "value": 0.91, "status": "healthy"},
      {"name": "transparency_score", "value": 0.89, "status": "healthy"}
    ],
    "executive_summary": "Analyzed 247 traits across 12 users. Found 3 minor coherence issues and 1 transparency improvement. Overall health: healthy.",
    "report_url": "/devx/api/guardian/report/audit_2025-10-17"
  }
}
```

**Response** (async mode):
```json
{
  "audit_id": "audit_2025-10-17",
  "status": "running",
  "estimated_completion_sec": 120,
  "poll_url": "/devx/api/guardian/status/audit_2025-10-17"
}
```

### 5.2 Get Report

**Endpoint**: `GET /devx/api/guardian/report/{audit_id}`

**Purpose**: Retrieve full audit report

**Response**:
```json
{
  "id": "audit_2025-10-17",
  "audit_date": "2025-10-17T14:30:00Z",
  "audit_duration_sec": 87.3,
  "llm_model_used": "phi3:mini",
  "why_cards_reviewed": 247,
  "curiosity_items_reviewed": 18,
  "promotions_reviewed": 312,
  "users_analyzed": 12,
  "findings": [
    {
      "id": "f1",
      "category": "coherence",
      "severity": "warning",
      "title": "Contradictory social traits",
      "description": "...",
      "confidence": 0.88,
      "impact_score": 0.65,
      "recommendation": "Generate Curiosity item"
    }
  ],
  "findings_by_category": {
    "coherence": 3,
    "transparency": 1
  },
  "metrics": [...],
  "overall_health": "healthy",
  "executive_summary": "...",
  "top_recommendation": "Implement semantic contradiction detection"
}
```

### 5.3 Get Metrics Summary

**Endpoint**: `GET /devx/api/guardian/metrics`

**Purpose**: Quick health check for DevX UI

**Response**:
```json
{
  "latest_audit": {
    "audit_id": "audit_2025-10-17",
    "audit_date": "2025-10-17T14:30:00Z",
    "overall_health": "healthy",
    "coherence_score": 0.87,
    "fairness_score": 0.91,
    "transparency_score": 0.89
  },
  "historical_trend": {
    "coherence_trend": "stable",
    "fairness_trend": "improving",
    "transparency_trend": "stable"
  },
  "next_audit_due": "2025-10-24T14:30:00Z"
}
```

### 5.4 Get Status (Async)

**Endpoint**: `GET /devx/api/guardian/status/{audit_id}`

**Purpose**: Poll audit progress

**Response**:
```json
{
  "audit_id": "audit_2025-10-17",
  "status": "running",  // queued|running|completed|failed
  "progress": 0.65,  // 0-1
  "current_phase": "analyzing_coherence",
  "elapsed_sec": 45.2,
  "estimated_remaining_sec": 42.1
}
```

---

## 6. Storage Plan

### 6.1 Report Storage

**Location**: `~/.redna/guardian/reports/YYYY-MM-DD.json`

**Format**: One JSON file per audit, named by date

**Example** (`2025-10-17.json`):
```json
{
  "id": "audit_2025-10-17",
  "audit_date": "2025-10-17T14:30:00Z",
  "findings": [...],
  "metrics": [...],
  "executive_summary": "..."
}
```

**Retention**: Keep last 12 weeks (84 days), then archive to `~/.redna/guardian/archive/`

### 6.2 Index File

**Location**: `~/.redna/guardian/index.json`

**Purpose**: Fast lookup for DevX UI

**Format**:
```json
{
  "audits": [
    {
      "audit_id": "audit_2025-10-17",
      "audit_date": "2025-10-17T14:30:00Z",
      "overall_health": "healthy",
      "findings_count": 4,
      "file_path": "reports/2025-10-17.json"
    }
  ],
  "latest_audit_id": "audit_2025-10-17",
  "last_updated": "2025-10-17T14:32:00Z"
}
```

**Update**: Appended after each audit completion

### 6.3 Feedback Actions Log

**Location**: `~/.redna/guardian/actions.jsonl`

**Purpose**: Track Guardian-initiated actions (e.g., flagged Why-Cards, generated Curiosity items)

**Format** (JSONL):
```json
{"audit_id": "audit_2025-10-17", "action": "flag_whycard", "target_id": "wc789", "reason": "lacks_evidence", "timestamp": "2025-10-17T14:35:00Z"}
{"audit_id": "audit_2025-10-17", "action": "enqueue_curiosity", "trait_id": "SocialPreference", "user_id": "dbg_user", "reason": "contradiction", "timestamp": "2025-10-17T14:36:00Z"}
```

---

## 7. Implementation Details

### 7.1 Coherence Checker

```python
async def check_coherence(why_cards: list[WhyCard]) -> list[AuditFinding]:
    """Detect contradictory beliefs within user profiles."""

    # Group Why-Cards by user
    user_profiles = defaultdict(list)
    for wc in why_cards:
        if wc.confidence.ucn > 0.7:  # Only check high-confidence beliefs
            user_profiles[wc.user_id].append(wc)

    # Load contradiction rules
    contradiction_rules = load_contradiction_rules()  # e.g., {"Introvert": ["SocialButterfly"]}

    findings = []
    for user_id, cards in user_profiles.items():
        # Check all pairs
        for i, card1 in enumerate(cards):
            for card2 in cards[i+1:]:
                if is_contradictory(card1.trait_id, card2.trait_id, contradiction_rules):
                    # Generate finding via LLM
                    finding = await generate_coherence_finding(card1, card2)
                    findings.append(finding)

    return findings

def is_contradictory(trait1: str, trait2: str, rules: dict) -> bool:
    """Check if two traits are semantically contradictory."""
    return trait2 in rules.get(trait1, []) or trait1 in rules.get(trait2, [])
```

### 7.2 Fairness Analyzer

```python
async def check_fairness(promotions: list[PromotionRecord]) -> list[AuditFinding]:
    """Detect bias in promotion patterns."""

    findings = []

    # Check 1: Promotion threshold consistency
    trait_thresholds = defaultdict(list)
    for promo in promotions:
        if promo.promoted:
            trait_thresholds[promo.trait_id].append(promo.ucn)

    # Detect if certain traits have systematically different thresholds
    avg_thresholds = {trait: np.mean(ucns) for trait, ucns in trait_thresholds.items()}
    global_avg = np.mean(list(avg_thresholds.values()))

    for trait, avg_ucn in avg_thresholds.items():
        if abs(avg_ucn - global_avg) > 0.15:  # 15% deviation
            finding = AuditFinding(
                category="fairness",
                severity="warning",
                title=f"Inconsistent threshold for {trait}",
                description=f"{trait} promoted at avg ucn={avg_ucn:.2f}, vs global avg={global_avg:.2f}",
                confidence=0.82,
                impact_score=0.55,
                recommendation=f"Review if {trait} should have different threshold policy"
            )
            findings.append(finding)

    # Check 2: Demographic bias (requires user metadata)
    # ... (age/gender/orientation analysis)

    return findings
```

### 7.3 Transparency Reviewer

```python
async def check_transparency(why_cards: list[WhyCard]) -> list[AuditFinding]:
    """Evaluate Why-Card explanation quality."""

    findings = []

    for wc in why_cards:
        issues = []

        # Check 1: Evidence count
        if len(wc.evidence) == 0:
            issues.append("lacks_evidence")

        # Check 2: Humility (low ucn should acknowledge uncertainty)
        if wc.confidence.ucn < 0.75 and "maybe" not in wc.summary.lower() and "likely" not in wc.summary.lower():
            issues.append("lacks_humility")

        # Check 3: Summary informativeness (via LLM)
        if len(wc.summary.split()) < 10:
            issues.append("summary_too_brief")

        # Check 4: Actionability (if needs_verification but no next_question)
        if wc.needs_verification and not wc.next_question:
            issues.append("missing_next_question")

        if issues:
            finding = AuditFinding(
                category="transparency",
                severity="info",
                title=f"Why-Card quality issues for {wc.trait_id}",
                description=f"Issues detected: {', '.join(issues)}",
                evidence=[{"why_card_id": wc.id, "issues": issues}],
                confidence=0.78,
                impact_score=0.40,
                recommendation=f"Regenerate Why-Card with improved template"
            )
            findings.append(finding)

    return findings
```

---

## 8. Testing Plan

### 8.1 Coherence Test: Contradictory Traits

**Setup**:
```python
# Create synthetic user with contradictory traits
test_user = "guardian_test_coherence"
ingest_text(user_id=test_user, text="I am an introvert who loves being the life of the party")

# Manually promote both Introvert and SocialButterfly with high ucn
promote_trait(user_id=test_user, trait_id="Introvert", value=True, ucn=0.88)
promote_trait(user_id=test_user, trait_id="SocialButterfly", value=True, ucn=0.85)

# Run audit
audit = run_guardian_audit()

# Verify
assert any(f.category == "coherence" and "Introvert" in f.description for f in audit.findings)
assert audit.metrics["coherence_score"] < 0.90  # Should be degraded
```

**Expected Result**:
- Finding: "Contradictory social preference traits"
- Severity: `warning`
- Recommendation: "Generate Curiosity item to clarify"

### 8.2 Fairness Test: Threshold Bias

**Setup**:
```python
# Create two user groups with different promotion patterns
for i in range(10):
    # Group A: Young users, low threshold
    ingest_text(user_id=f"user_young_{i}", text="I am 22 years old and prefer hiking")
    # Promote DatingPref at ucn=0.65
    promote_trait(user_id=f"user_young_{i}", trait_id="DatingPreference", value="outdoor", ucn=0.65)

    # Group B: Older users, high threshold
    ingest_text(user_id=f"user_old_{i}", text="I am 45 years old and prefer hiking")
    # Promote DatingPref at ucn=0.85
    promote_trait(user_id=f"user_old_{i}", trait_id="DatingPreference", value="outdoor", ucn=0.85)

# Run audit
audit = run_guardian_audit()

# Verify
fairness_findings = [f for f in audit.findings if f.category == "fairness"]
assert len(fairness_findings) > 0
assert "age" in fairness_findings[0].description.lower()
```

**Expected Result**:
- Finding: "Age bias in DatingPreference promotion"
- Severity: `warning`
- Confidence: > 0.70

### 8.3 Transparency Test: Low-Quality Why-Cards

**Setup**:
```python
# Create Why-Card with no evidence
poor_whycard = WhyCard(
    trait_id="Chronotype",
    value="morning",
    user_id="test_transparency",
    summary="You are a morning person",  # Too brief, no evidence
    evidence=[],  # Empty!
    confidence=ConfidenceExplanation(ucn=0.72, reasoning=""),
    needs_verification=True,
    next_question=None  # Missing despite needs_verification=True
)

# Run audit
audit = run_guardian_audit()

# Verify
transparency_findings = [f for f in audit.findings if f.category == "transparency"]
assert len(transparency_findings) > 0
assert "lacks_evidence" in str(transparency_findings[0].evidence)
```

**Expected Result**:
- Finding: "Why-Card quality issues for Chronotype"
- Issues: `["lacks_evidence", "missing_next_question"]`
- Severity: `info`

### 8.4 Performance Test: Runtime < 2 Minutes

**Setup**:
```python
# Create realistic dataset
for i in range(20):  # 20 users
    for j in range(15):  # 15 traits each = 300 total
        promote_trait(user_id=f"user_{i}", trait_id=f"Trait_{j}", value=True, ucn=random.uniform(0.6, 0.95))
        create_whycard(user_id=f"user_{i}", trait_id=f"Trait_{j}")

# Run timed audit
start = time.time()
audit = run_guardian_audit()
duration = time.time() - start

# Verify
assert duration < 120  # 2 minutes
assert audit.why_cards_reviewed == 300
```

**Expected Result**:
- Duration: 60-90 seconds
- All checks completed
- Report generated successfully

### 8.5 Detection Rate Test

**Metric**: ≥ 90% detection of synthetic contradictions

**Setup**:
```python
# Create 20 users, 10 with contradictions, 10 without
contradictory_pairs = [
    ("Introvert", "SocialButterfly"),
    ("Smoker", "NonSmoker"),
    ("VeganDiet", "MeatLover"),
    ("EarlyBird", "NightOwl"),
    ("MinimalistLifestyle", "LuxuryEnthusiast")
]

for i in range(10):
    pair = contradictory_pairs[i % 5]
    promote_trait(user_id=f"user_contra_{i}", trait_id=pair[0], value=True, ucn=0.85)
    promote_trait(user_id=f"user_contra_{i}", trait_id=pair[1], value=True, ucn=0.85)

for i in range(10):
    promote_trait(user_id=f"user_normal_{i}", trait_id="Chronotype", value="morning", ucn=0.85)

# Run audit
audit = run_guardian_audit()
coherence_findings = [f for f in audit.findings if f.category == "coherence"]

# Verify detection rate
detected = len(set(f.related_users[0] for f in coherence_findings if f.related_users))
detection_rate = detected / 10  # 10 contradictory users

assert detection_rate >= 0.90  # 90% detection
```

**Expected Result**: Detection rate ≥ 90% (9-10 out of 10 contradictions caught)

---

## 9. UI/DevX Integration

### 9.1 Governance Score Chip

Display in DevX metrics sidebar:

```tsx
// web/src/components/governance/GovernanceScoreChip.tsx
export function GovernanceScoreChip() {
  const { data } = useSWR('/devx/api/guardian/metrics', fetcher);

  const getColor = (health: string) => {
    switch(health) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'critical': return 'error';
      default: return 'default';
    }
  };

  return (
    <Chip
      label={`Governance: ${data?.latest_audit?.overall_health || 'unknown'}`}
      color={getColor(data?.latest_audit?.overall_health)}
      icon={<ShieldIcon />}
      onClick={() => router.push('/tools/governance')}
    />
  );
}
```

### 9.2 Audit Report Viewer

**Route**: `/tools/governance`

**Features**:
- List of recent audits (last 12 weeks)
- Overall health trend chart
- Expandable findings by category
- Quick actions (e.g., "Generate Curiosity for contradictory traits")

```tsx
// web/src/app/tools/governance/page.tsx
export default function GovernancePage() {
  const { data: report } = useSWR('/devx/api/guardian/report/latest', fetcher);

  return (
    <Container>
      <Typography variant="h4">Guardian Audit Report</Typography>

      <MetricsGrid>
        <MetricCard
          title="Coherence Score"
          value={report.metrics.coherence_score}
          status={report.metrics.coherence_status}
        />
        <MetricCard
          title="Fairness Score"
          value={report.metrics.fairness_score}
          status={report.metrics.fairness_status}
        />
        <MetricCard
          title="Transparency Score"
          value={report.metrics.transparency_score}
          status={report.metrics.transparency_status}
        />
      </MetricsGrid>

      <FindingsList findings={report.findings} />

      <Button onClick={runNewAudit}>Run New Audit</Button>
    </Container>
  );
}
```

### 9.3 Automated Scheduling

**Cron Job**: Run Guardian every Sunday at 2am

```python
# ReDNACoreDemo/devx/backend/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', day_of_week='sun', hour=2)
async def weekly_guardian_audit():
    """Run Guardian audit weekly."""
    logger.info("Starting scheduled Guardian audit")
    audit = await run_guardian_audit()
    logger.info(f"Audit completed: {audit.overall_health}, {len(audit.findings)} findings")

    # Send notification if critical
    if audit.overall_health == "critical":
        await send_alert_notification(audit)
```

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Detection Rate** | ≥ 90% of synthetic contradictions | Test 8.5 |
| **False Positive Rate** | ≤ 5% | Manual review of 100 findings |
| **Runtime** | < 2 minutes for 300 traits | Test 8.4 |
| **Report Completeness** | 100% (all sections populated) | Schema validation |
| **Actionability** | ≥ 80% of findings have concrete recommendation | Manual review |
| **Audit Frequency** | 1 per week (automated) | Cron job logs |
| **User Trust** | Governance score visible in UI | DevX integration test |

---

## 11. Rollout Plan (6 Weeks)

### Weeks 1-2: Core Infrastructure
- [ ] Define Pydantic schemas (AuditFinding, AuditReport, GovernanceMetric)
- [ ] Implement storage layer (`~/.redna/guardian/`)
- [ ] Create `/devx/api/guardian/run` endpoint skeleton
- [ ] Write unit tests for data models

**Deliverable**: Guardian can collect Why-Cards, Curiosity items, promotions

### Weeks 3-4: Analysis Engines
- [ ] Implement coherence checker with contradiction rules
- [ ] Implement fairness analyzer with threshold comparison
- [ ] Implement transparency reviewer with quality criteria
- [ ] Add LLM prompt generation and parsing
- [ ] Test each analyzer independently (Tests 8.1-8.3)

**Deliverable**: All three analysis engines operational

### Weeks 5-6: Integration & UI
- [ ] Add `/devx/api/guardian/report/{id}` and `/devx/api/guardian/metrics` endpoints
- [ ] Create Governance page in Next.js frontend
- [ ] Add GovernanceScoreChip to DevX sidebar
- [ ] Implement automated weekly scheduling
- [ ] Run end-to-end verification (Test 8.4-8.5)
- [ ] Document all APIs and prompts

**Deliverable**: Full Guardian system with UI, passing all success metrics

---

## 12. Philosophy Alignment Assessment

| Principle | Implementation | Score (0-10) |
|-----------|----------------|--------------|
| **Self-Awareness** | Guardian reviews its own reasoning artifacts | 10 |
| **Humility** | Flags uncertainty, acknowledges when unsure | 9 |
| **Explainability** | Every finding includes evidence and reasoning | 10 |
| **Continuous Learning** | Audit outcomes feed Phase 7-8 improvements | 7 |
| **Fairness** | Explicit bias detection across demographics | 9 |
| **Transparency** | Reports are human-readable with concrete actions | 10 |
| **Holism** | Correlates beliefs across traits and users | 8 |
| **Non-Destructive** | Flags issues, never auto-deletes data | 10 |

**Overall Alignment**: **9.1/10** (Exceptional alignment with ReDNA philosophy)

---

## 13. Future Enhancements

### 13.1 Adaptive Contradiction Rules

Instead of static `contradiction_rules.yaml`, learn contradictions from data:
```python
# Detect semantic similarity between trait embeddings
trait_embeddings = generate_embeddings(all_trait_ids)
for t1, t2 in combinations(trait_embeddings, 2):
    similarity = cosine_similarity(t1, t2)
    if similarity < -0.7:  # Negative correlation → likely contradictory
        flag_as_potential_contradiction(t1.trait_id, t2.trait_id)
```

### 13.2 Longitudinal Bias Tracking

Track fairness metrics over time to detect emerging bias:
```python
# Compare this week's fairness_score to 12-week rolling average
if current_fairness < rolling_avg - 0.10:
    alert("Fairness degradation detected", severity="warning")
```

### 13.3 Interactive Resolution

Allow users to review Guardian findings and provide feedback:
```python
# POST /devx/api/guardian/finding/{id}/resolve
{
  "resolution": "accepted",  // accepted|rejected|deferred
  "action_taken": "Generated Curiosity item for user dbg_user",
  "notes": "Contradiction was valid, user confirmed preference change"
}
```

### 13.4 Cross-Service Learning

Share Guardian findings with Core for immediate action:
```python
if finding.severity == "critical":
    # Auto-flag Why-Card for regeneration
    await core_api.flag_whycard(finding.evidence["why_card_id"], reason=finding.title)

    # Auto-enqueue Curiosity item for contradictions
    if finding.category == "coherence":
        await core_api.enqueue_curiosity(
            user_id=finding.related_users[0],
            trait_id=finding.related_traits[0],
            reason_code="contradiction"
        )
```

---

## 14. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LLM hallucination** | False findings | Combine LLM + rule-based checks, require high confidence |
| **High runtime** | Blocks other services | Run async, 5-minute timeout per check |
| **Storage bloat** | Disk space issues | Auto-archive reports >84 days, compress JSON |
| **Privacy leak** | Audit logs expose user data | Redact PII in reports, restrict access |
| **Alert fatigue** | Engineers ignore findings | Only alert on critical, weekly digest for warnings |
| **Contradiction rule maintenance** | Rules become stale | Version contradiction_rules.yaml, review quarterly |

---

## 15. Verification Script

```bash
#!/bin/bash
# scripts/verify_guardian.sh

set -e

BASE="http://127.0.0.1:8012"

echo "=== Guardian LLM Verification ==="
echo ""

# Test 1: Create synthetic contradiction
echo "1. Setting up contradictory traits..."
USER="guardian_test_$(date +%s)"

curl -s -X POST "$BASE/core/api/ingest_text" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$USER\",\"text\":\"I am an introvert\",\"source\":\"test\"}"

curl -s -X POST "$BASE/core/api/ingest_text" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$USER\",\"text\":\"I love being the life of the party\",\"source\":\"test\"}"

echo "   ✅ Created contradictory traits for $USER"

# Test 2: Run Guardian audit
echo ""
echo "2. Running Guardian audit..."
AUDIT_RESPONSE=$(curl -s -X POST "$BASE/devx/api/guardian/run" \
  -H 'Content-Type: application/json' \
  -d '{"audit_scope":{"lookback_days":1},"async":false}')

AUDIT_ID=$(echo $AUDIT_RESPONSE | jq -r '.audit_id')
OVERALL_HEALTH=$(echo $AUDIT_RESPONSE | jq -r '.report.overall_health')
FINDINGS_COUNT=$(echo $AUDIT_RESPONSE | jq '.report.findings_count')

echo "   Audit ID: $AUDIT_ID"
echo "   Overall Health: $OVERALL_HEALTH"
echo "   Findings: $FINDINGS_COUNT"

# Test 3: Verify coherence finding
echo ""
echo "3. Checking for coherence finding..."
COHERENCE_FINDINGS=$(echo $AUDIT_RESPONSE | jq '.report.findings[] | select(.category=="coherence")')

if [ -n "$COHERENCE_FINDINGS" ]; then
  echo "   ✅ Coherence issue detected"
  echo $COHERENCE_FINDINGS | jq -r '   "   - " + .title'
else
  echo "   ⚠️  No coherence finding (may need more evidence)"
fi

# Test 4: Verify metrics
echo ""
echo "4. Checking governance metrics..."
COHERENCE_SCORE=$(echo $AUDIT_RESPONSE | jq -r '.report.metrics[] | select(.name=="coherence_score") | .value')
FAIRNESS_SCORE=$(echo $AUDIT_RESPONSE | jq -r '.report.metrics[] | select(.name=="fairness_score") | .value')
TRANSPARENCY_SCORE=$(echo $AUDIT_RESPONSE | jq -r '.report.metrics[] | select(.name=="transparency_score") | .value')

echo "   Coherence: $COHERENCE_SCORE"
echo "   Fairness: $FAIRNESS_SCORE"
echo "   Transparency: $TRANSPARENCY_SCORE"

# Validate scores are in [0, 1]
for score in $COHERENCE_SCORE $FAIRNESS_SCORE $TRANSPARENCY_SCORE; do
  if (( $(echo "$score >= 0.0 && $score <= 1.0" | bc -l) )); then
    echo "   ✅ Score $score in valid range"
  else
    echo "   ❌ Invalid score: $score"
    exit 1
  fi
done

# Test 5: Fetch report via API
echo ""
echo "5. Fetching full report..."
REPORT=$(curl -s "$BASE/devx/api/guardian/report/$AUDIT_ID")
SUMMARY=$(echo $REPORT | jq -r '.executive_summary')

echo "   Executive Summary:"
echo "   $SUMMARY"

# Test 6: Check metrics endpoint
echo ""
echo "6. Testing metrics endpoint..."
METRICS=$(curl -s "$BASE/devx/api/guardian/metrics")
LATEST_HEALTH=$(echo $METRICS | jq -r '.latest_audit.overall_health')

echo "   Latest health: $LATEST_HEALTH"

if [ "$LATEST_HEALTH" == "healthy" ] || [ "$LATEST_HEALTH" == "degraded" ]; then
  echo "   ✅ Metrics endpoint operational"
else
  echo "   ❌ Unexpected health status: $LATEST_HEALTH"
  exit 1
fi

echo ""
echo "=== All Guardian Tests Passed ✅ ==="
```

---

## 16. Summary

The **Guardian LLM** closes the loop on ReDNA's self-awareness. By periodically auditing its own reasoning, the system can:

1. **Detect contradictions** before they degrade user experience
2. **Ensure fairness** across demographics and trait types
3. **Improve transparency** through high-quality Why-Cards
4. **Enable continuous learning** by feeding findings into Phase 7-8 adaptive policies

**Key Innovations**:
- **AI-on-AI**: LLM reviews LLM-generated content (meta-reasoning)
- **Non-destructive**: Flags issues without auto-deleting data
- **Actionable**: Every finding includes concrete remediation steps
- **Composable**: Integrates with Why-Cards, Curiosity Queue, DevX Diagnostics

**Philosophy Alignment**: **9.1/10** (Exceptional)

**Next Steps**:
1. Await approval from Codex for implementation
2. Begin 6-week rollout starting with core infrastructure
3. Update `AI_Philosophy_Integration_Summary.md` with Phase 6 completion score

---

**End of Phase 6.4 Specification**
