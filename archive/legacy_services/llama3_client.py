# llama3_client.py
import os
import json
import http.client
from typing import Dict, Any

# Env flags (safe defaults)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
AI_ENABLED   = os.getenv("REDNA_AI_ENABLED", "false").lower() == "true"
DEBUG        = os.getenv("REDNA_AI_DEBUG", "0") in ("1", "true", "True")

def _dbg(msg: str):
    if DEBUG:
        print(f"[AI-DEBUG] {msg}")

def chat(system_text: str, user_text: str) -> Dict[str, Any]:
    """
    Send prompt to local Ollama chat API and return {"ok": bool, ...}.
    If AI is disabled/unavailable, returns {"ok": False, "reason": "..."}.
    """
    if not AI_ENABLED:
        _dbg("AI disabled by env var REDNA_AI_ENABLED.")
        return {"ok": False, "reason": "ai_disabled"}

    try:
        conn = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=60)
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user",   "content": user_text}
            ],
            "stream": False
        })
        _dbg(f"POST http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat")
        conn.request("POST", "/api/chat", body=payload,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="ignore")
        status = resp.status
        conn.close()

        _dbg(f"HTTP {status}; raw length={len(raw)}")
        if status != 200:
            return {"ok": False, "reason": f"http_{status}", "raw": raw[:400]}

        # Some Ollama builds return a JSON envelope; others may return plain text.
        try:
            data = json.loads(raw)
            content = (data.get("message") or {}).get("content", "")
            _dbg(f"Parsed JSON envelope; content length={len(content)}")
            return {"ok": True, "text": content}
        except Exception as e:
            _dbg(f"JSON envelope parse failed: {e}. Returning raw.")
            return {"ok": True, "text": raw}
    except Exception as e:
        _dbg(f"Connection error: {type(e).__name__}: {e}")
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}