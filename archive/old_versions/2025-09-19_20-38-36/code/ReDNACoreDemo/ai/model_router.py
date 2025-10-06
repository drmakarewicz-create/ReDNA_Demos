# ai/model_router.py
from __future__ import annotations
import os, json, time, requests
from typing import Dict, Any, Optional, Tuple

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL      = os.getenv("LLM_MODEL", "llama3")
PROVIDER           = os.getenv("LLM_PROVIDER", "ollama").lower()  # 'ollama' | 'openai' | 'azure' (future)

class LLMError(RuntimeError): ...
def _as_json(s: str) -> Any:
    try: return json.loads(s)
    except Exception: return {"text": s}

def call_llm(prompt: str, system: Optional[str] = None, temperature: float = 0.2,
             max_tokens: int = 512, json_mode: bool = True,
             model: Optional[str] = None, timeout_s: int = 30) -> Dict[str, Any]:
    """Minimal, swappable LLM caller. Default: Ollama llama3."""
    model = model or DEFAULT_MODEL
    if PROVIDER == "ollama":
        url = f"{DEFAULT_OLLAMA_URL}/api/generate"
        full_prompt = (f"<<SYS>>\n{system}\n<</SYS>>\n" if system else "") + prompt
        payload = {
            "model": model,
            "prompt": full_prompt,
            "options": {"temperature": temperature},
            "stream": False,
        }
        t0 = time.time()
        try:
            r = requests.post(url, json=payload, timeout=timeout_s)
        except Exception as e:
            raise LLMError(f"Ollama request failed: {e}")
        if r.status_code != 200:
            raise LLMError(f"Ollama HTTP {r.status_code}: {r.text[:400]}")
        data = r.json()
        raw = data.get("response", "")
        out = _as_json(raw) if json_mode else {"text": raw}
        out["_provider"] = "ollama"
        out["_model"] = model
        out["_latency_ms"] = int((time.time()-t0)*1000)
        return out

    # Future: OpenAI / Azure (kept here for quick switch)
    raise LLMError(f"LLM provider '{PROVIDER}' not supported in this demo.")