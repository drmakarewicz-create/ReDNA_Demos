# DevX Environment Guide — Vite-Friendly Configuration

## Why `process.env` breaks in Vite

The DevX frontend is bundled with Vite, which runs in the browser and does **not** inject Node’s `process` object. Any references to `process.env` therefore resolve to `undefined`, causing white-screen renders when components rely on environment variables at runtime.

Vite exposes build-time variables via `import.meta.env`. Only variables prefixed with `VITE_` are passed through to client bundles, so every environment read must use the Vite pattern:

```ts
const apiBase = import.meta.env.VITE_DEVX_API_BASE ?? 'http://localhost:8100/devx/api'
```

## Required `.env` layout

Create `ReDNACoreDemo/devx/frontend/.env` with the following defaults (already committed):

```
VITE_DEVX_API_BASE=http://localhost:8100/devx/api
VITE_CORE_API_BASE=http://localhost:8015
```

All additional frontend variables should use the `VITE_` prefix so Vite can expose them to the bundle.

## Startup sequence

1. Start the DevX backend on port `8100`: `python -m ReDNACoreDemo.devx.backend.api`.
2. Start Core on `8015` (for Coach/Narrator APIs) if needed.
3. Launch the frontend from `ReDNACoreDemo/devx/frontend`: `npm install` (first run) then `npm run dev`.
4. Visit `http://localhost:3100` and open the 🧠 Coaches or 🤖 Agents tabs to confirm connectivity.

## Verification command

Use Vite’s built-in client heartbeat to confirm the dev server is serving assets:

```bash
curl -I "http://localhost:3100/@vite/client"
```

The response should return `200 OK` with `content-type: text/javascript`.

## Regression guard

The frontend lint script now runs `scripts/check-env.mjs`, which fails the build if any `process.env` usage is reintroduced in `src/`. A pytest (`tests/test_devx_env_integrity.py`) enforces the same guard inside CI.
