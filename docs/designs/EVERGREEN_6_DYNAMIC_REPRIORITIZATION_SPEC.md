# Dynamic Curiosity Reprioritization & Daily HC Prompts

**Version:** 1.0
**Date:** 2025-10-12
**Purpose:** Adaptive curiosity focus based on real-time context

---

## 1. Overview

Dynamic reprioritization ensures that curiosity exploration remains relevant, timely, and contextually appropriate. Rather than following a static exploration plan, the system continuously adapts based on:

- User's current life context
- Conversation dynamics
- Temporal patterns
- Emerging priorities
- User engagement signals

Additionally, the Head Coach receives daily prompts to systematically reduce curiosity debt.

---

## 2. Reprioritization Triggers

### 2.1 Context Change Events

```python
class ReprioritizationTrigger(Enum):
    USER_CONTEXT_CHANGE = "user_context_change"
    CONVERSATION_SHIFT = "conversation_shift"
    TIME_OF_DAY = "time_of_day"
    USER_MENTION = "user_mention"
    ENGAGEMENT_CHANGE = "engagement_change"
    LIFE_EVENT = "life_event"
    PREREQUISITE_FILLED = "prerequisite_filled"
    SCHEDULED_REVIEW = "scheduled_review"

@dataclass
class ReprioritizationEvent:
    trigger: ReprioritizationTrigger
    timestamp: datetime
    context: Dict[str, Any]
    priority: str  # "immediate", "high", "normal", "low"
```

### 2.2 Trigger Handlers

```python
class DynamicReprioritizer:
    """
    Dynamically adjust curiosity priorities based on context.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.current_priorities = self.load_current_priorities()
        self.reprioritization_history = []

    async def handle_trigger(self, event: ReprioritizationEvent):
        """
        Handle a reprioritization trigger.
        """
        if event.trigger == ReprioritizationTrigger.USER_CONTEXT_CHANGE:
            await self.handle_context_change(event)

        elif event.trigger == ReprioritizationTrigger.CONVERSATION_SHIFT:
            await self.handle_conversation_shift(event)

        elif event.trigger == ReprioritizationTrigger.USER_MENTION:
            await self.handle_user_mention(event)

        elif event.trigger == ReprioritizationTrigger.ENGAGEMENT_CHANGE:
            await self.handle_engagement_change(event)

        elif event.trigger == ReprioritizationTrigger.LIFE_EVENT:
            await self.handle_life_event(event)

        elif event.trigger == ReprioritizationTrigger.PREREQUISITE_FILLED:
            await self.handle_prerequisite_filled(event)

        # Log the reprioritization
        self.reprioritization_history.append({
            "timestamp": event.timestamp,
            "trigger": event.trigger.value,
            "context": event.context,
            "result": "priorities_updated"
        })

    async def handle_context_change(self, event: ReprioritizationEvent):
        """
        User's life context has changed (e.g., new job, relationship, goal).
        """
        new_context = event.context.get('new_context', {})

        # Identify newly relevant namespaces
        relevant_namespaces = self.identify_relevant_namespaces(new_context)

        # Boost containers in these namespaces
        for namespace in relevant_namespaces:
            containers = self.get_containers_by_namespace(namespace)
            for container in containers:
                self.boost_priority(container.id, boost_factor=0.3, reason="context_change")

        # De-prioritize less relevant areas
        less_relevant = self.identify_less_relevant_namespaces(new_context)
        for namespace in less_relevant:
            containers = self.get_containers_by_namespace(namespace)
            for container in containers:
                self.reduce_priority(container.id, reduction=0.2, reason="context_change")

    async def handle_conversation_shift(self, event: ReprioritizationEvent):
        """
        Conversation has shifted to a new topic.
        """
        new_topic = event.context.get('topic')

        # Find containers related to this topic
        related_containers = self.find_related_containers(new_topic)

        # Temporarily boost these containers
        for container_id in related_containers:
            self.boost_priority(
                container_id,
                boost_factor=0.4,
                duration_minutes=15,  # Temporary boost
                reason="conversation_relevance"
            )

    async def handle_user_mention(self, event: ReprioritizationEvent):
        """
        User explicitly mentioned a topic or area.
        """
        mentioned_topic = event.context.get('topic')

        # Strong signal - user is interested in this area
        related_containers = self.find_related_containers(mentioned_topic)

        for container_id in related_containers:
            self.boost_priority(
                container_id,
                boost_factor=0.5,
                reason="user_expressed_interest"
            )

    async def handle_engagement_change(self, event: ReprioritizationEvent):
        """
        User's engagement level has changed.
        """
        engagement_level = event.context.get('engagement_level')

        if engagement_level == "high":
            # User is engaged - good time for deeper exploration
            self.enable_deep_dive_mode()

        elif engagement_level == "low":
            # User is disengaged - stick to lighter, easier topics
            self.enable_light_exploration_mode()

        elif engagement_level == "distracted":
            # Pause curiosity exploration
            self.pause_exploration(duration_minutes=30)

    async def handle_life_event(self, event: ReprioritizationEvent):
        """
        Significant life event detected.
        """
        life_event = event.context.get('event_type')

        # Major life events shift priorities dramatically
        event_priority_map = {
            "new_job": ["CareerDNA", "GoalDNA", "StressDNA"],
            "relationship_change": ["RelationshipDNA", "EmotionalDNA", "CommStyleDNA"],
            "health_issue": ["HealthDNA", "StressDNA", "SupportDNA"],
            "relocation": ["EnvironmentDNA", "SocialDNA", "AdaptabilityDNA"],
            "financial_change": ["FinancialDNA", "GoalDNA", "SecurityDNA"]
        }

        if life_event in event_priority_map:
            priority_namespaces = event_priority_map[life_event]

            for namespace in priority_namespaces:
                containers = self.get_containers_by_namespace(namespace)
                for container in containers:
                    self.boost_priority(
                        container.id,
                        boost_factor=0.6,
                        reason=f"life_event_{life_event}"
                    )

    async def handle_prerequisite_filled(self, event: ReprioritizationEvent):
        """
        A prerequisite container was filled - unlock dependent containers.
        """
        filled_container = event.context.get('container_id')

        # Find containers that depend on this one
        dependent_containers = self.find_dependent_containers(filled_container)

        for container_id in dependent_containers:
            self.unlock_container(container_id)
            self.boost_priority(
                container_id,
                boost_factor=0.4,
                reason="prerequisite_met"
            )

    def boost_priority(self, container_id: str, boost_factor: float,
                      reason: str, duration_minutes: Optional[int] = None):
        """
        Increase the priority of a container.
        """
        current_priority = self.current_priorities.get(container_id, {})

        new_priority = min(
            current_priority.get('score', 0.5) + boost_factor,
            1.0
        )

        self.current_priorities[container_id] = {
            'score': new_priority,
            'reason': reason,
            'boosted_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=duration_minutes) if duration_minutes else None
        }

        self.save_priorities()

    def reduce_priority(self, container_id: str, reduction: float, reason: str):
        """
        Decrease the priority of a container.
        """
        current_priority = self.current_priorities.get(container_id, {})

        new_priority = max(
            current_priority.get('score', 0.5) - reduction,
            0.0
        )

        self.current_priorities[container_id] = {
            'score': new_priority,
            'reason': reason,
            'reduced_at': datetime.now()
        }

        self.save_priorities()
```

---

## 3. Temporal Reprioritization

### 3.1 Time-of-Day Patterns

```python
class TemporalReprioritizer:
    """
    Adjust priorities based on time of day and user patterns.
    """

    def get_time_appropriate_containers(self, user_id: str) -> List[str]:
        """
        Return containers appropriate for current time.
        """
        current_hour = datetime.now().hour
        user_patterns = load_user_temporal_patterns(user_id)

        # Morning (6am-12pm): Energy, goals, work
        if 6 <= current_hour < 12:
            return [
                "GoalDNA.daily_priorities",
                "EnergyDNA.morning_routines",
                "ProductivityDNA.*",
                "CareerDNA.*"
            ]

        # Afternoon (12pm-5pm): Work, productivity, decisions
        elif 12 <= current_hour < 17:
            return [
                "DecisionDNA.*",
                "StressDNA.*",
                "CareerDNA.*",
                "CollaborationDNA.*"
            ]

        # Evening (5pm-9pm): Relationships, reflection, hobbies
        elif 17 <= current_hour < 21:
            return [
                "RelationshipDNA.*",
                "HobbyDNA.*",
                "ReflectionDNA.*",
                "BalanceDNA.*"
            ]

        # Night (9pm-12am): Reflection, planning, self-care
        elif 21 <= current_hour < 24:
            return [
                "SelfCareDNA.*",
                "ReflectionDNA.*",
                "SleepDNA.*",
                "GoalDNA.future_vision"
            ]

        # Late night (12am-6am): Minimal exploration (user likely asleep)
        else:
            return []

    def apply_temporal_boost(self, container_priorities: Dict) -> Dict:
        """
        Apply time-of-day boosts to container priorities.
        """
        time_appropriate = self.get_time_appropriate_containers(self.user_id)

        for container_id in container_priorities:
            # Check if this container matches time-appropriate patterns
            if any(self.matches_pattern(container_id, pattern)
                   for pattern in time_appropriate):
                # Boost priority
                container_priorities[container_id]['score'] *= 1.3
                container_priorities[container_id]['temporal_boost'] = True

        return container_priorities
```

### 3.2 Weekly and Seasonal Patterns

```python
def apply_weekly_patterns(container_priorities: Dict, user_id: str) -> Dict:
    """
    Adjust for day of week patterns.
    """
    day_of_week = datetime.now().weekday()

    # Monday: Goal setting, week planning
    if day_of_week == 0:
        boost_patterns = ["GoalDNA.*", "PlanningDNA.*", "MotivationDNA.*"]

    # Wednesday: Check-in, progress
    elif day_of_week == 2:
        boost_patterns = ["ProgressDNA.*", "AdjustmentDNA.*"]

    # Friday: Reflection, work-life balance
    elif day_of_week == 4:
        boost_patterns = ["ReflectionDNA.*", "BalanceDNA.*", "TransitionDNA.*"]

    # Weekend: Relationships, hobbies, rest
    elif day_of_week >= 5:
        boost_patterns = ["RelationshipDNA.*", "HobbyDNA.*", "RestDNA.*"]

    else:
        boost_patterns = []

    # Apply boosts
    for container_id in container_priorities:
        if any(matches_pattern(container_id, pattern) for pattern in boost_patterns):
            container_priorities[container_id]['score'] *= 1.2

    return container_priorities
```

---

## 4. Daily HC Prompts

### 4.1 Prompt Generation System

```python
class DailyCuriosityPrompt:
    """
    Generate daily prompts for Head Coach to explore unfilled containers.
    """

    def generate_daily_prompt(self, user_id: str) -> Dict:
        """
        Generate a focused exploration plan for today.
        """
        # Get high-debt containers
        debt_tracker = CuriosityDebtTracker(user_id)
        high_debt = debt_tracker.get_high_debt_containers(threshold=0.6)

        # Apply dynamic reprioritization
        reprioritizer = DynamicReprioritizer(user_id)
        prioritized = reprioritizer.apply_current_boosts(high_debt)

        # Apply temporal filtering
        temporal = TemporalReprioritizer()
        time_appropriate = temporal.filter_by_time_of_day(prioritized)

        # Select top 3-5 for today
        today_focus = time_appropriate[:5]

        # Generate exploration strategies
        strategies = []
        for container in today_focus:
            strategy = self.generate_exploration_strategy(container, user_id)
            strategies.append(strategy)

        return {
            "date": datetime.now().date(),
            "user_id": user_id,
            "focus_containers": [c.container_id for c in today_focus],
            "exploration_strategies": strategies,
            "estimated_questions": sum(s['question_count'] for s in strategies),
            "priority_explanation": self.explain_priorities(today_focus)
        }

    def generate_exploration_strategy(self, container: PrioritizedContainer, user_id: str) -> Dict:
        """
        Create a strategy for exploring this container today.
        """
        container_info = load_container_info(container.container_id)

        # Determine question approach
        approach = self.determine_approach(container, user_id)

        # Generate sample questions
        sample_questions = self.generate_sample_questions(container, approach)

        # Identify conversation opportunities
        opportunities = self.identify_opportunities(container, user_id)

        return {
            "container_id": container.container_id,
            "container_name": container_info.name,
            "debt_score": container.priority_score,
            "approach": approach,
            "sample_questions": sample_questions,
            "opportunities": opportunities,
            "question_count": len(sample_questions),
            "estimated_duration_minutes": len(sample_questions) * 3
        }

    def determine_approach(self, container: PrioritizedContainer, user_id: str) -> str:
        """
        Determine best approach for this container.
        """
        # Check user's conversation style preference
        user_prefs = load_user_preferences(user_id)

        # Check container characteristics
        container_info = load_container_info(container.container_id)

        # Match approach to container and user
        if container_info.is_sensitive:
            return "gentle_indirect"
        elif container_info.is_abstract:
            return "concrete_examples"
        elif user_prefs.prefers_direct:
            return "direct_inquiry"
        else:
            return "conversational_discovery"

    def generate_sample_questions(self, container: PrioritizedContainer, approach: str) -> List[str]:
        """
        Generate 2-4 sample questions for this container.
        """
        container_info = load_container_info(container.container_id)

        # Load question templates for this approach
        templates = load_question_templates(approach)

        # Generate questions
        questions = []
        for template in templates[:4]:  # Max 4 questions
            question = template.format(
                topic=container_info.friendly_name,
                context=container_info.context_hint
            )
            questions.append(question)

        return questions

    def identify_opportunities(self, container: PrioritizedContainer, user_id: str) -> List[str]:
        """
        Identify when/where to naturally explore this container.
        """
        opportunities = []

        # Check conversation history for related topics
        conversation_history = load_conversation_history(user_id, days=7)
        related_topics = self.find_related_topics(container, conversation_history)

        if related_topics:
            opportunities.append(f"When user mentions: {', '.join(related_topics[:3])}")

        # Check scheduled activities
        user_schedule = load_user_schedule(user_id)
        relevant_activities = self.find_relevant_activities(container, user_schedule)

        if relevant_activities:
            opportunities.append(f"During/after: {', '.join(relevant_activities[:2])}")

        # Time-based opportunities
        time_ops = self.get_time_based_opportunities(container)
        opportunities.extend(time_ops)

        return opportunities
```

### 4.2 Daily Prompt Delivery

```python
async def deliver_daily_prompt_to_hc(user_id: str):
    """
    Deliver daily curiosity prompt to Head Coach.
    """
    # Generate prompt
    prompt_generator = DailyCuriosityPrompt()
    daily_prompt = prompt_generator.generate_daily_prompt(user_id)

    # Format for HC consumption
    hc_prompt = {
        "type": "daily_curiosity_focus",
        "user_id": user_id,
        "date": str(daily_prompt['date']),
        "instructions": generate_hc_instructions(daily_prompt),
        "focus_areas": daily_prompt['focus_containers'],
        "strategies": daily_prompt['exploration_strategies'],
        "priority_explanation": daily_prompt['priority_explanation']
    }

    # Deliver to HC orchestrator
    await hc_orchestrator.receive_daily_prompt(hc_prompt)

    # Log delivery
    log_prompt_delivery(user_id, daily_prompt)

def generate_hc_instructions(daily_prompt: Dict) -> str:
    """
    Generate natural language instructions for HC.
    """
    instructions = f"""
    Today's Curiosity Focus for User {daily_prompt['user_id']}
    ============================================

    Priority Areas to Explore:
    {format_container_list(daily_prompt['focus_containers'])}

    Exploration Approach:
    {format_strategies(daily_prompt['exploration_strategies'])}

    Why These Areas:
    {daily_prompt['priority_explanation']}

    Target: {daily_prompt['estimated_questions']} questions across {len(daily_prompt['focus_containers'])} areas

    Remember:
    - Weave questions naturally into conversation
    - Don't force if user is unengaged or stressed
    - Adapt based on user's responses
    - Celebrate progress in reducing curiosity debt
    """

    return instructions
```

### 4.3 Progress Tracking

```python
class DailyCuriosityTracker:
    """
    Track progress on daily curiosity exploration.
    """

    def track_daily_progress(self, user_id: str, date: datetime.date) -> Dict:
        """
        Track how much curiosity debt was addressed today.
        """
        daily_prompt = load_daily_prompt(user_id, date)
        conversation_log = load_conversation_log(user_id, date)

        progress = {
            "date": date,
            "target_containers": daily_prompt['focus_containers'],
            "explored_containers": [],
            "questions_asked": 0,
            "questions_answered": 0,
            "new_data_points": 0,
            "debt_reduction": 0.0
        }

        # Analyze conversation for curiosity exploration
        for turn in conversation_log:
            if self.is_curiosity_question(turn):
                progress['questions_asked'] += 1

                # Check if user responded with useful info
                if self.has_useful_response(turn):
                    progress['questions_answered'] += 1

                    # Track which container was explored
                    container = self.identify_explored_container(turn)
                    if container:
                        progress['explored_containers'].append(container)

                    # Count new data points
                    data_points = self.extract_data_points(turn)
                    progress['new_data_points'] += len(data_points)

        # Calculate debt reduction
        initial_debt = self.get_morning_debt_score(user_id, date)
        final_debt = self.get_evening_debt_score(user_id, date)
        progress['debt_reduction'] = initial_debt - final_debt

        return progress

    def generate_daily_report(self, user_id: str, date: datetime.date) -> str:
        """
        Generate end-of-day curiosity exploration report.
        """
        progress = self.track_daily_progress(user_id, date)

        report = f"""
        Daily Curiosity Report - {date}
        ================================

        Exploration Target: {len(progress['target_containers'])} containers
        Actually Explored: {len(progress['explored_containers'])} containers

        Questions Asked: {progress['questions_asked']}
        Useful Responses: {progress['questions_answered']}
        New Data Points: {progress['new_data_points']}

        Debt Reduction: {progress['debt_reduction']:.2f}

        Explored Areas:
        {format_container_list(progress['explored_containers'])}

        Status: {"✓ Target Met" if len(progress['explored_containers']) >= len(progress['target_containers']) else "⚠ Partial Progress"}
        """

        return report
```

---

## 5. Feedback Loop & Learning

### 5.1 Question Quality Evaluation

```python
class QuestionQualityEvaluator:
    """
    Evaluate and improve question quality based on user responses.
    """

    def evaluate_question(self, question: str, user_response: str,
                         container_id: str) -> Dict:
        """
        Evaluate how effective a question was.
        """
        metrics = {
            "question": question,
            "container_id": container_id,
            "response_length": len(user_response.split()),
            "data_extracted": self.count_extractable_data(user_response),
            "user_engagement": self.measure_engagement(user_response),
            "naturalness": self.assess_naturalness(question, user_response),
            "effectiveness_score": 0.0
        }

        # Calculate overall effectiveness
        metrics['effectiveness_score'] = (
            min(metrics['response_length'] / 50, 1.0) * 0.3 +
            min(metrics['data_extracted'] / 3, 1.0) * 0.4 +
            metrics['user_engagement'] * 0.3
        )

        return metrics

    def update_question_templates(self, evaluation_results: List[Dict]):
        """
        Improve question templates based on evaluation data.
        """
        # Group by container type
        by_container = {}
        for result in evaluation_results:
            container = result['container_id']
            if container not in by_container:
                by_container[container] = []
            by_container[container].append(result)

        # For each container, identify best-performing questions
        for container_id, results in by_container.items():
            # Find highest-scoring questions
            best_questions = sorted(
                results,
                key=lambda r: r['effectiveness_score'],
                reverse=True
            )[:5]

            # Update template library
            self.update_templates_for_container(container_id, best_questions)

    def measure_engagement(self, user_response: str) -> float:
        """
        Measure user engagement from response.

        Signals:
        - Response length
        - Emotional language
        - Details provided
        - Follow-up questions from user
        """
        engagement_score = 0.0

        # Length bonus
        word_count = len(user_response.split())
        engagement_score += min(word_count / 100, 0.3)

        # Emotional language
        if self.contains_emotional_language(user_response):
            engagement_score += 0.2

        # Details (names, numbers, specific examples)
        if self.contains_specific_details(user_response):
            engagement_score += 0.3

        # User asks follow-up
        if "?" in user_response:
            engagement_score += 0.2

        return min(engagement_score, 1.0)
```

---

## 6. Integration Summary

### Files to Create/Modify

1. **NEW: `ReDNACoreDemo/core/curiosity/dynamic_reprioritizer.py`**
2. **NEW: `ReDNACoreDemo/core/curiosity/temporal_reprioritizer.py`**
3. **NEW: `ReDNACoreDemo/core/curiosity/daily_prompt_generator.py`**
4. **NEW: `ReDNACoreDemo/core/curiosity/question_quality_evaluator.py`**
5. **MODIFY: `ReDNACoreDemo/core/hc_orchestrator.py`** - Add daily prompt handling

---

## 7. Success Metrics

1. **Reprioritization Responsiveness**: Time from context change to priority adjustment
2. **Temporal Appropriateness**: % of questions asked at appropriate times
3. **Daily Target Achievement**: % of daily curiosity targets met
4. **Question Effectiveness**: Average effectiveness score of questions
5. **Debt Reduction Rate**: Weekly average curiosity debt reduction

---

## Summary

Dynamic reprioritization and daily HC prompts transform curiosity exploration from static to adaptive. By continuously adjusting to user context, time patterns, and engagement signals, we ensure exploration remains relevant and effective. Daily prompts give HC clear, actionable guidance while maintaining conversational naturalness.

**Next Steps:**
1. Implement reprioritization trigger system
2. Build temporal pattern recognition
3. Create daily prompt generator
4. Integrate with HC orchestrator
5. Deploy question quality feedback loop
