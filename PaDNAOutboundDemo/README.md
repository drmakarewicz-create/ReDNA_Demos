# PaDNA Outbound Renderer

This demo renders Streamlit previews and an API for PaDNA avatars. Key pieces:

- `src/vision/renderer_mappings.py` – maps resolved PaDNA traits (Canonical keys + synonyms) into palette and feature toggles.
- `src/vision/renderer_v2.py` – builds the SVG, applying theme/feature toggles and returning debug info.
- `app.py` – Streamlit front end with theme/palette overrides and debug view.
- `tools/render_smoke.py` – smoke harness that renders sample avatars to `_smoke_outputs/` for quick visual QA.

Run smoke test:

```bash
python -m PaDNAOutboundDemo.tools.render_smoke
```

Run palette mapping unit tests:

```bash
pytest PaDNAOutboundDemo/tests/test_palette_mapping.py
```
