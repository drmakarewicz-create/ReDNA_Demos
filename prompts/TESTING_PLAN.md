# Head Coach AI Ingestion — Testing Plan

## Overview

This testing plan validates that the new HC system prompt correctly:
1. Detects factual statements in natural language
2. Structures them as canonical evidence
3. Routes them through the ingestion pipeline
4. Updates resolved.json automatically
5. Maintains natural conversational tone
6. Handles edge cases gracefully

---

## Test Environment Setup

### Prerequisites

```bash
# 1. Ensure server is running with new logging
curl http://127.0.0.1:8015/health

# 2. Clear test user data
rm -rf data/users/HC_TEST_*

# 3. Start log monitoring
tail -f /tmp/core_pipeline.log | grep "chat_"
```

### Test Users

Create dedicated test users for each scenario:
- `HC_TEST_BASIC` - Basic fact extraction
- `HC_TEST_AMBIG` - Ambiguous statements
- `HC_TEST_CONFLICT` - Conflicting data
- `HC_TEST_PREFERENCE` - Non-factual preferences
- `HC_TEST_META` - Meta-traits and unknowns

---

## Test Scenarios

### Scenario 1: Direct Physical Fact

**Objective**: Verify HC extracts clear factual statements with high confidence

**Test Case 1.1: Height**
```
Input: "I am 6 feet tall."

Expected Extraction:
{
  "trait_id": "PaDNA.BodyDNA.Height",
  "value": {"text": "6 feet tall"},
  "confidence_llm": 0.85-0.95,
  "raw_text": "I am 6 feet tall"
}

Expected Ingestion:
✅ evidence.json contains trait_id with timestamp
✅ resolved.json has PaDNA.BodyDNA.Height = "6 feet tall"
✅ UCN ≥ 0.8
✅ resolver_traces/<req_id>.json exists

Expected HC Response (natural):
"Got it — 6 feet tall! That's helpful context."
OR
"Six feet tall — nice! Are you more of an indoorsy or outdoorsy person?"

Validation:
```bash
curl -s "http://127.0.0.1:8015/ui/unabridged?user_id=HC_TEST_BASIC" | jq '.traits[] | select(.trait_id | contains("Height"))'
```
```

**Test Case 1.2: Eye Color**
```
Input: "I have blue eyes."

Expected Extraction:
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "blue"},
  "confidence_llm": 0.9-1.0
}

Expected Ingestion:
✅ resolved.json has PaDNA.EyeDNA.IrisColor = "blue"
✅ Inferences triggered:
   - PaDNA.SkinDNA.Freckles = "higher_likelihood"
   - PaDNA.HairDNA.DarknessPrior = "slightly_lower"

Expected HC Response:
"Blue eyes — I got that. Do you have lighter or darker hair?"

Validation:
- Check for 3 traits (direct + 2 inferences)
- Verify inference provenance tags
```

**Test Case 1.3: Age**
```
Input: "I'm 30 years old."

Expected Extraction:
{
  "trait_id": "BasicDNA.Age",
  "value": {"text": "30 years old"},
  "confidence_llm": 0.9
}

Expected Ingestion:
✅ BasicDNA.Age in resolved.json
✅ No inferences (age doesn't trigger rules)

Expected HC Response:
"Noted — 30 years old. What brings you here today?"
```

---

### Scenario 2: Ambiguous or Qualified Statements

**Objective**: Verify HC handles uncertainty appropriately

**Test Case 2.1: Vague Measurement**
```
Input: "I think I'm about six feet."

Expected Extraction:
{
  "trait_id": "PaDNA.BodyDNA.Height",
  "value": {"text": "about six feet"},
  "confidence_llm": 0.5-0.7,
  "ambiguity_flags": ["qualified_statement"]
}

Expected Ingestion:
✅ Evidence stored with ucn_prior = 0.5-0.7
✅ resolved.json updated but with lower UCN

Expected HC Response (clarifying):
"About six feet — got it. Is that pretty accurate or more of a rough estimate?"
```

**Test Case 2.2: Uncertain Color**
```
Input: "I think my eyes are blueish gray."

Expected Extraction:
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "blue-gray"},  # OR {"text": "blueish gray"}
  "confidence_llm": 0.4-0.6,
  "needs_confirmation": true
}

Expected Ingestion:
✅ Evidence stored
✅ UCN = 0.4-0.6 (medium confidence)
✅ Partial inferences (lower confidence than with "blue")

Expected HC Response:
"Blue-gray eyes sound really striking! Do they tend to look more blue or gray depending on the light?"

Validation:
- UCN should be < 0.7
- Curiosity score should remain elevated (0.4-0.6)
```

---

### Scenario 3: Conflicting Information

**Objective**: Verify HC handles contradictions gracefully

**Test Case 3.1: Eye Color Correction**
```
Message 1: "I have blue eyes."
Message 2: "Actually I have brown eyes."

Expected Extraction (Message 2):
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "brown"},
  "confidence_llm": 0.9,
  "provenance": "correction"
}

Expected Ingestion:
✅ Blue eyes evidence marked deprecated
✅ Brown eyes becomes canonical value
✅ Inferences updated (freckles likelihood decreases, hair darkness increases)
✅ Conflict logged in provenance

Expected HC Response:
"Ah, brown eyes — got it! That makes more sense."
OR
"Brown eyes it is! I'll update that."

Validation:
```bash
# Check evidence.json has both entries
jq '.items[] | select(.trait_id == "PaDNA.EyeDNA.IrisColor")' data/users/HC_TEST_CONFLICT/evidence.json

# Check resolved.json has brown (not blue)
jq '.["PaDNA.EyeDNA.IrisColor"].value' data/users/HC_TEST_CONFLICT/resolved.json
# Should return: {"enum": "brown"}
```
```

---

### Scenario 4: Non-Factual Statements

**Objective**: Verify HC doesn't over-extract or create spurious traits

**Test Case 4.1: Preference Statement**
```
Input: "I like pizza."

Expected Extraction:
{
  "trait_id": "PreferenceDNA.Food.Pizza",
  "value": {"text": "likes"},
  "confidence_llm": 0.8
}
# OR no extraction if pizza isn't in trait ontology

Expected Ingestion:
✅ If extracted: stored as preference, NOT physical trait
✅ No physical/demographic traits created

Expected HC Response:
"Pizza is always a solid choice! What's your go-to topping?"

Validation:
- Verify NO PaDNA, BasicDNA, or BehaviorDNA traits created
- If PreferenceDNA created, that's acceptable
```

**Test Case 4.2: Conversational Filler**
```
Input: "How are you?"

Expected Extraction:
None (purely conversational)

Expected Ingestion:
✅ No evidence items created
✅ Pipeline not called (or called with empty list)

Expected HC Response:
"I'm here and ready to help! How are you doing today?"

Validation:
```bash
# Check logs show no extraction
grep "chat_extract{req_id=<req_id>, user=HC_TEST_PREFERENCE, items=0}" /tmp/core_pipeline.log
```
```

**Test Case 4.3: Question to HC**
```
Input: "Do you think I should dye my hair?"

Expected Extraction:
None (user asking, not stating)

Expected Ingestion:
✅ No evidence created

Expected HC Response:
"That's a big decision! What color are you thinking about?"

Validation:
- No traits created
- Logs show 0 items extracted
```

---

### Scenario 5: Meta-Traits & Behavioral Cues

**Objective**: Verify HC captures meta-information

**Test Case 5.1: Explicit Unknown**
```
Input: "I don't know my height."

Expected Extraction:
{
  "trait_id": "PaDNA.BodyDNA.Height",
  "value": {"text": "unknown"},
  "status": "unknown",
  "confidence_llm": 0.9  # High confidence that it's unknown
}

Expected Ingestion:
✅ Height trait marked with status: unknown
✅ Curiosity score elevated (0.9+)

Expected HC Response:
"No worries! We can figure that out later if needed."

Validation:
- Check curiosity queue (when implemented)
- Verify trait marked as high-priority for future queries
```

**Test Case 5.2: Reported Perception**
```
Input: "People say I look athletic."

Expected Extraction:
{
  "trait_id": "PaDNA.BodyDNA.Build",  # OR SelfImage.Athletic
  "value": {"text": "athletic"},
  "confidence_llm": 0.3-0.4,  # Lower confidence (3rd party)
  "provenance": "reported_perception"
}

Expected Ingestion:
✅ Evidence stored with low UCN (0.3-0.4)
✅ Provenance tag indicates "reported perception"

Expected HC Response:
"Interesting! Do you feel athletic yourself, or is that mostly others' perception?"

Validation:
- UCN should be significantly lower than direct self-report
- Provenance field should indicate 3rd party source
```

---

### Scenario 6: Complex Multi-Fact Statements

**Objective**: Verify HC extracts multiple facts from single message

**Test Case 6.1: Multiple Physical Traits**
```
Input: "I'm 6 feet tall with blue eyes and brown hair."

Expected Extraction:
[
  {
    "trait_id": "PaDNA.BodyDNA.Height",
    "value": {"text": "6 feet tall"},
    "confidence_llm": 0.9
  },
  {
    "trait_id": "PaDNA.EyeDNA.IrisColor",
    "value": {"enum": "blue"},
    "confidence_llm": 0.9
  },
  {
    "trait_id": "PaDNA.HairDNA.Color.Natural",
    "value": {"enum": "brown"},
    "confidence_llm": 0.9
  }
]

Expected Ingestion:
✅ All 3 traits stored
✅ All 3 appear in resolved.json
✅ Inferences triggered based on combinations

Expected HC Response:
"Got it — 6 feet, blue eyes, brown hair. That's a great combo!"

Validation:
```bash
# Count traits
jq '.items | length' data/users/HC_TEST_COMPLEX/evidence.json
# Should be >= 3 (plus any inferences)
```
```

**Test Case 6.2: Narrative with Facts Embedded**
```
Input: "I'm a 30-year-old software engineer from Boston. I love hiking and have blue eyes."

Expected Extraction:
[
  {"trait_id": "BasicDNA.Age", "value": {"text": "30 years old"}},
  {"trait_id": "BasicDNA.Occupation", "value": {"text": "software engineer"}},
  {"trait_id": "BasicDNA.Location", "value": {"text": "Boston"}},
  {"trait_id": "BehaviorDNA.Hobbies", "value": {"text": "hiking"}},
  {"trait_id": "PaDNA.EyeDNA.IrisColor", "value": {"enum": "blue"}}
]

Expected Ingestion:
✅ All facts extracted and stored
✅ No facts missed due to sentence complexity

Expected HC Response:
"Cool! Boston-based software engineer who loves hiking with blue eyes — I'm getting a clear picture of you!"

Validation:
- Verify at least 4-5 traits extracted
- Check that both demographic and behavioral traits captured
```

---

## Regression Tests

### Ensure Existing Functionality Still Works

**RT-1: Fallback Extraction**
```
Input: "I have purple eyes" (non-standard color)

Expected:
✅ Fallback extractor catches it
✅ Evidence stored even if HC misses it
✅ No data loss
```

**RT-2: Onboarding Flow**
```
Use case: User goes through onboarding wizard

Expected:
✅ Onboarding data still ingests correctly
✅ HC doesn't interfere with structured form inputs
✅ All onboarding traits appear in resolved.json
```

**RT-3: Goal Setting**
```
Use case: User sets a goal

Expected:
✅ Goal data stored separately from physical traits
✅ HC doesn't extract goals as evidence
✅ Goal system continues to function
```

---

## Performance Tests

### PT-1: Extraction Latency

**Objective**: Ensure HC doesn't slow down responses

```python
import time

start = time.time()
response = chat_send(user_id, "I am 6 feet tall")
latency = time.time() - start

assert latency < 3.0  # Response within 3 seconds
```

**Target**: < 2 seconds for simple messages

### PT-2: Batch Extraction

**Objective**: Handle multiple facts efficiently

```
Input: 10 facts in one message

Expected latency: < 5 seconds
Expected extraction rate: 100% (all 10 facts captured)
```

---

## Edge Cases

### EC-1: Unicode & Special Characters
```
Input: "Mi nombre es José. Tengo ojos azules."

Expected:
✅ Unicode handled correctly
✅ Eye color extracted despite language
```

### EC-2: Extremely Long Message
```
Input: 500-word narrative with 3 facts embedded

Expected:
✅ All 3 facts extracted
✅ No timeout errors
```

### EC-3: Rapid-Fire Messages
```
User sends 5 messages in 10 seconds

Expected:
✅ All messages processed
✅ All extractions completed
✅ No race conditions in evidence storage
```

---

## Validation Script

```bash
#!/bin/bash
# Run all test scenarios

echo "=== HC AI Ingestion Test Suite ==="

# Scenario 1: Direct Facts
echo "[TEST 1.1] Height extraction"
curl -X POST http://127.0.0.1:8015/ui/chat/send \
  -H "Content-Type: application/json" \
  -d '{"user_id":"HC_TEST_BASIC","persona":"head_coach","text":"I am 6 feet tall","client_ts":1760500000000}' \
  -s | jq '.message_id'

sleep 2
HEIGHT=$(jq -r '.["PaDNA.BodyDNA.Height"].value.text' data/users/HC_TEST_BASIC/resolved.json 2>/dev/null)
if [[ "$HEIGHT" == *"6 feet"* ]]; then
  echo "✅ PASS: Height extracted"
else
  echo "❌ FAIL: Height not found in resolved.json"
fi

# Scenario 2: Eye color + inferences
echo "[TEST 1.2] Eye color with inferences"
curl -X POST http://127.0.0.1:8015/ui/chat/send \
  -H "Content-Type: application/json" \
  -d '{"user_id":"HC_TEST_BASIC","persona":"head_coach","text":"I have blue eyes","client_ts":1760500001000}' \
  -s | jq '.message_id'

sleep 2
INFERENCES=$(jq -r 'keys[] | select(contains("Freckles") or contains("DarknessPrior"))' data/users/HC_TEST_BASIC/resolved.json 2>/dev/null | wc -l)
if [[ "$INFERENCES" -ge 1 ]]; then
  echo "✅ PASS: Inferences triggered"
else
  echo "❌ FAIL: No inferences found"
fi

# Add more test cases...

echo "=== Test Suite Complete ==="
```

---

## Success Criteria

For the HC AI Ingestion system to be considered **production-ready**, it must achieve:

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Extraction Accuracy** | ≥ 95% | Manually validate 100 test messages |
| **Ingestion Success Rate** | ≥ 98% | Check pipeline logs for failures |
| **False Positive Rate** | ≤ 5% | Verify no spurious traits created |
| **Response Latency** | < 3s p95 | Monitor response times |
| **Conversation Quality** | ≥ 4.5/5 | User ratings on naturalness |
| **Conflict Handling** | 100% | All conflicts logged and resolved |

---

## Monitoring Dashboard

### Key Metrics to Track (Post-Deployment)

```yaml
extraction_rate:
  query: count(chat_extract.items > 0) / count(chat_messages)
  target: "> 0.3"  # 30% of messages contain facts

confidence_distribution:
  query: histogram(confidence_llm)
  target: "Peak at 0.8-0.9 (high confidence)"

ingestion_failures:
  query: count(CRITICAL: Failed to process)
  target: "< 5 per day"

inference_trigger_rate:
  query: count(inferred > 0) / count(ingested > 0)
  target: "> 0.4"  # 40% of ingestions trigger inferences
```

---

## Rollback Plan

If critical issues arise post-deployment:

1. **Immediate**: Set `extraction_mode: "fallback_only"` in config
2. **24 hours**: Revert to old extractor code
3. **48 hours**: Root cause analysis and fix
4. **Re-deploy**: With fixes and additional tests

---

## Appendix: Test Data Sets

### Golden Test Set (20 messages)

```yaml
# data/test_sets/hc_golden_set.yaml
messages:
  - text: "I am 6 feet tall"
    expected_traits: ["PaDNA.BodyDNA.Height"]
    expected_confidence: 0.9

  - text: "I have blue eyes"
    expected_traits: ["PaDNA.EyeDNA.IrisColor", "PaDNA.SkinDNA.Freckles"]
    expected_confidence: 0.9

  - text: "I think I'm about 30"
    expected_traits: ["BasicDNA.Age"]
    expected_confidence: 0.6

  # ... 17 more test cases
```

---

© ReDNA Project 2025 — HC AI Ingestion Testing Plan
