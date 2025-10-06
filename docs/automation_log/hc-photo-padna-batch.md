# Photo Coach + PaDNA Delta Loop Integration

**Date:** 2025-10-04
**Status:** ✅ Complete
**Sprint:** Photo Coach MVP

## Overview

This batch implementation adds Photo Coach ingestion pipeline and PaDNA Coach delta-loop wiring to enable:
- Photo upload, thumbnail generation, and manifest creation
- Render manifest tracking for PaDNA outputs
- Delta analysis between photo batches and render batches
- Automated task enqueueing based on photo-render gaps
- Complete file-backed storage under `data/users/<USER_ID>/`

## Directory Structure

```
data/users/<USER_ID>/
├── media/
│   ├── images/<batch_id>/         # Original uploaded photos
│   ├── thumbs/<batch_id>/         # Thumbnails (512x512 max)
│   └── manifests/<batch_id>.json  # Photo batch manifests
├── renders/<render_id>/
│   ├── render.png                 # Primary render output
│   ├── comp_side_by_side.png      # Comparison image
│   └── render_manifest.json       # Render manifest
└── hc/
    ├── journal/<date>.md          # Daily journal with automation events
    └── state/resolved.json        # Resolved PaDNA state
```

## Photo Batch Manifest Schema

See [schemas/photo_manifest.schema.json](../../ReDNACoreDemo/schemas/photo_manifest.schema.json)

**Example:**
```json
{
  "user_id": "alice",
  "batch_id": "alice_20251004_143022_abc123",
  "created_at": "2025-10-04T14:30:22.123456Z",
  "count": 2,
  "images": [
    {
      "filename": "portrait.jpg",
      "path": "media/images/alice_20251004_143022_abc123/portrait.jpg",
      "thumb": "media/thumbs/alice_20251004_143022_abc123/portrait.jpg",
      "hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "width": 1920,
      "height": 1080,
      "size_bytes": 245678,
      "exif": {
        "DateTime": "2025:10:04 14:30:22",
        "Make": "Apple",
        "Model": "iPhone 14"
      },
      "labels": ["portrait", "face", "freckles?", "skin_tone:fair"],
      "notes": ""
    }
  ]
}
```

## Render Batch Manifest Schema

See [schemas/render_manifest.schema.json](../../ReDNACoreDemo/schemas/render_manifest.schema.json)

**Example:**
```json
{
  "user_id": "alice",
  "render_batch_id": "alice_20251004_150000_def456",
  "created_at": "2025-10-04T15:00:00.123456Z",
  "inputs": {
    "traits_resolved_path": "users/alice/hc/state/resolved.json",
    "images_batch_id": "alice_20251004_143022_abc123",
    "workflow": "comfyui/realvisxl.json",
    "seed": 12345,
    "prompt": "portrait of a woman with fair skin and freckles"
  },
  "outputs": {
    "render": "renders/alice_20251004_150000_def456/render.png",
    "side_by_side": "renders/alice_20251004_150000_def456/comp_side_by_side.png"
  }
}
```

## API Endpoints

### Photo Coach Endpoints

#### `POST /photo/ingest`
Upload batch of photos, create thumbnails, generate manifest.

**Query Parameters:**
- `user_id` (required): User identifier
- `batch_id` (optional): Custom batch ID (auto-generated if not provided)

**Request Body:**
- `files` (multipart/form-data): One or more image files

**Response:**
```json
{
  "user_id": "alice",
  "batch_id": "alice_20251004_143022_abc123",
  "created_at": "2025-10-04T14:30:22.123456Z",
  "count": 2,
  "images": [...]
}
```

**Status Codes:**
- 200: Success
- 400: Invalid files or parameters
- 500: Server error

---

#### `GET /photo/batches`
List all photo batches for a user (sorted by created_at desc).

**Query Parameters:**
- `user_id` (required): User identifier

**Response:**
```json
{
  "user_id": "alice",
  "batches": [
    {
      "batch_id": "alice_20251004_143022_abc123",
      "created_at": "2025-10-04T14:30:22.123456Z",
      "count": 2
    }
  ]
}
```

---

#### `GET /photo/batch`
Get full manifest for a specific batch.

**Query Parameters:**
- `user_id` (required): User identifier
- `batch_id` (required): Batch identifier

**Response:**
Full photo batch manifest (see schema above)

**Status Codes:**
- 200: Success
- 404: Batch not found

---

#### `POST /photo/vision/label`
Add vision labels to photos (stub implementation until vision LLM integrated).

**Query Parameters:**
- `user_id` (required): User identifier
- `batch_id` (required): Batch identifier
- `image` (optional): Specific image filename (labels all if not provided)

**Response:**
```json
{
  "batch_id": "alice_20251004_143022_abc123",
  "updated_images": 2,
  "labels_added": ["portrait", "face", "freckles?", "skin_tone:fair"]
}
```

**Mock Labels:**
- portrait
- face
- freckles?
- skin_tone:fair
- (More to be added when vision LLM is integrated)

---

### HC Integration Updates

#### `GET /hc/state` (Extended)
Now includes media and render stats when `enable_photo_coach: true`:

```json
{
  "user_id": "alice",
  "traits": {...},
  "media": {
    "batches": 3,
    "latest_batch_id": "alice_20251004_143022_abc123"
  },
  "renders": {
    "batches": 2,
    "latest_render_id": "alice_20251004_150000_def456"
  }
}
```

---

#### `POST /hc/playbooks/run` (Extended)
Implements `photo_refine` playbook logic:

**Query Parameters:**
- `user_id` (required): User identifier
- `playbook_id` (required): Must be "photo_refine"

**Behavior:**
1. Gets latest photo batch and latest render batch
2. Runs delta analysis comparing photo labels to render traits
3. Enqueues tasks for gaps (priority ≥ 3):
   - `add_evidence` - Add missing trait evidence
   - `verify_evidence` - Verify existing trait evidence
   - `re_render` - Regenerate render with updated traits
4. All tasks include provenance metadata:
   ```json
   {
     "source": "playbook",
     "playbook_id": "photo_refine",
     "reason": "Freckles detected in photos but may not be in resolved state"
   }
   ```

**Response:**
```json
{
  "user_id": "alice",
  "playbook_id": "photo_refine",
  "message": "photo_refine executed successfully",
  "tasks_enqueued": 3
}
```

---

## Delta Analysis Heuristics

The `analyze_photo_render_delta` function performs heuristic analysis to detect gaps:

**Freckles Detection:**
- **Labels:** `freckles?`, `freckles`
- **Recommendation:** Add evidence for `PaDNA.SkinDNA.Freckles.Density`
- **Priority:** 5

**Skin Tone Detection:**
- **Labels:** Any label containing `skin_tone`
- **Recommendation:** Verify evidence for `PaDNA.SkinDNA.SkinTone.Base`
- **Priority:** 4

**Face/Portrait Detection:**
- **Labels:** `face`, `portrait`
- **Recommendation:** Add evidence for `PaDNA.FacialDNA.FaceShape.Overall`
- **Priority:** 3

**Output:**
```json
{
  "photo_batch_id": "alice_20251004_143022_abc123",
  "render_batch_id": "alice_20251004_150000_def456",
  "photo_labels": ["portrait", "face", "freckles?", "skin_tone:fair"],
  "recommendations": [
    {
      "trait": "PaDNA.SkinDNA.Freckles.Density",
      "action": "add_evidence",
      "reason": "Freckles detected in photos but may not be in resolved state",
      "priority": 5
    }
  ],
  "delta_count": 3
}
```

---

## Next.js API Proxies

All proxies follow the pattern: `web/src/app/api/hc/photo/*`

1. **`/api/hc/photo/ingest`** - POST multipart/form-data proxy
2. **`/api/hc/photo/batches`** - GET batches list proxy
3. **`/api/hc/photo/batch`** - GET single batch proxy
4. **`/api/hc/photo/vision_label`** - POST vision label proxy

All proxies:
- Accept camelCase query params (`userId`, `batchId`)
- Convert to snake_case for Core API (`user_id`, `batch_id`)
- Forward requests to `CORE_API_URL` (default: http://localhost:8001)
- Handle errors and return appropriate status codes

---

## Feature Flags

Added to `ReDNACoreDemo/config/hc_flags.yaml`:

```yaml
# Photo Coach - Image ingestion and analysis
enable_photo_coach: true

# Photo Vision Stub - Mock vision labeling (until vision LLM integrated)
enable_photo_vision_stub: true
```

---

## Acceptance Tests

### Test Suite 1: `test_photo_coach_acceptance.py`

1. **test_ingest_creates_manifest_and_thumbs**
   - Uploads 2 test images (red, green)
   - Verifies manifest structure (user_id, batch_id, count, images[])
   - Verifies original files exist at correct paths
   - Verifies thumbnails exist and are ≤512x512
   - Verifies SHA-256 hashes

2. **test_list_batches_returns_latest_first**
   - Creates 2 batches with time delay
   - Verifies descending sort order by created_at

3. **test_get_batch_returns_manifest**
   - Uploads single image
   - Retrieves via `/photo/batch`
   - Verifies full manifest with metadata

4. **test_vision_stub_adds_labels**
   - Uploads image
   - Calls `/photo/vision/label`
   - Verifies mock labels added to manifest

### Test Suite 2: `test_padna_delta_wiring.py`

1. **test_photo_refine_playbook_enqueues_tasks**
   - Creates photo batch with labels
   - Creates render batch manifest
   - Runs `photo_refine` playbook
   - Verifies ≥1 task enqueued (add_evidence, verify_evidence, re_render)

2. **test_tasks_have_provenance**
   - Creates photo and render batches
   - Runs `photo_refine` playbook
   - Verifies all tasks have provenance with:
     - `source: "playbook"`
     - `playbook_id: "photo_refine"`
     - `reason: "..."`

3. **test_tick_executes_re_render_stub**
   - Creates photo and render batches
   - Runs `photo_refine` playbook
   - Executes `/hc/tasks/tick`
   - Verifies task status changes
   - Verifies journal entry appended

---

## Runbook

### Prerequisites
- Core API running on port 8001
- Python 3.10+ with dependencies installed
- `enable_photo_coach: true` in hc_flags.yaml

### 1. Start Core API

```bash
cd /path/to/ReDNA_Demos
source .venv/bin/activate
uvicorn ReDNACoreDemo.core.api:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Ingest Photo Batch

```bash
# Upload single photo
curl -X POST "http://localhost:8001/photo/ingest?user_id=alice" \
  -F "files=@/path/to/portrait.jpg"

# Upload multiple photos
curl -X POST "http://localhost:8001/photo/ingest?user_id=alice" \
  -F "files=@/path/to/photo1.jpg" \
  -F "files=@/path/to/photo2.jpg" \
  -F "files=@/path/to/photo3.jpg"

# With custom batch ID
curl -X POST "http://localhost:8001/photo/ingest?user_id=alice&batch_id=custom_batch_001" \
  -F "files=@/path/to/portrait.jpg"
```

**Response:**
```json
{
  "user_id": "alice",
  "batch_id": "alice_20251004_143022_abc123",
  "created_at": "2025-10-04T14:30:22.123456Z",
  "count": 1,
  "images": [...]
}
```

### 3. List Photo Batches

```bash
curl "http://localhost:8001/photo/batches?user_id=alice"
```

**Response:**
```json
{
  "user_id": "alice",
  "batches": [
    {
      "batch_id": "alice_20251004_143022_abc123",
      "created_at": "2025-10-04T14:30:22.123456Z",
      "count": 3
    }
  ]
}
```

### 4. Get Specific Batch

```bash
curl "http://localhost:8001/photo/batch?user_id=alice&batch_id=alice_20251004_143022_abc123"
```

### 5. Add Vision Labels (Stub)

```bash
# Label all images in batch
curl -X POST "http://localhost:8001/photo/vision/label?user_id=alice&batch_id=alice_20251004_143022_abc123"

# Label specific image
curl -X POST "http://localhost:8001/photo/vision/label?user_id=alice&batch_id=alice_20251004_143022_abc123&image=portrait.jpg"
```

**Response:**
```json
{
  "batch_id": "alice_20251004_143022_abc123",
  "updated_images": 3,
  "labels_added": ["portrait", "face", "freckles?", "skin_tone:fair"]
}
```

### 6. Run Photo Refine Playbook

```bash
curl -X POST "http://localhost:8001/hc/playbooks/run?user_id=alice&playbook_id=photo_refine"
```

**Response:**
```json
{
  "user_id": "alice",
  "playbook_id": "photo_refine",
  "message": "photo_refine executed successfully",
  "tasks_enqueued": 3
}
```

### 7. List Tasks

```bash
curl "http://localhost:8001/hc/tasks/list?user_id=alice"
```

**Response:**
```json
{
  "user_id": "alice",
  "tasks": [
    {
      "task_id": "task_20251004_150500_xyz",
      "title": "add_evidence: Freckles",
      "action": "add_evidence",
      "status": "pending",
      "provenance": {
        "source": "playbook",
        "playbook_id": "photo_refine",
        "reason": "Freckles detected in photos but may not be in resolved state"
      }
    }
  ]
}
```

### 8. Execute Task Tick

```bash
curl -X POST "http://localhost:8001/hc/tasks/tick?user_id=alice"
```

**Response:**
```json
{
  "task_id": "task_20251004_150500_xyz",
  "action": "add_evidence",
  "status": "completed"
}
```

### 9. Check HC State (with Media Stats)

```bash
curl "http://localhost:8001/hc/state?user_id=alice"
```

**Response:**
```json
{
  "user_id": "alice",
  "traits": {...},
  "media": {
    "batches": 3,
    "latest_batch_id": "alice_20251004_143022_abc123"
  },
  "renders": {
    "batches": 2,
    "latest_render_id": "alice_20251004_150000_def456"
  }
}
```

### 10. Run Acceptance Tests

```bash
# Test Photo Coach
pytest test_photo_coach_acceptance.py -v -s

# Test PaDNA Delta Wiring
pytest test_padna_delta_wiring.py -v -s

# Run all tests
pytest test_photo_coach_acceptance.py test_padna_delta_wiring.py -v -s
```

---

## Implementation Notes

### Core Modules

**`ReDNACoreDemo/core/photo_coach.py`:**
- `ingest_photo_batch()` - Main ingestion function
- `create_thumbnail()` - PIL-based thumbnail generation (THUMB_SIZE = 512x512)
- `compute_sha256()` - File hashing for deduplication
- `extract_exif()` - EXIF metadata extraction
- `add_vision_labels_stub()` - Mock vision labeling
- `list_photo_batches()`, `get_photo_batch()` - Batch retrieval
- `get_media_stats()` - Summary statistics

**`ReDNACoreDemo/core/render_coach.py`:**
- `create_render_manifest()` - Render manifest creation
- `list_render_batches()`, `get_render_batch()` - Render retrieval
- `analyze_photo_render_delta()` - Heuristic delta analysis
- `get_render_stats()` - Summary statistics

### Ground Rules Followed

✅ **Additive Only:** No breaking changes to v1 APIs
✅ **File-Backed:** All data persists to `data/users/` directory
✅ **Mock-Friendly:** Vision labels use stub until vision LLM ready
✅ **Existing Patterns:** Follows TaskRunner, Playbook, and Journal patterns
✅ **Schema Validation:** JSON schemas provided for manifests

---

## Acceptance Criteria

✅ 1. POST /photo/ingest creates manifest, saves originals, creates thumbnails
✅ 2. GET /photo/batches returns sorted list (desc)
✅ 3. GET /photo/batch returns full manifest
✅ 4. POST /photo/vision/label adds mock labels
✅ 5. photo_refine playbook enqueues ≥1 task when delta exists
✅ 6. Tasks have provenance (source=playbook, playbook_id=photo_refine)
✅ 7. Task tick executes and appends journal
✅ 8. Next.js proxies forward requests correctly
✅ 9. Acceptance tests pass

---

## Future Enhancements

**Sprint 2b: Vision LLM Integration**
- Replace `add_vision_labels_stub()` with real vision LLM calls
- Enhanced label taxonomy (age, emotion, clothing, lighting, etc.)
- Confidence scores for labels

**Sprint 3: Per-Image Notes**
- `POST /photo/note` endpoint to update individual image notes
- Frontend UI for annotation

**Sprint 4: Side-by-Side Comparisons**
- Generate comparison images (photo vs render)
- Visual diff highlighting

**Sprint 5: Batch Operations**
- Delete batch
- Merge batches
- Export batch as ZIP

---

## Related Documentation

- [Photo Manifest Schema](../../ReDNACoreDemo/schemas/photo_manifest.schema.json)
- [Render Manifest Schema](../../ReDNACoreDemo/schemas/render_manifest.schema.json)
- [Playbook: photo_refine](../../ReDNACoreDemo/config/playbooks/photo_refine.json)
- [Feature Flags](../../ReDNACoreDemo/config/hc_flags.yaml)

---

**Last Updated:** 2025-10-04
**Author:** Claude (Automated Implementation)
**Review Status:** Pending
