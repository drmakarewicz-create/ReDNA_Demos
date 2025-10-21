# Phase 8 Stage 3: Update Rules — Technical Addendum

**Version**: 1.1 (Addendum to Phase8_Spec_v1.0.md)
**Date**: 2025-10-19
**Status**: SPECIFICATION

---

## Overview

Stage 3 connects the belief graph module to the existing trait promotion pipeline. Every trait promotion must update the user's belief graph with provenance tracking, ensuring full traceability from raw observations to promoted beliefs.

---

## 1. Belief Graph Update Invariants

### Core Invariant: Promotion → Graph Update

**RULE**: Every trait promotion MUST produce exactly:
1. **One observation node** (raw evidence)
2. **One trait belief node** (promoted trait) OR update to existing trait belief node
3. **One evidence_for edge** (linking observation → trait belief)

**Enforcement**: The promotion pipeline must call `on_trait_promotion()` synchronously before returning success to the caller.

### Provenance Rules

#### Observation Node Requirements
```python
{
  "node_type": "observation",
  "observation_text": str,       # Original raw text (e.g., "I wake up at 6am every day")
  "observation_source": str,      # Source of evidence ("chat", "photo_analysis", "inference", "onboarding")
  "observation_ts": ISO8601,      # Timestamp when observation was captured
  "metadata": {
    "extraction_context": str,    # Optional: LLM extraction rationale
    "raw_message_id": str,        # Optional: Link to chat message
    "session_id": str             # Optional: User session context
  }
}
```

#### Trait Belief Node Requirements
```python
{
  "node_type": "trait_belief",
  "trait_id": str,                # Canonical trait ID (e.g., "PaDNA.Chronotype")
  "value": Any,                   # Promoted value ("Morning Lark", 175, {"min": 5, "max": 7})
  "rr_score": float,              # RR score from UCNRR (0-1000)
  "ucn": {                        # UCN scores from UCNRR
    "u": float,                   # Uncertainty [0, 1]
    "c": float,                   # Curiosity [0, 1]
    "n": float                    # Necessity [0, 1]
  },
  "last_updated": ISO8601         # Timestamp of last promotion (versioning)
}
```

#### Evidence Edge Requirements
```python
{
  "edge_type": "evidence_for",
  "from_node": str,               # observation node_id
  "to_node": str,                 # trait_belief node_id
  "weight": float,                # RR score normalized to [0, 1]: rr_score / 1000
  "confidence": float,            # UCN 'c' score [0, 1]
  "source": "promotion",          # Fixed value for promotion-generated edges
  "why_card_id": str,             # Optional: Link to Why-Card if generated
  "metadata": {
    "promotion_ts": ISO8601,      # Timestamp of promotion
    "ucnrr_endpoint": str,        # Optional: UCNRR endpoint used
    "llm_model": str              # Optional: LLM model used for extraction
  }
}
```

### Schema Guardrails

#### No Self-Loops for Evidence Edges
```python
# REJECT with error:
{
  "edge_type": "evidence_for",
  "from_node": "bn_abc123",
  "to_node": "bn_abc123"  # ❌ INVALID: same node
}

# Error response:
{
  "error": "INVALID_EDGE",
  "message": "evidence_for edges cannot be self-loops",
  "edge": {...}
}
```

#### Observation → Trait Belief Only
```python
# REJECT with error:
{
  "edge_type": "evidence_for",
  "from_node": "bn_trait_abc",      # ❌ INVALID: from_node is trait_belief
  "to_node": "bn_obs_xyz"
}

# Error response:
{
  "error": "INVALID_EDGE_DIRECTION",
  "message": "evidence_for edges must go from observation → trait_belief",
  "from_node_type": "trait_belief",  # Expected: "observation"
  "to_node_type": "observation"
}
```

#### Required Fields Validation
```python
# REJECT if missing required fields:
observation_node_required = ["observation_text", "observation_source", "observation_ts"]
trait_belief_required = ["trait_id", "value", "rr_score", "ucn"]
edge_required = ["from_node", "to_node", "weight", "confidence"]

# Error response:
{
  "error": "MISSING_REQUIRED_FIELDS",
  "message": "Node missing required fields",
  "missing_fields": ["observation_text", "observation_source"],
  "node": {...}
}
```

---

## 2. ID Resolution & Node Reuse

### Helper Function: `get_or_create_user_trait_node()`

**Purpose**: Reuse trait belief nodes across multiple promotions for the same trait.

**Signature**:
```python
def get_or_create_user_trait_node(
    graph: BeliefGraph,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float]
) -> Tuple[BeliefNode, bool]:
    """
    Get existing trait belief node or create new one.

    Returns:
        (node, is_new) where is_new=True if node was created

    Rules:
    - If node exists with same trait_id AND same value:
        - Update rr_score, ucn, last_updated
        - Return (existing_node, False)
    - If node exists with same trait_id BUT different value:
        - Create new node (value changed)
        - Add contradicts edge from old → new
        - Return (new_node, True)
    - If node doesn't exist:
        - Create new node
        - Return (new_node, True)
    """
```

**Implementation Logic**:
```python
# 1. Find existing trait belief node with same trait_id
existing = None
for node in graph.nodes:
    if node.node_type == "trait_belief" and node.trait_id == trait_id:
        existing = node
        break

# 2. Check if value matches
if existing:
    if existing.value == value:
        # CASE A: Same trait, same value → UPDATE
        existing.rr_score = rr_score
        existing.ucn = ucn
        existing.last_updated = datetime.utcnow()
        return (existing, False)
    else:
        # CASE B: Same trait, different value → CONTRADICTION
        new_node = BeliefNode(
            node_type="trait_belief",
            trait_id=trait_id,
            value=value,
            rr_score=rr_score,
            ucn=ucn
        )

        # Add contradiction edge (handled separately)
        # on_contradiction_detected(user_id, existing.node_id, new_node.node_id)

        return (new_node, True)
else:
    # CASE C: New trait → CREATE
    new_node = BeliefNode(
        node_type="trait_belief",
        trait_id=trait_id,
        value=value,
        rr_score=rr_score,
        ucn=ucn
    )
    return (new_node, True)
```

### Node Versioning Strategy

**Approach**: Update `last_updated` timestamp on existing nodes rather than creating duplicates.

**Rationale**:
- Avoids graph explosion with duplicate trait belief nodes
- Maintains single source of truth for each trait
- Evidence edges from multiple observations point to same trait node
- Temporal evolution tracked via `last_updated` + edge timestamps

**Example**:
```
User says "I wake up at 6am" → Observation1 → TraitBelief(Chronotype=Morning, rr=700)
User says "I love mornings" → Observation2 → TraitBelief(Chronotype=Morning, rr=850)
                                              ^
                                              Same node, updated rr_score
```

---

## 3. Integration with Promotion Pipeline

### Hook Point: `on_trait_promotion()`

**Location**: Called from existing promotion logic in `ReDNACoreDemo/core/redna_core.py` or `ReDNACoreDemo/core/ucn_rr_service.py`

**Signature**:
```python
def on_trait_promotion(
    user_id: str,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float],
    observation_text: str,
    observation_source: str,
    observation_ts: Optional[datetime] = None,
    why_card_text: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update user's belief graph after trait promotion.

    Returns:
        {
            "status": "ok",
            "observation_node_id": str,
            "trait_node_id": str,
            "edge_id": str,
            "is_new_trait": bool,
            "contradiction_detected": bool
        }
    """
```

**Implementation**:
```python
from .graph.storage import get_graph_storage
from .graph.schemas import BeliefNode, BeliefEdge
from datetime import datetime

def on_trait_promotion(
    user_id: str,
    trait_id: str,
    value: Any,
    rr_score: float,
    ucn: Dict[str, float],
    observation_text: str,
    observation_source: str,
    observation_ts: Optional[datetime] = None,
    why_card_text: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    storage = get_graph_storage()
    graph = storage.load_user_graph(user_id)

    # 1. Create observation node
    obs_node = BeliefNode(
        node_type="observation",
        observation_text=observation_text,
        observation_source=observation_source,
        observation_ts=observation_ts or datetime.utcnow(),
        metadata=metadata or {}
    )

    # 2. Get or create trait belief node
    trait_node, is_new = get_or_create_user_trait_node(
        graph, trait_id, value, rr_score, ucn
    )

    # 3. Create evidence edge
    edge = BeliefEdge(
        edge_type="evidence_for",
        from_node=obs_node.node_id,
        to_node=trait_node.node_id,
        weight=rr_score / 1000.0,  # Normalize to [0, 1]
        confidence=ucn.get("c", 0.5),
        source="promotion",
        why_card_id=None,  # Set later if Why-Card generated
        metadata={
            "promotion_ts": datetime.utcnow().isoformat(),
            "why_card_text": why_card_text
        }
    )

    # 4. Validate (no self-loops)
    if edge.from_node == edge.to_node:
        raise ValueError("evidence_for edges cannot be self-loops")

    # 5. Append to storage
    nodes_to_add = [obs_node]
    if is_new:
        nodes_to_add.append(trait_node)

    storage.append_user_graph_update(
        user_id=user_id,
        nodes=nodes_to_add,
        edges=[edge]
    )

    # 6. Check for high uncertainty → trigger curiosity
    if ucn.get("u", 0) > 0.7:
        on_high_uncertainty(user_id, trait_id, ucn)

    return {
        "status": "ok",
        "observation_node_id": obs_node.node_id,
        "trait_node_id": trait_node.node_id,
        "edge_id": edge.edge_id,
        "is_new_trait": is_new,
        "contradiction_detected": False  # Stage 3: stub, Stage 4: implement
    }
```

---

## 4. Curiosity Trigger (Stage 3 Stub)

### Hook Point: `on_high_uncertainty()`

**Purpose**: Enqueue curiosity items when trait uncertainty is high.

**Signature**:
```python
def on_high_uncertainty(
    user_id: str,
    trait_id: str,
    ucn: Dict[str, float]
) -> None:
    """
    Trigger curiosity queue update for high-uncertainty traits.

    Stage 3: Simple threshold-based enqueue
    Stage 4: LLM-powered question selection using graph context
    """
```

**Stage 3 Implementation** (Simple Stub):
```python
from .curiosity import store as curiosity_store
from .curiosity.models import CuriosityItem

def on_high_uncertainty(
    user_id: str,
    trait_id: str,
    ucn: Dict[str, float]
) -> None:
    """Stage 3: Threshold-based curiosity trigger."""

    uncertainty = ucn.get("u", 0)
    curiosity = ucn.get("c", 0)

    # Only trigger if uncertainty is high AND curiosity is non-zero
    if uncertainty > 0.7 and curiosity > 0.3:

        # Create simple curiosity item (Stage 4 will use graph context)
        item = CuriosityItem(
            user_id=user_id,
            trait_id=trait_id,
            question_text=f"[STUB] Tell me more about {trait_id}",
            priority=curiosity,
            metadata={
                "ucn": ucn,
                "source": "graph_uncertainty",
                "stage": 3
            }
        )

        # Enqueue (integrates with existing curiosity queue)
        curiosity_store.enqueue_item(user_id, item)

        logger.info(f"Enqueued curiosity item for {user_id}/{trait_id} (u={uncertainty:.2f})")
```

**Stage 4 Enhancement**:
- Replace stub question with LLM-generated graph-aware question
- Use ontology neighbors to suggest related traits
- Generate question that reduces uncertainty based on edge relationships

**Integration Point**:
- `curiosity_store.enqueue_item()` must exist in `ReDNACoreDemo/core/curiosity/store.py`
- If not, create simple wrapper around existing curiosity queue

---

## 5. Example: Chronotype Promotion Flow

### Input: Chat Message
```json
{
  "user_id": "alice",
  "text": "I wake up at 6am every morning naturally, I love being productive early",
  "source": "chat",
  "timestamp": "2025-10-19T08:30:00Z"
}
```

### Step 1: Trait Extraction (Existing Pipeline)
```python
# Existing LLM extraction yields:
extracted_trait = {
  "trait_id": "PaDNA.Chronotype",
  "value": "Morning Lark",
  "confidence": 0.85
}
```

### Step 2: UCNRR Scoring (Existing Pipeline)
```python
# UCNRR scores the trait:
ucn_response = {
  "rr_score": 720,
  "ucn": {
    "u": 0.3,   # Low uncertainty (clear evidence)
    "c": 0.6,   # Moderate curiosity (could ask more)
    "n": 0.7    # High necessity (important trait)
  }
}
```

### Step 3: Promotion (NEW: Call on_trait_promotion)
```python
# Existing promotion logic calls:
result = on_trait_promotion(
    user_id="alice",
    trait_id="PaDNA.Chronotype",
    value="Morning Lark",
    rr_score=720,
    ucn={"u": 0.3, "c": 0.6, "n": 0.7},
    observation_text="I wake up at 6am every morning naturally, I love being productive early",
    observation_source="chat",
    observation_ts=datetime.fromisoformat("2025-10-19T08:30:00Z"),
    why_card_text="Based on your statement about waking early naturally and loving morning productivity"
)
```

### Step 4: Graph Update (Executed by on_trait_promotion)

#### 4a. Create Observation Node
```json
{
  "node_id": "bn_obs_a1b2c3",
  "node_type": "observation",
  "observation_text": "I wake up at 6am every morning naturally, I love being productive early",
  "observation_source": "chat",
  "observation_ts": "2025-10-19T08:30:00Z",
  "created_at": "2025-10-19T08:30:01.234Z",
  "metadata": {
    "extraction_context": "User explicitly stated morning routine"
  }
}
```

#### 4b. Create/Update Trait Belief Node
```json
{
  "node_id": "bn_trait_d4e5f6",
  "node_type": "trait_belief",
  "trait_id": "PaDNA.Chronotype",
  "value": "Morning Lark",
  "rr_score": 720.0,
  "ucn": {
    "u": 0.3,
    "c": 0.6,
    "n": 0.7
  },
  "created_at": "2025-10-19T08:30:01.235Z",
  "last_updated": "2025-10-19T08:30:01.235Z",
  "metadata": {}
}
```

#### 4c. Create Evidence Edge
```json
{
  "edge_id": "be_edge_g7h8i9",
  "edge_type": "evidence_for",
  "from_node": "bn_obs_a1b2c3",
  "to_node": "bn_trait_d4e5f6",
  "weight": 0.72,          // rr_score / 1000
  "confidence": 0.6,       // ucn.c
  "source": "promotion",
  "why_card_id": null,
  "created_at": "2025-10-19T08:30:01.236Z",
  "metadata": {
    "promotion_ts": "2025-10-19T08:30:01.236Z",
    "why_card_text": "Based on your statement about waking early naturally and loving morning productivity"
  }
}
```

### Step 5: JSONL Append (Storage Layer)
```jsonl
{"type": "add_node", "node": {"node_id": "bn_obs_a1b2c3", "node_type": "observation", ...}}
{"type": "add_node", "node": {"node_id": "bn_trait_d4e5f6", "node_type": "trait_belief", ...}}
{"type": "add_edge", "edge": {"edge_id": "be_edge_g7h8i9", "edge_type": "evidence_for", ...}}
```

### Final Graph State (alice's belief graph)

**Nodes**: 2
- 1 observation node (`bn_obs_a1b2c3`)
- 1 trait belief node (`bn_trait_d4e5f6`)

**Edges**: 1
- 1 evidence_for edge (`be_edge_g7h8i9`: observation → trait)

**Visual Representation**:
```
[Observation: "I wake up at 6am..."]
         |
         | evidence_for (weight=0.72, confidence=0.6)
         ↓
[Trait Belief: PaDNA.Chronotype = "Morning Lark", rr=720]
```

### Step 6: Second Promotion (Same Trait, Same Value)

**Input**:
```json
{
  "user_id": "alice",
  "text": "I prefer morning workouts because I have more energy",
  "source": "chat",
  "timestamp": "2025-10-20T09:00:00Z"
}
```

**UCNRR Response**:
```json
{
  "trait_id": "PaDNA.Chronotype",
  "value": "Morning Lark",
  "rr_score": 850,
  "ucn": {"u": 0.2, "c": 0.5, "n": 0.7}
}
```

**Graph Update**:
```jsonl
{"type": "add_node", "node": {"node_id": "bn_obs_j1k2l3", "node_type": "observation", ...}}
{"type": "update_node", "node_id": "bn_trait_d4e5f6", "updates": {"rr_score": 850, "ucn": {...}, "last_updated": "2025-10-20T09:00:01Z"}}
{"type": "add_edge", "edge": {"edge_id": "be_edge_m4n5o6", "from_node": "bn_obs_j1k2l3", "to_node": "bn_trait_d4e5f6", ...}}
```

**Final Graph State**:
```
[Observation1: "I wake up at 6am..."]
         |
         | evidence_for (weight=0.72)
         ↓
[Trait Belief: PaDNA.Chronotype = "Morning Lark", rr=850] ← UPDATED
         ↑
         | evidence_for (weight=0.85)
         |
[Observation2: "I prefer morning workouts..."]
```

**Nodes**: 3 (2 observations, 1 trait belief - REUSED)
**Edges**: 2 (both pointing to same trait belief node)

---

## 6. Error Handling

### Validation Errors

**Invalid Edge Direction**:
```python
raise ValueError(
    f"evidence_for edges must go from observation → trait_belief, "
    f"got {from_node.node_type} → {to_node.node_type}"
)
```

**Self-Loop Detection**:
```python
if edge.from_node == edge.to_node:
    raise ValueError(
        f"evidence_for edges cannot be self-loops (node_id={edge.from_node})"
    )
```

**Missing Required Fields**:
```python
required = ["observation_text", "observation_source", "observation_ts"]
missing = [f for f in required if getattr(node, f, None) is None]
if missing:
    raise ValueError(
        f"Observation node missing required fields: {', '.join(missing)}"
    )
```

### Storage Failures

**JSONL Write Failure**:
```python
try:
    storage.append_user_graph_update(user_id, nodes=[...], edges=[...])
except IOError as e:
    logger.error(f"Failed to update graph for {user_id}: {e}")
    # Promotion continues but graph update failed
    # Return warning in response
    return {
        "status": "degraded",
        "warning": "Graph update failed, promotion succeeded",
        "error": str(e)
    }
```

---

## 7. Testing Plan

### Unit Tests

**Test Case 1: First Promotion Creates Nodes + Edge**
```python
def test_first_promotion_creates_graph():
    result = on_trait_promotion(
        user_id="test_user",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=700,
        ucn={"u": 0.3, "c": 0.6, "n": 0.7},
        observation_text="I wake up early",
        observation_source="chat"
    )

    assert result["status"] == "ok"
    assert result["is_new_trait"] == True

    graph = storage.load_user_graph("test_user")
    assert len(graph.nodes) == 2  # observation + trait
    assert len(graph.edges) == 1  # evidence_for
```

**Test Case 2: Second Promotion Reuses Trait Node**
```python
def test_second_promotion_reuses_node():
    # First promotion
    on_trait_promotion(...)

    # Second promotion (same trait, same value)
    result = on_trait_promotion(
        user_id="test_user",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",  # Same value
        rr_score=850,           # Higher RR
        ucn={"u": 0.2, "c": 0.5, "n": 0.7},
        observation_text="I love mornings",
        observation_source="chat"
    )

    assert result["is_new_trait"] == False  # Reused

    graph = storage.load_user_graph("test_user")
    assert len(graph.nodes) == 3  # 2 observations + 1 trait (reused)
    assert len(graph.edges) == 2  # 2 evidence edges → same trait
```

**Test Case 3: Contradiction Detection**
```python
def test_contradiction_creates_new_node():
    # First: Morning Lark
    on_trait_promotion(..., value="Morning Lark", rr_score=700)

    # Second: Night Owl (contradiction)
    result = on_trait_promotion(
        ...,
        value="Night Owl",  # Different value
        rr_score=750
    )

    assert result["is_new_trait"] == True
    assert result["contradiction_detected"] == True  # Stage 4

    graph = storage.load_user_graph("test_user")
    assert len([n for n in graph.nodes if n.node_type == "trait_belief"]) == 2
```

**Test Case 4: High Uncertainty Triggers Curiosity**
```python
def test_high_uncertainty_enqueues_curiosity():
    on_trait_promotion(
        ...,
        ucn={"u": 0.85, "c": 0.7, "n": 0.5}  # High uncertainty
    )

    # Check curiosity queue
    queue = curiosity_store.get_queue("test_user")
    assert len(queue) > 0
    assert queue[0].trait_id == "PaDNA.Chronotype"
```

**Test Case 5: Self-Loop Rejection**
```python
def test_self_loop_rejected():
    with pytest.raises(ValueError, match="self-loops"):
        edge = BeliefEdge(
            edge_type="evidence_for",
            from_node="bn_abc",
            to_node="bn_abc"  # Same node
        )
        validate_edge(edge)
```

### Integration Tests

**End-to-End: Chat → Extraction → Promotion → Graph**
```python
def test_e2e_chat_to_graph():
    # 1. Simulate chat message
    response = client.post("/ui/chat/send", json={
        "user_id": "alice",
        "persona": "head_coach",
        "text": "I wake up at 6am naturally"
    })

    # 2. Wait for trait extraction + promotion
    time.sleep(2)

    # 3. Check graph was updated
    graph_response = client.get("/core/graph/user/alice")
    graph = graph_response.json()

    assert len(graph["nodes"]) >= 2
    assert any(n["trait_id"] == "PaDNA.Chronotype" for n in graph["nodes"])
```

---

## 8. Acceptance Criteria

- ✅ `on_trait_promotion()` implemented in `ReDNACoreDemo/core/graph/belief.py`
- ✅ Hook integrated into existing promotion pipeline
- ✅ Every promotion creates observation + trait + edge
- ✅ `get_or_create_user_trait_node()` reuses nodes correctly
- ✅ Self-loop validation rejects invalid edges
- ✅ High uncertainty (u > 0.7) triggers curiosity enqueue
- ✅ Unit tests pass (5 test cases)
- ✅ Integration test: chat → graph update works end-to-end
- ✅ JSONL storage persists all updates
- ✅ No errors in production logs

---

## 9. Next Steps: Stage 4 (LLM Integration)

**Deferred to Stage 4**:
1. **LLM-powered edge inference**: Infer ontology edges from trait promotions
2. **Graph-aware Why-Cards**: Generate Why-Cards using graph context (provenance chain)
3. **Smart curiosity questions**: Use ontology neighbors to suggest next questions
4. **Contradiction resolution**: LLM explains contradictory beliefs

**Stage 3 Focus**: Deterministic graph updates, no LLM calls (except existing extraction/promotion)

---

## 10. Summary

Stage 3 establishes the **deterministic update rules** for the belief graph:
- **Promotion invariant**: observation + trait + edge (always)
- **Node reuse**: Same trait/value updates existing node
- **Provenance tracking**: Every belief traces back to observations
- **Curiosity trigger**: High uncertainty → enqueue (simple threshold)

**Design Philosophy**: AI-native doesn't mean "LLM for everything"—use deterministic rules for graph structure, LLMs for reasoning (Stage 4).

**Implementation Estimate**: 2-3 hours
- `belief.py`: 200 lines
- Hook integration: 50 lines
- Unit tests: 150 lines
- Integration test: 50 lines

**Total Stage 3 LOC**: ~450 lines

🟢 **Ready to implement Stage 3**
