from datetime import datetime, timezone

from ReDNACoreDemo.core.conflict.evidence_weighting import compute_effective_weight
from ReDNACoreDemo.core.conflict.models import UserAssertion


def make_assertion(value: str, **provenance):
    return UserAssertion(
        evidence_id="ua-1",
        source_type="user_assertion",
        module="chat",
        timestamp=datetime.now(timezone.utc),
        value=value,
        assertion_text=value,
        provenance=provenance,
    )


def test_self_report_weight_respects_calibrated_bounds():
    assertion = make_assertion("I feel confident", consistency=1.1)
    breakdown = compute_effective_weight(assertion, user_base=0.65)
    assert 0.2 <= breakdown.base <= 0.7
    assert breakdown.total <= 0.7 * 1.2 * 1.3  # upper bound with modifiers


def test_anonymity_reduces_weight():
    public = make_assertion("public", anonymity=False)
    anon = make_assertion("anon", anonymity=True)
    public_weight = compute_effective_weight(public, user_base=0.4).total
    anon_weight = compute_effective_weight(anon, user_base=0.4).total
    assert anon_weight < public_weight

