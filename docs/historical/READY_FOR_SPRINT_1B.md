# Ready for Sprint 1b ✅

**Date**: 2025-10-04
**Sprint 1a Status**: COMPLETE & VERIFIED
**Tests**: 4/4 passing in fresh session

---

## Sprint 1a Complete ✅

All deliverables shipped and verified:

- ✅ **Task Runner** — File-backed queue with tick execution
- ✅ **Reminders** — Schedule → tick → auto-enqueue tasks
- ✅ **UCNRR Client** — Mock + real modes, non-blocking
- ✅ **Feature Flags** — Runtime YAML toggles
- ✅ **CLI Runner** — Cron-friendly execution script
- ✅ **11 API Endpoints** — Tasks, reminders, flags, state
- ✅ **Acceptance Tests** — 4/4 passing
- ✅ **Documentation** — Complete guides and examples

---

## Test Verification (This Session)

```
TEST 1: Feature Flags ✅
TEST 2: Task Runner (Queue → Tick → State Transitions) ✅
TEST 3: Reminders (Schedule → Tick → Task Enqueueing) ✅
TEST 4: HC State v2 (Flags, Tasks, Reminders) ✅

ALL TESTS PASSED ✅
```

**Verification Command**:
```bash
.venv/bin/python test_hc_v2_acceptance.py
```

---

## Sprint 1b Scope

### 1. UI Components

**Tasks Panel** (`web/src/components/hc/hc-tasks.tsx`):
- Display queued/running/done/failed tasks
- Task state badges with colors
- Provenance tooltips
- Manual tick button
- Real-time updates

**HC Panel Updates** (`web/src/components/hc/hc-panel.tsx`):
- Show reminders list
- Display task queue status
- Add "Schedule Reminder" button
- Show task execution history

**Next.js API Proxies**:
- `web/src/app/api/hc/tasks/queue/route.ts`
- `web/src/app/api/hc/tasks/list/route.ts`
- `web/src/app/api/hc/tasks/tick/route.ts`
- `web/src/app/api/hc/reminders/schedule/route.ts`
- `web/src/app/api/hc/reminders/list/route.ts`
- `web/src/app/api/hc/reminders/tick/route.ts`

---

### 2. Conversation Memory

**Core API** (`ReDNACoreDemo/core/api.py`):
- `POST /hc/say` — Record HC conversations
- Log dialogue to `data/users/{user_id}/hc/conversation/{date}.jsonl`
- Link conversations to task provenance
- Support multi-turn context

**React Integration**:
- Add chat input in HC panel
- Display conversation history
- Show HC responses
- Link tasks to conversation context

**Schema**:
```json
{
  "ts": "2025-10-04T01:30:00Z",
  "role": "user|assistant",
  "content": "...",
  "task_id": "optional-linked-task-id",
  "provenance": {...}
}
```

---

### 3. Playbook Runner

**Core API** (`ReDNACoreDemo/core/api.py`):
- `POST /hc/playbooks/run` — Execute playbook
- `GET /hc/playbooks/list` — List available playbooks
- `GET /hc/playbooks/status` — Check playbook execution status

**Playbooks to Implement**:
1. **Curiosity Campaign** — Enqueue tasks for high-curiosity traits
2. **Morning Snapshot** — Daily review of top traits
3. **Photo Refine** — Guide user through photo upload + fixes
4. **End of Day Recap** — Summarize day's changes

**Integration**:
- Playbooks enqueue tasks via task runner
- Tasks link back to playbook via provenance
- UI button to trigger playbook runs

---

### 4. Real Task Execution

**Replace Stubs in** `hc_task_runner.py`:

**`add_evidence`** — Currently stub:
```python
# Current (stub)
return {"message": "Evidence request logged"}

# Target (real)
trait_id = args["trait"]
evidence_type = args.get("type", "text")
# Prompt user for evidence, ingest via /ui/ingest/text
return {"evidence_id": "...", "trait": trait_id}
```

**`import_photo`** — Currently stub:
```python
# Current (stub)
return {"message": "Photo import logged"}

# Target (real)
photo_path = args["path"]
# Call Photo Coach extract endpoint
# Enqueue rescore task
return {"extracted_traits": [...], "rescore_task_id": "..."}
```

**`re_render`** — Currently stub:
```python
# Current (stub)
return {"message": "Re-render logged"}

# Target (real)
# Trigger /ui/render/avatar
# Poll for completion
return {"render_url": "...", "job_id": "..."}
```

**`morning_snapshot`** — Currently stub:
```python
# Current (stub)
return {"message": "Snapshot logged"}

# Target (real)
# Generate summary of top 5 traits by curiosity
# Log to conversation memory
return {"summary": "...", "traits": [...]}
```

**`end_of_day_recap`** — Currently stub:
```python
# Current (stub)
return {"message": "Recap logged"}

# Target (real)
# Compare current state to morning checkpoint
# Summarize changes
return {"recap": "...", "changes": [...]}
```

---

## File Structure (Sprint 1b)

```
web/src/
├── components/hc/
│   ├── hc-tasks.tsx                   # NEW: Tasks UI panel
│   └── hc-panel.tsx                   # MODIFIED: Add reminders/tasks display
├── app/api/hc/
│   ├── tasks/
│   │   ├── queue/route.ts             # NEW: Next.js proxy
│   │   ├── list/route.ts              # NEW: Next.js proxy
│   │   └── tick/route.ts              # NEW: Next.js proxy
│   ├── reminders/
│   │   ├── schedule/route.ts          # NEW: Next.js proxy
│   │   ├── list/route.ts              # NEW: Next.js proxy
│   │   └── tick/route.ts              # NEW: Next.js proxy
│   ├── say/route.ts                   # NEW: Conversation memory
│   └── playbooks/
│       ├── run/route.ts               # NEW: Playbook runner
│       └── list/route.ts              # NEW: Playbook list

ReDNACoreDemo/core/
├── api.py                             # MODIFIED: Add /hc/say, /hc/playbooks/*
└── hc_task_runner.py                  # MODIFIED: Real execution implementations
```

---

## Estimated Lines of Code

| Component | LOC |
|-----------|-----|
| UI Components | ~400 |
| Next.js API Proxies | ~200 |
| Conversation Memory | ~150 |
| Playbook Runner | ~200 |
| Real Task Execution | ~300 |
| Tests | ~200 |
| **Total** | **~1450** |

---

## Acceptance Tests (Sprint 1b)

1. **Task UI Test** — Verify tasks display in React panel
2. **Conversation Memory Test** — POST /hc/say, verify JSONL logging
3. **Playbook Runner Test** — Run curiosity campaign, verify tasks enqueued
4. **Real Execution Test** — Trigger add_evidence, verify evidence ingested
5. **End-to-End Test** — Onboard user → run playbook → execute tasks → verify state

---

## Design Decisions

### File-Backed Conversation Log
**Why**: Consistent with v1/Sprint 1a approach
**Format**: JSONL in `data/users/{user_id}/hc/conversation/`
**Benefits**: Easy to grep, append-only, no DB required

### Playbook as JSON
**Why**: Coach-agnostic, declarative, versionable
**Location**: `ReDNACoreDemo/core/hc_playbooks/*.json`
**Schema**:
```json
{
  "id": "curiosity_campaign",
  "title": "Curiosity Campaign",
  "tasks": [
    {
      "title": "Reduce uncertainty for {{trait}}",
      "action": "add_evidence",
      "args": {"trait": "{{trait}}"}
    }
  ]
}
```

### Real Execution Non-Blocking
**Why**: Tasks can fail gracefully without crashing queue
**Pattern**: Try/catch around all task actions, log errors, mark failed
**Retry**: User can manually retry failed tasks via UI

---

## Backward Compatibility

All Sprint 1b features are **additive**:
- ✅ No breaking changes to Sprint 1a API
- ✅ Stub execution still available (default for unknown actions)
- ✅ Feature flags control new features
- ✅ v1 endpoints unchanged

---

## Quick Start (Sprint 1a)

**Run Tests**:
```bash
.venv/bin/python -m uvicorn ReDNACoreDemo.core.api:app --port 8001
.venv/bin/python test_hc_v2_acceptance.py
```

**Enqueue Task**:
```bash
curl -X POST "http://localhost:8001/hc/tasks/queue?user_id=alice" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Reduce uncertainty for Freckles",
    "action": "add_evidence",
    "args": {"trait": "PaDNA.SkinDNA.Freckles.Density"},
    "eta_mins": 2
  }'
```

**Execute Task**:
```bash
curl -X POST "http://localhost:8001/hc/tasks/tick?user_id=alice"
```

---

## Documentation

- [HC v2 Sprint 1a Complete](HC_V2_SPRINT1A_COMPLETE.md) — Full delivery guide
- [Session Summary](SESSION_SUMMARY.md) — This session summary
- [Task Runner Guide](docs/hc_task_runner.md) — Task runner reference
- [HC Persona](docs/hc_persona.md) — Head Coach behavior guidelines
- [Automation Log](docs/automation_log/latest.md) — Latest changes

---

## Next Steps

When ready to begin Sprint 1b:

1. **Confirm Scope** — Review tasks above, adjust as needed
2. **Start with UI** — Build hc-tasks.tsx first (visible progress)
3. **Then Conversation** — Add /hc/say endpoint + React integration
4. **Then Playbooks** — Implement playbook runner
5. **Finally Real Execution** — Replace stubs with real implementations
6. **Test End-to-End** — Full flow from onboarding to task completion

---

**Status**: ✅ Sprint 1a complete, system verified, ready for Sprint 1b
**Blocking Issues**: None
**Dependencies**: All Sprint 1a infrastructure in place

---

**Last Verified**: 2025-10-04T01:29:26Z
**Tests Passing**: 4/4
**Production Ready**: ✅ Yes (single-user deployments)
