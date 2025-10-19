# Phase 6.3: DevX AI Diagnostics Specification

**Author**: Claude (Conceptual & Architectural Lead)
**Date**: 2025-10-17
**Status**: Draft for Review
**Version**: 1.0

---

## 1. Vision

The DevX AI Diagnostics subsystem transforms raw system metrics into actionable intelligence. Instead of requiring engineers to manually correlate latency spikes, error rates, and service health, an LLM analyzes the complete system state and provides natural-language diagnoses with concrete remediation steps.

**Philosophy Alignment**:
- **AI at Every Layer**: Diagnostics are reasoning tasks, not rule-based thresholds
- **Explainability**: Every diagnosis includes evidence trail and confidence
- **Forgiving Intelligence**: Handles ambiguous symptoms, partial data, and novel failure modes
- **Self-Evolution**: Learns from past incidents to improve future diagnoses

---

## 2. Objectives

1. **Single-Endpoint Diagnostics**: `POST /devx/api/diagnose` accepts current metrics, returns diagnosis
2. **Natural-Language Output**: "UCNRR latency is high (p95=1800ms) likely due to cold LLM cache. Warm it by running tier2_verify.py."
3. **Confidence Scoring**: Each diagnosis annotated with confidence (0-1) and evidence sources
4. **Remediation Suggestions**: Actionable next steps ranked by impact and ease
5. **Historical Context**: Optional comparison with baseline metrics for trend analysis
6. **Multi-Service Coverage**: Diagnose Core, UCNRR, DevX Backend, Next.js frontend, Ollama

---

## 3. Data Models

### 3.1 DiagnosticRequest

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class SystemMetrics(BaseModel):
    """Current system state snapshot."""
    core_health: Dict[str, Any]  # /health response
    ucnrr_health: Dict[str, Any]  # /health response
    roundtrip_metrics: Dict[str, Any]  # /metrics/roundtrip response
    recent_errors: Optional[list[str]] = None  # Last 10 error messages from logs
    service_uptime_sec: Optional[Dict[str, int]] = None  # {service: uptime}
    ollama_status: Optional[Dict[str, Any]] = None  # /api/tags response
    timestamp: datetime = Field(default_factory=datetime.now)

class DiagnosticRequest(BaseModel):
    """Input to /devx/api/diagnose endpoint."""
    current_metrics: SystemMetrics
    baseline_metrics: Optional[SystemMetrics] = None  # For trend comparison
    user_symptom: Optional[str] = None  # e.g., "Chat responses are slow"
    include_remediation: bool = True
    max_suggestions: int = 5
```

### 3.2 DiagnosticResponse

```python
from typing import Literal

DiagnosticSeverity = Literal["critical", "warning", "info", "healthy"]

class Evidence(BaseModel):
    """Supporting evidence for a diagnosis."""
    source: str  # e.g., "roundtrip_metrics.ucnrr_p95"
    value: Any  # Current value
    baseline_value: Optional[Any] = None  # For comparison
    threshold: Optional[float] = None  # Expected/threshold value
    interpretation: str  # 1 sentence explanation

class RemediationStep(BaseModel):
    """Actionable remediation suggestion."""
    action: str  # Natural-language instruction
    impact: Literal["high", "medium", "low"]  # Expected improvement
    effort: Literal["trivial", "easy", "moderate", "hard"]  # Implementation difficulty
    command: Optional[str] = None  # Bash command if applicable
    estimated_time_min: Optional[int] = None

class Diagnosis(BaseModel):
    """Single diagnostic finding."""
    id: str  # UUID
    severity: DiagnosticSeverity
    summary: str  # 1-2 sentences
    detailed_explanation: str  # 3-5 sentences with causal reasoning
    evidence: list[Evidence]
    confidence: float  # 0-1
    affected_services: list[str]  # e.g., ["ucnrr", "core"]
    probable_cause: str  # Root cause hypothesis
    remediation_steps: list[RemediationStep]
    related_diagnoses: list[str] = []  # IDs of related findings

class DiagnosticResponse(BaseModel):
    """Output from /devx/api/diagnose endpoint."""
    overall_health: DiagnosticSeverity
    diagnoses: list[Diagnosis]  # Sorted by severity, then confidence
    system_summary: str  # 2-3 sentence executive summary
    llm_model_used: str
    analysis_duration_ms: int
    created_at: datetime = Field(default_factory=datetime.now)
```

---

## 4. API Design

### 4.1 Diagnostic Endpoint

**Endpoint**: `POST /devx/api/diagnose`

**Request Example**:
```json
{
  "current_metrics": {
    "core_health": {"status": "healthy", "rr_mode": "online"},
    "ucnrr_health": {"status": "healthy", "llm_configured": true},
    "roundtrip_metrics": {
      "total_p50": 850,
      "total_p95": 1820,
      "ucnrr_p95": 1200,
      "core_p95": 620,
      "alerts": {"total_p95_high": true}
    },
    "recent_errors": [
      "UCNRR timeout after 30s (llama3.1:8b)",
      "UCNRR timeout after 30s (llama3.1:8b)"
    ],
    "ollama_status": {
      "models": ["phi3:mini", "llama3.1:8b"]
    }
  },
  "user_symptom": "Chat is taking forever to respond",
  "include_remediation": true,
  "max_suggestions": 3
}
```

**Response Example**:
```json
{
  "overall_health": "warning",
  "diagnoses": [
    {
      "id": "d1a2b3c4",
      "severity": "warning",
      "summary": "UCNRR latency exceeds threshold due to slow LLM model.",
      "detailed_explanation": "The p95 roundtrip latency is 1820ms, primarily driven by UCNRR (1200ms). Recent errors show repeated 30s timeouts with llama3.1:8b. This model is known to be slow for inference. Ollama is reachable and healthy, so the issue is model performance, not connectivity.",
      "evidence": [
        {
          "source": "roundtrip_metrics.ucnrr_p95",
          "value": 1200,
          "threshold": 800,
          "interpretation": "UCNRR p95 is 50% above healthy threshold (800ms)."
        },
        {
          "source": "recent_errors",
          "value": "UCNRR timeout after 30s (llama3.1:8b)",
          "interpretation": "Multiple timeouts indicate model is too slow for interactive use."
        }
      ],
      "confidence": 0.92,
      "affected_services": ["ucnrr", "core"],
      "probable_cause": "LLM model (llama3.1:8b) inference time exceeds timeout threshold",
      "remediation_steps": [
        {
          "action": "Switch UCNRR to faster model phi3:mini",
          "impact": "high",
          "effort": "trivial",
          "command": "# Edit .env: LLM_MODEL=phi3:mini, then restart Core",
          "estimated_time_min": 2
        },
        {
          "action": "Warm LLM cache by running tier2 verifier",
          "impact": "medium",
          "effort": "easy",
          "command": "python scripts/tier2_verify.py",
          "estimated_time_min": 5
        },
        {
          "action": "Increase UCNRR timeout from 30s to 60s (temporary workaround)",
          "impact": "low",
          "effort": "easy",
          "command": "# Edit ucnrr_app.py: LLM_TIMEOUT_SEC = 60",
          "estimated_time_min": 3
        }
      ]
    }
  ],
  "system_summary": "System is operational but UCNRR latency is degraded (p95=1820ms). Primary issue is slow LLM model. Recommend switching to phi3:mini for immediate improvement.",
  "llm_model_used": "phi3:mini",
  "analysis_duration_ms": 450
}
```

### 4.2 Health Check with Auto-Diagnose

**Endpoint**: `GET /devx/api/health?diagnose=true`

**Purpose**: Lightweight health check that optionally triggers diagnostic analysis

**Response**:
```json
{
  "status": "warning",
  "services": {
    "core": "healthy",
    "ucnrr": "degraded",
    "devx_backend": "healthy",
    "frontend": "healthy"
  },
  "quick_diagnosis": "UCNRR latency high. Recommend switching LLM model.",
  "full_report_url": "/devx/api/diagnose"
}
```

### 4.3 Diagnostic History

**Endpoint**: `GET /devx/api/diagnose/history?limit=10`

**Purpose**: Retrieve past diagnostic reports for trend analysis

**Response**:
```json
{
  "reports": [
    {
      "timestamp": "2025-10-17T14:32:00Z",
      "overall_health": "warning",
      "top_issue": "UCNRR latency high",
      "resolved": true,
      "resolution_time_min": 12
    }
  ]
}
```

---

## 5. LLM Prompt Design

### 5.1 System Prompt

```markdown
You are an expert system reliability engineer analyzing the ReDNA system.

Your task is to diagnose system health based on current metrics and provide actionable remediation steps.

**System Architecture**:
- **Core**: Main service (FastAPI) handling trait storage, promotion, and curiosity queue
- **UCNRR**: Statistical interpreter providing RR/UCN scoring via LLM extraction
- **DevX Backend**: Monitoring and diagnostics service
- **Ollama**: Local LLM provider (models: phi3:mini, llama3.1:8b)
- **Frontend**: Next.js application

**Known Failure Modes**:
1. **UCNRR Slow**: LLM model too large (llama3.1:8b > 1s inference)
2. **UCNRR Unreachable**: Service down or wrong port
3. **Core Offline**: Core service crashed or not started
4. **Ollama Timeout**: Model not loaded, needs warm-up
5. **High Error Rate**: Malformed requests or schema validation failures
6. **Memory Pressure**: Long-running services with no cleanup

**Healthy Baselines**:
- total_p95 < 2000ms
- ucnrr_p95 < 800ms
- core_p95 < 500ms
- error_rate < 3%
- All services status="healthy"

**Output Format**:
Return a JSON object matching the DiagnosticResponse schema. For each diagnosis:
1. Identify the symptom (what is abnormal)
2. Explain the probable cause (why it's happening)
3. Provide evidence (cite specific metrics)
4. Suggest remediation (concrete steps, ranked by impact/effort)
5. Assign confidence (0-1) based on evidence strength
```

### 5.2 User Prompt Template

```python
def build_diagnostic_prompt(request: DiagnosticRequest) -> str:
    """Generate LLM prompt for diagnostic analysis."""

    # Format current metrics
    metrics_str = json.dumps(request.current_metrics.model_dump(), indent=2)

    # Optional baseline comparison
    baseline_str = ""
    if request.baseline_metrics:
        baseline_str = f"\n**Baseline Metrics (for comparison)**:\n{json.dumps(request.baseline_metrics.model_dump(), indent=2)}"

    # Optional user symptom
    symptom_str = ""
    if request.user_symptom:
        symptom_str = f"\n**User-Reported Symptom**: {request.user_symptom}"

    prompt = f"""
Analyze the following system metrics and diagnose any issues.

**Current Metrics**:
{metrics_str}
{baseline_str}
{symptom_str}

**Instructions**:
1. Compare current metrics to healthy baselines
2. Identify anomalies (latency spikes, errors, service degradation)
3. Correlate symptoms across services (e.g., high UCNRR latency → high total latency)
4. Provide {request.max_suggestions} remediation steps per diagnosis, ranked by impact
5. Assign severity: critical (service down), warning (degraded), info (advisory), healthy (no issues)
6. Include confidence score (0-1) based on evidence clarity

Return valid JSON matching DiagnosticResponse schema.
"""
    return prompt
```

### 5.3 Fallback Logic

If LLM call fails or times out, return rule-based diagnosis:

```python
def fallback_diagnose(metrics: SystemMetrics) -> DiagnosticResponse:
    """Rule-based fallback when LLM unavailable."""
    diagnoses = []

    # Rule 1: High UCNRR latency
    if metrics.roundtrip_metrics.get("ucnrr_p95", 0) > 800:
        diagnoses.append(Diagnosis(
            severity="warning",
            summary="UCNRR latency is high.",
            detailed_explanation="Check LLM model performance.",
            confidence=0.6,
            remediation_steps=[
                RemediationStep(
                    action="Switch to faster LLM model (phi3:mini)",
                    impact="high",
                    effort="trivial"
                )
            ]
        ))

    # Rule 2: Service unreachable
    if metrics.ucnrr_health.get("status") != "healthy":
        diagnoses.append(Diagnosis(
            severity="critical",
            summary="UCNRR service is unreachable.",
            confidence=0.95,
            remediation_steps=[
                RemediationStep(
                    action="Restart UCNRR service",
                    impact="high",
                    effort="easy",
                    command="./scripts/start_ucnrr.sh"
                )
            ]
        ))

    return DiagnosticResponse(
        overall_health="warning" if diagnoses else "healthy",
        diagnoses=diagnoses,
        system_summary="Fallback rule-based diagnosis (LLM unavailable)",
        llm_model_used="fallback_rules"
    )
```

---

## 6. Integration Points

### 6.1 DevX Backend `/metrics` Integration

The `/devx/api/metrics` endpoint already aggregates:
- Roundtrip latency percentiles
- UCNRR status
- Alert flags

**Hook**: Auto-trigger diagnosis when alerts fire:

```python
@app.get("/devx/api/metrics")
async def get_metrics():
    metrics = fetch_all_metrics()

    # Auto-diagnose if alerts present
    if metrics["roundtrip"]["alerts"]["total_p95_high"]:
        diagnosis = await diagnose_system(metrics)
        metrics["auto_diagnosis"] = diagnosis.system_summary

    return metrics
```

### 6.2 RoundtripChart UI Integration

Display diagnosis in UI when available:

```tsx
// web/src/components/metrics/RoundtripChart.tsx
{metrics.auto_diagnosis && (
  <Alert severity="warning">
    <AlertTitle>System Diagnosis</AlertTitle>
    {metrics.auto_diagnosis}
    <Button href="/tools/diagnostics">View Full Report</Button>
  </Alert>
)}
```

### 6.3 Slack/Discord Alerting (Future)

When critical diagnosis detected, send to Slack:

```python
if diagnosis.overall_health == "critical":
    await send_slack_alert(
        channel="#redna-alerts",
        message=diagnosis.system_summary,
        remediation=diagnosis.diagnoses[0].remediation_steps[0].action
    )
```

---

## 7. Confidence Calculation

Confidence is based on:
1. **Evidence Completeness**: More metrics → higher confidence
2. **Symptom Clarity**: Ambiguous symptoms (e.g., "slow") → lower confidence
3. **Baseline Availability**: Trend comparison → higher confidence
4. **Error Message Specificity**: Stack traces → higher confidence

**Formula**:
```python
def calculate_confidence(diagnosis: Diagnosis) -> float:
    """Calculate confidence score for a diagnosis."""
    base_confidence = 0.5

    # +0.1 per piece of evidence (max +0.3)
    evidence_bonus = min(0.3, len(diagnosis.evidence) * 0.1)

    # +0.2 if baseline comparison available
    baseline_bonus = 0.2 if has_baseline_comparison(diagnosis) else 0.0

    # -0.2 if symptom is vague
    vagueness_penalty = -0.2 if is_vague_symptom(diagnosis) else 0.0

    confidence = base_confidence + evidence_bonus + baseline_bonus + vagueness_penalty
    return max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
```

---

## 8. Test Cases

### 8.1 Test Case 1: Slow UCNRR Model

**Input Metrics**:
```json
{
  "ucnrr_health": {"status": "healthy", "llm_configured": true},
  "roundtrip_metrics": {"ucnrr_p95": 1500, "total_p95": 2100},
  "recent_errors": ["UCNRR timeout after 30s"]
}
```

**Expected Diagnosis**:
- Severity: `warning`
- Probable Cause: "Slow LLM model (llama3.1:8b)"
- Remediation: "Switch to phi3:mini"
- Confidence: > 0.85

### 8.2 Test Case 2: UCNRR Service Down

**Input Metrics**:
```json
{
  "ucnrr_health": {"error": "Connection refused"},
  "roundtrip_metrics": {"alerts": {"total_p95_high": true}}
}
```

**Expected Diagnosis**:
- Severity: `critical`
- Probable Cause: "UCNRR service not running"
- Remediation: "Start UCNRR service via ./scripts/start_ucnrr.sh"
- Confidence: > 0.9

### 8.3 Test Case 3: Ollama Model Not Loaded

**Input Metrics**:
```json
{
  "ucnrr_health": {"status": "healthy"},
  "recent_errors": ["Ollama generate timeout", "Model not found"],
  "ollama_status": {"models": []}
}
```

**Expected Diagnosis**:
- Severity: `warning`
- Probable Cause: "Ollama model not loaded or pulled"
- Remediation: "Pull model: ollama pull phi3:mini"
- Confidence: > 0.8

### 8.4 Test Case 4: High Error Rate

**Input Metrics**:
```json
{
  "core_health": {"status": "healthy"},
  "roundtrip_metrics": {"error_count": 45, "total_requests": 1000},
  "recent_errors": [
    "ValidationError: trait_id required",
    "ValidationError: trait_id required"
  ]
}
```

**Expected Diagnosis**:
- Severity: `warning`
- Probable Cause: "Request validation failures (missing trait_id)"
- Remediation: "Check API clients for schema compliance"
- Confidence: > 0.75

### 8.5 Test Case 5: Healthy System

**Input Metrics**:
```json
{
  "core_health": {"status": "healthy"},
  "ucnrr_health": {"status": "healthy"},
  "roundtrip_metrics": {"total_p95": 650, "ucnrr_p95": 350}
}
```

**Expected Diagnosis**:
- Overall Health: `healthy`
- Diagnoses: `[]` (empty)
- System Summary: "All services operational. No issues detected."

---

## 9. Verification Script

```bash
#!/bin/bash
# scripts/verify_devx_diagnostics.sh

set -e

BASE="http://127.0.0.1:8012"

echo "=== DevX AI Diagnostics Verification ==="
echo ""

# Test 1: Diagnose current system state
echo "1. Fetching current metrics..."
METRICS=$(curl -s $BASE/devx/api/metrics)
echo "   ✅ Metrics retrieved"

echo ""
echo "2. Requesting diagnosis..."
DIAGNOSIS=$(curl -s -X POST $BASE/devx/api/diagnose \
  -H 'Content-Type: application/json' \
  -d "{\"current_metrics\": $METRICS, \"include_remediation\": true}")

echo "   Overall Health: $(echo $DIAGNOSIS | jq -r '.overall_health')"
echo "   Diagnoses Count: $(echo $DIAGNOSIS | jq '.diagnoses | length')"
echo "   System Summary: $(echo $DIAGNOSIS | jq -r '.system_summary')"

# Test 2: Check confidence scores
echo ""
echo "3. Validating confidence scores..."
CONFIDENCES=$(echo $DIAGNOSIS | jq -r '.diagnoses[].confidence')
for conf in $CONFIDENCES; do
  if (( $(echo "$conf >= 0.0 && $conf <= 1.0" | bc -l) )); then
    echo "   ✅ Confidence $conf in valid range [0, 1]"
  else
    echo "   ❌ Invalid confidence: $conf"
    exit 1
  fi
done

# Test 3: Verify remediation steps
echo ""
echo "4. Checking remediation steps..."
STEPS=$(echo $DIAGNOSIS | jq '.diagnoses[0].remediation_steps | length')
if [ "$STEPS" -gt 0 ]; then
  echo "   ✅ Found $STEPS remediation steps"
  echo $DIAGNOSIS | jq -r '.diagnoses[0].remediation_steps[0] | "   - \(.action) (impact: \(.impact), effort: \(.effort))"'
else
  echo "   ⚠️  No remediation steps (system may be healthy)"
fi

# Test 4: Health check with auto-diagnose
echo ""
echo "5. Testing auto-diagnose health check..."
HEALTH=$(curl -s "$BASE/devx/api/health?diagnose=true")
echo "   Status: $(echo $HEALTH | jq -r '.status')"
echo "   Quick Diagnosis: $(echo $HEALTH | jq -r '.quick_diagnosis')"

echo ""
echo "=== All Diagnostics Tests Passed ✅ ==="
```

---

## 10. Implementation Plan (8 Weeks)

### Weeks 1-2: Core Infrastructure
- [ ] Define Pydantic models (DiagnosticRequest, DiagnosticResponse, etc.)
- [ ] Implement `/devx/api/diagnose` endpoint skeleton
- [ ] Add fallback rule-based diagnosis (5 common failure modes)
- [ ] Write unit tests for confidence calculation

**Deliverable**: Working endpoint with rule-based fallback

### Weeks 3-4: LLM Integration
- [ ] Implement LLM prompt generation (`build_diagnostic_prompt`)
- [ ] Add LLM call with timeout and error handling
- [ ] Parse LLM response into DiagnosticResponse schema
- [ ] Test with phi3:mini on known failure scenarios

**Deliverable**: LLM-powered diagnosis working for top 3 failure modes

### Weeks 5-6: UI & Alerting
- [ ] Create Diagnostics page in Next.js frontend (`/tools/diagnostics`)
- [ ] Integrate auto-diagnosis into RoundtripChart component
- [ ] Add `/devx/api/diagnose/history` endpoint
- [ ] Implement Slack webhook for critical alerts (optional)

**Deliverable**: Full diagnostic UI with alert integration

### Weeks 7-8: Optimization & Documentation
- [ ] Implement diagnostic caching (5-minute TTL)
- [ ] Add baseline metrics comparison
- [ ] Write comprehensive documentation (this spec + API docs)
- [ ] Run verification script on staging environment
- [ ] Update `AI_Philosophy_Integration_Summary.md` with alignment score

**Deliverable**: Production-ready diagnostics with full documentation

---

## 11. Philosophy Alignment

| Principle | How This Spec Addresses It | Score (0-10) |
|-----------|---------------------------|--------------|
| **AI at Every Layer** | LLM analyzes metrics instead of fixed rules | 9 |
| **Explainability** | Every diagnosis includes evidence and confidence | 10 |
| **Forgiving Intelligence** | Handles partial data, ambiguous symptoms, novel failures | 8 |
| **Curiosity Before Certainty** | Low-confidence diagnoses suggest further investigation | 7 |
| **Adaptation Over Perfection** | Learns from past incidents (via history endpoint) | 6 |
| **Holism** | Correlates symptoms across services (UCNRR → Core → Frontend) | 9 |
| **Self-Evolution** | Future: train model on resolved incidents | 5 |

**Overall Alignment**: **7.7/10** (Strong alignment with room for learning improvements)

---

## 12. Success Criteria

1. ✅ **Endpoint Operational**: `POST /devx/api/diagnose` returns valid DiagnosticResponse
2. ✅ **LLM Integration**: Successfully uses phi3:mini for analysis
3. ✅ **Confidence Scoring**: All diagnoses have confidence ∈ [0, 1]
4. ✅ **Remediation Quality**: At least 3 actionable steps per diagnosis
5. ✅ **Fallback Robustness**: Works without LLM (rule-based mode)
6. ✅ **UI Integration**: Diagnostics visible in DevX frontend
7. ✅ **Verification**: All test cases pass (5/5)
8. ✅ **Documentation**: Complete spec + API reference + verification script

---

## 13. Future Enhancements

### 13.1 Learning from Resolutions
Store diagnosis + remediation + outcome:
```python
class DiagnosticOutcome(BaseModel):
    diagnosis_id: str
    remediation_applied: str
    resolved: bool
    resolution_time_min: int
    feedback: Optional[str]  # Human annotation
```

Use this data to:
- Rank remediation steps by historical success rate
- Fine-tune LLM prompt with past examples
- Detect recurring issues

### 13.2 Predictive Diagnostics
Analyze metric trends to predict failures before they occur:
- "UCNRR latency trending up 15%/hour → will exceed threshold in 2 hours"

### 13.3 Multi-LLM Ensemble
Run diagnosis through multiple models (phi3, llama3.1) and ensemble results for higher confidence.

### 13.4 Interactive Debugging
Allow user to ask follow-up questions:
- User: "Why is UCNRR slow?"
- System: "Checking... LLM model is llama3.1:8b (known slow). Recent p95: 1500ms. Recommend phi3:mini."

---

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LLM hallucination** | Incorrect diagnosis | Fallback rules, confidence scoring, human review |
| **High LLM latency** | Slow diagnostics | 5s timeout, cached results (5min TTL) |
| **Metric collection failure** | Incomplete data | Graceful degradation, partial diagnosis |
| **Prompt injection** | Security risk | Sanitize user_symptom input, no eval() |
| **Over-reliance on AI** | Engineers skip manual checks | Always show raw metrics alongside diagnosis |

---

## 15. Summary

The DevX AI Diagnostics subsystem brings **adaptive intelligence** to system monitoring. Instead of manually correlating metrics, engineers get natural-language explanations with concrete next steps. This aligns with ReDNA's philosophy: **AI is not an add-on, it's the organism**.

**Key Innovations**:
1. **LLM-Powered Root Cause Analysis**: Correlates symptoms across services
2. **Confidence-Annotated Output**: Transparent uncertainty
3. **Actionable Remediation**: Ranked by impact/effort with bash commands
4. **Graceful Degradation**: Rule-based fallback when LLM unavailable
5. **Historical Learning**: Future training data from resolved incidents

**Next Steps**: Await approval from Codex for implementation kickoff.

---

**End of Phase 6.3 Specification**
