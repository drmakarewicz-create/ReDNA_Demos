# DNA Ontology Overview

## Purpose

The ReDNA DNA Ontology is a hierarchical, graph-native knowledge system for organizing and relating personality traits, physical characteristics, behaviors, and other personal attributes. It supports:

- **Scalable growth**: 1k → 10k → 100k → 1M containers
- **AI-upgradable**: AI can propose additions/edits with human oversight
- **Curiosity-driven**: Low RR (high curiosity) traits get priority attention
- **Privacy-first**: Sensitivity markings, consent requirements, k-anonymity
- **Deterministic generation**: Rules-based expansion with AI shadow proposals

## Architecture

### Core Components

```
core/ontology/
├── namespaces.yaml              # 18 top-level DNA namespaces + rules
├── dna_registry.json            # Canonical container index (~300+ containers)
├── dna_registry.schema.json     # JSON Schema for validation
└── dna_graph.jsonl              # Edge definitions (planned)

core/validation/
└── registry_linter.py           # Schema + business rule validation

core/generation/
└── dna_generator.py             # Deterministic container generation

core/curiosity/
└── curiosity_engine.py          # RR-integrated curiosity scoring
```

### Three-Layer Model

1. **Namespaces** (18 top-level umbrellas)
   - PaDNA: Physical Appearance
   - PsyDNA: Psychological traits
   - EmDNA: Emotional patterns
   - CogDNA: Cognitive abilities
   - SocDNA: Social behaviors
   - ReDNA: Relationship patterns
   - HeritDNA: Cultural heritage
   - HistDNA: Life history
   - PrefDNA: Preferences
   - SkillDNA: Abilities
   - BehDNA: Behavioral patterns
   - MetaDNA: Self-awareness
   - BioDNA: Biological health
   - FinDNA: Financial patterns
   - FamilyDNA: Family dynamics
   - CareerDNA: Professional life
   - GoalsDNA: Aspirations
   - HealthDNA: Physical/mental health

2. **Containers** (hierarchical nodes)
   - Format: `PaDNA.HairDNA.ColorDNA`
   - Versioned: `.v1`, `.v2`, etc.
   - Lifecycle: prototype → candidate → stable → deprecated
   - Status-dependent: AI can only edit certain statuses

3. **Traits** (leaf-level observations)
   - Stored in user `resolved.json`
   - Each has UCN (confidence 0-1000) and RR (percentile 0-100)
   - Example: `{"PaDNA.HairDNA.Color": {"value": "Blonde", "ucn": 950, "rr": 95.8}}`

## Key Concepts

### Container Record Format

Every container in `dna_registry.json` follows this schema:

```json
{
  "id": "PaDNA.HairDNA.ColorDNA.v1",
  "namespace": "PaDNA",
  "path": "PaDNA.HairDNA.ColorDNA",
  "version": 1,
  "status": "stable",
  "description": "Hair color characteristics and attributes",
  "inputs": [],
  "outputs": [],
  "ucn_weight_hint": 0.01,
  "dependencies": [],
  "correlates_with": [
    {
      "path": "PaDNA.SkinDNA.ToneDNA",
      "strength": 0.68,
      "evidence": "Statistical correlation from population data"
    }
  ],
  "contradicts": [],
  "sensitive": false,
  "consent_required": false,
  "ai_upgradable": true,
  "discovery": {
    "method": "deterministic_generation",
    "confidence": 1.0,
    "evidence": "Generated from ontology expansion rules",
    "proposer": "dna_generator.py"
  },
  "parent_containers": [
    {
      "path": "PaDNA.HairDNA",
      "edge_type": "is_a"
    }
  ],
  "tags": ["pa", "hair", "color"],
  "created_at": "2025-10-06T...",
  "updated_at": "2025-10-06T...",
  "created_by": "system_generator",
  "changelog": [...]
}
```

### Edge Types

Containers relate via typed edges:

- **is_a**: Taxonomic hierarchy (ColorDNA is_a HairDNA)
- **part_of**: Compositional (NoseDNA part_of FaceDNA)
- **derived_from**: Computational dependency (AgeDNA derived_from WrinklesDNA)
- **correlates_with**: Statistical correlation (HairColor ↔ SkinTone, 0.68 strength)
- **contradicts**: Mutually exclusive (Bald ⊥ LongHair)

### Status Lifecycle

```
prototype → candidate → stable → deprecated
```

- **prototype**: Experimental, no approval required
- **candidate**: Validated, requires approval to promote
- **stable**: Production-ready, widely used
- **deprecated**: Archived, no longer recommended

Only valid transitions allowed (enforced by linter).

### Curiosity Economy

**Formula**: `Curiosity = 100 - RR`

- RR = 0 → Curiosity = 100 (no data, highest priority)
- RR = 95 → Curiosity = 5 (highly refined, low priority)

The curiosity engine generates priority-ordered agendas:

```bash
python3 core/curiosity/curiosity_engine.py --user-id alice --top-n 20
```

AI coaches use these agendas to focus on high-curiosity gaps.

## Privacy & Sensitivity

### Sensitive Namespaces

These require explicit consent and privacy protection:

- PsyDNA, EmDNA, SocDNA, ReDNA
- HeritDNA, HistDNA, BioDNA, FinDNA
- FamilyDNA, HealthDNA

### K-Anonymity

Population distributions enforce k≥5 (minimum 5 users per bin) to prevent re-identification.

### Consent Tracking

Containers can require explicit user consent via `consent_required: true`.

## Generation Rules

### Deterministic Expansion

The generator uses domain knowledge to expand families:

```python
"HairDNA" → ["ColorDNA", "LengthDNA", "TextureDNA", "VolumeDNA", "StyleDNA"]
"ColorDNA" → ["HueDNA", "SaturationDNA", "BrightnessDNA", "ShadeVariantDNA"]
```

Run generator:

```bash
python3 core/generation/dna_generator.py \
  --namespaces core/ontology/namespaces.yaml \
  --output core/ontology/dna_registry.json \
  --target 1000
```

### AI Shadow Proposals

(Phase B+) AI can propose new containers without auto-write:

1. AI identifies gap (e.g., "Eye-specific mascara preference")
2. Generates proposal: `PaDNA.MakeupDNA.EyeMakeupDNA.MascaraStyleDNA`
3. Policy gate checks: safety, evidence threshold, human approval
4. If approved → added to registry with `discovery.method = "ai_shadow_proposal"`

## Validation

### Linter Checks

```bash
python3 core/validation/registry_linter.py core/ontology/dna_registry.json
```

Validates:
- ✅ JSON Schema compliance
- ✅ Unique IDs and paths
- ✅ Referential integrity (all dependencies exist)
- ✅ No cycles in hierarchical edges
- ✅ Namespace naming patterns
- ✅ Status transition rules
- ✅ Privacy/sensitivity settings
- ✅ Metadata consistency

### Expected Output

```
✅ Registry validation passed with no errors or warnings
```

or

```
❌ VALIDATION FAILED
[ERROR] [integrity] Dependency not found: PaDNA.InvalidDNA
[WARNING] [privacy] Container in sensitive namespace not marked sensitive
```

## Integration Points

### 1. Holistic Review

When holistic review runs, it:
- Calculates per-trait RR (percentile)
- Derives container-level RR (weighted average)
- Updates curiosity scores (100 - RR)
- Identifies missing containers from registry

### 2. UI Display

Frontend can:
- Fetch ontology structure from registry
- Display trait hierarchy
- Color-code by curiosity (red = high, green = low)
- Show missing containers as exploration opportunities

### 3. AI Coach Prompts

Coaches use curiosity agendas:

```
"I notice your CogDNA.LearningDNA has high curiosity (85).
Let's explore your learning style preferences..."
```

## Phase Roadmap

### Phase A: 1,000 containers (Current) ✅
- [x] Namespaces defined (18)
- [x] Schema created
- [x] Linter working
- [x] Generator producing ~300 seed containers
- [x] Curiosity engine integrated
- [ ] Graph storage (dna_graph.jsonl)
- [ ] Policy gate framework
- [ ] API endpoints
- [ ] UI hooks

### Phase B: 10,000 containers (1-2 weeks)
- [ ] AI shadow proposals
- [ ] Cross-product generation (Color × Shade)
- [ ] Statistical inference from correlations
- [ ] Ontology explorer UI

### Phase C: 100,000 containers (3-4 weeks)
- [ ] Auto-expansion from user feedback
- [ ] Residual variance catchers
- [ ] Multi-level curiosity maps
- [ ] Performance optimization (<150ms load)

### Phase D: 1,000,000 containers (6-8 weeks)
- [ ] Distributed ontology storage
- [ ] Federated learning for correlations
- [ ] AI-native container discovery
- [ ] Real-time ontology updates

## Quick Start

### Generate Seed Registry

```bash
cd ReDNACoreDemo
python3 core/generation/dna_generator.py \
  --namespaces core/ontology/namespaces.yaml \
  --output core/ontology/dna_registry.json \
  --target 1000
```

### Validate Registry

```bash
python3 core/validation/registry_linter.py core/ontology/dna_registry.json
```

### Generate Curiosity Agenda

```bash
python3 core/curiosity/curiosity_engine.py --user-id alice --top-n 20
```

### Add New Container (Manual)

1. Edit `core/ontology/dna_registry.json`
2. Add container following schema
3. Run linter to validate
4. Commit with changelog entry

### Add New Container (AI Shadow - Future)

1. AI proposes container via API
2. Policy gate evaluates (safety, evidence, threshold)
3. Human reviews and approves
4. System adds to registry with provenance

## API Endpoints (Planned)

```
GET  /ontology/registry           # Full registry
GET  /ontology/container/:path    # Single container
GET  /ontology/namespace/:ns      # All containers in namespace
POST /ontology/propose            # AI shadow proposal
GET  /curiosity/:user_id          # Curiosity agenda
GET  /ontology/search?q=hair      # Search containers
```

## Files Reference

| File | Purpose | Size |
|------|---------|------|
| `namespaces.yaml` | Namespace definitions + rules | ~10KB |
| `dna_registry.json` | Container index | ~500KB (1k containers) |
| `dna_registry.schema.json` | JSON Schema | ~10KB |
| `registry_linter.py` | Validation logic | ~600 lines |
| `dna_generator.py` | Deterministic generation | ~500 lines |
| `curiosity_engine.py` | RR-integrated scoring | ~500 lines |

## Next Steps

See:
- [DNA_REGISTRY_SCHEMA.md](./DNA_REGISTRY_SCHEMA.md) - Detailed schema documentation
- [CONTAINER_GENERATION_RULES.md](./CONTAINER_GENERATION_RULES.md) - Generation algorithms
- [CURIOSITY_ENGINE.md](./CURIOSITY_ENGINE.md) - Curiosity scoring details
- [POLICY_GATE_README.md](./POLICY_GATE_README.md) - AI shadow governance (planned)
