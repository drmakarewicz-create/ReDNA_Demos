# Plan Composer Design Document

**Date:** 2025-10-04
**Status:** 🔧 In Progress
**Related Benchmark:** #10 (Improve inference quality)

---

## 🎯 Objective

Build a Plan Composer that drafts **3-step game plans** from top curiosity deltas, giving Head Coach actionable strategies for reducing uncertainty in high-priority areas.

---

## 📋 Requirements (from Roadmap)

> "Add plan composer stub to Head Coach (draft a 3-step game plan from top curiosity deltas)."

**Functional Requirements:**
1. Identify top 3-5 curiosity deltas (highest uncertainty areas)
2. Generate a 3-step action plan for each focus area
3. Prioritize steps by impact and effort
4. Provide clear, actionable guidance
5. Persist plans for tracking and iteration

**Non-Functional Requirements:**
- Fast generation (< 500ms)
- Works with/without LLM (fallback to rule-based)
- Integrates with existing Head Coach workflow
- Surfaced in UI (Head Coach tab or Dev Explorer)

---

## 🔍 Current State Analysis

### Existing Components

**1. Curiosity Engine** (`curiosity_engine.py`)
- Computes curiosity scores from RR (inverse relationship)
- Loads trait schema with curiosity weights
- Surfaces gaps but doesn't plan actions

**2. Planner** (`planner.py`)
- Converts gaps into "asks" (questions for user)
- Manages ask queue (pending/approved/snoozed)
- Tactical (per-trait) not strategic (multi-step plans)

**3. Head Coach Service** (`head_coach_service.py`)
- Has `plan_next_actions()` method
- Returns goals, quick wins, prioritized tasks
- Currently generic (not curiosity-driven)

**4. Head Coach UCN Bridge** (`head_coach_ucn_bridge.py`)
- `ActionPlan` dataclass
- Builds plans from curiosity hotspots
- Focused on delegation to lower coaches

### Gaps
❌ No **3-step game plan** generation
❌ No **strategy-level planning** (currently tactical asks only)
❌ No **plan persistence** beyond ask queue
❌ No **UI for viewing plans** in one place

---

## 🎨 Design

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Head Coach UI                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Plan Composer View                               │  │
│  │  - Current Focus (top curiosity delta)            │  │
│  │  - 3-Step Game Plan                               │  │
│  │  - Step 1: [Action] (Effort: Low, Impact: High)  │  │
│  │  - Step 2: [Action] (Effort: Med, Impact: Med)   │  │
│  │  - Step 3: [Action] (Effort: Low, Impact: Low)   │  │
│  │  - [Generate New Plan] [View History]            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
                          │ API: /hc/compose_plan
                          │
┌─────────────────────────┴───────────────────────────────┐
│            Plan Composer Module                          │
│  (ReDNACoreDemo/core/plan_composer.py)                  │
│                                                          │
│  compose_plan(user_id) → GamePlan                       │
│    1. Get top 3 curiosity deltas                        │
│    2. For each delta, generate 3-step plan             │
│    3. Prioritize by impact/effort                       │
│    4. Return structured plan                            │
│                                                          │
│  get_plan_history(user_id, limit=10) → List[GamePlan]  │
│    - Load past plans from storage                       │
│                                                          │
│  persist_plan(user_id, plan: GamePlan) → None          │
│    - Save plan to user's plans directory                │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Uses
                          ▼
┌─────────────────────────────────────────────────────────┐
│       Existing Components                                │
│  - curiosity_engine (get top deltas)                    │
│  - planner (ask queue integration)                      │
│  - head_coach_service (goal context)                    │
└─────────────────────────────────────────────────────────┘
```

### Data Model

**GamePlan** (dataclass):
```python
@dataclass
class Step:
    number: int
    action: str
    rationale: str
    effort: str  # "low", "medium", "high"
    impact: str  # "low", "medium", "high"
    estimated_minutes: int
    coach_delegation: Optional[str] = None  # Which coach to delegate to

@dataclass
class GamePlan:
    id: str  # hash of focus + timestamp
    user_id: str
    created_at: str
    focus_area: str  # Top curiosity delta (e.g., "PaDNA.LooksDNA.Style")
    curiosity_score: float
    goal: str  # What we're trying to achieve
    steps: List[Step]  # 3 steps
    status: str  # "active", "completed", "abandoned"
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Storage:**
- Path: `data/users/{user_id}/plans/plan_{timestamp}.json`
- Index: `data/users/{user_id}/plans/index.json` (list of plan IDs with summaries)

---

## 🧠 Plan Generation Strategy

### Step 1: Identify Focus Area

**Input:** User ID
**Process:**
1. Call `curiosity_engine.compute_curiosity(user_id)`
2. Get top 3 traits with highest curiosity scores
3. Pick #1 as primary focus
4. Filter sensitive traits (defer if sensitivity flag set)

**Output:** Focus trait + curiosity score

### Step 2: Generate 3-Step Plan

**Rule-Based Approach** (v1 - no LLM required):

**Template Structure:**
1. **Step 1: Quick Data Gather** (Low Effort, Medium Impact)
   - Ask 1-2 direct questions via lower coach
   - Effort: Low (2-5 min)
   - Impact: Medium (some evidence → UCN up, RR down, curiosity down)

2. **Step 2: Observation Task** (Medium Effort, High Impact)
   - Guide user to observe/reflect on trait
   - Effort: Medium (10-15 min)
   - Impact: High (rich evidence → significant curiosity drop)

3. **Step 3: Behavioral Micro-Action** (Low Effort, Low Impact)
   - Suggest small action to surface trait signal
   - Effort: Low (2-5 min)
   - Impact: Low (indirect evidence, long-term value)

**Example (for "PaDNA.LooksDNA.Style.PreferredColors"):**
- **Goal:** Reduce uncertainty around color preferences
- **Step 1:** Ask Photo Coach to show 5 color palettes, ask "Which resonates?"
  - Effort: Low (2 min)
  - Impact: Medium (direct signal)
  - Coach: Photo Coach
- **Step 2:** Guide user to review recent outfit photos, note recurring colors
  - Effort: Medium (10 min)
  - Impact: High (behavioral evidence)
  - Coach: Photo Coach
- **Step 3:** Suggest user take one photo highlighting favorite color today
  - Effort: Low (3 min)
  - Impact: Low (reinforces preference)
  - Coach: Photo Coach

**LLM-Enhanced Approach** (v2 - optional):
- Use LLM to generate custom steps based on trait context
- Prompt template: "Given user's curiosity gap in [trait], suggest 3 progressive steps..."
- Fallback to rule-based if LLM unavailable

---

## 📐 Implementation Plan

### File Structure

```
ReDNACoreDemo/core/
├── plan_composer.py         ← NEW (core logic)
├── api_plan_composer.py     ← NEW (FastAPI endpoints)
└── ...

data/users/{user_id}/
└── plans/
    ├── index.json           ← Plan summaries
    ├── plan_20251004_120530.json
    ├── plan_20251004_140215.json
    └── ...

ExplorerDev/tabs/
└── head_coach_tab.py        ← Update with Plan Composer UI

prompts/head_coach/
└── plan_composer_system.md  ← NEW (LLM prompt for custom plans)
```

### Core Module (`plan_composer.py`)

**Functions:**
1. `compose_plan(user_id: str, focus_override: Optional[str] = None) -> GamePlan`
   - Main entry point
   - Gets top curiosity delta (or uses override)
   - Generates 3-step plan
   - Persists to storage
   - Returns GamePlan

2. `_generate_steps_rule_based(trait: str, curiosity_score: float) -> List[Step]`
   - Rule-based step generation
   - Uses trait family to customize approach
   - Returns 3 steps

3. `_generate_steps_llm(trait: str, curiosity_score: float, user_context: Dict) -> List[Step]`
   - LLM-based step generation (optional)
   - Falls back to rule-based if LLM fails

4. `get_plan_history(user_id: str, limit: int = 10) -> List[GamePlan]`
   - Loads past plans from storage
   - Returns most recent first

5. `persist_plan(user_id: str, plan: GamePlan) -> None`
   - Saves plan to user's plans directory
   - Updates index

6. `update_plan_status(user_id: str, plan_id: str, status: str) -> None`
   - Mark plan as completed/abandoned

---

## 🎨 UI Design

### Location: Head Coach Tab in ExplorerDev

**Section: "Game Plan Composer"**

```
┌─────────────────────────────────────────────────────────────┐
│  🎯 Current Focus: PaDNA.LooksDNA.Style.PreferredColors     │
│  Curiosity Score: 0.82 (High Uncertainty)                   │
│                                                              │
│  Goal: Reduce uncertainty around color preferences          │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Step 1: Quick Data Gather                             │ │
│  │ ────────────────────────────────────────────────────  │ │
│  │ Action: Ask Photo Coach to show 5 color palettes     │ │
│  │ Rationale: Direct signal from user preference         │ │
│  │ Effort: Low (2 min)   Impact: Medium                  │ │
│  │ Coach: Photo Coach                                     │ │
│  │ [✓ Mark Complete] [⏭ Skip]                            │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Step 2: Observation Task                              │ │
│  │ ────────────────────────────────────────────────────  │ │
│  │ Action: Review recent outfit photos, note colors      │ │
│  │ Rationale: Behavioral evidence from past choices      │ │
│  │ Effort: Medium (10 min)   Impact: High                │ │
│  │ Coach: Photo Coach                                     │ │
│  │ [Mark Complete] [Skip]                                │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Step 3: Behavioral Micro-Action                       │ │
│  │ ────────────────────────────────────────────────────  │ │
│  │ Action: Take one photo highlighting favorite color    │ │
│  │ Rationale: Reinforces preference, creates evidence    │ │
│  │ Effort: Low (3 min)   Impact: Low                     │ │
│  │ Coach: Photo Coach                                     │ │
│  │ [Mark Complete] [Skip]                                │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  [🔄 Generate New Plan] [📋 View Plan History]             │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Current focus highlighted
- 3 steps shown as cards
- Effort/Impact badges
- Coach delegation visible
- Mark complete / skip actions
- Generate new plan button
- View history button

---

## 🚀 Success Criteria

- ✅ Plans generate in < 500ms
- ✅ 3 steps per plan (always)
- ✅ Steps are actionable (user can execute)
- ✅ Plans persist to storage
- ✅ UI displays plans clearly
- ✅ Integration with existing Head Coach workflow
- ✅ Falls back gracefully if LLM unavailable
- ✅ Curiosity-driven (always targets highest uncertainty)

---

## 📊 Impact

**Before:**
- Head Coach has generic quick wins
- No strategic multi-step planning
- Curiosity deltas visible but not actionable

**After:**
- Head Coach generates 3-step game plans
- Plans target highest curiosity areas
- Clear effort/impact guidance
- Persistent plan history
- UI for tracking progress

---

## 🔧 Implementation Phases

### Phase 1: Core Module (MVP)
- ✅ Create `plan_composer.py`
- ✅ Implement rule-based plan generation
- ✅ Add storage persistence
- ✅ Create GamePlan/Step dataclasses

### Phase 2: API Integration
- ✅ Create FastAPI endpoint (`/hc/compose_plan`)
- ✅ Add plan history endpoint (`/hc/plan_history`)
- ✅ Add update status endpoint (`/hc/plan_status`)

### Phase 3: UI
- ✅ Add Plan Composer section to Head Coach tab
- ✅ Display current plan with steps
- ✅ Add mark complete / skip actions
- ✅ Add plan history view

### Phase 4: LLM Enhancement (Future)
- Create prompt template
- Implement LLM-based generation
- Add fallback logic

---

## 📚 Related Documentation

- **Curiosity Engine:** `ReDNACoreDemo/core/curiosity_engine.py`
- **Planner:** `ReDNACoreDemo/core/planner.py`
- **Head Coach Service:** `ReDNACoreDemo/core/head_coach_service.py`
- **Roadmap:** `docs/Core_Benchmarks_Roadmap.md` (Benchmark #10)

---

**Next:** Implement Phase 1 (Core Module)
