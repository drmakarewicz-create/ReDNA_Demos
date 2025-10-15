# ReDNACoreDemo/core/llm/provider.py
"""
LLM Provider Adapter - Single interface for all LLM calls.
Currently Ollama-only. Future: add OpenAI/Anthropic behind feature flags.
"""

from __future__ import annotations
import os
import requests
from typing import Any, Dict, List, Optional, TypedDict


class ChatMessage(TypedDict, total=False):
    """Standard chat message format."""
    role: str  # "system" | "user" | "assistant"
    content: str


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse environment variable as boolean."""
    v = os.getenv(name, "")
    if not v:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


class LLMClient:
    """
    A thin provider adapter for LLM calls.
    Currently only allows Ollama (local, free).
    Cloud providers (OpenAI, Anthropic, Azure) are disabled until explicitly enabled.
    """

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.default_model = os.getenv("OLLAMA_MODEL", "llama3:8b")

        # Hard guards for cloud providers
        self.openai_enabled = _env_bool("OPENAI_ENABLED", False)
        self.anthropic_enabled = _env_bool("ANTHROPIC_ENABLED", False)
        self.azure_enabled = _env_bool("AZURE_OPENAI_ENABLED", False)
        self.reject_openai_key_if_not_enabled = _env_bool(
            "REJECT_OPENAI_KEY_IF_NOT_ENABLED", True
        )

        # Prevent accidental cloud API usage
        if self.reject_openai_key_if_not_enabled and not self.openai_enabled:
            # Remove OpenAI key from environment to prevent accidental use
            if "OPENAI_API_KEY" in os.environ:
                os.environ.pop("OPENAI_API_KEY", None)

        # Hard fail if someone tries to switch to a non-allowed provider
        if self.provider != "ollama":
            raise RuntimeError(
                f"LLM provider '{self.provider}' is not enabled. "
                "Set LLM_PROVIDER=ollama (default) or explicitly enable a cloud provider "
                "by setting OPENAI_ENABLED=true, ANTHROPIC_ENABLED=true, etc."
            )

    def health(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            r = requests.get(f"{self.ollama_host}/api/tags", timeout=3)
            return r.ok
        except Exception:
            return False

    def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Send a chat request to Ollama.

        Args:
            messages: List of chat messages with 'role' and 'content'
            model: Optional model override (defaults to OLLAMA_MODEL)
            **kwargs: Additional Ollama parameters (temperature, options, etc.)

        Returns:
            Parsed JSON response from Ollama

        Raises:
            requests.HTTPError: If the request fails
        """
        use_model = (model or self.default_model).strip()
        payload: Dict[str, Any] = {"model": use_model, "messages": messages}

        # Allow extra parameters through, e.g., temperature, options
        payload.update(kwargs)

        resp = requests.post(
            f"{self.ollama_host}/api/chat",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Simple text generation (non-chat) via Ollama.

        Args:
            prompt: The prompt text
            model: Optional model override
            **kwargs: Additional Ollama parameters

        Returns:
            Parsed JSON response from Ollama
        """
        use_model = (model or self.default_model).strip()
        payload: Dict[str, Any] = {"model": use_model, "prompt": prompt}
        payload.update(kwargs)

        resp = requests.post(
            f"{self.ollama_host}/api/generate",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()


# Convenience singleton
_global_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    """Get the global LLM client singleton."""
    global _global_client
    if _global_client is None:
        _global_client = LLMClient()
    return _global_client
