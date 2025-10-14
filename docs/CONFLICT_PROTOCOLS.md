# Conflict Protocols

Conflicts progress through four stages:

1. **Auto** – low-severity trait disagreements merge automatically using weighted evidence.
2. **Hierarchical** – medium+ severity or cross-module disputes are delegated to the Head Coach via `conflict_bridge.adjudicate`.
3. **Policy Gate** – policy and permission requests fail closed unless a capability is presented by PermCoach.
4. **Escalation** – sensitive traits lacking corroboration, or high/ethical conflicts, are escalated for human review.

Escalated cases append a ledger entry with `resolver="escalation"` and pause further automation until a manual `POST /conflicts/resolve` arrives.

Permutation of policies and capabilities are enforced by the resolver using `policy/conflict_rules.yaml`.  DevX exposes the status via the **Conflicts** dashboard and `/conflicts/learning-stats`.

