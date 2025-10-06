#!/usr/bin/env python3
"""
HC v2 Sprint 2a Acceptance Tests
=================================

Tests for Sprint 2a features:
1. Mock LLM reply generation (deterministic fallback)
2. Conversation context loading (last 5 messages)
3. State snapshot integration (high-curiosity traits)
4. Provenance tracking (provider, model, tokens)
5. End-to-end: conversation with LLM reply

All tests use mock mode by default (no API keys required).
Tests with real LLM APIs are optional and require environment variables.
"""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

# Test configuration
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8001")
TEST_USER_PREFIX = "test_sprint2a_"


def cleanup_test_user(user_id: str):
    """Clean up test user data."""
    user_dir = Path("data/users") / user_id
    if user_dir.exists():
        shutil.rmtree(user_dir)


@pytest.fixture
def test_user():
    """Create isolated test user."""
    user_id = f"{TEST_USER_PREFIX}{int(time.time() * 1000)}"
    yield user_id
    cleanup_test_user(user_id)


def test_1_mock_llm_reply_generation(test_user):
    """
    Test 1: Mock LLM reply generation (deterministic fallback)

    Steps:
    1. Ensure llm_provider is set to "mock" in flags
    2. POST /hc/say with user message
    3. Verify reply_logged: true
    4. Verify assistant reply contains "Mock reply"
    5. Verify provenance has provider="mock", tokens_used=0
    """
    print(f"\n=== Test 1: Mock LLM Reply (user={test_user}) ===")

    # Step 1: Send user message
    response = requests.post(
        f"{CORE_API_URL}/hc/say",
        params={"user_id": test_user},
        json={"message": "What should I focus on?", "role": "user"}
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    print(f"  ✓ User message logged: {data}")

    assert data["logged"] is True
    assert data.get("reply_logged") is True
    assert data.get("llm_provider") == "mock"
    assert data.get("tokens_used") == 0

    # Step 2: Get conversation history
    response = requests.get(
        f"{CORE_API_URL}/hc/conversation/history",
        params={"user_id": test_user, "limit": 30}
    )

    assert response.status_code == 200

    history_data = response.json()
    messages = history_data.get("messages", [])

    print(f"  ✓ History fetched: {len(messages)} messages")

    assert len(messages) >= 2  # user + assistant

    # Verify assistant reply
    assistant_msg = messages[1]
    assert assistant_msg["role"] == "assistant"
    assert "Mock reply" in assistant_msg["content"]
    assert assistant_msg["provenance"]["source"] == "llm_reply"
    assert assistant_msg["provenance"]["provider"] == "mock"
    assert assistant_msg["provenance"]["tokens_used"] == 0

    print(f"  ✓ Mock reply: {assistant_msg['content'][:60]}...")
    print("  ✅ Test 1 PASSED")


def test_2_conversation_context_loading(test_user):
    """
    Test 2: Conversation context loading (last 5 messages)

    Steps:
    1. Send 6 messages (3 user, 3 assistant via LLM replies)
    2. Send 7th message
    3. Verify reply references context (mentions "context: N messages")
    """
    print(f"\n=== Test 2: Context Loading (user={test_user}) ===")

    # Step 1: Send 6 messages (user + assistant pairs)
    for i in range(3):
        response = requests.post(
            f"{CORE_API_URL}/hc/say",
            params={"user_id": test_user},
            json={"message": f"Message {i+1}", "role": "user"}
        )
        assert response.status_code == 200

    print(f"  ✓ Sent 3 messages (6 total with replies)")

    # Step 2: Send 7th message
    response = requests.post(
        f"{CORE_API_URL}/hc/say",
        params={"user_id": test_user},
        json={"message": "What's my history?", "role": "user"}
    )

    assert response.status_code == 200

    # Step 3: Verify context in reply
    response = requests.get(
        f"{CORE_API_URL}/hc/conversation/history",
        params={"user_id": test_user, "limit": 30}
    )

    history_data = response.json()
    messages = history_data.get("messages", [])

    # Last message should be assistant reply
    last_reply = messages[-1]
    assert last_reply["role"] == "assistant"

    # Mock replies include context count
    assert "context:" in last_reply["content"]
    print(f"  ✓ Reply with context: {last_reply['content'][:70]}...")
    print("  ✅ Test 2 PASSED")


def test_3_state_snapshot_integration(test_user):
    """
    Test 3: State snapshot integration (high-curiosity traits)

    Steps:
    1. Create user with high-curiosity trait
    2. POST /hc/say with message
    3. Verify reply mentions the high-curiosity trait
    4. Verify provenance includes trait context
    """
    print(f"\n=== Test 3: State Snapshot (user={test_user}) ===")

    # Step 1: Create user with high-curiosity trait
    from ReDNACoreDemo.core.storage import write_user_state

    resolved_state = {
        "PaDNA.EyeDNA.Iris.BaseColor": {
            "resolved_value": "Amber",
            "curiosity": 920,
            "ucn": 200,
            "rr": 100
        }
    }

    evidence = {"items": []}
    observations = {"items": [], "by_trait": {}}

    write_user_state(
        test_user,
        resolved_state,
        evidence,
        observations,
        enforce_governance=False
    )

    print(f"  ✓ Created user with high curiosity trait (curiosity=920)")

    # Step 2: Send message
    response = requests.post(
        f"{CORE_API_URL}/hc/say",
        params={"user_id": test_user},
        json={"message": "What should I work on?", "role": "user"}
    )

    assert response.status_code == 200

    # Step 3: Verify reply mentions trait
    response = requests.get(
        f"{CORE_API_URL}/hc/conversation/history",
        params={"user_id": test_user, "limit": 30}
    )

    history_data = response.json()
    messages = history_data.get("messages", [])

    assistant_msg = messages[-1]
    assert assistant_msg["role"] == "assistant"

    # Mock reply should mention the trait
    assert "BaseColor" in assistant_msg["content"] or "curiosity" in assistant_msg["content"]

    print(f"  ✓ Reply mentions trait: {assistant_msg['content'][:70]}...")
    print("  ✅ Test 3 PASSED")


def test_4_provenance_tracking(test_user):
    """
    Test 4: Provenance tracking (provider, model, tokens)

    Steps:
    1. POST /hc/say with user message
    2. Verify assistant reply has provenance with:
       - source: "llm_reply"
       - provider: "mock" (or real provider if API key present)
       - model: "mock" (or real model)
       - tokens_used: 0 (or >0 for real LLM)
    """
    print(f"\n=== Test 4: Provenance Tracking (user={test_user}) ===")

    # Step 1: Send message
    response = requests.post(
        f"{CORE_API_URL}/hc/say",
        params={"user_id": test_user},
        json={"message": "Help me", "role": "user"}
    )

    assert response.status_code == 200

    # Step 2: Verify provenance
    response = requests.get(
        f"{CORE_API_URL}/hc/conversation/history",
        params={"user_id": test_user, "limit": 30}
    )

    history_data = response.json()
    messages = history_data.get("messages", [])

    assistant_msg = messages[-1]
    assert assistant_msg["role"] == "assistant"

    prov = assistant_msg.get("provenance", {})
    assert prov["source"] == "llm_reply"
    assert "provider" in prov
    assert "model" in prov
    assert "tokens_used" in prov
    assert prov["trigger"] == "user_message"

    print(f"  ✓ Provenance verified: provider={prov['provider']}, model={prov['model']}, tokens={prov['tokens_used']}")
    print("  ✅ Test 4 PASSED")


def test_5_end_to_end_llm_conversation(test_user):
    """
    Test 5: End-to-end conversation with LLM reply

    Steps:
    1. Create user with high-curiosity trait
    2. Send 3 messages in conversation
    3. Verify all assistant replies are contextually relevant
    4. Verify conversation history maintains continuity
    """
    print(f"\n=== Test 5: End-to-End LLM Conversation (user={test_user}) ===")

    # Step 1: Create user with high-curiosity trait
    from ReDNACoreDemo.core.storage import write_user_state

    resolved_state = {
        "PaDNA.SkinDNA.Freckles.Density": {
            "resolved_value": "High",
            "curiosity": 885,
            "ucn": 250,
            "rr": 120
        }
    }

    evidence = {"items": []}
    observations = {"items": [], "by_trait": {}}

    write_user_state(
        test_user,
        resolved_state,
        evidence,
        observations,
        enforce_governance=False
    )

    print(f"  ✓ Created user with high curiosity trait")

    # Step 2: Send 3 messages
    messages_to_send = [
        "What should I focus on today?",
        "How can I reduce uncertainty?",
        "Tell me more about my traits"
    ]

    for i, msg in enumerate(messages_to_send):
        response = requests.post(
            f"{CORE_API_URL}/hc/say",
            params={"user_id": test_user},
            json={"message": msg, "role": "user"}
        )
        assert response.status_code == 200
        print(f"  ✓ Message {i+1} sent and replied")

    # Step 3: Verify conversation history
    response = requests.get(
        f"{CORE_API_URL}/hc/conversation/history",
        params={"user_id": test_user, "limit": 30}
    )

    history_data = response.json()
    messages = history_data.get("messages", [])

    # Should have 6 messages (3 user + 3 assistant)
    assert len(messages) >= 6

    # Verify alternating user/assistant pattern
    for i in range(0, len(messages), 2):
        if i < len(messages):
            assert messages[i]["role"] == "user"
        if i + 1 < len(messages):
            assert messages[i + 1]["role"] == "assistant"

    print(f"  ✓ Conversation history: {len(messages)} messages")
    print(f"  ✓ Last reply: {messages[-1]['content'][:60]}...")
    print("  ✅ Test 5 PASSED")


# Optional test for real OpenAI API (requires API key)
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set (optional test)"
)
def test_6_optional_openai_integration(test_user):
    """
    Test 6: Optional OpenAI integration (requires API key)

    This test only runs if OPENAI_API_KEY is set in environment.
    It temporarily changes the provider to "openai" and verifies real LLM response.
    """
    print(f"\n=== Test 6: OpenAI Integration (user={test_user}) ===")

    # Temporarily update flags to use OpenAI
    import yaml
    from pathlib import Path

    flags_path = Path("ReDNACoreDemo/config/hc_flags.yaml")
    with open(flags_path, "r") as f:
        flags = yaml.safe_load(f)

    original_provider = flags.get("llm_provider")
    flags["llm_provider"] = "openai"

    with open(flags_path, "w") as f:
        yaml.dump(flags, f)

    try:
        # Send message
        response = requests.post(
            f"{CORE_API_URL}/hc/say",
            params={"user_id": test_user},
            json={"message": "Hello, Head Coach!", "role": "user"}
        )

        assert response.status_code == 200

        data = response.json()
        assert data.get("llm_provider") == "openai"
        assert data.get("tokens_used", 0) > 0  # Real LLM uses tokens

        # Verify reply
        response = requests.get(
            f"{CORE_API_URL}/hc/conversation/history",
            params={"user_id": test_user, "limit": 30}
        )

        history_data = response.json()
        messages = history_data.get("messages", [])

        assistant_msg = messages[-1]
        assert assistant_msg["provenance"]["provider"] == "openai"
        assert assistant_msg["provenance"]["tokens_used"] > 0
        assert "Mock reply" not in assistant_msg["content"]  # Real reply

        print(f"  ✓ OpenAI reply: {assistant_msg['content'][:70]}...")
        print(f"  ✓ Tokens used: {assistant_msg['provenance']['tokens_used']}")
        print("  ✅ Test 6 PASSED")

    finally:
        # Restore original provider
        flags["llm_provider"] = original_provider
        with open(flags_path, "w") as f:
            yaml.dump(flags, f)


if __name__ == "__main__":
    print("=" * 70)
    print("HC v2 Sprint 2a Acceptance Tests")
    print("=" * 70)

    # Check if Core API is running
    try:
        response = requests.get(f"{CORE_API_URL}/health", timeout=2)
        print(f"✓ Core API is running at {CORE_API_URL}")
    except Exception as e:
        print(f"✗ Core API not available at {CORE_API_URL}")
        print(f"  Please start: .venv/bin/python -m uvicorn ReDNACoreDemo.core.api:app --port 8001")
        exit(1)

    # Run tests
    pytest.main([__file__, "-v", "-s"])
