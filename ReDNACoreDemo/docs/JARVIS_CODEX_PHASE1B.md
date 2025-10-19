# Jarvis-Codex Interface — Phase 1B (HC Proposal Generator)

**Date:** 2025-10-10
**Status:** ✅ Complete
**LOC:** ~700 (Guardrails: 285, Generator: 395, Orchestrator: +160)

---

## Overview

Phase 1B enables Head Coach to autonomously generate UI improvement proposals through heuristics and optional LLM assistance. HC can identify text/style improvement opportunities and submit them to the Jarvis-Codex guarded approval workflow.

**Key principle:** HC generates proposals only—no auto-apply. All changes require human review and approval via DevX panel.

---

## Architecture

### Components

1. **CodexGuardrails** (`ReDNACoreDemo/core/jarvis_codex/codex_guardrails.py`)
   - Validates proposals against hard constraints
   - Enforces scope, confidence, language, and diff size limits
   - Blocks marketing language and all-caps text

2. **ProposalGenerator** (`ReDNACoreDemo/core/jarvis_codex/proposal_generator.py`)
   - Analyzes UI files for improvement candidates
   - Applies heuristic rewrites (e.g., "Self-Improvement" → "Adaptive Learning")
   - Optional LLM-assisted text improvement
   - Validates proposals before submission

3. **HC Orchestrator Integration** (`ReDNACoreDemo/core/hc_orchestrator.py`)
   - `maybe_propose_ui_improvements()` method
   - Triggers on explicit command, analysis results, or cadence
   - Logs telemetry for all proposals

---

## Guardrails

### Hard Constraints

**1. Allowed Paths**
```python
allowed_paths = [
    "web/src/",
    "devx/frontend/src/"
]
```
Only UI files in these directories can be modified. Backend code protected.

**2. File Size Limit**
- Maximum: **50 KB** per file
- Prevents large bundled files from being processed

**3. Allowed Change Types** (Phase 1B)
- `text_replace`: Simple text substitution
- `style_token_swap`: CSS utility class changes (e.g., `bg-blue-500` → `bg-emerald-600`)

**4. Confidence Threshold**
- Minimum: **0.85**
- Low-confidence proposals automatically dropped

**5. Diff Size Limit**
- Maximum: **12 lines** per proposal
- Prevents large structural changes

**6. Label Length Limit**
- Maximum: **80 characters**
- Ensures concise UI text

**7. Language Rules**
- **Concise:** No verbose or redundant phrasing
- **Neutral:** No marketing language (e.g., "amazing", "revolutionary")
- **No exclamation marks**
- **No all-caps** (except acronyms ≤3 chars)

### Blocked Words

Marketing/hype words that trigger rejection:
- "amazing", "incredible", "revolutionary", "best", "perfect"
- "guaranteed", "free", "limited", "exclusive", "premium"
- "ultimate", "extraordinary", "exceptional", "outstanding"

---

## Proposal Generation

### Heuristic Rewrites

**Heuristic 1: Remove redundant "Panel" suffix**
```python
"Configuration Panel" → "Configuration"
# Confidence: 0.85
```

**Heuristic 2: "Self-Improvement" → "Adaptive Learning"**
```python
"Self-Improvement Panel" → "Adaptive Learning"
# Applies both H1 and H2, final: "Adaptive Learning"
# Confidence: 0.88
```

**Heuristic 3: Remove trailing ellipsis**
```python
"Loading..." → "Loading"
# Confidence: 0.80
```

**Heuristic 4: Remove action verbs from button text**
```python
"Click to Submit" → "Submit"
# Confidence: 0.82
```

### LLM-Assisted Rewrites

When `ANTHROPIC_API_KEY` is available:

**Prompt Template:**
```
Rewrite this UI label to be more concise and clear:

Original: "{text}"
Context: {context}

Rules:
- Maximum 80 characters
- Concise, neutral language (no marketing speak)
- No exclamation marks
- Preserve key meaning

Return ONLY the improved label, nothing else.
```

**Model:** `claude-3-5-sonnet-20241022`
**Confidence:** 0.90 (if similarity < 0.9 vs original)

**Fallback:** If LLM fails or produces similar text, falls back to heuristic rewrites.

---

## Trigger Mechanisms

### 1. Explicit Command

User or HC sends command:
```python
{
  "explicit_command": "optimize UI labels in DevX"
}
```

**Behavior:**
- Scans `devx/frontend/src/` or `web/src/` based on command
- Generates up to `max_proposals` (default: 5)
- Uses LLM if available

### 2. Analysis-Driven (Self-Improvement)

Triggered after `/learning/analyze` shows recurring confusion:

```python
{
  "analysis_results": {
    "confusion_signals": {
      "modules": [
        {
          "name": "DevX Self-Improvement",
          "confused_text": ["panel", "configuration"]
        }
      ]
    }
  }
}
```

**Behavior:**
- Identifies confused modules
- Scans relevant directories
- Generates context-aware proposals (e.g., "address confusion: panel, configuration")

### 3. Threshold Cadence

Periodic check (e.g., daily):
```python
trigger_context = None  # No explicit context
```

**Behavior:**
- Light scan of recent files (`devx/frontend/src/routes`)
- Low-volume proposals (routine checks)

---

## API Integration

HC submits proposals via existing endpoint:

**Endpoint:** `POST /jarvis_codex/propose`

**Payload:**
```json
{
  "scope": "frontend",
  "file": "devx/frontend/src/routes/self-improvement/SelfImprovementPanel.tsx",
  "intent": "Improve clarity: tighten label for clarity",
  "suggested_change": {
    "type": "text_replace",
    "before": "Self-Improvement Panel",
    "after": "Adaptive Learning Dashboard"
  },
  "confidence": 0.90,
  "source": "head_coach"
}
```

**Response:**
```json
{
  "ok": true,
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "diff_preview": "...",
  "confidence": 0.90,
  "time_ms": 25.3
}
```

---

## Usage Examples

### Example 1: Explicit Command via Orchestrator

```python
from ReDNACoreDemo.core.hc_orchestrator import create_orchestrator

orchestrator = create_orchestrator()

trigger_context = {
    "explicit_command": "optimize UI labels in DevX"
}

proposals = orchestrator.maybe_propose_ui_improvements(
    user_id="TEST",
    trigger_context=trigger_context,
    max_proposals=5
)

print(f"Generated {len(proposals)} proposals")
for p in proposals:
    print(f"  - {p['file']}: {p['intent']}")
```

### Example 2: Analysis-Driven Proposals

```python
# After /learning/analyze detects confusion
analysis_results = {
    "confusion_signals": {
        "modules": [
            {"name": "DevX Trait Workshop", "confused_text": ["value model", "semantics"]}
        ]
    }
}

trigger_context = {"analysis_results": analysis_results}

proposals = orchestrator.maybe_propose_ui_improvements(
    user_id="TEST",
    trigger_context=trigger_context,
    max_proposals=3
)
```

### Example 3: Direct Proposal Generation

```python
from ReDNACoreDemo.core.jarvis_codex.proposal_generator import create_proposal_generator
from pathlib import Path

generator = create_proposal_generator(
    project_root=Path.cwd(),
    llm_client=None  # Use heuristics only
)

# Scan directory for proposals
proposals = generator.scan_directory_for_proposals(
    directory=Path("web/src/components"),
    intent_context="routine UI clarity check",
    max_proposals=10,
    use_llm=False
)

print(f"Found {len(proposals)} improvement opportunities")
```

---

## DevX Workflow

HC-generated proposals appear in DevX Jarvis-Codex panel with:
- **Source badge:** "head_coach"
- **Intent description:** Context for improvement (e.g., "address confusion: panel")
- **Confidence score:** 0.85–1.00
- **Diff preview:** Before/after comparison

**Review process:**
1. Open DevX → Jarvis-Codex panel
2. Filter by source: "head_coach"
3. Review proposal metadata and diff
4. Approve or reject

---

## Telemetry

**Location:** `prompts/insights/hc_orchestrator_telemetry.jsonl`

**Event Type:** `codex_proposed`

**Example Entry:**
```json
{
  "ts": "2025-10-10T03:15:30.123456+00:00",
  "user_id": "TEST",
  "event_type": "codex_proposed",
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "file": "devx/frontend/src/routes/self-improvement/SelfImprovementPanel.tsx",
  "intent": "Improve clarity: tighten label for clarity",
  "confidence": 0.90
}
```

**Query Examples:**
```bash
# Count HC proposals
grep '"event_type":"codex_proposed"' prompts/insights/hc_orchestrator_telemetry.jsonl | wc -l

# Average confidence
grep '"event_type":"codex_proposed"' prompts/insights/hc_orchestrator_telemetry.jsonl | jq '.confidence' | awk '{s+=$1} END {print s/NR}'

# Proposals by file
grep '"event_type":"codex_proposed"' prompts/insights/hc_orchestrator_telemetry.jsonl | jq '.file' | sort | uniq -c
```

---

## Testing

**Test Suite:** `ReDNACoreDemo/tests/test_jarvis_codex_phase1b.py`

**Scenarios:**
1. ✅ Valid text_replace proposal passes guardrails
2. ✅ Oversized diff rejected (>12 lines)
3. ✅ Low confidence rejected (<0.85)
4. ✅ Style token swap allowed
5. ✅ Invalid scope rejected (non-frontend)
6. ✅ Marketing language rejected
7. ✅ Invalid file path rejected
8. ✅ Heuristic rewrites work correctly
9. ✅ File analysis extracts candidates
10. ✅ Proposal generation from candidates
11. ✅ Low confidence proposals dropped
12. ✅ Orchestrator explicit command trigger
13. ✅ Orchestrator telemetry logging
14. ✅ Analysis-driven proposal generation
15. ✅ End-to-end pipeline: file → heuristic → proposal

**Run tests:**
```bash
PYTHONPATH=.:ReDNACoreDemo:$PYTHONPATH python3 -m pytest \
  ReDNACoreDemo/tests/test_jarvis_codex_phase1b.py -v
```

**Expected:** 16/16 passing

---

## Security Considerations

### Threat Model

**1. Malicious Proposals**
- **Mitigated by:** Scope enforcement, guardrails validation
- Backend code unreachable
- All proposals require human approval

**2. Low-Quality Auto-Generated Text**
- **Mitigated by:** Confidence threshold (0.85), language rules
- Marketing language blocked
- Heuristic fallback if LLM fails

**3. Excessive Proposal Volume**
- **Mitigated by:** `max_proposals` limit (default: 5)
- Rate limiting via cadence trigger
- Human review required for all

**4. Path Traversal**
- **Mitigated by:** Validated against `allowed_paths`
- Relative paths resolved safely
- File size limit (50KB)

---

## Configuration

### Guardrails Config

```python
guardrails_config = {
    "allowed_paths": [
        "web/src/",
        "devx/frontend/src/"
    ],
    "max_file_size_kb": 50,
    "allowed_change_types": [
        "text_replace",
        "style_token_swap"
    ],
    "min_confidence": 0.85,
    "max_diff_lines": 12,
    "max_label_chars": 80,
    "language_rules": {
        "concise": True,
        "neutral": True,
        "non_marketing": True
    }
}
```

### Proposal Generator Config

```python
from ReDNACoreDemo.core.jarvis_codex.proposal_generator import create_proposal_generator
import anthropic
import os

# With LLM
llm_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) if os.getenv("ANTHROPIC_API_KEY") else None

generator = create_proposal_generator(
    project_root=Path.cwd(),
    guardrails_config=guardrails_config,
    llm_client=llm_client
)
```

---

## Troubleshooting

### No Proposals Generated

**Possible causes:**
1. No improvable text found (heuristics too strict)
2. All candidates filtered by guardrails
3. File paths not in allowed scopes

**Solution:**
- Lower `min_confidence` (not recommended)
- Adjust heuristic thresholds in `_has_improvement_potential()`
- Check file paths match allowed scopes

### Low Confidence Scores

**Possible causes:**
1. LLM unavailable (using heuristics only)
2. Text already concise
3. Minimal improvement possible

**Solution:**
- Set `ANTHROPIC_API_KEY` for LLM assistance
- Review heuristic rules
- Accept that not all text needs improvement

### Guardrails Rejecting Valid Proposals

**Possible causes:**
1. Text contains marketing words
2. Diff too large (>12 lines)
3. Label too long (>80 chars)

**Solution:**
- Review `language_rules` configuration
- Increase `max_diff_lines` if needed (not recommended)
- Break large changes into multiple proposals

---

## Next Steps

### Phase 1C: Enhanced Generator (Future)
- AST-based semantic refactoring
- Multi-line structure changes
- Accessibility improvements (aria-labels, alt text)

### Phase 2: Style System Integration (Future)
- Design token management
- Theme consistency checks
- Color contrast validation

### Phase 3: A/B Testing (Future)
- Generate alternative phrasings
- Track approval rates
- Learn from rejections

---

## References

- **Phase 1 Backend:** [JARVIS_CODEX_PHASE1.md](JARVIS_CODEX_PHASE1.md)
- **DevX UI Panel:** [JARVIS_CODEX_PHASE1.md#devx-ui-panel](JARVIS_CODEX_PHASE1.md#devx-ui-panel)
- **Test Suite:** [test_jarvis_codex_phase1b.py](../tests/test_jarvis_codex_phase1b.py)
- **Orchestrator:** [hc_orchestrator.py](../core/hc_orchestrator.py)

---

**Phase 1B Complete** ✅
HC can now generate small, guarded UI proposals autonomously.
