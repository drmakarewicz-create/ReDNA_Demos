# Head Coach Conversation Review Setup

## Best Approach: Export Transcript + Structured Review Process

Based on the available features, here's the recommended workflow for reviewing and refining Head Coach conversations:

---

## Option 1: Export Transcript (Recommended for Quick Reviews)

### How to Export
1. Open the Head Coach chat interface
2. Click the **menu button** (three dots) in the transcript panel header
3. Select **"Export JSON"** or **"Export CSV"**

### What You Get
**JSON Format:**
```json
[
  {
    "ts": "2025-10-04T23:15:30.123Z",
    "role": "user",
    "persona": null,
    "text": "I have two dogs"
  },
  {
    "ts": "2025-10-04T23:15:32.456Z",
    "role": "assistant",
    "persona": "head_coach",
    "text": "Two dogs! That's great. What's been the biggest change..."
  }
]
```

**CSV Format:**
```csv
ts,role,persona,text
"2025-10-04T23:15:30.123Z","user","","I have two dogs"
"2025-10-04T23:15:32.456Z","assistant","head_coach","Two dogs! That's great..."
```

### Workflow
1. **Export transcript** after a conversation session
2. **Share the file** with me (paste JSON content or attach file)
3. **I'll analyze** for:
   - Tone issues (too formal, too casual, robotic)
   - Missing context or continuity
   - Unclear or unhelpful responses
   - Opportunities to be more curious/engaging
4. **We'll update prompts** in [api.py:661-691](ReDNACoreDemo/core/api.py#L661)
5. **Restart Core** to test improvements
6. **Iterate**

---

## Option 2: Live Conversation Monitoring (Advanced)

For real-time feedback, I can create a conversation logging system that captures more context.

### What This Would Add
- **Full LLM request/response** (including system prompts sent)
- **Model metadata** (temperature, tokens used, latency)
- **User trait context** (what observations/traits were passed to the LLM)
- **Provider info** (which LLM was used: Ollama, OpenAI, etc.)

### Implementation
I would create:
1. **Logging decorator** in [chat_providers.py](ReDNACoreDemo/core/chat_providers.py)
2. **Conversation log file** in `ReDNACoreDemo/data/users/{user_id}/chat_log.jsonl`
3. **Review endpoint** at `/ui/chat/review/{user_id}` for easy access

### Benefit
You could see exactly what prompts/context the LLM received, making it easier to debug why responses are stiff or off-tone.

---

## Option 3: Snapshot-Based Review (Already Available!)

The **Snapshots** feature already exists for capturing user state. We could extend it to include recent chat history.

### Current Snapshot Contents
- User observations
- Trait resolutions
- Evidence
- UCN/RR scores

### Enhancement Idea
Add a **"Chat History"** section to snapshots that includes the last N conversation turns.

**Modified snapshot structure:**
```json
{
  "user_id": "TEST",
  "snapshot_ts": "2025-10-04T23:00:00Z",
  "observations": {...},
  "chat_history": [
    {"ts": "...", "role": "user", "text": "..."},
    {"ts": "...", "role": "assistant", "persona": "head_coach", "text": "..."}
  ]
}
```

---

## My Recommendation

**Start with Option 1 (Export Transcript)** because:

1. ✅ **Already built** - no development needed
2. ✅ **Simple workflow** - export, paste, review, update
3. ✅ **Lightweight** - focuses on conversation quality
4. ✅ **Fast iteration** - we can test prompt changes quickly

**Graduate to Option 2 (Live Logging)** if you need:
- Deep debugging of LLM behavior
- Analysis of what context/traits are being passed
- Performance metrics (token usage, latency)
- A/B testing different prompts

---

## Prompt Refinement Process

Once you share a conversation transcript, here's how we'll refine:

### 1. Identify Issues
- **Tone problems**: "Too formal", "Too robotic", "Not curious enough"
- **Context failures**: HC not remembering what user said
- **Unhelpful responses**: Generic advice vs. specific guidance
- **Missed opportunities**: Should have asked a follow-up question

### 2. Update System Prompts
Current prompts at [api.py:661-691](ReDNACoreDemo/core/api.py#L661):

**SYSTEM_PROMPT** (lines 661-666):
```python
SYSTEM_PROMPT = (
    "You are a warm, insightful Head Coach helping someone grow and improve. "
    "Speak naturally and conversationally - like a friendly mentor, not a corporate consultant. "
    "Be curious about what they share, ask thoughtful questions, and offer practical next steps. "
    "Keep responses concise (2-3 sentences) and grounded in what they've told you."
)
```

**PERSONA_PROMPTS["head coach"]** (lines 668-672):
```python
"You're the Head Coach - think of yourself as a trusted guide who coordinates the whole journey. "
"Acknowledge what the person shares, show genuine interest, and help them figure out what to focus on next. "
"Use simple, friendly language. Avoid jargon like 'orchestrate' or 'tailor accordingly.'"
```

**PERSONA_RUBRICS["head coach"]** (line 684):
```python
"Rubric: Be warm and genuinely curious. Acknowledge what they shared, then ask a thoughtful question or suggest one simple next step."
```

### 3. Test & Iterate
1. Update prompts
2. Restart Core
3. Test with similar conversation scenarios
4. Export and review again
5. Repeat until tone feels right

---

## Example Review Session

**You share this transcript:**
```json
[
  {"role": "user", "text": "I'm struggling with work-life balance"},
  {"role": "assistant", "persona": "head_coach", "text": "Let's orchestrate a systematic approach to optimizing your time allocation framework. First, we'll establish baseline metrics for your current allocation, then identify optimization opportunities across your professional and personal domains."}
]
```

**I identify:**
- ❌ Too formal ("orchestrate", "systematic approach", "optimization opportunities")
- ❌ Corporate jargon ("allocation framework", "baseline metrics")
- ❌ Not empathetic (doesn't acknowledge the struggle)
- ❌ Not curious (doesn't ask what's hard about it)

**We update the prompt to emphasize:**
```python
"Avoid business jargon completely. Speak like a caring friend who wants to understand. "
"When someone shares a struggle, acknowledge how hard it is before jumping to solutions."
```

**New response after update:**
> "Work-life balance is tough—I hear you. What's feeling most out of whack right now? Is it the hours, the energy drain, or something else?"

---

## Action Items

**To start reviewing conversations:**

1. ✅ Have a conversation with Head Coach in the UI
2. ✅ Click menu → **Export JSON**
3. ✅ Paste the JSON content in our chat or attach the file
4. ✅ I'll analyze and suggest prompt improvements
5. ✅ We'll update [api.py:661-691](ReDNACoreDemo/core/api.py#L661)
6. ✅ Restart Core and test

**Optional enhancements (we can build later):**
- [ ] Add conversation logging to `chat_providers.py`
- [ ] Create review dashboard endpoint
- [ ] Include chat history in snapshots
- [ ] Build A/B testing framework for prompts

---

## Current Head Coach Configuration

**File:** [ReDNACoreDemo/core/api.py](ReDNACoreDemo/core/api.py#L661)

**Lines to edit:**
- **661-666**: Main system prompt
- **668-672**: Head Coach persona instructions
- **684**: Behavioral rubric

**How to apply changes:**
1. Edit the prompts
2. Save the file
3. Go to CP++ → Stop Core → Start Core
4. Test conversation
5. Export and review

---

## Summary

✅ **Use Export Transcript** for quick, iterative prompt refinement
✅ **Share transcripts** with me to analyze tone, engagement, helpfulness
✅ **Update prompts** in api.py based on feedback
✅ **Test and iterate** until Head Coach feels natural and helpful

Optional: Build advanced logging/monitoring later if needed for deeper analysis.
