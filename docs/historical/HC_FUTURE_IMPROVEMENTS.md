# Head Coach Future Improvements

## Priority 1: Data Ingestion & ReDNA Container Analysis

### Current State
Head Coach is primarily conversational - it responds to users but doesn't actively extract and store trait inferences into the ReDNA system.

### Desired State
**"Hungry Data Extraction"** - HC should:
- Analyze every user statement for trait signals
- Extract word choices, emotional reactions, preferences
- Identify what excites, offends, or motivates the user
- Feed observations to UCN/RR for trait inference
- Fill/refine ReDNA containers automatically during conversation

### Example Scenario

**User says:** "I just wish I could find the right guy"

**Current behavior:**
- HC responds conversationally
- Maybe suggests Relationship Coach
- No data extraction

**Desired behavior:**
- HC responds conversationally (still warm and helpful)
- **Background extraction:**
  - Observation: User expressed desire for romantic partner (heterosexual orientation inferred)
  - Observation: User used "wish" (implies longing, possible loneliness trait signal)
  - Observation: User said "the right guy" (suggests high standards or past unsuccessful matches)
  - Feed to UCN/RR → update relationship status, relationship goals, possibly loneliness/connection traits
  - Store word choice patterns: "wish", "find", "right" → language style analysis

### Technical Architecture

#### Option A: Real-Time Extraction During Chat

**Flow:**
1. User sends message
2. HC generates response (LLM)
3. **NEW**: Before sending response, run extraction pipeline:
   - Parse user message for trait signals
   - Identify emotional valence (positive/negative)
   - Extract preferences, values, concerns
   - Call UCN/RR API to infer traits
   - Update observations in user profile
4. Send HC response to user

**Files to modify:**
- `ReDNACoreDemo/core/api.py` - `/ui/chat/send` endpoint (line ~2524)
- Create new `conversation_analyzer.py` module
- Integrate with existing `curiosity_engine.py` (line 643)

**Pros:**
- Real-time enrichment
- Every conversation builds user profile
- No additional user action needed

**Cons:**
- Adds latency to chat responses
- May slow down conversation flow

---

#### Option B: Async Background Analysis

**Flow:**
1. User sends message
2. HC generates and returns response immediately
3. **Background task**: Analyze conversation asynchronously
   - Parse last N turns of conversation
   - Extract trait signals in batch
   - Update user profile
   - No impact on response time

**Implementation:**
- Use Python `asyncio` or background task queue
- Process conversation analysis separately from chat flow

**Pros:**
- No latency impact on user experience
- Can do deeper analysis (more compute time)

**Cons:**
- Slight delay before traits appear in profile
- More complex architecture

---

### Data Extraction Categories

What should HC extract and analyze?

#### 1. **Explicit Preferences**
- "I like X" / "I hate Y"
- "I want to find a partner"
- "I'm not interested in Z"

→ Store in observations, feed to trait inference

#### 2. **Emotional Signals**
- Positive words: "awesome", "great", "love"
- Negative words: "tough", "hard", "struggling"
- Intensity: "really", "very", "extremely"

→ Track emotional patterns, mood trends

#### 3. **Values & Priorities**
- "Family is important to me"
- "Work is great"
- "I value X"

→ Infer core values, life priorities

#### 4. **Word Choice Patterns**
- Formal vs. casual language
- Specific vocabulary (jargon, slang)
- Sentence complexity

→ Build communication style profile

#### 5. **Topics of Interest**
- What user brings up repeatedly
- What they avoid discussing
- What they ask follow-up questions about

→ Identify engagement patterns, interests

#### 6. **Relationship Signals**
- Mentions of friends, family, partners
- Relationship status indicators
- Social connection quality

→ Update relationship context, social traits

---

### Implementation Plan

#### Phase 1: Basic Observation Extraction (Easiest)
**Goal:** Extract explicit statements and store as observations

**Steps:**
1. Add keyword/phrase detection to chat endpoint
2. When user mentions key topics (dating, work, family, etc.), create observation
3. Store in `observations.json`

**Example code location:**
```python
# In ReDNACoreDemo/core/api.py around line 2600
# After getting user message, before generating HC response:

def _extract_observations_from_message(user_id: str, message: str) -> None:
    """Extract trait signals from user message."""
    observations = []

    # Relationship signals
    if any(word in message.lower() for word in ["dating", "partner", "boyfriend", "girlfriend", "relationship"]):
        observations.append({
            "trait": "relationship_interest",
            "signal": "mentioned romantic relationships",
            "raw_text": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Family signals
    if any(word in message.lower() for word in ["family", "mom", "dad", "parents", "siblings"]):
        observations.append({
            "trait": "family_connection",
            "signal": "mentioned family",
            "raw_text": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # Store observations
    if observations:
        _store_chat_observations(user_id, observations)
```

---

#### Phase 2: LLM-Based Extraction (Medium Complexity)
**Goal:** Use LLM to extract nuanced traits from conversation

**Approach:**
- Send user message to LLM with extraction prompt
- Ask LLM to identify: emotional tone, preferences, values, concerns
- Structure output as JSON
- Feed to UCN/RR for trait inference

**Example extraction prompt:**
```python
EXTRACTION_PROMPT = """
Analyze this user message and extract trait signals:

User message: "{message}"

Extract:
1. Emotional tone (positive/negative/neutral and intensity 1-5)
2. Explicit preferences mentioned (what they like/dislike)
3. Values or priorities expressed
4. Concerns or challenges mentioned
5. Topics they seem interested in

Return as JSON:
{
  "emotional_tone": {"valence": "positive", "intensity": 3},
  "preferences": ["likes family time", "wants romantic partner"],
  "values": ["family", "relationships"],
  "concerns": ["finding right partner"],
  "interests": ["dating", "relationships"]
}
"""
```

---

#### Phase 3: Full UCN/RR Integration (Advanced)
**Goal:** Automatically update ReDNA containers based on conversation

**Flow:**
1. Extract observations (Phase 1 or 2)
2. Call UCN/RR API with new observations
3. UCN/RR infers traits and updates user profile
4. Curiosity engine tracks what's been learned
5. HC uses updated profile in future conversations

**Files to integrate:**
- `ReDNACoreDemo/core/api.py` - chat endpoint
- `ReDNACoreDemo/core/curiosity_engine.py` - track learning
- UCN/RR API - trait inference
- `observations.json`, `resolved.json` - data storage

---

### Success Metrics

After implementation, a 10-turn conversation should result in:
- **5-10 new observations** stored in user profile
- **2-3 trait inferences** made by UCN/RR
- **Curiosity score updated** based on what was learned
- **No noticeable latency** in chat responses (if async)

---

## Priority 2: UI/UX Improvements for Chat Transcript

### Current Issues

#### Issue 2a: Manual Scrolling Required
**Problem:** After sending message, user must manually scroll in transcript to find HC response

**User Experience:**
1. User types in text box
2. User hits Enter
3. Response appears in transcript (somewhere above)
4. User must scroll to find it
5. Breaks conversation flow

**Expected behavior:**
- Transcript should **auto-scroll to newest message**
- User shouldn't have to hunt for response

---

#### Issue 2b: Limited Transcript Space
**Problem:** Transcript area is cramped due to:
- Large header (workspace label, navigation, status badges, user switcher, import buttons)
- Large persona rail (right side)
- Large text box at bottom
- Result: Small viewport for actual conversation

**Current layout:**
```
┌─────────────────────────────────────────────────┐
│  LARGE HEADER (workspace, nav, status, etc.)    │ ← Takes vertical space
├──────────────────────────┬──────────────────────┤
│                          │                      │
│                          │  PERSONA RAIL        │ ← Takes horizontal space
│   TRANSCRIPT AREA        │  (Right pane)        │
│   (Cramped!)             │                      │
│                          │                      │
├──────────────────────────┴──────────────────────┤
│  LARGE TEXT BOX (composer)                      │ ← Takes vertical space
└─────────────────────────────────────────────────┘
```

**Desired layout:**
- More space for transcript
- Easy-to-follow conversation flow
- Less scrolling required

---

### Solutions

#### Solution 2a: Auto-Scroll to Latest Message

**Implementation:**
File: `web/src/components/transcript-panel.tsx`

**Current behavior:**
- Transcript doesn't auto-scroll when new messages arrive

**Fix:**
Add `scrollIntoView` when new message is added:

```typescript
// In transcript-panel.tsx, after new message is added:
useEffect(() => {
  if (entries.length > 0) {
    // Scroll to last message
    const lastMessage = document.querySelector('[data-message-index]:last-child');
    if (lastMessage) {
      lastMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }
}, [entries.length]);
```

**Benefit:**
- User always sees latest response immediately
- No manual scrolling needed
- Maintains conversation flow

---

#### Solution 2b: Reduce Header/Composer Size

**Option 1: Collapsible Header**
- Make header collapse/minimize after initial page load
- Show only essential info (user switcher, status)
- Hide navigation links, import buttons behind menu

**Option 2: Smaller Composer**
- Reduce composer height from current size to single-line input
- Expand only when user is actively typing
- Similar to messaging apps (Slack, iMessage)

**Option 3: Hide Persona Rail by Default**
- Make persona rail collapsible
- Show only active persona badge
- Click to expand full rail when needed

**Combined approach:**
```
┌─────────────────────────────────────────────────┐
│  COMPACT HEADER (just user + status)            │ ← Smaller!
├─────────────────────────────────────────────────┤
│                                                 │
│                                                 │
│   TRANSCRIPT AREA                               │ ← Much larger!
│   (More space!)                                 │
│                                                 │
│                                                 │
├─────────────────────────────────────────────────┤
│  COMPACT COMPOSER (single line)                 │ ← Smaller!
└─────────────────────────────────────────────────┘
```

---

#### Solution 2c: Full-Screen Chat Mode

**Add a "Focus Mode" toggle:**
- Hides header, persona rail, all UI chrome
- Shows only: transcript + composer
- Full screen for conversation
- Toggle button to restore full UI

**User flow:**
1. Click "Focus" button
2. UI hides everything except chat
3. Maximum space for conversation
4. Click "Exit Focus" to restore

**Similar to:**
- Slack's full-screen message view
- Gmail's focus mode
- Zen mode in text editors

---

### Implementation Priority

**Quick Wins (Do First):**
1. ✅ **Auto-scroll to latest message** (Solution 2a)
   - Small code change
   - Big UX improvement
   - File: `web/src/components/transcript-panel.tsx`

2. ✅ **Reduce composer height** (Solution 2b, Option 2)
   - Change from multi-line to single-line
   - Expand on focus
   - File: `web/src/components/chat-composer.tsx`

**Medium Effort:**
3. 🔄 **Collapsible header** (Solution 2b, Option 1)
   - Requires state management
   - Need to design compact view
   - Files: `web/src/app/page-client.tsx`

**Larger Project:**
4. 🔄 **Full-screen focus mode** (Solution 2c)
   - New feature, needs design
   - Toggle state, keyboard shortcut
   - Multiple files

---

## Recommended Implementation Order

### Phase 1: Quick UX Fixes (This Week)
1. ✅ Add auto-scroll to latest message in transcript
2. ✅ Reduce composer to single-line (expandable)

**Estimated time:** 2-3 hours
**Impact:** Immediate improvement to conversation flow

---

### Phase 2: Data Extraction MVP (Next Week)
1. ✅ Add basic keyword-based observation extraction
2. ✅ Store observations in user profile
3. ✅ Test with sample conversations

**Estimated time:** 1-2 days
**Impact:** HC starts building user profile automatically

---

### Phase 3: Advanced Extraction (Next 2 Weeks)
1. 🔄 LLM-based trait extraction
2. 🔄 UCN/RR integration for automatic inference
3. 🔄 Curiosity engine tracking

**Estimated time:** 3-5 days
**Impact:** Full "hungry data extraction" capability

---

### Phase 4: Advanced UI (Next Month)
1. 🔄 Collapsible header
2. 🔄 Full-screen focus mode
3. 🔄 Persona rail improvements

**Estimated time:** 1 week
**Impact:** Premium conversation experience

---

## Next Steps

**Immediate (Today):**
1. ✅ Test updated HC prompts (feature-aware, future-focused)
2. ✅ Export new conversation transcript
3. ✅ Review improvements

**This Week:**
1. 🔄 Implement auto-scroll for transcript
2. 🔄 Reduce composer size
3. 🔄 Start basic observation extraction

**Want me to start on any of these now?**
- Auto-scroll fix (easiest, immediate impact)
- Composer size reduction (easy, big UX improvement)
- Basic observation extraction (foundation for data ingestion)
