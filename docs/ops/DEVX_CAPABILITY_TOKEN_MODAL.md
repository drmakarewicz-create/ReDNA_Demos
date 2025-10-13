# DevX Capability Token Modal

## Purpose

Admins can now mint short-lived capability tokens directly from **DevX → User Ops → Head Coach**. This removes the need to open the Core API UI when Quick Capture or other Life OS actions require elevated capabilities.

## Prerequisites

1. Launch DevX with the feature flag enabled:
   - Set `VITE_DEVX_SHOW_CAP_MODAL=true` in `ReDNACoreDemo/devx/frontend/.env.local` (or equivalent).
2. Provide an **admin bearer token** for the `/devx/api/capability/issue` endpoint:
   - Preferred: add `VITE_DEVX_ADMIN_TOKEN=` to `.env.local`.
   - Alternative: store it at runtime with `localStorage.setItem('DEVX_ADMIN_TOKEN', '<token>')` in the browser console.

If neither variable is set, the modal raises `Admin token missing…`.

## How to Generate a Token

1. Navigate to `http://localhost:3100/user-ops/<USER_ID>/hc`.
2. In the **Life OS** card, click **Generate Capability Token** (button only appears when the feature flag is true).
3. Complete the form:
   - **Scope** (pre-populated options such as `core.agent.config` and `core.agent.run`).
   - **TTL (minutes)** between 5 and 240 (default 30).
   - **Reason** (default: “DevX Life OS quick capture”).
4. Submit. On success the modal shows:
   - Capability ID (short form).
   - Expiration time with a live countdown.
   - Masked token with a **Copy** button (clipboard contains the full token; UI never displays it in full).

Paste the copied token into the Life OS Quick Capture request header (`X-Capability`) or any client that needs temporary access.

## Smoke Test

1. `npm run dev` inside `ReDNACoreDemo/devx/frontend`.
2. In a browser, load `http://localhost:3100/user-ops/USER1/hc`.
3. Generate a token and copy it.
4. Trigger a Life OS action (e.g., Quick Capture). The request should succeed with the freshly issued token.

## Security Notes

- The modal is **feature-flagged and dev-only**; do not enable the flag in production builds.
- Tokens are short-lived; default TTL is 30 minutes and capped at 4 hours.
- The React code never logs tokens to the console. Only the masked value is shown in the UI.
- `.env` remains ignored—admin secrets live in local `.env.local` or runtime localStorage.
