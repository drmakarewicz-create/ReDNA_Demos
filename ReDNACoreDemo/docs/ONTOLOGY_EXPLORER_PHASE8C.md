# ReDNA Phase 8C: Ontology Explorer UI

**Status:** 🟡 In Progress
**Estimated Effort:** 4-6 hours
**Dependencies:** Phase 8A ✅, Phase 8B ✅, Phase 8B.1 ✅

---

## 🎯 Objective

Build a **visual ontology exploration interface** in the DevX environment that enables developers and users to:
- Search and filter the 2,615 containers
- Visualize the correlation network (49,342 edges)
- Explore container relationships interactively
- Export ontology data for analysis

---

## 📋 Requirements

### Functional Requirements

1. **Search Interface**
   - Text search across paths, descriptions, tags
   - Namespace filter dropdown
   - Real-time results (debounced)
   - Result count display

2. **Graph Visualization**
   - Interactive node-link diagram
   - Nodes: Containers (colored by namespace)
   - Edges: Correlations (thickness = confidence)
   - Pan, zoom, and drag interactions
   - Click node to view details

3. **Container Detail Panel**
   - Full container metadata
   - Related containers list (sorted by confidence)
   - Edge type badges
   - Copy path button

4. **Namespace Explorer**
   - Tree view of all namespaces
   - Container count per namespace
   - Click to filter by namespace

5. **Export Functionality**
   - Export current view as JSON
   - Export graph data for Cytoscape/Gephi
   - Copy container IDs to clipboard

### Non-Functional Requirements

1. **Performance**
   - Initial load < 2 seconds
   - Search results < 500ms
   - Graph rendering < 1 second (for 100 nodes)
   - Smooth 60fps interactions

2. **Responsiveness**
   - Works on desktop (1920x1080 and higher)
   - Collapsible panels for smaller screens
   - Keyboard shortcuts for common actions

3. **Accessibility**
   - Semantic HTML
   - ARIA labels
   - Keyboard navigation
   - Focus indicators

---

## 🎨 UI Design

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  DevX Top Bar                                                   │
├─────────────┬───────────────────────────────────┬───────────────┤
│             │                                   │               │
│  Namespace  │       Graph Visualization         │   Container   │
│  Tree       │                                   │   Details     │
│  (20%)      │           (50%)                   │   (30%)       │
│             │                                   │               │
│  • SkillDNA │   ┌─────┐                        │  Path:        │
│    (367)    │   │     │◄──────┐               │  SkillDNA...  │
│  • BehDNA   │   └──┬──┘       │               │               │
│    (273)    │      │          │               │  Description: │
│  • CogDNA   │      ▼          │               │  ...          │
│    (255)    │   ┌─────┐    ┌─────┐           │               │
│  ...        │   │     │────►│     │           │  Related (15):│
│             │   └─────┘    └─────┘           │  • BehDNA...  │
│             │                                   │  • CogDNA...  │
│             │                                   │  ...          │
├─────────────┴───────────────────────────────────┴───────────────┤
│  Search: [__________________]  Namespace: [All ▼]  Depth: [2▼] │
│  Found: 2,615 containers • 49,342 edges                        │
└─────────────────────────────────────────────────────────────────┘
```

### Controls

**Top Bar:**
- Search input (with clear button)
- Namespace filter dropdown
- Graph depth slider (1-3 levels)
- Export button (JSON, CSV, Graph)
- Help button (keyboard shortcuts)

**Graph Area:**
- Pan: Click and drag background
- Zoom: Mouse wheel
- Select: Click node
- Multi-select: Shift + click
- Context menu: Right-click node

**Keyboard Shortcuts:**
- `/` - Focus search
- `Esc` - Clear selection
- `Ctrl+F` - Toggle search panel
- `Ctrl+E` - Export current view
- `Arrow keys` - Navigate nodes

---

## 🛠️ Technical Stack

### Frontend Libraries

| Library | Purpose | Justification |
|---------|---------|---------------|
| **React** | UI framework | Already in use in DevX |
| **D3.js** or **Cytoscape.js** | Graph visualization | D3 = flexibility, Cytoscape = performance |
| **React Query** | Data fetching | Caching, deduplication |
| **Tailwind CSS** | Styling | Consistent with DevX |
| **Lucide React** | Icons | Lightweight, tree-shakeable |

### Graph Library Comparison

| Feature | D3.js | Cytoscape.js |
|---------|-------|--------------|
| **Flexibility** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Performance** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Learning Curve** | Steep | Moderate |
| **Layout Algorithms** | Manual | Built-in |
| **Recommended For** | Custom viz | Large graphs |

**Recommendation:** Start with **Cytoscape.js** for MVP (easier, faster), consider D3.js for v2 if custom interactions needed.

---

## 📁 File Structure

```
web/src/
├── app/
│   └── ontology-explorer/
│       ├── page.tsx                    # Main explorer page
│       └── layout.tsx                  # Layout wrapper
│
├── components/
│   └── ontology-explorer/
│       ├── OntologyExplorer.tsx        # Main component
│       ├── GraphVisualization.tsx      # Cytoscape wrapper
│       ├── NamespaceTree.tsx           # Namespace sidebar
│       ├── ContainerDetail.tsx         # Detail panel
│       ├── SearchBar.tsx               # Search controls
│       ├── ExportMenu.tsx              # Export dropdown
│       └── KeyboardShortcuts.tsx       # Help modal
│
├── lib/
│   └── ontology-api.ts                 # API client for v5 endpoints
│
└── hooks/
    └── use-ontology.ts                 # React Query hooks
```

---

## 🔌 API Integration

### Endpoints Used

```typescript
// Summary
GET /ontology/v5/summary
→ Used for: Initial stats, namespace list

// Container lookup
GET /ontology/v5/container/{path}
→ Used for: Node details, edge list

// Related containers
GET /ontology/v5/related/{path}?limit=50
→ Used for: Graph expansion, recommendations

// Search
GET /ontology/v5/search?q={query}&namespace={ns}
→ Used for: Search bar, filtering
```

### Client Library

```typescript
// lib/ontology-api.ts
export class OntologyAPI {
  private baseUrl = 'http://localhost:8015/ontology/v5';

  async getSummary(): Promise<OntologySummary> {
    const res = await fetch(`${this.baseUrl}/summary`);
    return res.json();
  }

  async getContainer(path: string): Promise<Container> {
    const res = await fetch(`${this.baseUrl}/container/${encodeURIComponent(path)}`);
    return res.json();
  }

  async getRelated(path: string, limit = 20): Promise<RelatedContainer[]> {
    const res = await fetch(`${this.baseUrl}/related/${encodeURIComponent(path)}?limit=${limit}`);
    const data = await res.json();
    return data.related;
  }

  async search(query: string, namespace?: string): Promise<Container[]> {
    const url = new URL(`${this.baseUrl}/search`);
    url.searchParams.set('q', query);
    if (namespace) url.searchParams.set('namespace', namespace);

    const res = await fetch(url.toString());
    const data = await res.json();
    return data.results;
  }
}
```

---

## 🎯 Implementation Plan

### Phase 1: Basic UI (2 hours)

**Tasks:**
1. Create route at `/ontology-explorer`
2. Build three-column layout (namespace, graph, detail)
3. Implement search bar with namespace filter
4. Add namespace tree component
5. Create container detail panel
6. Wire up API client

**Deliverables:**
- Basic layout renders
- Search works (displays results as list)
- Namespace filter functional
- Container detail shows on selection

### Phase 2: Graph Visualization (2-3 hours)

**Tasks:**
1. Install Cytoscape.js (`npm install cytoscape`)
2. Create `GraphVisualization.tsx` wrapper
3. Implement node/edge rendering
4. Add color coding by namespace
5. Add click handlers (select node → show detail)
6. Implement layout algorithm (force-directed)
7. Add pan/zoom controls

**Deliverables:**
- Graph renders 100+ nodes smoothly
- Nodes clickable, edges visible
- Color-coded by namespace
- Smooth interactions (60fps)

### Phase 3: Polish & Features (1-2 hours)

**Tasks:**
1. Add export functionality (JSON, CSV)
2. Implement keyboard shortcuts
3. Add loading states
4. Add error handling
5. Polish styling (shadows, borders, spacing)
6. Add help modal
7. Performance optimization (virtualization)

**Deliverables:**
- Export buttons work
- Keyboard shortcuts active
- Loading spinners
- Error messages
- Professional styling

---

## 🧪 Testing Strategy

### Manual Testing Checklist

- [ ] Search returns correct results
- [ ] Namespace filter works
- [ ] Graph renders without errors
- [ ] Clicking node shows details
- [ ] Related containers load
- [ ] Export generates valid JSON
- [ ] Keyboard shortcuts work
- [ ] Performance acceptable (no lag)

### Test Scenarios

1. **Search Test**
   - Search "python" → Should find SkillDNA.Programming.Python
   - Search "leadership" with BehDNA filter → Should find BehDNA leadership containers

2. **Graph Test**
   - Select SkillDNA → Should render related nodes
   - Click Programming.Python → Should show 20+ related containers
   - Zoom in/out → Should be smooth

3. **Performance Test**
   - Load 500 nodes → Should render in < 2s
   - Search 2,615 containers → Should return in < 500ms
   - Pan/zoom → Should be 60fps

### Acceptance Criteria

| Criterion | Target | How to Verify |
|-----------|--------|---------------|
| Initial load | < 2s | Network tab |
| Search latency | < 500ms | Console.time() |
| Graph rendering | < 1s (100 nodes) | Performance profiler |
| Interaction FPS | 60fps | Chrome DevTools |
| Memory usage | < 200MB | Task manager |

---

## 📊 Success Metrics

### User Experience

- ✅ Can find any container in < 30 seconds
- ✅ Graph is intuitive without instructions
- ✅ Detail panel provides sufficient context
- ✅ Export works reliably

### Technical

- ✅ 0 console errors on load
- ✅ All API calls succeed
- ✅ No memory leaks (stable after 5 min use)
- ✅ Responsive on 1920x1080 and larger

---

## 🚀 Future Enhancements (Phase 8D+)

### v2.0 Features
- **Advanced Filtering:** Filter by confidence, edge type, tags
- **Graph Layouts:** Tree, radial, circular, hierarchical
- **Time Machine:** View ontology evolution over time
- **Diff View:** Compare two containers side-by-side
- **Annotation:** Add notes to containers
- **Collaboration:** Share views via URL

### v3.0 Features
- **AI Assistant:** Natural language queries ("Show me leadership skills")
- **Auto-Layout:** ML-based optimal graph layout
- **3D Visualization:** Three.js 3D graph
- **Real-time Sync:** Live updates as ontology changes
- **Mobile Support:** Touch-friendly interface

---

## 🎓 Design Principles

1. **Progressive Disclosure:** Start simple, reveal complexity on demand
2. **Immediate Feedback:** Visual confirmation of all actions
3. **Keyboard-First:** All actions accessible via keyboard
4. **Error Recovery:** Clear error messages with suggestions
5. **Performance:** Never block the main thread

---

## 📚 References

### Libraries
- [Cytoscape.js Documentation](https://js.cytoscape.org/)
- [React Query](https://tanstack.com/query/latest)
- [D3.js Force Layout](https://d3js.org/d3-force)

### Inspiration
- [Neo4j Browser](https://neo4j.com/developer/neo4j-browser/)
- [Gephi](https://gephi.org/)
- [GraphXR](https://www.kineviz.com/)

---

**Status:** 🟡 Ready to implement
**Next Step:** Create basic layout and search UI
**Estimated Completion:** 2025-10-11 (same day, 4-6 hours)
