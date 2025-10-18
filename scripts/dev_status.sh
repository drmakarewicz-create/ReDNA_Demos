#!/usr/bin/env bash
set -euo pipefail

OUT="/tmp/redna_phase6_status_bundle"
mkdir -p "$OUT"

echo "=== OpenAPI (debug paths) ==="
curl -s 127.0.0.1:8004/openapi.json | jq -r '.paths | keys[]' | sort | tee "$OUT/openapi_paths.txt" >/dev/null

echo "=== Core debug ==="
curl -s 127.0.0.1:8004/core/api/debug/envpath         | tee "$OUT/core_envpath.json"         >/dev/null || true
curl -s 127.0.0.1:8004/core/api/debug/envvars         | tee "$OUT/core_envvars.json"         >/dev/null || true
curl -s 127.0.0.1:8004/core/api/debug/promotion_state | tee "$OUT/core_promotions.json"      >/dev/null || true

echo "=== UCNRR health ==="
curl -s 127.0.0.1:8017/health | tee "$OUT/ucnrr_health.json" >/dev/null || true

echo "=== Chronotype ingest (baseline) ==="
curl -s -X POST 127.0.0.1:8004/core/api/ingest_text \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"dbg_chrono","text":"I am a morning person, up before sunrise.","source":"bench"}' \
  | jq '{rescore: .rescore, snapshot: .snapshot}' | tee "$OUT/ingest_chrono.json" >/dev/null || true

echo "=== Tests (Tier-2) ==="
pytest -q tests/test_value_normalizer_tier2.py        | tee "$OUT/pytest_tier2_unit.txt"  >/dev/null || true
pytest -q tests/integration/test_tier2_smoke.py      | tee "$OUT/pytest_tier2_integ.txt" >/dev/null || true

tar -czf /tmp/redna_phase6_status_bundle.tgz -C "$OUT" .
echo "Bundle: /tmp/redna_phase6_status_bundle.tgz"
