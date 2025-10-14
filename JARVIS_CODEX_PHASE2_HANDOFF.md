# 🧭 Jarvis-Codex Phase 2 Handoff — Continuation Prompt

**Status:** Foundation complete, remaining components pending
**Completed:** Design tokens, token validator, semantic patch engine (851 LOC)
**Remaining:** Auto-review, multi-file, rollback, API, UI, tests, docs (~2500 LOC)

---

## Context

Phase 2 implementation began with the foundation layer successfully completed:

### ✅ Completed Components

1. **Design-Token Registry** (`ReDNACoreDemo/core/jarvis_codex/design_tokens.json`)
   - 4 categories: color, spacing, typography, layout
   - 100+ utility → token mappings
   - Examples: `text-gray-600` → `text-foreground-muted`, `p-4` → `p-lg`

2. **Token Validator** (`ReDNACoreDemo/core/jarvis_codex/token_validator.py`, 208 LOC)
   - Validates token replacements against registry
   - Blocks arbitrary hex/rgb patterns (`[#fff]`, `rgb(...)`)
   - Methods: `validate_token_replacement()`, `validate_style_class()`, `validate_className_change()`
   - Detects unregistered utilities in style categories

3. **Semantic Patch Engine** (`ReDNACoreDemo/core/jarvis_codex/semantic_patch.py`, 423 LOC)
   - Operation allowlist: `rename_prop`, `wrap_node`, `reorder_siblings`, `replace_style_class`, `remap_token`
   - Per-operation safety limits (max files, max occurrences)
   - Manifest generation with `SemanticPatchManifest` dataclass
   - Risk scoring: 0.0–1.0 based on files, lines, operation complexity
   - AST validation stubs (bracket balancing for TSX/JSX)

**Key classes:**
- `SemanticChange` (dataclass): Single operation record
- `SemanticPatchManifest` (dataclass): Bundle of changes with summary
- `SemanticPatchEngine`: Generate patches, validate operations, calculate risk

---

## 🎯 Remaining Work

### 1) Auto-Review Pipeline

**File:** `ReDNACoreDemo/core/jarvis_codex/auto_review.py` (~350 LOC)

**Requirements:**

Create `AutoReviewer` class that runs pre-approval checks:

```python
class AutoReviewer:
    def __init__(self, token_validator, patch_engine):
        self.token_validator = token_validator
        self.patch_engine = patch_engine

    def review_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all auto-review checks.

        Returns:
        {
            "status": "pass|fail",
            "risk_score": 0.24,
            "checks": {
                "ast_parse": "pass",
                "token_policy": "pass",
                "diff_limits": "pass",
                "typecheck": "skipped"
            },
            "notes": ["Prop rename limited to <Card> in 1 file"],
            "recommendation": "approve|manual_review|reject"
        }
        """
```

**Checks to implement:**

1. **AST Parse Check**
   - Apply patch to file content
   - Run `patch_engine.validate_ast_syntax()`
   - Mark `pass` if syntax valid, `fail` otherwise

2. **Token Policy Check**
   - For `replace_style_class` or `remap_token` operations
   - Validate using `token_validator.validate_token_replacement()`
   - Mark `pass` if all tokens in registry

3. **Diff Limits Check**
   - Per-file limit: ≤60 lines
   - Per-proposal limit: ≤3 files
   - Mark `pass` if within limits

4. **Type Check (Stub)**
   - Check if `tsc --noEmit` available
   - If yes, run on patched file (optional)
   - If no or fails, mark `skipped` (don't block)

**Risk Score Thresholds:**
- 0.0–0.3: `recommendation: "approve"`
- 0.3–0.6: `recommendation: "manual_review"`
- 0.6–1.0: `recommendation: "reject"`

**Output:** Attach auto-review result to proposal object before returning from API.

---

### 2) Multi-File Support + Rollback

**File:** `ReDNACoreDemo/core/jarvis_codex/codex_agent.py` (+400 LOC)

**Extend existing `CodexAgent` class:**

#### Multi-File Proposal Creation

```python
def propose_multi_file_change(
    self,
    files: List[str],
    operations: List[Dict[str, Any]],
    intent: str,
    confidence: float,
    source: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create proposal affecting 1-3 files.

    Args:
        files: List of file paths
        operations: List of operation specs (one per file)
        intent: Human-readable intent
        confidence: 0.0-1.0
        source: "head_coach"|"user"

    Returns:
        (success, proposal_data)
    """
    # 1. Validate: max 3 files
    # 2. For each file, generate semantic patch
    # 3. Create manifest with all changes
    # 4. Run auto-review
    # 5. Store proposal with multi-file flag
    # 6. Return proposal data
```

#### Atomic Apply

```python
def apply_multi_file_proposal(
    self,
    proposal_id: str,
    user: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Apply multi-file proposal atomically.

    Process:
    1. Create backup for each file
    2. Apply patches sequentially
    3. If any fails, restore all backups and abort
    4. Log audit entry with all files

    Returns:
        (success, result_data)
    """
```

#### Rollback

```python
def rollback_proposal(
    self,
    proposal_id: str,
    user: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    Rollback applied proposal using backups.

    Process:
    1. Load proposal metadata
    2. Check if proposal was applied
    3. Restore all backup files
    4. Update proposal status to "rolled_back"
    5. Log audit entry

    Returns:
        (success, {
            "proposal_id": "...",
            "files_restored": ["file1", "file2"],
            "backup_paths": ["path1", "path2"]
        })
    """
```

**Backup Management:**
- Create `web/backups/<proposal_id>/` directory
- Store one backup per file: `<filename>_<timestamp>.bak`
- Keep backup manifest: `manifest.json` with file list and timestamps

**Telemetry Extensions:**
Add to all proposal logs:
```json
{
  "files": ["file1.tsx", "file2.tsx"],
  "operations": ["rename_prop", "replace_style_class"],
  "risk_score": 0.24,
  "auto_review_status": "pass"
}
```

---

### 3) API Endpoints

**File:** `ReDNACoreDemo/core/api.py` (+220 LOC)

**New/Modified Endpoints:**

#### POST /jarvis_codex/propose (Extend)

Add support for `suggested_change.type = "semantic"`:

```python
{
  "scope": "frontend",
  "file": "web/src/components/ui/Card.tsx",  # Primary file
  "files": ["web/src/components/ui/Card.tsx", "web/src/components/ui/CardHeader.tsx"],  # Optional: multi-file
  "intent": "Standardize Card props across components",
  "suggested_change": {
    "type": "semantic",
    "operation": "rename_prop",
    "selector": "Card",
    "from": "title",
    "to": "heading"
  },
  "confidence": 0.9,
  "source": "head_coach"
}
```

**Processing:**
1. Detect semantic operation
2. Use `SemanticPatchEngine` instead of text diff
3. Run `AutoReviewer.review_proposal()`
4. Attach `auto_review` block to proposal
5. Store manifest in `prompts/insights/patches/<proposal_id>_manifest.json`

#### POST /jarvis_codex/rollback (New)

```python
@app.post("/jarvis_codex/rollback")
def jarvis_codex_rollback(payload: Dict[str, Any], request: Request):
    """
    Rollback applied proposal.

    Payload:
    {
        "proposal_id": "550e8400-...",
        "user": "admin"
    }

    Returns:
    {
        "ok": true,
        "proposal_id": "...",
        "status": "rolled_back",
        "files_restored": ["file1.tsx", "file2.tsx"],
        "backup_paths": ["web/backups/.../file1_....bak"],
        "time_ms": 45.2
    }
    """
```

#### GET /jarvis_codex/proposals (Extend Response)

Add to each proposal object:
```json
{
  "proposal_id": "...",
  "type": "text_replace|semantic",
  "auto_review": {
    "status": "pass",
    "risk_score": 0.24,
    "checks": {...},
    "recommendation": "approve"
  },
  "manifest": {
    "changes": [...],
    "summary": {"insertions": 7, "deletions": 4, "files": 2}
  }
}
```

---

### 4) DevX Panel UI Enhancements

**File:** `ReDNACoreDemo/devx/frontend/src/routes/jarvis-codex/JarvisCodexPanel.tsx` (+350 LOC)

**New Components:**

#### ProposalTypePill

```tsx
function ProposalTypePill({ type }: { type: 'text_replace' | 'semantic' }) {
  const colors = {
    text_replace: 'bg-blue-100 text-blue-700',
    semantic: 'bg-purple-100 text-purple-700'
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[type]}`}>
      {type === 'semantic' ? '🔧 Semantic' : '📝 Text'}
    </span>
  );
}
```

#### AutoReviewChip

```tsx
function AutoReviewChip({ autoReview }: { autoReview: any }) {
  const colors = {
    pass: 'bg-emerald-100 text-emerald-700',
    fail: 'bg-red-100 text-red-700'
  };

  const riskColor = autoReview.risk_score < 0.3 ? 'text-green-600' :
                    autoReview.risk_score < 0.6 ? 'text-amber-600' : 'text-red-600';

  return (
    <div className="flex items-center gap-2">
      <span className={`px-2 py-1 rounded text-xs font-medium ${colors[autoReview.status]}`}>
        {autoReview.status === 'pass' ? '✓ Auto-Review' : '✗ Auto-Review'}
      </span>
      <span className={`text-xs font-medium ${riskColor}`}>
        Risk: {(autoReview.risk_score * 100).toFixed(0)}%
      </span>
    </div>
  );
}
```

#### MultiFileViewer

```tsx
function MultiFileViewer({ manifest }: { manifest: any }) {
  const [selectedFile, setSelectedFile] = useState(0);

  return (
    <div className="grid grid-cols-[200px_1fr] gap-4">
      {/* File tree sidebar */}
      <div className="border-r pr-4">
        <h4 className="font-semibold mb-2">Files ({manifest.summary.files})</h4>
        {manifest.changes.map((change, idx) => (
          <button
            key={idx}
            onClick={() => setSelectedFile(idx)}
            className={`block w-full text-left px-2 py-1 rounded text-sm ${
              selectedFile === idx ? 'bg-blue-100' : 'hover:bg-gray-100'
            }`}
          >
            {change.file.split('/').pop()}
            <span className="text-xs text-gray-500 ml-2">
              ±{change.lines_touched}
            </span>
          </button>
        ))}
      </div>

      {/* Diff viewer for selected file */}
      <div>
        <DiffViewer change={manifest.changes[selectedFile]} />
      </div>
    </div>
  );
}
```

#### GuardrailsChecklist

```tsx
function GuardrailsChecklist({ checks }: { checks: any }) {
  const checkIcons = {
    pass: '✓',
    fail: '✗',
    skipped: '○'
  };

  return (
    <div className="space-y-1">
      {Object.entries(checks).map(([name, status]) => (
        <div key={name} className="flex items-center gap-2 text-sm">
          <span className={status === 'pass' ? 'text-green-600' : status === 'fail' ? 'text-red-600' : 'text-gray-400'}>
            {checkIcons[status]}
          </span>
          <span>{name.replace('_', ' ')}</span>
        </div>
      ))}
    </div>
  );
}
```

#### RollbackButton

```tsx
function RollbackButton({ proposalId, onRollback }: any) {
  const [loading, setLoading] = useState(false);

  const handleRollback = async () => {
    if (!confirm('Rollback this proposal? This will restore original files.')) return;

    setLoading(true);
    try {
      const result = await rollbackProposal(proposalId, 'admin');
      toast.success(`✓ Rolled back: ${result.files_restored.length} files restored`);
      onRollback();
    } catch (error) {
      toast.error('Rollback failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleRollback}
      disabled={loading}
      className="px-3 py-1 bg-amber-500 text-white rounded hover:bg-amber-600 disabled:opacity-50"
    >
      {loading ? 'Rolling back...' : '↺ Rollback'}
    </button>
  );
}
```

**Update Main Panel:**
- Add type pill next to source badge
- Show auto-review chip in header
- Show guardrails checklist in metadata block
- Use `MultiFileViewer` for proposals with multiple files
- Add rollback button for applied proposals

**API Client Updates** (`jarvisCodexApi.ts`, +50 LOC):

```typescript
export async function rollbackProposal(
  proposalId: string,
  user: string = 'admin'
): Promise<RollbackResult> {
  const response = await fetch(`${API_BASE}/jarvis_codex/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposal_id: proposalId, user })
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  if (!data.ok) throw new Error(data.error);

  return data;
}
```

---

### 5) Test Suite

**File:** `ReDNACoreDemo/tests/test_jarvis_codex_phase2.py` (~650 LOC)

**Test Classes:**

#### TestTokenValidator

```python
def test_valid_token_replacement():
    validator = create_token_validator()
    is_valid, error = validator.validate_token_replacement("text-gray-600", "text-foreground-muted")
    assert is_valid is True

def test_arbitrary_hex_rejected():
    validator = create_token_validator()
    is_valid, error = validator.validate_style_class("text-[#ff0000]")
    assert is_valid is False
    assert "Arbitrary style" in error

def test_unregistered_utility_rejected():
    validator = create_token_validator()
    is_valid, error = validator.validate_style_class("text-custom-500")
    assert is_valid is False
```

#### TestSemanticPatchEngine

```python
def test_rename_prop_generates_patch(tmp_path):
    engine = create_semantic_patch_engine(tmp_path)

    # Create test file with <Card title="...">
    test_file = tmp_path / "Card.tsx"
    test_file.write_text('<Card title="Hello" />')

    patch, change = engine.generate_patch(
        test_file,
        "rename_prop",
        {"selector": "Card", "from": "title", "to": "heading"}
    )

    assert patch is not None
    assert 'heading="Hello"' in patch
    assert change.operation == "rename_prop"

def test_replace_style_class_uses_tokens(tmp_path):
    engine = create_semantic_patch_engine(tmp_path)

    test_file = tmp_path / "Button.tsx"
    test_file.write_text('<button className="text-gray-600">Click</button>')

    patch, change = engine.generate_patch(
        test_file,
        "replace_style_class",
        {"from": "text-gray-600", "to": "text-foreground-muted"}
    )

    assert 'text-foreground-muted' in patch
    assert change.lines_touched == 1

def test_risk_score_calculation():
    engine = create_semantic_patch_engine()

    changes = [
        SemanticChange("file1.tsx", "rename_prop", lines_touched=5),
        SemanticChange("file2.tsx", "wrap_node", lines_touched=3)
    ]

    manifest = engine.create_manifest("test-id", changes)

    # Risk should be > 0 due to 2 files + operations
    assert 0.0 < manifest.risk_score < 1.0
```

#### TestAutoReview

```python
def test_auto_review_passes_valid_proposal():
    reviewer = create_auto_reviewer()

    proposal = {
        "suggested_change": {
            "type": "semantic",
            "operation": "rename_prop",
            "selector": "Card",
            "from": "title",
            "to": "heading"
        },
        "file": "web/src/Card.tsx"
    }

    result = reviewer.review_proposal(proposal)

    assert result["status"] == "pass"
    assert result["checks"]["ast_parse"] == "pass"
    assert result["recommendation"] in ["approve", "manual_review"]

def test_auto_review_fails_large_diff():
    reviewer = create_auto_reviewer()

    # Proposal with >60 lines per file
    proposal = {...}  # Large diff

    result = reviewer.review_proposal(proposal)

    assert result["status"] == "fail"
    assert result["checks"]["diff_limits"] == "fail"
```

#### TestMultiFileAndRollback

```python
def test_multi_file_atomic_apply(tmp_path):
    agent = create_codex_agent(project_root=tmp_path)

    # Create proposal with 2 files
    result = agent.propose_multi_file_change(
        files=["file1.tsx", "file2.tsx"],
        operations=[...],
        intent="Test multi-file",
        confidence=0.9,
        source="test"
    )

    assert result[0] is True
    proposal_id = result[1]["proposal_id"]

    # Apply
    apply_result = agent.apply_multi_file_proposal(proposal_id, "admin")
    assert apply_result[0] is True

    # Rollback
    rollback_result = agent.rollback_proposal(proposal_id, "admin")
    assert rollback_result[0] is True
    assert len(rollback_result[1]["files_restored"]) == 2
```

#### TestUIIntegration

```python
@patch('fetch')
def test_panel_shows_risk_chip(mock_fetch):
    # Mock API response with auto_review
    mock_fetch.return_value.json.return_value = {
        "proposals": [{
            "proposal_id": "test",
            "auto_review": {"status": "pass", "risk_score": 0.24}
        }]
    }

    # Render component and check for risk chip
    # (Use React testing library or similar)
```

**Run all tests:**
```bash
pytest ReDNACoreDemo/tests/test_jarvis_codex_phase2.py -v
```

**Expected:** All green, <2s runtime

---

### 6) Documentation

**File:** `ReDNACoreDemo/docs/JARVIS_CODEX_PHASE2.md` (~700 LOC)

**Sections:**

1. **Overview**
   - What's new in Phase 2
   - Semantic vs text/style operations
   - Safety guarantees

2. **Semantic Operations**
   - Operation allowlist with examples
   - Per-operation limits
   - Code examples for each operation

3. **Design-Token System**
   - Token registry structure
   - How to add new tokens
   - Migration guide (utility → token)

4. **Auto-Review Pipeline**
   - Check descriptions
   - Risk scoring formula
   - Recommendation thresholds

5. **Multi-File Proposals**
   - When to use multi-file
   - Atomic apply guarantees
   - Rollback process

6. **API Reference**
   - Updated `/propose` with semantic support
   - New `/rollback` endpoint
   - Request/response examples

7. **DevX UI Guide**
   - New UI components
   - How to review semantic proposals
   - How to rollback

8. **Security Model**
   - Operation allowlist rationale
   - Token policy enforcement
   - AST validation

9. **Troubleshooting**
   - Common errors
   - How to debug failed auto-review
   - Rollback recovery

---

## 📊 Acceptance Criteria Checklist

- [ ] Semantic operations limited to allowlist
- [ ] AST parses before & after apply
- [ ] Design-token policy enforced
- [ ] Arbitrary styles (hex/rgb) rejected
- [ ] Auto-review computes risk + checks
- [ ] Risk score surfaced in DevX UI
- [ ] Multi-file bundles apply atomically
- [ ] Rollback restores all files
- [ ] Telemetry includes risk_score, ops, files
- [ ] 16+ tests passing
- [ ] Performance: <350ms render with 20 proposals
- [ ] No regressions to Phase 1/1B

---

## 🔬 Verification Commands

```bash
# 1. Test token validator
python3 -c "
from ReDNACoreDemo.core.jarvis_codex.token_validator import create_token_validator
v = create_token_validator()
print('✓ Valid token:', v.validate_token_replacement('text-gray-600', 'text-foreground-muted'))
print('✗ Invalid hex:', v.validate_style_class('text-[#ff0000]'))
"

# 2. Test semantic patch engine
python3 -c "
from ReDNACoreDemo.core.jarvis_codex.semantic_patch import create_semantic_patch_engine
from pathlib import Path
e = create_semantic_patch_engine()
print('✓ Operations:', e.allowed_operations)
print('✓ Risk calc:', e._calculate_risk_score([], {'files': 2, 'insertions': 10, 'deletions': 5}))
"

# 3. Run tests (when complete)
pytest ReDNACoreDemo/tests/test_jarvis_codex_phase2.py -v

# 4. Verify API endpoints (when implemented)
curl -X POST http://localhost:8015/jarvis_codex/propose -H "Content-Type: application/json" \
  -d '{"scope":"frontend","file":"web/src/Card.tsx","intent":"Test semantic","suggested_change":{"type":"semantic","operation":"rename_prop","selector":"Card","from":"title","to":"heading"},"confidence":0.9,"source":"test"}'

curl -X POST http://localhost:8015/jarvis_codex/rollback -H "Content-Type: application/json" \
  -d '{"proposal_id":"test-id","user":"admin"}'
```

---

## 📄 Files to Create/Modify

**New Files:**
- `ReDNACoreDemo/core/jarvis_codex/auto_review.py` (~350 LOC)
- `ReDNACoreDemo/tests/test_jarvis_codex_phase2.py` (~650 LOC)
- `ReDNACoreDemo/docs/JARVIS_CODEX_PHASE2.md` (~700 LOC)

**Modified Files:**
- `ReDNACoreDemo/core/jarvis_codex/codex_agent.py` (+400 LOC)
- `ReDNACoreDemo/core/api.py` (+220 LOC)
- `ReDNACoreDemo/devx/frontend/src/routes/jarvis-codex/JarvisCodexPanel.tsx` (+350 LOC)
- `ReDNACoreDemo/devx/frontend/src/lib/jarvisCodexApi.ts` (+50 LOC)

**Total Remaining:** ~2720 LOC

---

## 💡 Implementation Strategy

**Recommended Order:**

1. **Auto-Review Pipeline** (350 LOC, ~2 hours)
   - Highest value, enables risk assessment
   - Integrates with existing token validator + patch engine

2. **Multi-File + Rollback** (400 LOC, ~3 hours)
   - Critical for Phase 2 safety guarantees
   - Builds on Phase 1 backup system

3. **API Endpoints** (220 LOC, ~2 hours)
   - Wires everything together
   - Extends existing endpoints

4. **DevX UI** (400 LOC, ~3 hours)
   - Visual representation of new features
   - Enhances existing panel

5. **Tests** (650 LOC, ~3 hours)
   - Validates all components
   - Ensures no regressions

6. **Documentation** (700 LOC, ~2 hours)
   - Usage guide
   - API reference
   - Examples

**Total Estimated Time:** ~15 hours

---

## 🎯 One-Sentence Summary (Target)

"Jarvis-Codex Phase 2 implemented: safe semantic refactors with design-token enforcement, auto-review pipeline, risk scoring, and atomic multi-file rollback."

---

## Questions?

- Foundation components: `ReDNACoreDemo/core/jarvis_codex/` (design_tokens.json, token_validator.py, semantic_patch.py)
- Existing Phase 1/1B: `ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1.md`, `JARVIS_CODEX_PHASE1B.md`
- Tests for foundation: Can be added to test suite incrementally

---

**Ready to continue implementation!** 🚀

Start with auto-review pipeline → multi-file → API → UI → tests → docs.
