# Jarvis-Codex Interface — Phase 1

**Status:** ✅ Complete (Backend + DevX UI)
**Benchmark:** Self-Rewriting UI Capability
**Date:** 2025-10-10

## Overview

The Jarvis-Codex Interface enables Head Coach to safely propose and apply UI text/style edits through a guarded approval workflow. This establishes the foundation for ReDNA's self-rewriting interface capability.

**Phase 1 Scope:** Text replacement edits with full audit trail, checksum validation, and backup management.

## Architecture

### Core Components

1. **CodexAgent** (`ReDNACoreDemo/core/jarvis_codex/codex_agent.py`)
   - Validates edit requests
   - Generates unified diff patches
   - Manages proposal lifecycle
   - Enforces security constraints

2. **API Endpoints** (`ReDNACoreDemo/core/api.py`)
   - `POST /jarvis_codex/propose` — Create proposal
   - `GET /jarvis_codex/proposals` — List proposals
   - `GET /jarvis_codex/proposals/{proposal_id}` — Get single proposal
   - `POST /jarvis_codex/apply` — Apply approved proposal
   - `POST /jarvis_codex/reject` — Reject proposal

3. **Telemetry** (`prompts/insights/`)
   - `jarvis_codex_proposals.jsonl` — All proposals
   - `jarvis_codex_audit.jsonl` — Apply/reject actions
   - `jarvis_codex_telemetry.jsonl` — API events

## Security Model

### Validation Layers

**1. Scope Enforcement**
```python
allowed_scopes = [
    "web/src/",
    "devx/frontend/src/"
]
```
Only UI files allowed. Backend code protected.

**2. File Size Limit**
- Maximum: 50 KB per file
- Prevents processing large binaries or bundled assets

**3. Confidence Threshold**
- Minimum: 0.85 (configurable)
- Low-confidence proposals automatically rejected

**4. Checksum Validation**
```python
# On propose:
checksum_before = SHA256(file_content)

# On apply:
if SHA256(current_content) != checksum_before:
    abort("File changed since proposal")
```

**5. Atomic Backup**
- Every apply creates timestamped backup
- Location: `web/backups/{filename}_{timestamp}.bak`
- Enables rollback on errors

### Safety Guarantees

- ✅ **No backend code modification** — Scope restricted to UI only
- ✅ **Stale patch detection** — Checksum prevents race conditions
- ✅ **Reversible changes** — Full backup on every apply
- ✅ **Audit trail** — Complete history in JSONL logs
- ✅ **Confidence gating** — Low-quality proposals blocked

## Proposal Lifecycle

### 1. Propose

**Request:**
```json
{
  "scope": "frontend",
  "file": "web/src/components/header/HeaderTitle.tsx",
  "intent": "Improve clarity of main header",
  "suggested_change": {
    "type": "text_replace",
    "before": "Self-Improvement Panel",
    "after": "Adaptive Learning Dashboard"
  },
  "confidence": 0.93,
  "source": "head_coach"
}
```

**Processing:**
1. Validate scope (file in allowed paths)
2. Validate file size (<50KB)
3. Validate confidence (≥0.85)
4. Read file content
5. Generate unified diff
6. Compute SHA-256 checksum
7. Save patch file
8. Log to proposals.jsonl

**Response:**
```json
{
  "ok": true,
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "file": "web/src/components/header/HeaderTitle.tsx",
  "diff_preview": "--- a/web/src/components/header/HeaderTitle.tsx\n+++ b/web/src/components/header/HeaderTitle.tsx\n@@ -12,1 +12,1 @@\n-      <h1>Self-Improvement Panel</h1>\n+      <h1>Adaptive Learning Dashboard</h1>",
  "confidence": 0.93,
  "time_ms": 8.5
}
```

### 2. Review (via DevX UI or API)

**List Pending:**
```bash
GET /jarvis_codex/proposals?status=pending
```

**Response:**
```json
{
  "ok": true,
  "proposals": [
    {
      "proposal_id": "550e8400-...",
      "scope": "frontend",
      "file": "web/src/components/header/HeaderTitle.tsx",
      "intent": "Improve clarity of main header",
      "suggested_change": {
        "type": "text_replace",
        "before": "Self-Improvement Panel",
        "after": "Adaptive Learning Dashboard"
      },
      "confidence": 0.93,
      "source": "head_coach",
      "status": "pending",
      "created_at": "2025-10-10T02:45:00.123456Z",
      "checksum_before": "abc123...",
      "patch_file": "data/codex_patches/550e8400-....patch"
    }
  ],
  "total": 1
}
```

### 3. Apply (Approve)

**Request:**
```json
{
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "user": "admin"
}
```

**Processing:**
1. Load proposal from log
2. Verify status is "pending"
3. Compute current file checksum
4. Compare with stored checksum
5. **Abort if mismatch**
6. Create backup (web/backups/)
7. Apply text replacement
8. Write modified file
9. Update proposal status → "applied"
10. Log audit event

**Response:**
```json
{
  "ok": true,
  "proposal_id": "550e8400-...",
  "file": "web/src/components/header/HeaderTitle.tsx",
  "status": "applied",
  "time_ms": 18.2
}
```

**Audit Entry:**
```json
{
  "ts": "2025-10-10T02:45:30.456789Z",
  "proposal_id": "550e8400-...",
  "action": "applied",
  "user": "admin",
  "file": "web/src/components/header/HeaderTitle.tsx",
  "backup": "web/backups/HeaderTitle.tsx_20251010T024530.bak",
  "checksum_after": "def456..."
}
```

### 4. Reject (Alternative)

**Request:**
```json
{
  "proposal_id": "550e8400-...",
  "user": "admin",
  "reason": "Wording preference"
}
```

**Processing:**
1. Load proposal
2. Update status → "rejected"
3. Log audit event
4. **No file changes**

**Response:**
```json
{
  "ok": true,
  "proposal_id": "550e8400-...",
  "status": "rejected"
}
```

## API Reference

### POST /jarvis_codex/propose

Create a new edit proposal.

**Payload:**
```typescript
{
  scope: "frontend",
  file: string,  // Relative path from project root
  intent: string,  // Human-readable intent
  suggested_change: {
    type: "text_replace",
    before: string,
    after: string
  },
  confidence: number,  // 0.0 to 1.0
  source: string  // "head_coach" | "user" | etc.
}
```

**Response:**
```typescript
{
  ok: boolean,
  proposal_id: string,
  status: "pending",
  file: string,
  diff_preview: string,  // Unified diff
  confidence: number,
  time_ms: number
}
```

**Errors:**
- `400` — Invalid request (missing fields, bad scope, low confidence)
- `500` — Internal error (file I/O failure)

### GET /jarvis_codex/proposals

List proposals with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by "pending" | "applied" | "rejected"
- `limit` (default: 50): Max proposals to return

**Response:**
```typescript
{
  ok: boolean,
  proposals: Array<{
    proposal_id: string,
    scope: string,
    file: string,
    intent: string,
    suggested_change: object,
    confidence: number,
    source: string,
    status: string,
    created_at: string,
    checksum_before: string,
    patch_file: string
  }>,
  total: number
}
```

### POST /jarvis_codex/apply

Apply approved proposal.

**Payload:**
```typescript
{
  proposal_id: string,
  user: string  // User approving
}
```

**Response:**
```typescript
{
  ok: boolean,
  proposal_id: string,
  file: string,
  status: "applied",
  time_ms: number
}
```

**Errors:**
- `400` — Proposal not found, already applied/rejected, or checksum mismatch
- `500` — Apply failed (backup or write error)

### POST /jarvis_codex/reject

Reject proposal.

**Payload:**
```typescript
{
  proposal_id: string,
  user: string,
  reason?: string  // Optional rejection reason
}
```

**Response:**
```typescript
{
  ok: boolean,
  proposal_id: string,
  status: "rejected"
}
```

## Configuration

**Default Config:**
```json
{
  "allowed_scopes": [
    "web/src/",
    "devx/frontend/src/"
  ],
  "max_file_size_kb": 50,
  "min_confidence": 0.85,
  "backup_dir": "web/backups/",
  "proposals_log": "prompts/insights/jarvis_codex_proposals.jsonl",
  "audit_log": "prompts/insights/jarvis_codex_audit.jsonl"
}
```

**Customization:**
```python
from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

custom_config = {
    "min_confidence": 0.90,  # Stricter threshold
    "allowed_scopes": ["web/src/components/"]  # Narrower scope
}

agent = create_codex_agent(config=custom_config)
```

## File Layout

### Proposal Storage

```
data/codex_patches/
├── 550e8400-e29b-41d4-a716-446655440000.patch
├── 661f9511-f3ac-52e5-b827-557766551111.patch
└── ...
```

### Backups

```
web/backups/
├── HeaderTitle.tsx_20251010T024530.bak
├── HeaderTitle.tsx_20251010T031245.bak
└── ...
```

### Telemetry

```
prompts/insights/
├── jarvis_codex_proposals.jsonl  # All proposals
├── jarvis_codex_audit.jsonl      # Apply/reject actions
└── jarvis_codex_telemetry.jsonl  # API events
```

## Usage Examples

### Example 1: Propose from HC

```python
from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent

agent = create_codex_agent()

request = {
    "scope": "frontend",
    "file": "web/src/components/header/HeaderTitle.tsx",
    "intent": "Update panel title for clarity",
    "suggested_change": {
        "type": "text_replace",
        "before": "Self-Improvement Panel",
        "after": "Adaptive Learning Dashboard"
    },
    "confidence": 0.93,
    "source": "head_coach"
}

proposal, error = agent.generate_patch(request)

if error:
    print(f"Error: {error}")
else:
    print(f"Proposal created: {proposal.proposal_id}")
    print(f"Status: {proposal.status}")
    print(f"Diff preview:\n{agent.get_patch_diff(proposal.proposal_id)}")
```

### Example 2: List Pending Proposals

```python
agent = create_codex_agent()

pending = agent.list_proposals(status="pending", limit=10)

for proposal in pending:
    print(f"{proposal['proposal_id'][:8]}... - {proposal['file']}")
    print(f"  Intent: {proposal['intent']}")
    print(f"  Confidence: {proposal['confidence']}")
    print(f"  Created: {proposal['created_at']}")
```

### Example 3: Apply Proposal

```python
agent = create_codex_agent()

proposal_id = "550e8400-e29b-41d4-a716-446655440000"
success, error = agent.apply_patch(proposal_id, user="admin")

if success:
    print(f"✓ Proposal applied successfully")
else:
    print(f"✗ Apply failed: {error}")
```

### Example 4: Curl Commands

```bash
# Propose
curl -s -X POST http://localhost:8015/jarvis_codex/propose \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "frontend",
    "file": "web/src/components/header/HeaderTitle.tsx",
    "intent": "Clarify header",
    "suggested_change": {
      "type": "text_replace",
      "before": "Self-Improvement Panel",
      "after": "Adaptive Learning Dashboard"
    },
    "confidence": 0.93,
    "source": "head_coach"
  }' | jq .

# List pending
curl -s http://localhost:8015/jarvis_codex/proposals?status=pending | jq .

# Apply
curl -s -X POST http://localhost:8015/jarvis_codex/apply \
  -H "Content-Type: application/json" \
  -d '{"proposal_id":"550e8400-...","user":"admin"}' | jq .

# Reject
curl -s -X POST http://localhost:8015/jarvis_codex/reject \
  -H "Content-Type: application/json" \
  -d '{"proposal_id":"550e8400-...","user":"admin","reason":"Not needed"}' | jq .
```

## Test Coverage

**Test Suite:** `ReDNACoreDemo/tests/test_jarvis_codex_phase1.py`

**8 Scenarios (All Passing):**

1. ✅ `test_valid_proposal_creates_patch` — Patch + JSON log
2. ✅ `test_checksum_mismatch_aborts_apply` — Safety abort
3. ✅ `test_low_confidence_rejected` — Threshold enforcement
4. ✅ `test_approve_flow_with_backup` — Full apply workflow
5. ✅ `test_reject_flow` — Status update only
6. ✅ `test_telemetry_events` — Audit logging
7. ✅ `test_api_round_trip` — Endpoint validation
8. ✅ `test_list_proposals_filtering` — Status filtering

**Run Tests:**
```bash
PYTHONPATH=.:ReDNACoreDemo:$PYTHONPATH python3 -m pytest \
  ReDNACoreDemo/tests/test_jarvis_codex_phase1.py -v
```

**Expected:**
```
===================== 8 passed in 0.30s =========================
```

## Performance

**Benchmarks:**
- Propose (with diff): ~5-10ms
- Apply (with backup + checksum): ~15-25ms
- List 20 proposals: <5ms
- API overhead: ~10-15ms
- Total round-trip: <50ms

**Acceptance Criteria:**
- ✅ Propose + list + apply: <100ms total
- ✅ No blocking I/O
- ✅ Diff computation optimized for <50KB files

## DevX UI Panel (Pending)

**File:** `ReDNACoreDemo/devx/frontend/src/routes/jarvis-codex/JarvisCodexPanel.tsx`

**Proposed Features:**

### Layout

```
┌─────────────────────────────────────────────────────┐
│ Jarvis Codex Editor         [Guarded Mode On 🔴]   │
├──────────────┬──────────────────────────────────────┤
│ Pending (3)  │ Proposal #550e8400                   │
│ Applied (12) │ File: web/src/components/.../Title   │
│ Rejected (2) │ Intent: Clarify header               │
│              │ Confidence: 93%                      │
│ ─────────────│                                      │
│ □ Proposal 1 │ ┌────────────────────────────────┐   │
│ □ Proposal 2 │ │ Monaco Diff Viewer             │   │
│ ☑ Proposal 3 │ │ - Self-Improvement Panel       │   │
│              │ │ + Adaptive Learning Dashboard  │   │
│              │ └────────────────────────────────┘   │
│              │                                      │
│              │ [✅ Approve]  [❌ Reject]             │
└──────────────┴──────────────────────────────────────┘
```

### Components

**1. Sidebar** (`ProposalList.tsx`)
- Filterable list (All/Pending/Applied/Rejected)
- Confidence score badges
- Created timestamp
- Source indicator (HC/User)

**2. Main Pane** (`ProposalViewer.tsx`)
- Monaco Diff Viewer (side-by-side)
- File path + intent display
- Confidence meter
- Action buttons

**3. Header** (`CodexHeader.tsx`)
- Mode badge (Guarded/Developer)
- Auto-refresh toggle
- Settings menu

**4. Notifications** (React Toastify)
- Apply success: "✓ Proposal applied"
- Apply error: "✗ Checksum mismatch"
- Reject: "Proposal rejected"

### Tech Stack

- React + TypeScript
- Monaco Editor (`@monaco-editor/react`)
- Tailwind CSS
- React Query (data fetching)
- React Toastify (notifications)

**Estimated:** ~500 LOC + tests

## Integration with HC

**Future Enhancement:** HC can propose edits during conversations

**Example HC Prompt Addition:**
```markdown
You can propose UI text improvements using:

{
  "action": "propose_ui_edit",
  "file": "web/src/components/...",
  "change": {
    "before": "...",
    "after": "..."
  },
  "intent": "...",
  "confidence": 0.93
}

Only suggest for:
- Clarity improvements
- Consistency fixes
- Accessibility enhancements

Never modify:
- Backend code
- Security-sensitive text
- User-generated content
```

## Phase 2 Roadmap

**Future Enhancements:**

1. **Semantic Refactoring**
   - Component renaming with import updates
   - Function signature changes
   - TypeScript type updates

2. **Multi-File Atomic Changes**
   - Cross-file refactoring
   - Dependency graph validation
   - Git commit bundling

3. **Design Token Integration**
   - Color scheme updates
   - Typography changes
   - Spacing scale modifications

4. **AI-Suggested Improvements**
   - Style consistency scanning
   - Accessibility audits
   - Performance optimizations

5. **Preview Mode**
   - Hot-reload preview
   - Visual diff rendering
   - Component isolation sandbox

## Troubleshooting

### "Checksum mismatch" Error

**Cause:** File was modified between proposal creation and apply attempt.

**Solution:**
1. Create a new proposal with current file content
2. Or, manually revert file to match checksum
3. Or, use backup to restore previous state

### "Text not found in file"

**Cause:** Target text doesn't exist or appears multiple times.

**Solution:**
- Be more specific in "before" text
- Include surrounding context
- Check file hasn't been modified

### Low Confidence Rejection

**Cause:** Confidence below 0.85 threshold.

**Solution:**
- Increase confidence score if justified
- Or, adjust `min_confidence` in config
- Or, manually approve via direct file edit

## Security Considerations

**Threat Model:**

1. **Malicious Proposals**
   - Mitigated by scope enforcement
   - Backend code unreachable

2. **Path Traversal**
   - Validated against allowed_scopes
   - Relative paths resolved safely

3. **Code Injection**
   - Text replacement only (no eval)
   - Diff validation

4. **Race Conditions**
   - Checksum prevents stale patches
   - Atomic file operations

5. **Audit Trail Tampering**
   - Append-only JSONL logs
   - External backup recommended

---

## DevX UI Panel

**Status:** ✅ Complete
**Location:** `ReDNACoreDemo/devx/frontend/src/routes/jarvis-codex/`

### Components

#### 1. API Client (`lib/jarvisCodexApi.ts`)

TypeScript client for Jarvis-Codex backend with full type safety.

**Key Types:**
```typescript
interface Proposal {
  proposal_id: string;
  scope: string;
  file: string;
  intent: string;
  suggested_change: SuggestedChange;
  confidence: number;
  source: string;
  status: 'pending' | 'applied' | 'rejected';
  created_at: string;
  checksum_before?: string;
  patch_file?: string;
}

interface ApplyResult {
  ok: boolean;
  proposal_id: string;
  file: string;
  status: 'applied';
  backup?: string;
  time_ms: number;
}
```

**API Functions:**
- `listProposals(status?, limit)` — Fetch proposals with optional filter
- `getProposal(proposalId)` — Get single proposal by ID
- `applyProposal(proposalId, user)` — Approve and apply proposal
- `rejectProposal(proposalId, user, reason?)` — Reject proposal
- `getProposalStats()` — Get counts by status

#### 2. Main Panel (`JarvisCodexPanel.tsx`)

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│ Header                                               │
│ ┌────────┐ ┌───────────┐ ┌─────┬────────┬────────┐ │
│ │Refresh │ │Guarded On │ │ 5 P │ 3 A    │ 2 R    │ │
│ └────────┘ └───────────┘ └─────┴────────┴────────┘ │
├──────────────┬───────────────────────────────────────┤
│ Sidebar      │ Main Pane                             │
│              │                                       │
│ ┌──────────┐ │ ┌─────────────────────────────────┐ │
│ │All       │ │ │ File: HeaderTitle.tsx           │ │
│ │Pending   │ │ │ Intent: Improve clarity         │ │
│ │Applied   │ │ │ Confidence: 93%                 │ │
│ │Rejected  │ │ └─────────────────────────────────┘ │
│ └──────────┘ │                                       │
│              │ ┌─────────────────────────────────┐ │
│ • Proposal 1 │ │ Diff Viewer                     │ │
│ • Proposal 2 │ │ - Old: "Self-Improvement Panel" │ │
│ • Proposal 3 │ │ + New: "Adaptive Dashboard"     │ │
│              │ └─────────────────────────────────┘ │
│              │                                       │
│              │ ┌─────────┐ ┌────────┐              │
│              │ │ Approve │ │ Reject │              │
│              │ └─────────┘ └────────┘              │
└──────────────┴───────────────────────────────────────┘
```

**Features:**

1. **Header**
   - Refresh button with loading state
   - "Guarded Mode On" badge (red warning indicator)
   - Live stats chips: Pending/Applied/Rejected counts
   - Auto-refreshes stats on mount and after actions

2. **Sidebar**
   - Filter chips: All | Pending | Applied | Rejected
   - Scrollable proposal list
   - Each item shows:
     - File name (truncated)
     - Intent (truncated)
     - Confidence percentage
     - Created date (relative, e.g., "2h ago")
     - Source badge
     - Status indicator (colored dot)

3. **Main Pane**
   - Metadata block:
     - Full file path
     - Intent description
     - Source and confidence
     - Status and checksum (for debugging)
   - Diff viewer:
     - Side-by-side before/after comparison
     - Syntax highlighting (simple)
     - Scrollable for long changes
   - Action buttons:
     - "Approve" (green) — Only for pending proposals
     - "Reject" (red) — Only for pending proposals
     - Disabled for already-actioned proposals

**State Management:**
```typescript
const [proposals, setProposals] = useState<Proposal[]>([]);
const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
const [filter, setFilter] = useState<FilterStatus>('all');
const [loading, setLoading] = useState(true);
```

**Optimistic UI:**
```typescript
// Approve with instant feedback
const handleApprove = async () => {
  // Optimistic update
  setProposals(prev => prev.map(p =>
    p.proposal_id === id ? { ...p, status: 'applied' } : p
  ));

  try {
    await applyProposal(id);
    toast.success('✓ Proposal Applied');
  } catch (error) {
    // Rollback on error
    await loadProposals();
    toast.error('Failed to apply');
  }
};
```

**Performance:**
- Renders 20 proposals: <300ms
- Diff viewer mount: <200ms for files ≤50KB
- Filter switching: <50ms
- Optimistic updates: <10ms

#### 3. Navigation Integration

**File:** `ReDNACoreDemo/devx/frontend/src/App.tsx`

Added navigation link and route:
```tsx
<NavLink to="/jarvis-codex">
  🤖 Jarvis-Codex
</NavLink>

<Route path="/jarvis-codex" element={<JarvisCodexPanel />} />
```

### User Workflow

#### Reviewing Proposals

1. Open DevX → Navigate to "🤖 Jarvis-Codex"
2. Panel loads all pending proposals (default filter)
3. Stats chips show: 5 Pending, 3 Applied, 2 Rejected
4. Sidebar lists proposals with metadata

#### Approving a Proposal

1. Click proposal in sidebar → Main pane shows details
2. Review:
   - File path and intent
   - Confidence score (must be ≥85%)
   - Before/after diff
   - Source (e.g., "head_coach")
3. Click "Approve" button
4. **Optimistic update:** Status → "applied" (instant UI feedback)
5. **API call:** Backend creates backup, applies change
6. **Toast notification:** "✓ Proposal Applied — Backup: web/backups/..."
7. Proposal removed from sidebar (no longer pending)

#### Rejecting a Proposal

1. Click proposal → Review diff
2. Click "Reject" button
3. Optional: Add reason in prompt (future enhancement)
4. **Optimistic update:** Status → "rejected"
5. **API call:** Backend logs rejection to audit trail
6. **Toast notification:** "✓ Proposal Rejected"
7. Proposal removed from sidebar

#### Viewing History

1. Click "Applied" filter chip
2. Sidebar shows all applied proposals
3. Main pane displays read-only view
4. Backup path shown in metadata (for manual rollback)

### API Endpoint Added

**GET /jarvis_codex/proposals/{proposal_id}**

Single proposal fetch for performance optimization.

**Response:**
```json
{
  "ok": true,
  "proposal": {
    "proposal_id": "550e8400-...",
    "file": "web/src/components/header/HeaderTitle.tsx",
    "intent": "Improve clarity",
    "confidence": 0.93,
    "status": "pending",
    ...
  },
  "time_ms": 12.5
}
```

**Usage:** Frontend uses this for detail view instead of filtering full list client-side.

### Confidence Thresholds

**Backend Enforcement:**
- Minimum: **0.85** (configurable in `codex_agent.py`)
- Proposals below threshold rejected on `/propose`

**UI Indicators:**
- 0.85–0.89: Yellow badge ("Moderate")
- 0.90–0.94: Blue badge ("High")
- 0.95–1.00: Green badge ("Very High")

**Rationale:**
- Prevents low-quality AI-generated edits
- Reduces human review burden
- Ensures only confident proposals reach UI

### Checksum Validation

**Flow:**

1. **On Propose:**
   ```python
   checksum_before = hashlib.sha256(file_content.encode()).hexdigest()
   ```
   Stored in proposal metadata.

2. **On Apply:**
   ```python
   current_checksum = hashlib.sha256(current_content.encode()).hexdigest()
   if current_checksum != proposal.checksum_before:
       abort("File changed since proposal")
   ```

**UI Behavior:**
- Apply fails with error toast: "File changed since proposal (checksum mismatch)"
- Proposal remains pending
- User must refresh proposal or reject outdated one

**Why This Matters:**
- Prevents race conditions (file edited between propose and apply)
- Protects against stale patches overwriting recent changes
- Maintains data integrity

### Backup Management

**Created On:** Every `/apply` action

**Location:** `web/backups/{filename}_{timestamp}.bak`

**Example:**
```
web/backups/HeaderTitle.tsx_20251010_024530.bak
```

**Content:** Full original file before change

**Rollback (Manual):**
```bash
cp web/backups/HeaderTitle.tsx_20251010_024530.bak \
   web/src/components/header/HeaderTitle.tsx
```

**Audit Trail Reference:**
```json
{
  "ts": "2025-10-10T02:45:30Z",
  "proposal_id": "550e8400-...",
  "action": "applied",
  "user": "admin",
  "file": "web/src/components/header/HeaderTitle.tsx",
  "backup": "web/backups/HeaderTitle.tsx_20251010_024530.bak"
}
```

**Retention:** Manual cleanup (recommend keep 30 days)

### Audit Trail Examples

**Location:** `prompts/insights/jarvis_codex_audit.jsonl`

**Applied Proposal:**
```json
{
  "ts": "2025-10-10T02:45:30.123456+00:00",
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "action": "applied",
  "user": "admin",
  "file": "web/src/components/header/HeaderTitle.tsx",
  "backup": "web/backups/HeaderTitle.tsx_20251010_024530.bak",
  "checksum_after": "a7f3b2e1..."
}
```

**Rejected Proposal:**
```json
{
  "ts": "2025-10-10T02:50:15.987654+00:00",
  "proposal_id": "660f9511-f3ac-52e5-b827-557766551111",
  "action": "rejected",
  "user": "admin",
  "reason": "Wording preference - keep original"
}
```

**Checksum Mismatch:**
```json
{
  "ts": "2025-10-10T03:00:00.000000+00:00",
  "proposal_id": "770fa622-g4bd-63f6-c938-668877662222",
  "action": "checksum_mismatch",
  "user": "admin",
  "file": "web/src/components/dashboard/Dashboard.tsx",
  "reason": "File changed since proposal (manual edit detected)"
}
```

**Query Examples:**
```bash
# Count total applies
grep '"action":"applied"' prompts/insights/jarvis_codex_audit.jsonl | wc -l

# Find all backups for specific file
grep 'HeaderTitle.tsx' prompts/insights/jarvis_codex_audit.jsonl | jq '.backup'

# Recent rejections
tail -20 prompts/insights/jarvis_codex_audit.jsonl | grep rejected
```

### Screenshots

*(DevX panel in action — to be added after deployment)*

**Pending Proposals View:**
- Header with stats: 5 Pending, 3 Applied, 2 Rejected
- Sidebar showing filtered list
- Main pane with diff viewer and approve/reject buttons

**Applied Proposal (History):**
- Sidebar filtered to "Applied" status
- Main pane showing read-only view
- Backup path displayed in metadata

**Toast Notifications:**
- Success: "✓ Proposal Applied — Backup: web/backups/..."
- Error: "✗ Failed to apply: File changed since proposal"

---

**Next Steps:**
1. ~~Implement DevX UI Panel (~500 LOC)~~ ✅ Complete
2. Integrate HC proposal capability (Phase 1B)
3. Add visual regression testing
4. Expand to semantic refactoring (Phase 2)

**Questions?** See test suite for working examples or inspect audit logs.
