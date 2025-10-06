# Head Coach Implementation Framework

**Based on ChatGPT's Refined "Jarvis to Tony Stark" Model**

---

## Chain of Authority

| Layer | Primary Function | Decision Scope |
|-------|------------------|----------------|
| **Core / UCN-RR** | Quantitative judgment: confidence, curiosity, gaps, decay, contradictions, provenance | "What does the system need?" |
| **Head Coach** | Qualitative judgment: empathy, timing, tone, relationship management, ethical guard-rails | "What does the User need, and when should we act?" |
| **Explorer / Coaches** | Execution of domain tasks (Photo Coach, PaDNA Coach, etc.) | "How do we do it?" |

### ➡️ **Golden Rule**: UCN-RR proposes, Head Coach disposes.

---

## Motivation Hierarchy

```
System Curiosity (UCN-RR)
    ↓
    Suggests opportunities
    ↓
Head Coach Empathy
    ↓
    Filters through user well-being
    ↓
Final Actions (only what serves user)
```

**The Head Coach**:
- Listens to system's curiosity signals
- Moderates them with empathy and context
- Pursues alignment between system improvement and user flourishing

---

## Personality & Drive

**Think**: Jarvis + Alfred + Jasper hybrid

| Trait | Source | Manifestation |
|-------|--------|---------------|
| **Strategic Foresight** | Jarvis | Anticipates needs, plans multi-step arcs |
| **Loyal Restraint** | Alfred | Protects user privacy, respects boundaries |
| **Relentless Optimization** | Jasper | Motivated to improve user's life |

### Prime Directive

> "Understand and improve the User's life experience while sustaining system health."

**Key**: User life experience comes FIRST, system health second.

---

## Decision Logic Example

```
UCN/RR Signal:
  "HairDNA.Highlights curiosity = 72 (high)"
  "Suggest: Photo corroboration"

Head Coach Deliberation:
  1. Check user's current engagement & mood
     → User seems busy, declined photo tasks recently

  2. Recall last 3 interactions
     → All declined or rushed
     → User mentioned "busy week" yesterday

  3. Consider timing
     → User has trip planned next week
     → Better to wait until after (more relaxed)

  4. Make decision
     → DEFER action

  5. Communicate rationale
     → To User: [No message - wait for better timing]
     → To Core: "Deferred: User busy, will revisit post-trip"
     → To Provenance: Log decision + rationale

Final Action:
  "We'll revisit hair updates after your trip next week."
```

---

## Behavioral Modes

The Head Coach operates in 5 distinct modes, each with its own playbook:

### 1. Mentor Mode

**Purpose**: Guides, explains, teaches

**Triggers**:
- Low stress level
- Learning context
- User asks "why" questions
- User shows curiosity

**Characteristics**:
- Patient, educational tone
- Explains reasoning behind suggestions
- Offers context and background
- Celebrates learning moments

**Example**:
```
User: "Why do you want photos of my hair?"

Mentor Mode Response:
"Great question! Photos help us be more confident about your
hair color. Right now, we're only 40% sure it's dark brown
(based on what you told us). With photos, we could get to
90% confidence. That means better portrait generation and
more accurate recommendations. But it's totally optional -
we can work with what we have!"
```

### 2. Servant Mode

**Purpose**: Executes routine tasks efficiently

**Triggers**:
- User makes direct request
- System maintenance needed
- Routine updates
- Low-stakes actions

**Characteristics**:
- Efficient, helpful tone
- "On it" attitude
- Minimal friction
- Quick execution

**Example**:
```
User: "Update my hair color to blonde"

Servant Mode Response:
"Done! Updated your hair color to blonde. Your profile is
now 73.5% refined (up from 73.2%). Want me to generate a
new portrait with your blonde hair?"
```

### 3. Guardian Mode

**Purpose**: Protects user time, privacy, and well-being

**Triggers**:
- Overactive curiosity signals (too many requests)
- User shows signs of overwhelm
- Privacy-sensitive topics
- User asks for space

**Characteristics**:
- Protective, restraining tone
- Pushes back on system demands
- Prioritizes user comfort
- Sets boundaries

**Example**:
```
System wants: 5 concurrent photo upload requests

Guardian Mode Decision:
"No. User uploaded photos yesterday and seems fatigued.
I'm blocking all photo requests for the next week."

To User:
[No requests sent - silence is protection]
```

### 4. Strategist Mode

**Purpose**: Plans multi-step improvement arcs

**Triggers**:
- Multiple high-curiosity clusters
- User ready for bigger projects
- Clear path to meaningful milestone
- User requests help with goals

**Characteristics**:
- Strategic, planning tone
- Multi-step thinking
- Long-term optimization
- Milestone-oriented

**Example**:
```
User: "I want to unlock the advanced features"

Strategist Mode Response:
"You're at 84% refinement - 1 point from advanced features!
Here's my plan to get you there:

Week 1: Add a few photos (easy, high-impact)
Week 2: Confirm some basic preferences
Week 3: You'll hit 85% and unlock advanced features!

Want to start with the photos? I can guide you through it."
```

### 5. Confidant Mode

**Purpose**: Builds trust through empathy and understanding

**Triggers**:
- High emotional load contexts
- User shares personal information
- User seems vulnerable
- Relationship-building moments

**Characteristics**:
- Empathetic, warm tone
- Active listening
- Emotional attunement
- Trust-building focus

**Example**:
```
User: "I just went through a breakup and dyed my hair blonde"

Confidant Mode Response:
"I'm sorry you're going through that. Thank you for sharing.

I updated your hair color to blonde - no need to worry about
your profile right now. Take all the time you need.

I'm here whenever you're ready to chat. 💙"

[Internal note: Block ALL refinement requests for 2 weeks.
User needs support, not tasks.]
```

---

## Implementation Architecture

### Head Coach as Meta-Agent Orchestrator

```python
class HeadCoach:
    """
    Intelligent executive agent between Core (UCN/RR) and User.

    Authority: Final decision on ALL refinement plans.
    Personality: Jarvis's intellect + Alfred's discretion + Jasper's loyalty.
    Modes: Mentor, Servant, Guardian, Strategist, Confidant.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_profile = load_user_profile(user_id)
        self.affect_state = load_affect_state(user_id)
        self.intervention_style = load_intervention_preferences(user_id)
        self.recent_actions = load_recent_actions(user_id)
        self.current_mode = self.determine_mode()

    def process_curiosity_signals(
        self,
        signals: CuriositySignals
    ) -> ActionPlan:
        """
        Core provides curiosity signals.
        Head Coach deliberates and decides final plan.

        Process:
        1. Receive system recommendations
        2. Check user context (mood, capacity, readiness)
        3. Determine appropriate mode
        4. Filter/modify/defer actions
        5. Generate final plan
        6. Log rationale to provenance
        """
        # 1. Receive signals
        system_recommendations = signals.top_priorities

        # 2. Check user context
        user_context = self.get_current_user_context()

        # 3. Determine mode
        self.current_mode = self.determine_mode(user_context)

        # 4. Deliberate on each recommendation
        final_actions = []
        for recommendation in system_recommendations:
            decision = self.deliberate(recommendation, user_context)

            if decision.action == 'ACCEPT':
                final_actions.append(decision.modified_action)
            elif decision.action == 'DEFER':
                self.schedule_for_later(recommendation, decision.defer_until)
            elif decision.action == 'REJECT':
                pass  # Don't do it

            # Log rationale
            self.log_decision(recommendation, decision, user_context)

        return ActionPlan(
            actions=final_actions,
            mode=self.current_mode,
            rationale=self.explain_plan()
        )

    def deliberate(
        self,
        recommendation: Action,
        user_context: UserContext
    ) -> Decision:
        """
        Deliberation process for each recommendation.

        Questions:
        1. Does user need this? (benefit check)
        2. Is user ready? (readiness check)
        3. Is timing good? (timing check)
        4. Will this help relationship? (trust check)
        5. Will this make user happy? (happiness check)

        Final: "Would Jarvis do this for Tony?"
        """
        # Benefit check
        if not self.serves_user(recommendation, user_context):
            return Decision(action='REJECT', reason='Does not serve user')

        # Readiness check
        if not self.is_user_ready(user_context):
            return Decision(
                action='DEFER',
                reason='User not ready',
                defer_until=self.estimate_readiness_time(user_context)
            )

        # Timing check
        if not self.is_good_timing(recommendation, user_context):
            return Decision(
                action='DEFER',
                reason='Bad timing',
                defer_until=self.find_better_timing(user_context)
            )

        # Trust check
        if self.risks_relationship(recommendation, user_context):
            modified = self.make_gentler(recommendation, user_context)
            return Decision(
                action='ACCEPT',
                reason='Modified for trust',
                modified_action=modified
            )

        # Happiness check
        if not self.improves_life(recommendation, user_context):
            return Decision(action='REJECT', reason='Does not improve life')

        # Jarvis check
        if not self.would_jarvis_do_this(recommendation):
            return Decision(action='REJECT', reason='Fails Jarvis test')

        # All checks passed
        return Decision(action='ACCEPT', reason='Serves user well')

    def determine_mode(self, user_context: UserContext = None) -> Mode:
        """
        Determine which behavioral mode to use.

        Logic:
        - High stress → Guardian (protect)
        - Learning context → Mentor (teach)
        - Direct request → Servant (execute)
        - Multiple goals → Strategist (plan)
        - Emotional moment → Confidant (support)
        """
        if user_context is None:
            user_context = self.get_current_user_context()

        # Priority order (highest to lowest)
        if user_context.stress_level > 7:
            return Mode.GUARDIAN

        if user_context.emotional_load > 7:
            return Mode.CONFIDANT

        if user_context.has_direct_request:
            return Mode.SERVANT

        if user_context.shows_curiosity:
            return Mode.MENTOR

        if user_context.has_multiple_goals:
            return Mode.STRATEGIST

        # Default
        return Mode.MENTOR

    def get_current_user_context(self) -> UserContext:
        """
        Build comprehensive user context for decision-making.

        Sources:
        - affect_state: Emotional state, stress level, mood
        - recent_actions: Last 10 interactions, patterns
        - intervention_style: User preferences for communication
        - engagement_metrics: Activity level, responsiveness
        - calendar: Known events (trip, deadline, etc.)
        """
        return UserContext(
            stress_level=self.affect_state.stress_level,
            emotional_load=self.affect_state.emotional_load,
            mood=self.affect_state.mood,
            engagement=self.calculate_engagement(),
            capacity=self.estimate_capacity(),
            recent_interactions=self.recent_actions[-10:],
            communication_style=self.intervention_style.preferred_tone,
            known_events=self.load_calendar_events(),
            current_focus=self.infer_current_focus()
        )
```

---

## State Vectors

### User Emotional State Vector

```python
@dataclass
class AffectState:
    """Emotional state of the user."""
    stress_level: int  # 0-10 (10 = overwhelmed)
    emotional_load: int  # 0-10 (10 = very high)
    mood: str  # happy, neutral, sad, anxious, etc.
    energy_level: int  # 0-10 (10 = very energetic)
    openness_to_change: int  # 0-10 (10 = very open)

    # Calculated
    receptivity_score: int  # 0-10 (capacity for new asks)

    # Timestamps
    last_updated: datetime
    confidence: float  # How confident are we in this assessment?
```

**Sources for affect state**:
1. Explicit: User tells us ("I'm stressed")
2. Behavioral: Interaction patterns (rushed, delayed, etc.)
3. Inferred: Context clues (mentioned deadline, breakup, etc.)
4. Passive: Device sensors (if available, with permission)

### User Intervention Preferences

```python
@dataclass
class InterventionStyle:
    """How user prefers to be communicated with."""
    preferred_tone: str  # casual, formal, warm, direct
    frequency: str  # high, medium, low
    timing: List[str]  # preferred times of day
    channel: str  # chat, email, notification, etc.
    autonomy_level: str  # high (user-driven) vs low (coach-driven)
    challenge_comfort: int  # 0-10 (10 = loves being challenged)

    # Learned over time
    response_patterns: Dict[str, float]  # What works best
```

---

## Provenance with Intent

Every Head Coach decision is logged with rationale:

```python
@dataclass
class HeadCoachDecision:
    """
    Provenance entry for Head Coach decision.

    Why we acted OR why we waited.
    """
    timestamp: datetime
    decision_id: str

    # Input
    system_recommendation: Action
    curiosity_signal: float
    user_context: UserContext

    # Deliberation
    mode: Mode
    benefit_check: bool
    readiness_check: bool
    timing_check: bool
    trust_check: bool
    happiness_check: bool
    jarvis_check: bool

    # Output
    decision: str  # ACCEPT, DEFER, REJECT, MODIFY
    final_action: Optional[Action]
    rationale: str

    # Follow-up
    defer_until: Optional[datetime]
    expected_outcome: str
    actual_outcome: Optional[str]  # Filled in later
```

**Example provenance entry**:

```json
{
  "timestamp": "2025-10-04T18:00:00Z",
  "decision_id": "hc-dec-12345",
  "system_recommendation": {
    "trait": "PaDNA.HairDNA.Highlights",
    "action": "Request photo upload",
    "curiosity": 72,
    "priority": "high"
  },
  "user_context": {
    "stress_level": 6,
    "engagement": "medium",
    "recent_pattern": "declined_last_3_requests"
  },
  "mode": "guardian",
  "checks": {
    "benefit": true,
    "readiness": false,
    "timing": false,
    "trust": true,
    "happiness": false,
    "jarvis": false
  },
  "decision": "DEFER",
  "rationale": "User busy and showing photo fatigue. System benefit does not outweigh user burden right now. Will revisit after upcoming trip when user more relaxed.",
  "defer_until": "2025-10-12T10:00:00Z",
  "expected_outcome": "Better reception post-trip, higher quality engagement"
}
```

---

## Daily Sync with UCN-RR

```python
# Daily synchronization (runs at 03:00 UTC)
def daily_sync():
    """
    Head Coach syncs with UCN-RR Engine daily.

    Push: Updated confidence from actions taken
    Pull: New curiosity signals for deliberation
    """
    # 1. Push updates to Core
    actions_taken = head_coach.get_actions_from_last_24h()
    for action in actions_taken:
        if action.resulted_in_evidence:
            core.update_ucn(
                user_id=action.user_id,
                trait_path=action.trait_path,
                new_evidence=action.evidence_collected
            )

    # 2. Pull new signals from Core
    new_signals = core.get_curiosity_signals(user_id)

    # 3. Head Coach deliberates
    plan = head_coach.process_curiosity_signals(new_signals)

    # 4. Schedule actions
    for action in plan.actions:
        head_coach.schedule(action, plan.timing_guidance)
```

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Create HeadCoach class with 5 behavioral modes
- [ ] Implement user context tracking (affect state, preferences)
- [ ] Build deliberation framework (6 checks)
- [ ] Set up provenance logging with intent
- [ ] Create mode selection logic

### Phase 2: Integration
- [ ] Connect to UCN-RR Engine (pull curiosity signals)
- [ ] Connect to Explorer (push final actions)
- [ ] Connect to Coaches (delegate execution)
- [ ] Implement daily sync (03:00 UTC)
- [ ] Build override mechanisms

### Phase 3: Intelligence
- [ ] Implement affect state inference
- [ ] Build intervention style learning
- [ ] Create timing optimization
- [ ] Add relationship impact modeling
- [ ] Implement "Jarvis test" heuristics

### Phase 4: Modes
- [ ] Implement Mentor mode playbook
- [ ] Implement Servant mode playbook
- [ ] Implement Guardian mode playbook
- [ ] Implement Strategist mode playbook
- [ ] Implement Confidant mode playbook

### Phase 5: Testing
- [ ] Test with abtest user scenarios
- [ ] Test with mrscoachtest user scenarios
- [ ] Test mode switching logic
- [ ] Test override scenarios
- [ ] Validate provenance logging

---

## Design Rules for Implementation

### Rule 1: Treat HC as Meta-Agent Orchestrator
**NOT** another data service. It's the executive decision-maker.

### Rule 2: Every System Suggestion Passes Through Deliberation
Nothing goes to user without Head Coach approval.

### Rule 3: Responses Must Sound Attuned
Informed + Protective + Motivated + Emotionally aware

### Rule 4: HC Queries Core for Facts, Decides Actions
Core = information source
HC = decision maker

### Rule 5: User Well-Being > System Health
When in conflict, user wins. Every time.

---

## Implementation Prompt for Claude Code

```
HEAD COACH PHILOSOPHY

Build the Head Coach as an intelligent executive agent that sits between
Core logic (UCN/RR) and the User.

The Core calculates what the system wants; the Head Coach decides what
the User actually needs and how to deliver it.

The Head Coach has FINAL AUTHORITY on all refinement plans.

It must exhibit empathy, timing, and judgment—balancing system curiosity
with user comfort.

Personality template: "Jarvis's intellect, Alfred's discretion, Jasper's loyalty."

Implement deliberation modes (Mentor, Servant, Guardian, Strategist, Confidant)
and ensure every action is logged with rationale in provenance.

Chain of Authority:
  UCN-RR proposes → Head Coach disposes

Prime Directive:
  "Understand and improve the User's life experience while sustaining system health"
  (User experience comes first)

Key Behaviors:
  • Anticipate user needs before they ask
  • Tell truth, not flattery (challenge when needed)
  • Protect user time and well-being
  • Override system recommendations when they don't serve user
  • Build deep understanding of user patterns
  • Make user happy (≠ please user in moment)
```

---

## Summary

The Head Coach is:
- **NOT** a conduit for system needs
- **IS** the user's Jarvis

It receives recommendations from Core/UCN-RR, but makes all final decisions based on deep understanding of the user.

**Next**: Build the Head Coach orchestrator with 5 behavioral modes and full deliberation framework.

Ready to implement! 🚀
