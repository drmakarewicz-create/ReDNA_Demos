from datetime import datetime, timezone
from uuid import uuid4

from ReDNACoreDemo.core.conflict.models import Evidence
from ReDNACoreDemo.core.conflict.detectors import make_conflict
from ReDNACoreDemo.core.conflict.resolver import ConflictResolver


def build_evidence(source: str, value: str) -> Evidence:
    return Evidence(
        evidence_id=str(uuid4()),
        source_type=source,
        module=source,
        timestamp=datetime.now(timezone.utc),
        value=value,
        provenance={},
    )


def test_sensitive_conflicts_require_corroboration():
    resolver = ConflictResolver()
    evidence = [build_evidence("user_assertion", "flip")]  # single source
    conflict = make_conflict(
        conflict_id=str(uuid4()),
        user_id="TEST",
        kind="trait",
        severity="low",
        path="BeliefValueDNA.trust",
        evidence=evidence,
        signals={"ucn_gap": 80},
    )
    result = resolver.resolve(conflict)
    assert result.conflict.status == "escalated"
    assert "corroboration" in result.outcome.reason.lower()

