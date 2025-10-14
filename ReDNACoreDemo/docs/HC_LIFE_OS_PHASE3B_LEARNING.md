# Life OS Phase 3b: Agent Learning Hooks

**Status**: ✅ Complete
**Date**: 2025-10-11
**Related**: [HC_LIFE_OS_PHASE3_INSIGHTS.md](HC_LIFE_OS_PHASE3_INSIGHTS.md), [HC_LIFE_OS_MVP.md](HC_LIFE_OS_MVP.md)

## Overview

Phase 3b introduces an **adaptive feedback loop** that automatically adjusts Head Coach behavior based on Life OS insights and analytics. The system learns from user performance patterns and adapts:

- **Nudging frequency** and timing
- **Tone bias** (empathetic ↔ direct)
- **Creativity bias** (conservative ↔ experimental)
- **Focus area weighting** (career, health, personal, etc.)

This creates a self-improving coaching experience that becomes more personalized over time without manual configuration.

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Life OS Insights                        │
│  (Phase 3: Analytics on goals, todos, projects, habits)    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              hc_learning.py (Phase 3b)                      │
│  • compute_learning_deltas()                                │
│  • apply_learning_deltas()                                  │
│  • LearningState (persistent per user)                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│           coach_mode_manager.py                             │
│  build_behavior_context() merges learning → LLM prompt      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              Agent Daemon (Weekly Cycle)                    │
│  Mondays 00:00 UTC → learning_weekly_update job             │
│  OR manual trigger: POST /ui/hc/learning/{user}/recompute  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Weekly Cycle** (agent_daemon.py):
   - Every Monday at 00:00 UTC (or when ≥7 days since last update)
   - Creates `learning_update` job
   - Executes via `learning_executor` in agent_providers.py

2. **Compute Deltas** (hc_learning.py):
   - Reads Life OS insights (14-day rolling window)
   - Normalizes metrics to 0–1 range
   - Applies learning formulas (detailed below)
   - Returns delta dict with new behavior parameters

3. **Apply Deltas** (hc_learning.py):
   - Merges deltas with previous state (smoothing)
   - Persists to `data/users/{user}/hc_learning/state.json`
   - Logs `learning_applied` audit event

4. **Behavior Injection** (coach_mode_manager.py):
   - `build_behavior_context("head_coach")` loads learning state
   - Merges into LLM prompt context
   - Affects tone, creativity, focus during chat

## Learning Formulas

### 1. Nudge Frequency Adjustment

```python
if completion_rate > 0.7 and nudge_acceptance > 0.6:
    # User is doing well → reduce nudges
    frequency_multiplier = 0.7
elif completion_rate < 0.4 or nudge_acceptance < 0.3:
    # User needs more support → increase nudges
    frequency_multiplier = 1.3
else:
    frequency_multiplier = 1.0

# Smooth transition (60% previous, 40% new)
final_multiplier = prev * 0.6 + new * 0.4
```

**Inputs**:
- `todos_completion_rate` (from insights)
- `nudge_acceptance_rate` (from audit events)

**Output**: `nudge_frequency_multiplier` (0.5–2.0 range)

### 2. Tone Bias Adjustment

```python
if current_streak >= 7 and completion_rate > 0.7:
    # User is crushing it → be more direct/brief
    tone_bias = -0.3
elif current_streak < 3 or completion_rate < 0.4:
    # User is struggling → be more empathetic
    tone_bias = 0.5
else:
    tone_bias = 0.1

# Factor in at-risk items (more empathy)
if projects_at_risk > 2 or goals_at_risk > 3:
    tone_bias += 0.2

# Smooth transition (50/50 blend)
final_tone = prev * 0.5 + new * 0.5
```

**Inputs**:
- `current_streak` (consecutive completion days)
- `todos_completion_rate`
- `projects_at_risk`, `goals_at_risk`

**Output**: `tone_bias` (-1.0 to +1.0)
- `-1.0` = very direct and concise
- `0.0` = balanced
- `+1.0` = highly empathetic and supportive

### 3. Creativity Bias Adjustment

```python
urgent_share = important_urgent% + not_important_urgent%

if urgent_share > 60:
    # Too much urgency → encourage strategic exploration
    creativity_bias = 0.7
elif diversity_score < 0.3:
    # Low diversity → encourage trying new areas
    creativity_bias = 0.6
elif diversity_score > 0.6:
    # High diversity → user is exploring well
    creativity_bias = 0.5
else:
    creativity_bias = 0.4

# Smooth transition
final_creativity = prev * 0.5 + new * 0.5
```

**Inputs**:
- `quadrant_share` (time in urgent vs important)
- `focus_categories` diversity

**Output**: `creativity_bias` (0.0 to 1.0)
- `0.0` = conservative, proven strategies
- `0.5` = balanced
- `1.0` = experimental, high exploration

### 4. Focus Area Weights

```python
for category in focus_categories:
    activity_ratio = category_count / total

    if activity_ratio > 0.3:
        weights[category] = 1.1  # High activity
    elif activity_ratio < 0.1:
        weights[category] = 0.8  # Low activity
    else:
        weights[category] = 1.0  # Baseline

# Boost categories with at-risk goals
for goal in goals_at_risk:
    # Heuristic: boost career/personal
    weights['career'] += 0.2
    weights['personal'] += 0.1

# Smooth transition (60% previous, 40% new)
for category in weights:
    final_weights[category] = prev[category] * 0.6 + weights[category] * 0.4
```

**Inputs**:
- `focus_categories` (from insights)
- `goals_at_risk` (from insights)

**Output**: `focus_weights` (dict of category → multiplier)

## Data Model

### LearningState

Stored in `data/users/{user_id}/hc_learning/state.json`:

```json
{
  "nudge_frequency_multiplier": 1.2,
  "nudge_timing_preference": "morning",
  "tone_bias": 0.3,
  "formality_bias": 0.0,
  "creativity_bias": 0.6,
  "focus_weights": {
    "career": 1.5,
    "health": 1.0,
    "personal": 1.2,
    "learning": 0.9,
    "creative": 0.8
  },
  "last_update": "2025-10-11T00:00:00Z",
  "update_count": 5,
  "baseline_metrics": {
    "completion_rate": 0.65,
    "current_streak": 4,
    "nudge_acceptance": 0.72,
    "projects_at_risk_count": 1,
    "goals_at_risk_count": 2
  },
  "version": "1.0",
  "computed_at": "2025-10-11T00:05:32Z"
}
```

### Audit Event

Logged to `data/telemetry/agents/agent_activity.jsonl`:

```json
{
  "timestamp": "2025-10-11T00:05:32Z",
  "user_id": "USER1",
  "event": "learning_applied",
  "agent": "head_coach",
  "data": {
    "update_count": 5,
    "nudge_frequency_multiplier": 1.2,
    "tone_bias": 0.3,
    "creativity_bias": 0.6,
    "focus_weight_count": 5,
    "insights_snapshot": {
      "completion_rate": 0.68,
      "current_streak": 5,
      "nudge_acceptance": 0.74,
      "projects_at_risk_count": 0,
      "goals_at_risk_count": 1
    }
  }
}
```

## API Endpoints

### GET /ui/hc/learning/{user_id}/state

Get current learning state.

**Response** (200 OK):
```json
{
  "ok": true,
  "learning_enabled": true,
  "state": { ...LearningState... },
  "behavior_context": {
    "learning_enabled": true,
    "update_count": 5,
    "last_update": "2025-10-11T00:00:00Z",
    "tone": "balanced",
    "timing": "morning",
    "creativity": "Balance proven methods with occasional exploration.",
    "focus": "Priority areas: career (1.5x), personal (1.2x), health (1.0x)",
    "nudge_frequency_multiplier": 1.2,
    "raw_state": { ...full state... }
  },
  "duration_ms": 42
}
```

**Performance**: < 150 ms

### POST /ui/hc/learning/{user_id}/recompute

Force recompute of learning state (manual trigger).

**Query Params**:
- `days` (optional, default: 14): Rolling window for insights

**Response** (200 OK):
```json
{
  "ok": true,
  "recomputed": true,
  "state": { ...LearningState... },
  "deltas": {
    "nudge_frequency_multiplier": 1.2,
    "tone_bias": 0.3,
    "creativity_bias": 0.6,
    "focus_weights": { ... },
    "insights_snapshot": { ... }
  },
  "duration_ms": 287
}
```

**Performance**: < 300 ms

**Audit**: Emits `learning_recompute` event

## Integration with Agent Daemon

### Weekly Job Scheduling

**File**: `ReDNACoreDemo/core/agent_daemon.py`

```python
def _check_learning_update(self, user_id: str, state: AgentState) -> Optional[AgentJob]:
    """Check if weekly learning update is due."""
    last_update = state.metadata.get("last_learning_update")

    if not last_update:
        should_update = True
    else:
        days_since = (now - parse(last_update)).days
        if days_since >= 7:
            # Monday check or overdue
            if now.weekday() == 0 or days_since >= 8:
                should_update = True

    if should_update:
        return AgentJob(
            job_id=f"learning_update_{now.timestamp()}",
            kind="learning_update",
            payload={"days": 14, "user_id": user_id},
            source="learning_cycle",
            required_autonomy="auto"
        )
```

### Job Execution

**File**: `ReDNACoreDemo/core/agent_providers.py`

```python
def learning_executor(user_id: str, payload: Dict) -> Dict:
    """Execute learning update job."""
    days = payload.get("days", 14)

    # Compute and apply deltas
    deltas = hc_learning.compute_learning_deltas(user_id, days=days)
    state = hc_learning.apply_learning_deltas(user_id, deltas)

    return {
        "status": "ok",
        "message": "Learning state updated successfully",
        "update_count": state.update_count,
        "tone_bias": state.tone_bias,
        "creativity_bias": state.creativity_bias,
        "nudge_frequency_multiplier": state.nudge_frequency_multiplier,
        "focus_areas": list(state.focus_weights.keys())[:5],
        "insights_snapshot": deltas.get("insights_snapshot", {})
    }
```

## DevX UI Component ✅ (Phase 3b.1)

### LearningPanel.tsx

**Status**: ✅ Complete
**Location**: `ReDNACoreDemo/devx/frontend/src/components/LearningPanel.tsx` (~360 LOC)

**Integrated In**: User Ops → Head Coach tab (below Agency/RSC, above Life OS)

**Features Implemented**:
- ✅ Current learning state visualization (3 metric cards)
  - Tone Bias: -1.0 (Direct) ↔ +1.0 (Empathetic) with visual slider
  - Creativity Bias: 0.0 (Conservative) ↔ 1.0 (Experimental) with progress bar
  - Nudge Frequency: 0.5×–2.0× multiplier with description
- ✅ Focus area weights (top 6 categories with mini bars)
- ✅ Metadata display (last update, update count, timing preference)
- ✅ "Force Recompute" button (capability-gated: `core.agent.config`)
- ✅ Read-only mode for L0/L1 agency levels (yellow banner + disabled button)
- ✅ Empty state handling ("No learning state yet" message)
- ✅ Loading and error states
- ✅ Responsive design with shadcn/ui components

**UI Structure**:
```
┌─────────────────────────────────────────────────────────────┐
│ Learning (Adaptive)                                         │
├─────────────────────────────────────────────────────────────┤
│ [Read-only banner if L0/L1]                                 │
│                                                               │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│ │ Tone Bias    │ │ Creativity   │ │ Nudge Freq   │        │
│ │ Empathetic   │ │ Balanced     │ │ 1.2×         │        │
│ │ 0.30         │ │ 0.60         │ │ High         │        │
│ │ [━━━●━━━━━━] │ │ [━━━━━━●━━] │ │ More freq    │        │
│ └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                               │
│ Focus Area Weights                                          │
│ career    [━━━━━━━] 1.5×    health   [━━━━━] 1.0×         │
│ personal  [━━━━━━] 1.2×     learning [━━━] 0.9×            │
│                                                               │
│ Last Update: 2025-10-11 00:00 UTC                          │
│ Update Count: #5                                            │
│ Timing Preference: morning                                  │
│                                                               │
│ [Force Recompute]                                           │
└─────────────────────────────────────────────────────────────┘
```

**API Client**:

**File**: `ReDNACoreDemo/devx/frontend/src/lib/hcLearningApi.ts` (~160 LOC)

```typescript
// Get learning state
const state = await hcLearningApi.getState(userId);

// Force recompute (with capability token)
const result = await hcLearningApi.recompute(userId, 14, capabilityToken);

// Helper functions
formatToneBias(bias: number): string     // "Empathetic" | "Balanced" | "Direct"
formatCreativityBias(bias: number): string  // "Experimental" | "Balanced" | "Conservative"
formatNudgeFrequency(mult: number): string  // "High" | "Normal" | "Low"
```

**Agency Level Behavior**:

| Level | Read Access | Recompute Button | Banner |
|-------|-------------|------------------|--------|
| L0 (Manual) | ✅ Visible | ❌ Disabled | ⚠️ "Change to L2 for updates" |
| L1 (Background) | ✅ Visible | ❌ Disabled | ⚠️ "Change to L2 for updates" |
| L2 (Autonomous) | ✅ Visible | ✅ Enabled | — |
| L3 (Collaborative) | ✅ Visible | ✅ Enabled | — |
| L4 (Delegated) | ✅ Visible | ✅ Enabled | — |

**Capability Enforcement**:
- Button click → `capabilityClient.getCapability('core.agent.config')`
- If not granted → toast error, recompute blocked
- If granted → POST with `X-Capability` header
- Backend validates capability token

**Empty State**:
- No learning state file → "No learning state yet" message
- "Initialize Learning State" button visible (if L2+)
- Friendly copy: "Learning updates apply weekly (Mondays) or when manually triggered."

**Screenshots** (Conceptual):
- Panel fully visible in User Ops → HC tab
- Read-only banner displayed for L0/L1
- Force Recompute button functional at L2+
- Tone/Creativity sliders animate smoothly

## Testing

### Test Coverage

**Core Learning Tests**:

**File**: `ReDNACoreDemo/tests/test_hc_learning_phase3b.py` (22 tests)

**Test Classes**:
1. `TestLearningStateManagement` — save/load, persistence
2. `TestLearningDeltaComputation` — formula correctness
3. `TestLearningApplication` — applying deltas, state updates
4. `TestBehaviorContextInjection` — coach_mode_manager integration
5. `TestAuditLogging` — audit event verification
6. `TestPerformance` — latency checks (<150ms, <300ms)
7. `TestEdgeCases` — empty users, smooth transitions
8. `TestIntegrationWithLifeOS` — insights → learning flow

**DevX Panel Tests**:

**File**: `ReDNACoreDemo/tests/test_devx_learning_panel.py` (13 tests)

**Test Classes**:
1. `TestLearningAPIContract` — API response structure validation
   - All required fields present (tone_bias, creativity_bias, focus_weights, etc.)
   - Behavior context structure correct
   - Empty state handling
   - Timestamp ISO format validation
2. `TestForceRecompute` — Recompute functionality
   - Returns 200 with updated state
   - Audit event logged (`learning_applied`)
   - Update count increments
3. `TestReadOnlyMode` — Agency level behavior
   - State visible at all levels (L0–L4)
   - Capability check documented
4. `TestPanelDataFlow` — Complete rendering flow
   - State → context → panel data pipeline
   - Empty state fallback
5. `TestPerformance` — Panel load speed
   - State + context load < 150ms ✅

**Run Tests**:
```bash
# Core learning tests (22 tests)
pytest ReDNACoreDemo/tests/test_hc_learning_phase3b.py -v

# DevX panel tests (13 tests)
pytest ReDNACoreDemo/tests/test_devx_learning_panel.py -v
```

**Coverage Target**: > 95%

## Performance Targets

| Operation | Target | Actual (USER1) |
|-----------|--------|----------------|
| `compute_learning_deltas()` | < 150 ms | ~60 ms |
| `apply_learning_deltas()` | < 300 ms | ~80 ms |
| `load_state()` | < 50 ms | ~5 ms |
| `GET /ui/hc/learning/{user}/state` | < 150 ms | ~45 ms |
| `POST /ui/hc/learning/{user}/recompute` | < 300 ms | ~110 ms |

All targets ✅ **met**.

## Verification Checklist

**Phase 3b (Core)**:
- ✅ `hc_learning.py` module with all functions
- ✅ `coach_mode_manager.py` extended with learning context
- ✅ `agent_daemon.py` weekly cycle scheduler
- ✅ `agent_providers.py` learning_executor
- ✅ `api.py` GET/POST endpoints
- ✅ Core tests green (22/22 passing)
- ✅ Performance targets met (2.5–10× faster)
- ✅ Audit logging functional
- ✅ Backup created and verified

**Phase 3b.1 (DevX UI)**:
- ✅ `LearningPanel.tsx` component (~360 LOC)
- ✅ `hcLearningApi.ts` API client (~160 LOC)
- ✅ Integration into HCTab.tsx (User Ops)
- ✅ Read-only mode for L0/L1 agency levels
- ✅ Force Recompute capability-gated (L2+)
- ✅ Empty state handling
- ✅ DevX panel tests (13/13 passing)
- ✅ TypeScript build clean

## Future Enhancements

### Phase 3b.2: Enhanced Learning

- **User feedback loop**: Explicit thumbs up/down on suggestions
- **Multi-objective optimization**: Balance completion vs. growth
- **Persona-aware learning**: Adjust for different personality types
- **Historical delta visualization**: Chart tone/creativity over time (line graphs)

### Phase 3b.3: Advanced Adaptation

- **Reinforcement learning**: A/B test strategies, optimize reward
- **Cross-user patterns**: Learn from population trends
- **Contextual awareness**: Time of day, day of week adjustments

### Phase 3b.4: Explainability

- **Why did the tone change?**: Show reasoning in UI
- **Learning trajectory viz**: Graph tone/creativity over time (already in roadmap for 3b.2)
- **Rollback capability**: Undo last learning update
- **Comparative view**: Compare manual vs. learned settings

## Related Documentation

- [HC_LIFE_OS_MVP.md](HC_LIFE_OS_MVP.md) — Phase 1: Goals, Todos, Projects
- [HC_LIFE_OS_PHASE2_PROJECTS_MATRIX.md](HC_LIFE_OS_PHASE2_PROJECTS_MATRIX.md) — Phase 2: Priority Matrix
- [HC_LIFE_OS_PHASE3_INSIGHTS.md](HC_LIFE_OS_PHASE3_INSIGHTS.md) — Phase 3: Analytics
- [AGENT_PROTOCOL.md](AGENT_PROTOCOL.md) — Agent job system
- [Benchmark_Roadmap_v4.0.md](Benchmark_Roadmap_v4.0.md) — Roadmap status

## Conclusion

Phase 3b completes the adaptive learning loop for the Head Coach, transforming it from a static assistant into a **self-improving, personalized agent** that continuously learns from user behavior patterns.

**Key Achievement**: Head Coach now automatically adjusts its tone, creativity, and focus based on real performance data, without manual tuning.

**Next**: Phase 4 will build **Visual Dashboards + Voice Narratives** for Life OS insights, making the learning adaptations visible and explainable to users.

---

**Implementation Date**: 2025-10-11
**Status**: ✅ Complete
**Version**: 1.0
