# Synthetic Reference Population Calibration Report

**Generated:** 2025-10-21 09:59:03
**Phase:** 10.2.3
**Purpose:** Verify demo users with moderate UCNs land in mid-range RR (30-80%)

## Universe Statistics

| Universe | Min | Mean | Median | P90 | Max | Std |
|----------|-----|------|--------|-----|-----|-----|
| combined | 0.1286 | 0.6656 | 0.6759 | 0.8652 | 0.9825 | 0.1567 |
| generic | 0.1286 | 0.6656 | 0.6759 | 0.8652 | 0.9825 | 0.1567 |
| high | 0.3127 | 0.8051 | 0.8197 | 0.9238 | 0.9876 | 0.1007 |
| low | 0.1183 | 0.5441 | 0.5463 | 0.7194 | 0.9193 | 0.1344 |
| medium | 0.2397 | 0.6970 | 0.7066 | 0.8505 | 0.9718 | 0.1229 |

## Calibration: UCN → RR Percentile

| Universe | UCN=0.50 | UCN=0.60 | UCN=0.70 | UCN=0.75 | UCN=0.80 | UCN=0.85 | UCN=0.90 | UCN=0.95 |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| combined | 16.0% | 33.1% | 55.6% | 66.7% | 77.5% | 87.4% | 95.0% | 99.3% |
| generic | 16.0% | 33.1% | 55.6% | 66.7% | 77.5% | 87.4% | 95.0% | 99.3% |
| high | 0.7% | 3.8% | 15.4% | 26.7% | 42.7% | 61.9% | 81.9% | 96.5% |
| low | 37.2% | 64.6% | 87.0% | 93.9% | 97.9% | 99.5% | 100.0% | 100.0% |
| medium | 6.8% | 21.8% | 47.9% | 63.2% | 77.9% | 89.8% | 97.1% | 99.9% |

## Calibration Targets (Combined Universe)

- ✅ **UCN=0.70 → RR**: 55.6% (target: 50-60%)
- ✅ **UCN=0.80 → RR**: 77.5% (target: 75-85%)
- ✅ **UCN=0.90 → RR**: 95.0% (target: 90-95%)

## Summary

✅ **All calibration targets met!** Demo users with moderate UCNs will land in mid-range RR values.

## Next Steps

1. Restart Core API to reload synthetic populations: `make cp-nuclear`
2. Verify with demo user: `curl -s http://127.0.0.1:8004/ui/unabridged?user_id=TEST | jq '.traits[] | {trait_id, ucn, rr}'`
3. Expect RR values distributed roughly 30-80% for mid-range UCNs
