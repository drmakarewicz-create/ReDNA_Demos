# LLM Provider Migration Guide

## Overview

All LLM calls in ReDNA should route through the `ReDNACoreDemo.core.llm.provider` adapter.
This ensures:
- Single point of configuration
- Easy provider switching (Ollama, OpenAI, Anthropic)
- Fail-fast guards against accidental cloud API usage
- No secrets in logs

## Current Status: Ollama-Only

**Default**: Ollama (local, free)
**Cloud Providers**: Disabled until explicitly enabled

## Files Requiring Migration

The following files have direct OpenAI/Anthropic imports and should be migrated:

### High Priority
- `ReDNACoreDemo/core/rc_llm_agent.py` - Relationship Coach LLM agent
- `ReDNACoreDemo/core/hc_llm_agent.py` - Head Coach LLM agent
- `ReDNACoreDemo/core/api.py` - Core API with direct LLM calls
- `ReDNACoreDemo/core/jarvis_codex/proposal_generator.py` - Jarvis Codex proposals

### Migration Pattern

**Before** (direct OpenAI):
```python
import openai

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}]
)
```

**After** (via adapter):
```python
from ReDNACoreDemo.core.llm.provider import get_client, ChatMessage

llm = get_client()
result = llm.chat([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": prompt}
])
# Access result["message"]["content"] per Ollama response schema
```

**Before** (direct Anthropic):
```python
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-3-sonnet",
    messages=[{"role": "user", "content": prompt}]
)
```

**After** (via adapter):
```python
from ReDNACoreDemo.core.llm.provider import get_client

llm = get_client()
result = llm.chat([
    {"role": "user", "content": prompt}
])
```

## Ollama Response Format

Ollama's `/api/chat` returns:
```json
{
  "model": "llama3:8b",
  "created_at": "2024-...",
  "message": {
    "role": "assistant",
    "content": "The response text..."
  },
  "done": true
}
```

Access the response content: `result["message"]["content"]`

## Configuration

Set in `.env`:
```bash
# Current defaults
LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3:8b

# Cloud providers disabled
OPENAI_ENABLED=false
ANTHROPIC_ENABLED=false
AZURE_OPENAI_ENABLED=false
```

## Future: Enabling Cloud Providers

When ready to enable OpenAI:
1. Set `OPENAI_ENABLED=true` in `.env`
2. Set `LLM_PROVIDER=openai`
3. Provide `OPENAI_API_KEY`
4. Update adapter to handle OpenAI SDK calls

## Testing

```bash
# 1. Ensure Ollama is running
ollama run llama3:8b "Say hello"

# 2. Test adapter
python3 -c "
from ReDNACoreDemo.core.llm.provider import get_client
llm = get_client()
print('Health:', llm.health())
result = llm.chat([{'role': 'user', 'content': 'Say hello in 3 words'}])
print('Response:', result['message']['content'])
"

# 3. Check CP++ LLM Status tile shows green
streamlit run control_panel_plus_plus.py
```

## Notes

- All LLM calls must go through `core.llm.provider`
- Do NOT import `openai` or `anthropic` directly
- The adapter handles provider selection and guards
- No secrets in logs (adapter suppresses keys)
