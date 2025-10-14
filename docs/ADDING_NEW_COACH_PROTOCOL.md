# Protocol: Adding a New Coach

This document outlines all the steps required when adding a new coach to the ReDNA system. Following this protocol ensures the Head Coach knows about the new coach, the backend can handle mode switches, and the frontend UI properly displays and switches between coaches.

## Architecture Overview: The Multi-Layer Problem

Coach switching involves **5 distinct layers** that must all be updated:

1. **Backend Coach Registry** (`coach_registry.yaml`) - Defines coach capabilities
2. **Backend Mode Management** (`coach_mode_manager.py`) - Validates mode switches
3. **Backend UI Roster** (`ui_readonly.py`) - Provides fallback personas for frontend
4. **Frontend Persona System** (`api.ts`) - ⭐ **CRITICAL LAYER** - Canonical roster validation
5. **Frontend UI Handlers** (`page-client.tsx`) - Handles UI persona normalization and rendering
6. **Backend Prompts** (`api.py`, `hc_llm_agent.py`) - Informs LLM about coaches

**Missing any layer will cause silent failures** where coaches appear but don't work when clicked.

### 🚨 CRITICAL: api.ts is the Gatekeeper

**The most common failure mode** is forgetting to update `web/src/lib/api.ts`. Even if ALL other layers are correct, missing the api.ts updates will cause:
- URL changes to `?persona=your_coach`
- But UI falls back to Head Coach
- No errors in console
- Complete silent failure

**Always update api.ts FIRST** when adding a new coach to catch this immediately.

---

## Critical Discovery: Persona Key Normalization

The frontend normalizes certain coach IDs for backwards compatibility:
- `photo_coach` → `photo`
- `padna_coach` → `padna`
- `relationship` → `relationship_coach`

**Both the original and normalized forms** must be supported in VALID_MODES.

---

## Step-by-Step Protocol

### ⚡ RECOMMENDED ORDER

To catch frontend integration issues immediately, follow this order:

1. **Frontend First**: Update `api.ts` CANONICAL_ORDER, CANONICAL_DEFAULTS, PERSONA_ALIASES
2. **Backend Mode**: Update `coach_mode_manager.py` VALID_MODES, MODE_DISPLAY_NAMES, MODE_CAPABILITIES
3. **Backend Roster**: Update `ui_readonly.py` icons and fallback personas
4. **Registry**: Update `coach_registry.yaml` (if not done already)
5. **Prompts**: Update `api.py` and `hc_llm_agent.py` (optional, for Head Coach knowledge)
6. **Test**: Verify coach switching works in UI

This order ensures you'll catch the most common failure (missing api.ts) early.

---

### Step 1: Add Coach to Registry

**File**: `ReDNACoreDemo/core/coach_registry.yaml`

Add the new coach definition under the `coaches:` section:

```yaml
coaches:
  new_coach_id:
    display_name: "New Coach Name"
    id: "new_coach_id"
    description: "What this coach does"
    primary_namespaces:
      - RelevantDNA.Namespace
    capabilities:
      - RelevantDNA.*
    delegation_context: "brief description"
    natural_domains:
      - "domain 1"
      - "domain 2"
    suitable_for_types:
      - trait
      - container
      - missing
    autonomy_level: "medium"  # or "low", "medium-high", "high"
```

Update the `availability` section at the bottom:
```yaml
availability:
  new_coach_id: true
```

---

### Step 2: Update Backend Coach Mode Manager

**File**: `ReDNACoreDemo/core/coach_mode_manager.py`

#### Add to VALID_MODES (around line 27)

```python
VALID_MODES = {
    "head_coach",
    "photo",
    "photo_coach",
    "relationship",
    "relationship_coach",
    "career_coach",
    "personality_test_coach",
    "padna",
    "padna_coach",
    "new_coach_id"  # ADD THIS LINE
}
```

**If your coach has legacy aliases** (like `photo` vs `photo_coach`), add **both versions** to VALID_MODES.

#### Add to MODE_DISPLAY_NAMES (around line 30)

```python
MODE_DISPLAY_NAMES = {
    "head_coach": "Head Coach",
    "photo": "Photo Coach",
    "photo_coach": "Photo Coach",
    "relationship": "Relationship Coach",
    "relationship_coach": "Relationship Coach",
    "career_coach": "Career Coach",
    "personality_test_coach": "Personality Test Coach",
    "padna": "PaDNA Coach",
    "padna_coach": "PaDNA Coach",
    "new_coach_id": "New Coach Name",  # ADD THIS LINE
}
```

#### Add to MODE_CAPABILITIES (around line 43)

```python
MODE_CAPABILITIES = {
    # ... existing coaches ...
    "new_coach_id": {
        "namespaces": ["RelevantDNA", "OtherDNA"],
        "description": "Brief description of what this coach does",
        "emoji": "🎯",
    },
}
```

**CRITICAL**: Without these updates, clicking the coach in the Coach Catalog will fail with "Failed to switch modes" error.

---

### Step 3: Update Backend UI Roster (Fallback Personas)

**File**: `ReDNACoreDemo/core/ui_readonly.py`

#### Add icon to _DEFAULT_ICONS (around line 17)

```python
_DEFAULT_ICONS: Dict[str, str] = {
    # ... existing icons ...
    "new_coach_id": "🎯",  # ADD THIS LINE
}
```

#### Add to _FALLBACK_PERSONAS (around line 33)

```python
_FALLBACK_PERSONAS = [
    {"key": "head_coach", "label": "Head Coach (Orchestrator)", "icon": _DEFAULT_ICONS["head_coach"]},
    {"key": "relationship_coach", "label": "Relationship Coach", "icon": _DEFAULT_ICONS["relationship_coach"]},
    {"key": "career_coach", "label": "Career Coach", "icon": _DEFAULT_ICONS["career_coach"]},
    {"key": "personality_test_coach", "label": "Personality Test Coach", "icon": _DEFAULT_ICONS["personality_test_coach"]},
    {"key": "padna_coach", "label": "PaDNA Coach", "icon": _DEFAULT_ICONS["padna_coach"]},
    {"key": "photo_coach", "label": "Photo Coach", "icon": _DEFAULT_ICONS["photo_coach"]},
    {"key": "new_coach_id", "label": "New Coach Name", "icon": _DEFAULT_ICONS["new_coach_id"]},  # ADD THIS LINE
]
```

**Why this matters**: The frontend loads the persona roster and will reset `activePersona` to the first enabled coach if the clicked coach isn't in this list. Without this entry, coach clicks will silently fail and revert to Head Coach.

---

### Step 4: Update Frontend Persona System

**File**: `web/src/lib/api.ts`

#### Add to CANONICAL_ORDER (around line 2463)

```typescript
const CANONICAL_ORDER = [
  'head_coach',
  'relationship_coach',
  'career_coach',
  'personality_test_coach',
  'padna',
  'photo',
  'new_coach_id'  // ADD THIS LINE
] as const;
```

#### Add to CANONICAL_DEFAULTS (around line 2466)

```typescript
const CANONICAL_DEFAULTS: Record<CanonicalKey, PersonaRosterEntry> = {
  // ... existing coaches ...
  new_coach_id: {
    key: 'new_coach_id',
    label: 'New Coach Name',
    icon: '🎯',
    enabled: true,
    accent_color: null
  }  // ADD THIS ENTRY
};
```

#### Add aliases to PERSONA_ALIASES (around line 2511)

```typescript
const PERSONA_ALIASES: Record<string, CanonicalKey> = {
  // ... existing aliases ...
  new_coach_id: 'new_coach_id',
  'new coach': 'new_coach_id',
  // If your coach has a legacy alias:
  new_coach_legacy: 'new_coach_id'  // Maps legacy ID to canonical ID
};
```

**Why this matters**: The `normalizePersonaRoster` function filters out any personas not in `PERSONA_ALIASES`. Without this, the coach won't appear in the frontend persona roster even if the backend returns it.

---

### Step 5: Update Frontend Persona Normalization ⚠️ CRITICAL - ALWAYS REQUIRED

**File**: `web/src/app/page-client.tsx`

**THIS STEP IS MANDATORY** - Missing this causes silent failures where the coach appears but isn't clickable.

#### 5a. Update normalizePersonaKey return type (around line 2986)

```typescript
function normalizePersonaKey(key: string): 'head_coach' | 'photo' | 'padna' | 'relationship_coach' | 'career_coach' | 'personality_test_coach' | 'chatdna_coach' | 'beliefdna_coach' | 'new_coach_id' {
  // Add 'new_coach_id' to the union type above ↑
```

#### 5b. Add switch case (around line 3023)

```typescript
  switch (normalized) {
    // ... existing cases ...
    case 'new_coach_id':
    case 'new coach':
    case 'newcoach':  // Add all variations
      return 'new_coach_id';
    default:
      return 'head_coach';
  }
```

#### 5c. Add to shouldShowCoachToolsPane (around line 2828)

```typescript
  case 'career_coach':
  case 'relationship_coach':
  case 'personality_test_coach':
  case 'chatdna_coach':
  case 'beliefdna_coach':
  case 'new_coach_id':  // Add this line - most coaches should return false
    return false;
```

#### 5d. Add to renderRightPane (around line 2906)

```typescript
  case 'beliefdna_coach':
    return (
      <>
        <PanelBoundary resetKeys={[personaKey, context.activeUser]}>
          <BeliefDNACoachPanel userId={context.activeUser} />
        </PanelBoundary>
      </>
    );
  case 'new_coach_id':  // Add this case
    // New coach: no specialized tools yet, just support panels
    return null;
  default:
    return null;
```

**Why this is ALWAYS required**: TypeScript validates persona keys at compile time. Without updating the union type, the frontend will reject the new coach and fall back to head_coach.

---

### Step 6: Update Head Coach System Prompts

**File**: `ReDNACoreDemo/core/api.py`

Update in **THREE locations**:

#### Location 1: SYSTEM_PROMPT (around line 684-697)

```python
SYSTEM_PROMPT = (
    # ... earlier content ...
    "AVAILABLE COACHES: You work with specialized coaches who help in different areas:\n"
    "• Relationship Coach 💞 - dating, relationships, emotions, psychology\n"
    "• Photo Coach 📸 - physical appearance, style, visual presence\n"
    "• Personality Test Coach 🧠 - personality profiling, motivations, values\n"
    "• Career Coach 💼 - career planning, skills, professional development\n"
    "• New Coach 🎯 - brief description of what they do\n"  # ADD THIS LINE
    # ... rest of prompt ...
)
```

#### Location 2: PERSONA_PROMPTS["head_coach"] (around line 714-722)

```python
PERSONA_PROMPTS = {
    "head_coach": (
        # ... earlier content ...
        "AVAILABLE COACHES:\n"
        "• Relationship Coach 💞 - relationships, emotions, psychology\n"
        "• Photo Coach 📸 - appearance, style, visual presence\n"
        "• Personality Test Coach 🧠 - personality, motivations, values\n"
        "• Career Coach 💼 - career, skills, professional development\n"
        "• New Coach 🎯 - brief description\n"  # ADD THIS LINE
        # ... rest of prompt ...
    ),
}
```

#### Location 3: PERSONA_RUBRICS["head_coach"] (around line 754-761)

```python
PERSONA_RUBRICS = {
    "head_coach": (
        # ... earlier content ...
        "COACH MATCHING:\n"
        "• Relationships, emotions, psychology → Relationship Coach\n"
        "• Appearance, style, physical traits → Photo Coach\n"
        "• Personality, motivations, values → Personality Test Coach\n"
        "• Career, skills, work, professional growth → Career Coach\n"
        "• Relevant keywords → New Coach\n"  # ADD THIS LINE
        # ... rest of rubric ...
    ),
}
```

---

### Step 7: Update Head Coach LLM Agent (OpenAI/Anthropic)

**File**: `ReDNACoreDemo/core/hc_llm_agent.py`

Update the `_build_system_message` function around line 230-255:

```python
system_msg += "\n\n=== AVAILABLE SPECIALIST COACHES ===\n"
system_msg += "You work alongside specialized coaches who can help explore specific domains:\n\n"
# ... existing coaches ...
system_msg += "🎯 New Coach - Brief description\n"
system_msg += "   • Key capability 1\n"
system_msg += "   • Key capability 2\n\n"
```

---

### Step 8: Restart Services

After making all changes:

1. **Core API** will auto-reload if running with `--reload` flag
2. **Next.js frontend** will hot-reload automatically (may need browser refresh)
3. Verify changes by checking server logs for reload messages

---

### Step 9: Run Smoke Tests

Use the comprehensive smoke test script:

```bash
cd ReDNACoreDemo
./scripts/test_all_coach_modes.sh
```

This tests:
- All coach mode switches via API
- Mode persistence after switching
- Legacy alias support

---

### Step 10: Manual UI Testing

Test these scenarios in the browser:

1. **Coach Catalog Display**
   - Open Coach Catalog (📚 button)
   - Verify new coach appears with correct icon and description

2. **Coach Switching**
   - Click the new coach in the catalog
   - Verify the UI updates to show the new coach as active
   - Verify the backend mode is actually switched (check user data)

3. **Coach Knowledge**
   - Ask Head Coach: "What coaches are available?"
   - Should list ALL coaches including the new one
   - Ask: "Tell me about [New Coach]"
   - Should provide accurate information

4. **Mode Persistence**
   - Switch to new coach
   - Refresh the page
   - Verify the new coach is still active

---

## Why This Protocol is Complex

The architecture has evolved with multiple legacy systems and normalization layers:

### Persona Key Normalization Chain

```
Coach Catalog ID        Frontend Normalization     Backend Mode
─────────────────       ──────────────────────     ────────────
photo_coach      →      photo                →     photo_coach ✓
padna_coach      →      padna                →     padna_coach ✓
career_coach     →      career_coach         →     career_coach ✓
```

### The 5-Layer Validation Stack

1. **Coach Registry** - Does coach definition exist?
2. **VALID_MODES** - Is mode ID allowed?
3. **Persona Roster** - Is coach in frontend persona list?
4. **PERSONA_ALIASES** - Can frontend normalize the ID?
5. **normalizePersonaKey** - Does UI state handle this ID?

**Any layer failing = silent failure** where the coach appears but doesn't work.

---

## Common Failure Modes

### Symptom: Coach appears in catalog but clicking switches to Head Coach

**THIS IS THE #1 FAILURE MODE** 🚨

**Root causes (in order of likelihood)**:
1. ⭐ **Coach not in `page-client.tsx` `normalizePersonaKey` return type** - #1 MOST COMMON - TypeScript silently rejects
2. ⭐ **Coach not in `api.ts` `CANONICAL_ORDER`** - Second most common, hardest to debug
3. ⭐ **Coach not in `api.ts` `CANONICAL_DEFAULTS`** - Required for roster validation
4. ⭐ **Coach not in `api.ts` `PERSONA_ALIASES`** - Required for ID normalization
5. Coach not in `ui_readonly.py` `_FALLBACK_PERSONAS`
6. Coach not in `page-client.tsx` switch statement or helper functions

**Debugging this issue**:
- Check browser URL: if it shows `?persona=your_coach` but UI shows Head Coach → api.ts is missing
- Check browser console: no errors = api.ts silently rejected the persona
- Check `/ui/personas` endpoint: if coach appears there but still fails → definitely api.ts

### Symptom: "Failed to switch modes" error

**Root causes**:
- Coach not in `coach_mode_manager.py` `VALID_MODES`
- Legacy alias missing (e.g., added `photo_coach` but not `photo`)

### Symptom: Head Coach doesn't know about the coach

**Root causes**:
- Missing from one of the 3 prompt locations in `api.py`
- Missing from `hc_llm_agent.py` system message builder

---

## Complete Checklist

When adding a new coach, verify:

### Backend (Python)
- [ ] Added to `coach_registry.yaml` with full definition
- [ ] Added to `coach_mode_manager.py` VALID_MODES
- [ ] Added to `coach_mode_manager.py` MODE_DISPLAY_NAMES
- [ ] Added to `coach_mode_manager.py` MODE_CAPABILITIES
- [ ] Added to `ui_readonly.py` _DEFAULT_ICONS
- [ ] Added to `ui_readonly.py` _FALLBACK_PERSONAS
- [ ] Added to `api.py` SYSTEM_PROMPT (3 locations!)
- [ ] Added to `hc_llm_agent.py` system message builder

### Frontend (TypeScript)
- [ ] Added to `api.ts` CANONICAL_ORDER
- [ ] Added to `api.ts` CANONICAL_DEFAULTS
- [ ] Added to `api.ts` PERSONA_ALIASES (with all aliases!)
- [ ] ⚠️ **CRITICAL** - Added to `page-client.tsx` normalizePersonaKey return type union
- [ ] Added to `page-client.tsx` normalizePersonaKey switch statement
- [ ] Added to `page-client.tsx` shouldShowCoachToolsPane
- [ ] Added to `page-client.tsx` renderRightPane

### Testing
- [ ] Ran `./scripts/test_all_coach_modes.sh` - all tests pass
- [ ] Coach appears in Coach Catalog with correct icon
- [ ] Clicking coach switches mode (doesn't revert to Head Coach)
- [ ] Backend mode persists after switch
- [ ] Head Coach knows about the coach (ask "what coaches are available?")
- [ ] Head Coach describes coach correctly when asked
- [ ] No "Failed to switch modes" errors
- [ ] Mode persists after page refresh

---

## Future Improvements

1. **Centralize coach definitions** - Single source of truth for all coach metadata
2. **Auto-generate prompts** - Build LLM prompts from coach registry
3. **Unify ID normalization** - Remove legacy aliases and use consistent IDs everywhere
4. **Add type safety** - Use TypeScript to enforce coach ID validity across layers
5. **Create integration tests** - Automated end-to-end tests for coach switching

---

## Quick Reference: File Locations

| Layer | File | Lines | What to Update |
|-------|------|-------|----------------|
| Registry | `core/coach_registry.yaml` | Bottom | Add coach definition |
| Mode Validation | `core/coach_mode_manager.py` | 27, 30, 43 | VALID_MODES, DISPLAY_NAMES, CAPABILITIES |
| UI Roster | `core/ui_readonly.py` | 17, 33 | Icons, fallback personas |
| Prompts | `core/api.py` | 684, 714, 754 | 3 prompt locations |
| LLM Agent | `core/hc_llm_agent.py` | 230 | System message builder |
| Frontend Roster | `web/src/lib/api.ts` | 2463, 2466, 2511 | Order, defaults, aliases |
| **Frontend Normalize** ⚠️ | **`web/src/app/page-client.tsx`** | **2986, 3023, 2828, 2906** | **Type union, switch, helpers** |

---

## Emergency Debugging

If a coach isn't working, check these layers in order:

1. **Backend accepts the mode**: `curl -X POST http://localhost:8000/users/TEST/coach-mode -d '{"target_mode":"your_coach"}'`
2. **Frontend sees the coach**: Check `/ui/personas` API response
3. **Catalog shows the coach**: Check `/ui/coach-catalog` API response
4. **Click triggers switch**: Check browser console for errors
5. **Mode persists**: Check `/users/TEST` API response for coach_mode field

---

## Lessons Learned: ChatDNA Coach (October 2025)

**Issue**: ChatDNA Coach was fully implemented in registry, backend mode manager, and UI roster, but clicking it in the catalog would change the URL to `?persona=chatdna_coach` while the UI remained on Head Coach.

**Root Cause**: Missing `api.ts` updates. The frontend canonical persona system (`CANONICAL_ORDER`, `CANONICAL_DEFAULTS`, `PERSONA_ALIASES`) acts as a gatekeeper - even if the backend returns the coach in `/ui/personas`, the frontend will reject it if it's not in these three constants.

**The Fix**: Added chatdna_coach to all three TypeScript constants in [web/src/lib/api.ts](../web/src/lib/api.ts):
- Line 2463: `CANONICAL_ORDER`
- Lines 2495-2501: `CANONICAL_DEFAULTS`
- Lines 2529-2531: `PERSONA_ALIASES`

**Key Insight**: This was the **exact same issue** that occurred when adding career_coach and personality_test_coach. The solution is to **always update api.ts first** when adding a new coach.

**Protocol Change**: Reordered steps to put frontend api.ts updates **before** backend updates, catching this failure mode immediately instead of after multiple debugging rounds.

---

*Last updated: 2025-10-07 - Added ChatDNA Coach lessons learned and reordered protocol*
