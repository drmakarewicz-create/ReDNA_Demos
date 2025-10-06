from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from ReDNACoreDemo.core.policy import evaluate_nudge_policy


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat()


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_allows_when_ttl_expired(self) -> None:
        payload = {
            "now": _iso(self.now),
            "last_sent": _iso(self.now - timedelta(minutes=2000)),
            "ttl": 1440,
            "snooze": 120,
            "rate_cap_per_day": 3,
            "sent_count_today": 0,
        }
        result = evaluate_nudge_policy(payload)
        self.assertEqual(result, {"allow": True, "reason": "ok"})

    def test_blocks_when_ttl_active(self) -> None:
        payload = {
            "now": _iso(self.now),
            "last_sent": _iso(self.now - timedelta(minutes=30)),
            "ttl": 60,
        }
        result = evaluate_nudge_policy(payload)
        self.assertEqual(result["allow"], False)
        self.assertEqual(result["reason"], "ttl_active")

    def test_blocks_when_snoozed(self) -> None:
        payload = {
            "now": _iso(self.now),
            "last_snoozed_at": _iso(self.now - timedelta(minutes=30)),
            "snooze": 90,
        }
        result = evaluate_nudge_policy(payload)
        self.assertFalse(result["allow"])
        self.assertEqual(result["reason"], "snoozed")

    def test_blocks_rate_cap(self) -> None:
        payload = {
            "now": _iso(self.now),
            "rate_cap_per_day": 3,
            "sent_count_today": 3,
        }
        result = evaluate_nudge_policy(payload)
        self.assertFalse(result["allow"])
        self.assertEqual(result["reason"], "rate_cap")

    def test_blocks_wrong_cohort(self) -> None:
        payload = {
            "now": _iso(self.now),
            "ab_cohort": "B",
            "allowed_cohort": "A",
        }
        result = evaluate_nudge_policy(payload)
        self.assertFalse(result["allow"])
        self.assertEqual(result["reason"], "cohort_block")


if __name__ == "__main__":  # pragma: no cover - defensive fallback
    unittest.main()
