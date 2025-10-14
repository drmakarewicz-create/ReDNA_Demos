# Head Coach Life OS MVP

**Status:** ✅ Complete
**Version:** 1.0
**Last Updated:** 2025-10-10

## Overview

The Head Coach Life OS is a personal productivity system integrated into the ReDNA platform. It provides users with a unified interface for managing goals, tasks, quick capture, reading lists, and daily inspiration—all accessible via the Head Coach tab in the User Ops panel.

## Architecture

### Data Model

All data is stored under `data/users/<user_id>/hc_life/`:

```
hc_life/
├── north_star.json      # Core identity, purpose, happiness notes
├── goals.jsonl          # Quarter/long-term goals
├── todos.jsonl          # Tasks and reminders
├── links.jsonl          # Saved articles and resources
└── inspiration.jsonl    # Quotes and advice
```

### Storage Format

**North Star** (`north_star.json`):
```json
{
  "identity": "Software engineer passionate about AI",
  "purpose": "Build products that help people learn faster",
  "happiness_notes": "Balance, autonomy, growth"
}
```

**Goals** (`goals.jsonl`):
```json
{"id": "g_abc123", "text": "Get promoted to senior", "owner": "me", "why": "Career growth", "first_step": "Talk to manager", "confidence": 0.7, "target_date": "2025-12-31", "status": "active", "created_at": "...", "updated_at": "..."}
```

**Todos** (`todos.jsonl`):
```json
{"id": "td_xyz789", "text": "Review PRs", "when": "today", "priority": 0.8, "status": "open", "goal_id": "g_abc123", "tags": ["work"], "created_at": "...", "updated_at": "..."}
```

**Links** (`links.jsonl`):
```json
{"id": "lnk_def456", "title": "Great article on leadership", "url": "https://example.com", "source": "newsletter", "est_time_minutes": 15, "created_at": "..."}
```

**Inspiration** (`inspiration.jsonl`):
```json
{"id": "insp_ghi789", "text": "The only way to do great work is to love what you do", "source": "Steve Jobs", "why_matters": "Reminds me to stay passionate", "created_at": "..."}
```

## API Endpoints

All endpoints are under `/ui/hc/life/<user_id>/`:

### GET `/summary`

Returns aggregated Life OS summary for the right pane:

```json
{
  "ok": true,
  "summary": {
    "north_star": {
      "identity": "...",
      "purpose": "...",
      "happiness_notes": "..."
    },
    "today_three": [
      {"id": "td_1", "text": "Task 1", "priority": 0.9, ...},
      ...
    ],
    "inbox": [
      {"id": "td_5", "text": "Backlog task", ...},
      ...
    ],
    "goals": [
      {"id": "g_1", "text": "Goal 1", "confidence": 0.8, ...},
      ...
    ],
    "links": [
      {"id": "lnk_1", "title": "Article", "url": "...", ...},
      ...
    ],
    "quote": {
      "id": "insp_1",
      "text": "Quote text",
      "source": "Author",
      "why_matters": "..."
    }
  }
}
```

### POST `/capture`

Quick capture a new todo:

**Request:**
```json
{
  "text": "Call mentor",
  "when": "today",
  "tags": ["career"]
}
```

**Response:**
```json
{
  "ok": true,
  "todo": {
    "id": "td_abc123",
    "text": "Call mentor",
    "when": "today",
    ...
  }
}
```

**Audit Event:** `life_capture`

### CRUD Endpoints

#### Goals

- `GET /goals?status=active` - List goals
- `POST /goals` - Create goal
- `PATCH /goals/{id}` - Update goal (status, confidence, first_step, etc.)

**Audit Events:** `life_goal_create`, `life_goal_update`

#### Todos

- `GET /todos?scope=today&status=open` - List todos
- `POST /todos` - Create todo
- `PATCH /todos/{id}` - Update todo (status, when, priority, etc.)

**Audit Events:** `life_todo_create`, `life_todo_update`

#### Links

- `GET /links?limit=10` - List saved links
- `POST /links` - Save a link

**Audit Event:** `life_link_save`

#### Inspiration

- `GET /inspiration?limit=1` - Get inspiration/quotes

## UI Components

### LifeOSPane Component

Located at: `ReDNACoreDemo/devx/frontend/src/components/LifeOSPane.tsx`

**Sections:**

1. **North Star** - Core identity, purpose, and happiness notes
2. **Today's 3** - Top 3 must-do tasks with checkboxes
3. **Quick Capture** - Inline input to add tasks instantly
4. **Inbox** - Unscheduled backlog tasks
5. **Goals** - Quarter goals with confidence bars and first steps
6. **Links** - Saved articles and resources
7. **Inspiration** - Daily quote with context

**Integration:**

Added to Head Coach tab in User Ops:
- File: `ReDNACoreDemo/devx/frontend/src/routes/user-ops/tabs/HCTab.tsx`
- Displays as a collapsible section below Agent Control Center and RSC Collaboration

## Agent Daily Nudge

### Provider: `life_os_daily_provider`

Located in: `ReDNACoreDemo/core/agent_providers.py`

**Logic:**

1. Check if "Today's 3" is empty
2. Check cooldown (once per 20 hours)
3. Derive suggestions from active goals' `first_step`
4. Enqueue job with `kind: life_daily_three`

**Job Payload:**
```json
{
  "job_id": "life-daily-user123",
  "kind": "life_daily_three",
  "payload": {
    "suggestions": [
      {
        "text": "Write technical spec",
        "goal_id": "g_abc",
        "priority": 0.9,
        "reason": "Next step for: Ship new feature"
      }
    ],
    "reason": "today_three_empty"
  },
  "required_autonomy": "semi",
  "metadata": {
    "proposed_at": "2025-10-10T08:00:00Z"
  }
}
```

**Autonomy Levels:**

- **L1 (Propose):** Logs proposed Today's 3 in agent activity
- **L2+ (Auto):** Can auto-populate tasks (with user review)

## Security & Consent

- **Capability required:** `core.agent.config` for all write operations
- **Audit logging:** All create/update events logged to `data/telemetry/agents/agent_activity.jsonl`
- **No external data:** All data is user-generated; no external feeds by default
- **Future extensions:** Finance/media cards will require explicit consent

## Testing

**Test File:** `ReDNACoreDemo/tests/test_hc_life_mvp.py`

**Coverage:**

✅ Quick capture creates todo
✅ Summary returns all sections
✅ PATCH updates todo status
✅ PATCH updates goal fields
✅ Audit events logged
✅ L2 daily nudge enqueues when empty
✅ Daily nudge respects cooldown
✅ Inbox filters backlog todos
✅ Goals sorted by recency

**Run tests:**
```bash
python -m pytest ReDNACoreDemo/tests/test_hc_life_mvp.py -v
```

## Usage Example

### 1. Quick Capture

```bash
curl -X POST "http://localhost:8015/ui/hc/life/USER1/capture" \
  -H "Content-Type: application/json" \
  -H "X-Capability: <devx token>" \
  -d '{"text":"Call mentor","when":"today"}'
```

### 2. Get Summary

```bash
curl "http://localhost:8015/ui/hc/life/USER1/summary" | jq .
```

### 3. Update Todo Status

```bash
curl -X PATCH "http://localhost:8015/ui/hc/life/USER1/todos/td_abc123" \
  -H "Content-Type: application/json" \
  -H "X-Capability: <devx token>" \
  -d '{"status":"done"}'
```

### 4. Agent Daily Nudge

```bash
python -m ReDNACoreDemo.core.agent_daemon --user USER1 --once
tail -n 10 data/telemetry/agents/agent_activity.jsonl
```

## Next Steps (Beyond MVP)

### Planned Enhancements

1. **Projects & Priority Matrix**
   - Multi-step efforts linked to goals
   - Important/Urgent matrix with drag-to-reorder

2. **This Week View**
   - 3 commitments + 1 stretch item
   - Focus hours target

3. **Appointments & Reminders**
   - Calendar integration (today + next 48h)
   - Snooze/defer/done actions

4. **Curated Content**
   - External feeds (with consent)
   - Finance/media watchlists

5. **Smart Nudges**
   - "30 mins free: move Project X forward?"
   - "Meeting in 2h: review Goal Y one-pager?"
   - Recurring reminder suggestions

## Files Modified/Created

**Backend:**
- ✅ `ReDNACoreDemo/core/hc_life.py` - Data model and storage
- ✅ `ReDNACoreDemo/core/api.py` - API endpoints (lines 12554-12896)
- ✅ `ReDNACoreDemo/core/agent_providers.py` - Daily nudge provider

**Frontend:**
- ✅ `ReDNACoreDemo/devx/frontend/src/components/LifeOSPane.tsx` - UI component
- ✅ `ReDNACoreDemo/devx/frontend/src/routes/user-ops/tabs/HCTab.tsx` - Integration

**Tests:**
- ✅ `ReDNACoreDemo/tests/test_hc_life_mvp.py` - Test suite

**Documentation:**
- ✅ `ReDNACoreDemo/docs/HC_LIFE_OS_MVP.md` - This file

## Performance

- **GET /summary:** < 150ms (aggregates 5 JSONL files)
- **POST /capture:** < 50ms (single JSONL append)
- **PATCH updates:** < 100ms (read, modify, write JSONL)

## Acceptance Criteria

✅ Head Coach tab shows Life OS cards
✅ Quick Capture, Goals add/edit, Today's 3 check-off functional
✅ GET summary < 150ms
✅ Write endpoints audit `life_*` events
✅ L2 agents propose daily "Today's 3" when empty
✅ L1 only logs proposed set
✅ No external feeds required
✅ Capability helper used for writes
✅ Tests/docs/state updated
✅ No regressions to User Ops, Triggers, RSC, or Agency Configurator

---

## Phase 2: Projects + Priority Matrix

**Status:** ✅ Complete
**Documentation:** See [HC_LIFE_OS_PHASE2_PROJECTS_MATRIX.md](./HC_LIFE_OS_PHASE2_PROJECTS_MATRIX.md)

Phase 2 extends the Life OS with:
- **Projects** system for organizing goals and todos
- **Priority Matrix** (Eisenhower Matrix) for visual priority management
- **Agent integration** for important/urgent task suggestions
- **Collapse state persistence** for chat panel UX

Key additions:
- `hc_life_projects.py` - Projects and matrix backend
- API endpoints: `/ui/hc/life/{user}/projects`, `/ui/hc/life/{user}/matrix`
- `LifeProjectsCard.tsx` - DevX Projects component with drag-drop matrix
- Updated `life-os-chat-panel.tsx` - Top project display + persistent collapse
- `test_hc_life_projects_phase2.py` - Comprehensive test coverage

---

**Status:** Phases 1 & 2 Complete ✅
**Next:** Phase 3 - Life OS Insights & Patterns (planned)
