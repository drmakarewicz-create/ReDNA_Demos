# Synthetic Reference Population Calibration Report

**Generated:** 2025-10-21 09:56:46
**Phase:** 10.2.3
**Purpose:** Verify demo users with moderate UCNs land in mid-range RR (30-80%)

## Universe Statistics

| Universe | Min | Mean | Median | P90 | Max | Std |
|----------|-----|------|--------|-----|-----|-----|
| combined | 0.2524 | 0.7777 | 0.7919 | 0.9235 | 0.9885 | 0.1201 |
| generic | 0.2524 | 0.7777 | 0.7919 | 0.9235 | 0.9885 | 0.1201 |
| high | 0.4865 | 0.8886 | 0.9025 | 0.9628 | 0.9894 | 0.0679 |
| low | 0.2515 | 0.6802 | 0.6893 | 0.8133 | 0.9290 | 0.1078 |
| medium | 0.3757 | 0.8035 | 0.8151 | 0.9077 | 0.9750 | 0.0876 |

## Calibration: UCN → RR Percentile

| Universe | UCN=0.50 | UCN=0.60 | UCN=0.70 | UCN=0.75 | UCN=0.80 | UCN=0.85 | UCN=0.90 | UCN=0.95 |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| combined | 2.1% | 8.8% | 24.9% | 37.3% | 52.7% | 68.3% | 83.7% | 95.9% |
| generic | 2.1% | 8.8% | 24.9% | 37.3% | 52.7% | 68.3% | 83.7% | 95.9% |
| high | 0.0% | 0.1% | 1.6% | 4.2% | 10.9% | 24.1% | 48.5% | 82.1% |
| low | 6.1% | 22.6% | 53.8% | 71.4% | 86.9% | 96.2% | 99.7% | 100.0% |
| medium | 0.2% | 2.3% | 12.9% | 25.2% | 43.6% | 66.1% | 87.3% | 98.9% |

## Calibration Targets (Combined Universe)

- ❌ **UCN=0.70 → RR**: 24.9% (target: 50-60%)
- ❌ **UCN=0.80 → RR**: 52.7% (target: 75-85%)
- ❌ **UCN=0.90 → RR**: 83.7% (target: 90-95%)

## Summary

⚠️ **Some calibration targets not met.** Review universe configuration and regenerate.

## Next Steps

1. Restart Core API to reload synthetic populations: `make cp-nuclear`
2. Verify with demo user: `curl -s http://127.0.0.1:8004/ui/unabridged?user_id=TEST | jq '.traits[] | {trait_id, ucn, rr}'`
3. Expect RR values distributed roughly 30-80% for mid-range UCNs
