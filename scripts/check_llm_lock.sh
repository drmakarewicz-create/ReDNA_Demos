#!/usr/bin/env bash
# Check that LLM provider is locked to Ollama-only
# Usage: ./scripts/check_llm_lock.sh
# Exit codes: 0 = OK, 1 = locked provider violation

set -euo pipefail

: "${LLM_PROVIDER:=ollama}"
: "${OPENAI_ENABLED:=false}"
: "${ANTHROPIC_ENABLED:=false}"
: "${AZURE_OPENAI_ENABLED:=false}"

echo "🔒 Checking LLM provider lock..."
echo "   LLM_PROVIDER=${LLM_PROVIDER}"
echo "   OPENAI_ENABLED=${OPENAI_ENABLED}"
echo "   ANTHROPIC_ENABLED=${ANTHROPIC_ENABLED}"
echo "   AZURE_OPENAI_ENABLED=${AZURE_OPENAI_ENABLED}"

# Check that provider is ollama
if [[ "${LLM_PROVIDER}" != "ollama" ]]; then
  echo "✖ LLM lock failed: LLM_PROVIDER must be 'ollama', got '${LLM_PROVIDER}'"
  exit 1
fi

# Check that cloud providers are disabled
if [[ "${OPENAI_ENABLED}" == "true" ]]; then
  echo "✖ LLM lock failed: OPENAI_ENABLED must be false"
  exit 1
fi

if [[ "${ANTHROPIC_ENABLED}" == "true" ]]; then
  echo "✖ LLM lock failed: ANTHROPIC_ENABLED must be false"
  exit 1
fi

if [[ "${AZURE_OPENAI_ENABLED}" == "true" ]]; then
  echo "✖ LLM lock failed: AZURE_OPENAI_ENABLED must be false"
  exit 1
fi

echo "✔ LLM lock OK (Ollama-only mode enforced)"
exit 0
