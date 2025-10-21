# Phase 9: UCN↔RR Conflation Audit Report

**Generated:** 2025-10-20T10:43:21.153198

## Executive Summary

- **Files Scanned:** 271
- **Total Lines:** 90,939
- **Total Findings:** 30
  - Critical: 14
  - Warnings: 1
  - Info: 15

### Findings by Classification

- 0-1000 → 0-100 Conversion: 10
- RR 0-1000 Scale: 9
- RR > 100 Check: 6
- Curiosity Legacy Formula: 2
- Direct UCN→RR Assignment: 2
- UCN→RR Conflation: 1

## Terminology Reference

| Term | Range | Purpose | Visibility |
|------|-------|---------|------------|
| **UCN** | 0-1000 | Internal confidence audit | Hidden |
| **RR** | 0-100 | User-facing percentile | Visible |
| **Curiosity** | 0-100 | Inverse of RR (= 100 - RR) | Hidden |

## Critical Findings

These require immediate attention as they may leak UCN as RR or use incorrect formulas.

### RR 0-1000 Scale

**File:** `core/ucn_rr_service.py:99`

**Code:**
```python
rr: float   # 0-1000 Rarity score (LEGACY - Phase 9: Should be 0-100 percentile)
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### Curiosity Legacy Formula

**File:** `core/ucn_rr_service.py:228`

**Code:**
```python
curiosity = 1000.0 - rr
```

**Issue:** Curiosity computed as 1000-X instead of 100-RR

**Fix:** Change to: curiosity = 100.0 - rr

---

### Curiosity Legacy Formula

**File:** `core/ucn_rr_service.py:289`

**Code:**
```python
curiosity = 1000.0 - rr
```

**Issue:** Curiosity computed as 1000-X instead of 100-RR

**Fix:** Change to: curiosity = 100.0 - rr

---

### RR 0-1000 Scale

**File:** `core/graph/normalize_egress.py:68`

**Code:**
```python
logger.warning(f"[RR-Norm] {trait_id}: rr={rr:.2f} > 100, adapting from 0-1000 scale")
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### RR 0-1000 Scale

**File:** `core/graph/normalize_egress.py:195`

**Code:**
```python
logger.warning(f"[RR-Norm] {trait_id}: rr={rr:.2f} > 100, adapting from 0-1000 scale")
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### RR 0-1000 Scale

**File:** `core/graph/debug_api.py:87`

**Code:**
```python
issue_description = f"rr={rr:.2f} > 100, likely 0-1000 scale (should divide by 10)"
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### RR 0-1000 Scale

**File:** `core/graph/debug_api.py:121`

**Code:**
```python
issue_description = f"rr_score={rr_score:.2f} in 0-1000 range (will normalize to 0-100)"
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### RR 0-1000 Scale

**File:** `core/graph/belief.py:201`

**Code:**
```python
rr_score: RR score from UCNRR (0-1000)
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### RR 0-1000 Scale

**File:** `core/graph/schemas.py:136`

**Code:**
```python
rr_score: Optional[float] = None  # Legacy 0-1000 (kept for backward compat)
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### RR 0-1000 Scale

**File:** `core/graph/whycard_gen.py:39`

**Code:**
```python
rr_score: RR score (0-1000)
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

### UCN→RR Conflation

**File:** `core/refinement/refinement_resolver.py:400`

**Code:**
```python
rr = ucn
```

**Issue:** RR is being assigned from UCN fields (u, c, n)

**Fix:** Use rr_to_percentile() adapter to convert UCN to RR percentile

---

### Direct UCN→RR Assignment

**File:** `core/refinement/refinement_resolver.py:400`

**Code:**
```python
rr = ucn
```

**Issue:** Direct assignment rr = ucn without percentile conversion

**Fix:** Use rr_to_percentile() adapter to compute percentile

---

### Direct UCN→RR Assignment

**File:** `core/refinement/refinement_resolver.py:400`

**Code:**
```python
rr = ucn
```

**Issue:** Direct assignment rr = ucn without percentile conversion

**Fix:** Use rr_to_percentile() adapter to compute percentile

---

### RR 0-1000 Scale

**File:** `core/resolver/impl.py:256`

**Code:**
```python
rr_score = (1.0 - ucn_score) * 1000.0
```

**Issue:** RR is computed on 0-1000 scale instead of 0-100 percentile

**Fix:** Ensure RR is computed as percentile (0-100), not raw UCN score

---

## Warnings

These should be reviewed but may not cause functional issues.

### RR > 100 Check

**File:** `core/graph/debug_api.py:84`

**Code:**
```python
if rr is not None and rr > 100:
```

**Issue:** Code checks if RR > 100, suggesting 0-1000 scale legacy

**Fix:** This is likely adapter code (OK) or legacy data handling

---

## Informational

These are likely intentional (e.g., adapter logic) but flagged for completeness.

### 0-1000 → 0-100 Conversion

**File:** `core/api.py:12088`

**Code:**
```python
confidence = rr / 100.0 if rr > 0 else 0.0
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### 0-1000 → 0-100 Conversion

**File:** `core/api.py:12115`

**Code:**
```python
confidence = rr / 100.0 if rr > 0 else 0.0
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### 0-1000 → 0-100 Conversion

**File:** `core/api.py:12220`

**Code:**
```python
"confidence": round(cadence_rr / 100.0, 2) if cadence_rr > 0 else 0.5
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### 0-1000 → 0-100 Conversion

**File:** `core/api.py:12230`

**Code:**
```python
"confidence": round(vocab_rr / 100.0, 2) if vocab_rr > 0 else 0.5
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### 0-1000 → 0-100 Conversion

**File:** `core/api.py:12240`

**Code:**
```python
"confidence": round(hedging_rr / 100.0, 2) if hedging_rr > 0 else 0.5
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### 0-1000 → 0-100 Conversion

**File:** `core/api.py:12255`

**Code:**
```python
"confidence": round(formality_rr / 100.0, 2) if formality_rr > 0 else 0.5
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### RR > 100 Check

**File:** `core/graph/normalize_egress.py:7`

**Code:**
```python
- Adapts rr > 100 (legacy 0-1000 scale)
```

**Issue:** Code checks if RR > 100, suggesting 0-1000 scale legacy

**Fix:** This is likely adapter code (OK) or legacy data handling

---

### RR > 100 Check

**File:** `core/graph/normalize_egress.py:41`

**Code:**
```python
1. If rr > 100 → assume 0-1000 scale, divide by 10, recompute curiosity
```

**Issue:** Code checks if RR > 100, suggesting 0-1000 scale legacy

**Fix:** This is likely adapter code (OK) or legacy data handling

---

### RR > 100 Check

**File:** `core/graph/normalize_egress.py:67`

**Code:**
```python
if rr is not None and rr > 100:
```

**Issue:** Code checks if RR > 100, suggesting 0-1000 scale legacy

**Fix:** This is likely adapter code (OK) or legacy data handling

---

### 0-1000 → 0-100 Conversion

**File:** `core/graph/normalize_egress.py:69`

**Code:**
```python
rr = rr / 10.0
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### RR > 100 Check

**File:** `core/graph/normalize_egress.py:174`

**Code:**
```python
1. If rr > 100 → assume 0-1000 scale, divide by 10, recompute curiosity
```

**Issue:** Code checks if RR > 100, suggesting 0-1000 scale legacy

**Fix:** This is likely adapter code (OK) or legacy data handling

---

### RR > 100 Check

**File:** `core/graph/normalize_egress.py:194`

**Code:**
```python
if rr is not None and rr > 100:
```

**Issue:** Code checks if RR > 100, suggesting 0-1000 scale legacy

**Fix:** This is likely adapter code (OK) or legacy data handling

---

### 0-1000 → 0-100 Conversion

**File:** `core/graph/normalize_egress.py:196`

**Code:**
```python
rr = rr / 10.0
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### 0-1000 → 0-100 Conversion

**File:** `core/graph/belief.py:272`

**Code:**
```python
weight=rr_score / 1000.0,  # Normalize to [0, 1]
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

### 0-1000 → 0-100 Conversion

**File:** `core/curiosity/curiosity_engine_v2.py:399`

**Code:**
```python
gap_score = ucnrr / 100.0
```

**Issue:** Dividing by 10 suggests 0-1000 → 0-100 normalization

**Fix:** Verify this is intentional adapter logic

---

## Recommendations

1. **Apply egress normalization everywhere**: Ensure all API endpoints use `normalize_egress.py` before returning RR/Curiosity.
2. **Never compute RR directly from UCN**: Always use `rr_to_percentile()` adapter which handles reference population percentiles.
3. **Enforce curiosity formula**: Always `curiosity = 100.0 - rr`, never `1000 - ucn`.
4. **Update terminology**: Replace all 'Readiness Rating' with 'Refinement Rating'.
5. **Add runtime guards**: Implement debug endpoint `/core/debug/rr_audit/{user_id}` to detect mismatches in production.

