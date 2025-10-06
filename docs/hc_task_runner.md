# Head Coach Task Runner

**Version**: 2.0 (Sprint 1a)
**Status**: Production-ready

---

## Overview

The HC Task Runner is a lightweight, file-backed task queue system that enables autonomous execution of actions for users. Tasks move through a simple lifecycle: `queued → running → done/failed/snoozed`.

---

## Task Schema

```json
{
  "id": "uuid",
  "title": "Human-readable title",
  "action": "add_evidence | import_photo | re_render | morning_snapshot | end_of_day_recap",
  "args": {...},
  "state": "queued | running | done | failed | snoozed",
  "created_ts": "ISO8601 UTC",
  "updated_ts": "ISO8601 UTC",
  "eta_mins": 2,
  "provenance": {
    "source_coach": "Photo Coach",
    "source": "reminder",
    "reminder_id": "...",
    "reason": "Scheduled reminder at ..."
  },
  "error": "Optional error message if failed"
}
```

---

## Task States

| State | Description | Next States |
|-------|-------------|-------------|
| **queued** | Ready to execute | running, snoozed |
| **running** | Currently executing | done, failed |
| **done** | Successfully completed | (terminal) |
| **failed** | Execution failed | queued (retry) |
| **snoozed** | Temporarily paused | queued |

---

## Task Actions

### Core Actions

| Action | Description | Args |
|--------|-------------|------|
| `add_evidence` | Request evidence for a trait | `{trait: "PaDNA.SkinDNA.Freckles.Density"}` |
| `import_photo` | Trigger photo import | `{photo_path: "path/to/photo.jpg"}` |
| `re_render` | Re-render portrait | `{}` |
| `morning_snapshot` | Generate morning snapshot | `{}` |
| `end_of_day_recap` | Generate end-of-day recap | `{}` |

### Custom Actions

You can define custom actions by adding handlers in `hc_task_runner.py::_execute_task()`.

---

## File Storage

Tasks are stored as JSON files:

```
data/users/{user_id}/hc/tasks/
├── {task_id_1}.json
├── {task_id_2}.json
└── {task_id_3}.json
```

Each task is a separate file, enabling simple file-based queueing without a database.

---

## API Endpoints

### POST /hc/tasks/queue

Enqueue a new task.

**Request**:
```json
{
  "user_id": "alice",
  "title": "Reduce uncertainty for Freckles",
  "action": "add_evidence",
  "args": {"trait": "PaDNA.SkinDNA.Freckles.Density"},
  "eta_mins": 2,
  "provenance": {"source": "test", "reason": "acceptance test"}
}
```

**Response**:
```json
{
  "id": "251bc2c8-ae82-4181-b06e-d83a8049801c",
  "title": "Reduce uncertainty for Freckles",
  "action": "add_evidence",
  "args": {"trait": "PaDNA.SkinDNA.Freckles.Density"},
  "state": "queued",
  "created_ts": "2025-10-04T01:11:22.000000Z",
  "updated_ts": "2025-10-04T01:11:22.000000Z",
  "eta_mins": 2,
  "provenance": {"source": "test", "reason": "acceptance test"}
}
```

---

### GET /hc/tasks/list

List tasks for a user.

**Query Parameters**:
- `user_id` (required): User identifier
- `state` (optional): Filter by state (queued, running, done, failed, snoozed)

**Response**:
```json
{
  "tasks": [
    {
      "id": "...",
      "title": "...",
      "state": "queued",
      ...
    }
  ]
}
```

---

### POST /hc/tasks/tick

Run one task execution step.

Finds the oldest queued task and attempts to execute it.

**Query Parameters**:
- `user_id` (required): User identifier

**Response (task executed)**:
```json
{
  "executed": true,
  "task": {
    "id": "...",
    "title": "...",
    "state": "done",
    ...
  },
  "result": {
    "message": "Evidence request for ... logged",
    "next_step": "User should provide evidence via coach"
  }
}
```

**Response (no tasks)**:
```json
{
  "executed": false,
  "reason": "No queued tasks"
}
```

---

### POST /hc/tasks/update

Update task state manually.

**Request**:
```json
{
  "user_id": "alice",
  "task_id": "251bc2c8-ae82-4181-b06e-d83a8049801c",
  "new_state": "snoozed",
  "error": null
}
```

**Response**:
```json
{
  "id": "251bc2c8-ae82-4181-b06e-d83a8049801c",
  "state": "snoozed",
  ...
}
```

---

## CLI Usage

Run tasks from the command line:

```bash
# Run one tick for a user
python ReDNACoreDemo/scripts/hc_run_once.py --user alice

# Process reminders only
python ReDNACoreDemo/scripts/hc_run_once.py --user alice --reminders-only

# Process tasks only
python ReDNACoreDemo/scripts/hc_run_once.py --user alice --tasks-only

# Verbose output
python ReDNACoreDemo/scripts/hc_run_once.py --user alice -v
```

**Example Output**:
```
HC Runner for user: alice
============================================================

[1/2] Processing reminders...
  • No due reminders

[2/2] Processing tasks...
  ✓ Executed task: Reduce uncertainty for Freckles
    Action: add_evidence
    State: done

============================================================
Summary:
  Reminders processed: 0
  Tasks executed: 1
```

---

## Python API

```python
from ReDNACoreDemo.core.hc_task_runner import get_task_runner

# Get runner instance
runner = get_task_runner()

# Enqueue a task
task = runner.enqueue(
    user_id="alice",
    title="Reduce uncertainty for Freckles",
    action="add_evidence",
    args={"trait": "PaDNA.SkinDNA.Freckles.Density"},
    eta_mins=2,
    provenance={"source": "Photo Coach", "reason": "Delta analysis"}
)

# List tasks
queued_tasks = runner.list_tasks("alice", state="queued")

# Execute one task
result = runner.tick("alice")

# Update task state
runner.update_state("alice", task["id"], "snoozed")

# Delete a task
runner.delete_task("alice", task["id"])
```

---

## Execution Logic

When a task is executed (`tick()`):

1. Find oldest queued task
2. Mark as `running`
3. Execute based on `action` type
4. On success: mark as `done`
5. On failure: mark as `failed` with error message

### Execution Stubs (v2 Sprint 1a)

Current implementation provides stubs for all actions:

```python
def _execute_task(self, user_id, task):
    action = task.get("action")

    if action == "add_evidence":
        # Stub: Log request
        return {"message": "Evidence request logged", "next_step": "User should provide evidence"}

    elif action == "import_photo":
        # Stub: Log import request
        return {"message": "Photo import request logged"}

    # ... etc
```

**Sprint 1b/v3** will add real implementations that:
- Trigger Photo Coach for `import_photo`
- Submit observations for `add_evidence`
- Call rendering engine for `re_render`
- Generate snapshots/recaps with HC Brain

---

## Task Lifecycle Example

```
1. Photo Coach analyzes photo
   ↓
2. HC detects high curiosity trait
   ↓
3. HC enqueues "add_evidence" task
   ↓
4. Task state: queued
   ↓
5. User/cron calls tick()
   ↓
6. Task state: running
   ↓
7. Execute add_evidence action
   ↓
8. Task state: done
   ↓
9. User provides evidence
   ↓
10. Curiosity reduced
```

---

## Integration with Reminders

Reminders automatically enqueue tasks when due:

```
1. User schedules reminder
   ↓
2. Reminder waits until due_ts
   ↓
3. User/cron calls /hc/reminders/tick
   ↓
4. Reminder creates task
   ↓
5. Reminder marked completed
   ↓
6. Task appears in queue
   ↓
7. User/cron calls /hc/tasks/tick
   ↓
8. Task executes
```

---

## Error Handling

### Failed Tasks

When a task fails:
- State changes to `failed`
- Error message stored in `error` field
- Task remains in history for debugging

### Retry Logic

To retry a failed task:
```python
runner.update_state("alice", task_id, "queued")
```

This returns the task to the queue for re-execution.

---

## Best Practices

### 1. Keep Tasks Small
Each task should represent a single, atomic action (2-5 minutes).

### 2. Use Provenance
Always include provenance to track why a task was created:
```python
provenance={
    "source_coach": "Photo Coach",
    "reason": "Delta analysis identified missing evidence"
}
```

### 3. Set Realistic ETAs
Helps users understand time commitments:
- `add_evidence`: 2 mins
- `import_photo`: 3 mins
- `re_render`: 1 min
- `morning_snapshot`: 1 min

### 4. Clean Up Old Tasks
Periodically remove old `done` tasks to keep queue manageable.

---

## Limitations (v2 Sprint 1a)

- **No scheduling**: Tasks execute immediately when tick() is called
- **No priorities**: FIFO (oldest first) execution only
- **No dependencies**: Tasks can't wait for other tasks
- **Stub execution**: Real action implementations coming in Sprint 1b/v3
- **No parallelism**: One task at a time per user

---

## Future Enhancements (v3)

- Task priorities (high, medium, low)
- Task dependencies (`task_a` must complete before `task_b`)
- Scheduled execution (run task at specific time)
- Parallel execution (multiple tasks simultaneously)
- Task groups/batches
- Progress tracking (0-100%)
- Task templates/playbooks

---

## Related Documentation

- [HC v2 Sprint 1a](automation_log/hc-v2-sprint1a.md) — Implementation summary
- [HC Reminders](hc_reminders.md) — Reminders system (coming soon)
- [HC Persona](hc_persona.md) — HC behavior guidelines

---

**Last Updated**: 2025-10-04T01:15:00Z
**Version**: 2.0 (Sprint 1a)
**Status**: ✅ Production-ready
