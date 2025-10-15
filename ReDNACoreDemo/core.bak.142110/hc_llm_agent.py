"""
Head Coach LLM Agent (Sprint 2a)
==================================

Handles LLM-based conversation intelligence for Head Coach.

Supports:
- OpenAI (GPT-4o-mini, GPT-4, etc.)
- Anthropic (Claude 3.5 Sonnet, etc.)
- Mock mode (deterministic fallback)

Features:
- Reads conversation history for context
- Includes high-curiosity traits in prompt
- Graceful fallback on API failures
- Token tracking and provenance
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def generate_reply(
    user_id: str,
    user_message: str,
    state_snapshot: Dict[str, Any],
    model_config: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Generate LLM reply to user message.

    Args:
        user_id: User identifier
        user_message: User's message content
        state_snapshot: Dict with high_curiosity_traits list
        model_config: LLM configuration (provider, model, max_tokens, etc.)
        conversation_history: Recent conversation messages for context

    Returns:
        {
            "content": "<assistant reply>",
            "reasoning": "<short explanation>",
            "tokens_used": <int>,
            "model": "<model_name>",
            "provider": "<provider_name>"
        }
    """
    provider = model_config.get("provider", "mock")
    model = model_config.get("model", "gpt-4o-mini")
    max_tokens = model_config.get("max_tokens", 300)
    temperature = model_config.get("temperature", 0.7)
    timeout_sec = model_config.get("timeout_sec", 10)

    # Build prompt context
    context_messages = _build_context_messages(
        user_message=user_message,
        state_snapshot=state_snapshot,
        conversation_history=conversation_history or []
    )

    # Route to appropriate provider
    try:
        if provider == "openai":
            return _generate_openai_reply(
                context_messages=context_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout_sec=timeout_sec
            )
        elif provider == "anthropic":
            return _generate_anthropic_reply(
                context_messages=context_messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout_sec=timeout_sec
            )
        else:
            # Mock mode (deterministic fallback)
            return _generate_mock_reply(
                user_message=user_message,
                state_snapshot=state_snapshot,
                conversation_history=conversation_history or []
            )

    except Exception as e:
        logger.warning(f"LLM generation failed for {user_id}: {e}. Falling back to mock.")
        return _generate_mock_reply(
            user_message=user_message,
            state_snapshot=state_snapshot,
            conversation_history=conversation_history or []
        )


def _build_context_messages(
    user_message: str,
    state_snapshot: Dict[str, Any],
    conversation_history: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    Build context messages for LLM prompt.

    Returns OpenAI-style message list:
    [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
        ...
        {"role": "user", "content": "<current_message>"}
    ]
    """
    messages = []

    # System message with HC persona and current state
    system_content = _build_system_message(state_snapshot)
    messages.append({"role": "system", "content": system_content})

    # Add conversation history (last 5 messages)
    for msg in conversation_history[-5:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        messages.append({"role": role, "content": content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    return messages


def _build_system_message(state_snapshot: Dict[str, Any]) -> str:
    """
    Build system message with HC persona and current user state.
    Uses simplified prompt for local models (ollama), full prompt for cloud models.
    """
    import os
    from pathlib import Path

    # Check if using local model (Ollama) - use simplified prompt
    provider = os.getenv("HC_CHAT_PROVIDER", "").lower()
    use_simple = provider in ["ollama", "local"]

    # Load appropriate prompt
    if use_simple:
        prompt_file = Path(__file__).parent.parent / "prompts" / "head_coach_simple.md"
        try:
            base_prompt = prompt_file.read_text(encoding="utf-8")
        except Exception:
            # Fallback to inline simple prompt if file not found
            base_prompt = "You are the Head Coach, a friendly AI assistant. Chat naturally, keep responses short (2-3 sentences), and show genuine interest in learning about the user."
    else:
        # Use full v2.0 prompt for capable cloud models
        from .hc_prompt_loader import get_hc_prompt_text
        base_prompt = get_hc_prompt_text()

    # Append current user state context (only for full prompt)
    if not use_simple:
        high_curiosity_traits = state_snapshot.get("high_curiosity_traits", [])
        state_context = "\n\n---\n\nCurrent User State:\n"

        if high_curiosity_traits:
            state_context += "High-Curiosity Traits (need evidence):\n"
            for trait in high_curiosity_traits[:3]:  # Top 3
                trait_name = trait.get("trait", "Unknown").split(".")[-1]
                curiosity = int(trait.get("curiosity", 0))
                state_context += f"  • {trait_name}: curiosity {curiosity}\n"
        else:
            state_context += "No high-curiosity traits right now.\n"

        state_context += "\nRespond to the user's message with actionable guidance based on the principles above."
        return base_prompt + state_context

    return base_prompt


def _generate_openai_reply(
    context_messages: List[Dict[str, str]],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout_sec: int
) -> Dict[str, Any]:
    """
    Generate reply using OpenAI API.
    """
    import openai

    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")

    client = openai.OpenAI(api_key=api_key, timeout=timeout_sec)

    response = client.chat.completions.create(
        model=model,
        messages=context_messages,
        max_tokens=max_tokens,
        temperature=temperature
    )

    reply_content = response.choices[0].message.content
    tokens_used = response.usage.total_tokens

    return {
        "content": reply_content,
        "reasoning": f"Generated by {model}",
        "tokens_used": tokens_used,
        "model": model,
        "provider": "openai"
    }


def _generate_anthropic_reply(
    context_messages: List[Dict[str, str]],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout_sec: int
) -> Dict[str, Any]:
    """
    Generate reply using Anthropic API.
    """
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout_sec)

    # Anthropic uses different message format (system separate)
    system_msg = context_messages[0]["content"]
    conversation_msgs = context_messages[1:]

    response = client.messages.create(
        model=model,
        system=system_msg,
        messages=conversation_msgs,
        max_tokens=max_tokens,
        temperature=temperature
    )

    reply_content = response.content[0].text
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    return {
        "content": reply_content,
        "reasoning": f"Generated by {model}",
        "tokens_used": tokens_used,
        "model": model,
        "provider": "anthropic"
    }


def _generate_mock_reply(
    user_message: str,
    state_snapshot: Dict[str, Any],
    conversation_history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate deterministic mock reply (fallback).
    """
    high_curiosity_traits = state_snapshot.get("high_curiosity_traits", [])
    context_count = len(conversation_history)

    if high_curiosity_traits:
        top_trait = high_curiosity_traits[0]
        trait_name = top_trait.get("trait", "Unknown").split(".")[-1]
        curiosity = int(top_trait.get("curiosity", 0))

        reply = f"Mock reply: I see you have high curiosity for {trait_name} (curiosity: {curiosity}). Would you like to add evidence? [context: {context_count} messages]"
    else:
        reply = f"Mock reply for: {user_message} [context: {context_count} messages, no high-curiosity traits]"

    return {
        "content": reply,
        "reasoning": "Mock mode (no API key)",
        "tokens_used": 0,
        "model": "mock",
        "provider": "mock"
    }


def load_conversation_history(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Load recent conversation history for context.

    Args:
        user_id: User identifier
        limit: Max messages to load (default: 5)

    Returns:
        List of message dicts with {role, content, ts}
    """
    from pathlib import Path

    user_dir = Path("data/users") / user_id
    conv_dir = user_dir / "hc" / "conversation"

    if not conv_dir.exists():
        return []

    # Get today's conversation file
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    log_file = conv_dir / f"{date_str}.jsonl"

    if not log_file.exists():
        return []

    # Read messages
    messages = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
    except Exception as e:
        logger.warning(f"Error loading conversation history for {user_id}: {e}")
        return []

    # Return most recent {limit} messages
    return messages[-limit:]
