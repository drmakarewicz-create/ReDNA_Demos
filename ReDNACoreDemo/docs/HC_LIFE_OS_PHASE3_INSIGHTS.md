# Life OS Phase 3: Insights & Analytics

**Status**: ✅ Complete
**Date**: 2025-10-11
**Version**: 1.0.0

---

## Summary

Life OS Phase 3 adds a lightweight analytics layer that summarizes behavior and progress over time. Users can now see insights about their productivity patterns, goal momentum, focus areas, and at-risk items through both DevX dashboard cards and a compact chat rail display.

---

## Features Delivered

### 1. Analytics Engine

**File**: `ReDNACoreDemo/core/hc_life_insights.py` (636 lines)

**Core Functions**:
- `compute_insights(user_id, days=14)` - Snapshot metrics for rolling window
- `compute_trends(user_id, weeks=8)` - Time-series data for charts

**Metrics Computed**:
- **Goal Progression**: completion %, velocity, confidence drift, at-risk goals
- **Todo Patterns**: completion rate, Today's 3 success %, avg completion hour
- **Quadrant Balance**: time share across Eisenhower matrix (IU/IN/NU/NN)
- **Streaks**: current streak, longest streak, streak days
- **Focus Clusters**: top tags heatmap, category distribution
- **Nudge Effectiveness**: acceptance % and completion rate
- **At-Risk Signals**: idle goals (7+ days), projects with missing next_step

### 2. API Endpoints

**File**: `ReDNACoreDemo/core/api.py` (+115 lines)

#### GET /ui/hc/life/{user}/insights?days=14

Returns snapshot metrics for rolling window.

**Parameters**:
- `days` (query, optional): Window size in days (1-90, default: 14)

**Performance**: <2ms typical, <150ms target

**Response**:
```json
{
  "ok": true,
  "insights": {
    "goals_total": 4,
    "goals_active": 4,
    "goals_completed": 0,
    "goal_completion_rate": 0.0,
    "goal_velocity": 0.0,
    "goals_at_risk": [],
    "todos_completed": 0,
    "todos_created": 0,
    "todos_completion_rate": 0.0,
    "todays_three_success_rate": 0.0,
    "avg_completion_hour": null,
    "quadrant_share": {
      "important_urgent": 0.0,
      "important_not_urgent": 0.0,
      "not_important_urgent": 0.0,
      "neither": 0.0
    },
    "current_streak": 0,
    "longest_streak": 0,
    "streak_days": [],
    "top_tags": [],
    "focus_categories": {},
    "nudge_acceptance_rate": 0.0,
    "nudge_completion_rate": 0.0,
    "projects_at_risk": [],
    "idle_days_threshold": 7,
    "window_days": 14,
    "computed_at": "2025-10-11T03:30:15.123456Z"
  },
  "duration_ms": 2
}
```

#### GET /ui/hc/life/{user}/trends?weeks=8

Returns time-series trends with weekly bins.

**Parameters**:
- `weeks` (query, optional): Number of weeks to analyze (1-52, default: 8)

**Performance**: <1ms typical, <300ms target

**Response**:
```json
{
  "ok": true,
  "trends": {
    "weeks": 8,
    "start_date": "2025-08-25",
    "end_date": "2025-10-20",
    "data": [
      {
        "week_start": "2025-08-25",
        "week_label": "Week of Aug 25",
        "todos_completed": 0,
        "goals_progressed": 0,
        "avg_confidence": 0.0,
        "quadrant_share": {
          "important_urgent": 0.0,
          "important_not_urgent": 0.0,
          "not_important_urgent": 0.0,
          "neither": 0.0
        },
        "top_tag": null
      }
      // ... 7 more weeks
    ],
    "computed_at": "2025-10-11T03:30:15.234567Z"
  },
  "duration_ms": 1
}
```

#### POST /ui/hc/life/{user}/insights/recompute

Force recompute of insights (audited). Useful for debugging or manual refresh.

**Response**: Same as GET /insights

### 3. DevX Insights Pane

**File**: `devx/frontend/src/components/LifeInsightsPane.tsx` (423 lines)

**Insight Cards**:

1. **This Week at a Glance**
   - Today's 3 success %
   - Current streak
   - Tasks completed
   - Most productive hour

2. **Quadrant Balance**
   - 2×2 mini grid showing IU/IN/NU/NN percentages
   - Rebalance tip if >50% in any quadrant

3. **Goal Momentum**
   - Active goals count
   - Completion rate
   - Velocity (% per week)
   - At-risk goals list

4. **Focus Clusters**
   - Top 5 tags with counts
   - Category breakdown (career/health/creative/learning/personal)

5. **Nudge Impact**
   - Acceptance rate
   - Completion rate

**Interaction**:
- Click "View detailed trends →" opens modal
- Modal shows 3 time-series charts:
  - Tasks completed per week (bar chart)
  - Goals progressed per week (bar chart)
  - Average goal confidence (bar chart)

**Empty State**:
- Friendly placeholders with tips
- "💡 Tip: Use 'Today's 3' to track daily wins"
- "🎯 Tip: Set goals with confidence levels"
- "📅 Tip: Organize work by quadrant priority"

**Integration**:
Mounted in `LifeOSPane.tsx` above Projects card (line 398-405):
```typescript
{/* Insights - Phase 3 */}
<section>
  <div className="mb-3">
    <h3 className="text-lg font-semibold text-gray-900">Insights & Analytics</h3>
    <p className="text-sm text-gray-600">Track your progress and patterns over time</p>
  </div>
  <LifeInsightsPane userId={userId} embedded={embedded} />
</section>
```

### 4. Chat Right Rail - Compact Insights

**File**: `web/src/components/life-os-chat-panel.tsx` (+88 lines)

**Display** (appears after "Top Project", before "Reading"):
```
📊 Insights
┌─────────────────────────────────┐
│ 65%      3      35%             │
│ Success  Streak  Plan           │
├─────────────────────────────────┤
│ Focus: health                   │
├─────────────────────────────────┤
│ View details in DevX →          │
└─────────────────────────────────┘
```

**Data**:
- Today's 3 success %
- Current streak
- Important/not-urgent quadrant %
- Top tag (focus area)
- Link to DevX User Ops for details

**Conditional Rendering**:
Only shown if `insights.current_streak > 0 || insights.todays_three_success_rate > 0`

### 5. Narrator Weekly Summary

**File**: `hc_narrator.py` (+88 lines)

**Function**: `build_weekly_life_summary(user_id: str) -> str`

**Example Outputs**:
```
"You completed 8 tasks this week, maintained a 3-day streak, and focused on health. One career goal looks idle—want to plan a next step?"

"You completed 12 tasks this week, maintained a 5-day streak, and focused on career. 2 projects need attention—want to plan next steps?"

"No activity this week. Want to set some goals for the week ahead?"
```

**Narrator Trace**:
Logs decision `"life_os_weekly_summary"` with:
- Reasoning: tasks completed, streak, at-risk count
- Confidence: 0.9
- Impact: medium
- Metadata: todos_completed, current_streak, goals_at_risk, projects_at_risk

**Agent Hook** (optional, not implemented):
Could be called by agent daemon on Mondays via policy toggle.

### 6. Comprehensive Tests

**File**: `tests/test_hc_life_insights_phase3.py` (373 lines)

**Test Classes**:
1. `TestInsightsComputation` - Core computation functions
2. `TestInsightsAPI` - API endpoints and performance
3. `TestNarratorSummary` - Weekly summary generation
4. `TestEmptyStateBehavior` - Handles missing data gracefully
5. `TestQuadrantMath` - Validates quadrant percentages
6. `TestStreakLogic` - Validates streak calculations

**Key Tests**:
- ✅ Insights compute on sparse and dense data
- ✅ Windows respected (7d, 14d, 30d)
- ✅ Trends return correct weekly bins
- ✅ Quadrant/time share math correct
- ✅ Streak logic correct (current <= longest)
- ✅ Empty state returns safe defaults (no crashes)
- ✅ API performance <150ms (insights) and <300ms (trends)
- ✅ Narrator summary generated with trace

---

## Metrics Catalog

### Goal Metrics

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| `goals_total` | Count of all goals | 0+ | Total goals ever created |
| `goals_active` | Count with status='active' | 0+ | Goals currently being worked on |
| `goals_completed` | Count with status='completed' | 0+ | Goals achieved |
| `goal_completion_rate` | completed / total | 0.0-1.0 | % of goals achieved |
| `goal_velocity` | Avg confidence delta per week | -1.0 to +1.0 | Progress speed (simplified) |
| `goals_at_risk` | Active goals idle >7 days | Array | Goals needing attention |

### Todo Metrics

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| `todos_completed` | Count with status='done' in window | 0+ | Tasks finished |
| `todos_created` | Count created in window | 0+ | Tasks added |
| `todos_completion_rate` | completed / created | 0.0-1.0 | % of tasks finished |
| `todays_three_success_rate` | From audit events | 0.0-1.0 | Daily priorities hit rate |
| `avg_completion_hour` | Mean hour of day tasks completed | 0-23 | Peak productivity time |

### Quadrant Metrics

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| `quadrant_share.important_urgent` | % todos in IU quadrant | 0-100 | Crisis management time |
| `quadrant_share.important_not_urgent` | % todos in IN quadrant | 0-100 | Strategic planning time |
| `quadrant_share.not_important_urgent` | % todos in NU quadrant | 0-100 | Interruption time |
| `quadrant_share.neither` | % todos in NN quadrant | 0-100 | Time wasters |

**Ideal Balance**: 60% IN, 25% IU, 10% NU, 5% NN

### Streak Metrics

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| `current_streak` | Consecutive days with >=1 completion (from today backward) | 0+ | Active momentum |
| `longest_streak` | Max consecutive days in window | 0+ | Best run |
| `streak_days` | ISO dates with completions | Array | Activity pattern |

### Focus Metrics

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| `top_tags` | Most frequent tags in window | Array[(tag, count)] | Top 5 focus areas |
| `focus_categories` | Tags grouped by keyword matching | Dict[category, count] | Career/health/creative/learning/personal |

### Nudge Metrics

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| `nudge_acceptance_rate` | accepted / proposed | 0.0-1.0 | How often user acts on nudges |
| `nudge_completion_rate` | completed / accepted | 0.0-1.0 | Follow-through rate |

### At-Risk Metrics

| Metric | Formula | Range | Interpretation |
|--------|---------|-------|----------------|
| `projects_at_risk` | Projects with missing next_step or idle >14d | Array | Projects stalled |
| `idle_days_threshold` | Configurable threshold | 7 | Days before flagging as idle |

---

## Performance Benchmarks

| Endpoint | Target | Typical | Measured |
|----------|--------|---------|----------|
| GET /insights?days=14 | <150ms | <10ms | 2ms ✅ |
| GET /trends?weeks=8 | <300ms | <10ms | 1ms ✅ |
| POST /insights/recompute | <150ms | <10ms | 2ms ✅ |

**Test Conditions**:
- User: USER1
- Goals: 4 active
- Todos: 0 completed in window
- Audit events: ~20 in window

---

## Files Modified/Created

### Core Backend
1. **`core/hc_life_insights.py`** (NEW, 636 lines) - Analytics engine
2. **`core/api.py`** (+115 lines) - API endpoints
3. **`core/hc_narrator.py`** (+88 lines) - Weekly summary function

### DevX Frontend
4. **`devx/frontend/src/components/LifeInsightsPane.tsx`** (NEW, 423 lines) - Insights cards
5. **`devx/frontend/src/components/LifeOSPane.tsx`** (+8 lines) - Integration

### Chat Frontend
6. **`web/src/components/life-os-chat-panel.tsx`** (+88 lines) - Compact insights

### Tests
7. **`tests/test_hc_life_insights_phase3.py`** (NEW, 373 lines) - Comprehensive tests

### Documentation
8. **`docs/HC_LIFE_OS_PHASE3_INSIGHTS.md`** (THIS FILE) - Full documentation

---

## Verification Commands

```bash
# Test insights API
curl -s "http://localhost:8015/ui/hc/life/USER1/insights?days=14" | jq .

# Test trends API
curl -s "http://localhost:8015/ui/hc/life/USER1/trends?weeks=8" | jq .

# Test recompute
curl -s -X POST "http://localhost:8015/ui/hc/life/USER1/insights/recompute" | jq .

# Test narrator summary
python3 -c "from ReDNACoreDemo.core.hc_narrator import build_weekly_life_summary; print(build_weekly_life_summary('USER1'))"

# DevX: Open User Ops → Head Coach → Life OS
# Confirm Insights cards render above Projects

# Chat: Open right rail
# Confirm compact Insights section appears after Top Project

# Run tests
pytest ReDNACoreDemo/tests/test_hc_life_insights_phase3.py -v
```

---

## Example Screenshots

### DevX Insights Cards

```
┌─────────────────────────────────────────────┐
│ 📈 This Week at a Glance                    │
├─────────────────────────────────────────────┤
│  65%              3              8           │
│  Today's 3     Day Streak    Tasks Done     │
│  Success                                     │
│                                              │
│  Most productive around 14:00                │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ ⚖️ Quadrant Balance                          │
├─────────────────────────────────────────────┤
│  ┌─────────┬─────────┐                      │
│  │ IU 25%  │ IN 60%  │                      │
│  ├─────────┼─────────┤                      │
│  │ NU 10%  │ NN 5%   │                      │
│  └─────────┴─────────┘                      │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 🎯 Goal Momentum                             │
├─────────────────────────────────────────────┤
│  Active goals          4                     │
│  Completion rate      75%                    │
│  Velocity          +2.1%/wk                  │
│                                              │
│  ⚠️ At Risk (1)                              │
│  • Learn TypeScript (14d idle)              │
└─────────────────────────────────────────────┘
```

---

## Next Steps

### Phase 3b: Agent Learning Hooks (Optional)
- Agent daemon calls `build_weekly_life_summary()` on Mondays
- Configurable in agent policy YAML
- Sends summary as nudge or starts conversation

### Phase 4: Advanced Insights
- Goal confidence trends over time
- Productivity heatmap (hour × day)
- Tag co-occurrence network
- Predictive "at-risk" ML model
- Personalized recommendations

### Phase 5: Export & Integration
- Weekly email digests
- Markdown export for journaling
- Calendar integration (sync streaks)
- CSV export for external analysis

---

**Phase 3 Complete**: ✅ Analytics engine, API endpoints, DevX UI, chat insights, narrator summaries, and comprehensive tests delivered!
