# Head Coach Automated Testing Guide

## Overview

The `test_hc_conversations.py` script automatically tests Head Coach behavior by simulating conversations and validating responses against expected behavior.

## Test Scenarios

### 1. Boundary Respect
**Tests:** Does HC respect "not now" or "later" boundaries?

**Scenario:**
- User mentions wanting relationship help
- User says "not right now" and changes topic to pizza
- User asks follow-up restaurant question

**Expected:**
- ✅ HC should NOT mention Relationship Coach again
- ✅ HC should answer pizza/restaurant questions
- ✅ HC should not force topic back to relationships

---

### 2. Topic Flexibility
**Tests:** Can HC handle casual topics without pivoting to goals?

**Scenario:**
- User asks about TV shows
- User asks follow-up questions about the show

**Expected:**
- ✅ HC should discuss TV shows naturally
- ✅ HC should NOT pivot to relationships, goals, or coaches
- ✅ HC should answer follow-ups about the show

---

### 3. Simple Question Answering
**Tests:** Does HC answer simple questions directly?

**Scenario:**
- User asks about weather, books, colors

**Expected:**
- ✅ HC should answer each question
- ✅ HC should NOT redirect to "important" topics
- ✅ HC should NOT suggest coaches for casual questions

---

### 4. No Repetitive Questions
**Tests:** Does HC avoid asking the same question multiple times?

**Scenario:**
- User mentions work stress
- User deflects/changes topic multiple times

**Expected:**
- ✅ HC should ask different questions each turn
- ✅ HC should NOT loop on same question
- ✅ HC should accept topic changes

---

### 5. Coach Suggestion Limits
**Tests:** Does HC only suggest each coach once per conversation?

**Scenario:**
- User asks about dating
- User declines coach help
- User continues dating discussion

**Expected:**
- ✅ HC should mention Relationship Coach maximum ONCE
- ✅ HC should not re-suggest after user says no
- ✅ HC can continue conversation without pushing coach

---

### 6. Frustration Detection
**Tests:** Does HC recognize and respond to user frustration?

**Scenario:**
- User expresses frustration: "I already told you..."
- User questions HC behavior: "Why do you keep..."

**Expected:**
- ✅ HC should apologize
- ✅ HC should change approach
- ✅ HC should NOT defend or justify

---

## How to Run Tests

### Prerequisites
1. Core API must be running on port 8015
2. Python 3.8+ with `requests` library

### Run All Tests
```bash
python3 test_hc_conversations.py
```

### Run Individual Test
Edit the script and comment out unwanted tests in `run_all_tests()`.

---

## Output

### Console Output
```
================================================================================
HEAD COACH AUTOMATED TESTING SUITE
================================================================================
Core API: http://127.0.0.1:8015
Test User: hc_test_user
Output Directory: ReDNACoreDemo/data/hc_conversation_reviews/automated_tests
✅ Core API is running

================================================================================
TEST SCENARIO 1: Boundary Respect
================================================================================

User (Turn 1): I'm feeling lonely and want to find a partner
HC: That's tough—feeling lonely is hard. What's been making it especially difficult lately?

User (Turn 2): I'd be interested in the Relationship Coach but not right now. Can you recommend a good pizza place?
HC: Joe's Pizza in Manhattan is amazing—classic NY slice. What neighborhood are you in?

User (Turn 3): Any other restaurant suggestions?
HC: Roberta's in Brooklyn has great pizza and a cool vibe. Worth checking out!

--------------------------------------------------------------------------------
✅ TEST PASSED - HC respected boundaries

================================================================================
TEST SUMMARY
================================================================================
✅ PASS - Boundary Respect
✅ PASS - Topic Flexibility
✅ PASS - Simple Questions
✅ PASS - No Repetitive Questions
✅ PASS - Coach Suggestion Limits
✅ PASS - Frustration Detection

6/6 tests passed (100%)

🎉 ALL TESTS PASSED!
```

### Transcript Files
Each test saves a JSON transcript to:
```
ReDNACoreDemo/data/hc_conversation_reviews/automated_tests/
├── boundary_respect_20251004_201530.json
├── topic_flexibility_20251004_201545.json
├── simple_questions_20251004_201600.json
├── no_repetitive_questions_20251004_201615.json
├── coach_suggestion_limits_20251004_201630.json
└── frustration_detection_20251004_201645.json
```

You can review these transcripts manually to see exactly how HC behaved.

---

## Validation Rules

Tests use configurable validation rules:

```python
validation = {
    # HC should never say these phrases
    "should_not_contain": ["Relationship Coach", "let's get back to"],

    # HC should say at least once
    "should_contain": ["pizza"],

    # Maximum times HC can ask similar question
    "max_repetitions": 1,

    # If user says these, HC should drop the topic
    "respect_boundaries": ["not right now", "later"],
    "boundary_topic": "Relationship Coach"
}
```

---

## Adding New Tests

### 1. Create Test Function
```python
def test_my_scenario(tester: ConversationTester):
    """Test description."""
    messages = [
        "User message 1",
        "User message 2",
        "User message 3",
    ]

    passed, issues = tester.run_test_scenario("my_scenario", messages)

    validation = {
        "should_not_contain": ["bad phrase"],
        "should_contain": ["good phrase"],
    }

    analysis_issues = tester.analyze_conversation("my_scenario", validation)
    tester.save_transcript("my_scenario")

    if analysis_issues:
        print("❌ TEST FAILED")
        for issue in analysis_issues:
            print(f"  - {issue}")
    else:
        print("✅ TEST PASSED")

    return len(analysis_issues) == 0
```

### 2. Add to Test Suite
```python
tests = [
    # ... existing tests ...
    ("My Scenario", test_my_scenario),
]
```

---

## Common Test Patterns

### Test: Coach Mention Counting
```python
hc_responses = [e["text"] for e in tester.conversation_history if e["role"] == "assistant"]
coach_mentions = sum(1 for r in hc_responses if "Relationship Coach" in r)

if coach_mentions > 1:
    issues.append(f"Mentioned coach {coach_mentions} times (max 1)")
```

### Test: Apology Detection
```python
# Find user frustration signal
for i, entry in enumerate(tester.conversation_history):
    if entry["role"] == "member" and "I already told you" in entry["text"]:
        # Check next HC response for apology
        next_hc = [e for e in tester.conversation_history[i+1:] if e["role"] == "assistant"][0]
        if not any(word in next_hc["text"].lower() for word in ["sorry", "apologize"]):
            issues.append("No apology after frustration")
```

### Test: Topic Pivot Detection
```python
# User asks about TV, HC should not pivot to goals
if "TV" in user_msg and any(word in hc_response for word in ["goal", "relationship", "career"]):
    issues.append("HC pivoted from casual topic to goals")
```

---

## Interpreting Results

### ✅ All Tests Pass
- HC prompts are working well
- LLM is following instructions
- Safe to deploy to users

### ⚠️ Some Tests Fail
- Review failed test transcripts
- Identify patterns in failures
- Update prompts to address issues
- Re-run tests

### ❌ Most Tests Fail
- Major prompt issues
- LLM may not be capable enough (consider upgrading from Llama to GPT-4o)
- Review [ANALYSIS_20251004_MISSTEPS.md](ReDNACoreDemo/data/hc_conversation_reviews/ANALYSIS_20251004_MISSTEPS.md) for prompt fixes

---

## Best Practices

### 1. Run Tests After Prompt Changes
Always run the full test suite after modifying HC prompts to ensure no regressions.

### 2. Test with Different LLMs
Run tests with:
- Llama 3.1 (baseline)
- GPT-4o-mini (faster, better)
- GPT-4o (best quality)

Compare results to see which LLM handles prompts best.

### 3. Create Tests from Real User Issues
When you get a bad transcript from a real user:
1. Create a test scenario that reproduces the issue
2. Verify it fails with current prompts
3. Fix prompts
4. Verify test now passes
5. Add to test suite permanently

### 4. Regression Testing
Keep all tests in the suite even after fixing issues. This prevents regressions when making future changes.

---

## Advanced: Continuous Integration

### Future Enhancement
Set up automated testing that runs:
- On every prompt change (git hook)
- Daily (cron job)
- Before deploying to production

Example:
```bash
# Run tests and fail if any fail
python3 test_hc_conversations.py
if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Not deploying."
    exit 1
fi
```

---

## Troubleshooting

### Core API Not Running
```
❌ ERROR: Core API is not running. Please start Core first.
```
**Solution:** Start Core via CP++ or manually:
```bash
cd ReDNACoreDemo
uvicorn core.api:build_app --factory --port 8015
```

### Connection Timeout
```
Error sending message: HTTPConnectionPool... Read timed out
```
**Solution:** Increase timeout in script or check if Core is overloaded.

### Test User Data Persists
Tests use user_id `hc_test_user`. If you want fresh state each run:
```bash
rm -rf ReDNACoreDemo/data/users/hc_test_user
```

---

## Example: Comparing Before/After Prompt Changes

### Before (Old Prompts)
```bash
$ python3 test_hc_conversations.py

TEST SUMMARY
❌ FAIL - Boundary Respect
❌ FAIL - Topic Flexibility
✅ PASS - Simple Questions
❌ FAIL - No Repetitive Questions
❌ FAIL - Coach Suggestion Limits
❌ FAIL - Frustration Detection

2/6 tests passed (33%)
⚠️  4 test(s) failed
```

### After (Fixed Prompts)
```bash
$ python3 test_hc_conversations.py

TEST SUMMARY
✅ PASS - Boundary Respect
✅ PASS - Topic Flexibility
✅ PASS - Simple Questions
✅ PASS - No Repetitive Questions
✅ PASS - Coach Suggestion Limits
✅ PASS - Frustration Detection

6/6 tests passed (100%)
🎉 ALL TESTS PASSED!
```

---

## Summary

**Automated testing allows you to:**
- ✅ Catch prompt issues before users see them
- ✅ Validate fixes work as expected
- ✅ Test edge cases consistently
- ✅ Compare different LLMs objectively
- ✅ Build confidence in HC behavior

**Run tests frequently** - especially after:
- Prompt changes
- LLM upgrades
- Core API updates
- User reports of bad conversations
