"""
AI Decision Controller — Dual-Path Pattern Reference Implementation
Version: 1.0 | Date: 2025-10-06

This module implements the universal dual-path controller pattern for all AI-upgradable
decision points in ReDNA. It provides:
1. Deterministic rule execution (always runs)
2. AI shadow proposal (optional, controlled by feature flags)
3. Policy gate evaluation (decides if AI can override)
4. Audit logging (full transparency in Dev Mode)

Usage:
    from core.ai_decision_controller import decide_with_ai, DecisionInput

    result = decide_with_ai(
        rule_id="rsc/camo_select_v1",
        context={...},
        deterministic_out={...},
        metadata={...}
    )
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import yaml
import logging
from pathlib import Path

# ========================================
# DATA MODELS
# ========================================

@dataclass
class DecisionInput:
    """Input to decision controller"""
    rule_id: str  # references ai_decision_points.yaml
    context: Dict[str, Any]  # user, trait, relationship, recency, provenance summary
    deterministic_out: Dict[str, Any]  # result from deterministic rule
    metadata: Dict[str, Any] = field(default_factory=dict)  # version, timestamps, etc.

@dataclass
class AIProposal:
    """AI proposal structure"""
    enabled: bool  # was AI evaluation performed?
    proposal: Optional[Dict[str, Any]]  # same shape as deterministic_out
    confidence: float  # 0.0-1.0
    rationale: str  # <=300 chars, model's reasoning
    safety_flags: List[str] = field(default_factory=list)  # e.g., ["privacy_risk"]
    latency_ms: Optional[float] = None  # inference time

class DecisionMode(Enum):
    """Decision execution mode"""
    DETERMINISTIC = "deterministic"  # only deterministic rule
    AI_OVERRIDE = "ai_override"  # AI overrode deterministic
    AI_SHADOW = "ai_shadow"  # AI ran but didn't override (data collection)
    AI_FALLBACK = "ai_fallback"  # AI attempted but failed, fell back to deterministic

@dataclass
class DecisionOutput:
    """Output from decision controller"""
    result: Dict[str, Any]  # final decision (deterministic or AI)
    mode: DecisionMode  # how decision was made
    ai_proposal: Optional[AIProposal]  # AI's proposal (if enabled)
    policy_gate_passed: bool  # did AI proposal pass policy gate?
    audit_record: Dict[str, Any]  # full audit log entry

# ========================================
# POLICY GATE EVALUATOR
# ========================================

class PolicyGate:
    """Evaluates AI proposals against policy constraints"""

    def __init__(self, policy_config_path: str = "data/policy_gate.yaml"):
        self.config_path = Path(policy_config_path)
        self.config = self._load_config()
        self.logger = logging.getLogger(__name__)

    def _load_config(self) -> Dict[str, Any]:
        """Load policy gate configuration"""
        if not self.config_path.exists():
            self.logger.warning(f"Policy config not found: {self.config_path}, using defaults")
            return self._default_config()

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _default_config(self) -> Dict[str, Any]:
        """Default policy configuration (failsafe)"""
        return {
            "policies": {
                "default": {
                    "mode": "shadow_only",
                    "gates": {
                        "min_confidence": 0.75,
                        "max_safety_flags": 0,
                        "require_dev_mode_for": [],
                        "require_hc_approval_for": [],
                        "telemetry": True
                    },
                    "disallowed_safety_flags": [
                        "privacy_risk",
                        "manipulation_risk",
                        "consent_violation",
                        "cross_user_leak"
                    ]
                }
            },
            "global": {
                "feature_flags": {
                    "ai_override_enabled": False,
                    "shadow_mode_enabled": True,
                    "governed_override_enabled": False,
                    "ai_native_enabled": False
                },
                "safety": {
                    "confidence_floor": 0.50
                }
            }
        }

    def should_override(
        self,
        ai: AIProposal,
        inp: DecisionInput,
        policy_name: str = "default"
    ) -> tuple[bool, str]:
        """
        Evaluate if AI proposal should override deterministic rule.

        Returns:
            (should_override: bool, reason: str)
        """
        # Check if AI is enabled
        if not ai.enabled:
            return False, "ai_disabled"

        # Check global master switch
        if not self.config["global"]["feature_flags"]["ai_override_enabled"]:
            return False, "master_switch_off"

        # Check if policy allows overrides
        policy = self.config["policies"].get(policy_name, self.config["policies"]["default"])
        if policy["mode"] == "shadow_only":
            return False, "shadow_only_mode"

        # Check confidence threshold
        min_confidence = policy["gates"]["min_confidence"]
        if ai.confidence < min_confidence:
            return False, f"confidence_too_low ({ai.confidence:.2f} < {min_confidence})"

        # Check global confidence floor
        confidence_floor = self.config["global"]["safety"]["confidence_floor"]
        if ai.confidence < confidence_floor:
            return False, f"below_confidence_floor ({ai.confidence:.2f} < {confidence_floor})"

        # Check safety flags
        disallowed_flags = set(policy.get("disallowed_safety_flags", []))
        ai_flags = set(ai.safety_flags)
        violations = ai_flags.intersection(disallowed_flags)
        if violations:
            return False, f"safety_flag_violation ({', '.join(violations)})"

        max_flags = policy["gates"]["max_safety_flags"]
        if len(ai.safety_flags) > max_flags:
            return False, f"too_many_safety_flags ({len(ai.safety_flags)} > {max_flags})"

        # Check dev mode requirements
        # (In production, this would check actual dev mode state from context)
        require_dev_mode = policy["gates"].get("require_dev_mode_for", [])
        if require_dev_mode and not inp.context.get("dev_mode", False):
            return False, f"dev_mode_required_for {require_dev_mode}"

        # Check Head Coach approval requirements
        # (In production, this would check HC approval queue)
        require_hc = policy["gates"].get("require_hc_approval_for", [])
        if require_hc and not inp.context.get("hc_approved", False):
            return False, f"hc_approval_required_for {require_hc}"

        # All gates passed
        return True, "gates_passed"

# ========================================
# AUDIT LOGGER
# ========================================

class AuditLogger:
    """Logs all AI decision attempts for transparency and learning"""

    def __init__(self, log_path: str = "data/logs/ai_decisions.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def record(
        self,
        rule_id: str,
        decision_mode: DecisionMode,
        base_result: Dict[str, Any],
        ai_proposal: Optional[AIProposal],
        final_result: Dict[str, Any],
        context: Dict[str, Any],
        policy_gate_passed: bool,
        policy_gate_reason: str
    ) -> Dict[str, Any]:
        """
        Create audit record and append to log.

        Returns:
            audit_record: dict for inclusion in DecisionOutput
        """
        audit_record = {
            "rule_id": rule_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "decision_mode": decision_mode.value,
            "policy_gate_passed": policy_gate_passed,
            "policy_gate_reason": policy_gate_reason,
            "deterministic_result": base_result,
            "ai_proposal": asdict(ai_proposal) if ai_proposal else None,
            "final_result": final_result,
            "context": self._scrub_context(context),
        }

        # Write to JSONL log
        try:
            with open(self.log_path, 'a') as f:
                import json
                f.write(json.dumps(audit_record) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")

        return audit_record

    def _scrub_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from context for audit log"""
        scrubbed = context.copy()

        # Remove user IDs (hash them)
        if "user_id" in scrubbed:
            import hashlib
            scrubbed["user_id_hash"] = hashlib.sha256(
                str(scrubbed["user_id"]).encode()
            ).hexdigest()[:16]
            del scrubbed["user_id"]

        # Remove partner IDs
        if "partner_id" in scrubbed:
            import hashlib
            scrubbed["partner_id_hash"] = hashlib.sha256(
                str(scrubbed["partner_id"]).encode()
            ).hexdigest()[:16]
            del scrubbed["partner_id"]

        # Remove PII
        for field in ["email", "phone", "address", "name"]:
            if field in scrubbed:
                del scrubbed[field]

        return scrubbed

# ========================================
# AI AGENT INTERFACE (Stub)
# ========================================

class AIAgent:
    """
    Interface for AI model inference.

    In production, this would integrate with:
    - LLM API (OpenAI, Anthropic, etc.)
    - Local ML models (sklearn, pytorch, etc.)
    - RL agents (trained with gym/stable-baselines)

    For now, this is a stub that returns disabled proposals.
    """

    def __init__(self, registry_path: str = "data/ai_decision_points.yaml"):
        self.registry_path = Path(registry_path)
        self.registry = self._load_registry()
        self.logger = logging.getLogger(__name__)

    def _load_registry(self) -> Dict[str, Any]:
        """Load AI decision points registry"""
        if not self.registry_path.exists():
            self.logger.warning(f"Registry not found: {self.registry_path}")
            return {"decision_points": {}}

        with open(self.registry_path, 'r') as f:
            return yaml.safe_load(f)

    def propose_override(self, inp: DecisionInput) -> AIProposal:
        """
        Generate AI proposal for decision override.

        Args:
            inp: Decision input (context + deterministic result)

        Returns:
            AIProposal (enabled=False if AI not available)
        """
        # Check if this decision point is registered
        decision_point = self.registry["decision_points"].get(inp.rule_id)
        if not decision_point:
            self.logger.warning(f"Decision point not registered: {inp.rule_id}")
            return AIProposal(
                enabled=False,
                proposal=None,
                confidence=0.0,
                rationale="decision_point_not_registered"
            )

        # Check if AI is enabled for this decision point
        status = decision_point.get("status", "current")
        if status == "current":
            # Deterministic only, no AI yet
            return AIProposal(
                enabled=False,
                proposal=None,
                confidence=0.0,
                rationale="ai_not_enabled_for_decision_point"
            )

        # TODO: Integrate actual AI model here
        # For now, return stub proposal
        return self._stub_proposal(inp, decision_point)

    def _stub_proposal(
        self,
        inp: DecisionInput,
        decision_point: Dict[str, Any]
    ) -> AIProposal:
        """
        Stub AI proposal (placeholder for actual model inference).

        In production, this would:
        1. Load trained model for this decision point
        2. Prepare input features from inp.context
        3. Run inference
        4. Return proposal with confidence + rationale
        """
        self.logger.info(f"Stub AI proposal for {inp.rule_id} (no model loaded)")

        return AIProposal(
            enabled=True,
            proposal=inp.deterministic_out,  # stub: copy deterministic result
            confidence=0.65,  # stub: moderate confidence
            rationale="stub_proposal_from_ai_agent (no_model_loaded)",
            safety_flags=[],  # stub: no safety issues
            latency_ms=50.0  # stub: fake inference time
        )

# ========================================
# MAIN CONTROLLER FUNCTION
# ========================================

def decide_with_ai(
    rule_id: str,
    context: Dict[str, Any],
    deterministic_out: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    policy_name: str = "default"
) -> DecisionOutput:
    """
    Universal dual-path controller for AI-upgradable decisions.

    Args:
        rule_id: Decision point ID (references ai_decision_points.yaml)
        context: Input context (user, traits, relationship, etc.)
        deterministic_out: Result from deterministic rule
        metadata: Optional metadata (version, timestamps)
        policy_name: Policy gate to apply (default, autonomy_scaling, rsc_privacy, etc.)

    Returns:
        DecisionOutput with final result + audit record

    Example:
        result = decide_with_ai(
            rule_id="rsc/camo_select_v1",
            context={"user_id": "U123", "psydna_traits": {...}},
            deterministic_out={"template_id": "supportive_listening"},
            policy_name="rsc_privacy"
        )

        print(result.result)  # final decision
        print(result.mode)  # DETERMINISTIC or AI_OVERRIDE
        print(result.audit_record)  # full transparency log
    """
    # Initialize components
    inp = DecisionInput(
        rule_id=rule_id,
        context=context,
        deterministic_out=deterministic_out,
        metadata=metadata or {}
    )

    ai_agent = AIAgent()
    policy_gate = PolicyGate()
    audit_logger = AuditLogger()

    # Step 1: Always run deterministic rule (already provided in deterministic_out)
    base_result = deterministic_out

    # Step 2: Attempt AI proposal (shadow mode)
    ai_proposal = None
    try:
        ai_proposal = ai_agent.propose_override(inp)
    except Exception as e:
        logging.error(f"AI proposal failed for {rule_id}: {e}")
        ai_proposal = AIProposal(
            enabled=False,
            proposal=None,
            confidence=0.0,
            rationale=f"ai_inference_error: {str(e)}"
        )

    # Step 3: Evaluate policy gate
    policy_gate_passed = False
    policy_gate_reason = "ai_disabled"

    if ai_proposal and ai_proposal.enabled:
        policy_gate_passed, policy_gate_reason = policy_gate.should_override(
            ai_proposal, inp, policy_name
        )

    # Step 4: Decide final result
    if policy_gate_passed:
        final_result = ai_proposal.proposal
        decision_mode = DecisionMode.AI_OVERRIDE
    elif ai_proposal and ai_proposal.enabled:
        final_result = base_result
        decision_mode = DecisionMode.AI_SHADOW  # AI ran but didn't override
    else:
        final_result = base_result
        decision_mode = DecisionMode.DETERMINISTIC

    # Step 5: Audit logging
    audit_record = audit_logger.record(
        rule_id=rule_id,
        decision_mode=decision_mode,
        base_result=base_result,
        ai_proposal=ai_proposal,
        final_result=final_result,
        context=context,
        policy_gate_passed=policy_gate_passed,
        policy_gate_reason=policy_gate_reason
    )

    # Return decision output
    return DecisionOutput(
        result=final_result,
        mode=decision_mode,
        ai_proposal=ai_proposal,
        policy_gate_passed=policy_gate_passed,
        audit_record=audit_record
    )

# ========================================
# EXAMPLE USAGE
# ========================================

if __name__ == "__main__":
    # Example: Camouflage template selection with AI override path

    logging.basicConfig(level=logging.INFO)

    # Deterministic result (YAML template selection)
    deterministic_result = {
        "template_id": "supportive_listening",
        "tone": "supportive",
        "delay_seconds": 120,
        "variant_index": 2
    }

    # Context (User B's profile)
    context = {
        "user_id": "UserB_123",
        "partner_id": "UserA_456",
        "psydna_traits": {
            "Openness": 0.72,
            "Agreeableness": 0.85,
            "Neuroticism": 0.45
        },
        "recent_sentiment": 0.3,  # mildly positive
        "dev_mode": False,
        "hc_approved": False
    }

    # Call dual-path controller
    output = decide_with_ai(
        rule_id="rsc_protocol.camouflage_template_selection",
        context=context,
        deterministic_out=deterministic_result,
        metadata={"version": "v1.0", "timestamp": "2025-10-06T12:00:00Z"},
        policy_name="rsc_privacy"
    )

    # Print results
    print("\n=== Decision Output ===")
    print(f"Mode: {output.mode.value}")
    print(f"Policy Gate Passed: {output.policy_gate_passed}")
    print(f"Final Result: {output.result}")

    if output.ai_proposal:
        print(f"\nAI Proposal:")
        print(f"  Confidence: {output.ai_proposal.confidence:.2f}")
        print(f"  Rationale: {output.ai_proposal.rationale}")
        print(f"  Safety Flags: {output.ai_proposal.safety_flags}")

    print(f"\nAudit Record:")
    import json
    print(json.dumps(output.audit_record, indent=2))
