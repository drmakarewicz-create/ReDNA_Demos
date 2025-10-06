#!/usr/bin/env bash
export CORE_BASE="http://127.0.0.1:8015"
export UCNRR_BASE="http://127.0.0.1:8011"

# Llama server
export LLM_PROVIDER="llama"
export LLM_MODEL="llama3"
export LLM_BASE_URL="http://127.0.0.1:PORT"   # <-- change PORT to your local llama server port
export LLM_API_KEY="sk-local-anything"

# Prompts
export PROMPTS_DIR="/Users/davidmakarewicz/Documents/ReDNA_Demos/prompts"
export UCN_PROMPT_MAIN="$PROMPTS_DIR/ucn_rr_ai.md"
export UCN_PROMPT_CONF="$PROMPTS_DIR/ucn_rr_confidence.md"
export CORE_PROMPT_MAIN="$PROMPTS_DIR/core_ai.md"
export CORE_PROMPT_PROP="$PROMPTS_DIR/core_ai_propagation.md"

# Heuristics OFF (let the model do the work)
export UCNRR_USE_MIN_HEURISTICS="false"
