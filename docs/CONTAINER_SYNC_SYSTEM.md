# DNA Container Synchronization System

**Purpose**: Automatically keep DNA container definitions consistent across backend, frontend, and documentation.

## The Problem

DNA containers (PaDNA, Personality, Cognitive, etc.) are defined in multiple places:
1. **Backend**: `ReDNACoreDemo/core/hierarchy.py` - The authoritative source (REGISTRY dict)
2. **Frontend**: `web/src/components/rr-dna-panel.tsx` - UI display (DNA_CONTAINERS array)
3. **Documentation**: `docs/RR_BASELINE_REQUIREMENT.md` - Baseline requirement specs

When containers are added, removed, or renamed in `hierarchy.py`, the frontend and docs can become out of sync, causing:
- Missing containers in UI
- Orphaned trait data
- Outdated documentation
- Developer confusion

## The Solution: Automated Sync

### Sync Script: `ReDNACoreDemo/tools/sync_containers.py`

**What it does:**
1. Reads `REGISTRY` dict from `hierarchy.py`
2. Extracts all top-level container keys
3. Maps backend keys to frontend display names (using `CONTAINER_CONFIG`)
4. Updates `DNA_CONTAINERS` array in `rr-dna-panel.tsx`
5. Updates container list in `RR_BASELINE_REQUIREMENT.md` (between marker comments)

**Usage:**
```bash
# Dry run (shows what would change)
python3 ReDNACoreDemo/tools/sync_containers.py --dry-run

# Apply changes (merge mode - preserves planned containers)
python3 ReDNACoreDemo/tools/sync_containers.py

# Replace mode (removes unimplemented containers - use with caution!)
python3 ReDNACoreDemo/tools/sync_containers.py --mode=replace
```

**Modes:**
- **merge** (default): Adds backend containers to frontend, preserves planned containers not yet implemented
- **replace**: Removes frontend containers that don't exist in backend (destructive!)

**Example output:**
```
🔍 Scanning hierarchy.py for container definitions...
   Found 17 backend containers

📋 Mapping backend containers to frontend display format...
   Mapped to 12 frontend containers

🔄 Syncing container definitions (mode: merge)...
   Preserving 10 planned container(s) not yet in backend: Cultural, Environmental, Family, Finance, Gaming, Health, Learning, Routine, Safety, Writing
✅ Updated frontend containers in web/src/components/rr-dna-panel.tsx
✅ Updated container list in docs/RR_BASELINE_REQUIREMENT.md

✅ Container sync complete!
```

### Pre-Commit Hook: `.githooks/pre-commit`

**What it does:**
- Detects when `hierarchy.py` is being committed
- Automatically runs sync script
- Stages updated files (`rr-dna-panel.tsx`, `RR_BASELINE_REQUIREMENT.md`)
- Prevents committing hierarchy changes without syncing

**Setup:**
```bash
# Configure git to use .githooks directory
git config core.hooksPath .githooks

# Verify hook is installed
ls -la .githooks/pre-commit
```

**Example output:**
```
⚠️  Detected changes to hierarchy.py
🔄 Running container sync...
📝 Container sync updated files. Adding to commit...
✅ Container sync complete and staged
```

## Container Configuration

### Backend → Frontend Mapping

The sync script uses `CONTAINER_CONFIG` dict to map backend container keys to frontend display:

```python
CONTAINER_CONFIG = {
    # Frontend-only containers (top-level display categories)
    "Identity": {"icon": "🪪", "sensitive": False},
    "PaDNA": {"icon": "👤", "sensitive": False},
    "Personality": {"icon": "🎭", "sensitive": False},
    # ... more ...

    # Backend hierarchy → Frontend mapping
    "PaDNA.HairDNA": {"parent": "PaDNA"},
    "PaDNA.EyeDNA": {"parent": "PaDNA"},
    "PsyDNA.PersonalityDNA": {"parent": "Personality"},
    # ... more ...
}
```

**Mapping rules:**
1. **Top-level containers** (like `"PaDNA"`) have icon + sensitive flag
2. **Nested containers** (like `"PaDNA.HairDNA"`) map to a parent
3. Multiple backend containers can map to same frontend container
4. Frontend containers are de-duplicated automatically

### Adding New Containers

**Step 1: Update `hierarchy.py`**
```python
REGISTRY: Dict[str, List[str]] = {
    # ... existing containers ...

    # Add new container
    "NewDNA": [
        "Trait1",
        "Trait2",
    ],
}
```

**Step 2: Update `CONTAINER_CONFIG` in `sync_containers.py`**
```python
CONTAINER_CONFIG = {
    # ... existing config ...

    # Add frontend display config
    "NewDNA": {"icon": "🆕", "sensitive": False},

    # OR map to existing parent
    "NewDNA.Subcategory": {"parent": "Behavior"},
}
```

**Step 3: Run sync script**
```bash
python3 ReDNACoreDemo/tools/sync_containers.py
```

**Step 4: Commit**
```bash
git add ReDNACoreDemo/core/hierarchy.py
git add ReDNACoreDemo/tools/sync_containers.py  # If you updated CONTAINER_CONFIG
git commit -m "feat: add NewDNA container"

# Pre-commit hook will auto-sync frontend and docs
```

### Removing Containers

**Step 1: Remove from `hierarchy.py`**
```python
REGISTRY: Dict[str, List[str]] = {
    # Delete or comment out container
    # "OldDNA": [...],  # REMOVED
}
```

**Step 2: Run sync script**
```bash
python3 ReDNACoreDemo/tools/sync_containers.py
```

**Step 3: Verify no orphaned data**
```bash
# Check if any users have traits in removed container
grep -r "OldDNA" ReDNACoreDemo/data/users/*/resolved.json
```

**Step 4: Commit**
```bash
git add ReDNACoreDemo/core/hierarchy.py
git commit -m "feat: remove OldDNA container"

# Pre-commit hook will auto-sync frontend and docs
```

### Renaming Containers

**Option A: Backend key change (breaks existing data)**
```python
# Before
"OldName": ["Trait1", "Trait2"],

# After
"NewName": ["Trait1", "Trait2"],
```
⚠️ **Warning**: This breaks existing user data! All traits under `OldName.*` become orphaned.

**Option B: Display name change (data-safe)**
```python
# In sync_containers.py CONTAINER_CONFIG
CONTAINER_CONFIG = {
    # Keep backend key same, change display name
    "OldName": {"icon": "🆕", "sensitive": False},  # Frontend will show "OldName" (unchanged)
}

# In rr-dna-panel.tsx (manually edit after sync)
{ key: 'OldName', name: 'New Display Name', icon: '🆕', sensitive: false },
```
✅ **Safe**: Existing data still works, only display changes.

**Option C: Migration script (recommended for production)**
1. Add new container to hierarchy.py
2. Write migration script to copy `OldName.*` → `NewName.*`
3. Run migration on all users
4. Remove old container
5. Run sync script

## Validation

### After Syncing

**1. TypeScript type check:**
```bash
cd web
npm run typecheck
```

**2. Visual inspection:**
Open `web/src/components/rr-dna-panel.tsx` and verify:
- `DNA_CONTAINERS` array has expected containers
- Icons and sensitivity flags are correct
- No duplicate entries

**3. Documentation check:**
Open `docs/RR_BASELINE_REQUIREMENT.md` and verify:
- Container list is between `<!-- CONTAINER_LIST_START -->` and `<!-- CONTAINER_LIST_END -->`
- List matches frontend containers
- Sensitive containers are marked

**4. Runtime test:**
```bash
# Start dev server
cd web && npm run dev

# Navigate to RR by DNA panel
# Verify all containers appear correctly
# Check that traits are grouped under correct containers
```

## Troubleshooting

### "Could not find REGISTRY dict in hierarchy.py"
**Cause**: Script regex failed to parse REGISTRY
**Fix**: Ensure REGISTRY is formatted exactly as:
```python
REGISTRY: Dict[str, List[str]] = {
    "Container": [...],
}
```

### "Could not find insertion point in baseline doc"
**Cause**: Missing marker comments in `RR_BASELINE_REQUIREMENT.md`
**Fix**: Add markers manually:
```markdown
**Available DNA Containers**:
<!-- CONTAINER_LIST_START -->
<!-- CONTAINER_LIST_END -->
```

### "Frontend containers not updating"
**Cause**: Script couldn't match existing DNA_CONTAINERS array
**Fix**: Ensure `rr-dna-panel.tsx` has:
```typescript
const DNA_CONTAINERS = [
  { key: '...', name: '...', icon: '...', sensitive: ... },
];
```

### "Pre-commit hook not running"
**Cause**: Git not configured to use `.githooks/` directory
**Fix**:
```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

### "Container appears in backend but not frontend"
**Cause**: Missing entry in `CONTAINER_CONFIG`
**Fix**: Add mapping in `sync_containers.py`:
```python
CONTAINER_CONFIG = {
    "YourContainer": {"icon": "📦", "sensitive": False},
}
```

## Architecture Decisions

### Why backend is authoritative?
- `hierarchy.py` defines the canonical trait structure
- UCN/RR calculations depend on backend hierarchy
- Frontend displays what backend provides
- Documentation reflects implementation reality

### Why not use JSON schema?
- Python code is more flexible (comments, logic, helpers)
- Type hints provide validation (`Dict[str, List[str]]`)
- Easier for developers to edit
- No parsing overhead at runtime

### Why marker comments in docs?
- Allows human-readable content around auto-generated sections
- Preserves formatting and context
- Easily auditable in diffs
- Standard pattern (similar to code generation tools)

### Why pre-commit hook?
- Prevents forgetting to sync
- Catches issues before code review
- Auto-fixes common oversight
- Zero developer overhead

## Related Documentation

- [hierarchy.py](../ReDNACoreDemo/core/hierarchy.py) - Authoritative container registry
- [rr-dna-panel.tsx](../web/src/components/rr-dna-panel.tsx) - Frontend container display
- [RR_BASELINE_REQUIREMENT.md](./RR_BASELINE_REQUIREMENT.md) - Baseline specs with container list
- [sync_containers.py](../ReDNACoreDemo/tools/sync_containers.py) - Sync script implementation

## Future Enhancements

1. **Schema validation**: Add pytest test that verifies all backend containers have CONTAINER_CONFIG entries
2. **Migration support**: Auto-generate migration scripts when containers are renamed
3. **Orphan detection**: Scan user data for traits in removed containers
4. **Container metadata**: Track container descriptions, examples, use cases in REGISTRY
5. **Multi-language support**: Sync container display names for i18n locales

---

**Last Updated**: 2025-10-06
**Created By**: Automated container sync system implementation
**Status**: ✅ Active and enforced via pre-commit hook
