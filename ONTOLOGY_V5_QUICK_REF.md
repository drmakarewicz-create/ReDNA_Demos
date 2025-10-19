# Ontology V5 Quick Reference Card

**Version:** 5.0.0 | **Status:** ✅ Production Ready

---

## 📊 At a Glance

```
Containers:  2,615 (14 namespaces)
Edges:       49,342 (avg 18.87 per container)
API Latency: <10ms (cached)
Memory:      ~150MB
```

---

## 🚀 Quick Start

```bash
# Start service
bash scripts/start_all_services.sh

# Test API
curl http://localhost:8015/ontology/v5/summary
```

---

## 📡 API Endpoints

### 1. Summary
```bash
GET /ontology/v5/summary
→ Returns: Total containers, edges, namespace distribution
```

### 2. Get Container
```bash
GET /ontology/v5/container/{path}
→ Returns: Container details + related edges
```

### 3. Find Related
```bash
GET /ontology/v5/related/{path}?limit=20&min_confidence=0.5
→ Returns: Related containers sorted by confidence
```

### 4. Search
```bash
GET /ontology/v5/search?q=python&namespace=SkillDNA&limit=50
→ Returns: Matching containers
```

---

## 💻 Code Snippets

### Python
```python
from ReDNACoreDemo.core.ontology.correlation_engine import create_correlation_engine

engine = create_correlation_engine()
related = engine.get_related_containers("SkillDNA.Programming.Python", limit=20)
```

### JavaScript
```javascript
const summary = await fetch('http://localhost:8015/ontology/v5/summary').then(r => r.json());
console.log(`${summary.containers.total} containers`);
```

### cURL
```bash
# Summary
curl http://localhost:8015/ontology/v5/summary | jq

# Container
curl "http://localhost:8015/ontology/v5/container/SkillDNA" | jq

# Related
curl "http://localhost:8015/ontology/v5/related/SkillDNA.Programming.Python?limit=10" | jq

# Search
curl "http://localhost:8015/ontology/v5/search?q=leadership&namespace=BehDNA" | jq
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `core/api.py:8660-8927` | API endpoints |
| `core/ontology/expansion_engine.py` | Container generation |
| `core/ontology/correlation_engine.py` | Edge network |
| `data/ontology/registry_v5/dna_registry_v5.json` | All containers |
| `data/ontology/edges_v5.jsonl` | All edges (49,342) |

---

## 🧪 Testing

```bash
# Run test suite
python3 test_ontology_v5_api.py

# Expected output:
# ✅ Correlation engine loads correctly
# ✅ Related container lookup works
# ✅ Namespace distribution computed
# ✅ Validation passed
# ALL TESTS PASSED ✅
```

---

## 🐛 Troubleshooting

**Problem:** API returns 404 for v5 endpoints
- **Solution:** Check service is running on port 8015
- **Check:** `curl http://localhost:8015/health`

**Problem:** Slow first request (~2 seconds)
- **Cause:** Correlation engine initialization
- **Solution:** Normal behavior, subsequent requests < 10ms

**Problem:** Container not found
- **Check:** Path is case-sensitive
- **Example:** `SkillDNA.Programming.Python` not `skilldna.programming.python`

---

## 📈 Performance Tips

1. **Cache warming:** First API call loads engine (~2s), then < 10ms
2. **Batch queries:** Use search endpoint for multiple lookups
3. **Namespace filtering:** Use namespace parameter to reduce search space
4. **Confidence threshold:** Use min_confidence to filter low-quality edges

---

## 🔗 Documentation

- Full guide: [ONTOLOGY_V5_API_USAGE_EXAMPLES.md](ONTOLOGY_V5_API_USAGE_EXAMPLES.md)
- Implementation: [PHASE8B1_API_POLISH_COMPLETE.md](PHASE8B1_API_POLISH_COMPLETE.md)
- Architecture: [ONTOLOGY_V5_COMPLETE_SUMMARY.md](ONTOLOGY_V5_COMPLETE_SUMMARY.md)

---

## 📊 Namespace Reference

| Namespace | Containers | Description |
|-----------|------------|-------------|
| SkillDNA | 367 | Skills and competencies |
| BehDNA | 273 | Behavioral patterns |
| CogDNA | 255 | Cognitive traits |
| MetaDNA | 240 | Meta-cognition |
| ProfDNA | 226 | Professional traits |
| PrefDNA | 212 | Preferences |
| SocDNA | 191 | Social patterns |
| PsyDNA | 180 | Psychological traits |
| HistDNA | 160 | Historical data |
| EmDNA | 151 | Emotional patterns |
| PaDNA | 120 | Personal attributes |
| EnvDNA | 80 | Environmental factors |
| HealthDNA | 80 | Health-related |
| RoDNA | 80 | Roles and responsibilities |

---

## ✅ Status

- **Phase 8A:** Expansion Core — ✅ Complete
- **Phase 8B:** Correlation Network — ✅ Complete
- **Phase 8B.1:** API Polish — ✅ Complete
- **Phase 8C:** DevX Explorer UI — 🔜 Next

---

**Last Updated:** 2025-10-11 | **Branch:** ontology_explosion_v2
