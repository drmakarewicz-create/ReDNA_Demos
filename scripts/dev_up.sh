#!/usr/bin/env bash
set -euo pipefail

# UCNRR (reads UCN_RR_Demo/.env)
pkill -f "uvicorn.*8017" 2>/dev/null || true
uvicorn UCN_RR_Demo.ucnrr_app:app --host 127.0.0.1 --port 8017 --log-level info &
sleep 1

# Core (reads repo .env)
pkill -f "uvicorn.*8004" 2>/dev/null || true
uvicorn ReDNACoreDemo.core.api:app --host 127.0.0.1 --port 8004 --log-level info &
sleep 2

echo "=== Health ==="
curl -s 127.0.0.1:8017/health | jq '{status,llm_provider,llm_model,llm_configured}'
curl -s 127.0.0.1:8004/health | jq '{status,rr_mode,features}'
