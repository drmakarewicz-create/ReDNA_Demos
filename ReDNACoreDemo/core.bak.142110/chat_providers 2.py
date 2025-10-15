"""Chat provider abstraction for Head Coach chat streaming."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable

import requests
from requests import exceptions as requests_exceptions


class ProviderConfigError(Exception):
    """Raised when a provider is misconfigured via environment variables."""


class ProviderRuntimeError(Exception):
    """Raised when a provider fails during generation."""


class ProviderTimeoutError(ProviderRuntimeError):
    """Raised when a provider times out or cannot be reached."""


@dataclass
class ChatProvider:
    name: str

    def stream(
        self,
        *,
        system_prompt: str,
        persona_prompt: str,
        user_text: str,
        persona: str,
    ) -> Iterable[str]:
        raise NotImplementedError


class StubChatProvider(ChatProvider):
    RESPONSES = {
        "head coach": "(Head Coach) Thanks for the update. I noted your message and will suggest a next step shortly.",
        "rc": "(Relationship Coach) Appreciate you sharing this—let’s focus on a practical next action together.",
        "padna": "(PaDNA Coach) Got it. I’ll log this and circle back with a visual check when ready.",
        "photo": "(Photo Coach) Understood. I’ll keep it in mind for the next refinement pass.",
    }

    def __init__(self) -> None:
        super().__init__(name="stub")

    def stream(
        self,
        *,
        system_prompt: str,
        persona_prompt: str,
        user_text: str,
        persona: str,
    ) -> Iterable[str]:
        persona_key = persona.lower()
        base_reply = self.RESPONSES.get(
            persona_key,
            "(Coach) I've logged your update and will follow up soon.",
        )
        summary = user_text.strip().rstrip(".?!")
        additive = f" Noted your point about '{summary}'." if summary else ""
        response = base_reply + additive
        for token in response.split():
            yield token + " "


class OpenAIChatProvider(ChatProvider):
    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(name="openai")
        self._api_key = api_key
        self._model = model

    def stream(
        self,
        *,
        system_prompt: str,
        persona_prompt: str,
        user_text: str,
        persona: str,
    ) -> Iterable[str]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": persona_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        try:
            with requests.post(url, json=payload, headers=headers, stream=True, timeout=30) as response:
                if response.status_code >= 400:
                    raise ProviderRuntimeError(f"OpenAI error {response.status_code}: {response.text[:200]}")
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        content = line[len("data: "):]
                        if content.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(content)
                        except Exception:
                            continue
                        delta = data.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield delta
        except ProviderRuntimeError:
            raise
        except requests_exceptions.Timeout as exc:
            raise ProviderTimeoutError("OpenAI request timed out") from exc
        except requests_exceptions.RequestException as exc:
            raise ProviderRuntimeError(str(exc)) from exc
        except Exception as exc:
            raise ProviderRuntimeError(str(exc)) from exc


class OllamaChatProvider(ChatProvider):
    def __init__(self, base_url: str, model: str) -> None:
        super().__init__(name="ollama")
        self._base = base_url.rstrip("/")
        self._model = model

    def stream(
        self,
        *,
        system_prompt: str,
        persona_prompt: str,
        user_text: str,
        persona: str,
    ) -> Iterable[str]:
        url = f"{self._base}/api/generate"
        prompt = (
            f"{system_prompt}\n\nPersona guidance:\n{persona_prompt}\n\n"
            f"User message: {user_text}\nAssistant:"
        )
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.6},
        }
        try:
            with requests.post(url, json=payload, stream=True, timeout=30) as response:
                if response.status_code >= 400:
                    raise ProviderRuntimeError(f"Ollama error {response.status_code}: {response.text[:200]}")
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    delta = data.get("response")
                    if delta:
                        yield delta
                    if data.get("done"):
                        break
        except ProviderRuntimeError:
            raise
        except requests_exceptions.Timeout as exc:
            raise ProviderTimeoutError("Ollama request timed out") from exc
        except requests_exceptions.RequestException as exc:
            raise ProviderRuntimeError(str(exc)) from exc
        except Exception as exc:
            raise ProviderRuntimeError(str(exc)) from exc


def get_provider(name: str) -> ChatProvider:
    normalized = (name or "stub").strip().lower()
    if normalized in {"", "stub"}:
        return StubChatProvider()
    if normalized == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            raise ProviderConfigError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIChatProvider(api_key=api_key, model=model)
    if normalized == "ollama":
        base_url = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.1")
        if not base_url:
            raise ProviderConfigError("OLLAMA_BASE is required for Ollama provider")
        return OllamaChatProvider(base_url=base_url, model=model)
    raise ProviderConfigError(f"Unknown provider '{name}'")
