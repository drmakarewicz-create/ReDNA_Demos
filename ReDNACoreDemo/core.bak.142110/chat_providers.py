"""Chat provider abstractions with streaming support."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Sequence, Tuple

import requests
from requests import exceptions as requests_exceptions


class ProviderConfigError(Exception):
    """Raised when a provider is misconfigured via environment variables."""


class ProviderRuntimeError(Exception):
    """Raised when a provider fails during generation."""


class ProviderTimeoutError(ProviderRuntimeError):
    """Raised when a provider times out or cannot be reached."""


ChatMessage = Dict[str, str]


@dataclass
class ChatProvider:
    name: str

    def stream(
        self,
        *,
        system_prompt: str,
        persona: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        raise NotImplementedError


class StubChatProvider(ChatProvider):
    RESPONSES = {
        "head coach": "I logged that for the Head Coach board.",
        "rc": "Relationship Coach has that in focus.",
        "padna": "PaDNA Coach noted the style cue.",
        "photo": "Photo Coach queued the shot guidance.",
    }

    ACTIONS = {
        "head coach": "Let's turn it into one concrete action to keep momentum going.",
        "rc": "I'll suggest one empathetic next step so you can move forward confidently.",
        "padna": "I'll confirm one visual adjustment you can apply right now.",
        "photo": "I'll return one camera-ready tweak you can try on the next shoot.",
    }

    def __init__(self) -> None:
        super().__init__(name="stub")

    def stream(
        self,
        *,
        system_prompt: str,
        persona: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        persona_key = persona.lower()
        base = self.RESPONSES.get(persona_key, self.RESPONSES["head coach"])
        action = self.ACTIONS.get(persona_key, self.ACTIONS["head coach"])

        last_user_message = ""
        last_actionable = ""
        for entry in reversed(messages):
            role = entry.get("role", "")
            content = entry.get("content", "").strip()
            if not content:
                continue
            if not last_user_message and role == "user":
                last_user_message = content.rstrip(".?!")
            if role == "assistant" and not last_actionable:
                last_actionable = content
            if last_user_message and last_actionable:
                break

        summary = f" You mentioned '{last_user_message}'." if last_user_message else ""
        continuity = (
            " Building on what we discussed earlier,"
            if last_actionable
            else ""
        )
        reply = f"{base}{summary}{continuity} {action}"

        for token in reply.split():
            yield token + " "


class OpenAIChatProvider(ChatProvider):
    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(name="openai")
        self._api_key = api_key
        self._default_model = model

    def stream(
        self,
        *,
        system_prompt: str,
        persona: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload_messages = [{"role": "system", "content": system_prompt}]
        for entry in messages:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if content:
                payload_messages.append({"role": role, "content": content})

        payload: Dict[str, object] = {
            "model": model or self._default_model,
            "stream": True,
            "messages": payload_messages,
        }

        if temperature is not None:
            payload["temperature"] = max(0.0, min(2.0, float(temperature)))
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = int(max_tokens)

        try:
            with requests.post(url, json=payload, headers=headers, stream=True, timeout=45) as response:
                if response.status_code >= 400:
                    raise ProviderRuntimeError(f"OpenAI error {response.status_code}: {response.text[:200]}")
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        chunk = line[len("data: "):]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
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
        self._default_model = model

    def stream(
        self,
        *,
        system_prompt: str,
        persona: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        url = f"{self._base}/api/generate"

        conversation_lines = []
        for entry in messages:
            role = entry.get("role", "user")
            content = entry.get("content", "").strip()
            if not content:
                continue
            speaker = "User" if role == "user" else "Coach"
            conversation_lines.append(f"{speaker}: {content}")

        prompt_parts = [system_prompt.strip()]
        if conversation_lines:
            prompt_parts.append("Recent conversation:\n" + "\n".join(conversation_lines))
        prompt_parts.append("Coach:")
        prompt = "\n\n".join(part for part in prompt_parts if part)

        payload: Dict[str, object] = {
            "model": model or self._default_model,
            "prompt": prompt,
            "stream": True,
            "options": {},
        }
        options = payload["options"]  # type: ignore[assignment]
        if temperature is not None:
            options["temperature"] = max(0.0, float(temperature))
        if max_tokens is not None and max_tokens > 0:
            options["num_predict"] = int(max_tokens)

        try:
            with requests.post(url, json=payload, stream=True, timeout=45) as response:
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


class AnthropicChatProvider(ChatProvider):
    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(name="anthropic")
        self._api_key = api_key or ""
        self._model = model or "claude-3-5-sonnet-latest"

    def stream(
        self,
        *,
        system_prompt: str,
        persona: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        # Stub for now; no API calls
        yield "[Anthropic provider stubbed response] "
        yield "This is a placeholder. "
        yield "Full Anthropic integration coming soon."


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
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        if not base_url:
            raise ProviderConfigError("OLLAMA_BASE is required for Ollama provider")
        return OllamaChatProvider(base_url=base_url, model=model)
    if normalized == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        return AnthropicChatProvider(api_key=api_key, model=model)
    raise ProviderConfigError(f"Unknown provider '{name}'")


@dataclass
class CircuitState:
    failure_count: int = 0
    first_failure_ts: float = 0.0
    open_until: float = 0.0


_CIRCUIT_STATES: Dict[str, CircuitState] = {}
_CIRCUIT_LOCK = threading.Lock()
_FAILURE_THRESHOLD = max(1, int(os.getenv("HC_CHAT_BREAKER_THRESHOLD", "3")))
_FAILURE_WINDOW = max(1.0, float(os.getenv("HC_CHAT_BREAKER_WINDOW", "120")))
_OPEN_DURATION = max(1.0, float(os.getenv("HC_CHAT_BREAKER_OPEN_SECONDS", "60")))


def resolve_circuit_model(provider: ChatProvider, override: Optional[str]) -> str:
    if isinstance(override, str) and override.strip():
        return override.strip()
    for attr_name in ("_default_model", "default_model", "model"):
        value = getattr(provider, attr_name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "default"


def circuit_key(provider_name: str, model_name: str) -> str:
    return f"{provider_name}:{model_name}".lower()


def circuit_retry_after(key: str) -> Optional[float]:
    now = time.monotonic()
    with _CIRCUIT_LOCK:
        state = _CIRCUIT_STATES.get(key)
        if not state:
            return None
        if state.open_until > now:
            return state.open_until - now
        if state.open_until > 0 and state.open_until <= now:
            _CIRCUIT_STATES.pop(key, None)
        return None


def circuit_record_failure(key: str) -> Tuple[Optional[float], bool]:
    now = time.monotonic()
    with _CIRCUIT_LOCK:
        state = _CIRCUIT_STATES.get(key)
        if state is None:
            state = CircuitState()
            _CIRCUIT_STATES[key] = state

        if state.open_until > now:
            return state.open_until - now, False
        if state.open_until > 0 and state.open_until <= now:
            state.failure_count = 0
            state.first_failure_ts = 0.0
            state.open_until = 0.0

        if state.failure_count == 0 or (now - state.first_failure_ts) > _FAILURE_WINDOW:
            state.failure_count = 1
            state.first_failure_ts = now
        else:
            state.failure_count += 1

        if state.failure_count >= _FAILURE_THRESHOLD:
            state.failure_count = 0
            state.first_failure_ts = 0.0
            state.open_until = now + _OPEN_DURATION
            return state.open_until - now, True

        return None, False


def circuit_record_success(key: str) -> bool:
    with _CIRCUIT_LOCK:
        state = _CIRCUIT_STATES.pop(key, None)
    if not state:
        return False
    return state.open_until > 0
