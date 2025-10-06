# Photo Refinement Coach

## PaDNA JSON Import (manual pipeline)

The Photo Refinement Coach now accepts PaDNA observation bundles that were generated offline (for example, by ChatGPT). Use the **Import JSON** card in the Photo tab to validate and ingest traits directly into Core:

1. Upload a `.json` bundle. The validator checks `user_id`, normalises observations, and reports warnings (duplicates, numeric coercions, volume > 500).
2. Review the preview table (trait path, resolved value, UCN, RR, curiosity, provenance source). Large imports (>500 traits) require an explicit confirmation checkbox.
3. Choose whether Core should recompute RR/Curiosity (`Compute RR/Curiosity` ON by default) and whether inbound RR/Curiosity values should be preserved (`Use inbound RR/Curiosity` OFF by default).
4. Click **Ingest to Core** to POST the bundle to `CORE_BASE/ingest_from_ucnrr`. The status panel shows the response payload (`changed`, `resolved_keys`, errors, etc.).

### Accepted JSON shapes

Root keys:

- `user_id` – required.
- `provenance` – optional object; merged into each observation. Runtime ingest also adds `{source:"photo-coach", from:"manual-import", ts:<iso8601>, images:[...]}`.
- `images` – optional list (`[{"id": "img2", "filename": "LLTEST2.jpg"}, ...]`) used to harvest photo filenames.
- `observations` – either:
  - **Flat map**: `{ "PaDNA.Trait.Path": {"resolved_value": ..., "ucn": ..., ...}, ... }`
  - **Image-grouped**: `{ "img-id": { "PaDNA.Trait.Path": {...}, ... }, ... }`

Trait objects must include `resolved_value`. Optional fields: `ucn` (0–1000 float), `reasons`/`flags` (list), `status` (string), `notes` (object), `provenance` (object), `rr`, `curiosity`. Scalars are auto-wrapped as `{ "resolved_value": <value>, "ucn": 80.0 }`.

Warning thresholds:

- More than 500 traits trigger a confirmation checkbox.
- Duplicate trait paths keep the last occurrence but surface a warning.
- Non-numeric `ucn`/`rr`/`curiosity` values are dropped with a warning.

### Sample bundle

`examples/padna_import_example.json` contains a ready-to-ingest PaDNA bundle used by the acceptance checks:

```bash
CORE=http://127.0.0.1:8015
curl -s -X POST "$CORE/ingest_from_ucnrr" \
  -H "content-type: application/json" \
  -d @PhotoRefinementCoach/examples/padna_import_example.json | jq
```
