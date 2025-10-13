# Evergreen API Contracts

**Version:** 1.0
**Date:** 2025-10-12
**Purpose:** Define all API contracts between Evergreen components

---

## Overview

This document specifies the interfaces, data formats, and contracts between all Evergreen components to ensure clean integration and maintainability.

---

## 1. Data Ingestion Pipeline APIs

### 1.1 PreProcessor API

#### Input Format

```python
{
    "source_type": "CHAT" | "FILE" | "THIRD_PARTY" | "BEHAVIOR",
    "data": Any,  # Raw data in any format
    "user_id": str,
    "metadata": {
        "timestamp": str,  # ISO 8601
        "session_id": Optional[str],
        "origin": str  # e.g., "head_coach", "web_upload"
    }
}
```

#### Output Format (NormalizedData)

```python
{
    "source_type": "CHAT" | "FILE" | "THIRD_PARTY" | "BEHAVIOR",
    "timestamp": str,  # ISO 8601
    "content": {
        "text": Optional[str],
        "structured": Optional[Dict],
        "binary": Optional[bytes]
    },
    "metadata": {
        "original_format": str,
        "size_bytes": int,
        "encoding": str,
        "extracted_fields": Dict
    },
    "sensitivity_hint": int  # 1-10
}
```

#### Method Signature

```python
def process(raw_data: Dict[str, Any]) -> NormalizedData:
    """
    Normalize raw data into standard format.

    Args:
        raw_data: Raw input data with source_type, data, user_id, metadata

    Returns:
        NormalizedData: Standardized data object

    Raises:
        ValueError: If data format cannot be processed
        TypeError: If required fields missing
    """
```

---

### 1.2 Comfort Index Filter API

#### Input Format

```python
# Takes NormalizedData from PreProcessor
NormalizedData (see 1.1 Output)
```

#### Output Format (FilterResult)

```python
{
    "action": "PASS" | "REVIEW" | "BLOCK" | "ANONYMIZE",
    "reason": str,
    "modified_data": Optional[NormalizedData],  # If anonymized
    "requires_user_consent": bool,
    "suggested_sensitivity": Optional[int],
    "detected_issues": List[str],  # ["pii_email", "sensitive_topic_health"]
    "filter_version": str
}
```

#### Method Signature

```python
def apply_filter(data: NormalizedData) -> FilterResult:
    """
    Apply comfort index filter to data.

    Args:
        data: Normalized data to filter

    Returns:
        FilterResult: Filter decision and details

    Raises:
        ConfigError: If user comfort config invalid
    """
```

---

### 1.3 Provenance Tagger API

#### Input Format

```python
{
    "data_id": str,
    "source": {
        "type": str,
        "origin": str,
        "timestamp": str,
        "user_id": str
    },
    "chain_events": List[{
        "stage": str,
        "timestamp": str,
        "processor": str,
        "result": str
    }]
}
```

#### Output Format

```python
{
    "provenance_id": str,  # Format: prov_YYYYMMDD_hash
    "data_id": str,
    "source": Dict,
    "chain_of_custody": List[Dict],
    "user_consent": {
        "implicit": bool,
        "comfort_level": int,
        "reviewed_by_user": bool,
        "consent_timestamp": str
    },
    "data_classification": {
        "sensitivity": int,
        "categories": List[str],
        "retention_policy": str
    }
}
```

---

### 1.4 Core Storage API

#### Store Method

```python
def store(user_id: str,
          data: NormalizedData,
          provenance: Dict) -> str:
    """
    Store data with provenance.

    Args:
        user_id: User identifier
        data: Normalized data to store
        provenance: Provenance record

    Returns:
        str: Unique data_id

    Raises:
        StorageError: If storage fails
        PermissionError: If user directory inaccessible
    """
```

#### Retrieve Method

```python
def retrieve(user_id: str, data_id: str) -> Optional[Dict]:
    """
    Retrieve stored data.

    Args:
        user_id: User identifier
        data_id: Data identifier

    Returns:
        Dict with 'data', 'provenance', 'stored_at' or None

    Raises:
        PermissionError: If user lacks access
    """
```

#### Query Method

```python
def query(user_id: str,
          filters: Dict,
          limit: int = 100) -> List[Dict]:
    """
    Query stored data.

    Args:
        user_id: User identifier
        filters: {
            "source_type": Optional[str],
            "date_range": Optional[Tuple[str, str]],
            "containers": Optional[List[str]],
            "min_confidence": Optional[float]
        }
        limit: Max results

    Returns:
        List of matching data entries
    """
```

---

### 1.5 Enrichment Engine API

#### Input Format

```python
{
    "data": NormalizedData,
    "user_id": str,
    "user_ontology": Dict,  # Current user ontology
    "options": {
        "deep_analysis": bool,
        "relationship_discovery": bool
    }
}
```

#### Output Format

```python
{
    "mapped_containers": [
        {
            "container_id": str,
            "confidence": float,
            "evidence": List[str]
        }
    ],
    "extracted_traits": {
        "trait_name": {
            "value": Any,
            "confidence": float,
            "evidence": str
        }
    },
    "relationships": [
        {
            "type": "supports" | "contradicts" | "refines",
            "target": str,
            "strength": float
        }
    ],
    "patterns_detected": List[str],
    "enrichment_timestamp": str
}
```

---

### 1.6 Distribution Layer API

#### Publish Method

```python
async def publish(topic: str, payload: Dict) -> bool:
    """
    Publish event to event bus.

    Args:
        topic: Event topic (e.g., "data_ingested")
        payload: Event data

    Returns:
        bool: Success status
    """
```

#### Subscribe Method

```python
async def subscribe(topic: str, callback: Callable) -> str:
    """
    Subscribe to event topic.

    Args:
        topic: Event topic to subscribe to
        callback: Async function to call on events

    Returns:
        str: Subscription ID for unsubscribe
    """
```

---

## 2. Curiosity Engine v3 APIs

### 2.1 Core Analyzer API

#### Analyze Method

```python
def analyze_user_ontology(user_id: str) -> List[ContainerAnalysis]:
    """
    Analyze user ontology for gaps.

    Args:
        user_id: User identifier

    Returns:
        List of ContainerAnalysis objects with:
        - container_id
        - namespace
        - fullness (0.0-1.0)
        - confidence
        - importance
        - last_explored
        - related_containers
    """
```

---

### 2.2 Curiosity Debt Tracker API

#### Calculate Debt Method

```python
def calculate_debt(container_analysis: ContainerAnalysis,
                  ucnrr_gap: Dict) -> CuriosityDebt:
    """
    Calculate curiosity debt for container.

    Args:
        container_analysis: Analysis from CoreAnalyzer
        ucnrr_gap: Gap analysis from UCNRRAnalyzer

    Returns:
        CuriosityDebt with:
        - container_id
        - debt_score (0.0-1.0)
        - age_days
        - importance_weight
        - debt_velocity
        - debt_history
    """
```

---

### 2.3 Prioritization Engine API

#### Prioritize Method

```python
def prioritize(debts: List[CuriosityDebt],
              user_context: Dict,
              conversation_state: Dict) -> List[PrioritizedContainer]:
    """
    Prioritize containers for exploration.

    Args:
        debts: List of curiosity debts
        user_context: {
            "current_priorities": List[str],
            "life_context": Dict,
            "container_data": Dict
        }
        conversation_state: {
            "recent_topics": List[str],
            "phase": str,
            "engagement_level": str
        }

    Returns:
        List of PrioritizedContainer with:
        - container_id
        - priority_score
        - reasons
        - optimal_timing
        - conversation_strategy
    """
```

---

### 2.4 Question Generator API

#### Generate Method

```python
async def generate_questions(container: PrioritizedContainer,
                            approach: str,
                            count: int = 3) -> List[GeneratedQuestion]:
    """
    Generate curiosity questions.

    Args:
        container: Prioritized container to explore
        approach: "direct" | "anecdotal" | "reflective" | "comparative" | "hypothetical"
        count: Number of questions

    Returns:
        List of GeneratedQuestion with:
        - question_text
        - container_id
        - approach
        - expected_data_types
        - follow_up_suggestions
    """
```

---

### 2.5 Dynamic Reprioritizer API

#### Handle Trigger Method

```python
async def handle_trigger(event: ReprioritizationEvent) -> Dict:
    """
    Handle reprioritization trigger.

    Args:
        event: {
            "trigger": "USER_CONTEXT_CHANGE" | "CONVERSATION_SHIFT" | ...,
            "timestamp": str,
            "context": Dict,
            "priority": "immediate" | "high" | "normal" | "low"
        }

    Returns:
        {
            "priorities_updated": List[str],  # Container IDs
            "boost_applied": Dict[str, float],
            "reason": str
        }
    """
```

---

## 3. Empathy & Bonding APIs

### 3.1 Empathy Engine API

#### Analyze User State Method

```python
async def analyze_user_state(conversation_context: Dict) -> EmpathyModel:
    """
    Analyze user's emotional and cognitive state.

    Args:
        conversation_context: {
            "current_message": str,
            "recent_messages": List[str],
            "session_metadata": Dict,
            "behavioral_signals": Dict
        }

    Returns:
        EmpathyModel with:
        - emotional_state: EmotionalState enum
        - intensity: float (0.0-1.0)
        - cognitive_understanding: Dict
        - needs_assessment: List[str]
        - appropriate_responses: List[str]
        - confidence: float
    """
```

---

### 3.2 Motivation Engine API

#### Generate Motivational Message Method

```python
async def generate_motivational_message(user_id: str,
                                       goal: str,
                                       context: Dict) -> str:
    """
    Generate personalized motivational message.

    Args:
        user_id: User identifier
        goal: Goal to motivate toward
        context: {
            "emotional_state": str,
            "recent_progress": Dict,
            "obstacles": List[str]
        }

    Returns:
        str: Motivational message text
    """
```

---

### 3.3 Bonding Monitor API

#### Calculate Metrics Method

```python
def calculate_bonding_metrics(user_id: str) -> BondingMetrics:
    """
    Calculate relationship health metrics.

    Args:
        user_id: User identifier

    Returns:
        BondingMetrics with:
        - trust_score: float (0.0-1.0)
        - vulnerability_sharing: float
        - recommendation_following: float
        - session_frequency: float
        - session_depth: float
        - topic_breadth: float
        - positive_sentiment: float
        - emotional_openness: float
        - affection_expressions: int
        - goal_progress: float
        - self_awareness_growth: float
        - life_satisfaction: float
        - consistency_score: float
        - retention_probability: float
        - relationship_stage: str
    """
```

---

## 4. Tools APIs

### 4.1 Financial Planner API

#### Track Expense

```python
async def track_expense(amount: float,
                       category: str,
                       description: str,
                       date: datetime) -> Dict:
    """
    Track financial expense.

    Returns:
        {
            "transaction": Dict,
            "budget_status": Dict,
            "insights": List[FinancialInsight]
        }
    """
```

#### Set Financial Goal

```python
async def set_financial_goal(name: str,
                            target_amount: float,
                            target_date: datetime,
                            category: str) -> Dict:
    """
    Set financial goal.

    Returns:
        {
            "goal": FinancialGoal,
            "savings_plan": Dict,
            "feasibility_score": float
        }
    """
```

---

### 4.2 Mood Tracker API

#### Log Mood

```python
async def log_mood(mood_level: MoodLevel,
                  emotions: List[str],
                  context: Dict,
                  notes: Optional[str] = None) -> Dict:
    """
    Log mood entry.

    Returns:
        {
            "entry": MoodEntry,
            "new_patterns": List[MoodPattern],
            "insights": List[str],
            "suggestions": List[str]
        }
    """
```

---

### 4.3 Goal Engine API

#### Create Goal

```python
async def create_goal(title: str,
                     description: str,
                     category: str,
                     target_date: datetime,
                     priority: str = "medium") -> Dict:
    """
    Create new goal with AI-generated milestones.

    Returns:
        {
            "goal": Goal,
            "suggested_milestones": List[Dict],
            "feasibility_score": float,
            "recommendations": List[str]
        }
    """
```

#### Track Progress

```python
def track_progress(goal_id: str, progress_update: Dict) -> Dict:
    """
    Track goal progress.

    Args:
        progress_update: {
            "percentage": float,
            "notes": str,
            "milestone_completed": Optional[str]
        }

    Returns:
        {
            "goal": Goal,
            "progress_change": float,
            "completed_milestones": List[str],
            "message": str,
            "on_track": bool
        }
    """
```

---

### 4.4 Habit Loop Designer API

#### Design Habit

```python
async def design_habit(desired_behavior: str,
                      frequency: Dict) -> Dict:
    """
    Design habit using behavioral science.

    Args:
        frequency: {
            "type": "daily" | "weekly" | "custom",
            "count": int
        }

    Returns:
        {
            "habit": Habit,
            "implementation_plan": Dict,
            "success_predictors": List[str],
            "tips": List[str]
        }
    """
```

#### Log Completion

```python
def log_completion(habit_id: str,
                  completed: bool,
                  notes: Optional[str] = None) -> Dict:
    """
    Log habit completion.

    Returns:
        {
            "habit": Habit,
            "feedback": str,
            "streak_status": str,
            "next_milestone": int
        }
    """
```

---

### 4.5 Tool Manager API

#### Invoke Tool

```python
async def invoke_tool(tool_id: str,
                     action: str,
                     params: Dict) -> Dict:
    """
    Invoke tool action.

    Args:
        tool_id: "financial_planner" | "mood_tracker" | "goal_engine" | "habit_designer"
        action: Tool-specific action name
        params: Action parameters

    Returns:
        Tool-specific result

    Raises:
        ToolNotFoundError: If tool unavailable
        PermissionError: If user lacks access
    """
```

#### Get Tool Recommendations

```python
async def generate_tool_recommendations(context: Dict) -> List[Dict]:
    """
    Recommend tools based on context.

    Returns:
        List of recommendations with:
        - tool_id
        - name
        - reason
        - suggested_action
        - relevance_score
    """
```

---

## 5. HC Orchestrator Integration APIs

### 5.1 Ingestion Trigger

```python
async def trigger_ingestion(user_id: str,
                           observation: Dict) -> Dict:
    """
    HC triggers data ingestion.

    Args:
        observation: {
            "type": "chat" | "behavioral" | "emotional",
            "content": Any,
            "context": Dict
        }

    Returns:
        {
            "status": "ingested" | "needs_review" | "blocked",
            "result": Dict
        }
    """
```

### 5.2 Curiosity Request

```python
async def request_curiosity_questions(user_id: str,
                                     context: Dict,
                                     count: int = 3) -> List[str]:
    """
    Request curiosity questions for conversation.

    Returns:
        List of natural questions to explore
    """
```

### 5.3 Empathy Analysis

```python
async def analyze_empathy(user_id: str,
                         conversation_context: Dict) -> EmpathyModel:
    """
    Request empathy analysis.

    Returns:
        EmpathyModel with state and recommendations
    """
```

### 5.4 Tool Suggestion

```python
async def suggest_tools(user_id: str, context: Dict) -> Optional[Dict]:
    """
    Get tool suggestion for conversation.

    Returns:
        {
            "message": str,  # Natural integration message
            "tool_offer": Dict,
            "type": "tool_suggestion"
        } or None
    """
```

---

## 6. Error Handling

### Standard Error Response

```python
{
    "error": {
        "type": str,  # Error type
        "message": str,  # Human-readable message
        "code": str,  # Machine-readable error code
        "details": Dict,  # Additional context
        "timestamp": str,
        "request_id": str
    }
}
```

### Error Types

- `ValidationError`: Invalid input data
- `PermissionError`: Insufficient permissions
- `StorageError`: Storage operation failed
- `ConfigError`: Configuration invalid
- `ProcessingError`: Processing failed
- `TimeoutError`: Operation timed out

---

## 7. Versioning

All APIs include version in response:

```python
{
    "api_version": "1.0",
    "component": "curiosity_engine",
    "data": { ... }
}
```

---

## 8. Authentication & Authorization

### User Context

All APIs that operate on user data require user context:

```python
{
    "user_id": str,
    "session_id": Optional[str],
    "permissions": List[str],
    "auth_token": Optional[str]
}
```

---

## Summary

These API contracts ensure:
- **Type Safety**: Clear input/output types
- **Error Handling**: Standard error responses
- **Versioning**: API version tracking
- **Documentation**: Complete method signatures
- **Testability**: Clear contracts for mocking

All implementations must adhere to these contracts to maintain system integrity.

---

**Status:** Complete API specification for all Evergreen components
**Version:** 1.0
**Last Updated:** 2025-10-12
