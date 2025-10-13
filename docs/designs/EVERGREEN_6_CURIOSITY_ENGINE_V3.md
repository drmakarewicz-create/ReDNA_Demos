# Evergreen 6: Curiosity Engine v3 - Architecture & Design

**Version:** 3.0
**Date:** 2025-10-12
**Purpose:** Intelligent exploration of unfilled ontology containers

---

## 1. Executive Summary

Curiosity Engine v3 represents a significant evolution in how ReDNA discovers and fills gaps in user understanding. By combining Core intelligence, UCN/RR distribution analysis, and Head Coach conversation strategy, the system proactively identifies unexplored areas and generates contextually appropriate questions.

### Key Innovations

1. **Curiosity Debt Tracking**: Quantify unexplored containers and prioritize exploration
2. **Dynamic Reprioritization**: Adjust curiosity focus based on user context and needs
3. **Multi-Source Intelligence**: Combine Core, UCN/RR, and HC insights
4. **Conversational Integration**: Seamlessly weave curiosity questions into natural dialogue
5. **Learning Feedback Loop**: Improve question quality based on user responses

---

## 2. System Architecture

### 2.1 High-Level Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   CURIOSITY ENGINE V3                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐    ┌─────────────┐    ┌───────────────┐        │
│  │  Core      │───→│  Curiosity  │←───│   UCN/RR      │        │
│  │  Analysis  │    │  Coordinator│    │   Analysis    │        │
│  └────────────┘    └──────┬──────┘    └───────────────┘        │
│                           │                                     │
│                           ▼                                     │
│                  ┌─────────────────┐                           │
│                  │  Curiosity Debt │                           │
│                  │    Tracker      │                           │
│                  └────────┬────────┘                           │
│                           │                                     │
│                           ▼                                     │
│                  ┌─────────────────┐                           │
│                  │  Prioritization │                           │
│                  │    Engine       │                           │
│                  └────────┬────────┘                           │
│                           │                                     │
│                           ▼                                     │
│                  ┌─────────────────┐                           │
│                  │   Question      │                           │
│                  │   Generator     │                           │
│                  └────────┬────────┘                           │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   Head Coach    │
                   │   Integration   │
                   └─────────────────┘
```

### 2.2 Core Components

#### Component 1: Core Analysis
- **Purpose**: Identify empty/low-confidence containers
- **Input**: User ontology graph
- **Output**: List of unexplored containers with metadata

#### Component 2: UCN/RR Analysis
- **Purpose**: Assess distribution gaps and statistical anomalies
- **Input**: UCN/RR distributions, population baselines
- **Output**: Priority containers based on uncertainty

#### Component 3: Curiosity Coordinator
- **Purpose**: Orchestrate multi-source inputs
- **Input**: Core analysis + UCN/RR analysis
- **Output**: Unified curiosity map

#### Component 4: Curiosity Debt Tracker
- **Purpose**: Quantify and track unexplored areas
- **Input**: Curiosity map + exploration history
- **Output**: Debt scores and exploration priorities

#### Component 5: Prioritization Engine
- **Purpose**: Rank containers for exploration
- **Input**: Debt scores + user context + conversation state
- **Output**: Ordered list of containers to explore

#### Component 6: Question Generator
- **Purpose**: Create natural, contextual questions
- **Input**: Prioritized containers + conversation history
- **Output**: Candidate questions for HC

#### Component 7: HC Integration
- **Purpose**: Seamlessly inject questions into conversation
- **Input**: Generated questions + conversation flow
- **Output**: Natural dialogue with embedded curiosity

---

## 3. Detailed Component Specifications

### 3.1 Core Analysis

```python
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class ContainerAnalysis:
    container_id: str
    namespace: str
    fullness: float  # 0.0 = empty, 1.0 = fully explored
    confidence: float  # Average confidence of existing data
    importance: float  # Domain importance score
    last_explored: Optional[datetime]
    related_containers: List[str]

class CoreAnalyzer:
    """
    Analyze user's ontology to identify exploration gaps.
    """

    def analyze_user_ontology(self, user_id: str) -> List[ContainerAnalysis]:
        """
        Scan user's ontology for unexplored or low-confidence containers.
        """
        ontology = load_user_ontology(user_id)
        container_patterns = load_container_patterns_v5()

        analyses = []

        for container in container_patterns.all_containers:
            # Get user's data for this container
            user_data = ontology.get_container_data(container.id)

            # Calculate fullness
            fullness = self.calculate_fullness(user_data, container)

            # Calculate average confidence
            confidence = self.calculate_average_confidence(user_data)

            # Determine importance
            importance = self.determine_importance(container, user_id)

            # Find last exploration time
            last_explored = self.find_last_exploration(user_id, container.id)

            # Identify related containers
            related = self.find_related_containers(container, ontology)

            analyses.append(ContainerAnalysis(
                container_id=container.id,
                namespace=container.namespace,
                fullness=fullness,
                confidence=confidence,
                importance=importance,
                last_explored=last_explored,
                related_containers=related
            ))

        return analyses

    def calculate_fullness(self, user_data: dict, container: dict) -> float:
        """
        Calculate how "full" a container is with user data.

        Fullness = (traits_present / total_traits) * avg_data_quality
        """
        if not container.expected_traits:
            return 0.0

        traits_present = sum(1 for trait in container.expected_traits
                           if trait.id in user_data.traits)
        trait_ratio = traits_present / len(container.expected_traits)

        # Factor in data quality
        avg_quality = self.calculate_average_quality(user_data)

        return trait_ratio * avg_quality

    def calculate_average_confidence(self, user_data: dict) -> float:
        """
        Average confidence score of all data points in container.
        """
        if not user_data.traits:
            return 0.0

        total_confidence = sum(trait.confidence for trait in user_data.traits.values())
        return total_confidence / len(user_data.traits)

    def determine_importance(self, container: dict, user_id: str) -> float:
        """
        Determine importance of this container for this user.

        Factors:
        - Domain criticality (core beliefs > peripheral interests)
        - User's life context (career-focused user → CareerDNA high priority)
        - Dependency relationships (foundational containers first)
        """
        base_importance = container.metadata.get('importance', 0.5)

        # Adjust for user context
        user_context = load_user_context(user_id)
        context_boost = self.calculate_context_relevance(container, user_context)

        # Adjust for dependencies
        dependency_boost = self.calculate_dependency_importance(container)

        return min(base_importance + context_boost + dependency_boost, 1.0)

    def find_last_exploration(self, user_id: str, container_id: str) -> Optional[datetime]:
        """
        Find the last time this container was actively explored.
        """
        exploration_log = load_exploration_log(user_id)
        relevant_entries = [e for e in exploration_log if e.container_id == container_id]

        if relevant_entries:
            return max(e.timestamp for e in relevant_entries)

        return None
```

### 3.2 UCN/RR Analysis

```python
from typing import List, Tuple
import numpy as np

class UCNRRAnalyzer:
    """
    Analyze UCN/RR distributions to identify uncertainty and gaps.
    """

    def analyze_distribution_gaps(self, user_id: str) -> List[Dict]:
        """
        Identify containers with high uncertainty or unusual distributions.
        """
        user_dist = load_user_ucnrr_distribution(user_id)
        population_baseline = load_population_baseline()

        gaps = []

        for container_id in user_dist.containers:
            user_container = user_dist.get_container(container_id)
            baseline_container = population_baseline.get_container(container_id)

            # Calculate uncertainty (entropy)
            uncertainty = self.calculate_entropy(user_container)

            # Compare to baseline
            divergence = self.calculate_kl_divergence(user_container, baseline_container)

            # Check for missing data
            sparsity = self.calculate_sparsity(user_container)

            # Determine if this is a gap worth exploring
            if self.is_significant_gap(uncertainty, divergence, sparsity):
                gaps.append({
                    'container_id': container_id,
                    'uncertainty': uncertainty,
                    'divergence': divergence,
                    'sparsity': sparsity,
                    'exploration_priority': self.calculate_priority(
                        uncertainty, divergence, sparsity
                    )
                })

        return sorted(gaps, key=lambda x: x['exploration_priority'], reverse=True)

    def calculate_entropy(self, distribution: np.ndarray) -> float:
        """
        Calculate Shannon entropy of distribution.
        Higher entropy = more uncertainty.
        """
        # Normalize
        dist = distribution / np.sum(distribution)

        # Remove zeros to avoid log(0)
        dist = dist[dist > 0]

        # Calculate entropy
        entropy = -np.sum(dist * np.log2(dist))

        return entropy

    def calculate_kl_divergence(self, dist_p: np.ndarray, dist_q: np.ndarray) -> float:
        """
        Calculate KL divergence: how different is user's distribution from baseline?
        """
        # Normalize
        p = dist_p / np.sum(dist_p)
        q = dist_q / np.sum(dist_q)

        # Avoid division by zero
        q = np.where(q == 0, 1e-10, q)

        # Calculate KL divergence
        kl = np.sum(p * np.log(p / q))

        return kl

    def calculate_sparsity(self, distribution: np.ndarray) -> float:
        """
        Calculate how sparse the distribution is.
        High sparsity = missing data.
        """
        total_bins = len(distribution)
        empty_bins = np.sum(distribution == 0)

        return empty_bins / total_bins

    def is_significant_gap(self, uncertainty: float, divergence: float, sparsity: float) -> bool:
        """
        Determine if this represents a meaningful exploration opportunity.
        """
        UNCERTAINTY_THRESHOLD = 0.7
        DIVERGENCE_THRESHOLD = 0.5
        SPARSITY_THRESHOLD = 0.4

        return (
            uncertainty > UNCERTAINTY_THRESHOLD or
            divergence > DIVERGENCE_THRESHOLD or
            sparsity > SPARSITY_THRESHOLD
        )
```

### 3.3 Curiosity Debt Tracker

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CuriosityDebt:
    container_id: str
    debt_score: float  # 0.0 = no debt, 1.0 = max debt
    age_days: int  # Days since last exploration
    importance_weight: float
    debt_velocity: float  # Rate of debt accumulation
    debt_history: List[Tuple[datetime, float]]

class CuriosityDebtTracker:
    """
    Track and quantify unexplored areas of user's ontology.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.debt_ledger = self.load_debt_ledger()

    def calculate_debt(self,
                       container_analysis: ContainerAnalysis,
                       ucnrr_gap: Dict) -> CuriosityDebt:
        """
        Calculate curiosity debt for a container.

        Debt accumulates over time for:
        - Empty containers (high importance)
        - Low-confidence containers
        - High-uncertainty distributions
        - Stale data (not explored recently)
        """
        # Base debt from emptiness
        emptiness_debt = (1.0 - container_analysis.fullness) * container_analysis.importance

        # Confidence debt
        confidence_debt = (1.0 - container_analysis.confidence) * 0.5

        # Uncertainty debt from UCN/RR
        uncertainty_debt = ucnrr_gap.get('uncertainty', 0) * 0.3

        # Time decay - debt increases with age
        age_debt = self.calculate_age_debt(container_analysis.last_explored)

        # Total debt
        total_debt = min(
            emptiness_debt + confidence_debt + uncertainty_debt + age_debt,
            1.0
        )

        # Calculate velocity (how fast debt is growing)
        velocity = self.calculate_debt_velocity(container_analysis.container_id)

        # Calculate age
        age_days = self.calculate_age_days(container_analysis.last_explored)

        return CuriosityDebt(
            container_id=container_analysis.container_id,
            debt_score=total_debt,
            age_days=age_days,
            importance_weight=container_analysis.importance,
            debt_velocity=velocity,
            debt_history=self.get_debt_history(container_analysis.container_id)
        )

    def calculate_age_debt(self, last_explored: Optional[datetime]) -> float:
        """
        Calculate debt contribution from staleness.

        Debt increases over time:
        - 0-7 days: 0.0
        - 7-30 days: 0.0-0.2
        - 30-90 days: 0.2-0.5
        - 90+ days: 0.5-0.8
        """
        if last_explored is None:
            return 0.8  # Never explored = high debt

        days_ago = (datetime.now() - last_explored).days

        if days_ago <= 7:
            return 0.0
        elif days_ago <= 30:
            return 0.2 * ((days_ago - 7) / 23)
        elif days_ago <= 90:
            return 0.2 + 0.3 * ((days_ago - 30) / 60)
        else:
            return min(0.5 + 0.3 * ((days_ago - 90) / 180), 0.8)

    def calculate_debt_velocity(self, container_id: str) -> float:
        """
        Calculate how fast debt is accumulating for this container.

        Uses historical debt scores to compute rate of change.
        """
        history = self.debt_ledger.get_history(container_id)

        if len(history) < 2:
            return 0.0

        # Get last two debt scores
        recent_debt = history[-1][1]
        previous_debt = history[-2][1]

        # Time difference in days
        time_diff = (history[-1][0] - history[-2][0]).days

        if time_diff == 0:
            return 0.0

        # Velocity = change in debt / time
        velocity = (recent_debt - previous_debt) / time_diff

        return velocity

    def update_debt_ledger(self, debts: List[CuriosityDebt]):
        """
        Record current debt scores for historical tracking.
        """
        timestamp = datetime.now()

        for debt in debts:
            self.debt_ledger.record(
                container_id=debt.container_id,
                timestamp=timestamp,
                debt_score=debt.debt_score
            )

        self.save_debt_ledger()

    def get_high_debt_containers(self, threshold: float = 0.6) -> List[CuriosityDebt]:
        """
        Get containers with high curiosity debt.
        """
        all_debts = self.get_all_debts()
        return [d for d in all_debts if d.debt_score >= threshold]

    def generate_debt_report(self) -> Dict:
        """
        Generate summary report of curiosity debt.
        """
        all_debts = self.get_all_debts()

        return {
            "total_containers": len(all_debts),
            "high_debt_count": len([d for d in all_debts if d.debt_score >= 0.6]),
            "average_debt": np.mean([d.debt_score for d in all_debts]),
            "highest_debt_containers": sorted(all_debts,
                                            key=lambda d: d.debt_score,
                                            reverse=True)[:10],
            "fastest_growing_debt": sorted(all_debts,
                                          key=lambda d: d.debt_velocity,
                                          reverse=True)[:10],
            "oldest_unexplored": sorted(all_debts,
                                       key=lambda d: d.age_days,
                                       reverse=True)[:10]
        }
```

### 3.4 Prioritization Engine

```python
from typing import List
from dataclasses import dataclass

@dataclass
class PrioritizedContainer:
    container_id: str
    priority_score: float
    reasons: List[str]
    optimal_timing: str  # "immediate", "soon", "later"
    conversation_strategy: str

class PrioritizationEngine:
    """
    Prioritize containers for exploration based on multiple factors.
    """

    def prioritize(self,
                   debts: List[CuriosityDebt],
                   user_context: Dict,
                   conversation_state: Dict) -> List[PrioritizedContainer]:
        """
        Rank containers for exploration.

        Factors:
        1. Curiosity debt score
        2. User context relevance
        3. Conversation flow naturalness
        4. Dependency prerequisites
        5. User engagement state
        """
        prioritized = []

        for debt in debts:
            # Base score from debt
            base_score = debt.debt_score * debt.importance_weight

            # Context relevance boost
            context_boost = self.calculate_context_relevance(
                debt.container_id, user_context
            )

            # Conversation flow fit
            flow_fit = self.calculate_flow_fit(
                debt.container_id, conversation_state
            )

            # Prerequisite check
            prerequisites_met = self.check_prerequisites(
                debt.container_id, user_context
            )

            # User engagement consideration
            engagement_factor = self.calculate_engagement_factor(
                conversation_state
            )

            # Calculate final priority
            if not prerequisites_met:
                priority_score = 0.0  # Can't explore yet
            else:
                priority_score = (
                    base_score * 0.4 +
                    context_boost * 0.3 +
                    flow_fit * 0.2 +
                    engagement_factor * 0.1
                )

            # Determine timing
            optimal_timing = self.determine_optimal_timing(
                priority_score, conversation_state
            )

            # Select conversation strategy
            strategy = self.select_conversation_strategy(
                debt.container_id, conversation_state
            )

            # Build reasoning
            reasons = self.build_reasoning(
                debt, context_boost, flow_fit, engagement_factor
            )

            prioritized.append(PrioritizedContainer(
                container_id=debt.container_id,
                priority_score=priority_score,
                reasons=reasons,
                optimal_timing=optimal_timing,
                conversation_strategy=strategy
            ))

        # Sort by priority
        prioritized.sort(key=lambda p: p.priority_score, reverse=True)

        return prioritized

    def calculate_context_relevance(self, container_id: str, user_context: Dict) -> float:
        """
        How relevant is this container to user's current life context?
        """
        container = load_container_info(container_id)

        # Extract namespace (e.g., "CareerDNA", "RelationshipDNA")
        namespace = container.namespace

        # Get user's current life priorities
        priorities = user_context.get('current_priorities', [])

        # Check if namespace aligns with priorities
        relevance = 0.0
        for priority in priorities:
            if self.namespace_matches_priority(namespace, priority):
                relevance += 0.3

        # Check temporal relevance (e.g., work questions during work hours)
        temporal_relevance = self.calculate_temporal_relevance(
            namespace, user_context
        )
        relevance += temporal_relevance

        return min(relevance, 1.0)

    def calculate_flow_fit(self, container_id: str, conversation_state: Dict) -> float:
        """
        How naturally does this fit into the current conversation?
        """
        container = load_container_info(container_id)

        # Get recent conversation topics
        recent_topics = conversation_state.get('recent_topics', [])

        # Check semantic similarity
        similarity_scores = [
            self.calculate_semantic_similarity(container, topic)
            for topic in recent_topics
        ]

        if similarity_scores:
            best_similarity = max(similarity_scores)
        else:
            best_similarity = 0.0

        # Consider conversation phase
        phase = conversation_state.get('phase', 'exploration')
        phase_bonus = {
            'greeting': 0.0,
            'exploration': 0.3,
            'deep_dive': 0.5,
            'reflection': 0.2,
            'closing': 0.0
        }.get(phase, 0.0)

        return min(best_similarity + phase_bonus, 1.0)

    def check_prerequisites(self, container_id: str, user_context: Dict) -> bool:
        """
        Check if prerequisite containers have been explored.

        Some containers depend on others being filled first.
        """
        container = load_container_info(container_id)

        if not container.prerequisites:
            return True

        # Check each prerequisite
        for prereq_id in container.prerequisites:
            prereq_data = user_context.get('container_data', {}).get(prereq_id)

            if not prereq_data or prereq_data.get('fullness', 0) < 0.3:
                return False  # Prerequisite not sufficiently explored

        return True

    def determine_optimal_timing(self, priority_score: float, conversation_state: Dict) -> str:
        """
        Determine when to explore this container.
        """
        # High priority + good flow = immediate
        if priority_score > 0.7:
            flow_fit = conversation_state.get('current_flow_fit', 0.0)
            if flow_fit > 0.6:
                return "immediate"
            else:
                return "soon"

        # Medium priority = soon
        elif priority_score > 0.4:
            return "soon"

        # Low priority = later
        else:
            return "later"

    def select_conversation_strategy(self, container_id: str, conversation_state: Dict) -> str:
        """
        Select how to explore this container conversationally.

        Strategies:
        - direct: Ask directly about the topic
        - anecdotal: Request a story or example
        - reflective: Ask user to reflect on related experience
        - comparative: Compare to something already known
        - hypothetical: Use hypothetical scenarios
        """
        container = load_container_info(container_id)

        # Consider container type
        if container.namespace in ["BeliefDNA", "ValueDNA"]:
            return "reflective"
        elif container.namespace in ["BehaviorDNA", "HabitDNA"]:
            return "anecdotal"
        elif container.namespace in ["GoalDNA", "AspirationDNA"]:
            return "hypothetical"
        else:
            return "direct"
```

---

## 4. Curiosity Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│            CURIOSITY ENGINE V3 COMPLETE FLOW                      │
└──────────────────────────────────────────────────────────────────┘

PHASE 1: ANALYSIS
═════════════════

User Ontology                    UCN/RR Distribution
      │                                  │
      ▼                                  ▼
┌─────────────┐                  ┌──────────────┐
│   Core      │                  │    UCN/RR    │
│  Analyzer   │                  │   Analyzer   │
└──────┬──────┘                  └──────┬───────┘
       │                                │
       │  List[ContainerAnalysis]       │  List[DistributionGap]
       │                                │
       └────────────┬───────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │   Curiosity      │
          │   Coordinator    │
          └────────┬─────────┘
                   │
                   │  Unified Curiosity Map
                   ▼

PHASE 2: DEBT TRACKING
═══════════════════════

          ┌──────────────────┐
          │  Curiosity Debt  │
          │     Tracker      │
          └────────┬─────────┘
                   │
                   │  For Each Container:
                   │  1. Calculate debt score
                   │  2. Track age
                   │  3. Compute velocity
                   │  4. Update ledger
                   │
                   ▼
          ┌──────────────────┐
          │  Debt Ledger     │
          │  (Historical)    │
          └────────┬─────────┘
                   │
                   │  List[CuriosityDebt]
                   ▼

PHASE 3: PRIORITIZATION
════════════════════════

          ┌──────────────────┐
          │  Prioritization  │
          │     Engine       │
          └────────┬─────────┘
                   │
                   │  Inputs:
                   │  • Debt scores
                   │  • User context
                   │  • Conversation state
                   │
                   │  Scoring:
                   │  ├─ Base (debt × importance)
                   │  ├─ Context relevance
                   │  ├─ Flow fit
                   │  └─ Engagement
                   │
                   ▼
          ┌──────────────────┐
          │  Ranked List     │
          │  with Timing &   │
          │  Strategy        │
          └────────┬─────────┘
                   │
                   │  List[PrioritizedContainer]
                   ▼

PHASE 4: QUESTION GENERATION
═════════════════════════════

          ┌──────────────────┐
          │   Question       │
          │   Generator      │
          └────────┬─────────┘
                   │
                   │  For Top N Containers:
                   │  1. Select strategy
                   │  2. Consider context
                   │  3. Generate questions
                   │  4. Ensure naturalness
                   │
                   ▼
          ┌──────────────────┐
          │  Question Bank   │
          │  with Metadata   │
          └────────┬─────────┘
                   │
                   │  List[GeneratedQuestion]
                   ▼

PHASE 5: HC INTEGRATION
════════════════════════

          ┌──────────────────┐
          │   Head Coach     │
          │   Conversation   │
          │   Manager        │
          └────────┬─────────┘
                   │
                   │  Decision:
                   │  • When to ask?
                   │  • How to weave in?
                   │  • Follow-up strategy?
                   │
                   ▼
     ┌─────────────────────────────┐
     │  Natural Conversation       │
     │                             │
     │  HC: "That's interesting... │
     │       Speaking of work-life │
     │       balance, how do you   │
     │       typically recharge?"  │
     │                             │
     │       [Exploring:           │
     │        RestorativeDNA       │
     │        via anecdotal]       │
     └──────────────┬──────────────┘
                    │
                    ▼
              User Response
                    │
                    ▼
     ┌─────────────────────────────┐
     │  Response Processing        │
     │  • Extract traits           │
     │  • Update containers        │
     │  • Reduce debt              │
     │  • Evaluate question quality│
     └──────────────┬──────────────┘
                    │
                    ▼
              Feedback Loop
                    │
                    └──────────────────┐
                                       │
                                       ▼
                            ┌──────────────────┐
                            │  Learning        │
                            │  Feedback Loop   │
                            └──────────────────┘
                                       │
                                       │  Updates:
                                       │  • Question quality metrics
                                       │  • Strategy effectiveness
                                       │  • Timing optimization
                                       │
                                       └───────┐
                                               │
                                               ▼
                                    PHASE 1 (Next Cycle)
```

---

## 5. Interaction Sequence Diagram

```
┌──────┐         ┌──────┐        ┌────────┐        ┌──────┐
│  HC  │         │ Core │        │ UCN/RR │        │ User │
└───┬──┘         └───┬──┘        └───┬────┘        └───┬──┘
    │                │               │                 │
    │ 1. Request     │               │                 │
    │    Curiosity   │               │                 │
    │───────────────>│               │                 │
    │                │               │                 │
    │                │ 2. Analyze    │                 │
    │                │    Ontology   │                 │
    │                │               │                 │
    │                │ 3. Request    │                 │
    │                │    UCN/RR Gap │                 │
    │                │──────────────>│                 │
    │                │               │                 │
    │                │ 4. Return     │                 │
    │                │    Gaps       │                 │
    │                │<──────────────│                 │
    │                │               │                 │
    │ 5. Return      │               │                 │
    │    Prioritized │               │                 │
    │    Questions   │               │                 │
    │<───────────────│               │                 │
    │                │               │                 │
    │ 6. Weave       │               │                 │
    │    Question    │               │                 │
    │    into        │               │                 │
    │    Dialogue    │               │                 │
    │                │               │                 │
    │ 7. Ask User    │               │                 │
    │────────────────┴───────────────┴────────────────>│
    │                                                  │
    │ 8. User Response                                 │
    │<─────────────────────────────────────────────────│
    │                │               │                 │
    │ 9. Extract     │               │                 │
    │    Data        │               │                 │
    │───────────────>│               │                 │
    │                │               │                 │
    │                │ 10. Update    │                 │
    │                │     Container │                 │
    │                │               │                 │
    │                │ 11. Update    │                 │
    │                │     UCN/RR    │                 │
    │                │──────────────>│                 │
    │                │               │                 │
    │ 12. Debt       │               │                 │
    │     Reduced    │               │                 │
    │<───────────────│               │                 │
    │                │               │                 │
    │ 13. Continue   │               │                 │
    │     or New     │               │                 │
    │     Question   │               │                 │
    │                │               │                 │
```

---

## 6. Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Implement Core Analyzer
- [ ] Build UCN/RR Analyzer
- [ ] Create Curiosity Coordinator
- [ ] Design debt ledger schema

### Phase 2: Debt Tracking (Week 3)
- [ ] Implement Curiosity Debt Tracker
- [ ] Build debt calculation logic
- [ ] Create historical tracking
- [ ] Add velocity computation

### Phase 3: Prioritization (Week 4)
- [ ] Build Prioritization Engine
- [ ] Implement context relevance scoring
- [ ] Add conversation flow fitting
- [ ] Create prerequisite checking

### Phase 4: Question Generation (Week 5)
- [ ] Design question templates
- [ ] Implement strategy-based generation
- [ ] Add context-aware phrasing
- [ ] Build question quality scoring

### Phase 5: HC Integration (Week 6)
- [ ] Integrate with HC orchestrator
- [ ] Add conversation flow management
- [ ] Implement response processing
- [ ] Build feedback loop

### Phase 6: Testing & Refinement (Week 7-8)
- [ ] End-to-end testing
- [ ] Question quality evaluation
- [ ] User experience testing
- [ ] Performance optimization

---

## 7. Success Metrics

1. **Debt Reduction Rate**: Decrease in average curiosity debt over time
2. **Container Fullness**: Increase in average container fullness
3. **Question Effectiveness**: % of questions that yield useful data
4. **User Engagement**: User response rate to curiosity questions
5. **Naturalness Score**: HC ratings of conversation flow
6. **Coverage**: % of ontology explored over time

---

## Summary

Curiosity Engine v3 transforms exploration from reactive (user volunteers information) to proactive (system identifies and fills gaps). By combining multiple intelligence sources, tracking debt, and seamlessly integrating with HC conversations, we ensure comprehensive, natural, and effective user understanding.

**Next Steps:**
1. Begin Phase 1 implementation
2. Create curiosity_engine_v3.py module
3. Design API interfaces
4. Build initial question templates
5. Integrate with existing HC workflows
