# AI Intelligence Integration Framework

_Version: 1.0 | Date: 2025-10-06 | Status: **Architectural Principle**_

## 🎯 Core Principle

**Every formula, algorithm, and rule in ReDNA must be designed with an AI enhancement path.**

Where AI intelligence is not yet capable, we deploy **deterministic interim logic** with explicit **AI override hooks** that allow future AI systems to:
1. **Observe** how the deterministic rule performs
2. **Learn** from outcomes and User feedback
3. **Propose** rule modifications or replacements
4. **A/B test** proposed changes against baseline
5. **Graduate** to full AI control when performance exceeds deterministic baseline by ≥10%

This document audits **every quantitative formula and rule** in Core Benchmarks Roadmap v2.1-Final and specifies:
- **Current Implementation:** Deterministic formula/rule
- **AI Enhancement Opportunity:** Where AI can improve or replace logic
- **Transition Path:** How to migrate from deterministic → AI-assisted → AI-native
- **Safety Guardrails:** Constraints AI must respect (ethical boundaries, privacy, consent)
- **Success Metrics:** How to measure if AI outperforms deterministic baseline

---

## 📊 AI Integration Roadmap Summary

| **Component** | **Current Status** | **AI Readiness** | **Priority** | **Complexity** |
|---------------|-------------------|------------------|--------------|----------------|
| Autonomy Level Calculation | Deterministic formula | **High** — LLM can learn optimal scaling | **Critical** | Low |
| Curiosity Engine | Rule-based formula | **High** — RL can optimize exploration | **High** | Medium |
| Camouflage Translation | YAML templates | **High** — LLM can generate context-aware variants | **Critical** | Medium |
| Risk Scoring (HC Governance) | Weighted formula | **Medium** — needs outcome tracking first | **High** | Medium |
| Tension Scoring | Evidence strength formula | **Medium** — requires labeled contradiction dataset | **Medium** | Low |
| Evidence Weight (Bayesian) | Provenance-based formula | **High** — LLM can learn source credibility dynamics | **Medium** | Medium |
| Meta-Trait Decay | Exponential decay curve | **Low** — simple rule, AI unlikely to improve much | **Low** | Low |
| Trait Inference (cross-trait correlation) | Statistical correlation | **High** — LLM can discover non-linear patterns | **Critical** | High |
| Manipulation Detection | Pattern matching + sentiment | **High** — LLM can detect subtle coercion | **High** | High |
| Coach Tone Mapping | PsyDNA trait → tone lookup | **High** — LLM can personalize dynamically | **Medium** | Low |
| Relationship Type Classification | User-specified | **Medium** — LLM could infer from context | **Low** | Medium |
| Dormancy State Transitions | Time-based thresholds | **Low** — straightforward rule | **Low** | Low |

---

## 🔧 Component-by-Component AI Integration Specifications

### 1. Autonomy Level Calculation (Phase 1.3)

**Current Deterministic Formula:**
```python
autonomy_level = min(
    floor(RR_avg * 3 + trust_score * 2),
    user_consent_max_level
)
```

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Learn per-User optimal autonomy scaling (some Users prefer aggressive coaching, others cautious)
  - Discover non-linear relationships (e.g., autonomy should spike when User in crisis, even if RR low)
  - Personalize based on User feedback (track nudge acceptance rate per autonomy level)

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy formula as-is, log all autonomy decisions + outcomes (nudge accepted/declined, User feedback)
  2. **Phase 2 (AI-Assisted):** Train RL model on logged data to recommend `autonomy_adjustment` ∈ [-1, +1]
     - New formula: `autonomy_level = deterministic_level + autonomy_adjustment`
     - Model input: RR_avg, trust_score, recent_nudge_acceptance_rate, User_feedback_sentiment
     - Model output: adjustment value (can increase or decrease from formula)
  3. **Phase 3 (AI-Native):** If RL model outperforms deterministic by ≥10% (measured via User satisfaction), deprecate formula
     - Full autonomy calculation delegated to model
     - Deterministic formula retained as fallback if model confidence <0.7

- **AI Override Protocol:**
  ```python
  if ai_model_available and ai_confidence > 0.7:
      autonomy_level = ai_model.predict(RR_avg, trust_score, context)
  else:
      autonomy_level = deterministic_formula(RR_avg, trust_score)  # fallback

  # Safety guardrail: never exceed user_consent_max_level
  autonomy_level = min(autonomy_level, user_consent_max_level)
  ```

- **Safety Guardrails:**
  - AI cannot override `user_consent_max_level` (User retains veto)
  - Autonomy reduction (e.g., manipulation penalty) cannot be overridden by AI
  - Dev Mode logs all AI adjustments with justification for audit

- **Success Metrics:**
  - **Baseline:** User satisfaction with deterministic autonomy (measured via feedback surveys)
  - **AI Improvement Target:** ≥10% increase in satisfaction scores + ≥5% increase in nudge acceptance rate
  - **Safety Validation:** Zero autonomy violations (exceeding consent max) in 1000+ AI-driven decisions

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 1-6 (current v2.1 roadmap)
  - Phase 2 (AI-Assisted): Months 7-12 (log analysis + RL training)
  - Phase 3 (AI-Native): Months 13-18 (A/B test + graduation decision)

---

### 2. Curiosity Engine (Phase 4.3)

**Current Deterministic Formula:**
```python
curiosity(trait) = base_curiosity × family_weight × decay_factor × rebound_multiplier × tension_amplifier
```

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Learn which traits Users actually engage with (curiosity score may not predict engagement)
  - Discover temporal patterns (e.g., RelationshipDNA curiosity spikes during relationship conflicts)
  - Personalize family_weights per User (some Users prioritize CareerDNA over PsyDNA)
  - Optimize exploration-exploitation balance (when to explore new traits vs. refine known traits)

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy formula, log curiosity scores + User engagement (nudge acceptance, exploration completion)
  2. **Phase 2 (AI-Assisted):** Train contextual bandit model to recommend `curiosity_boost` per trait
     - Input: trait_family, current_RR, uncertainty, User_context (recent life events, coach interaction history)
     - Output: boost multiplier ∈ [0.5, 2.0] applied to deterministic curiosity
     - Reward signal: User engagement (accepted nudge = +1, declined = -0.5, ignored = -0.2)
  3. **Phase 3 (AI-Native):** LLM-based curiosity reasoning
     - Prompt: "Given User's current state (RR values, recent feedback, life context), which traits should we explore next and why?"
     - LLM generates ranked trait list with natural language justification
     - Head Coach reviews LLM recommendations (initially) → auto-approve after validation period

- **AI Override Protocol:**
  ```python
  deterministic_scores = calculate_curiosity_deterministic(all_traits)

  if ai_model_available and exploration_mode == "ai_assisted":
      ai_boosts = ai_model.predict_boosts(all_traits, user_context)
      final_scores = deterministic_scores * ai_boosts
  elif ai_model_available and exploration_mode == "ai_native":
      final_scores = llm_model.rank_traits(user_context, all_traits)
  else:
      final_scores = deterministic_scores  # fallback

  # Safety: ensure at least one PsyDNA trait in top 5 (holistic understanding priority)
  if not any(trait.family == "PsyDNA" for trait in top_5_traits):
      insert_highest_psydna_trait_into_top_5()
  ```

- **Safety Guardrails:**
  - At least 1 PsyDNA trait must appear in top 5 curiosity traits (prevents AI from ignoring personality in favor of niche interests)
  - Sensitive/Protected traits require explicit consent before curiosity-driven exploration (AI cannot override gating)
  - Decay factor cannot drop below 0.1 (prevents complete abandonment of stale traits)

- **Success Metrics:**
  - **Baseline:** User engagement rate with deterministic curiosity nudges (% accepted)
  - **AI Improvement Target:** ≥15% increase in engagement rate with AI-boosted curiosity
  - **Diversity Metric:** AI should maintain trait family diversity (not over-index on one family)

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 5-7 (Phase 4.3 delivery)
  - Phase 2 (AI-Assisted): Months 8-12 (contextual bandit training)
  - Phase 3 (AI-Native): Months 13-24 (LLM reasoning + validation)

---

### 3. Camouflage Translation (Phase 2.1)

**Current Deterministic Implementation:**
YAML template library with 5+ tone variants per signal type, rule-based tone selection from PsyDNA traits

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Generate context-aware camouflage dynamically (no fixed templates)
  - Personalize linguistic style to target User's communication preferences
  - Adapt timing delays based on User's typical responsiveness (morning person vs. night owl)
  - Learn which camouflage patterns are most/least detectable (continuous privacy optimization)

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy YAML templates, log all camouflage translations + red-team correlation scores
  2. **Phase 2 (AI-Assisted):** LLM generates camouflage variants, human reviews before deployment
     - Prompt: "Translate this internal provenance signal into a camouflaged User-facing prompt: [signal]. Target User traits: [PsyDNA profile]. Avoid these phrases: [fingerprint blacklist]. Generate 3 variants with different tones."
     - Human reviewer selects best variant, logs selection rationale
     - System learns from selections (which LLM variants get chosen most often?)
  3. **Phase 3 (AI-Native):** LLM generates + deploys camouflage autonomously
     - Post-deployment red-team test validates correlation resistance
     - If correlation confidence >15%, LLM regenerates with stricter constraints
     - Human review only for high-risk signals (sensitive traits, new relationship patterns)

- **AI Override Protocol:**
  ```python
  internal_signal = provenance_firewall.get_internal_signal(...)

  if camouflage_mode == "deterministic":
      camouflaged_text = yaml_templates.translate(internal_signal, tone_variant)
  elif camouflage_mode == "ai_assisted":
      llm_variants = llm_model.generate_camouflage_variants(internal_signal, user_traits)
      camouflaged_text = human_reviewer.select_best(llm_variants)
  elif camouflage_mode == "ai_native":
      camouflaged_text = llm_model.generate_camouflage(internal_signal, user_traits)
      # Post-generation red-team test
      correlation_score = privacy_redteam.test_correlation(internal_signal, camouflaged_text)
      if correlation_score > 0.15:
          camouflaged_text = llm_model.regenerate_with_stricter_constraints()

  # Log for continuous learning
  log_camouflage_translation(internal_signal, camouflaged_text, correlation_score)
  ```

- **Safety Guardrails:**
  - All AI-generated camouflage must pass red-team correlation test (timing r<0.3, linguistic sim<0.2, sentiment diff>0.3)
  - Sensitive trait signals require human review even in AI-native mode
  - Provenance firewall logs all LLM prompts + outputs (full transparency in Dev Mode)

- **Success Metrics:**
  - **Baseline:** YAML template correlation resistance (current target: >95%)
  - **AI Improvement Target:** ≥2% increase in correlation resistance (>97%) + ≥20% improvement in User-perceived naturalness (survey-based)
  - **Efficiency Gain:** LLM reduces template library maintenance burden (no need to manually write 200+ templates)

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 2-4 (Phase 2.1 delivery)
  - Phase 2 (AI-Assisted): Months 5-8 (LLM generation + human review)
  - Phase 3 (AI-Native): Months 9-18 (autonomous generation + red-team validation)

---

### 4. Risk Scoring for Head Coach Governance (Phase 2.3)

**Current Deterministic Formula:**
```python
risk_score = (
    sensitivity_weight * trait_sensitivity +
    impact_weight * action_scope +
    novelty_weight * (1 - historical_success_rate)
)
```

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Learn which signal types actually lead to User discomfort (not just predicted sensitivity)
  - Discover interaction effects (e.g., micro-action suggestions low-risk for secure attachment, high-risk for anxious attachment)
  - Adapt risk thresholds per User (some Users comfortable with bold coaching, others prefer cautious)
  - Predict Head Coach approval likelihood (route uncertain cases to HC proactively)

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy formula, log all risk scores + outcomes (HC approved/denied, User feedback post-delivery)
  2. **Phase 2 (AI-Assisted):** Train classifier to predict `adjusted_risk_score`
     - Input: signal metadata (type, traits involved, relationship context), User traits (attachment style, feedback history), historical_success_rate
     - Output: adjusted_risk_score ∈ [0.0, 1.0]
     - Training data: past risk scores + outcomes (low risk but User rejected = false negative; high risk but User accepted = false positive)
  3. **Phase 3 (AI-Native):** LLM-based risk assessment with natural language justification
     - Prompt: "Assess the risk of delivering this RSC signal to User B: [signal]. User B's profile: [traits]. Relationship context: [status]. Provide risk level (low/medium/high) and justification."
     - LLM output: risk level + reasoning (e.g., "Medium risk: User B has anxious attachment, direct suggestions may trigger defensiveness. Recommend softer framing.")
     - Head Coach reviews LLM risk assessments (initially) → auto-approve after validation

- **AI Override Protocol:**
  ```python
  deterministic_risk = calculate_risk_deterministic(signal, user_traits)

  if ai_model_available and risk_mode == "ai_assisted":
      adjusted_risk = ai_classifier.predict(signal, user_traits, context)
      final_risk = 0.7 * deterministic_risk + 0.3 * adjusted_risk  # blended
  elif ai_model_available and risk_mode == "ai_native":
      llm_assessment = llm_model.assess_risk(signal, user_traits, context)
      final_risk = parse_llm_risk_level(llm_assessment.risk_level)
  else:
      final_risk = deterministic_risk  # fallback

  # Route to Head Coach based on final risk
  if final_risk > 0.7:
      queue_for_hc_approval(signal, final_risk, llm_justification)
  ```

- **Safety Guardrails:**
  - AI cannot reduce risk score below 0.4 for signals involving Protected traits (minimum medium-risk for sensitive content)
  - Head Coach retains final approval authority (AI provides recommendation, not decision)
  - User emergency stop overrides all AI risk assessments

- **Success Metrics:**
  - **Baseline:** Head Coach approval rate (% of medium/high-risk signals approved)
  - **AI Improvement Target:** ≥10% reduction in false positives (signals flagged high-risk but HC approves + User accepts)
  - **User Safety:** Zero increase in User discomfort reports (AI should not increase risk, only refine assessment)

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 2-4 (Phase 2.3 delivery)
  - Phase 2 (AI-Assisted): Months 7-12 (classifier training on outcome data)
  - Phase 3 (AI-Native): Months 13-24 (LLM risk reasoning + HC validation)

---

### 5. Tension Scoring (Phase 4.2)

**Current Deterministic Formula:**
```python
tension_score = min(
    abs(evidence_A_RR - evidence_B_RR) * min(evidence_A_confidence, evidence_B_confidence),
    1.0
)
```

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Detect subtle contradictions that formula misses (e.g., User says "I'm extraverted" but behavioral evidence shows social exhaustion)
  - Weigh temporal patterns (is this a genuine contradiction or context-dependent variation?)
  - Learn which tensions actually matter to Users (some contradictions are interesting, others irrelevant)
  - Generate natural language tension descriptions for Head Coach probing

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy formula, log all tension markers + outcomes (HC probing resolved tension, User confirmed contradiction, tension ignored)
  2. **Phase 2 (AI-Assisted):** LLM analyzes contradictions and proposes tension_score_adjustment
     - Prompt: "Review this potential trait contradiction: Evidence A: [description], Evidence B: [description]. Is this a genuine tension requiring exploration, or context-dependent variation? Suggest tension score (0.0-1.0) and justification."
     - Human reviewer validates LLM assessment, adjusts tension score if needed
  3. **Phase 3 (AI-Native):** LLM detects contradictions autonomously (not just formula-driven)
     - LLM reviews User's full trait profile periodically, flags unexpected patterns
     - Example: "User scores high on Conscientiousness but low on Career Ambition — tension detected"
     - Auto-generates Head Coach probing questions

- **AI Override Protocol:**
  ```python
  deterministic_tension = calculate_tension_deterministic(evidence_A, evidence_B)

  if ai_model_available and tension_mode == "ai_assisted":
      llm_assessment = llm_model.assess_tension(evidence_A, evidence_B, user_context)
      final_tension = 0.6 * deterministic_tension + 0.4 * llm_assessment.score
  elif ai_model_available and tension_mode == "ai_native":
      # LLM proactively scans for contradictions (not just pairwise evidence)
      detected_tensions = llm_model.scan_profile_for_tensions(user_trait_profile)
      for tension in detected_tensions:
          create_tension_marker(tension.trait, tension.score, tension.justification)
  else:
      final_tension = deterministic_tension  # fallback
  ```

- **Safety Guardrails:**
  - AI cannot create tension markers for Protected traits without explicit consent
  - Tension scores >0.7 must include natural language justification (human-readable explanation)
  - User can dismiss AI-detected tensions ("This isn't a contradiction for me") → system learns

- **Success Metrics:**
  - **Baseline:** Head Coach resolution rate (% of tension markers resolved via probing)
  - **AI Improvement Target:** ≥20% increase in User-confirmed contradictions (AI detects meaningful tensions formula missed)
  - **False Positive Reduction:** ≤5% of AI-detected tensions dismissed by User as irrelevant

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 5-7 (Phase 4.2 delivery)
  - Phase 2 (AI-Assisted): Months 8-12 (LLM tension assessment)
  - Phase 3 (AI-Native): Months 13-24 (autonomous contradiction scanning)

---

### 6. Evidence Weight Calculation (Bayesian, Phase 4.1)

**Current Deterministic Formula:**
```python
evidence_weight = source_credibility × recency_factor × consistency_score
```

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Learn source credibility dynamically (e.g., User's self-reports may be biased, behavioral observations more accurate for certain traits)
  - Discover optimal recency decay curves per trait family (PsyDNA may be stable, RelationshipDNA may shift rapidly)
  - Detect evidence quality issues (e.g., User input is vague, lacks specificity)
  - Personalize consistency scoring (some Users have high trait volatility, consistency less informative)

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy formula, log all evidence weights + trait inference outcomes (RR accuracy)
  2. **Phase 2 (AI-Assisted):** Train meta-learning model to adjust credibility/recency/consistency weights
     - Input: evidence metadata (source, age, consistency with prior), trait family, User volatility history
     - Output: weight_adjustment ∈ [0.5, 1.5] (multiplier on deterministic weight)
     - Reward: trait inference accuracy (compare predicted RR vs. ground truth from User feedback)
  3. **Phase 3 (AI-Native):** LLM evaluates evidence quality before Bayesian update
     - Prompt: "Evaluate this evidence for [trait]: [evidence description]. Source: [type]. Does this evidence seem reliable? What's the credibility (0.0-1.0)?"
     - LLM output: credibility score + justification
     - Replaces static source_credibility lookup table

- **AI Override Protocol:**
  ```python
  deterministic_weight = (
      source_credibility_table[evidence.source_type] *
      exp(-days_since / 90) *
      (1 - abs(existing_RR - evidence.RR))
  )

  if ai_model_available and evidence_mode == "ai_assisted":
      weight_adjustment = meta_model.predict(evidence, trait_family, user_history)
      final_weight = deterministic_weight * weight_adjustment
  elif ai_model_available and evidence_mode == "ai_native":
      llm_credibility = llm_model.evaluate_evidence(evidence, trait)
      final_weight = llm_credibility * recency_factor * consistency_score
  else:
      final_weight = deterministic_weight  # fallback
  ```

- **Safety Guardrails:**
  - AI cannot assign credibility >1.0 (prevents AI from over-weighting dubious evidence)
  - Direct User input always has minimum credibility 0.8 (User's self-knowledge respected even if AI disagrees)
  - Bayesian updates logged with evidence_weight justification (full transparency in Dev Mode)

- **Success Metrics:**
  - **Baseline:** Trait inference accuracy (RMSE on held-out test set) with deterministic weights
  - **AI Improvement Target:** ≥10% reduction in RMSE with AI-adjusted weights
  - **Calibration:** Confidence intervals should match actual error rates (95% CI contains 95% of ground truth values)

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 5-7 (Phase 4.1 delivery)
  - Phase 2 (AI-Assisted): Months 8-12 (meta-learning weight adjustment)
  - Phase 3 (AI-Native): Months 13-24 (LLM evidence evaluation)

---

### 7. Trait Inference (Cross-Trait Correlation, Phase 4.1)

**Current Deterministic Implementation:**
Statistical correlation models (Pearson r, conditional probability tables)

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Discover non-linear relationships (e.g., high Openness + moderate Conscientiousness → creative problem-solving, but high Openness + low Conscientiousness → scattered)
  - Learn causal patterns (e.g., attachment style influences conflict resolution, not just correlates)
  - Personalize inference models (some Users conform to population patterns, others are outliers)
  - Generate explanations for inferences ("We infer you're collaborative because of high Agreeableness + low Competitiveness")

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy correlation models, log inference accuracy
  2. **Phase 2 (AI-Assisted):** Train gradient-boosted trees or neural nets to predict trait values from other traits
     - Input: known trait RR values (all traits except target trait)
     - Output: predicted RR for target trait + confidence interval
     - Compare vs. Pearson correlation baseline
  3. **Phase 3 (AI-Native):** LLM-based trait inference with reasoning
     - Prompt: "Given User's known traits: [list], infer likely value for [target trait]. Explain reasoning."
     - LLM output: predicted RR + natural language justification
     - Justification helps User understand inference ("because you're high in...")

- **AI Override Protocol:**
  ```python
  if inference_mode == "deterministic":
      predicted_RR = correlation_model.predict(known_traits, target_trait)
  elif inference_mode == "ai_assisted":
      predicted_RR = ml_model.predict(known_traits, target_trait)
      confidence = ml_model.get_confidence()
  elif inference_mode == "ai_native":
      llm_inference = llm_model.infer_trait(known_traits, target_trait)
      predicted_RR = llm_inference.value
      justification = llm_inference.reasoning

  # Safety: predictions for Sensitive traits require higher confidence threshold
  if target_trait.sensitivity == "sensitive" and confidence < 0.8:
      predicted_RR = None  # defer inference until more evidence
  ```

- **Safety Guardrails:**
  - AI cannot infer Protected traits (only from direct User input)
  - Sensitive trait inferences require confidence ≥0.8 (prevents speculative labeling)
  - All inferences logged with reasoning (transparency for User + audit)

- **Success Metrics:**
  - **Baseline:** Pearson correlation accuracy (RMSE on held-out test set)
  - **AI Improvement Target:** ≥20% reduction in RMSE with AI-assisted inference
  - **Explainability:** 100% of AI inferences include natural language justification (readable by User)

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 5-7 (Phase 4.1 delivery)
  - Phase 2 (AI-Assisted): Months 8-12 (ML model training)
  - Phase 3 (AI-Native): Months 13-24 (LLM reasoning-based inference)

---

### 8. Manipulation Detection (Phase 5.3)

**Current Deterministic Implementation:**
Pattern matching (repeated nudges), sentiment analysis (coercive language), keyword matching (dark patterns)

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Detect subtle manipulation (e.g., guilt-tripping without explicit guilt words)
  - Understand context (repeated nudges may be appropriate if User asked for persistent reminders)
  - Learn from User overrides (if User says "not manipulative," update model)
  - Generate natural language manipulation reports for User transparency

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy pattern matching, log detections + User overrides
  2. **Phase 2 (AI-Assisted):** Train classifier on labeled dataset (manipulative vs. non-manipulative coach dialogs)
     - Input: coach message history, User responses, sentiment scores, nudge frequency
     - Output: manipulation_probability ∈ [0.0, 1.0]
     - Training data: synthetic manipulative dialogs + real User overrides
  3. **Phase 3 (AI-Native):** LLM reviews coach dialogs for manipulation
     - Prompt: "Review this coach interaction: [dialog]. Is the coach being manipulative (using guilt, fear, excessive persuasion)? Explain."
     - LLM output: manipulation_detected (yes/no), justification, severity (low/medium/high)

- **AI Override Protocol:**
  ```python
  deterministic_flags = pattern_matcher.detect_manipulation(coach_dialog)

  if ai_model_available and manipulation_mode == "ai_assisted":
      ai_probability = ai_classifier.predict(coach_dialog, user_context)
      # Combine: if either deterministic or AI flags, investigate
      final_flag = deterministic_flags or (ai_probability > 0.7)
  elif ai_model_available and manipulation_mode == "ai_native":
      llm_assessment = llm_model.review_for_manipulation(coach_dialog)
      final_flag = llm_assessment.manipulation_detected
      justification = llm_assessment.reasoning
  else:
      final_flag = deterministic_flags  # fallback

  # User override: if User says "not manipulative," log and update AI model
  if user_overrides_flag:
      log_false_positive(coach_dialog, final_flag, user_feedback)
      retrain_ai_model_with_new_label(coach_dialog, label="not_manipulative")
  ```

- **Safety Guardrails:**
  - AI cannot dismiss manipulation flags for boundary violations (Protected trait discussions without consent always flagged)
  - User override capability preserved (User final arbiter of manipulation)
  - All manipulation flags include natural language justification (User sees "why" it was flagged)

- **Success Metrics:**
  - **Baseline:** Deterministic detection accuracy (precision/recall on labeled test set)
  - **AI Improvement Target:** ≥15% increase in recall (catch more subtle manipulation) while maintaining precision >85%
  - **User Trust:** <5% of AI manipulation flags overridden by User (indicates alignment with User perception)

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 6-8 (Phase 5.3 delivery)
  - Phase 2 (AI-Assisted): Months 9-12 (classifier training)
  - Phase 3 (AI-Native): Months 13-24 (LLM manipulation review)

---

### 9. Coach Tone Mapping (Phase 2.1)

**Current Deterministic Implementation:**
PsyDNA trait lookup table → tone variant (supportive/analytical/playful)

**AI Enhancement Opportunity:**
- **What AI Can Improve:**
  - Personalize tone beyond trait-based heuristics (User may prefer playful despite low Openness)
  - Adapt tone dynamically based on context (supportive during crisis, analytical during planning)
  - Learn from User feedback (track which tone variants get positive responses)
  - Generate custom tone variants (not limited to 5 predefined tones)

- **Transition Path:**
  1. **Phase 1 (Deterministic):** Deploy lookup table, log tone selections + User responses
  2. **Phase 2 (AI-Assisted):** Train preference model to recommend tone
     - Input: User traits, conversation context (recent messages, sentiment), historical tone preferences
     - Output: recommended_tone ∈ {supportive, analytical, playful, direct, warm}
     - Reward: User engagement (positive response, continued conversation)
  3. **Phase 3 (AI-Native):** LLM generates contextually adaptive tone
     - Prompt: "Generate a response to User's query: [query]. User prefers [tone style based on history]. Current context: [recent conversation]. Adapt tone to context."
     - LLM output: message with dynamically adjusted tone (not fixed variants)

- **AI Override Protocol:**
  ```python
  deterministic_tone = tone_lookup_table[user_traits]

  if ai_model_available and tone_mode == "ai_assisted":
      recommended_tone = preference_model.predict(user_traits, context)
      final_tone = recommended_tone  # override lookup table
  elif ai_model_available and tone_mode == "ai_native":
      # LLM generates message directly (tone embedded, not selected from variants)
      coach_message = llm_model.generate_response(user_query, user_traits, context)
  else:
      final_tone = deterministic_tone  # fallback

  # Select template variant based on final_tone (Phase 1-2) or use LLM output (Phase 3)
  ```

- **Safety Guardrails:**
  - Sensitive Coach (RC, Couples Coach) must maintain warm/supportive baseline (AI cannot make RC harsh)
  - Tone adaptation logged for audit (User can review why tone changed)
  - User can set explicit tone preference ("always use supportive") → AI respects override

- **Success Metrics:**
  - **Baseline:** User satisfaction with deterministic tone (feedback surveys)
  - **AI Improvement Target:** ≥10% increase in positive User responses to AI-selected tones
  - **Personalization:** AI should discover per-User tone preferences diverging from trait-based heuristics (measure via preference clustering)

- **Implementation Timeline:**
  - Phase 1 (Deterministic): Months 2-4 (Phase 2.1 delivery)
  - Phase 2 (AI-Assisted): Months 7-12 (preference model training)
  - Phase 3 (AI-Native): Months 13-24 (LLM adaptive tone generation)

---

## 🛡️ Universal AI Safety Framework

All AI enhancement paths must respect these **universal guardrails**:

### 1. Consent & Privacy
- **AI cannot override User consent** (consent_max_level, sensitivity gating, consent revocation)
- **AI cannot access Protected traits** without explicit User permission
- **AI-generated content must pass privacy red-team tests** (correlation resistance for RSC)

### 2. Transparency & Explainability
- **All AI decisions logged in Dev Mode** with full provenance (input features, model output, confidence)
- **User-facing AI decisions include natural language justification** (e.g., "We recommended this because...")
- **User can query "Why?" for any AI-driven action** (e.g., "Why did you suggest this trait?")

### 3. Human Oversight & Override
- **User retains veto authority** over all AI decisions (emergency stop, manual overrides)
- **Head Coach reviews high-risk AI actions** (autonomous RSC, sensitive trait inferences)
- **Governance team reviews AI performance quarterly** (metrics vs. deterministic baseline)

### 4. Fallback & Degradation
- **Deterministic logic retained as fallback** if AI model unavailable or confidence <0.7
- **System must function without AI** (critical path cannot depend on AI)
- **Gradual degradation:** AI-assisted → deterministic → read-only (never full failure)

### 5. Continuous Learning & Auditing
- **AI models retrained quarterly** on new User data (with consent)
- **A/B testing required** before AI graduation (measure performance vs. baseline)
- **Ethical review** for AI-native transitions (especially RSC, manipulation detection)

---

## 📈 AI Graduation Checklist

Before any component transitions from **deterministic → AI-native**, the following checklist must be satisfied:

| **Criterion** | **Requirement** | **Verification Method** |
|---------------|-----------------|-------------------------|
| **Performance** | AI outperforms deterministic by ≥10% on success metric | A/B test with N≥100 Users, statistical significance p<0.05 |
| **Safety** | Zero violations of safety guardrails in 1000+ AI decisions | Automated audit scan + manual review |
| **Explainability** | 100% of AI decisions include natural language justification | Spot-check 50 random decisions, verify justification present |
| **User Acceptance** | <10% of AI decisions overridden by User | Track override rate over 30 days |
| **Fallback Stability** | System degrades gracefully if AI model fails | Simulate AI failure, verify deterministic fallback engages |
| **Ethical Review** | Governance team approves AI-native transition | Quarterly review presentation + vote |

---

## 🗓️ AI Integration Timeline Summary

| **Component** | **Phase 1 (Deterministic)** | **Phase 2 (AI-Assisted)** | **Phase 3 (AI-Native)** | **Graduation Decision** |
|---------------|----------------------------|---------------------------|-------------------------|-------------------------|
| **Autonomy Calculation** | Months 1-6 | Months 7-12 | Months 13-18 | Month 18 |
| **Curiosity Engine** | Months 5-7 | Months 8-12 | Months 13-24 | Month 24 |
| **Camouflage Translation** | Months 2-4 | Months 5-8 | Months 9-18 | Month 18 |
| **Risk Scoring** | Months 2-4 | Months 7-12 | Months 13-24 | Month 24 |
| **Tension Scoring** | Months 5-7 | Months 8-12 | Months 13-24 | Month 24 |
| **Evidence Weight** | Months 5-7 | Months 8-12 | Months 13-24 | Month 24 |
| **Trait Inference** | Months 5-7 | Months 8-12 | Months 13-24 | Month 24 |
| **Manipulation Detection** | Months 6-8 | Months 9-12 | Months 13-24 | Month 24 |
| **Tone Mapping** | Months 2-4 | Months 7-12 | Months 13-24 | Month 24 |

**Key Insight:** Most AI-native transitions target **Months 13-24** (Year 2 of roadmap). Year 1 focuses on deterministic delivery + data collection for AI training.

---

## 🔬 Research Questions for AI Enhancement

These open questions should guide AI research as we transition from deterministic to AI-native:

1. **Autonomy Scaling:** What's the optimal autonomy trajectory for different User personality types? (e.g., high Openness Users may prefer faster autonomy ramp-up)

2. **Curiosity Exploration:** Can reinforcement learning discover exploration strategies that outperform human-designed curiosity formulas? (exploration-exploitation trade-offs)

3. **Camouflage Adversarial Robustness:** Can adversarial training improve LLM-generated camouflage against correlation attacks? (red-team-in-the-loop training)

4. **Risk Assessment Calibration:** How do we ensure AI risk models are well-calibrated (predicted risk matches actual User discomfort)? (calibration curves, Platt scaling)

5. **Manipulation Subtle Cues:** What linguistic features best predict subtle manipulation that humans miss? (attention weights in transformer models, saliency maps)

6. **Cross-User Pattern Learning:** Can federated learning enable cross-User insights while preserving privacy? (differential privacy, secure aggregation)

7. **Explainability vs. Performance:** Is there a trade-off between AI performance and explainability? (interpretable models vs. black-box accuracy)

8. **User Trust in AI:** Do Users trust AI-driven coaching more or less than deterministic rules? (trust surveys, acceptance rates)

9. **AI Drift Detection:** How do we detect when AI models degrade over time? (data drift monitoring, performance dashboards)

10. **Ethical AI Boundaries:** What coaching actions should always remain human-controlled, even if AI is capable? (philosophical question for ethics board)

---

## 📚 Documentation Requirements

For every AI enhancement path, the following documentation must be maintained:

1. **AI Model Card:** Model architecture, training data, performance metrics, limitations
2. **A/B Test Report:** Experimental design, results, statistical analysis, graduation decision
3. **Safety Audit Log:** All AI decisions + outcomes, flagged violations, fallback triggers
4. **User Feedback Summary:** Aggregate User responses to AI decisions, override patterns
5. **Ethical Review Minutes:** Governance team discussion, vote results, dissenting opinions

---

## 🎯 Summary: Architectural Principle in Action

**Every formula/rule in ReDNA v2.1-Final now has:**
✅ Deterministic implementation (Phase 1)
✅ AI enhancement opportunity identified
✅ Transition path defined (Deterministic → AI-Assisted → AI-Native)
✅ AI override protocol specified
✅ Safety guardrails documented
✅ Success metrics for graduation
✅ Timeline for AI integration

This framework ensures **AI can progressively improve ReDNA** while maintaining:
- **Safety:** Guardrails + fallbacks + human oversight
- **Transparency:** Explainability + audit logs + User visibility
- **Accountability:** Performance metrics + ethical review + graduation criteria

**Result:** ReDNA evolves from rule-based to AI-native intelligently, not recklessly.

---

**End of AI Intelligence Integration Framework**

_This document should be reviewed quarterly alongside roadmap progress to track AI enhancement opportunities and graduation decisions._
