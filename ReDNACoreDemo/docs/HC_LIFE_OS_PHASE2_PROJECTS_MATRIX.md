# Head Coach Life OS Phase 2: Projects + Priority Matrix

**Status**: ✅ Implemented
**Version**: 2.0
**Date**: 2025-10-10

## Overview

Phase 2 extends the Life OS system with **Projects** and a **Priority Matrix**, enabling users to organize goals and todos into higher-level strategic groupings and visualize priorities using the Eisenhower Matrix framework.

## Key Features

### 1. Projects System

Projects group related goals and todos together, providing:

- **Title & Description**: Clear project naming
- **Quadrant Assignment**: Automatic priority categorization
- **Status Tracking**: active | paused | completed
- **Progress Metrics**: Confidence scores and calculated progress
- **Next Steps**: Clear action items for each project
- **Risk Assessment**: Risk notes for each project

### 2. Priority Matrix (Eisenhower Matrix)

A 2×2 grid organizing todos by:

- **Important & Urgent** (Do First) - Orange
- **Important & Not Urgent** (Schedule) - Green
- **Not Important & Urgent** (Delegate) - Yellow
- **Neither** (Eliminate) - Gray

### 3. Agent Integration

The Life OS daily agent provider now:
- Checks for Important & Urgent tasks first
- Suggests them when "Today's 3" is empty
- Falls back to goal-based suggestions if matrix is empty

## Architecture

### Backend Components

#### Core Module: `hc_life_projects.py`

```python
@dataclass
class Project:
    id: str
    title: str
    goal_id: Optional[str]
    quadrant: str  # 'important_urgent' | 'important_not_urgent' | 'not_important_urgent' | 'neither'
    status: str    # 'active' | 'paused' | 'completed'
    next_step: Optional[str]
    risk: Optional[str]
    confidence: float
    created_at: Optional[str]
    updated_at: Optional[str]
```

**Key Functions**:
- `create_project()` - Create a new project
- `list_projects()` - List all projects (filterable by status)
- `get_project()` - Get specific project by ID
- `update_project()` - Update project fields
- `delete_project()` - Delete a project
- `get_priority_matrix()` - Get quadrant → todo mappings
- `update_todo_quadrant()` - Move todo between quadrants
- `get_top_projects()` - Get prioritized active projects
- `get_important_urgent_task()` - Get one task from important/urgent quadrant
- `calculate_project_progress()` - Calculate project completion percentage

#### Storage

Projects are stored in JSONL format:
```
data/users/{user_id}/hc_life/projects.jsonl
```

Each line is a JSON object representing one project.

#### Audit Trail

All project operations are logged to:
```
data/audit/life_projects_{YYYYMM}.jsonl
```

Events logged:
- `project_created`
- `project_updated`
- `project_deleted`
- `todo_quadrant_updated`

### API Endpoints

#### Projects CRUD

```http
GET    /ui/hc/life/{user_id}/projects?status=active
POST   /ui/hc/life/{user_id}/projects
PATCH  /ui/hc/life/{user_id}/projects/{project_id}
DELETE /ui/hc/life/{user_id}/projects/{project_id}
```

#### Matrix Operations

```http
GET   /ui/hc/life/{user_id}/matrix
PATCH /ui/hc/life/{user_id}/matrix
```

#### Top Projects

```http
GET /ui/hc/life/{user_id}/projects/top?limit=3
```

### Frontend Components

#### DevX: LifeProjectsCard.tsx

Located in: `ReDNACoreDemo/devx/frontend/src/components/LifeProjectsCard.tsx`

Features:
- Displays top 3 active projects
- Color-coded borders by quadrant
- Progress bars with confidence scores
- Next step display
- Risk indicators
- "Matrix" button → opens full matrix modal
- Drag-and-drop todo reassignment between quadrants

#### Main Chat: life-os-chat-panel.tsx

Located in: `web/src/components/life-os-chat-panel.tsx`

Features:
- Shows top 1 project (most important)
- Next step display
- "Matrix →" link to DevX
- **Persistent collapse state** using localStorage

## Usage Examples

### Creating a Project

```python
from ReDNACoreDemo.core.hc_life_projects import create_project

project = create_project(
    user_id="USER1",
    title="Launch Product V2",
    goal_id="goal-123",
    quadrant="important_urgent",
    next_step="Finalize requirements doc",
    risk="Timeline is tight",
    confidence=0.65
)
```

### Getting Priority Matrix

```python
from ReDNACoreDemo.core.hc_life_projects import get_priority_matrix

matrix = get_priority_matrix("USER1")
# Returns:
# {
#   "important_urgent": ["todo-1", "todo-5"],
#   "important_not_urgent": ["todo-2", "todo-8"],
#   "not_important_urgent": ["todo-3"],
#   "neither": ["todo-4", "todo-6", "todo-7"]
# }
```

### Moving Todo Between Quadrants

```python
from ReDNACoreDemo.core.hc_life_projects import update_todo_quadrant

update_todo_quadrant(
    user_id="USER1",
    todo_id="todo-123",
    quadrant="important_urgent"
)
```

### Agent Provider Integration

The `life_os_daily_provider` now checks for Important & Urgent tasks:

```python
# When "Today's 3" is empty, the provider will:
# 1. Check for Important & Urgent tasks from the matrix
# 2. Suggest one if available
# 3. Fall back to goal-based suggestions if matrix is empty

# Example job payload:
{
  "job_id": "life-daily-USER1",
  "kind": "life_daily_three",
  "payload": {
    "suggestions": [
      {
        "text": "Finalize requirements doc",
        "todo_id": "todo-123",
        "priority": 1.0,
        "reason": "Important & Urgent from Priority Matrix"
      }
    ]
  }
}
```

## Testing

Comprehensive test coverage in: `ReDNACoreDemo/tests/test_hc_life_projects_phase2.py`

**Test Coverage**:
- ✅ Project CRUD operations
- ✅ Matrix generation and quadrant logic
- ✅ Quadrant reassignment
- ✅ Top projects prioritization
- ✅ Important/urgent task selection
- ✅ Progress calculation (goal-linked and todo-based)
- ✅ Audit event recording
- ✅ Agent provider integration

**Run tests**:
```bash
pytest ReDNACoreDemo/tests/test_hc_life_projects_phase2.py -v
```

## UI/UX Design

### Quadrant Color Coding

| Quadrant | Color | Meaning |
|----------|-------|---------|
| Important & Urgent | Orange | Do First - Critical tasks |
| Important & Not Urgent | Green | Schedule - Strategic work |
| Not Important & Urgent | Yellow | Delegate - Interruptions |
| Neither | Gray | Eliminate - Low value |

### DevX Projects Card

```
┌─────────────────────────────────────┐
│ 🎯 Projects            [Matrix] → │
├─────────────────────────────────────┤
│ ┃ Launch Product V2         65%    │
│ ┃ ████████████░░░░░░░░             │
│ ┃ Next: Finalize requirements doc  │
│ ┃ ⚠ Timeline is tight              │
├─────────────────────────────────────┤
│ ┃ Build Marketing Campaign   80%   │
│ ┃ ████████████████░░░░             │
│ ┃ Next: Draft social posts        │
├─────────────────────────────────────┤
│ ┃ Onboard New Team Member    45%   │
│ ┃ █████████░░░░░░░░░░░             │
│ ┃ Next: Schedule orientation      │
└─────────────────────────────────────┘
```

### Chat Panel Top Project

```
┌─────────────────────────────────────┐
│ Top Project              Matrix →  │
├─────────────────────────────────────┤
│ ┃ Launch Product V2               │
│ ┃ Next: Finalize requirements doc │
│ ┃ ████████████░░░░░░░    65%      │
└─────────────────────────────────────┘
```

### Priority Matrix Modal (DevX)

```
┌──────────────────────────────────────────────┐
│              Priority Matrix            [×]  │
├──────────────────────────────────────────────┤
│                                              │
│  Important & Urgent    Important & Not       │
│  (Orange)              Urgent (Green)        │
│  ┌───────────────┐    ┌───────────────┐    │
│  │ • Finalize    │    │ • Write blog  │    │
│  │   requirements│    │   post        │    │
│  │ • Fix bug #123│    │ • Research AI │    │
│  └───────────────┘    └───────────────┘    │
│                                              │
│  Not Important &      Neither (Gray)         │
│  Urgent (Yellow)                             │
│  ┌───────────────┐    ┌───────────────┐    │
│  │ • Team meeting│    │ • Read random │    │
│  │ • Answer email│    │   article     │    │
│  └───────────────┘    └───────────────┘    │
│                                              │
│  Drag and drop todos between quadrants       │
└──────────────────────────────────────────────┘
```

## Collapse State Persistence

The chat Life OS panel now remembers its collapsed/expanded state per user:

**Implementation**:
```typescript
// On load
const [collapsed, setCollapsed] = useState(() => {
  const key = `life_os_chat_collapsed:${userId}`;
  return localStorage.getItem(key) === 'true';
});

// On toggle
const handleToggleCollapse = () => {
  const newCollapsed = !collapsed;
  setCollapsed(newCollapsed);
  localStorage.setItem(`life_os_chat_collapsed:${userId}`, String(newCollapsed));
};
```

**localStorage keys**:
- Format: `life_os_chat_collapsed:{user_id}`
- Value: `"true"` or `"false"`

**SSR Safety**: Checks for `window` existence before accessing localStorage.

## Integration Points

### With Goals
- Projects can be linked to goals via `goal_id`
- Project progress can be calculated from goal confidence
- Goals' first_step feeds into project next_step suggestions

### With Todos
- Todos can have a `quadrant` in their metadata
- Todos can be linked to projects via `project_id` in metadata
- Project progress can be calculated from linked todos' completion rate

### With Agent Daemon
- Important & Urgent tasks are prioritized in "Today's 3" suggestions
- Agent provider checks matrix before falling back to goals
- Provides clear reasoning: "Important & Urgent from Priority Matrix"

## Migration from Phase 1

Phase 2 is **fully backward compatible** with Phase 1:

- All existing todos, goals, and Life OS data remain unchanged
- Matrix automatically categorizes existing todos based on priority and due_date
- No data migration required
- Projects system is opt-in (users start with 0 projects)

## Future Enhancements (Phase 3)

Planned for Phase 3:
- **Life OS Insights**: Analyze patterns in project completion
- **Narrator Integration**: Record project milestones in user's story
- **Curiosity Hooks**: Suggest learning based on project needs
- **Batch Operations**: Move multiple todos at once
- **Project Templates**: Pre-configured project structures
- **Time Estimates**: Track estimated vs. actual time per project

## Verification Checklist

✅ Backend
- [x] Projects CRUD functions implemented
- [x] Matrix generation and quadrant logic
- [x] API endpoints created and tested
- [x] Audit logging active
- [x] Agent provider updated

✅ Frontend
- [x] DevX LifeProjectsCard component
- [x] Matrix modal with drag-drop
- [x] Chat panel project display
- [x] Collapse state persistence

✅ Testing
- [x] Comprehensive unit tests
- [x] Agent provider integration test
- [x] Audit event verification

✅ Documentation
- [x] This document
- [x] Updated HC_LIFE_OS_MVP.md
- [x] Updated Benchmark_Roadmap_v4.0.md

## Quick Start

### 1. Create a Project (API)

```bash
curl -X POST http://localhost:8015/ui/hc/life/USER1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Launch New Product",
    "quadrant": "important_urgent",
    "next_step": "Define MVP scope",
    "confidence": 0.6
  }'
```

### 2. View Projects (DevX)

Navigate to: `http://localhost:8100/user-ops/USER1/hc`

Scroll to the "Projects" card beneath Goals.

### 3. Open Priority Matrix

Click the "Matrix" button in the Projects card to see the full 2×2 grid.

### 4. Move Todos

Drag todos between quadrants to reorganize by priority.

### 5. Check Chat Panel

In Coach Chat UI, the Life OS panel now shows the top project and persists its collapse state.

## Performance Notes

- Projects are stored in JSONL (one-file-per-user)
- Matrix generation scans all active todos (O(n))
- Typical performance: <10ms for 100 todos
- Collapse state is localStorage-only (no network calls)

## Security & Privacy

- Projects and matrix data follow existing Life OS access patterns
- No new capability tokens required
- Audit trail captures all project modifications
- localStorage is client-side only (per-device preference)

## Summary

Phase 2 successfully adds:
- ✅ **Projects** for organizing goals and todos
- ✅ **Priority Matrix** for visual priority management
- ✅ **Agent integration** for important/urgent task suggestions
- ✅ **Collapse state persistence** for better UX
- ✅ **Comprehensive testing** and documentation

**Total LOC**: ~1,500
- Backend: ~500 LOC
- Frontend: ~500 LOC
- Tests: ~300 LOC
- Docs: ~200 LOC

---

**Next Phase**: [Phase 3 - Life OS Insights & Patterns](./HC_LIFE_OS_PHASE3_INSIGHTS.md) (Planned)
