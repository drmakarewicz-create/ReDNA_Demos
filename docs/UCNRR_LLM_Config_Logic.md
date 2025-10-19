# UCNRR LLM Configuration Logic

## Code Location

**File**: `UCN_RR_Demo/ucnrr_app.py`
**Function**: `_is_llm_configured()` (lines 853-863)

## Code Snippet

```python
def _is_llm_configured() -> bool:
    """Check if LLM is properly configured based on provider."""
    if not LLM_PROVIDER:
        return False

    # Ollama doesn't need API key, just needs provider + base URL
    if LLM_PROVIDER.lower() == "ollama":
        return bool(LLM_BASE_URL or os.getenv("OLLAMA_BASE_URL"))

    # OpenAI, Anthropic, etc. need API key
    return bool(LLM_API_KEY)
```

## Truth Table

| LLM_PROVIDER | LLM_BASE_URL or OLLAMA_BASE_URL | LLM_API_KEY | Result | Reason |
|--------------|----------------------------------|-------------|--------|--------|
| `None` or `""` | - | - | **False** | No provider specified |
| `"ollama"` | Set (non-empty) | - | **True** | Ollama doesn't require API key |
| `"ollama"` | `None` or `""` | - | **False** | Ollama needs base URL |
| `"openai"` | - | Set (non-empty) | **True** | Paid providers need API key |
| `"anthropic"` | - | Set (non-empty) | **True** | Paid providers need API key |
| `"openai"` | - | `None` or `""` | **False** | Paid provider missing API key |

## Environment Variables Required

### For Ollama (local)
- **LLM_PROVIDER**: Must be set to `"ollama"`
- **LLM_BASE_URL** or **OLLAMA_BASE_URL**: Must be set (e.g., `http://127.0.0.1:11434`)
- **LLM_MODEL**: Recommended (e.g., `"phi3:mini"`)

### For OpenAI / Anthropic (paid)
- **LLM_PROVIDER**: Must be set to `"openai"` or `"anthropic"`
- **LLM_BASE_URL**: API endpoint (e.g., `https://api.openai.com`)
- **LLM_API_KEY**: Required authentication token
- **LLM_MODEL**: Model name (e.g., `"gpt-4o-mini"`)

## Additional Dependencies

Beyond `_is_llm_configured()` returning `True`, the following are also required:

1. **Prompt file**: `prompts/ucn_rr_ai.md` must exist
2. **Network connectivity**: Ollama service must be running and reachable
3. **Model availability**: For Ollama, the specified model must be pulled (`ollama pull <model>`)

## Debug Endpoints

Use these endpoints to diagnose LLM configuration issues:

- **GET /ucnrr/debug/config**: Shows effective LLM config, env paths, and `llm_configured` status with reason
- **GET /ucnrr/debug/probe**: Tests actual connectivity to Ollama `/api/tags` and `/api/generate`
- **GET /health** or **GET /api/health**: Includes `llm_configured` boolean

## Example Configuration (.env)

```bash
# Ollama (local, free)
LLM_PROVIDER=ollama
LLM_MODEL=phi3:mini
LLM_BASE_URL=http://127.0.0.1:11434
# No LLM_API_KEY needed

# OpenAI (paid)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com
LLM_API_KEY=sk-proj-...

# Anthropic (paid)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=sk-ant-...
```
