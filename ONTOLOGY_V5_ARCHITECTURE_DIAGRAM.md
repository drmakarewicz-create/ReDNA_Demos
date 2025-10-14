# Ontology V5 Architecture Diagram

**Version:** 5.0.0
**Last Updated:** 2025-10-11
**Status:** Production Ready ✅

---

## 🏗️ Full Stack Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                            │
│                   http://localhost:3000                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Ontology Explorer (React)                              │   │
│  │  /ontology-explorer                                     │   │
│  │                                                          │   │
│  │  ┌─────────────┬──────────────────┬──────────────────┐ │   │
│  │  │ Namespace   │  Search Results  │  Container       │ │   │
│  │  │ Sidebar     │  + Detail Modal  │  Statistics      │ │   │
│  │  │             │                  │                  │ │   │
│  │  │ • SkillDNA  │  [Search bar]    │  Total: 2,615    │ │   │
│  │  │   (367)     │                  │  Edges: 49,342   │ │   │
│  │  │ • BehDNA    │  Results:        │                  │ │   │
│  │  │   (273)     │  ┌──────────┐    │  Semantic: 81%   │ │   │
│  │  │ • CogDNA    │  │Container │    │  Hierarchy: 5%   │ │   │
│  │  │   (255)     │  │  Item    │    │  Cross-NS: 14%   │ │   │
│  │  │ • ...       │  └──────────┘    │                  │ │   │
│  │  └─────────────┴──────────────────┴──────────────────┘ │   │
│  │                                                          │   │
│  │  Features:                                               │   │
│  │  ✓ Real-time search (300ms debounce)                    │   │
│  │  ✓ Namespace filtering                                  │   │
│  │  ✓ Container detail modal                               │   │
│  │  ✓ Statistics panel                                     │   │
│  └────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              │ HTTP/REST                        │
│                              ▼                                  │
└─────────────────────────────────────────────────────────────────┘

                               │
                               │
                               ▼

┌─────────────────────────────────────────────────────────────────┐
│                        REST API LAYER                            │
│                   http://localhost:8015                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FastAPI Application (core/api.py)                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Ontology V5 Endpoints (Lines 8660-8927)              │   │
│  │                                                         │   │
│  │  GET /ontology/v5/summary                              │   │
│  │  ├─ Returns: Container counts, edge stats, version     │   │
│  │  └─ Response time: <50ms                               │   │
│  │                                                         │   │
│  │  GET /ontology/v5/container/{path}                     │   │
│  │  ├─ Returns: Container + related edges                 │   │
│  │  └─ Response time: <10ms (cached)                      │   │
│  │                                                         │   │
│  │  GET /ontology/v5/related/{path}                       │   │
│  │  ├─ Returns: Related containers by confidence          │   │
│  │  └─ Response time: <10ms (cached)                      │   │
│  │                                                         │   │
│  │  GET /ontology/v5/search?q={query}&namespace={ns}      │   │
│  │  ├─ Returns: Matching containers                       │   │
│  │  └─ Response time: <50ms                               │   │
│  └────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Correlation Engine Cache (Thread-Safe)                │   │
│  │                                                         │   │
│  │  _correlation_engine_cache (global)                    │   │
│  │  _correlation_engine_lock (threading.Lock)             │   │
│  │                                                         │   │
│  │  Lazy Initialization:                                  │   │
│  │  1. First API call triggers load (~2s)                 │   │
│  │  2. Loads 2,615 containers                             │   │
│  │  3. Loads 49,342 edges from JSONL                      │   │
│  │  4. Subsequent calls: <10ms (cached)                   │   │
│  │                                                         │   │
│  │  Memory: ~150MB                                        │   │
│  └────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
└─────────────────────────────────────────────────────────────────┘

                               │
                               │
                               ▼

┌─────────────────────────────────────────────────────────────────┐
│                       CORE ENGINE LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Correlation Engine                                     │   │
│  │  (core/ontology/correlation_engine.py)                 │   │
│  │                                                         │   │
│  │  Class: CorrelationEngine                              │   │
│  │                                                         │   │
│  │  Methods:                                               │   │
│  │  • __init__() - Load registry + edges                  │   │
│  │  • _load_registry() - Load v5 JSON                     │   │
│  │  • _load_edges() - Stream JSONL                        │   │
│  │  • compute_semantic_similarity() - TF-IDF + Jaccard    │   │
│  │  • get_related_containers() - Find neighbors           │   │
│  │  • validate() - Check integrity                        │   │
│  │                                                         │   │
│  │  Data Structures:                                       │   │
│  │  • containers: Dict[path, Container] (2,615 items)     │   │
│  │  • edges: List[Edge] (49,342 items)                    │   │
│  │  • edge_set: Set[Tuple] (deduplication)                │   │
│  │  • containers_by_namespace: Dict[ns, List]             │   │
│  └────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Expansion Engine                                       │   │
│  │  (core/ontology/expansion_engine.py)                   │   │
│  │                                                         │   │
│  │  Class: ExpansionEngine                                │   │
│  │                                                         │   │
│  │  Methods:                                               │   │
│  │  • generate_container() - Create new container         │   │
│  │  • compute_semantic_hash() - SHA256 deduplication      │   │
│  │  • add_container() - Add with duplicate check          │   │
│  │  • run_expansion() - Bulk generation                   │   │
│  │  • save_registry_v5() - Persist to disk                │   │
│  │                                                         │   │
│  │  Features:                                              │   │
│  │  • Pattern-based generation                            │   │
│  │  • Semantic hashing (prevents duplicates)              │   │
│  │  • Namespace indexing                                  │   │
│  │  • Validation framework                                │   │
│  └────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
└─────────────────────────────────────────────────────────────────┘

                               │
                               │
                               ▼

┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Registry V5                                            │   │
│  │  data/ontology/registry_v5/                            │   │
│  │                                                         │   │
│  │  dna_registry_v5.json (1.2MB)                          │   │
│  │  ├─ version: "5.0.0"                                   │   │
│  │  ├─ generated_at: "2025-10-11T..."                     │   │
│  │  ├─ containers: [ ... ] (2,615 items)                  │   │
│  │  └─ metadata: { ... }                                  │   │
│  │                                                         │   │
│  │  Container Structure:                                   │   │
│  │  {                                                      │   │
│  │    "id": "uuid",                                       │   │
│  │    "path": "SkillDNA.Programming.Python",              │   │
│  │    "namespace": "SkillDNA",                            │   │
│  │    "description": "...",                               │   │
│  │    "tags": ["skill", "programming"],                   │   │
│  │    "parent_containers": [...],                         │   │
│  │    "created_at": "2025-10-11T..."                      │   │
│  │  }                                                      │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Namespace Indices (JSONL)                             │   │
│  │  data/ontology/registry_v5/{Namespace}/                │   │
│  │                                                         │   │
│  │  SkillDNA/index.jsonl (367 containers)                 │   │
│  │  BehDNA/index.jsonl (273 containers)                   │   │
│  │  CogDNA/index.jsonl (255 containers)                   │   │
│  │  ... (14 namespaces total)                             │   │
│  │                                                         │   │
│  │  Purpose: Fast namespace-specific loading              │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Edge Network                                           │   │
│  │  data/ontology/edges_v5.jsonl (15MB)                   │   │
│  │                                                         │   │
│  │  Format: One JSON object per line                      │   │
│  │  Total: 49,342 edges                                   │   │
│  │                                                         │   │
│  │  Edge Structure:                                        │   │
│  │  {                                                      │   │
│  │    "from": "SkillDNA.Programming.Python",              │   │
│  │    "to": "SkillDNA.Programming.JavaScript",            │   │
│  │    "type": "correlates_with",                          │   │
│  │    "confidence": 0.87,                                 │   │
│  │    "evidence": "Semantic similarity",                  │   │
│  │    "metadata": {                                       │   │
│  │      "method": "semantic_similarity"                   │   │
│  │    },                                                   │   │
│  │    "generated_at": "2025-10-11T..."                    │   │
│  │  }                                                      │   │
│  │                                                         │   │
│  │  Breakdown:                                            │   │
│  │  • Semantic: 40,031 (81.1%)                            │   │
│  │  • Hierarchy: 2,601 (5.3%)                             │   │
│  │  • Cross-namespace: 6,710 (13.6%)                      │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow

### Search Flow

```
User Types Query
      │
      ▼
React Component (debounce 300ms)
      │
      ▼
fetch('/ontology/v5/search?q=python')
      │
      ▼
API Endpoint (api.py:8870)
      │
      ▼
_get_correlation_engine() [cached]
      │
      ▼
Search engine.containers (2,615 items)
      │
      ▼
Filter by query + namespace
      │
      ▼
Return results (JSON)
      │
      ▼
Display in UI (<500ms total)
```

### Container Detail Flow

```
User Clicks Container
      │
      ▼
setSelectedContainer(container)
      │
      ▼
Modal Opens with Details
      │
      │ (Optional: Load related)
      ▼
fetch('/ontology/v5/related/{path}')
      │
      ▼
engine.get_related_containers(path)
      │
      ▼
Filter edges by path
      │
      ▼
Sort by confidence
      │
      ▼
Return top 20
      │
      ▼
Display related list (<10ms)
```

---

## 📊 Performance Characteristics

### Cold Start (First API Call)

```
Time 0ms:    User request arrives
Time 0-50ms: Route to endpoint
Time 50ms:   Check cache (empty)
Time 50ms:   Acquire lock
Time 50ms:   Start engine initialization
             ├─ Load registry_v5.json (~500ms)
             ├─ Parse 2,615 containers (~200ms)
             ├─ Build indices (~100ms)
             ├─ Load edges_v5.jsonl (~800ms)
             ├─ Parse 49,342 edges (~300ms)
             └─ Build edge_set (~100ms)
Time 2000ms: Engine ready
Time 2000ms: Release lock
Time 2010ms: Process request
Time 2020ms: Return response

Total: ~2 seconds
```

### Warm (Cached) Requests

```
Time 0ms:   User request arrives
Time 0-5ms: Route to endpoint
Time 5ms:   Check cache (hit!)
Time 5-7ms: Process request (in-memory)
Time 7-9ms: Return response

Total: <10ms
```

---

## 🔧 Key Components

### 1. Expansion Engine

**Purpose:** Generate new containers systematically
**Algorithm:** Pattern-based + semantic hashing
**Output:** 2,615 containers (0 duplicates)

### 2. Correlation Engine

**Purpose:** Compute relationships between containers
**Algorithm:** Semantic similarity + hierarchy + cross-namespace
**Output:** 49,342 edges (avg confidence 0.641)

### 3. REST API

**Purpose:** Expose ontology data via HTTP
**Technology:** FastAPI with thread-safe caching
**Performance:** Sub-10ms (cached)

### 4. Visual Explorer

**Purpose:** User-friendly ontology browsing
**Technology:** React + Next.js
**Features:** Search, filter, detail views

---

## 🎯 Design Principles

1. **Lazy Loading:** Engine loads on first use (not startup)
2. **Thread Safety:** Global cache with lock for multi-worker
3. **Streaming:** JSONL enables incremental processing
4. **Caching:** In-memory cache for fast repeated access
5. **Deduplication:** Semantic hashing prevents duplicates

---

## 📈 Scaling Strategy

### Current (MVP)
- 2,615 containers
- 49,342 edges
- ~150MB memory
- Single-server deployment

### Future (8,000+ containers)
- Expand pattern files (4-6 hours curation)
- Increase edges proportionally (~150,000)
- Memory scales linearly (~400MB estimated)
- Consider sharding by namespace if needed

### Production Optimizations
- Pre-warm cache on startup
- SQLite index for sub-5ms queries
- Redis for distributed caching
- CDN for static registry data

---

**Document Version:** 1.0.0
**Last Updated:** 2025-10-11
**Architecture Status:** ✅ Production Ready
