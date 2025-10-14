"""
Relationship Coach LLM Agent
============================

Handles LLM interactions for the Relationship Coach persona.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def generate_reply(
    user_id: str,
    user_message: str,
    state_snapshot: Dict[str, Any],
    model_config: Dict[str, Any],
    conversation_history: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Generate Relationship Coach reply using configured LLM.

    Args:
        user_id: User identifier
        user_message: User's message
        state_snapshot: Current state (delegation context, curiosity targets, etc.)
        model_config: LLM configuration (provider, model, etc.)
        conversation_history: Recent conversation messages

    Returns:
        Dict with 'content', 'provider', 'model', 'finish_reason'
    """
    from .relationship_coach import build_relationship_coach_prompt

    # Extract delegation context from state
    delegation_id = state_snapshot.get("delegation_id")
    curiosity_targets = state_snapshot.get("curiosity_targets", [])
    user_context = {
        "tolerance_for_nudging": state_snapshot.get("tolerance_for_nudging", 0.5),
        "overall_rr": state_snapshot.get("overall_rr"),
    }

    # Build system prompt
    system_prompt = build_relationship_coach_prompt(
        delegation_id=delegation_id,
        curiosity_targets=curiosity_targets,
        user_context=user_context
    )

    # Build context messages for LLM
    context_messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in conversation_history:
        context_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    # Add current user message
    context_messages.append({"role": "user", "content": user_message})

    # Get LLM reply based on provider
    provider = model_config.get("provider", "mock")

    if provider == "mock":
        return _generate_mock_reply(context_messages, curiosity_targets)
    elif provider == "openai":
        return _generate_openai_reply(context_messages, model_config)
    elif provider == "anthropic":
        return _generate_anthropic_reply(context_messages, model_config)
    else:
        logger.warning(f"Unknown provider '{provider}', falling back to mock")
        return _generate_mock_reply(context_messages, curiosity_targets)


def _generate_mock_reply(
    context_messages: List[Dict[str, str]],
    curiosity_targets: List[str]
) -> Dict[str, Any]:
    """Generate mock reply for testing."""
    user_msg = context_messages[-1]["content"].lower()

    # Check for delegation-related keywords
    if curiosity_targets and any(
        kw in user_msg for kw in ["attachment", "relationship", "partner", "conflict", "trust"]
    ):
        target_names = [t.split(".")[-1] for t in curiosity_targets[:2]]
        reply = f"I'd love to explore your {' and '.join(target_names)} with you. Can you tell me about a recent relationship experience that comes to mind?"
    elif "attachment" in user_msg:
        reply = "Attachment styles shape how we connect with others. Tell me about your closest relationships - do you tend to need a lot of reassurance, or do you prefer more independence?"
    elif "conflict" in user_msg or "argument" in user_msg:
        reply = "When conflict arises in relationships, what's your typical pattern? Do you tend to withdraw, engage directly, or something else?"
    elif "trust" in user_msg:
        reply = "Trust is foundational. What does it take for you to truly trust someone? And how do you respond when that trust feels threatened?"
    else:
        reply = "I'm here to help you understand your relationship patterns. What's on your mind today - is there a relationship dynamic or emotional pattern you'd like to explore?"

    return {
        "content": reply,
        "provider": "mock",
        "model": "mock-rc-v1",
        "finish_reason": "stop"
    }


def _generate_openai_reply(
    context_messages: List[Dict[str, str]],
    model_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate reply using OpenAI API."""
    try:
        import openai
        import os

        openai.api_key = os.getenv("OPENAI_API_KEY")

        if not openai.api_key:
            logger.warning("OPENAI_API_KEY not set, falling back to mock")
            return _generate_mock_reply(context_messages, [])

        model = model_config.get("model", "gpt-4o-mini")
        max_tokens = model_config.get("max_tokens", 300)
        temperature = model_config.get("temperature", 0.7)
        timeout = model_config.get("timeout_sec", 10)

        response = openai.ChatCompletion.create(
            model=model,
            messages=context_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout
        )

        content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        return {
            "content": content,
            "provider": "openai",
            "model": model,
            "finish_reason": finish_reason
        }

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return _generate_mock_reply(context_messages, [])


def _generate_anthropic_reply(
    context_messages: List[Dict[str, str]],
    model_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate reply using Anthropic API."""
    try:
        import anthropic
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, falling back to mock")
            return _generate_mock_reply(context_messages, [])

        client = anthropic.Anthropic(api_key=api_key)

        model = model_config.get("model", "claude-3-5-sonnet-20241022")
        max_tokens = model_config.get("max_tokens", 300)
        temperature = model_config.get("temperature", 0.7)
        timeout = model_config.get("timeout_sec", 10)

        # Extract system message
        system_msg = ""
        messages = []
        for msg in context_messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                messages.append(msg)

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            system=system_msg,
            messages=messages
        )

        content = response.content[0].text
        finish_reason = response.stop_reason

        return {
            "content": content,
            "provider": "anthropic",
            "model": model,
            "finish_reason": finish_reason
        }

    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return _generate_mock_reply(context_messages, [])
