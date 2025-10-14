# Northstar Explainability / Provenance Panel — Complete

## Status: ✅ FULLY IMPLEMENTED & PRODUCTION-READY

Date: 2025-10-14
Branch: `feat/cppp_devx_bootstrap`

---

## Overview

A comprehensive first-class provenance viewer that provides complete transparency into how every trait in Northstar is determined. Users can click "Why?" on any trait to see the full evidence chain, inference rules, UCN scoring, timestamps, and sources.

---

## What Was Built

### 1. Core Provenance Service

**File:** [ReDNACoreDemo/core/provenance/service.py](ReDNACoreDemo/core/provenance/service.py:1)

**Function:** `build_provenance(user_id, trait_id, max_traces=10)`

**Capabilities:**
- Assembles complete provenance for any trait
- Scans multiple evidence file locations
- Extracts resolver trace references
- Separates direct evidence from inferences
- Determines RR scoring status
- Returns canonical provenance object

**Output Schema:**
```python
{
    "trait_id": str,                    # Canonical ID
    "resolved": {                        # Current state
        "value": dict,                   # Structured value
        "ucn": float,                    # Confidence (0-1)
        "status": str,                   # resolved/inferred/conflict
        "last_updated": str,             # ISO timestamp
        "sources": list[str]             # Source tags
    },
    "direct_evidence": [                 # All observations
        {
            "source": str,
            "ts": str,
            "value": dict,
            "ucn_prior": float,
            "provenance": str,
            "req_id": str
        }
    ],
    "inferences": [                      # Rule-based derivations
        {
            "source": str,
            "ts": str,
            "value": dict,
            "ucn_prior": float,
            "provenance": str            # "inference:rule_id"
        }
    ],
    "traces": [                          # Resolver traces
        {
            "req_id": str,
            "file": str,                 # Filename only (no secrets)
            "rr_ok": bool
        }
    ],
    "rr_status": "ok"|"offline"|"unknown"
}
```

### 2. Core API Endpoint

**Endpoint:** `GET /core/api/user/{user_id}/provenance/{trait_id}`

**File:** [ReDNACoreDemo/core/api.py](ReDNACoreDemo/core/api.py:2110)

**Features:**
- RESTful GET endpoint
- Path parameters for user_id and trait_id
- Input validation
- Error handling with appropriate HTTP status codes
- JSON response
- Logging for debugging

**Example Request:**
```bash
GET /core/api/user/USER123/provenance/PaDNA.EyeDNA.IrisColor
```

**Example Response:**
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
      "ucn_prior": 0.25
    }
  ],
  "inferences": [],
  "traces": [
    {"req_id": "a1b2c3d4", "file": "fixture-a1b2c3d4.json", "rr_ok": false}
  ],
  "rr_status": "offline"
}
```

### 3. TypeScript Provenance Client

**File:** [web/src/lib/provenanceClient.ts](web/src/lib/provenanceClient.ts:1)

**Exports:**
- Type definitions (Value, Evidence, TraceRef, Provenance, etc.)
- `fetchProvenance(userId, traitId)` - API client
- `formatValue(value)` - Display formatter
- `formatTimestamp(ts)` - Timestamp formatter
- `extractTraitLabel(traitId)` - Label extractor

**Features:**
- Fully typed with TypeScript
- Error handling
- Clean API abstraction
- Utility functions for formatting
- JSDoc documentation

### 4. TraitProvenanceDrawer Component

**File:** [web/src/components/provenance/trait-provenance-drawer.tsx](web/src/components/provenance/trait-provenance-drawer.tsx:1)

**UI Sections:**

1. **Header**
   - Trait label
   - Canonical trait ID
   - Close button

2. **Current State**
   - Current value (large, prominent)
   - UCN badge
   - Status badge
   - Last updated timestamp
   - Sources list

3. **Evidence Timeline**
   - All observations (newest first)
   - Value, source, timestamp
   - UCN prior
   - Request ID

4. **Inferences**
   - Inferred values
   - Rule IDs (provenance)
   - Prior UCN
   - Action buttons:
     - "Confirm / Correct…"
     - "Ask Follow-up…"

5. **RR Scoring**
   - Status: Online/Offline/Unknown
   - Color-coded indicator

6. **Resolver Traces (Dev Mode)**
   - Request IDs
   - Trace filenames
   - RR success/error per trace
   - Only shown on localhost

7. **Raw JSON Toggle**
   - Collapsible JSON view
   - Full provenance data
   - Syntax-highlighted

**Features:**
- Slide-in drawer from right
- Backdrop overlay
- Smooth animations
- Responsive layout
- Keyboard accessible
- Loading states
- Error handling
- Action callbacks

### 5. Integration with Unabridged Panel

**File:** [web/src/components/unabridged-panel.tsx](web/src/components/unabridged-panel.tsx:243)

**Changes:**
- Added "Why?" button to each trait row
- State management for drawer open/close
- State for selected trait ID
- Drawer rendering at component root
- Event dispatch for composer prefill
- Dev mode detection

**Why? Button:**
```tsx
<button
  onClick={() => {
    setProvenanceTraitId(row.original.trait_id);
    setProvenanceDrawerOpen(true);
  }}
  className="text-xs px-2 py-1 rounded border border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors"
  title="View trait provenance and evidence"
>
  Why?
</button>
```

**Drawer Instance:**
```tsx
<TraitProvenanceDrawer
  userId={snapshot?.user_id || ''}
  traitId={provenanceTraitId}
  open={provenanceDrawerOpen}
  onClose={() => {
    setProvenanceDrawerOpen(false);
    setProvenanceTraitId(null);
  }}
  onCompose={(text) => {
    window.dispatchEvent(new CustomEvent('northstar-compose', { detail: text }));
    setProvenanceDrawerOpen(false);
  }}
  devMode={typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')}
/>
```

### 6. Documentation

**File:** [web/NORTHSTAR_PROVENANCE.md](web/NORTHSTAR_PROVENANCE.md:1)

**Contents:**
- Feature overview
- User actions (Confirm/Correct, Ask Follow-up)
- How provenance data is collected
- RR status meanings
- Dev mode features
- Privacy & security
- Example workflow
- Troubleshooting guide
- API reference
- Future enhancements

---

## User Workflow

### 1. View Provenance

```
User sees trait: "Eye Color: blue · UCN 0.25"
                                    ↓
User clicks "Why?" button
                                    ↓
Drawer slides in from right
                                    ↓
Shows:
- Current: blue · UCN 0.25 · resolved
- Evidence: 1 item from "chat" at 3:45 PM
- Inferences: (none)
- RR Status: Offline (using priors)
```

### 2. Confirm Trait

```
User clicks "Confirm / Correct…"
                                    ↓
Composer prefills: "Confirm: my IrisColor is blue"
                                    ↓
User reviews and sends
                                    ↓
Pipeline processes message
                                    ↓
Resolver updates UCN
                                    ↓
Drawer refreshes with new data
```

### 3. Ask Follow-up

```
User clicks "Ask Follow-up…"
                                    ↓
Composer prefills: "Why did you infer IrisColor as blue?"
                                    ↓
User sends question
                                    ↓
Head Coach responds with explanation
```

---

## Technical Architecture

```
User clicks "Why?" on trait row
            ↓
UnabridgedPanel → setProvenanceTraitId(trait_id)
            ↓
TraitProvenanceDrawer opens
            ↓
fetchProvenance(userId, traitId)
            ↓
GET /core/api/user/{userId}/provenance/{traitId}
            ↓
build_provenance(user_id, trait_id)
            ↓
├── Read resolved.json
├── Scan evidence files
├── Scan resolver traces
└── Determine RR status
            ↓
Return provenance JSON
            ↓
Drawer renders:
├── Current State
├── Evidence Timeline
├── Inferences
├── RR Scoring
├── Traces (dev)
└── Raw JSON (toggle)
            ↓
User actions:
├── Confirm/Correct → Dispatch "northstar-compose" event
└── Ask Follow-up → Dispatch "northstar-compose" event
            ↓
ChatComposer listens → prefills input → user sends
```

---

## Privacy & Security

### No Secrets in Logs
- ✅ Full file paths never exposed in UI
- ✅ Only filenames shown (e.g., "fixture-a1b2c3d4.json")
- ✅ Request IDs sanitized
- ✅ No API keys or tokens in traces

### Dev Mode Gating
- ✅ Trace file paths only on localhost/127.0.0.1
- ✅ Production builds hide internal details
- ✅ Hostname detection: `window.location.hostname`

### Data Provenance
- ✅ All evidence tagged with source
- ✅ Timestamps preserved
- ✅ Inference rules identified
- ✅ Chain of custody maintained

---

## Files Created/Modified

### Created
- `ReDNACoreDemo/core/provenance/__init__.py` - Module init
- `ReDNACoreDemo/core/provenance/service.py` - Provenance builder
- `web/src/lib/provenanceClient.ts` - TypeScript client
- `web/src/components/provenance/trait-provenance-drawer.tsx` - Drawer component
- `web/NORTHSTAR_PROVENANCE.md` - User documentation
- `NORTHSTAR_EXPLAINABILITY_COMPLETE.md` - This document

### Modified
- `ReDNACoreDemo/core/api.py` - Added provenance endpoint
- `web/src/components/unabridged-panel.tsx` - Added Why button and drawer

---

## Testing

### Manual Test Checklist

1. ✅ **View Provenance**
   - Open Northstar unabridged panel
   - Click "Why?" on any trait
   - Drawer slides in from right
   - All sections render correctly

2. ✅ **Evidence Timeline**
   - Shows all observations
   - Timestamps formatted correctly
   - Sources displayed
   - Values human-readable

3. ✅ **Inferences**
   - Inferred traits marked
   - Rule IDs shown
   - Prior UCN displayed

4. ✅ **RR Status**
   - Shows "Online" when RR running
   - Shows "Offline (using priors)" when RR down
   - Color-coded appropriately

5. ✅ **Dev Mode Traces**
   - Visible on localhost
   - Hidden in production
   - Request IDs correct
   - Filenames shown (not full paths)

6. ✅ **Raw JSON**
   - Toggle works
   - JSON formatted correctly
   - All data present

7. ✅ **Confirm/Correct Action**
   - Button click prefills composer
   - Message format correct
   - Drawer closes
   - Pipeline processes message

8. ✅ **Ask Follow-up Action**
   - Button click prefills composer
   - Question format appropriate
   - Drawer closes
   - Head Coach responds

9. ✅ **Close Drawer**
   - X button works
   - Backdrop click works
   - State resets correctly

10. ✅ **Error Handling**
    - Shows error if API fails
    - Shows error if trait not found
    - Loading state during fetch

---

## Example Data

### Input: "I have blue eyes"

**Evidence Created:**
```json
{
  "trait_id": "PaDNA.EyeDNA.IrisColor",
  "value": {"enum": "blue"},
  "source": "chat",
  "ts": "2025-10-14T03:45:00Z",
  "ucn_prior": 0.25
}
```

**Provenance API Response:**
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
      "req_id": "fixture-a1b2c3d4",
      "file": "fixture-a1b2c3d4.json",
      "rr_ok": false
    }
  ],
  "rr_status": "offline"
}
```

**Drawer Display:**
```
Why this trait?
IrisColor
PaDNA.EyeDNA.IrisColor

Current State
blue · UCN 0.25 · resolved
Updated: 10/14/2025, 3:45:00 AM · Sources: chat

Evidence Timeline
blue · chat · 10/14/2025, 3:45:00 AM · prior 0.25

Inferences
No inferences for this trait.
[Confirm / Correct…] [Ask Follow-up…]

RR Scoring
Status: Offline (using priors)

☐ Show Raw JSON
```

---

## Benefits

### For Users
1. **Complete Transparency**: See exactly why Northstar thinks something
2. **Trust Building**: Full evidence chain visible
3. **Control**: Confirm or correct any trait
4. **Learning**: Understand how the system works
5. **Engagement**: Ask natural follow-up questions

### For Developers
1. **Debuggability**: Trace any trait to source
2. **Observability**: See resolver decisions
3. **Validation**: Verify pipeline is working
4. **Troubleshooting**: Diagnose UCN issues quickly
5. **Confidence**: Know data flow is correct

### For Product
1. **Differentiation**: First-class explainability
2. **Compliance**: Full audit trail
3. **User Satisfaction**: No black boxes
4. **Feedback Loop**: Users can correct errors
5. **Trust**: Transparency builds confidence

---

## Future Enhancements

### Planned
1. **Conflict Visualization**: Show when values conflict
2. **Confidence Intervals**: UCN uncertainty ranges
3. **Source Filtering**: Filter evidence by source type
4. **Time Travel**: View trait state historically
5. **Comparison Mode**: Compare two traits side-by-side

### Under Consideration
- Evidence graph visualization
- Plain English rule explanations
- Batch provenance for multiple traits
- Provenance search across all traits
- PDF/JSON export

---

## Commit Message

```bash
git add ReDNACoreDemo/core/provenance/
git add ReDNACoreDemo/core/api.py
git add web/src/lib/provenanceClient.ts
git add web/src/components/provenance/
git add web/src/components/unabridged-panel.tsx
git add web/NORTHSTAR_PROVENANCE.md
git add NORTHSTAR_EXPLAINABILITY_COMPLETE.md

git commit -m "feat(provenance): Northstar 'Why?' panel with Core provenance API

- Core: build_provenance() + GET /core/api/user/{id}/provenance/{trait_id}
- UI: TraitProvenanceDrawer with evidence timeline, inferences, RR status, traces (dev), raw JSON
- Actions: Confirm/Correct and Ask follow-up (prefill Composer)
- Privacy: No full file paths in UI, dev mode gating for traces
- Docs: Complete user guide and API reference

Every trait in Northstar is now fully explainable, confirmable, and traceable."
```

---

## Summary

The Northstar Provenance Viewer provides **complete explainability** for every trait:

✅ **Core Provenance Service** - Assembles evidence, traces, and status
✅ **REST API Endpoint** - GET provenance for any trait
✅ **TypeScript Client** - Type-safe API access
✅ **Drawer Component** - Beautiful, functional UI
✅ **Evidence Timeline** - Full observation history
✅ **Inference Visibility** - Rule-based derivations shown
✅ **RR Status** - Online/Offline transparency
✅ **Resolver Traces** - Dev mode debugging
✅ **User Actions** - Confirm/Correct, Ask Follow-up
✅ **Privacy-Preserving** - No secrets in logs
✅ **Comprehensive Docs** - User guide + API reference

**Every trait can now answer: "Why does Northstar think this about me?"**

The system is **production-ready** and provides the foundation for trust, transparency, and user control.
