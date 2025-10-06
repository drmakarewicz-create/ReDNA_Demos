# Relationship Synergy Coach MVP

The transactional Relationship Synergy Coach (RSC) supports short-term collaboration between two users with consent-first controls.

## Session lifecycle

1. **Create** – call `create_transaction_rsc(creator_id, partner_id, scope, expires_at, honesty_ceiling, shared_context)`.
   - Returns `session_id` and `consent_token`.
   - Shared context is automatically sanitised (replace `__PARTNER_NAME__` with `[partner]`).
2. **Accept** – invited partner calls `accept_rsc(session_id, partner_id, consent_token)`.
3. **Interact** – both parties post micro-actions via `post_micro_action(session_id, author_id, action, honesty_level=...)`.
   - Honesty level may not exceed the session ceiling.
   - Every action is logged with provenance.
4. **Expire/Revocation** – sessions auto-expire after `expires_at` or immediately via `expire_session(session_id)`.
   - Either participant may revoke with `revoke_session(session_id, actor_id, reason)`.

## Storage model

Sessions persist in JSON under `ReDNACoreDemo/data/rsc_sessions/*.json`:

```json
{
  "session_id": "7d5c2a8f",
  "creator_id": "alpha",
  "partner_id": "beta",
  "scope": "trust_building",
  "honesty_ceiling": "balanced",
  "created_at": "2024-09-22T10:15:04.512Z",
  "expires_at": "2024-09-22T13:15:04.512Z",
  "consent_token": "HxQz-42YWzw7",
  "accepted": true,
  "log": [
    {"ts": "2024-09-22T10:32:00.001Z", "author_id": "alpha", "payload": {"type": "prompt", "text": "Ask for their daily highlight."}}
  ],
  "revocations": []
}
```

Utility helpers:

- `session_snapshot(session_id, viewer_id=None)` – returns current state with `expired` flag.
- `shared_feed(session_id)` – ordered list of micro-action entries.
- `list_sessions()` – diagnostic helper for dev tooling.

## Consent safeguards

- Sessions require explicit partner ID and consent token acceptance.
- Revocations append to the audit log and block further actions.
- Expired sessions reject writes; clients should handle `RscSessionError`.
- Honesty guard enforces the stricter honesty mode selected during creation.

## Dev tab workflow

1. Set `PERSONA_DEV_TABS=true` while running Explorer.
2. Use **RSC Dev** to create sessions, accept with the token, and push micro-actions.
3. Inspect masked shared context and log output for accuracy.
4. Validate expiry and revocation flows before promoting to production personas.

## Next steps

- Wire the Head Coach to downgrade honesty if either persona lowers their ceiling mid-session.
- Introduce expiring masked contact handles once transport layer is ready.
- Layer in provider alerts when revocations cite policy-sensitive reasons.
