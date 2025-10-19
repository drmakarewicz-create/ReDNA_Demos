# Ontology V5 API Usage Examples

This document provides practical examples for using the new Ontology V5 REST API endpoints.

---

## Prerequisites

Ensure the core service is running:
```bash
# Start core service (port 8015)
bash scripts/start_all_services.sh
```

Verify service is up:
```bash
curl http://localhost:8015/health
```

---

## Example 1: Get Ontology Summary

Get high-level statistics about the ontology.

```bash
curl http://localhost:8015/ontology/v5/summary | jq
```

**Expected Response:**
```json
{
  "ok": true,
  "version": "5.0.0",
  "containers": {
    "total": 2615,
    "by_namespace": {
      "SkillDNA": 367,
      "BehDNA": 273,
      "CogDNA": 255,
      "MetaDNA": 240,
      "ProfDNA": 226,
      "PrefDNA": 212,
      "SocDNA": 191,
      "PsyDNA": 180,
      "HistDNA": 160,
      "EmDNA": 151,
      "PaDNA": 120,
      "EnvDNA": 80,
      "HealthDNA": 80,
      "RoDNA": 80
    }
  },
  "edges": {
    "total": 49342,
    "semantic": 40031,
    "hierarchy": 2601,
    "cross_namespace": 6710
  },
  "avg_edges_per_container": 18.87
}
```

---

## Example 2: Get Specific Container

Retrieve details about a specific container.

```bash
# Example: Get SkillDNA container
curl "http://localhost:8015/ontology/v5/container/SkillDNA" | jq
```

**Expected Response:**
```json
{
  "ok": true,
  "container": {
    "path": "SkillDNA",
    "namespace": "SkillDNA",
    "id": "...",
    "description": "Skills and competencies",
    "tags": ["namespace", "skills"],
    "parent_containers": []
  },
  "related_count": 50,
  "edges": [
    {
      "to": "SkillDNA.Programming.Python",
      "type": "correlates_with",
      "confidence": 0.85,
      "direction": "outgoing"
    }
  ]
}
```

---

## Example 3: Find Related Containers

Discover containers related to a given path via the correlation network.

```bash
# Get top 10 related containers with min 0.5 confidence
curl "http://localhost:8015/ontology/v5/related/SkillDNA.Programming.Python?limit=10&min_confidence=0.5" | jq
```

**Query Parameters:**
- `limit` (default: 20, max: 100) - Number of results
- `min_confidence` (default: 0.0, range: 0.0-1.0) - Minimum confidence

**Expected Response:**
```json
{
  "ok": true,
  "container_path": "SkillDNA.Programming.Python",
  "related_count": 10,
  "related": [
    {
      "container": {
        "path": "SkillDNA.Programming.JavaScript",
        "namespace": "SkillDNA",
        "description": "JavaScript programming skills",
        "tags": ["skill", "programming", "javascript"]
      },
      "edge_type": "correlates_with",
      "confidence": 0.87,
      "direction": "outgoing"
    },
    {
      "container": {
        "path": "SkillDNA.Programming.WebDevelopment",
        "namespace": "SkillDNA",
        "description": "Web development expertise",
        "tags": ["skill", "web", "development"]
      },
      "edge_type": "correlates_with",
      "confidence": 0.75,
      "direction": "incoming"
    }
  ]
}
```

---

## Example 4: Search Containers

Search across all containers by path, description, or tags.

```bash
# Basic search
curl "http://localhost:8015/ontology/v5/search?q=python" | jq

# Search with namespace filter
curl "http://localhost:8015/ontology/v5/search?q=leadership&namespace=BehDNA&limit=5" | jq
```

**Query Parameters:**
- `q` (required, min 2 chars) - Search query
- `namespace` (optional) - Filter by namespace
- `limit` (default: 50, max: 500) - Max results

**Expected Response:**
```json
{
  "ok": true,
  "query": "leadership",
  "namespace_filter": "BehDNA",
  "count": 5,
  "results": [
    {
      "path": "BehDNA.Leadership.TeamManagement",
      "namespace": "BehDNA",
      "description": "Team leadership and management behaviors",
      "tags": ["behavior", "leadership", "management"]
    },
    {
      "path": "BehDNA.Leadership.DecisionMaking",
      "namespace": "BehDNA",
      "description": "Leadership decision-making patterns",
      "tags": ["behavior", "leadership", "decisions"]
    }
  ]
}
```

---

## Example 5: Integration with Frontend

**JavaScript/TypeScript Example:**

```typescript
// Fetch ontology summary
async function getOntologySummary() {
  const response = await fetch('http://localhost:8015/ontology/v5/summary');
  const data = await response.json();
  return data;
}

// Get related containers
async function getRelatedContainers(path: string, minConfidence = 0.5) {
  const url = new URL('http://localhost:8015/ontology/v5/related/' + encodeURIComponent(path));
  url.searchParams.set('limit', '20');
  url.searchParams.set('min_confidence', minConfidence.toString());

  const response = await fetch(url.toString());
  const data = await response.json();
  return data.related;
}

// Search containers
async function searchContainers(query: string, namespace?: string) {
  const url = new URL('http://localhost:8015/ontology/v5/search');
  url.searchParams.set('q', query);
  if (namespace) {
    url.searchParams.set('namespace', namespace);
  }

  const response = await fetch(url.toString());
  const data = await response.json();
  return data.results;
}

// Usage
const summary = await getOntologySummary();
console.log(`Total containers: ${summary.containers.total}`);
console.log(`Total edges: ${summary.edges.total}`);

const related = await getRelatedContainers('SkillDNA.Programming.Python', 0.7);
console.log(`Found ${related.length} related containers`);

const results = await searchContainers('python', 'SkillDNA');
console.log(`Search found ${results.length} results`);
```

---

## Example 6: Python Client

**Python Example:**

```python
import requests

BASE_URL = "http://localhost:8015"

def get_summary():
    """Get ontology summary."""
    response = requests.get(f"{BASE_URL}/ontology/v5/summary")
    return response.json()

def get_container(path):
    """Get specific container."""
    response = requests.get(f"{BASE_URL}/ontology/v5/container/{path}")
    return response.json()

def get_related(path, limit=20, min_confidence=0.0):
    """Get related containers."""
    params = {'limit': limit, 'min_confidence': min_confidence}
    response = requests.get(f"{BASE_URL}/ontology/v5/related/{path}", params=params)
    return response.json()

def search_containers(query, namespace=None, limit=50):
    """Search containers."""
    params = {'q': query, 'limit': limit}
    if namespace:
        params['namespace'] = namespace
    response = requests.get(f"{BASE_URL}/ontology/v5/search", params=params)
    return response.json()

# Usage examples
if __name__ == "__main__":
    # Get summary
    summary = get_summary()
    print(f"Total containers: {summary['containers']['total']}")
    print(f"Total edges: {summary['edges']['total']}")

    # Get container
    container = get_container("SkillDNA.Programming.Python")
    print(f"\nContainer: {container['container']['path']}")
    print(f"Related edges: {container['related_count']}")

    # Get related
    related = get_related("SkillDNA.Programming.Python", limit=10, min_confidence=0.5)
    print(f"\nFound {related['related_count']} related containers:")
    for item in related['related'][:3]:
        print(f"  - {item['container']['path']} (confidence: {item['confidence']:.2f})")

    # Search
    results = search_containers("leadership", namespace="BehDNA", limit=5)
    print(f"\nSearch results: {results['count']} found")
    for result in results['results'][:3]:
        print(f"  - {result['path']}")
```

---

## Example 7: Building a Graph Visualization

**Using the API to build a graph:**

```javascript
// Fetch container and build graph
async function buildGraph(rootPath, maxDepth = 2) {
  const nodes = [];
  const edges = [];
  const visited = new Set();

  async function traverse(path, depth) {
    if (depth > maxDepth || visited.has(path)) return;
    visited.add(path);

    // Get container details
    const response = await fetch(
      `http://localhost:8015/ontology/v5/container/${encodeURIComponent(path)}`
    );
    const data = await response.json();

    // Add node
    nodes.push({
      id: path,
      label: path.split('.').pop(),
      namespace: data.container.namespace,
      description: data.container.description
    });

    // Add edges and traverse
    for (const edge of data.edges.slice(0, 10)) { // Limit to top 10
      edges.push({
        source: path,
        target: edge.to,
        confidence: edge.confidence,
        type: edge.type
      });

      await traverse(edge.to, depth + 1);
    }
  }

  await traverse(rootPath, 0);
  return { nodes, edges };
}

// Usage with D3.js or Cytoscape.js
const graph = await buildGraph('SkillDNA.Programming.Python', 2);
console.log(`Graph has ${graph.nodes.length} nodes and ${graph.edges.length} edges`);
```

---

## Performance Notes

- **First Request:** ~2 seconds (loads correlation engine + 49,342 edges)
- **Subsequent Requests:** < 10ms (cached engine)
- **Memory Usage:** ~150MB (correlation engine in memory)
- **Recommended:** Pre-warm cache on server startup for production

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Container not found: InvalidPath"
}
```

**Common HTTP Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Container or registry not found
- `422 Unprocessable Entity` - Invalid query parameters
- `500 Internal Server Error` - Server error

---

## Next Steps

1. **Phase 8C: DevX Explorer UI** - Visual interface for exploring the ontology
2. **Performance Optimization** - Consider SQLite cache for even faster lookups
3. **Advanced Queries** - Add filtering by confidence, edge type, etc.
4. **Batch Endpoints** - Support fetching multiple containers in one request

---

*Generated: 2025-10-11*
*For implementation details, see [PHASE8B1_API_POLISH_COMPLETE.md](PHASE8B1_API_POLISH_COMPLETE.md)*
