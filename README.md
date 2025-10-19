> **Note for AI Agents (Codex/Claude Code):**  
> Follow `docs/AGENT_PROTOCOL.md` and log every change to `docs/automation_log/changes.jsonl`.

# ReDNA Demos

This repository hosts the demo control panels and supporting services for the ReDNA experience (Core, UCN/RR, photo coaches, and supporting utilities).

## Virtual Environments

- **Root `.venv`** — used by Core, UCN/RR, and shared tooling.
  - Create: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
  - CP++ runs Core with: `<ABSOLUTE_REPO>/.venv/bin/python -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8004`
- **`PhotoRefinementCoach/.venv`** — create only if the photo coach requires conflicting dependencies.
  - `cd PhotoRefinementCoach && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

To consolidate environments, use `scripts/consolidate_venv.sh` (dry-run by default; set `RUN=1` to execute) which merges requirements into the root `.venv` and archives nested environments under `archive/venv_backup_<timestamp>/`.

## Control Panel Plus Plus (CP++)

To avoid picking up a nested venv (e.g., `PhotoRefinementCoach/.venv`), launch CP++ via the wrapper:

```bash
./scripts/run_cpplusplus.sh         # defaults to port 8501
./scripts/run_cpplusplus.sh 8510    # example: custom port
```

This guarantees Streamlit runs under `<repo>/.venv`.

### UCN/RR Service Management

CP++ provides full UCN/RR service management with:

- **Default Port:** 8017
- **Health Endpoint:** `http://127.0.0.1:8017/health`
- **Start Command:** Uses root `.venv/bin/python -m uvicorn ucnrr_app:app --host 0.0.0.0 --port {port} --reload`
- **Working Directory:** Repository root (where `ucnrr_app.py` lives)

**Configuration:**
- Port, working directory, and start command are editable in the "Environment & Ports" tab
- Settings persist to `.cpplusplus_env.json`

**Recommended Start Order:**
1. UCN/RR (Core depends on it for trait resolution)
2. Core
3. React / Streamlit

CP++ will automatically adopt already-running UCN/RR processes if they're healthy, or prompt you to resolve port conflicts before starting.

### AI Readiness & Unified Launch

- **Sidebar pulse:** CP++ polls `/devx/api/ingestion/ai_ready` every 10 seconds and shows a traffic-light pill. Clicking it opens React at `/tools/llm-benchmarks?tab=ai-readiness`.
- **Unified Launch All (open UI):** Starts UCN/RR → Core → React in order, waits for `llm_configured` and `rr_mode` health checks, then opens the LLM Benchmarks UI.
- **Stop / Restart All:** Gracefully stops managed processes _and_ clears ports 8017/8004/3000 before restarting the stack.
- **AI Config panel:** The Environment & Ports tab now surfaces the active AI env (LLM provider, model, Ollama base, UCNRR base/score path) with an “Apply & Restart” button to relaunch services with those settings.

## Holistic Review

The Holistic Review feature recalculates RR (Refinement Rating) and Curiosity values for all traits of a user by calling the UCN/RR `/api/rescore` endpoint and updating Core's `resolved.json`.

**Usage:**

1. In **CP++**, navigate to the **Launch** tab
2. Set the **Active user ID** to your target user
3. Click **🔄 Run Holistic Review**
4. Review the results in the expandable details panel

**API Endpoint:**

```bash
curl -X POST http://127.0.0.1:8004/ui/holistic/review \
  -H "Content-Type: application/json" \
  -d '{"user_id": "TEST"}'
```

**Response:**

```json
{
  "ok": true,
  "user_id": "TEST",
  "traits_updated": 12,
  "global_curiosity": 0.2456,
  "rescore_result": { ... },
  "provenance": { ... }
}
```

## Head Coach Orchestration — Coach Query + Rescore Now

The Head Coach provides two key endpoints for conversational interaction and trait rescoring:

### POST `/ui/coach/query`

Query any persona (head_coach, rc, photo, rendering) with conversational text. The endpoint:
- Loads persona-specific system prompts from the centralized registry
- Applies a shared safety preamble
- Logs provenance checkpoint events with persona, user input, and AI response

**Usage:**

```bash
curl -X POST http://127.0.0.1:8004/ui/coach/query \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "persona": "head_coach",
    "text": "What should I focus on next?"
  }'
```

**Response:**

```json
{
  "ok": true,
  "text": "Based on your profile, I suggest...",
  "event_ref": "checkpoint_1234567890"
}
```

### POST `/ui/coach/rescore_now`

Ingest freeform text, trigger UCN/RR rescore, and return updated traits with provenance logging.

**Usage:**

```bash
curl -X POST http://127.0.0.1:8004/ui/coach/rescore_now \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "text": "I noticed my eyes look more green in bright light.",
    "persona": "head_coach"
  }'
```

**Response:**

```json
{
  "ok": true,
  "updated_traits": [
    {
      "trait": "PaDNA.EyeDNA.IrisColor",
      "old_rr": 650.0,
      "new_rr": 720.0,
      "curiosity": 0.35
    }
  ],
  "event_ref": "checkpoint_1234567891"
}
```

**React Integration:**

The "Rescore Now" button in the Head Coach toolbar:
1. Captures text from the chat composer
2. Calls `/ui/coach/rescore_now`
3. Displays top 3 trait changes in a toast notification
4. Clears the composer on success

## Roundtrip Loop — Explorer Ingest & Trait Evolution

The Roundtrip Loop enables rapid exploration and refinement of user traits through a visual feedback cycle:

### Workflow

1. **Ingest** — User enters observations via text (e.g., "I noticed my eyes look more green in bright light")
2. **Rescore** — UCN/RR recalculates RR (Refinement Rating) and Curiosity for affected traits
3. **Visual Feedback** — UI auto-refreshes with:
   - Color-coded RR badges (low <333, medium 333-667, high >667)
   - Curiosity percentage badges showing data confidence
   - Delta indicators showing RR changes
4. **Undo** — Revert last rescore with one click (60-second window)

### RR/Curiosity Badges

Traits display inline badges in the Unabridged panel:

- **RR Badge**: Shows refinement rating with color band
  - 🔴 Low (0-332): Rose background
  - 🟡 Medium (333-667): Amber background
  - 🟢 High (668-1000): Emerald background

- **Curiosity Badge**: Shows data confidence as percentage
  - <20%: Low confidence (slate)
  - 20-50%: Moderate (blue)
  - 50-80%: High (violet)
  - >80%: Very high (fuchsia)

### Undo Last Rescore

```bash
curl -X POST http://127.0.0.1:8004/ui/trait/revert_last \
  -H "Content-Type: application/json" \
  -d '{"user_id": "TEST"}'
```

**Response:**

```json
{
  "ok": true,
  "reverted_count": 3,
  "message": "Reverted 3 traits to previous RR values"
}
```

**UI Integration:**

After a successful rescore, an "Undo" button appears in the Head Coach toolbar for 60 seconds, allowing instant reversion to previous RR values.

**How It Works:**

The undo functionality uses checkpoint-based provenance tracking:
1. Every `rescore_now` operation creates a checkpoint event with `trait_changes` array
2. Each trait change records: `trait` ID, `old_rr`, `new_rr`, `delta`, and `curiosity`
3. The `/ui/trait/revert_last` endpoint searches for the most recent `rescore_now` checkpoint
4. Traits are reverted by restoring their `old_rr` values from the checkpoint
5. Changes are immediately persisted to `resolved.json`

**Reliability:**

- Undo is **always available** via API (no 60-second limit)
- UI button timeout is purely UX (prevents accidental stale undos)
- Checkpoints are durable and survive service restarts
- Multiple sequential rescores can be undone (one at a time, newest first)
- No undo limit: works for any number of affected traits

### Screencast Script

```
1. Navigate to Head Coach panel with user "TEST" selected
2. Type in composer: "I have green eyes that change color in sunlight"
3. Click "Rescore Now"
4. Watch Observation Summary & Unabridged panels auto-refresh
5. Observe RR/Curiosity badges update with new values
6. See delta badges (+45, +12) appear next to updated traits in Unabridged panel
7. Toast notification shows: "Rescore complete! Updated 2 traits: IrisColor (+45), EyeDNA (+12)"
8. "↩ Undo" button appears in Head Coach toolbar (60-second window)
9. Click "↩ Undo" button
10. Panels refresh showing reverted RR values (deltas removed, original RR restored)
11. Toast confirms: "Undid last rescore (2 traits)"
12. Undo button disappears after successful revert
```

## How to Interpret Traits

Understanding the visual indicators and metrics in the ReDNA trait system:

### RR (Refinement Rating) Badges

RR values range from 0-1000 and indicate confidence in a trait's accuracy:

- **🔴 Low (0-332)**: Rose badge - Low confidence, needs more evidence
- **🟡 Medium (333-667)**: Amber badge - Moderate confidence, usable but improvable
- **🟢 High (668-1000)**: Emerald badge - High confidence, well-established

**Example:** `RR 742` with green badge = highly refined trait with strong evidence

### Curiosity Scores

Curiosity represents how valuable it would be to gather more evidence for a trait (0-100%):

- **<20%**: Slate badge - Low priority for additional data
- **20-50%**: Blue badge - Moderate value in gathering more evidence
- **50-80%**: Violet badge - High priority for data collection
- **>80%**: Fuchsia badge - Critical data gaps, urgent need for evidence

**High Curiosity Filter:** Use the "High curiosity ≥60%" checkbox to focus on traits with significant data gaps.

### Conflict Indicators

**⚠️ Warning Badge**: Appears when a trait has active conflicts or tensions

- Indicates contradictory evidence sources
- Hover for tooltip with conflict summary
- Common in traits with multiple observation channels
- Review provenance to understand conflicting data

### Staleness (Decay) Hints

**🕒 Clock Badge**: Appears when trait evidence is >30 days old

- Tooltip shows "Last updated N days ago"
- Suggests trait may need refresh
- Particularly important for dynamic traits (mood, preferences)
- Static traits (eye color, birth date) can safely be stale

### Provenance ("Why?") Button

Click the **Why?** button on any trait to see:

- Evidence sources and timestamps
- RR/Curiosity breakdown
- Reasons for current value
- Data gaps and recommended actions
- Source snippets and references

**Example workflow:**
1. Notice trait with ⚠️ conflict + 🕒 stale indicators
2. Click "Why?" to review evidence
3. Check if contradictions are due to outdated data
4. Use "Rescore Now" to refresh with new observations

### Complete Trait Anatomy

```
Trait: PaDNA.EyeDNA.IrisColor          🕒 (stale)
Value: "Hazel"                          ⚠️ (conflict)
RR: 650 (🟡 Medium)
Curiosity: 75% (Violet - High priority)
[Why?] [Timeline] buttons
```

**Interpretation:** This trait has medium confidence but high curiosity, with both staleness and conflict indicators. Priority action: gather fresh evidence via Photo Coach to resolve conflicts and improve RR.

## Photo Coach → Fix → Rescore → Render Flow

The Photo Coach provides a complete workflow for extracting traits from photos, applying suggested fixes, and triggering avatar renders.

### Workflow

1. **Upload Photo** — User uploads a photo via Photo Coach panel
2. **Extract Traits** — Core calls photo extraction service to identify traits (eye color, hair color, etc.)
3. **Three Fixes** — Photo Coach suggests up to 3 trait improvements with RR scores
4. **Apply Fix** — User clicks "Apply" button to accept a suggested trait value
5. **Override + Rescore** — Core applies trait override and triggers UCN/RR rescore
6. **Panel Refresh** — All panels auto-refresh to show updated trait values with delta badges
7. **Avatar Render** (optional) — User triggers avatar generation with updated traits

### POST `/ui/photo/apply_fix`

Apply a photo fix by creating a trait override and triggering automatic rescore.

**Usage:**

```bash
curl -X POST http://127.0.0.1:8004/ui/photo/apply_fix \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "trait_id": "PaDNA.EyeDNA.IrisColor",
    "value": "blue",
    "reason": "photo_fix_applied_from_ui"
  }'
```

**Response:**

```json
{
  "ok": true,
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": "blue",
  "changes": [
    {
      "trait": "PaDNA.EyeDNA.IrisColor",
      "old_rr": 750.0,
      "new_rr": 780.0,
      "delta": 30.0
    }
  ],
  "rescore_triggered": true
}
```

**React Integration:**

The Photo Coach panel displays extracted traits with "Apply" buttons:
1. User uploads photo
2. Photo Coach shows "Three Fixes" card with suggested trait improvements
3. Each fix shows: trait_id, value, RR score, and "Apply" button
4. Clicking "Apply" calls `/ui/photo/apply_fix`
5. Core writes override to `resolved.json` and triggers UCN/RR rescore
6. `'hc-traits-changed'` event dispatched → all panels refresh
7. Delta badges appear in Unabridged panel showing RR changes

### GET `/ui/render/jobs/{user_id}`

List all avatar rendering jobs for a user, sorted by creation time (newest first).

**Usage:**

```bash
curl http://127.0.0.1:8004/ui/render/jobs/TEST
```

**Response:**

```json
{
  "ok": true,
  "jobs": [
    {
      "job_id": "render_20251003_083000",
      "created_at": "2025-10-03T08:30:00Z",
      "traits_count": 42,
      "download_url": "/static/renders/TEST/render_20251003_083000/avatar.png",
      "state": "completed"
    },
    {
      "job_id": "render_20251003_073000",
      "created_at": "2025-10-03T07:30:00Z",
      "traits_count": 38,
      "download_url": "/static/renders/TEST/render_20251003_073000/avatar.png",
      "state": "completed"
    }
  ]
}
```

**React Integration (Pending):**

Rendering Coach panel will display job history and provide "Re-render" button to generate new avatar with current traits.

### Data Flow Diagram

```
┌─────────────┐
│ User Upload │
│    Photo    │
└──────┬──────┘
       │
       v
┌─────────────────┐
│ Photo Extraction│
│   (Core API)    │
└──────┬──────────┘
       │
       v
┌──────────────────────────────────────┐
│ Three Fixes Card                     │
│ ┌───────────────────────────────┐    │
│ │ Fix 1: eye_color → blue       │    │
│ │ RR: 820  [Apply]              │    │
│ ├───────────────────────────────┤    │
│ │ Fix 2: hair_color → brown     │    │
│ │ RR: 765  [Apply]              │    │
│ ├───────────────────────────────┤    │
│ │ Fix 3: skin_tone → medium     │    │
│ │ RR: 690  [Apply]              │    │
│ └───────────────────────────────┘    │
└──────┬───────────────────────────────┘
       │ User clicks "Apply"
       v
┌─────────────────┐
│ POST /ui/photo/ │
│   apply_fix     │
└──────┬──────────┘
       │
       ├─────────────────────┐
       v                     v
┌─────────────┐     ┌──────────────┐
│ Write       │     │ POST /api/   │
│ Override    │     │   rescore    │
│ (resolved)  │     │  (UCN/RR)    │
└─────────────┘     └──────┬───────┘
       │                   │
       │                   v
       │            ┌─────────────┐
       │            │ Update RR   │
       │            │ & Curiosity │
       │            └─────────────┘
       │
       └────────> Dispatch Event
                  'hc-traits-changed'
                         │
                         v
                  ┌──────────────┐
                  │ All Panels   │
                  │  Refresh     │
                  │ (Unabridged, │
                  │ Head Coach)  │
                  └──────────────┘
```

### Provenance Integration

All photo fix applications are logged to provenance checkpoints:

```json
{
  "event": "photo_fix_applied",
  "ts": 1728012000000,
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": "blue",
  "reason": "photo_fix_applied_from_ui",
  "rescore_triggered": true
}
```

Users can click the "Why?" button on any trait to view the complete provenance history, including photo fix applications and their impact on RR scores.

## Smoke Testing

Verify that Core and UCN/RR services are running and healthy:

```bash
./scripts/smoke_check.sh
```

**Output:**

```
==========================================
ReDNA Smoke Check
==========================================

== Core Health Check ==
✓ Core is UP at http://127.0.0.1:8004/health
{
  "service": "core",
  "version": "1.0.0",
  ...
}

== UCNRR Health Check ==
✓ UCNRR is UP at http://127.0.0.1:8017/api/health
{
  "status": "healthy",
  "service": "ucnrr",
  ...
}

== Core → UCNRR Integration Check ==
✓ Core can reach UCNRR
{
  "reachable": true,
  "base_url": "http://127.0.0.1:8017",
  ...
}

==========================================
Smoke check complete
==========================================
```

**Custom Ports:**

```bash
CORE_PORT=8020 UCNRR_PORT=8012 ./scripts/smoke_check.sh
```
