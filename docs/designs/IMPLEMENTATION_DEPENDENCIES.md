# Evergreen Implementation Dependencies & Critical Path

**Version:** 1.0
**Date:** 2025-10-12
**Purpose:** Define implementation dependencies and critical path for parallel development

---

## Overview

This document maps all dependencies between Evergreen components to enable parallel development and identify the critical path for fastest implementation.

---

## 1. Dependency Graph

### 1.1 Visual Dependency Map

```
PHASE 1: FOUNDATION (Week 1-2)
================================

┌─────────────────┐
│  PreProcessor   │ ← NO DEPENDENCIES (Start immediately)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ComfortFilter   │ ← Depends: PreProcessor output format
└────────┬────────┘
         │
         ├──────────────────────┐
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│  Provenance     │    │  CoreAnalyzer   │ ← Can develop in parallel
│    Tagger       │    │  (Curiosity)    │
└────────┬────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│  CoreStorage    │ ← Depends: Provenance format
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  EmpathyEngine  │ ← Can develop in parallel with storage
└─────────────────┘


PHASE 2: INTELLIGENCE (Week 3-4)
=================================

┌─────────────────┐
│ EnrichmentEngine│ ← Depends: CoreStorage, CoreAnalyzer
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Distribution    │ ← Depends: EnrichmentEngine
│     Layer       │
└────────┬────────┘
         │
         ├──────────────────────┬──────────────────┐
         ▼                      ▼                  ▼
┌─────────────────┐    ┌─────────────────┐  ┌──────────────┐
│CuriosityDebt    │    │DynamicReprio    │  │BondingMonitor│
│   Tracker       │    │   tizer         │  │              │
└─────────────────┘    └─────────────────┘  └──────────────┘


PHASE 3: TOOLS & INTEGRATION (Week 5-6)
========================================

All tools can develop in parallel:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│FinancialPlanner │  │  MoodTracker    │  │   GoalEngine    │  │  HabitDesigner  │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                     │                     │
         └────────────────────┴─────────────────────┴─────────────────────┘
                                        │
                                        ▼
                              ┌─────────────────┐
                              │  ToolManager    │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ HC Orchestrator │ ← Integration point
                              │   Integration   │
                              └─────────────────┘
```

---

## 2. Detailed Dependency Matrix

### 2.1 Component Dependencies

| Component | Depends On | Can Start After | Parallel With |
|-----------|------------|-----------------|---------------|
| **PreProcessor** | None | Day 1 | N/A |
| **ComfortFilter** | PreProcessor | Day 3 | CoreAnalyzer |
| **ProvenanceTagger** | PreProcessor | Day 3 | CoreAnalyzer |
| **CoreStorage** | ProvenanceTagger | Day 5 | EmpathyEngine |
| **CoreAnalyzer** | None | Day 1 | PreProcessor |
| **EmpathyEngine** | None | Day 1 | Any Phase 1 |
| **EnrichmentEngine** | CoreStorage, CoreAnalyzer | Day 15 | Distribution prep |
| **DistributionLayer** | EnrichmentEngine | Day 18 | N/A |
| **CuriosityDebtTracker** | CoreAnalyzer, DistributionLayer | Day 20 | Reprioritizer |
| **DynamicReprioritizer** | CuriosityDebtTracker | Day 22 | BondingMonitor |
| **BondingMonitor** | EmpathyEngine, Storage | Day 20 | CuriosityDebt |
| **FinancialPlanner** | ToolManager (basic) | Day 30 | Other tools |
| **MoodTracker** | ToolManager (basic) | Day 30 | Other tools |
| **GoalEngine** | ToolManager (basic) | Day 30 | Other tools |
| **HabitDesigner** | ToolManager (basic) | Day 30 | Other tools |
| **ToolManager** | None | Day 29 | N/A |
| **HC Integration** | All above | Day 38 | Testing |

---

## 3. Critical Path Analysis

### 3.1 Longest Path (Critical Path)

**Total Duration: 42 days (6 weeks core + 2 weeks testing)**

```
Day 1-2:   PreProcessor (2 days)
  ↓
Day 3-4:   ComfortFilter (2 days)
  ↓
Day 5-6:   ProvenanceTagger (2 days)
  ↓
Day 7-10:  CoreStorage (4 days) ← CRITICAL
  ↓
Day 11-14: EnrichmentEngine (4 days) ← CRITICAL
  ↓
Day 15-17: DistributionLayer (3 days)
  ↓
Day 18-21: CuriosityDebtTracker (4 days)
  ↓
Day 22-24: DynamicReprioritizer (3 days)
  ↓
Day 25-28: QuestionGenerator (4 days)
  ↓
Day 29-32: ToolManager + Tools (4 days)
  ↓
Day 33-35: HC Integration (3 days)
  ↓
Day 36-42: Integration Testing (7 days)
```

**Critical Path Total: 42 days**

### 3.2 Parallel Tracks (Can Reduce Total Time)

**Track A (Ingestion):** PreProcessor → Comfort → Provenance → Storage → Enrichment → Distribution
**Track B (Curiosity):** CoreAnalyzer → (wait for Distribution) → DebtTracker → Reprioritizer
**Track C (Empathy):** EmpathyEngine → (wait for Storage) → BondingMonitor
**Track D (Tools):** ToolManager → All Tools (parallel)

**With parallelization, can complete in 35 days instead of 42.**

---

## 4. Resource Allocation Strategy

### 4.1 Optimal Team Structure

**For fastest completion (35 days):**

#### Developer 1: Ingestion Track (Critical Path)
- Days 1-2: PreProcessor
- Days 3-4: ComfortFilter
- Days 5-6: ProvenanceTagger
- Days 7-10: CoreStorage ⚠️ CRITICAL
- Days 11-14: EnrichmentEngine ⚠️ CRITICAL
- Days 15-17: DistributionLayer
- Days 18-35: Integration support

#### Developer 2: Curiosity Track
- Days 1-4: CoreAnalyzer
- Days 5-14: UCNRRAnalyzer
- Days 15-21: CuriosityDebtTracker (wait for Distribution)
- Days 22-24: DynamicReprioritizer
- Days 25-28: QuestionGenerator
- Days 29-35: Integration testing

#### Developer 3: Empathy & Tools Track
- Days 1-7: EmpathyEngine
- Days 8-14: BondingMonitor
- Days 15-21: MotivationEngine
- Days 22-28: ToneAdapter
- Days 29-35: Integration testing

#### Developer 4: Tools Track
- Days 1-7: ToolManager foundation
- Days 8-14: FinancialPlanner
- Days 15-21: MoodTracker
- Days 22-28: GoalEngine
- Days 29-35: HabitDesigner

#### Developer 5: Integration & Testing
- Days 1-28: Write integration tests alongside development
- Days 29-35: Full integration testing
- Days 36-42: Performance optimization

**With 5 developers working in parallel: 35-42 days total**

---

## 5. Blocking Dependencies (High Priority)

### 5.1 Components That Block Others

1. **PreProcessor** (blocks 5 components)
   - ComfortFilter
   - ProvenanceTagger
   - CoreStorage (indirectly)
   - EnrichmentEngine (indirectly)
   - DistributionLayer (indirectly)

2. **CoreStorage** (blocks 4 components) ⚠️ CRITICAL
   - EnrichmentEngine
   - DistributionLayer (indirectly)
   - BondingMonitor
   - All downstream components

3. **DistributionLayer** (blocks 3 components)
   - CuriosityDebtTracker
   - DynamicReprioritizer
   - QuestionGenerator

### 5.2 Priority Order for Development

**Must Complete First (Week 1):**
1. PreProcessor (Day 1-2)
2. ComfortFilter (Day 3-4)
3. ProvenanceTagger (Day 5-6)

**Must Complete Second (Week 2):**
4. CoreStorage (Day 7-10) ⚠️ CRITICAL - allocate best developer
5. CoreAnalyzer (Day 1-4, parallel)
6. EmpathyEngine (Day 1-7, parallel)

**Can Proceed Once Above Complete (Week 3-4):**
7. EnrichmentEngine (Day 11-14)
8. DistributionLayer (Day 15-17)
9. BondingMonitor (Day 8-14, parallel)

---

## 6. Integration Points

### 6.1 Key Integration Moments

**Integration Point 1: Storage-Enrichment (Day 14)**
- CoreStorage must be fully tested
- EnrichmentEngine begins using Storage API
- Test data flow end-to-end

**Integration Point 2: Distribution-Curiosity (Day 17)**
- DistributionLayer operational
- CuriosityDebtTracker can subscribe to events
- Test event publishing

**Integration Point 3: All-to-HC (Day 33)**
- HC Orchestrator integration begins
- All components must have stable APIs
- Integration testing phase starts

---

## 7. Risk Mitigation

### 7.1 High-Risk Dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| CoreStorage delays | Blocks 4+ components | Allocate best developer, start Day 7 |
| EnrichmentEngine complexity | Blocks Distribution | Create mock version for testing |
| API contract changes | Integration breaks | Freeze APIs by Day 20 |
| LLM service outage | Testing blocked | Create mock LLM responses |

### 7.2 Contingency Plans

**If CoreStorage Delayed:**
- Use mock storage for downstream development
- Prioritize basic read/write operations
- Defer optimization features

**If EnrichmentEngine Delayed:**
- Create simplified enrichment for testing
- Focus on container mapping first
- Defer relationship discovery

**If Integration Issues:**
- Fall back to component-level testing
- Use mock interfaces
- Defer performance optimization

---

## 8. Testing Dependencies

### 8.1 Test Pyramid

```
           ┌─────────────┐
           │   E2E Tests │ Day 36-42 (requires all components)
           └─────────────┘
         ┌───────────────────┐
         │ Integration Tests  │ Day 29-35 (requires stable APIs)
         └───────────────────┘
    ┌──────────────────────────────┐
    │      Unit Tests              │ Ongoing (each component)
    └──────────────────────────────┘
```

### 8.2 Testing Critical Path

- **Unit Tests:** Write alongside each component (Days 1-35)
- **Integration Tests:** Begin Day 29 (requires stable APIs)
- **E2E Tests:** Begin Day 36 (requires all components)
- **Performance Tests:** Day 38-40 (requires realistic load)

---

## 9. Daily Standup Template

### Recommended Daily Standup Questions

For each developer track:

1. **Yesterday:** What components completed? Tests passing?
2. **Today:** Which component(s) working on? Expected completion?
3. **Blockers:** Waiting on any dependencies? API contracts finalized?
4. **Integration:** Ready for integration with other tracks?

### Key Metrics to Track Daily

- Components completed vs. planned
- Tests written vs. target coverage
- API contracts finalized
- Blocking dependencies resolved

---

## 10. Milestone Definitions

### Week 1 Milestone: Foundation Complete
- [ ] PreProcessor working with tests
- [ ] ComfortFilter operational
- [ ] ProvenanceTagger creating records
- [ ] CoreAnalyzer identifying gaps
- [ ] EmpathyEngine detecting emotions

**Definition of Done:** Can ingest and filter basic data with comfort controls

### Week 2 Milestone: Storage & Core Intelligence
- [ ] CoreStorage read/write operational
- [ ] Basic enrichment working
- [ ] BondingMonitor tracking metrics
- [ ] All Phase 1 components have 80%+ test coverage

**Definition of Done:** Data can flow from ingestion through storage to enrichment

### Week 4 Milestone: Full Intelligence Layer
- [ ] DistributionLayer publishing events
- [ ] CuriosityDebtTracker calculating debt
- [ ] DynamicReprioritizer handling triggers
- [ ] QuestionGenerator creating questions

**Definition of Done:** System can identify and prioritize curiosity exploration

### Week 6 Milestone: Tools & Integration
- [ ] All 4 tools implemented
- [ ] ToolManager orchestrating
- [ ] HC Orchestrator integration complete
- [ ] Integration tests passing

**Definition of Done:** Complete system operational end-to-end

---

## 11. Optimization Opportunities

### 11.1 Parallelization Wins

**Biggest Time Savings:**
1. **Tools Track:** All 4 tools can develop completely in parallel (saves 12 days)
2. **Empathy Track:** Parallel to ingestion track (saves 7 days)
3. **Curiosity Core:** CoreAnalyzer parallel to ingestion (saves 4 days)

**Total Savings with Optimal Parallelization: 7-10 days**

### 11.2 Resource Optimization

**If Limited Resources (2 developers):**
- Follow critical path strictly
- Defer non-blocking components
- Use mocks for testing
- **Timeline: 50-55 days**

**If Ample Resources (5+ developers):**
- Full parallelization
- Dedicated integration engineer
- Continuous testing
- **Timeline: 35 days**

---

## 12. Quick Reference

### Must Start First
1. PreProcessor (Day 1)
2. CoreAnalyzer (Day 1)
3. EmpathyEngine (Day 1)

### Can't Start Until Dependencies Complete
1. EnrichmentEngine (wait for CoreStorage + CoreAnalyzer)
2. CuriosityDebtTracker (wait for DistributionLayer)
3. HC Integration (wait for all components)

### Safe to Parallelize
1. All Phase 1 components (Week 1-2)
2. All Phase 3 tools (Week 5)
3. Testing alongside development

---

## Summary

**Critical Path:** 42 days
**Optimized with Parallelization:** 35 days
**Blocking Components:** CoreStorage, DistributionLayer
**High-Risk Areas:** Storage, Enrichment, Integration

**Recommendation:**
- Allocate best developer to CoreStorage (Day 7-10)
- Maximize parallelization in Phase 1 and Phase 3
- Freeze APIs by Day 20
- Begin integration testing Day 29

---

**Status:** Complete dependency analysis ready for project planning
**Use Case:** Project scheduling, resource allocation, risk management
**Next Step:** Create development schedule based on available resources
