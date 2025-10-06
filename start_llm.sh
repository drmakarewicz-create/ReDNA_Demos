# ~/Documents/ReDNA_Demos/start_llm.sh
#!/usr/bin/env bash
set -euo pipefail
# Start Ollama server if not already running, ensure model is present.

ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

BASE="http://127.0.0.1:11434"
# 1) Server up?
if ! curl -fsS "$BASE/api/version" >/dev/null 2>&1; then
  echo "[LLM] Starting Ollama server…"
  # Prefer the app if installed, else fallback to `ollama serve`
  if command -v open >/dev/null 2>&1 && [ -d "/Applications/Ollama.app" ]; then
    open -g -a "Ollama"
    # give it a moment
    for i in {1..20}; do
      curl -fsS "$BASE/api/version" >/dev/null 2>&1 && break || sleep 0.5
    done
  else
    # background serve
    nohup ollama serve >/dev/null 2>&1 &
    for i in {1..20}; do
      curl -fsS "$BASE/api/version" >/dev/null 2>&1 && break || sleep 0.5
    done
  fi
fi

# 2) Ensure model tag exists
if ! curl -fsS "$BASE/api/tags" | jq -e '.models[].name | select(.=="llama3:latest")' >/dev/null; then
  echo "[LLM] Pulling model llama3:latest (first time can take a bit)…"
  ollama pull llama3:latest
fi

echo "[LLM] Ready: $(curl -s $BASE/api/version)"
