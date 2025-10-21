# ReDNA Intel Pack

**Version:** 1.0
**Generated:** 2025-10-20
**Purpose:** Read-only workspace documentation for developers

## Overview

This directory contains 6 comprehensive documentation files that capture the current state of the ReDNA system. These files are read-only snapshots designed to help developers quickly understand the architecture, configuration, and operational details.

---

## Files

### 1. [ServicesAndPorts.json](ServicesAndPorts.json)
**Size:** 2.3 KB
**Format:** JSON

Documents all 7 microservices in the ReDNA ecosystem:
- Service names and purposes
- Port assignments
- Entrypoints and health check paths
- Base URLs for inter-service communication

**Quick View:**
```bash
jq '.services[] | {name, ports, base_url}' docs/Intel/ServicesAndPorts.json
```

---

### 2. [EndpointsIndex.json](EndpointsIndex.json)
**Size:** 12 KB
**Format:** JSON

Comprehensive index of 80+ API endpoints across all services:
- Organized by service and category
- HTTP methods and parameters
- Return types and descriptions
- Auth requirements

**Quick View:**
```bash
# List all Core API endpoints
jq '.services[] | select(.service == "Core API") | .categories[].endpoints[].path' \
  docs/Intel/EndpointsIndex.json
```

---

### 3. [FlagsAndDefaults.json](FlagsAndDefaults.json)
**Size:** 15 KB
**Format:** JSON

Runtime flags and environment variables (60+ entries):
- Current values vs defaults
- Organized into 9 categories
- Type information and descriptions
- Phase 4-9 promotion thresholds

**Quick View:**
```bash
# List all feature toggles
jq '.categories[] | select(.category == "Feature Toggles") | .flags[] |
  {name, current, description}' docs/Intel/FlagsAndDefaults.json
```

---

### 4. [DebugSurface.md](DebugSurface.md)
**Size:** 11 KB
**Format:** Markdown

Debug endpoints and diagnostic tools:
- 7 Core API debug endpoints with examples
- JSONL audit log locations
- Control Panel++ debug features
- Common debug workflows
- Production safety guidelines

**Topics:**
- UCN/RR diagnostics
- Resolver traces
- Ontology statistics
- Belief graph inspection
- Provenance chain tracing
- Pipeline health checks
- Curiosity engine diagnostics

---

### 5. [OntologyStatus.md](OntologyStatus.md)
**Size:** 8.3 KB
**Format:** Markdown

Current ontology hierarchy status (Phase 10):
- ReDNA root + 5 tier-1 subsystems
- Seed statistics (version 2.0, 10 nodes, 9 edges)
- Verification commands with expected outputs
- API endpoints for ontology operations
- Migration notes from Phase 9
- Test suite coverage (14/14 passing)

**Key Sections:**
- Phase 10 hierarchy model
- Current seed ontology breakdown
- Verification commands
- Known issues and future expansion

---

### 6. [PropagationPolicy.md](PropagationPolicy.md)
**Size:** 14 KB
**Format:** Markdown

AI-First Hierarchical UCN Propagation policy (Phase 9):
- 5 guiding principles with examples
- Soft scaffolding guidelines (±200 divergence)
- 4 complete scenario walkthroughs
- Phase 9 critical fixes (UCN ≠ RR)
- Implementation notes
- Future enhancements (ML, temporal dynamics)

**Key Principles:**
1. Read child UCNs as strong priors
2. Weigh parent-level evidence separately
3. Use discretion over formulas
4. Explain divergences via Why-Cards
5. Never expose UCN as RR

---

## Usage

### Quick Reference Commands

**View service health:**
```bash
jq '.services[] | {name, ports}' docs/Intel/ServicesAndPorts.json
```

**Find endpoint:**
```bash
grep -r "curiosity" docs/Intel/EndpointsIndex.json
```

**Check flag value:**
```bash
jq '.categories[].flags[] | select(.name == "CORE_CURIOSITY_ENABLED")' \
  docs/Intel/FlagsAndDefaults.json
```

**Verify ontology:**
```bash
curl -s http://127.0.0.1:8004/core/graph/ontology | \
  jq '{version: .version, nodes: (.nodes | length), edges: (.edges | length)}'
```

---

## Maintenance

### When to Update

These files should be regenerated when:
- New services are added or ports change
- New API endpoints are introduced
- Environment variables are added/changed
- Ontology hierarchy is updated
- Propagation policy changes

### Regeneration

To regenerate the Intel Pack:
```bash
# Provide Claude with the "Intel Pack" prompt from the original request
# Or manually update individual files as needed
```

---

## Related Documentation

- [ReDNA_Workspace_Manifest.md](../ReDNA_Workspace_Manifest.md) - Comprehensive workspace overview
- [Phase 10 Implementation](../Phase10_ReDNA_Hierarchy_Implementation.md) - Phase 10 details
- [Phase 9 Audit Report](../Phase9_RR_UCN_Audit_Report.md) - Phase 9 changes
- [Operations Guide](../OPERATIONS.md) - Operational procedures

---

## Notes

- All files are **read-only documentation** - they do not affect runtime behavior
- JSON files are pretty-printed for readability
- Markdown files include code examples and verification commands
- Phase 9/10 context is included throughout
- Test coverage and verification steps are documented

---

**Last Updated:** 2025-10-20
**Phase:** 10 (ReDNA Hierarchy)
**Status:** Complete ✅
