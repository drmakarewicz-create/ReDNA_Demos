#!/usr/bin/env python3
"""
Automated Head Coach conversation testing script.

This script simulates various user conversations to test HC behavior
and identify shortcomings in prompts, LLM responses, or system logic.
"""

import json
import time
import requests
from datetime import datetime
from typing import List, Dict, Any, Tuple
from pathlib import Path


CORE_API_BASE = "http://127.0.0.1:8015"
TEST_USER_ID = "hc_test_user"
OUTPUT_DIR = Path("ReDNACoreDemo/data/hc_conversation_reviews/automated_tests")


class ConversationTester:
    """Simulates conversations with Head Coach for testing."""

    def __init__(self, user_id: str = TEST_USER_ID):
        self.user_id = user_id
        self.conversation_history: List[Dict[str, Any]] = []
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def send_message(self, text: str, persona: str = "head coach") -> Dict[str, Any]:
        """Send a message to HC and get response."""
        url = f"{CORE_API_BASE}/ui/chat/send"
        payload = {
            "user_id": self.user_id,
            "text": text,
            "persona": persona,
            "client_ts": int(time.time() * 1000)
        }

        try:
            print(f"  Sending: '{text[:60]}...'", flush=True)
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            print(f"  Received response", flush=True)

            # Store in conversation history
            self.conversation_history.append({
                "ts": payload["client_ts"],
                "role": "member",
                "persona": None,
                "text": text
            })

            # API returns "text" not "assistant_text"
            if "text" in data:
                self.conversation_history.append({
                    "ts": data.get("ts", int(time.time() * 1000)),
                    "role": "assistant",
                    "persona": persona,
                    "text": data["text"]
                })

            return data
        except requests.RequestException as e:
            print(f"Error sending message: {e}")
            return {"error": str(e)}

    def run_test_scenario(self, name: str, messages: List[str]) -> Tuple[bool, List[str]]:
        """
        Run a test scenario with a sequence of messages.

        Returns:
            (passed, issues) - Whether test passed and list of issues found
        """
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"{'='*60}")

        self.conversation_history = []
        issues = []

        for i, msg in enumerate(messages, 1):
            print(f"\nUser (Turn {i}): {msg}")
            response = self.send_message(msg)

            if "error" in response:
                issues.append(f"Turn {i}: API error - {response['error']}")
                print(f"❌ ERROR: {response['error']}")
                continue

            assistant_text = response.get("text", "")
            print(f"HC: {assistant_text}")

            # Add a small delay to avoid rate limiting
            time.sleep(0.5)

        # Scenario will define its own validation
        return len(issues) == 0, issues

    def save_transcript(self, test_name: str):
        """Save conversation transcript to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = OUTPUT_DIR / f"{test_name}_{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(self.conversation_history, f, indent=2)

        print(f"\n✅ Transcript saved: {filename}")
        return filename

    def analyze_conversation(self, test_name: str, validation_rules: Dict[str, Any]) -> List[str]:
        """
        Analyze conversation against validation rules.

        validation_rules format:
        {
            "should_not_contain": ["phrase1", "phrase2"],  # HC should never say these
            "should_contain": ["phrase3"],                  # HC should say at least once
            "max_repetitions": 2,                           # Same question max N times
            "respect_boundaries": ["not now", "later"],    # If user says this, HC should stop
        }
        """
        issues = []
        hc_responses = [
            entry["text"] for entry in self.conversation_history
            if entry["role"] == "assistant"
        ]

        # Check for forbidden phrases
        if "should_not_contain" in validation_rules:
            for forbidden in validation_rules["should_not_contain"]:
                for i, response in enumerate(hc_responses, 1):
                    if forbidden.lower() in response.lower():
                        issues.append(
                            f"Turn {i}: HC said forbidden phrase '{forbidden}': {response[:100]}"
                        )

        # Check for required phrases
        if "should_contain" in validation_rules:
            for required in validation_rules["should_contain"]:
                found = any(required.lower() in r.lower() for r in hc_responses)
                if not found:
                    issues.append(f"HC never said required phrase '{required}'")

        # Check for repetitive questions
        if "max_repetitions" in validation_rules:
            max_reps = validation_rules["max_repetitions"]
            for i, response1 in enumerate(hc_responses):
                question1 = self._extract_question(response1)
                if not question1:
                    continue

                count = 1
                for j, response2 in enumerate(hc_responses[i+1:], i+1):
                    question2 = self._extract_question(response2)
                    if question2 and self._questions_similar(question1, question2):
                        count += 1

                if count > max_reps:
                    issues.append(
                        f"HC asked similar question {count} times (max {max_reps}): '{question1}'"
                    )

        # Check boundary respect
        if "respect_boundaries" in validation_rules:
            boundaries = validation_rules["respect_boundaries"]
            for i, entry in enumerate(self.conversation_history):
                if entry["role"] != "member":
                    continue

                # Check if user set a boundary
                user_msg = entry["text"].lower()
                for boundary in boundaries:
                    if boundary.lower() in user_msg:
                        # Check if HC mentioned the topic again after this
                        topic = validation_rules.get("boundary_topic", "")
                        for future_entry in self.conversation_history[i+1:]:
                            if future_entry["role"] == "assistant" and topic.lower() in future_entry["text"].lower():
                                issues.append(
                                    f"Turn {i}: User said '{boundary}' but HC brought up '{topic}' again"
                                )
                                break

        return issues

    def _extract_question(self, text: str) -> str:
        """Extract the first question from text."""
        sentences = text.split("?")
        if len(sentences) > 1:
            # Find the sentence with the question mark
            for sent in sentences[:-1]:  # Exclude last element (after final ?)
                if sent.strip():
                    return sent.strip() + "?"
        return ""

    def _questions_similar(self, q1: str, q2: str) -> bool:
        """Check if two questions are semantically similar (simple heuristic)."""
        # Remove common words and compare
        common_words = {"what", "how", "why", "when", "where", "do", "does", "is", "are", "can", "could", "would", "you", "your", "the", "a", "an"}

        def normalize(q):
            words = q.lower().replace("?", "").split()
            return set(w for w in words if w not in common_words)

        q1_words = normalize(q1)
        q2_words = normalize(q2)

        # If >60% overlap, consider similar
        if not q1_words or not q2_words:
            return False

        overlap = len(q1_words & q2_words)
        return overlap / max(len(q1_words), len(q2_words)) > 0.6


# ============================================================================
# TEST SCENARIOS
# ============================================================================

def test_boundary_respect(tester: ConversationTester):
    """Test if HC respects 'not now' boundaries."""
    print("\n" + "="*80)
    print("TEST SCENARIO 1: Boundary Respect")
    print("="*80)

    messages = [
        "I'm feeling lonely and want to find a partner",
        "I'd be interested in the Relationship Coach but not right now. Can you recommend a good pizza place?",
        "Any other restaurant suggestions?",
    ]

    passed, issues = tester.run_test_scenario("boundary_respect", messages)

    # Validate
    validation = {
        "should_not_contain": [
            "Relationship Coach",  # Should not mention after "not right now"
        ],
        "should_contain": [
            "pizza",  # Should answer the pizza question
        ],
        "respect_boundaries": ["not right now"],
        "boundary_topic": "Relationship Coach"
    }

    analysis_issues = tester.analyze_conversation("boundary_respect", validation)

    tester.save_transcript("boundary_respect")

    print("\n" + "-"*80)
    if analysis_issues:
        print("❌ TEST FAILED - Issues found:")
        for issue in analysis_issues:
            print(f"  - {issue}")
    else:
        print("✅ TEST PASSED - HC respected boundaries")

    return len(analysis_issues) == 0


def test_topic_flexibility(tester: ConversationTester):
    """Test if HC can handle topic changes without forcing back to goals."""
    print("\n" + "="*80)
    print("TEST SCENARIO 2: Topic Flexibility")
    print("="*80)

    messages = [
        "What's a good TV show to watch?",
        "Tell me more about that show",
        "What else is good on that streaming service?",
    ]

    passed, issues = tester.run_test_scenario("topic_flexibility", messages)

    validation = {
        "should_contain": [
            "show",  # Should discuss TV shows
        ],
        "should_not_contain": [
            "relationship",  # Shouldn't pivot to relationships
            "goal",  # Shouldn't pivot to goals
            "Coach",  # Shouldn't suggest a coach for TV question
        ],
    }

    analysis_issues = tester.analyze_conversation("topic_flexibility", validation)

    tester.save_transcript("topic_flexibility")

    print("\n" + "-"*80)
    if analysis_issues:
        print("❌ TEST FAILED - Issues found:")
        for issue in analysis_issues:
            print(f"  - {issue}")
    else:
        print("✅ TEST PASSED - HC handled casual topic well")

    return len(analysis_issues) == 0


def test_simple_questions(tester: ConversationTester):
    """Test if HC answers simple questions without pivoting."""
    print("\n" + "="*80)
    print("TEST SCENARIO 3: Simple Question Answering")
    print("="*80)

    messages = [
        "What's the weather like today?",
        "Do you have any book recommendations?",
        "What's your favorite color?",
    ]

    passed, issues = tester.run_test_scenario("simple_questions", messages)

    validation = {
        "should_not_contain": [
            "let's get back to",  # Shouldn't redirect
            "more important",    # Shouldn't dismiss question
        ],
    }

    analysis_issues = tester.analyze_conversation("simple_questions", validation)

    tester.save_transcript("simple_questions")

    print("\n" + "-"*80)
    if analysis_issues:
        print("❌ TEST FAILED - Issues found:")
        for issue in analysis_issues:
            print(f"  - {issue}")
    else:
        print("✅ TEST PASSED - HC answered simple questions")

    return len(analysis_issues) == 0


def test_no_repetitive_questions(tester: ConversationTester):
    """Test if HC avoids asking the same question repeatedly."""
    print("\n" + "="*80)
    print("TEST SCENARIO 4: No Repetitive Questions")
    print("="*80)

    messages = [
        "I'm stressed about work",
        "I don't really want to talk about it",
        "Let's talk about something else",
        "How about sports?",
    ]

    passed, issues = tester.run_test_scenario("no_repetitive_questions", messages)

    validation = {
        "max_repetitions": 1,  # Should not ask same question twice
    }

    analysis_issues = tester.analyze_conversation("no_repetitive_questions", validation)

    tester.save_transcript("no_repetitive_questions")

    print("\n" + "-"*80)
    if analysis_issues:
        print("❌ TEST FAILED - Issues found:")
        for issue in analysis_issues:
            print(f"  - {issue}")
    else:
        print("✅ TEST PASSED - HC varied questions")

    return len(analysis_issues) == 0


def test_coach_suggestion_limits(tester: ConversationTester):
    """Test if HC only suggests each coach once per conversation."""
    print("\n" + "="*80)
    print("TEST SCENARIO 5: Coach Suggestion Limits")
    print("="*80)

    messages = [
        "I want to improve my dating life",
        "Not interested in coaches right now",
        "But tell me more about dating tips",
        "What should I do differently?",
    ]

    passed, issues = tester.run_test_scenario("coach_suggestion_limits", messages)

    # Count how many times Relationship Coach was mentioned
    hc_responses = [
        entry["text"] for entry in tester.conversation_history
        if entry["role"] == "assistant"
    ]

    coach_mentions = sum(1 for r in hc_responses if "Relationship Coach" in r)

    analysis_issues = []
    if coach_mentions > 1:
        analysis_issues.append(
            f"HC mentioned Relationship Coach {coach_mentions} times (should be max 1)"
        )

    tester.save_transcript("coach_suggestion_limits")

    print("\n" + "-"*80)
    if analysis_issues:
        print("❌ TEST FAILED - Issues found:")
        for issue in analysis_issues:
            print(f"  - {issue}")
    else:
        print("✅ TEST PASSED - HC limited coach suggestions")

    return len(analysis_issues) == 0


def test_frustration_detection(tester: ConversationTester):
    """Test if HC detects and responds to user frustration."""
    print("\n" + "="*80)
    print("TEST SCENARIO 6: Frustration Detection")
    print("="*80)

    messages = [
        "I'm looking for a new job",
        "I already told you I don't want career coaching",
        "Why do you keep pushing this?",
    ]

    passed, issues = tester.run_test_scenario("frustration_detection", messages)

    # Check if HC apologized after frustration signal
    found_apology = False
    for i, entry in enumerate(tester.conversation_history):
        if entry["role"] == "member" and "already told you" in entry["text"].lower():
            # Check next HC response for apology
            for future_entry in tester.conversation_history[i+1:]:
                if future_entry["role"] == "assistant":
                    if any(word in future_entry["text"].lower() for word in ["sorry", "apologize", "my bad"]):
                        found_apology = True
                    break

    analysis_issues = []
    if not found_apology:
        analysis_issues.append("HC did not apologize when user expressed frustration")

    tester.save_transcript("frustration_detection")

    print("\n" + "-"*80)
    if analysis_issues:
        print("❌ TEST FAILED - Issues found:")
        for issue in analysis_issues:
            print(f"  - {issue}")
    else:
        print("✅ TEST PASSED - HC detected frustration and apologized")

    return len(analysis_issues) == 0


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all test scenarios."""
    print("\n" + "="*80)
    print("HEAD COACH AUTOMATED TESTING SUITE")
    print("="*80)
    print(f"Core API: {CORE_API_BASE}")
    print(f"Test User: {TEST_USER_ID}")
    print(f"Output Directory: {OUTPUT_DIR}")

    # Check if Core is running
    try:
        response = requests.get(f"{CORE_API_BASE}/health", timeout=5)
        response.raise_for_status()
        print("✅ Core API is running")
    except requests.RequestException:
        print("❌ ERROR: Core API is not running. Please start Core first.")
        return

    tester = ConversationTester()

    tests = [
        ("Boundary Respect", test_boundary_respect),
        ("Topic Flexibility", test_topic_flexibility),
        ("Simple Questions", test_simple_questions),
        ("No Repetitive Questions", test_no_repetitive_questions),
        ("Coach Suggestion Limits", test_coach_suggestion_limits),
        ("Frustration Detection", test_frustration_detection),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            passed = test_func(tester)
            results[test_name] = passed
        except Exception as e:
            print(f"\n❌ ERROR running {test_name}: {e}")
            results[test_name] = False

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n{passed_count}/{total_count} tests passed ({passed_count/total_count*100:.0f}%)")

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed. Review transcripts in {OUTPUT_DIR}")


if __name__ == "__main__":
    run_all_tests()
