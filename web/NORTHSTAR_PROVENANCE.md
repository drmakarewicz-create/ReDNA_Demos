# Northstar Provenance Viewer

## Overview

The Provenance Viewer provides complete transparency into how every trait in Northstar is determined, scored, and updated. Users can click "Why?" on any trait to see the full evidence chain, inference rules, UCN scoring, and resolver traces.

## Features

### 1. Complete Evidence Timeline

Shows all observations that contributed to a trait's current value:
- Source (chat, onboarding, goal, etc.)
- Timestamp
- Value
- UCN prior (confidence seed)
- Request ID (for tracing)

### 2. Inference Visibility

Displays all rule-based inferences:
- Inferred value
- Rule ID (provenance)
- Prior UCN
- UI hidden flag

### 3. RR Scoring Status

Shows whether RR (Relational Reasoning) service is:
- **Online**: Live model scoring UCN
- **Offline**: Using fallback priors
- **Unknown**: Status undetermined

### 4. Resolver Traces (Dev Mode)

For developers, shows:
- Request IDs
- Trace file references
- RR success/error status
- Step-by-step resolution log

### 5. Raw JSON View

Toggle to see complete provenance data structure for debugging.

---

## User Actions

### Confirm / Correct

Clicking this button prefills the chat composer with:
```
Confirm: my [trait] is [value]
```

This allows users to:
- Confirm an inferred trait (upgrades to "resolved" status)
- Correct an incorrect value
- Provide explicit confirmation for low-UCN traits

The message flows through the canonical ingestion → resolver pipeline, updating UCN and status.

### Ask Follow-up

Clicking this button prefills the chat composer with:
```
Why did you infer [trait] as [value]?
```
or
```
Tell me more about my [trait]
```

This lets users:
- Understand inference reasoning
- Get more context about their data
- Engage in natural conversation about their traits

---

## How Provenance Data is Collected

### 1. Evidence Collection

Every observation is stored with:
- **trait_id**: Canonical ID (e.g., "PaDNA.EyeDNA.IrisColor")
- **value**: Structured value (enum/number/text)
- **source**: Origin (chat, onboarding, etc.)
- **ts**: ISO8601 timestamp
- **provenance**: Optional inference rule ID
- **ucn_prior**: Confidence seed

Evidence is stored in:
- `users/<id>/evidence.json` (single file)
- `users/<id>/evidence/*.json` (directory of files)

### 2. Resolution Process

When evidence is ingested:
1. **Canonicalization**: Legacy trait IDs → canonical IDs
2. **Schema Validation**: Normalize value format
3. **Grouping**: Group evidence by trait_id
4. **Selection**: Choose winning value (latest-strongest)
5. **UCN Scoring**: Call RR service or use fallback
6. **Persistence**: Write to `resolved.json`
7. **Tracing**: Log resolution steps

### 3. Resolver Traces

Each resolution creates a trace file:
- **Location**: `users/<id>/resolver_traces/<req_id>.json`
- **Contents**: Step-by-step log of resolution process
- **Steps**: evidence_in, grouped, chosen, rr_input, ucn_scores, resolved_out

The provenance viewer scans recent traces to show which requests touched a given trait.

### 4. Inference Engine

Declarative rules generate inferred traits:
- **Input**: Canonical evidence
- **Process**: Pattern matching + rule application
- **Output**: New evidence with `provenance: "inference:<rule_id>"`
- **Filtering**: Only accepted if existing UCN < 0.3

Inferences are clearly marked and never overwrite confirmed values.

---

## RR Status Meanings

### Online
- RR service is responding
- UCN scores are from live model
- Highest confidence
- Normal operation

### Offline (using priors)
- RR service unavailable (timeout, connection error, etc.)
- UCN falls back to trait ontology priors
- Still functional, reduced confidence
- Expected during local development when RR not running

### Unknown
- No recent resolver traces found
- Status cannot be determined
- Trait may be very old or from legacy data

---

## Dev Mode Features

When accessing Northstar from localhost or 127.0.0.1, additional developer features are enabled:

### Resolver Traces Section
- Shows last 10 trace files that touched this trait
- Displays request IDs for correlation
- Shows RR status per request
- Links to trace filenames (not full paths - no secrets)

### Use Cases
- Debugging resolver behavior
- Investigating UCN calculation
- Tracing evidence flow
- Correlating with server logs

---

## Privacy & Security

### No Secrets in Logs
- Full file paths are never exposed in UI
- Only filenames are shown
- Request IDs are sanitized
- No API keys or tokens in traces

### Dev Mode Gating
- Trace file paths only shown on localhost
- Production builds hide internal details
- User data never leaves their session

### Data Provenance
- All evidence tagged with source
- Timestamps preserved
- Inference rules identified
- Chain of custody maintained

---

## Example Workflow

### Scenario: User says "I have blue eyes"

1. **Evidence Created**
   ```json
   {
     "trait_id": "PaDNA.EyeDNA.IrisColor",
     "value": {"enum": "blue"},
     "source": "chat",
     "ts": "2025-10-14T03:45:00Z",
     "ucn_prior": 0.25
   }
   ```

2. **Resolver Processes**
   - Groups evidence by trait_id
   - Selects "blue" as winning value
   - Scores UCN via RR (or fallback to 0.25)
   - Writes to resolved.json

3. **User Clicks "Why?"**
   - Drawer opens
   - Shows current: "blue · UCN 0.25 · resolved"
   - Evidence timeline: 1 item from "chat"
   - RR status: "Offline (using priors)"
   - Raw JSON available

4. **User Clicks "Confirm"**
   - Composer prefills: "Confirm: my IrisColor is blue"
   - User sends message
   - Pipeline re-resolves
   - UCN may increase
   - Status remains "resolved"

5. **Updated Provenance**
   - Now shows 2 evidence items
   - Latest from confirmation
   - UCN possibly higher
   - All history preserved

---

## Troubleshooting

### "Error: Provenance fetch failed"
- Check that Core service is running
- Verify user_id is valid
- Check browser console for details

### "No direct evidence logged"
- Trait may be from legacy data
- Evidence files may be in different location
- Check `users/<id>/evidence.json` exists

### "RR status: Unknown"
- No recent resolver traces
- Trait may be very old
- Try updating trait to generate new trace

### "Traces (dev)" section not showing
- Only visible on localhost/127.0.0.1
- Check `devMode` prop is true
- Verify hostname detection logic

---

## API Reference

### GET /core/api/user/{user_id}/provenance/{trait_id}

**Response:**
```json
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "resolved": {
    "value": {"enum": "blue"},
    "ucn": 0.25,
    "status": "resolved",
    "last_updated": "2025-10-14T03:45:00Z",
    "sources": ["chat"]
  },
  "direct_evidence": [
    {
      "source": "chat",
      "ts": "2025-10-14T03:45:00Z",
      "value": {"enum": "blue"},
      "ucn_prior": 0.25,
      "provenance": "direct"
    }
  ],
  "inferences": [],
  "traces": [
    {
      "req_id": "a1b2c3d4",
      "file": "fixture-a1b2c3d4.json",
      "rr_ok": false
    }
  ],
  "rr_status": "offline"
}
```

---

## Future Enhancements

### Planned Features
1. **Conflict Resolution UI**: Show when values conflict and how resolver chose
2. **Confidence Intervals**: Visualize UCN uncertainty ranges
3. **Source Filtering**: Filter evidence by source type
4. **Time Travel**: View trait state at historical timestamps
5. **Comparison Mode**: Compare two traits' provenance side-by-side
6. **Export**: Download provenance as PDF or JSON

### Under Consideration
- Evidence graph visualization
- Inference rule explanations in plain English
- Batch provenance for multiple traits
- Provenance search across all traits
- Integration with governance/audit logs

---

## Summary

The Northstar Provenance Viewer provides **complete explainability** for every trait:
- ✅ Full evidence timeline
- ✅ Inference visibility
- ✅ UCN scoring transparency
- ✅ Resolver trace references
- ✅ Actionable user controls
- ✅ Privacy-preserving design

Users can always answer: "Why does Northstar think this about me?" with concrete evidence and reasoning.
