"""
RSC (Remote Sentient Collaboration) v1 Tests
=============================================

Tests for agent-to-agent messaging, policy enforcement, and workflow.
"""

import pytest
from ReDNACoreDemo.agents.messages import RSCMessage, RSCMessageStore, send_message
from ReDNACoreDemo.agents.policy import get_agent_policy, update_policy, can_send_rsc_message, can_receive_rsc_message
from ReDNACoreDemo import agents


@pytest.fixture
def rsc_users(tmp_path, monkeypatch):
    """Setup two users with RSC-enabled policies."""
    from ReDNACoreDemo.core import storage
    from ReDNACoreDemo.agents import registry

    # Use unique temp directory for each test
    test_dir = tmp_path / "test_rsc"
    test_dir.mkdir()

    monkeypatch.setattr(storage, "CORE_DATA_ROOT", test_dir)
    monkeypatch.setattr(registry, "AGENTS_ROOT", test_dir / "agents")

    # Ensure clean registry
    registry.AGENTS_ROOT.mkdir(parents=True, exist_ok=True)

    # Create users
    agents.ensure_agent_record("USER1")
    agents.ensure_agent_record("USER2")

    # Enable RSC on both
    update_policy("USER1", {"rsc_enabled": True})
    update_policy("USER2", {"rsc_enabled": True})

    yield {"user1": "USER1", "user2": "USER2", "tmp": test_dir}


def test_send_invite_happy_path(rsc_users):
    """Test sending an RSC invite between two enabled agents."""
    message = send_message(
        from_user_id=rsc_users["user1"],
        to_user_id=rsc_users["user2"],
        message_type="rsc_invite",
        topic="career_brief",
        constraints={"namespaces": ["SkillDNA"], "max_tokens": 3000},
        policy={"allow_reply": True},
    )

    assert message.type == "rsc_invite"
    assert message.topic == "career_brief"
    assert message.thread_id is not None

    # Check recipient inbox
    store = RSCMessageStore(rsc_users["user2"])
    inbox = store.read_inbox(limit=10)
    assert len(inbox) == 1
    assert inbox[0].id == message.id

    # Check sender sent box
    sender_store = RSCMessageStore(rsc_users["user1"])
    sent = sender_store.read_sent(limit=10)
    assert len(sent) == 1
    assert sent[0].id == message.id


def test_policy_deny_rsc_disabled(rsc_users):
    """Test that messages fail when RSC is disabled."""
    # Disable RSC on sender
    update_policy(rsc_users["user1"], {"rsc_enabled": False})

    policy = get_agent_policy(rsc_users["user1"])
    can_send, reason = can_send_rsc_message(policy, f"hc_{rsc_users['user2']}")

    assert not can_send
    assert reason == "rsc_disabled"


def test_policy_partner_allowlist(rsc_users):
    """Test partner allowlist enforcement."""
    # Set USER1 to only allow USER2
    update_policy(rsc_users["user1"], {
        "rsc_enabled": True,
        "rsc_partners_allow": [f"hc_{rsc_users['user2']}"]
    })

    policy = get_agent_policy(rsc_users["user1"])

    # USER2 should be allowed
    can_send, reason = can_send_rsc_message(policy, f"hc_{rsc_users['user2']}")
    assert can_send

    # USER3 should not be allowed
    can_send, reason = can_send_rsc_message(policy, "hc_USER3")
    assert not can_send
    assert reason == "partner_not_allowed"


def test_policy_partner_denylist(rsc_users):
    """Test partner denylist enforcement."""
    # Block USER2
    update_policy(rsc_users["user1"], {
        "rsc_enabled": True,
        "rsc_partners_deny": [f"hc_{rsc_users['user2']}"]
    })

    policy = get_agent_policy(rsc_users["user1"])
    can_send, reason = can_send_rsc_message(policy, f"hc_{rsc_users['user2']}")

    assert not can_send
    assert reason == "partner_denied"


def test_message_expiry(rsc_users):
    """Test that expired messages are filtered."""
    # Send message with 1-second TTL
    message = send_message(
        from_user_id=rsc_users["user1"],
        to_user_id=rsc_users["user2"],
        message_type="rsc_invite",
        topic="test",
        ttl_seconds=1,
    )

    import time
    time.sleep(2)

    # Should not appear in non-expired inbox
    store = RSCMessageStore(rsc_users["user2"])
    inbox = store.read_inbox(include_expired=False)
    assert len(inbox) == 0

    # Should appear when including expired
    inbox_with_expired = store.read_inbox(include_expired=True)
    assert len(inbox_with_expired) == 1


def test_accept_decline_workflow(rsc_users):
    """Test accept/decline response flow."""
    # Send invite
    invite = send_message(
        from_user_id=rsc_users["user1"],
        to_user_id=rsc_users["user2"],
        message_type="rsc_invite",
        topic="career_brief",
    )

    # USER2 accepts
    accept_msg = send_message(
        from_user_id=rsc_users["user2"],
        to_user_id=rsc_users["user1"],
        message_type="rsc_accept",
        thread_id=invite.thread_id,
        in_reply_to=invite.id,
    )

    assert accept_msg.type == "rsc_accept"
    assert accept_msg.thread_id == invite.thread_id
    assert accept_msg.in_reply_to == invite.id

    # USER1 should see accept in inbox
    sender_store = RSCMessageStore(rsc_users["user1"])
    inbox = sender_store.read_inbox(thread_id=invite.thread_id)
    assert len(inbox) == 1
    assert inbox[0].type == "rsc_accept"


def test_thread_filtering(rsc_users):
    """Test filtering messages by thread_id."""
    # Send two invites with different threads
    msg1 = send_message(
        from_user_id=rsc_users["user1"],
        to_user_id=rsc_users["user2"],
        message_type="rsc_invite",
        topic="topic_a",
    )

    msg2 = send_message(
        from_user_id=rsc_users["user1"],
        to_user_id=rsc_users["user2"],
        message_type="rsc_invite",
        topic="topic_b",
    )

    assert msg1.thread_id != msg2.thread_id

    # Filter by thread
    store = RSCMessageStore(rsc_users["user2"])
    thread1_msgs = store.read_inbox(thread_id=msg1.thread_id)
    assert len(thread1_msgs) == 1
    assert thread1_msgs[0].id == msg1.id

    thread2_msgs = store.read_inbox(thread_id=msg2.thread_id)
    assert len(thread2_msgs) == 1
    assert thread2_msgs[0].id == msg2.id


def test_message_type_filtering(rsc_users):
    """Test filtering by message type."""
    # Send invite and accept
    invite = send_message(
        from_user_id=rsc_users["user1"],
        to_user_id=rsc_users["user2"],
        message_type="rsc_invite",
        topic="test",
    )

    send_message(
        from_user_id=rsc_users["user2"],
        to_user_id=rsc_users["user1"],
        message_type="rsc_accept",
        thread_id=invite.thread_id,
    )

    # USER1 inbox should have only accept
    store = RSCMessageStore(rsc_users["user1"])
    accepts = store.read_inbox(message_type="rsc_accept")
    assert len(accepts) == 1

    invites = store.read_inbox(message_type="rsc_invite")
    assert len(invites) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
