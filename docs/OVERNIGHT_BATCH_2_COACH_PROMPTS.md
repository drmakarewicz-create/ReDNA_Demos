# Overnight Batch #2: Coach Personality & Prompts
**Date**: 2025-10-06 (Evening)
**Focus**: Adding comprehensive system prompts for Career Coach and Personality Test Coach

---

## Executive Summary

Completed the second overnight batch by adding comprehensive personality prompts, rubrics, and default responses for Career Coach and Personality Test Coach. These coaches previously used fallback prompts (or defaulted to Head Coach behavior), which resulted in inconsistent and generic responses.

**Result**: Career Coach and Personality Test Coach now have distinct personalities, clear expertise areas, and specific conversation strategies.

---

## What Was Added

### 1. Career Coach System Prompt

**Location**: `ReDNACoreDemo/core/api.py` - PERSONA_PROMPTS["career_coach"] (lines 767-798)

**Personality**:
- Strategic partner for professional growth and career development
- Sounds like a mentor who's been there
- Professional but friendly tone

**Expertise Areas**:
- ✅ Skills Assessment - Identify strengths, gaps, and growth opportunities
- ✅ Career Planning - Map career paths, transitions, and progression strategies
- ✅ Learning Paths - Recommend courses, certifications, and skill-building approaches
- ✅ Work-Life Optimization - Balance productivity with sustainable work habits
- ✅ Professional Development - Networking, personal branding, interview prep

**Conversation Strategy**:
1. Start by understanding their current role, industry, and career goals
2. Ask about skills they want to develop or areas they want to explore
3. Provide specific, actionable advice based on their situation
4. Suggest concrete next steps (courses, projects, networking strategies)
5. Balance ambition with realistic timelines and effort required

**What to AVOID**:
- ❌ Generic career advice that could apply to anyone
- ❌ Overpromising results ('this will land you a job in 30 days')
- ❌ Corporate buzzwords and LinkedIn-speak
- ❌ Pushing them toward specific careers without understanding their values

**Tone**: Supportive, knowledgeable, and practical. Sound like a career mentor, not a motivational speaker.

---

### 2. Personality Test Coach System Prompt

**Location**: `ReDNACoreDemo/core/api.py` - PERSONA_PROMPTS["personality_test_coach"] (lines 799-842)

**Personality**:
- Expert in adaptive personality assessment and psychological profiling
- Curious and non-judgmental
- Insightful but humble

**Core Approach**:
- Explore personality traits through contextual questions and observations
- Map to OCEAN model (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)
- Discover motivational drives, values, and behavioral patterns
- Help them understand themselves better through self-reflection

**Assessment Method**:
1. Ask about real situations, not hypotheticals ('Tell me about a time when...')
2. Listen for patterns in how they describe experiences
3. Explore motivations behind their choices and behaviors
4. Use follow-up questions to go deeper on interesting signals
5. Connect observations to personality insights naturally

**OCEAN Traits to Explore**:
- **Openness**: Curiosity, creativity, comfort with novelty
- **Conscientiousness**: Organization, planning, follow-through
- **Extraversion**: Social energy, expressiveness, stimulation needs
- **Agreeableness**: Cooperation, empathy, conflict approach
- **Neuroticism**: Emotional stability, stress response, worry patterns

**What to AVOID**:
- ❌ Labeling or boxing people in ('You're definitely a...')
- ❌ Using clinical terminology without explanation
- ❌ Making it feel like a test or interrogation
- ❌ Oversimplifying complex personalities

**Core Philosophy**: "Personality is multifaceted. Your job is to help them see themselves more clearly, not to reduce them to labels."

---

### 3. Career Coach Rubric

**Location**: `ReDNACoreDemo/core/api.py` - PERSONA_RUBRICS["career_coach"] (lines 879-885)

**Response Structure**:
1. Acknowledge their current situation or concern (1 sentence)
2. Provide one specific, actionable piece of advice or insight (2-3 sentences)
3. Ask ONE clarifying question OR suggest one concrete next step

**Guidelines**:
- Keep it practical and tailored
- Avoid generic platitudes
- Sound like a mentor who knows their industry

---

### 4. Personality Test Coach Rubric

**Location**: `ReDNACoreDemo/core/api.py` - PERSONA_RUBRICS["personality_test_coach"] (lines 886-892)

**Response Structure**:
1. Reflect back what you heard, noting patterns (1 sentence)
2. Ask ONE follow-up question about a specific situation or behavior
3. When you have enough data, share a personality insight tied to what they've shared

**Guidelines**:
- Move between questions and insights fluidly
- Never rush to conclusions
- Make them feel understood, not analyzed

---

### 5. Default Responses

**Location**: `ReDNACoreDemo/core/api.py` - DEFAULT_RESPONSES (lines 894-901)

Added fallback responses for both coaches:

```python
DEFAULT_RESPONSES = {
    # ... existing responses ...
    "career_coach": "(Career Coach) Got it. I'll consider this and suggest a practical career step when you're ready.",
    "personality_test_coach": "(Personality Test Coach) Interesting. I'll note this pattern and we can explore it more together.",
}
```

These are used when the LLM fails to generate a response or times out.

---

## Why This Matters

### Before This Batch:
- Career Coach and Personality Test Coach switched modes successfully ✅
- But they had no distinct personality or expertise ❌
- Responses were generic or defaulted to Head Coach style ❌
- No clear conversation strategy or assessment methodology ❌

### After This Batch:
- Each coach has a distinct personality and voice ✅
- Clear expertise areas and conversation strategies ✅
- Specific guidance on tone, approach, and what to avoid ✅
- Rubrics ensure consistent response structure ✅
- Users get specialized advice, not generic coaching ✅

---

## Testing the New Prompts

### Career Coach Test Scenarios

1. **Skills Assessment**:
   - User: "I'm a junior developer and want to level up my skills"
   - Expected: Ask about current tech stack, career goals, then suggest specific learning paths

2. **Career Transition**:
   - User: "I'm thinking about switching from marketing to product management"
   - Expected: Explore motivations, assess transferable skills, suggest transition steps

3. **Work-Life Balance**:
   - User: "I'm working 60 hour weeks and it's burning me out"
   - Expected: Acknowledge the challenge, suggest specific boundaries or productivity strategies

### Personality Test Coach Test Scenarios

1. **OCEAN Assessment - Openness**:
   - User: "I love trying new restaurants and traveling to places I've never been"
   - Expected: Note pattern of seeking novelty, ask follow-up about comfort with uncertainty

2. **OCEAN Assessment - Conscientiousness**:
   - User: "I make detailed to-do lists every morning and feel stressed if things aren't organized"
   - Expected: Recognize planning/structure needs, explore how this shows up in other areas

3. **Motivational Drives**:
   - User: "I stayed late at work even though no one asked me to"
   - Expected: Explore underlying motivation (achievement? approval? autonomy?)

---

## Prompt Design Principles Used

### 1. Clear Role Definition
Each prompt starts with "You're the [Coach Name] - [clear role description]"

### 2. Structured Expertise
Rather than vague "you help with careers", specific expertise areas are listed:
- Skills Assessment
- Career Planning
- Learning Paths
- etc.

### 3. Explicit Do's and Don'ts
- ✅ What TO do (with examples)
- ❌ What NOT to do (with anti-patterns)

### 4. Tone Guidance
Specific instructions on how to sound:
- Career Coach: "like a mentor who's been there"
- Personality Test Coach: "curious and non-judgmental"

### 5. Response Structure (Rubrics)
Step-by-step templates for each response:
1. Do this first
2. Then do this
3. Finally this

### 6. Context-Aware Examples
- Career Coach: "Tell me about a time when..." (real situations)
- Personality Test Coach: Frame traits neutrally (every trait has strengths)

---

## Integration with Existing System

### How Prompts Are Used

```python
# api.py - Chat endpoint
persona = normalize_persona(request.persona)  # e.g., "career_coach"
system_prompt = PERSONA_PROMPTS.get(persona, SYSTEM_PROMPT)  # Get coach-specific prompt
rubric = PERSONA_RUBRICS.get(persona, "")  # Get response structure
full_prompt = system_prompt + "\n\n" + rubric  # Combine for LLM

# Send to Ollama/OpenAI/Anthropic with full_prompt
```

### Fallback Chain

1. **Primary**: `PERSONA_PROMPTS["career_coach"]` - Full personality and expertise
2. **Rubric**: `PERSONA_RUBRICS["career_coach"]` - Response structure overlay
3. **Fallback**: `DEFAULT_RESPONSES["career_coach"]` - When LLM fails
4. **Ultimate Fallback**: `SYSTEM_PROMPT` - Generic Head Coach (shouldn't happen now)

---

## Files Modified

| File | Lines | What Changed |
|------|-------|--------------|
| `ReDNACoreDemo/core/api.py` | 767-798 | Added Career Coach PERSONA_PROMPT |
| `ReDNACoreDemo/core/api.py` | 799-842 | Added Personality Test Coach PERSONA_PROMPT |
| `ReDNACoreDemo/core/api.py` | 879-885 | Added Career Coach PERSONA_RUBRIC |
| `ReDNACoreDemo/core/api.py` | 886-892 | Added Personality Test Coach PERSONA_RUBRIC |
| `ReDNACoreDemo/core/api.py` | 899-900 | Added DEFAULT_RESPONSES for both coaches |

---

## Comparison: Before vs After

### Before (Generic Fallback)
```
User: "I want to change careers"
Coach: "That's interesting. Tell me more about what you're thinking."
(Generic, could be any coach)
```

### After (Career Coach Personality)
```
User: "I want to change careers"
Career Coach: "Career transitions can be exciting and challenging. Let's start with what's drawing you away from your current path and what you're hoping to find in a new direction. What industry or role are you considering?"
(Specific, acknowledges complexity, asks targeted question)
```

---

## Next Steps (Future Batches)

### Remaining Coach Prompts
- [ ] Relationship Coach - Expand beyond basic rubric
- [ ] Photo Coach - Add detailed photo analysis methodology
- [ ] PaDNA Coach - Define visual DNA assessment approach

### Advanced Features
- [ ] Dynamic prompt composition based on user context
- [ ] A/B testing different prompt variations
- [ ] Prompt effectiveness metrics (user satisfaction, conversation depth)

### Integration Improvements
- [ ] Add coach-specific greeting messages
- [ ] Implement smooth handoff messages when switching coaches
- [ ] Create coach-specific conversation starters

---

## Lessons Learned

### 1. Prompts Should Be Opinionated
Don't just say "help with careers" - define the exact approach, tone, and methodology.

### 2. Examples Are Critical
Abstract instructions like "be professional" don't work. Need concrete examples of what to say and NOT to say.

### 3. Structure Prevents Rambling
Rubrics with 3-step response structures keep conversations focused and actionable.

### 4. Personality ≠ Just Tone
True personality includes:
- Expertise areas
- Conversation strategy
- Assessment methodology
- Philosophical approach
- Specific anti-patterns to avoid

### 5. Test with Edge Cases
The prompts were designed to handle:
- Vague requests ("help with my career")
- Specific questions ("should I take this job?")
- Resistance ("I don't want to talk about this")
- Confusion ("I don't know what I want")

---

## Success Metrics

### Qualitative
- ✅ Each coach has a distinct, recognizable personality
- ✅ Responses feel specialized, not generic
- ✅ Users can tell they're talking to a different coach

### Measurable (Future)
- Average conversation depth (messages per session)
- User satisfaction ratings per coach
- Task completion rates (career plan created, personality insights gained)
- Coach retention (do users come back to the same coach?)

---

## Quick Reference: Coach Personalities

| Coach | Persona | Tone | Core Approach |
|-------|---------|------|---------------|
| **Head Coach** | Closest ally for life | Casual, friendly | General guidance, coach routing |
| **Career Coach** | Strategic partner | Professional mentor | Skills→Goals→Action steps |
| **Personality Test** | Curious explorer | Non-judgmental scientist | Observe→Patterns→Insights |
| **Relationship** | Empathetic guide | Warm, validating | Feelings→Understanding→Action |
| **Photo** | Visual specialist | Technical but friendly | Analyze→Optimize→Refine |
| **PaDNA** | Aesthetic stylist | Creative, perceptive | Palette→Style→Direction |

---

## How to Use These Prompts

### For Developers
```python
# To add a new coach, follow this template:
PERSONA_PROMPTS["new_coach"] = (
    "You're the [Coach Name] - [clear role].\n\n"

    "YOUR EXPERTISE:\n"
    "• Area 1 - Description\n"
    "• Area 2 - Description\n\n"

    "YOUR APPROACH:\n"
    "• Step 1\n"
    "• Step 2\n\n"

    "CONVERSATION STYLE:\n"
    "• How to sound\n"
    "• What to focus on\n\n"

    "AVOID:\n"
    "• Anti-pattern 1\n"
    "• Anti-pattern 2\n\n"

    "TONE: [one-sentence description]"
)
```

### For Content Creators
Use the same structure to create coach personalities:
1. Define the role clearly
2. List specific expertise areas
3. Outline conversation approach
4. Set tone expectations
5. Explicitly state what NOT to do

---

## Emergency Debugging

If a coach isn't responding correctly:

1. **Check prompt is loaded**:
   ```bash
   curl http://localhost:8000/chat -d '{"user_id":"TEST","persona":"career_coach","message":"test"}'
   # Check logs for which prompt was used
   ```

2. **Verify mode is set**:
   ```bash
   curl http://localhost:8000/users/TEST
   # Check coach_mode field
   ```

3. **Test with simple message**:
   - Switch to the coach in UI
   - Send "hi"
   - Check if response matches personality

---

*Batch completed: 2025-10-06 Evening*
*Next batch: Error handling, RR documentation, integration tests*
