# Core UI Endpoints

The Head Coach React shell and Control Panel++ talk to the Core FastAPI app exclusively through
`/ui/*` endpoints. This reference summarises the most frequently used routes with payload templates
and validation logic.

All endpoints are unauthenticated in the demo environment. JSON responses set `Content-Type:
application/json` unless noted otherwise.

## User catalogue

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/ui/users` | Returns `{ users: [...] }` entries derived from the current workspace root. |
| `POST` | `/ui/user/create` | Creates a new user scaffold. Payload must include a `user_id` matching the regex `[a-z0-9][a-z0-9_-]{2,63}`. |

Creating a user automatically seeds disk folders under `data/users/<id>/` and `data/checkpoints/<id>/`.

## Draft Chat

```
GET /ui/draft_chat?user_id=TEST&limit=25&since=2024-09-01T00:00:00Z
```

- `user_id` is required; `limit` (1–500) and `since` (ISO-8601) are optional.
- Returns `{ "user_id": "TEST", "items": [...] }` where each item contains:
  - `id` – unique draft identifier
  - `ts` – ISO timestamp (falls back to file metadata if missing)
  - `title` – optional title/summary
  - `content` – Markdown-rendered text
  - `source_path` – full path to the draft JSON file relative to the workspace

Drafts are loaded from `data/users/<id>/drafts/` or checkpoint mirrors.

## Media library & hygiene

### Upload

```
POST /ui/media/upload
Content-Type: multipart/form-data
  user_id=TEST
  file=@sample.png
  label=Optional label
```

- Allowed extensions: `.jpg`, `.png`, `.json`
- Size limit: `MEDIA_MAX_MB` (default 20 MB)
- MIME sniffing must match the extension; mismatches return `415`
- Filenames are slugified; the original name is preserved in metadata under `source_name`
- Violations (size, MIME, extension) log to `data/_stats/uploads.log` as JSONL

Success response:

```json
{
  "ok": true,
  "media": {
    "id": "media-new",
    "filename": "media-new_sample.jpg",
    "original_name": "sample.jpg",
    "content_type": "image/jpeg",
    "size": 12345,
    "uploaded_ts": "2024-09-01T12:00:00Z",
    "download_url": "/ui/media/download/TEST/media-new"
  }
}
```

### List & delete

- `GET /ui/media/list?user_id=TEST` → `{ "user_id": "TEST", "items": [...] }`
- `DELETE /ui/media/delete?user_id=TEST&media_id=media-new`
  - Returns `{ "ok": true, "removed": true, "media_id": "media-new" }`
  - Missing IDs yield `404 MEDIA_NOT_FOUND`

### Download

`GET /ui/media/download/<user>/<media_id>` streams the stored file with the recorded
`content_type`. Missing IDs return standard `404` errors.

## Photo render jobs

### Create job

```
POST /ui/photo/render
Content-Type: application/json
{
  "user_id": "TEST",
  "media_id": "media-new",
  "params": { "mode": "preview" }
}
```

Response:

```json
{
  "ok": true,
  "job_id": "16f4b3...",
  "job": {
    "id": "16f4b3...",
    "user_id": "TEST",
    "media_id": "media-new",
    "state": "queued",
    "progress": 0.0,
    "created_at": "2024-09-01T12:00:00.000Z",
    "updated_at": "2024-09-01T12:00:00.000Z",
    "status_url": "/ui/photo/status?job_id=16f4b3...",
    "result_url": "/ui/photo/result?job_id=16f4b3...",
    "params": { "mode": "preview" }
  }
}
```

- Jobs are stored under `data/users/<id>/renders/<job_id>/`.
- If the referenced media is missing, the endpoint returns `404 MEDIA_NOT_FOUND`.

### Poll job status

`GET /ui/photo/status?job_id=<id>&user_id=TEST`

Returns `{ "ok": true, "user_id": "TEST", "job": { ... } }` with `state` transitioning through
`queued → running → done/error`. The worker stub copies the source file into the render directory
and simulates progress.

### List recent jobs

`GET /ui/photo/jobs?user_id=TEST&limit=20` → `{ "user_id": "TEST", "items": [...] }` sorted by
`created_at` descending.

### Fetch result

`GET /ui/photo/result?job_id=<id>` streams the generated file. If no artifact exists, a placeholder
PNG (1×1) is returned with header `x-placeholder: 1`.

## Draft endpoints summary

| Endpoint | Notes |
| --- | --- |
| `POST /ui/draft_chat` | *Not implemented; Draft Chat is read-only via GET.* |
| `GET /ui/draft_chat` | See section above |

## Miscellaneous UI helpers

- `GET /ui/users` – list user summaries (id, label, timestamps).
- `POST /ui/user/create` – create empty user skeletons (optionally provide `label`).
- `GET /ui/observations/aggregates` – aggregate snapshot powering the persona overview cards.
- `POST /ui/asks/add_demo` and `POST /ui/asks/act` – seed demo planner asks and approve them from
  the Head Coach toolbar.

## Error handling

All `/ui/*` endpoints return structured JSON errors:

```json
{
  "error": "MEDIA_TOO_LARGE",
  "message": "File exceeds the 20 MB upload limit."
}
```

Common HTTP statuses:

- `400 BAD_REQUEST` – missing required fields or invalid timestamps
- `404` – missing user/media/job resource
- `413` – upload over size budget
- `415` – unsupported file extension or MIME mismatch
- `500` – unexpected storage errors

Use these codes for optimistic UI updates or retry prompts within the React shell and CP++.
