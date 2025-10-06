# ReDNA Agent Documentation Protocol

**Applies to:** Codex, Claude Code, and any other code-gen agent.

## 0) Always read this first
- Locate and respect this file: `docs/AGENT_PROTOCOL.md`
- Acknowledge in your first reply:
  `ACK: following docs/AGENT_PROTOCOL.md @ <UTC timestamp or commit>`

## 1) Where to log changes
- Append one JSON line per batch to: `docs/automation_log/changes.jsonl`
- Optionally write a short human summary: `docs/automation_log/latest.md`

## 2) Required JSON schema (per batch)
Each line in `changes.jsonl` must be valid JSON with the following keys:
```json
{
  "ts": "2025-10-02T14:25:41Z",
  "agent": "codex|claude-code|other",
  "batch_id": "unique-id-or-title",
  "summary": "One sentence summary of changes.",
  "files_changed": ["path/to/file1", "path/to/file2"],
  "lines_added": 12,
  "lines_removed": 3,
  "breaking_changes": false,
  "followups": ["short follow-up todo 1", "todo 2"]
}
```

## 3) Required “Change Summary” block in agent replies

Every coding batch reply must include:
- Batch Title
- Agent (codex/claude-code/etc.)
- Timestamp (UTC)
- Files Modified
- Diff highlights (not the full diff)
- Manual steps (if any)
- Acceptance checks
- Rollback plan
- Inline JSON object appended to changes.jsonl

## 4) Guardrails
- Never overwrite changes.jsonl — only append.
- If superseding a batch, add a new line referencing "supersedes_batch_id".
- If editing .env, include masked keys and a one-liner on how to apply/restart.
- If you skip logging, your batch is incomplete.

## 5) Where to look (for agents)
- Protocol: docs/AGENT_PROTOCOL.md
- Change log: docs/automation_log/changes.jsonl
- Last human summary (optional): docs/automation_log/latest.md
- Environment: .cpplusplus_env.json and .env (mask in replies)
