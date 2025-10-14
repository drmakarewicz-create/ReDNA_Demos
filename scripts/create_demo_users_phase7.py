#!/usr/bin/env python3
"""
Create demo preset users for Phase 7 Wow Factor Demo.

This script creates USER_DEMO1, USER_DEMO2, and USER_DEMO3 with
scripted behaviors and sample data to showcase visualization features.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path to import ReDNA modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ReDNACoreDemo.core.storage import (
    CORE_DATA_ROOT,
    save_json,
)


def create_demo_user_1():
    """
    USER_DEMO1: Active learner with high engagement.
    - Multiple coach switches
    - Varied tone adaptations
    - Growing trait knowledge
    """
    user_id = "USER_DEMO1"
    print(f"Creating {user_id}...")

    # Create user directory
    user_dir = CORE_DATA_ROOT / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # User metadata
    user_file = user_dir / "user.json"
    save_json(
        user_file,
        {
            "user_id": user_id,
            "display_name": "Demo User 1 (Active Learner)",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            "demo_persona": "active_learner",
            "description": "High engagement, frequent coach switching, varied tone",
        },
    )

    # Create conversation history with varied emotions
    user_dir = CORE_DATA_ROOT / "users" / user_id
    conv_dir = user_dir / "hc" / "conversation"
    conv_dir.mkdir(parents=True, exist_ok=True)

    history_file = conv_dir / "history.jsonl"
    conversations = [
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
            "turn_id": f"turn_{i}",
            "user": f"User message {i}",
            "assistant": (
                "Great question! Let me help you with that."
                if i % 3 == 0
                else "I understand your concern. Here's what I think..."
                if i % 3 == 1
                else "That's an interesting perspective. Let's explore it together."
            ),
        }
        for i in range(20, 0, -1)
    ]

    with open(history_file, "w") as f:
        for conv in conversations:
            f.write(json.dumps(conv) + "\n")

    # Create trait timeline data
    trait_file = user_dir / "trait_timeline.json"
    timeline = []
    base_rr = 50
    base_ucn = 30

    for i in range(15):
        timeline.append(
            {
                "ts": (datetime.now(timezone.utc) - timedelta(days=15 - i)).isoformat(),
                "trait_id": "Conscientiousness",
                "value": 0.6 + (i * 0.02),
                "rr": base_rr + (i * 3),
                "ucn": base_ucn - (i * 1.5),
            }
        )

    save_json(trait_file, {"timeline": timeline})

    print(f"✓ Created {user_id}")


def create_demo_user_2():
    """
    USER_DEMO2: Privacy-conscious with permission requests.
    - Multiple permission accesses
    - Consent timeline activity
    - Mixed tone patterns
    """
    user_id = "USER_DEMO2"
    print(f"Creating {user_id}...")

    user_dir = CORE_DATA_ROOT / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    user_file = user_dir / "user.json"
    save_json(
        user_file,
        {
            "user_id": user_id,
            "display_name": "Demo User 2 (Privacy-Conscious)",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "demo_persona": "privacy_conscious",
            "description": "High privacy awareness, permission gating, selective sharing",
        },
    )

    # Create consent timeline
    user_dir = CORE_DATA_ROOT / "users" / user_id
    consent_dir = user_dir / "consent"
    consent_dir.mkdir(parents=True, exist_ok=True)

    timeline_file = consent_dir / "timeline.jsonl"
    consent_events = [
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=24 - i)).isoformat(),
            "namespace": ns,
            "reason": reason,
            "status": status,
            "accessed_data": data,
        }
        for i, (ns, reason, status, data) in enumerate(
            [
                ("PaDNA", "Profile photo analysis requested", "granted", ["photo_metadata"]),
                ("SkillDNA", "Career assessment access", "granted", ["skills", "experience"]),
                ("Photo", "Image generation requested", "pending", []),
                ("BeliefDNA", "Value system exploration", "granted", ["core_beliefs"]),
                ("PaDNA", "Personality trait inference", "denied", []),
                ("ChatDNA", "Communication style analysis", "granted", ["message_history"]),
            ]
        )
    ]

    with open(timeline_file, "w") as f:
        for event in consent_events:
            f.write(json.dumps(event) + "\n")

    # Conversation history
    conv_dir = user_dir / "hc" / "conversation"
    conv_dir.mkdir(parents=True, exist_ok=True)

    history_file = conv_dir / "history.jsonl"
    conversations = [
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=12 - i)).isoformat(),
            "turn_id": f"turn_{i}",
            "user": f"Privacy-related question {i}",
            "assistant": "I respect your privacy. Let me explain how we handle your data..."
            if i % 2 == 0
            else "That's a valid concern. We only access data with your explicit consent.",
        }
        for i in range(10)
    ]

    with open(history_file, "w") as f:
        for conv in conversations:
            f.write(json.dumps(conv) + "\n")

    print(f"✓ Created {user_id}")


def create_demo_user_3():
    """
    USER_DEMO3: Varied emotions with rich timeline.
    - Diverse emotional responses
    - Rich tone adaptation history
    - Multiple trait evolutions
    """
    user_id = "USER_DEMO3"
    print(f"Creating {user_id}...")

    user_dir = CORE_DATA_ROOT / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    user_file = user_dir / "user.json"
    save_json(
        user_file,
        {
            "user_id": user_id,
            "display_name": "Demo User 3 (Emotional Journey)",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
            "demo_persona": "emotional_journey",
            "description": "Rich emotional patterns, adaptive tone responses, growth mindset",
        },
    )

    user_dir = CORE_DATA_ROOT / "users" / user_id

    # Rich conversation history with varied sentiments
    conv_dir = user_dir / "hc" / "conversation"
    conv_dir.mkdir(parents=True, exist_ok=True)

    history_file = conv_dir / "history.jsonl"
    sentiment_patterns = [
        "This is amazing! I'm so happy with the progress!",
        "I'm a bit worried about this challenge.",
        "Let's think through this calmly and rationally.",
        "I'm frustrated with this issue.",
        "Great idea! That really helped clarify things.",
        "I'm not sure I understand this concept yet.",
        "Wonderful! This is exactly what I needed.",
        "This is difficult, but I'll keep trying.",
        "Thank you for the clear explanation!",
        "I have concerns about this approach.",
    ]

    conversations = [
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=30 - i * 2)).isoformat(),
            "turn_id": f"turn_{i}",
            "user": "User inquiry",
            "assistant": sentiment_patterns[i % len(sentiment_patterns)],
        }
        for i in range(30)
    ]

    with open(history_file, "w") as f:
        for conv in conversations:
            f.write(json.dumps(conv) + "\n")

    # Tone history
    learning_dir = CORE_DATA_ROOT / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    tone_file = learning_dir / "tone_history.jsonl"
    tone_scores = [0.3, 0.5, 0.7, 0.6, 0.8, 0.4, 0.7, 0.5, 0.9, 0.6]

    # Only append to existing file
    with open(tone_file, "a") as f:
        for i, score in enumerate(tone_scores):
            entry = {
                "ts": (datetime.now(timezone.utc) - timedelta(hours=20 - i * 2)).isoformat(),
                "user_id": user_id,
                "tone_score": score,
                "formality_score": 0.5 + (score - 0.5) * 0.5,
                "empathy_cue": "high" if score > 0.7 else "low" if score < 0.4 else "neutral",
            }
            f.write(json.dumps(entry) + "\n")

    print(f"✓ Created {user_id}")


def main():
    """Create all demo users."""
    print("\n" + "=" * 60)
    print("  ReDNA Phase 7: Creating Demo Users")
    print("=" * 60 + "\n")

    try:
        create_demo_user_1()
        create_demo_user_2()
        create_demo_user_3()

        print("\n✓ All demo users created successfully!")
        print("\nDemo users:")
        print("  - USER_DEMO1: Active learner with high engagement")
        print("  - USER_DEMO2: Privacy-conscious with permission requests")
        print("  - USER_DEMO3: Emotional journey with rich timeline")
        print("\nVisit /wow-demo in the web UI to explore the visualizations!\n")

    except Exception as e:
        print(f"\n✗ Error creating demo users: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
