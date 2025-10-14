# Head Coach Governance Overview

## Purpose

This document explains the governance framework for Head Coach autonomy, including safeguards, violation detection, and recovery procedures.

**Version:** 5.A.1
**Date:** 2025-10-11

---

## Governance Principles

1. **Safety First:** All autonomous actions must operate within explicit guardrails
2. **Transparency:** All actions are audited and visible to users
3. **Recoverability:** Violations trigger alerts but don't corrupt user data
4. **Progressive Trust:** Higher autonomy levels require proven compliance
5. **User Control:** Users can downgrade autonomy at any time

---

## Guardrail Categories

### 1. Daily Action Limits

**Purpose:** Prevent runaway task execution and quota exhaustion

**Implementation:**
```python
max_actions = policy.guardrails["max_self_actions_per_day"]
current_actions = state.actions_today

if current_actions >= max_actions:
    # Block further actions until midnight UTC reset
    return "Daily quota exceeded"
```

**Defaults by Level:**
- L0: 0 (no autonomy)
- L1: 0 (manual approval)
- L2: 5 actions/day
- L3: 10 actions/day
- L4: 20 actions/day

**Reset:** Automatic at midnight UTC

---

### 2. Learning Delta Bounds

**Purpose:** Prevent drastic personality/trait changes

**Implementation:**
```python
max_delta = policy.guardrails["max_learning_delta_per_week"]

for trait, delta in proposed_deltas.items():
    if abs(delta) > max_delta:
        violations.append(f"Delta for {trait} exceeds bounds")
```

**Defaults by Level:**
- L0-L1: N/A (no learning updates)
- L2: ±0.15 per week
- L3: ±0.20 per week
- L4: ±0.25 per week

**Rationale:** Gradual trait evolution maintains user recognition and trust

---

### 3. Tone & Creativity Shift Bounds

**Purpose:** Maintain consistent communication style

**Implementation:**
```python
tone_bounds = policy.guardrails["tone_shift_bounds"]
creativity_bounds = policy.guardrails["creativity_shift_bounds"]

if abs(tone_shift) > tone_bounds:
    violations.append("Tone shift exceeds bounds")

if abs(creativity_shift) > creativity_bounds:
    violations.append("Creativity shift exceeds bounds")
```

**Defaults by Level:**
- L0-L1: N/A
- L2: ±0.25
- L3: ±0.30
- L4: ±0.40

**Rationale:** Users expect consistent coaching tone, large shifts feel jarring

---

### 4. Consent Scope Enforcement

**Purpose:** Respect user privacy and control

**Implementation:**
```python
require_consent = policy.guardrails["require_consent_for"]

if action in require_consent:
    if action not in policy.consent_scope:
        return "Action requires explicit consent"
```

**Examples:**
- `rsc_invite`: Inviting other agents to collaborate
- `data_export`: Exporting user data outside system
- `cross_user_learning`: Learning from aggregate patterns

**Defaults:**
- L2: `["rsc_invite", "data_export"]`
- L3: `["rsc_invite", "data_export", "cross_user_learning"]`
- L4: `["data_export"]`

---

### 5. Prohibited Actions

**Purpose:** Hard block on dangerous operations

**Implementation:**
```python
prohibited = policy.guardrails["prohibited_actions"]

if action in prohibited:
    # Immediate rejection, emit alert
    emit_governance_review_required(user_id, f"Attempted prohibited action: {action}")
    return "Action prohibited by policy"
```

**Always Prohibited:**
- `policy_self_modify`: Agents cannot change their own autonomy level
- `user_data_delete`: Agents cannot delete user data (L0-L3)

**Rationale:** Critical operations require human oversight

---

## Violation Detection

### Automatic Checks

All autonomous actions pass through governance checks:

```python
compliance = check_governance_compliance(
    user_id=user_id,
    action=action,
    parameters=parameters
)

if not compliance["allowed"]:
    # Block action
    # Emit violation event
    # Log to audit trail
    return error_response(compliance["violations"])
```

### Violation Scoring

Each violation contributes to a compliance score:

```
compliance_score = (
    policy_readiness * 0.4 +
    (1 - violation_penalty) * 0.3 +
    quota_health * 0.15 +
    task_success_rate * 0.15
)
```

**Thresholds:**
- **< 0.50:** Critical, manual review required
- **0.50-0.70:** Warning, monitor closely
- **0.70-0.85:** Good standing
- **> 0.85:** Excellent compliance

---

## Violation Handling

### 1. Soft Violations (Warnings)

**Examples:**
- Approaching quota limit (80%+)
- Learning delta near bounds
- Task failure (non-critical)

**Action:**
- Log warning
- Display in DevX UI
- Continue operation
- Recommend policy adjustment

### 2. Hard Violations (Blocking)

**Examples:**
- Quota exceeded
- Learning delta exceeds bounds
- Consent not granted
- Prohibited action attempted

**Action:**
- Block action immediately
- Emit `autonomy_violation_detected` event
- Display error in UI
- Increment violation counter

### 3. Critical Violations (Alert)

**Examples:**
- Repeated violations (3+ in 24h)
- Attempted prohibited action
- Policy corruption detected

**Action:**
- Emit `governance_review_required` event
- Send alert to operators
- Consider autonomy downgrade
- Manual review before resuming

---

## Recovery Procedures

### Quota Exhaustion

**Symptom:** No tasks execute, quota shows 100%

**Recovery:**
1. Wait for midnight UTC reset (automatic)
2. Or manually reset quota:
   ```bash
   # Reset via policy update
   curl -X POST http://localhost:8015/ui/hc/autonomy/USER1/policy \
     -H "Content-Type: application/json" \
     -d '{"guardrails": {"max_self_actions_per_day": 10}}'
   ```

### Learning Delta Violation

**Symptom:** Learning updates blocked, violations logged

**Recovery:**
1. Review recent insights triggering large deltas
2. Adjust max_learning_delta_per_week if appropriate:
   ```python
   apply_autonomy_policy(user_id, {
       "guardrails": {"max_learning_delta_per_week": 0.20}
   })
   ```
3. Or wait for weekly reset
4. Consider upgrading to higher autonomy level if user trusts agent

### Task Failures

**Symptom:** Tasks show failure_count > 0

**Recovery:**
1. Check task error in `schedule_state.json`:
   ```json
   {
     "last_error": "Weekly review failed: No observations found"
   }
   ```
2. Address root cause (e.g., missing data)
3. Manually retry task:
   ```bash
   curl -X POST http://localhost:8015/ui/hc/autonomy/USER1/run/life_weekly_review
   ```

### Policy Corruption

**Symptom:** Policy validation errors

**Recovery:**
1. Check validation errors:
   ```bash
   curl http://localhost:8015/ui/hc/autonomy/USER1/policy | jq .evaluation.warnings
   ```
2. Reset to default for level:
   ```python
   from ReDNACoreDemo.core.hc_autonomy import get_default_policy_for_level, save_autonomy_policy

   default = get_default_policy_for_level(2)
   save_autonomy_policy("USER1", default)
   ```

---

## Compliance Monitoring

### Real-Time Monitoring

DevX UI displays:
- Current compliance score
- Active warnings
- Recent violations (last 7 days)
- Quota usage percentage
- Task success rate

### Periodic Review

Recommended: Weekly compliance review

```bash
# Get compliance report
curl http://localhost:8015/ui/hc/autonomy/USER1/compliance | jq .

# Sample output:
{
  "compliance_score": 0.87,
  "recent_violations": [],
  "quota_usage": {"today": 2, "max": 5, "percentage": 0.4},
  "task_health": {
    "success_rate": 1.0,
    "tasks_with_failures": 0
  }
}
```

### Audit Trail Analysis

Review all autonomy events:

```bash
# Last 24 hours of autonomy events
cat data/telemetry/agents/agent_activity.jsonl | \
  grep -E "autonomy|self_scheduled" | \
  tail -n 50 | \
  jq -s 'group_by(.event_type) | map({event: .[0].event_type, count: length})'
```

---

## Best Practices

### For Operators

1. **Start Conservative:** Begin users at L1 (semi) or L2 (supervised)
2. **Monitor First Week:** Watch compliance score and violation patterns
3. **Progressive Upgrade:** Move to L3+ only after proven compliance
4. **Review Alerts:** Respond to `governance_review_required` within 24h
5. **Document Changes:** Log reason for autonomy level changes

### For Users

1. **Understand Levels:** Read autonomy level descriptions before upgrading
2. **Review Guardrails:** Check guardrail table in DevX UI
3. **Monitor Tasks:** Review scheduled task success rates
4. **Trust Gradually:** Allow agents to prove reliability before full autonomy
5. **Downgrade If Needed:** Immediately reduce level if behavior seems erratic

---

## Emergency Procedures

### Immediate Downgrade

If agent behavior becomes problematic:

```bash
# Downgrade to L0 (disable autonomy)
curl -X POST http://localhost:8015/ui/hc/autonomy/USER1/policy \
  -H "Content-Type: application/json" \
  -d '{"level": 0, "self_schedule": false}'
```

This:
- Disables all autonomous actions
- Cancels pending tasks
- Revokes capability tokens
- Preserves audit trail

### Data Integrity Check

Verify no corruption after violations:

```bash
# Check user data integrity
python3 -c "
from ReDNACoreDemo.core.storage import load_user_info
info = load_user_info('USER1')
assert info, 'User data missing'
print('✓ User data intact')
"

# Check autonomy policy
curl -s http://localhost:8015/ui/hc/autonomy/USER1/policy | \
  jq '.evaluation.compliance'
# Should return: true
```

### Rollback to Defaults

Complete reset to safe defaults:

```python
from ReDNACoreDemo.core.hc_autonomy import get_default_policy_for_level, save_autonomy_policy
from ReDNACoreDemo.core.hc_scheduler import load_schedule_state, save_schedule_state

user_id = "USER1"

# Reset policy to L1
policy = get_default_policy_for_level(1)
save_autonomy_policy(user_id, policy)

# Reset schedule state
state = load_schedule_state(user_id)
state.actions_today = 0
state.total_actions = 0
for task in state.tasks.values():
    task.failure_count = 0
    task.last_error = None
save_schedule_state(state)

print("✓ Reset to safe defaults")
```

---

## FAQ

### Q: Can agents modify their own autonomy level?

**A:** No. `policy_self_modify` is always in the prohibited actions list. Only operators or users can change autonomy levels.

### Q: What happens if an agent exceeds quota?

**A:** The scheduler stops executing tasks until the next daily reset (midnight UTC). The agent continues to function normally for user-initiated actions.

### Q: Can users override guardrails?

**A:** Yes, but only through explicit policy updates via the API or DevX UI. Agents cannot override guardrails autonomously.

### Q: How often should compliance be reviewed?

**A:** Recommended: Weekly for new agents, monthly for established agents with good compliance history.

### Q: What if a task fails repeatedly?

**A:** After 3 consecutive failures, the task is automatically disabled and a `governance_review_required` event is emitted. Manual investigation and re-enablement required.

### Q: Are violations permanent?

**A:** No. Violations older than 30 days are archived and don't count toward compliance scoring. Recent compliance matters most.

---

## Summary

The governance framework provides:

✅ **Safety:** Multiple layers of guardrails prevent harmful actions
✅ **Transparency:** All actions audited and visible
✅ **Flexibility:** Policies adjust to user needs and trust levels
✅ **Recoverability:** Clear procedures for handling violations
✅ **Progressive Trust:** Autonomy increases with proven compliance

**Key Principle:** Autonomy is earned through compliance, not granted by default.

---

**Related Documentation:**
- [HC_AUTONOMY_PHASE5A_GRADUATION.md](./HC_AUTONOMY_PHASE5A_GRADUATION.md)
- [AGENT_PROTOCOL.md](./AGENT_PROTOCOL.md)
- [AGENTIC_HC_MVP_PHASE5A.md](./AGENTIC_HC_MVP_PHASE5A.md)
