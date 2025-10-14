# Container Explosion Plan - Master Index

**Project**: ReDNA DNA Ontology System
**Goal**: Scale from 422 → 1,000 → 10,000 → 100,000 → 1,000,000 containers
**Current Phase**: Phase A Complete ✅
**Next Phase**: Phase B (10k containers)

---

## Quick Navigation

### Phase Documentation
- **[Phase A Completion Report](./PHASE_A_COMPLETION.md)** - Detailed completion report (422 containers achieved)
- **[Ontology Overview](./ONTOLOGY_OVERVIEW.md)** - System architecture and concepts
- [Phase B Planning](./PHASE_B_PLANNING.md) - ⏳ Next phase (10k containers)

### Core Documentation
- **[RR System Index](./RR_SYSTEM_INDEX.md)** - Refinement Rating documentation hub
- [RR Architecture](./RR_ARCHITECTURE_MULTILEVEL.md) - Multi-level RR hierarchy
- [RR Quick Reference](./RR_QUICK_REFERENCE.md) - Commands and cheat sheet

### Technical Docs
- [DNA Registry Schema](./DNA_REGISTRY_SCHEMA.md) - ⏳ JSON Schema deep dive
- [Container Generation Rules](./CONTAINER_GENERATION_RULES.md) - ⏳ Expansion algorithms
- [Curiosity Engine](./CURIOSITY_ENGINE.md) - ⏳ Priority scoring details
- [Policy Gate Framework](./POLICY_GATE_README.md) - ⏳ AI shadow governance

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ReDNA DNA Ontology                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  18 Namespaces                                               │
│  ├─ PaDNA (Physical Appearance) ............. 157 containers │
│  ├─ PsyDNA (Psychological) ................... 31 containers │
│  ├─ EmDNA (Emotional) ........................ 24 containers │
│  ├─ CogDNA (Cognitive) ....................... 22 containers │
│  ├─ HealthDNA (Health) ....................... 19 containers │
│  ├─ SocDNA, PrefDNA .......................... 16 each       │
│  └─ 11 more namespaces ...................... 12-14 each    │
│                                                               │
│  Total: 422 containers, 358 edges                           │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                    Core Components                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Registry (dna_registry.json)                                │
│  ├─ Container definitions with metadata                      │
│  ├─ Versioning, status lifecycle, provenance                │
│  └─ Validation rules, population stats                       │
│                                                               │
│  Graph (dna_graph.jsonl)                                     │
│  ├─ Edge storage (is_a, part_of, correlates_with, etc.)    │
│  ├─ Fast traversal (ancestors, descendants)                 │
│  └─ Correlation strengths and evidence                      │
│                                                               │
│  Validation (registry_linter.py)                             │
│  ├─ Schema compliance                                        │
│  ├─ Referential integrity                                    │
│  ├─ Cycle detection                                          │
│  └─ 8 validation categories                                  │
│                                                               │
│  Generation (dna_generator.py)                               │
│  ├─ Deterministic rules (18 namespaces)                     │
│  ├─ Family explosion (HairDNA → Color, Length, Texture)    │
│  └─ Hierarchical relationships                               │
│                                                               │
│  Curiosity (curiosity_engine.py)                             │
│  ├─ RR integration (Curiosity = 100 - RR)                   │
│  ├─ Priority scoring (trait + container + missing)          │
│  └─ Agenda generation for AI coaches                         │
│                                                               │
│  API (core/api.py)                                           │
│  ├─ GET /ontology/registry                                   │
│  ├─ GET /ontology/container/:path                            │
│  ├─ GET /ontology/namespace/:ns                              │
│  ├─ GET /ontology/search?q=term                              │
│  ├─ GET /curiosity/:user_id                                  │
│  └─ GET /curiosity/:user_id/map                              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
ReDNACoreDemo/
├── core/
│   ├── ontology/
│   │   ├── namespaces.yaml ................... 18 namespace definitions
│   │   ├── dna_registry.json ................ 422 containers (~120KB)
│   │   ├── dna_registry.schema.json ......... JSON Schema validation
│   │   ├── dna_graph.jsonl .................. 358 edges (~35KB)
│   │   ├── dna_linker.py .................... Graph extraction/query
│   │   └── ontology_migrations/ ............. (future) Version migrations
│   │
│   ├── validation/
│   │   └── registry_linter.py ............... 8 validation categories
│   │
│   ├── generation/
│   │   └── dna_generator.py ................. Deterministic generation
│   │
│   ├── curiosity/
│   │   └── curiosity_engine.py .............. RR-integrated scoring
│   │
│   ├── rr_per_trait.py ...................... Per-trait RR calculator
│   ├── rr_aggregation.py .................... Container/overall RR
│   ├── rr_distribution_builder.py ........... Population distributions
│   ├── api.py ............................... REST API (+6 endpoints)
│   └── ...
│
├── data/
│   ├── population_distributions/ ............ RR histograms (12 files)
│   └── users/<user_id>/resolved.json ........ User trait data
│
├── docs/
│   ├── CONTAINER_EXPLOSION_INDEX.md ......... This file
│   ├── PHASE_A_COMPLETION.md ................ Phase A report
│   ├── ONTOLOGY_OVERVIEW.md ................. System overview
│   ├── RR_SYSTEM_INDEX.md ................... RR documentation hub
│   ├── RR_ARCHITECTURE_MULTILEVEL.md ........ Multi-level RR design
│   ├── RR_IMPLEMENTATION_REFINEMENTS.md ..... RR algorithms
│   ├── RR_QUICK_REFERENCE.md ................ Commands cheat sheet
│   └── ...
│
└── tests/
    ├── test_rr_per_trait.py ................. RR unit tests
    └── test_rr_integration.py ............... End-to-end tests
```

---

## Phase Roadmap

### Phase A: 1,000 Containers (Seed: 422) ✅ COMPLETE
**Duration**: 2-3 days
**Status**: Complete (October 6, 2025)

**Delivered**:
- ✅ 18 namespaces defined
- ✅ 422 containers generated (seed for 1k+)
- ✅ JSON Schema validation
- ✅ Registry linter (0 errors)
- ✅ Graph storage (358 edges)
- ✅ Curiosity engine (RR-integrated)
- ✅ 6 API endpoints
- ✅ Complete documentation

**Acceptance Criteria**:
- ✅ Linter passes with 0 violations
- ✅ API endpoints functional
- ✅ Curiosity engine tested
- ✅ Documentation complete
- ✅ Performance <150ms (50ms achieved)

---

### Phase B: 10,000 Containers ⏳ NEXT
**Duration**: 1-2 weeks (estimated)
**Status**: Planning

**Goals**:
- 🎯 Scale to 10,000 containers
- 🎯 AI shadow proposal system
- 🎯 Cross-product generation (Color × Shade)
- 🎯 Statistical correlation inference
- 🎯 Ontology explorer UI
- 🎯 Performance optimization

**Key Components**:
1. **Policy Gate Framework**
   - Safety checks (no sensitive data leaks)
   - Confidence thresholds (AI proposals must meet quality bar)
   - Human approval workflow
   - Audit trail for all AI additions

2. **Cross-Product Generator**
   - Cartesian product rules (e.g., HairColor × Shade = 6×4 = 24 containers)
   - Auto-expansion for multi-dimensional traits
   - Validation to prevent combinatorial explosion

3. **Correlation Inference**
   - Calculate statistical correlations from population data
   - Add `correlates_with` edges to graph
   - Strength thresholds (only add if r > 0.5)

4. **Ontology Explorer UI**
   - Tree view (expand/collapse)
   - Search and filtering
   - Curiosity heat map
   - Real-time statistics

**Acceptance Criteria**:
- 10,000 containers generated
- AI shadow system functional (with human approval gate)
- Graph includes correlation edges
- UI loads ontology <200ms
- Linter passes for all 10k containers

---

### Phase C: 100,000 Containers ⏳ FUTURE
**Duration**: 3-4 weeks (estimated)
**Status**: Design phase

**Goals**:
- Scale to 100,000 containers
- Auto-expansion from user feedback
- Residual variance catchers (fine-grained traits for edge cases)
- Multi-level curiosity maps
- Performance <300ms load time

**Key Components**:
- User feedback loop (suggest missing traits)
- Residual variance analysis (identify unexplained variance)
- Database backend (PostgreSQL with JSONB)
- Distributed validation (parallel linting)

---

### Phase D: 1,000,000 Containers ⏳ RESEARCH
**Duration**: 6-8 weeks (estimated)
**Status**: Research phase

**Goals**:
- Scale to 1,000,000 containers
- Federated ontology (multiple data sources)
- AI-native discovery (LLM-driven trait identification)
- Real-time updates (streaming ontology changes)

**Key Components**:
- Graph database (Neo4j or TigerGraph)
- Federated learning for correlations
- LLM integration for trait discovery
- Event-driven architecture

---

## Quick Start Commands

### Validate Registry
```bash
python3 core/validation/registry_linter.py core/ontology/dna_registry.json
```

### Generate/Expand Containers
```bash
python3 core/generation/dna_generator.py \
  --namespaces core/ontology/namespaces.yaml \
  --output core/ontology/dna_registry.json \
  --target 1000
```

### Extract Graph Edges
```bash
python3 core/ontology/dna_linker.py \
  --registry core/ontology/dna_registry.json \
  --stats
```

### Generate Curiosity Agenda
```bash
python3 core/curiosity/curiosity_engine.py \
  --user-id bstest \
  --top-n 20 \
  --min-curiosity 50
```

### Test API Endpoints
```bash
# Get full registry
curl http://localhost:8000/ontology/registry

# Search containers
curl http://localhost:8000/ontology/search?q=hair

# Get curiosity agenda
curl http://localhost:8000/curiosity/bstest?top_n=10
```

---

## Key Concepts

### Container
A node in the DNA ontology representing a trait category or attribute.

**Example**: `PaDNA.HairDNA.ColorDNA`

### Edge Types
- **is_a**: Hierarchical (ColorDNA is_a HairDNA)
- **part_of**: Compositional (NoseDNA part_of FaceDNA)
- **derived_from**: Computational (AgeDNA derived_from WrinklesDNA)
- **correlates_with**: Statistical (HairColor ↔ SkinTone, r=0.68)
- **contradicts**: Mutually exclusive (Bald ⊥ LongHair)

### Curiosity Economy
**Formula**: `Curiosity = 100 - RR`

High curiosity (low RR) traits get priority attention from AI coaches.

### RR (Refinement Rating)
0-100 percentile showing how refined a user's trait is compared to the population.
- RR = 0: No data (highest curiosity)
- RR = 50: Average refinement
- RR = 95: Highly refined (low curiosity)

### AI Shadow
AI proposes new containers without auto-write. Proposals go through policy gates for safety, evidence, and human approval before being added to the registry.

### Policy Gate
Governance layer with:
- Safety checks (no PII, sensitive data leaks)
- Confidence thresholds (AI must be >80% confident)
- Human approval workflow
- Audit trail

---

## Integration Points

### 1. Holistic Review
When holistic review runs:
- Calculates per-trait RR (percentile)
- Derives container-level RR (weighted average)
- Updates curiosity scores (100 - RR)
- Identifies missing containers from registry

### 2. AI Coaches
Coaches use curiosity agendas:
```
"I notice your CogDNA.LearningDNA has high curiosity (85).
Let's explore your learning style preferences..."
```

### 3. UI Display
Frontend can:
- Fetch ontology structure from `/ontology/registry`
- Display trait hierarchy
- Color-code by curiosity (red = high, green = low)
- Show missing containers as exploration opportunities

### 4. Data Collection
Priority-driven data collection:
- AI coaches focus on high-curiosity containers
- User interactions generate new trait data
- RR updates → curiosity updates → agenda updates

---

## Performance Benchmarks

### Current (422 Containers)
- Registry load: ~5ms
- Graph load: ~3ms
- Linter validation: ~50ms
- Curiosity agenda: ~100ms
- API response: 10-50ms

### Target (Phase B - 10,000 Containers)
- Registry load: <50ms
- Graph load: <20ms
- Linter validation: <200ms
- Curiosity agenda: <150ms
- API response: <100ms

### Target (Phase C - 100,000 Containers)
- Registry load: <100ms (with lazy loading)
- Graph load: <50ms (with indexing)
- Linter validation: <500ms (parallel)
- Curiosity agenda: <200ms (cached)
- API response: <150ms (database backend)

---

## Development Workflow

### Adding New Containers (Manual)
1. Edit `core/ontology/dna_registry.json`
2. Add container following schema
3. Run linter: `python3 core/validation/registry_linter.py core/ontology/dna_registry.json`
4. Extract edges: `python3 core/ontology/dna_linker.py --registry core/ontology/dna_registry.json`
5. Commit with changelog entry

### Adding New Expansion Rules
1. Edit `core/generation/dna_generator.py`
2. Add to `_get_family_children()` method
3. Regenerate registry: `python3 core/generation/dna_generator.py ...`
4. Validate with linter
5. Test with curiosity engine

### Updating Namespaces
1. Edit `core/ontology/namespaces.yaml`
2. Update naming patterns, max_depth, top_families
3. Regenerate registry
4. Validate with linter

### Testing Changes
```bash
# Run RR integration tests
python3 tests/test_rr_integration.py

# Validate registry
python3 core/validation/registry_linter.py core/ontology/dna_registry.json

# Test curiosity engine
python3 core/curiosity/curiosity_engine.py --user-id bstest --top-n 10
```

---

## Troubleshooting

### Linter Errors
**Error**: "Container path does not match namespace pattern"
**Fix**: Check `namespaces.yaml` naming_pattern regex. Ensure pattern allows top-level containers with `*` instead of `+`.

**Error**: "Cycle detected"
**Fix**: Check `parent_containers` for circular references. Use `dna_linker.py` to trace cycles.

**Error**: "Dependency not found"
**Fix**: Check that all dependencies exist in registry. Use `--stats` to see unique nodes.

### Curiosity Engine Errors
**Error**: "No distribution found for trait"
**Fix**: Run `POST /rr/rebuild_distributions` to build population distributions.

**Error**: "User not found"
**Fix**: Check that user exists in `data/users/<user_id>/resolved.json`.

### API Errors
**Error**: "Registry not found"
**Fix**: Ensure `core/ontology/dna_registry.json` exists. Regenerate if missing.

**Error**: "500 Internal Server Error"
**Fix**: Check logs in `.run/ucnrr.log` for stack traces.

---

## Contributing

### Code Style
- Python: PEP 8 (black formatter)
- Type hints required for all functions
- Docstrings for all public methods
- Comments for complex logic

### Testing
- Unit tests for all new functions
- Integration tests for end-to-end workflows
- Linter must pass before committing
- All tests must pass

### Documentation
- Update relevant docs for all changes
- Add inline comments for complex algorithms
- Update this index when adding new docs

---

## Support & Contact

**Documentation Issues**: File issue on GitHub with "docs:" prefix
**Bug Reports**: File issue with reproduction steps
**Feature Requests**: File issue with "enhancement:" prefix
**Questions**: Check docs first, then file issue with "question:" prefix

---

## Change Log

### October 6, 2025 - Phase A Complete
- Initial ontology infrastructure (422 containers)
- 18 namespaces defined
- Registry validation system
- Graph storage format
- Curiosity engine
- 6 API endpoints
- Complete documentation

---

## License

© 2025 ReDNA. All rights reserved.
