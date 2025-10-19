# Phase 9: Container Explosion & Adaptive Persona Context — Quick Start

**Ontology V6: 8K+ Containers with Persona Weighting**

Version: 1.0
Date: 2025-10-11
Status: 🚧 **IN PROGRESS**

---

## 🎯 Quick Start

### 1. Generate V6 Registry (8K+ Containers)

```bash
cd ReDNACoreDemo
PYTHONPATH=.:.. python3 -m ReDNACoreDemo.core.ontology.expansion_engine_v6
```

**Expected Output**:
- V6 registry: `data/ontology/registry_v6/dna_registry_v6.json`
- Persona index: `data/ontology/registry_v6/persona_context_index.json`
- Generation time: <10s
- Total containers: ≥8,000

### 2. Query Persona Context via API

```bash
# Get career-relevant containers
curl http://localhost:8000/ui/persona/context/career/TEST?limit=10

# Get relationship-relevant containers
curl http://localhost:8000/ui/persona/context/relationship/TEST?limit=10
```

**Response Format**:
```json
{
  "ok": true,
  "persona": "career",
  "user_id": "TEST",
  "total_containers": 2547,
  "returned_containers": 10,
  "containers": [
    {
      "container_id": "career_001",
      "path": "CareerDNA.skills.leadership",
      "weight": 0.95,
      "trait_relevance": 0.85,
      "curiosity_boost": 0.4
    }
  ],
  "duration_ms": 15
}
```

### 3. Test Persona Context Lookup

```python
from ReDNACoreDemo.core.ontology.expansion_engine_v6 import ExpansionEngineV6

# Load engine
engine = ExpansionEngineV6()

# Get career context
career_containers = engine.get_persona_context('career', limit=20)

# Print top 5
for container in career_containers[:5]:
    print(f"{container['path']} - weight: {container['weight']:.2f}")
```

---

## 🏗️ Architecture

### Container Metadata (V6)

Each container now includes:

```json
{
  "id": "container_001",
  "namespace": "CareerDNA",
  "path": "CareerDNA.skills.leadership",
  "description": "Leadership and team management abilities",

  "persona_weights": {
    "career": 0.95,
    "relationship": 0.4,
    "personality": 0.6,
    "chat": 0.3,
    "belief": 0.3
  },

  "trait_relevance": 0.85,
  "curiosity_boost": 0.4,
  "learning_value": 0.7,

  "tagged_at": "2025-10-11T20:00:00Z",
  "version": "v6.0"
}
```

### Persona Weight Mapping

Personas are scored based on:

1. **Namespace relevance** — CareerDNA has high career weight
2. **Trait keywords** — "leadership" boosts career weight
3. **Contextual keywords** — "empathy" boosts relationship weight

**Weight Formula**:
```
weight = base_namespace_weight + trait_keyword_boost
capped at 1.0
```

### Persona Context Index

Fast lookup structure:

```json
{
  "career": [
    {"container_id": "c1", "weight": 0.95, ...},
    {"container_id": "c2", "weight": 0.90, ...}
  ],
  "relationship": [
    {"container_id": "r1", "weight": 1.0, ...},
    {"container_id": "r2", "weight": 0.85, ...}
  ]
}
```

Pre-sorted by weight for O(1) lookup.

---

## 📊 Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Container generation | ≤10s for 8K | ✅ (MVP) |
| Memory usage | <400MB | ✅ |
| Context lookup | <20ms | ✅ |
| Duplicate rate | 0% | ✅ |
| Collision rate | 0% | ✅ |

---

## 🎨 Persona Weight Configuration

**File**: `ReDNACoreDemo/core/ontology/expansion_engine_v6.py`

### Career Persona

```python
"career": {
    "SkillDNA": 0.9,
    "ProfDNA": 0.95,
    "CareerDNA": 1.0,
    "traits": {
        "leadership": 0.9,
        "communication": 0.8,
        "technical": 0.95
    }
}
```

### Relationship Persona

```python
"relationship": {
    "RelationshipDNA": 1.0,
    "ChatDNA": 0.8,
    "PsyDNA": 0.85,
    "traits": {
        "empathy": 0.95,
        "communication": 0.9,
        "emotional": 0.9
    }
}
```

### Personality Persona

```python
"personality": {
    "PsyDNA": 1.0,
    "BeliefDNA": 0.8,
    "traits": {
        "personality": 1.0,
        "temperament": 0.95,
        "behavioral": 0.9
    }
}
```

---

## 🔧 API Reference

### GET `/ui/persona/context/{persona}/{user_id}`

Returns prioritized containers for a persona.

**Parameters**:
- `persona` (path): Persona identifier (career, relationship, personality, chat, belief)
- `user_id` (path): User identifier
- `limit` (query, optional): Max containers to return (default: 100)

**Response**:
```json
{
  "ok": true,
  "persona": "career",
  "user_id": "TEST",
  "total_containers": 2547,
  "returned_containers": 100,
  "containers": [...],
  "duration_ms": 15
}
```

**Status Codes**:
- `200` — Success
- `500` — Server error

---

## 🧪 Testing

### Run V6 Tests

```bash
cd ReDNACoreDemo
pytest tests/test_ontology_expansion_v6.py -v
pytest tests/test_persona_context_api.py -v
```

### Manual Verification

```bash
# 1. Generate V6 registry
python3 -m ReDNACoreDemo.core.ontology.expansion_engine_v6

# 2. Check file sizes
ls -lh data/ontology/registry_v6/

# 3. Count containers
cat data/ontology/registry_v6/dna_registry_v6.json | jq '.total_containers'

# 4. Check persona index
cat data/ontology/registry_v6/persona_context_index.json | jq 'keys'

# 5. Test API
curl http://localhost:8000/ui/persona/context/career/TEST?limit=5 | jq .
```

---

## 🚀 Integration with Right Pane

### Photo Coach Example

```typescript
// web/src/components/photo/photo-panel.tsx
import { fetchPersonaContext } from '@/lib/api';

async function loadPhotoContext(userId: string) {
  const response = await fetchPersonaContext('photo', userId, 20);
  // Use containers to highlight relevant traits
  // e.g., visual traits, aesthetic preferences
}
```

### Career Coach Example

```typescript
// web/src/components/career/career-snapshot-card.tsx
import { fetchPersonaContext } from '@/lib/api';

async function loadCareerContext(userId: string) {
  const response = await fetchPersonaContext('career', userId, 50);
  // Use containers to show career-relevant skills/goals
}
```

---

## 📚 Next Steps

### Phase 9A (Current)
- [x] V6 expansion engine
- [x] Persona context API
- [ ] Persona Lens UI
- [ ] Comprehensive tests
- [ ] Documentation

### Phase 9B (Future)
- [ ] Multiprocessing for parallel generation
- [ ] Template system integration
- [ ] Real-time adaptive weighting
- [ ] User-specific context tuning

---

## 📖 Documentation

- **[ONTOLOGY_EXPANSION_V6_PHASE9.md](docs/ONTOLOGY_EXPANSION_V6_PHASE9.md)** — Full architecture guide
- **[PHASE9_CONTAINER_EXPLOSION_QUICKSTART.md](PHASE9_CONTAINER_EXPLOSION_QUICKSTART.md)** — This document

---

**Status**: 🚧 **IN PROGRESS** (Core engine + API complete, UI pending)

**Next**: Add Persona Lens UI component + comprehensive tests
