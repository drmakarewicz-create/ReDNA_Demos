# Persona Snapshot Export Design Document

**Date:** 2025-10-04
**Status:** 🔧 In Progress
**Related Benchmark:** #11 (Persona snapshots)

---

## 🎯 Objective

Create an export pipeline that **freezes a user's PaDNA into timestamped JSON bundles** for:
- Outbound sharing (specific contexts)
- Backup/archival
- Analysis/reporting
- Persona preservation ("frozen" states)

---

## 📋 Requirements (from Roadmap)

> "Define export pipeline that freezes a user's PaDNA into timestamped JSON bundles surfaced in Explorer."

**Functional Requirements:**
1. Export complete PaDNA snapshot (all traits, evidence, metadata)
2. Timestamped for historical tracking
3. Frozen (immutable once exported)
4. JSON format for portability
5. Surfaced in Explorer UI
6. Support partial exports (specific trait families)
7. Include provenance and metadata

**Non-Functional Requirements:**
- Fast export (< 2s for full PaDNA)
- Compact size (compressed if needed)
- Human-readable JSON
- Privacy-aware (consent flags respected)
- Version-tagged for future compatibility

---

## 🔍 Current State Analysis

### Existing Components

**1. Storage System** (`storage.py`)
- User data in `data/users/{user_id}/`
- Observations, resolved state, evidence files
- JSON persistence already in place

**2. UI Readonly** (`ui_readonly.py`)
- `read_user_state()` - Loads obs/resolved/evidence
- `list_traits()` - Enumerates available traits
- Read-only access to user data

**3. Holistic System** (`holistic_scheduler.py`)
- Already creates periodic snapshots
- Raw JSON persistence
- Could be leveraged for snapshot export

### Gaps
❌ No **explicit export API** for snapshots
❌ No **timestamped bundles** (current files overwrite)
❌ No **UI for exporting** snapshots
❌ No **partial export** (trait family selection)
❌ No **snapshot history** or versioning

---

## 🎨 Design

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Explorer UI                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Persona Snapshot Manager                         │  │
│  │  - Current PaDNA Summary                          │  │
│  │  - [Export Full Snapshot]                         │  │
│  │  - [Export Specific Families...]                  │  │
│  │  - Snapshot History (10 most recent)              │  │
│  │    • 2025-10-04 12:30 - Full (1.2 MB)            │  │
│  │    • 2025-10-03 08:15 - Looks+Style (320 KB)     │  │
│  │  - [Download] [Delete] [View Details]            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ API: /snapshots/export
                          │
┌─────────────────────────┴───────────────────────────────┐
│         Snapshot Exporter Module                         │
│  (ReDNACoreDemo/core/snapshot_exporter.py)              │
│                                                          │
│  export_snapshot(user_id, families=None) → Snapshot    │
│    1. Load user state (obs/resolved/evidence)          │
│    2. Filter by families if specified                   │
│    3. Add metadata (timestamp, version, provenance)    │
│    4. Create timestamped bundle                         │
│    5. Save to snapshots/ directory                      │
│    6. Return Snapshot object                            │
│                                                          │
│  list_snapshots(user_id) → List[SnapshotMeta]          │
│    - Load snapshot index                                │
│    - Return metadata (no full data)                     │
│                                                          │
│  load_snapshot(user_id, snapshot_id) → Snapshot        │
│    - Load full snapshot from file                       │
│                                                          │
│  delete_snapshot(user_id, snapshot_id) → bool          │
│    - Remove snapshot file and update index              │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Uses
                          ▼
┌─────────────────────────────────────────────────────────┐
│       Existing Components                                │
│  - storage (read user data)                             │
│  - ui_readonly (read_user_state)                        │
└─────────────────────────────────────────────────────────┘
```

### Data Model

**Snapshot** (dataclass):
```python
@dataclass
class Snapshot:
    id: str  # timestamp-based ID
    user_id: str
    created_at: str  # ISO timestamp
    version: str  # "1.0.0"
    scope: str  # "full" or "partial"
    families: List[str]  # Trait families included
    data: Dict[str, Any]  # Full PaDNA data
    metadata: Dict[str, Any]  # Size, trait count, etc.

    # Data structure:
    # {
    #   "observations": {...},
    #   "resolved": {...},
    #   "evidence": {...},
    #   "ucn_rr": {...},
    #   "provenance": {...}
    # }
```

**SnapshotMeta** (lightweight for listings):
```python
@dataclass
class SnapshotMeta:
    id: str
    user_id: str
    created_at: str
    scope: str
    families: List[str]
    size_bytes: int
    trait_count: int
```

**Storage Structure:**
```
data/users/{user_id}/
└── snapshots/
    ├── index.json              ← Lightweight metadata
    ├── snapshot_20251004T123045.json
    ├── snapshot_20251003T081530.json
    └── ...
```

---

## 🧠 Export Strategy

### Full Snapshot

**Includes:**
- All observations (`observations.json`)
- All resolved state (`resolved.json`)
- All evidence (`evidence.json`)
- UCN/RR data (if available)
- Provenance metadata
- User metadata (demographics, consent flags)

**Size:** ~500KB - 2MB (typical user)

### Partial Snapshot (by Family)

**Examples:**
- "LooksDNA" → All Looks-related traits
- "LooksDNA,StyleDNA" → Looks + Style only
- "RelationshipDNA" → Relationship traits only

**Use Cases:**
- Share specific context (e.g., Looks for fashion app)
- Targeted backup
- Focused analysis

---

## 📐 Implementation Plan

### File Structure

```
ReDNACoreDemo/core/
├── snapshot_exporter.py     ← NEW (core logic)
├── api_snapshots.py         ← NEW (FastAPI endpoints)
└── ...

data/users/{user_id}/
└── snapshots/
    ├── index.json
    └── snapshot_*.json

ExplorerDev/tabs/
└── snapshot_manager.py      ← NEW (UI for snapshots)
```

### Core Module (`snapshot_exporter.py`)

**Functions:**
1. `export_snapshot(user_id, families=None, label=None) → Snapshot`
   - Main export function
   - Creates timestamped bundle
   - Saves to storage
   - Returns Snapshot object

2. `list_snapshots(user_id, limit=20) → List[SnapshotMeta]`
   - Lists snapshot metadata
   - Most recent first

3. `load_snapshot(user_id, snapshot_id) → Snapshot`
   - Loads full snapshot data

4. `delete_snapshot(user_id, snapshot_id) → bool`
   - Removes snapshot file
   - Updates index

5. `_filter_by_families(data, families) → Dict`
   - Filters traits by family list

6. `_compute_metadata(data) → Dict`
   - Calculates size, trait count, etc.

---

## 🎨 UI Design

### Location: ExplorerDev → New "Snapshots" Tab

```
┌─────────────────────────────────────────────────────────────┐
│  📸 Persona Snapshot Manager                                │
│                                                              │
│  Current PaDNA Status:                                       │
│  ├─ Total Traits: 247                                       │
│  ├─ Families: 8 (PaDNA, EmDNA, SoDNA, CaDNA, ...)          │
│  ├─ Last Updated: 2025-10-04 12:30:15                       │
│  └─ Size (est.): 1.2 MB                                     │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Export New Snapshot                                    │ │
│  │ ─────────────────────────────────────────────────────  │ │
│  │ Scope: ○ Full PaDNA  ● Specific Families              │ │
│  │ Select: ☑ LooksDNA  ☑ StyleDNA  ☐ RelationshipDNA     │ │
│  │         ☐ CareerDNA  ☐ HealthDNA  ☐ Other             │ │
│  │ Label: [Optional description]                          │ │
│  │ [Export Snapshot]                                      │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  Snapshot History (10 most recent):                         │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 2025-10-04 12:30:45 - Full PaDNA                      │ │
│  │ ─────────────────────────────────────────────────────  │ │
│  │ Families: All (8)                                      │ │
│  │ Size: 1.2 MB │ Traits: 247                            │ │
│  │ [📥 Download JSON] [👁 Preview] [🗑 Delete]           │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 2025-10-03 08:15:30 - Looks+Style                     │ │
│  │ ─────────────────────────────────────────────────────  │ │
│  │ Families: LooksDNA, StyleDNA (2)                       │ │
│  │ Size: 320 KB │ Traits: 64                             │ │
│  │ Label: "Fashion app export"                            │ │
│  │ [📥 Download JSON] [👁 Preview] [🗑 Delete]           │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Success Criteria

- ✅ Full snapshots export in < 2s
- ✅ Partial snapshots supported (family filtering)
- ✅ Timestamped and versioned
- ✅ JSON is human-readable
- ✅ Privacy flags respected (consent)
- ✅ UI for export/list/download/delete
- ✅ Snapshot history maintained
- ✅ API endpoints functional

---

## 📊 Snapshot Format

### Example (Full Snapshot)

```json
{
  "snapshot_id": "snapshot_20251004T123045",
  "user_id": "test_user",
  "created_at": "2025-10-04T12:30:45.123456Z",
  "version": "1.0.0",
  "scope": "full",
  "families": ["PaDNA", "EmDNA", "SoDNA", "CaDNA", ...],
  "metadata": {
    "trait_count": 247,
    "family_count": 8,
    "size_bytes": 1234567,
    "export_method": "api",
    "label": null
  },
  "data": {
    "observations": {
      "PaDNA.LooksDNA.EyeColor": {
        "value": "blue",
        "ucn": 450.0,
        "rr": 0.85,
        "last_update": "2025-10-01T10:00:00Z",
        "provenance": ["self_report", "photo_analysis"]
      },
      ...
    },
    "resolved": {
      "PaDNA.LooksDNA.EyeColor": {
        "resolved_value": "blue",
        "confidence": 0.95,
        "sources": 3
      },
      ...
    },
    "evidence": {
      "PaDNA.LooksDNA.EyeColor": [
        {
          "type": "confirmation",
          "value": "blue",
          "ts": "2025-09-28T14:30:00Z",
          "source": "photo_upload"
        },
        ...
      ]
    },
    "ucn_rr_summary": {
      "avg_ucn": 380.5,
      "avg_rr": 0.72,
      "curiosity_score": 0.28
    },
    "provenance": {
      "export_source": "ExplorerDev",
      "export_user": "admin",
      "write_protect_mode": true
    }
  }
}
```

### Example (Partial Snapshot - Looks+Style)

```json
{
  "snapshot_id": "snapshot_20251003T081530",
  "user_id": "test_user",
  "created_at": "2025-10-03T08:15:30.987654Z",
  "version": "1.0.0",
  "scope": "partial",
  "families": ["LooksDNA", "StyleDNA"],
  "metadata": {
    "trait_count": 64,
    "family_count": 2,
    "size_bytes": 327680,
    "export_method": "ui",
    "label": "Fashion app export"
  },
  "data": {
    "observations": {
      "PaDNA.LooksDNA.EyeColor": {...},
      "PaDNA.StyleDNA.PreferredColors": {...},
      ...
    },
    ...
  }
}
```

---

## 🔧 Implementation Phases

### Phase 1: Core Module
- ✅ Create `snapshot_exporter.py`
- ✅ Implement Snapshot/SnapshotMeta dataclasses
- ✅ Implement export_snapshot() with family filtering
- ✅ Add snapshot persistence and index

### Phase 2: API
- ✅ Create `api_snapshots.py`
- ✅ POST /snapshots/export
- ✅ GET /snapshots/list/{user_id}
- ✅ GET /snapshots/{snapshot_id}
- ✅ DELETE /snapshots/{snapshot_id}

### Phase 3: UI (Optional - can defer)
- Create Snapshot Manager tab
- Export form with family selection
- Snapshot history list
- Download/delete actions

---

## 📚 Related Documentation

- **Storage:** `ReDNACoreDemo/core/storage.py`
- **UI Readonly:** `ReDNACoreDemo/core/ui_readonly.py`
- **Holistic Scheduler:** `ReDNACoreDemo/core/holistic_scheduler.py`
- **Roadmap:** `docs/Core_Benchmarks_Roadmap.md` (Benchmark #11)

---

**Next:** Implement Phase 1 & 2 (Core Module + API)
