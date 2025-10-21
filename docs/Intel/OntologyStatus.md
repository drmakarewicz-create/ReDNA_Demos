# ReDNA Ontology Status

**Version:** 1.0
**Generated:** 2025-10-20
**Seed Version:** 2.0 (Phase 10)

## Overview

This document provides the current status of the ReDNA ontology hierarchy. The ontology defines the structure of trait categories (DNA systems) and their relationships.

---

## Phase 10 Hierarchy Model

### Structure

```
ReDNA (root, tier-0)
├── RelDNA (tier-1) - Relational DNA
├── PaDNA (tier-1) - Physical Attributes DNA
├── BehDNA (tier-1) - Behavioral DNA
├── CogDNA (tier-1) - Cognitive DNA
└── EmoDNA (tier-1) - Emotional DNA
```

### Key Changes from Phase 9

**Phase 9 (old):**
- RelDNA was considered the "root" organism
- No formal hierarchy above RelDNA

**Phase 10 (current):**
- ReDNA = Replicated Digital Neural Approximation (root)
- RelDNA = Relational DNA (one of five tier-1 subsystems)
- Full organism model with 5 major subsystems

---

## Current Seed Ontology

**File:** `data/ontology/seed_ontology.json`

### Statistics

- **Version:** 2.0
- **Total Nodes:** 10
- **Total Edges:** 9

### Node Breakdown

| Node Type | Count | Examples |
|-----------|-------|----------|
| `dna_category` | 6 | ReDNA, RelDNA, PaDNA, BehDNA, CogDNA, EmoDNA |
| `trait` | 4 | Chronotype, OutdoorActivity.Frequency, Exercise.PreferredTime, SocialStyle |
| `trait_value` | 0 | (None in seed) |
| `trait_belief` | 0 | (User-specific, not in seed) |

### Edge Breakdown

| Edge Type | Count | Description |
|-----------|-------|-------------|
| `is_parent_of` | 9 | Hierarchy relationships (ReDNA → tier-1, PaDNA → traits) |
| `correlates` | 0 | (None in seed) |
| `contradicts` | 0 | (None in seed) |
| `suggests_question` | 0 | (None in seed) |

---

## Hierarchy Details

### Tier 0: ReDNA (Root)

```json
{
  "node_id": "ont_redna_root",
  "node_type": "dna_category",
  "trait_id": "ReDNA",
  "label": "ReDNA",
  "description": "Replicated Digital Neural Approximation - The complete digital organism",
  "metadata": {
    "tier": 0,
    "full_name": "Replicated Digital Neural Approximation",
    "is_root": true
  }
}
```

### Tier 1: Five Major Subsystems

1. **RelDNA** - Relational DNA
   - Social connections and relationship patterns
   - Aliases: "RelationalDNA", "Relational DNA"

2. **PaDNA** - Physical Attributes DNA
   - Observable physical characteristics
   - Contains 4 seed traits (see below)

3. **BehDNA** - Behavioral DNA
   - Behavior patterns, habits, actions
   - Alias: "BehaviorDNA"

4. **CogDNA** - Cognitive DNA
   - Thinking patterns, mental processes

5. **EmoDNA** - Emotional DNA
   - Emotional patterns, regulation, affective responses

### Tier 2: PaDNA Traits (Seed)

The seed ontology includes 4 example traits under PaDNA:

1. **PaDNA.Chronotype**
   - Label: "Chronotype"
   - Description: "Morning person vs. night owl preference"
   - Category: "Physical"

2. **PaDNA.OutdoorActivity.Frequency**
   - Label: "Outdoor Activity Frequency"
   - Category: "Physical"

3. **PaDNA.Exercise.PreferredTime**
   - Label: "Preferred Exercise Time"
   - Category: "Physical"

4. **PaDNA.SocialStyle**
   - Label: "Social Style"
   - Category: "Social"
   - *Note: This trait has category mismatch (Social vs Physical parent)*

---

## Verification Commands

### 1. Check Seed File Version

```bash
jq '{version: .version, nodes: (.nodes | length), edges: (.edges | length)}' \
  data/ontology/seed_ontology.json
```

**Expected Output:**
```json
{
  "version": "2.0",
  "nodes": 10,
  "edges": 9
}
```

### 2. Force Load Ontology

```bash
curl -s -X POST http://127.0.0.1:8004/core/graph/ontology/load?force=true | jq .
```

**Expected Output:**
```json
{
  "status": "success",
  "action": "force_loaded",
  "nodes": 10,
  "edges": 9,
  "version": "2.0",
  "message": "Ontology loaded from seed (10 nodes, 9 edges)"
}
```

### 3. Get Current Ontology

```bash
curl -s http://127.0.0.1:8004/core/graph/ontology | \
  jq '{version: .version, nodes: (.nodes | length), edges: (.edges | length)}'
```

**Expected Output:**
```json
{
  "version": "2.0",
  "nodes": 10,
  "edges": 9
}
```

### 4. List Tier-1 DNA Categories

```bash
jq '.nodes[] | select(.metadata.tier == 1) | .trait_id' \
  data/ontology/seed_ontology.json
```

**Expected Output:**
```
"RelDNA"
"PaDNA"
"BehDNA"
"CogDNA"
"EmoDNA"
```

### 5. Inspect Hierarchy Edges

```bash
jq '.edges[] | select(.edge_type == "is_parent_of") |
  {from: .from_node, to: .to_node, rationale: .rationale}' \
  data/ontology/seed_ontology.json
```

**Expected Output:** 9 edges showing ReDNA → tier-1 and PaDNA → traits relationships

---

## API Endpoints

### Load Ontology

**Endpoint:** `POST /core/graph/ontology/load`

**Parameters:**
- `force` (optional, default=false) - If true, REPLACE existing ontology with seed

**Behavior:**
- Normal mode (`force=false`): Load seed only if ontology is empty OR seed version > stored version
- Force mode (`force=true`): Always replace stored ontology with seed (useful for debugging)

**Version Comparison:**
- Uses semantic versioning comparison
- Example: "2.0" > "1.0"
- Auto-upgrade triggers when seed is newer

### Get Ontology

**Endpoint:** `GET /core/graph/ontology`

**Returns:** Complete ontology graph (nodes + edges + version)

### Get Ontology Stats

**Endpoint:** `GET /core/debug/ontology/stats`

**Returns:** Summary statistics (node counts, edge types, categories)

---

## Migration Notes

### Upgrading from Phase 9 to Phase 10

If your stored ontology is still Phase 9 (version 1.0 or earlier):

1. **Automatic Upgrade:**
   - The loader will auto-upgrade when it detects seed version 2.0 > stored version 1.0
   - No manual intervention needed

2. **Manual Force Reload:**
   ```bash
   curl -X POST http://127.0.0.1:8004/core/graph/ontology/load?force=true
   ```

3. **Verify Upgrade:**
   ```bash
   curl -s http://127.0.0.1:8004/core/graph/ontology | jq .version
   # Should output: "2.0"
   ```

### Backward Compatibility

- Phase 10 is **backward compatible** with Phase 9 trait paths
- Existing traits like `PaDNA.HairDNA.Color` continue to work
- The hierarchy adds context but doesn't break existing data

---

## Known Issues

### Issue 1: PaDNA.SocialStyle Category Mismatch

**Description:** The trait `PaDNA.SocialStyle` has `category: "Social"` but parent is PaDNA (Physical).

**Impact:** Minimal - category is informational, hierarchy is authoritative.

**Fix:** Future seed update should either:
- Change category to "Physical"
- Move trait to RelDNA (if social traits are added there)

### Issue 2: Minimal Seed Traits

**Description:** Seed only includes 4 traits (all under PaDNA).

**Impact:** Other tier-1 systems (RelDNA, BehDNA, CogDNA, EmoDNA) have no seed traits yet.

**Plan:** Future phases will add representative traits for each tier-1 system.

---

## Testing

### Test Suite

**Location:** `tests/api/test_ontology_loader.py`

**Coverage:**
- ✅ Force load replaces ontology (not merge)
- ✅ Version-based auto-upgrade
- ✅ Phase 10 hierarchy structure (10 nodes, 9 edges)
- ✅ Semantic version comparison
- ✅ Schema support for `dna_category` and `is_parent_of`
- ✅ Backward compatibility with Phase 9 traits

**Run Tests:**
```bash
make test-graph
# or
pytest tests/api/test_ontology_loader.py -v
```

**Expected Result:** 14/14 tests passing

---

## Future Expansion

### Planned Additions (Post-Phase 10)

1. **Tier-1 Seed Traits:**
   - RelDNA: Relationship traits (e.g., Attachment.Style, Social.Network.Size)
   - BehDNA: Behavior traits (e.g., Morning.Routine, Work.Habits)
   - CogDNA: Cognitive traits (e.g., Learning.Style, Problem.Solving.Approach)
   - EmoDNA: Emotional traits (e.g., Emotional.Regulation, Stress.Response)

2. **Cross-Tier Correlations:**
   - Add `correlates` edges between traits across tier-1 systems
   - Example: PaDNA.Chronotype correlates with BehDNA.Morning.Routine

3. **Contradiction Detection:**
   - Add `contradicts` edges for trait pairs that shouldn't coexist
   - Example: PaDNA.Exercise.Frequency=High contradicts BehDNA.Sedentary=True

4. **Ontology Evolution:**
   - Support for incremental updates (not just full replacement)
   - Versioned migrations with rollback capability
   - User-specific ontology extensions

---

## Summary

- **Current Status:** Phase 10 hierarchy fully loaded (version 2.0)
- **Structure:** ReDNA root + 5 tier-1 subsystems + 4 seed traits
- **Health:** ✅ All tests passing, loader working correctly
- **Next Steps:** Expand seed traits for RelDNA, BehDNA, CogDNA, EmoDNA
