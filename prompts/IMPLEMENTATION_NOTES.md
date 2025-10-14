# Head Coach AI Ingestion — Implementation Notes

## Overview

The new HC system prompt transforms the Head Coach from a passive conversational agent into an **active cognitive gateway** that:
- Detects factual information in natural language
- Structures it as canonical evidence
- Routes it through the ReDNA pipeline
- Monitors ingestion success
- Drives curiosity-based follow-up questions

---

## File Locations

### Primary Prompt
**Path**: `/prompts/head_coach_ai_ingestion_v2.md`

**Usage**: This is the system prompt that should be loaded when initializing the Head Coach AI agent.

**Integration point**:
```python
# In HC agent initialization
system_prompt = load_file('prompts/head_coach_ai_ingestion_v2.md')
llm.configure(system_prompt=system_prompt, **config)
```

### Configuration
**Path**: `/prompts/hc_config.yaml` (to be created)

**Recommended parameters**:
```yaml
model: claude-3-5-sonnet-20241022
temperature: 0.7  # Balance creativity with consistency
max_tokens: 1500
context_window: 8192

# Behavioral flags
dev_mode: false  # Set true for verbose extraction logging
strict_extraction: true  # Require canonical trait IDs when possible
confidence_threshold: 0.3  # Minimum confidence to ingest
retry_on_failure: true
max_retries: 1

# Memory configuration
conversation_history_limit: 20  # Last N messages
trait_context_refresh: 5  # Re-fetch resolved traits every N messages
```

---

## Integration with Existing Modules

### 1. Extraction Layer

**Current**:
- `preference_extractor.py` - LLM-based extraction
- `conversation_analyzer.py` - Keyword-based extraction
- `fallback_lex.py` - Regex pattern matching

**New Flow**:
```
User message → HC (with new prompt)
  ↓
HC internally structures evidence using prompt guidelines
  ↓
HC emits extraction intent (conceptually)
  ↓
Backend still calls existing extractors as fallback
  ↓
Merge HC's structured output + extractor output
  ↓
Send to ingest_evidence_roundtrip()
```

**Recommended enhancement**:
Add a new extraction mode: `extraction_mode: "ai_driven"`

```python
# In chat endpoint
if extraction_mode == "ai_driven":
    # HC response includes structured evidence in special format
    hc_evidence = parse_hc_structured_response(hc_response)
    all_observations = hc_evidence + fallback_extract(text)
else:
    # Current flow
    all_observations = preference_extractor.extract() + conversation_analyzer.analyze()
```

### 2. Evidence Format Bridge

**HC Output Format** (from prompt):
```json
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "blue"},
  "confidence_llm": 0.85,
  "extraction_context": "Direct self-report",
  "raw_text": "I have blue eyes"
}
```

**Pipeline Input Format** (canonical):
```json
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "blue"},
  "source": "chat",
  "ts": "2025-10-14T18:00:00Z",
  "ucn_prior": 0.85  # Map from confidence_llm
}
```

**Conversion function** (to be implemented):
```python
def hc_evidence_to_canonical(hc_evidence: dict, user_id: str) -> dict:
    """Convert HC's evidence format to canonical pipeline format."""
    return {
        "trait_id": hc_evidence["trait_id"],
        "value": hc_evidence["value"],
        "source": "chat",
        "ts": now_iso(),
        "ucn_prior": hc_evidence.get("confidence_llm", 0.5),
        "provenance": hc_evidence.get("extraction_context", "llm_extraction"),
        "raw_text": hc_evidence.get("raw_text", "")
    }
```

### 3. Response Parsing

**Challenge**: HC responses are natural language, not structured JSON

**Solution Options**:

**Option A: Structured Output Mode** (Claude 3.5 Sonnet supports this)
```python
# Request structured output alongside natural response
response = claude.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[...],
    tools=[
        {
            "name": "ingest_evidence",
            "description": "Store factual evidence about the user",
            "input_schema": {
                "type": "object",
                "properties": {
                    "trait_id": {"type": "string"},
                    "value": {"type": "object"},
                    "confidence_llm": {"type": "number"}
                }
            }
        }
    ]
)

# Parse tool calls
evidence_items = [call for call in response.tool_calls if call.name == "ingest_evidence"]
```

**Option B: XML Tagging** (simpler, works with any LLM)
```python
# Instruct HC to wrap evidence in XML tags
<evidence>
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "blue"},
  "confidence_llm": 0.85
}
</evidence>

# Parse in backend
evidence_match = re.search(r'<evidence>(.*?)</evidence>', response, re.DOTALL)
if evidence_match:
    evidence = json.loads(evidence_match.group(1))
```

**Option C: Post-Processing Agent** (most robust)
```python
# After HC responds, run extraction agent
extraction_agent_prompt = f"""
Based on this user message: "{user_text}"
And HC response: "{hc_response}"

Extract all factual evidence mentioned. Return JSON array:
[
  {{"trait_id": "...", "value": {{}}, "confidence_llm": 0.0-1.0}}
]
"""
extracted_evidence = extraction_agent.run(extraction_agent_prompt)
```

**Recommendation**: Use **Option A** (structured output) for production, **Option B** (XML) as fallback.

---

## Recommended LLM Parameters

### For Production

```yaml
model: claude-3-5-sonnet-20241022
temperature: 0.7
max_tokens: 1500
top_p: 0.9

# System prompt configuration
system_prompt_file: prompts/head_coach_ai_ingestion_v2.md
inject_user_context: true  # Add current traits to each request

# Context injection format
user_context_template: |
  Current known traits for {user_id}:
  - Height: {height} (UCN: {height_ucn})
  - Eye color: {eye_color} (UCN: {eye_color_ucn})
  - Age: {age} (UCN: {age_ucn})

  High-curiosity traits: {curiosity_list}
```

### For Testing/Dev Mode

```yaml
temperature: 0.3  # More deterministic
dev_mode: true
verbose_logging: true

# Append to each response
response_suffix: |
  [DEV MODE]
  Extracted: {evidence_count} items
  Ingested: {ingestion_status}
  Curiosity updated: {curiosity_changes}
```

---

## Pipeline Modifications Needed

### 1. Add `confidence_llm` Support

**File**: `core/ingest/evidence_schema.py`

```python
def validate_and_fix(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize evidence record."""
    out = dict(ev)

    # Map confidence_llm → ucn_prior if present
    if "confidence_llm" in out and "ucn_prior" not in out:
        out["ucn_prior"] = out.pop("confidence_llm")

    # ... rest of validation
    return out
```

### 2. Add Provenance Tracking

**File**: `core/ingest/pipeline.py`

```python
def _store_evidence(...):
    # Add extraction_context to provenance
    for ev in evidence:
        if "extraction_context" in ev:
            ev["provenance"] = ev.pop("extraction_context")
```

### 3. Curiosity Feedback Loop

**File**: `core/api.py` (chat endpoint)

After successful ingestion:
```python
# Calculate curiosity changes
before_curiosity = get_curiosity_scores(user_id)
# ... ingestion happens ...
after_curiosity = get_curiosity_scores(user_id)

curiosity_delta = {
    trait_id: after - before_curiosity.get(trait_id, 0)
    for trait_id, after in after_curiosity.items()
    if abs(after - before_curiosity.get(trait_id, 0)) > 0.1
}

# Log for HC awareness (future: pass to next request)
logger.info(f"Curiosity changes: {curiosity_delta}")
```

---

## Testing Infrastructure

### Unit Tests

**File**: `tests/test_hc_ai_ingestion.py`

```python
import pytest
from core.hc_ai_extraction import parse_hc_evidence, hc_evidence_to_canonical

def test_parse_direct_fact():
    """HC extracts 'I am 6 feet tall' correctly."""
    hc_response = """
    Got it — 6 feet tall! That's helpful.
    <evidence>
    {
      "trait_id": "PaDNA.BodyDNA.Height",
      "value": {"text": "6 feet tall"},
      "confidence_llm": 0.9
    }
    </evidence>
    """

    evidence = parse_hc_evidence(hc_response)
    assert len(evidence) == 1
    assert evidence[0]["trait_id"] == "PaDNA.BodyDNA.Height"
    assert evidence[0]["confidence_llm"] == 0.9

def test_ambiguous_extraction():
    """HC handles 'I think my eyes are blueish gray' with lower confidence."""
    # ... similar test
    assert evidence[0]["confidence_llm"] < 0.6

def test_no_extraction_for_preferences():
    """'I like pizza' should not create physical trait."""
    # ... test that PreferenceDNA trait is created, not PaDNA
```

### Integration Tests

**File**: `tests/integration/test_hc_pipeline_e2e.py`

```python
def test_end_to_end_ingestion(test_user):
    """Full flow: message → extraction → ingestion → resolved.json"""

    # Send message
    response = chat_send(test_user, "I have blue eyes")

    # Check evidence stored
    evidence = load_evidence(test_user)
    assert any(e["trait_id"] == "PaDNA.EyeDNA.IrisColor" for e in evidence["items"])

    # Check resolved
    resolved = load_resolved(test_user)
    assert "PaDNA.EyeDNA.IrisColor" in resolved
    assert resolved["PaDNA.EyeDNA.IrisColor"]["value"]["enum"] == "blue"

    # Check inferences triggered
    assert "PaDNA.SkinDNA.Freckles" in resolved  # Inference from blue eyes
```

---

## Deployment Checklist

- [ ] Create `/prompts/hc_config.yaml` with recommended parameters
- [ ] Implement evidence parsing (Option A or B)
- [ ] Add `confidence_llm` → `ucn_prior` mapping in evidence schema
- [ ] Update chat endpoint to use HC structured output
- [ ] Add curiosity feedback calculation
- [ ] Create unit tests for evidence parsing
- [ ] Create integration tests for end-to-end flow
- [ ] Add dev mode toggle in config
- [ ] Document XML tagging format for HC responses
- [ ] Monitor extraction rate in production logs

---

## Monitoring & Observability

### Key Metrics to Track

```python
# In /core/api.py chat endpoint
metrics = {
    "extraction_rate": extracted_items / total_messages,
    "ingestion_success_rate": ingested_items / extracted_items,
    "confidence_distribution": histogram(confidence_llm values),
    "curiosity_delta_avg": avg(curiosity changes per message),
    "conflict_rate": conflicts_detected / total_ingestions
}

logger.info(f"HC_METRICS: {metrics}")
```

### Log Queries for Analysis

```bash
# How many facts are being extracted per message?
grep "chat_extract" /tmp/core_pipeline.log | awk '{print $6}' | stats

# What's the average confidence?
grep "confidence_llm" /tmp/core_pipeline.log | extract_json | jq '.confidence_llm' | stats

# Are there ingestion failures?
grep "CRITICAL: Failed to process" /tmp/core_pipeline.log
```

---

## Future Enhancements

### Phase 2a

1. **Active Curiosity Prompting**
   - Inject high-curiosity traits into HC context
   - HC asks strategic questions based on curiosity scores

2. **Self-Report Credibility Index (SRCI)**
   - Track HC's extraction accuracy per user
   - Adjust confidence_llm based on user's SRCI

3. **Conflict Detection & Resolution**
   - HC detects contradictions mid-conversation
   - Prompts user for clarification before ingesting

### Phase 2b

4. **Multi-Modal Extraction**
   - Extract traits from images (via Photo Coach handoff)
   - Extract from uploaded documents
   - Extract from external data sources

5. **Inference Suggestion**
   - HC proposes inferences before they're auto-applied
   - User can accept/reject inferred traits

---

## Rollout Strategy

### Week 1: Internal Testing
- Deploy with `dev_mode=true`
- Test with 5-10 internal users
- Collect extraction accuracy data

### Week 2: A/B Test
- 50% users: new HC prompt
- 50% users: old extraction flow
- Compare ingestion rates and user satisfaction

### Week 3: Full Rollout
- Deploy to all users
- Monitor metrics dashboard
- Collect user feedback

### Week 4: Optimization
- Tune confidence thresholds based on data
- Adjust curiosity prompting frequency
- Refine canonical trait ID mappings

---

## Support & Troubleshooting

### Common Issues

**Problem**: HC not extracting facts
- **Check**: System prompt loaded correctly
- **Fix**: Verify prompt file path in config

**Problem**: Evidence format errors
- **Check**: `confidence_llm` → `ucn_prior` mapping
- **Fix**: Update evidence_schema.py validation

**Problem**: Too many extractions (false positives)
- **Check**: Confidence threshold setting
- **Fix**: Increase `confidence_threshold` in config

**Problem**: User finds HC too data-hungry
- **Check**: Curiosity prompting frequency
- **Fix**: Reduce follow-up question rate

---

## Contact & Documentation

- **Prompt file**: `/prompts/head_coach_ai_ingestion_v2.md`
- **Config**: `/prompts/hc_config.yaml`
- **Tests**: `/tests/test_hc_ai_ingestion.py`
- **Logs**: `/tmp/core_pipeline.log`
- **Monitoring**: Grafana dashboard (TBD)

For questions or improvements, see `docs/PRINCIPLES.md` Section VIII (Experience & Feedback).

---

© ReDNA Project 2025 — HC AI Ingestion Implementation Guide
