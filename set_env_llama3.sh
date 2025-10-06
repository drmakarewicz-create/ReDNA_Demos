# ~/Documents/ReDNA_Demos/set_env_llama3.sh
#!/usr/bin/env bash
# Env for Core + UCN/RR (LLM via Ollama)
export LLM_PROVIDER=llama
export LLM_MODEL="llama3:latest"      # IMPORTANT: use the full tag you have
export LLM_BASE_URL="http://127.0.0.1:11434"
export LLM_API_KEY="dummy"
export PROMPTS_DIR="$HOME/Documents/ReDNA_Demos/prompts"
export UCN_PROMPT_MAIN="$PROMPTS_DIR/ucn_rr_ai.md"
export UCN_PROMPT_CONF="$PROMPTS_DIR/ucn_rr_confidence.md"
export CORE_PROMPT_MAIN="$PROMPTS_DIR/core_ai.md"
export CORE_PROMPT_PROP="$PROMPTS_DIR/core_ai_propagation.md"
export UCNRR_BASE_URL="http://127.0.0.1:8011"
echo "[env] Llama3 env exported."