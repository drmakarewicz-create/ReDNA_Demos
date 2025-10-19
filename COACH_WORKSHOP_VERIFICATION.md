# Coach Workshop Implementation — Verification Report

**Date:** 2025-10-09
**Status:** ✅ Complete

## Summary

Implemented Coach Workshop improvements with canonical registry and missing-file scaffold support.

## Components Implemented

### 1. Coach Registry ([ReDNACoreDemo/devx/backend/coach_registry.py](ReDNACoreDemo/devx/backend/coach_registry.py))
- **COACH_ROLES**: Canonical list of 12 coach roles
  - head_coach, career_coach, photo_coach, padna_coach, onboarding_coach
  - relationship_coach, credit_card_coach, claim_counsel_coach
  - permission_coach, personality_test_coach, beliefdna_coach, chatdna_coach
- **SYSTEM_AGENTS**: Exclusion list (core_ai.md, ucn_rr_ai.md)
- **get_coach_by_id()**: Lookup helper
- **get_default_scaffold()**: Template generator for missing files

### 2. Backend API ([ReDNACoreDemo/devx/backend/coach_api.py](ReDNACoreDemo/devx/backend/coach_api.py))
- **GET /devx/api/coaches**: Returns all registry roles with status
  - Fields: `id`, `label`, `filename`, `prompt_path`, `exists`, `status`, `size_bytes`
  - Status: "present" | "missing"
  - Excludes system agents
- **GET /devx/api/coaches/{coach_id}**: Returns prompt or scaffold
  - Returns 200 with scaffold if file missing (`exists: false`)
  - Returns file content if present
- **PUT /devx/api/coaches/{coach_id}**: Create or update prompt
  - Creates timestamped backup for existing files
  - Creates new file from scaffold
  - Returns backup path and metadata

### 3. Frontend ([ReDNACoreDemo/devx/frontend/src/routes/coach-workshop/CoachWorkshop.tsx](ReDNACoreDemo/devx/frontend/src/routes/coach-workshop/CoachWorkshop.tsx))
- **Coach List Panel**: All registry roles with badges
  - Green "Present" badge for existing files
  - Blue "Scaffold" badge for missing files
  - Shows registry stats (present vs missing)
- **Editor Panel**: Unified interface for existing and scaffold prompts
  - Blue "Scaffold (not saved yet)" badge when `exists: false`
  - Amber "Unsaved changes" badge when dirty
  - Button text adapts: "Create Prompt" vs "Save Prompt"
  - Download button to export markdown locally
- **Error Handling**: No 404 errors - missing files return scaffolds gracefully

## Verification Tests

### ✅ Backend API Tests

```bash
# Test 1: List all coaches (12 total, mixed present/missing)
curl http://127.0.0.1:8100/devx/api/coaches
# Result: 12 coaches returned, status correctly shows "present" or "missing"

# Test 2: GET missing coach returns scaffold (200 OK)
curl http://127.0.0.1:8100/devx/api/coaches/career_coach
# Result: {"exists": false, "text": "<!-- Career Coach Prompt Scaffold -->..."}

# Test 3: GET existing coach returns file content
curl http://127.0.0.1:8100/devx/api/coaches/padna_coach
# Result: {"exists": true, "text": "# PaDNA Outbound Coach...", "size_bytes": 324}

# Test 4: PUT creates new file from scaffold
curl -X PUT http://127.0.0.1:8100/devx/api/coaches/permission_coach \
  -H "Content-Type: application/json" \
  -d '{"text":"# Permission Coach Test\n..."}'
# Result: {"saved": true, "backup_created": false, "bytes": 73}

# Test 5: PUT updates existing file and creates backup
curl -X PUT http://127.0.0.1:8100/devx/api/coaches/permission_coach \
  -H "Content-Type: application/json" \
  -d '{"text":"# Permission Coach v2\n..."}'
# Result: {"saved": true, "backup_created": true, "backup_path": "prompts/backups/permission_coach_20251009_114806.md"}

# Test 6: Verify system agents excluded
curl http://127.0.0.1:8100/devx/api/coaches | grep -i "core\|ucn"
# Result: No matches (core_ai.md and ucn_rr_ai.md correctly excluded)
```

### ✅ File System Verification

```bash
# Verify created file
cat prompts/permission_coach_ai.md
# Result: "# Permission Coach v2\n\nUpdated version with backup.\n"

# Verify backup contains original
cat prompts/backups/permission_coach_20251009_114806.md
# Result: "# Permission Coach Test\n\nThis is a test prompt..."

# Verify updated list shows file as present
curl http://127.0.0.1:8100/devx/api/coaches | grep permission_coach
# Result: {"id":"permission_coach",...,"exists":true,"status":"present","size_bytes":52}
```

### ✅ CI Tests Pass

```bash
./scripts/run_tests_ci.sh
# Result: ✅ CI smoke complete
#   - Batch user ops: 2 passed
#   - Privacy API: 2 passed
#   - All health checks: green
```

## Acceptance Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Coach list shows all registry roles | ✅ | 12 coaches, including missing ones |
| Missing prompts load scaffold (200 OK) | ✅ | No 404 errors |
| Core/UCNRR excluded | ✅ | System agents not in coach list |
| Save from scaffold creates file | ✅ | New file created at prompts/{filename} |
| Save existing creates backup | ✅ | Timestamped backups in prompts/backups/ |
| CI tests pass | ✅ | All smoke tests green |

## Frontend Features

- **Status badges**: Present (green) vs Scaffold (blue)
- **Registry stats**: Shows X present, Y missing in header
- **Graceful missing file handling**: No errors, loads scaffold
- **Download button**: Export current editor content as .md
- **Button text adapts**: "Create Prompt" for new files, "Save Prompt" for existing
- **Backup notifications**: Shows backup path on successful save

## Next Steps (Optional Enhancements)

1. Add "System Prompts" section for core_ai.md and ucn_rr_ai.md
2. Add backup browser/restore functionality
3. Add diff viewer to compare current vs backup
4. Add validation for required prompt sections
5. Add preview renderer for markdown
6. Add search/filter in coach list

## Files Changed

1. `ReDNACoreDemo/devx/backend/coach_registry.py` (NEW)
2. `ReDNACoreDemo/devx/backend/coach_api.py` (REWRITTEN)
3. `ReDNACoreDemo/devx/frontend/src/routes/coach-workshop/CoachWorkshop.tsx` (UPDATED)

---

**Implementation complete and verified.** The Coach Workshop now uses a canonical registry, handles missing files gracefully with scaffolds, and excludes system agents from the coach list.
