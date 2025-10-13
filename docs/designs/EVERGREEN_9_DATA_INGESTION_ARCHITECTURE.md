# Evergreen 9: Universal Data Ingestion Architecture

**Version:** 1.0
**Date:** 2025-10-12
**Status:** Design Specification

## Executive Summary

This document defines the architecture for universal data ingestion across the ReDNA ecosystem, ensuring that the Head Coach (HC) and Core can automatically, persistently, and safely ingest all available user data while maintaining user control and privacy through the Comfort Index.

---

## 1. Design Goals

1. **Universality**: Ingest all data types without manual intervention
2. **Persistence**: Continuous, background ingestion with checkpoint recovery
3. **Safety**: Comfort Index pre-filtering before any storage
4. **Provenance**: Complete audit trail for all ingested data
5. **Cross-Coach Sharing**: Seamless data availability across all coach modes
6. **Third-Party Data**: Support for information shared by others about the user

---

## 2. Data Source Taxonomy

### 2.1 Primary Data Sources

```yaml
chat_patterns:
  - message_content: Direct user statements
  - tone_indicators: Sentiment, emotion markers
  - pacing: Response timing, session duration
  - emoji_usage: Frequency, context, emotional mapping
  - linguistic_style: Vocabulary, sentence structure, formality

file_uploads:
  - document_content: Text extraction and analysis
  - metadata: Filename, timestamp, size, type
  - embedded_data: EXIF for images, properties for docs
  - context: Upload reason, associated conversation

cross_coach_data:
  - session_transfers: Delegation context and history
  - shared_insights: Discoveries made by other coaches
  - consolidated_beliefs: Cross-domain belief validation
  - behavioral_patterns: Activity across different modes

third_party_data:
  - relationship_input: What others say about the user
  - contextual_validation: Corroboration or conflict detection
  - social_dynamics: Network effects and influence patterns
  - provenance_tracking: Source attribution and credibility
```

### 2.2 Derived Data Sources

```yaml
behavioral_inference:
  - engagement_metrics: Interaction frequency and depth
  - preference_modeling: Implicit choices and patterns
  - temporal_patterns: Time-of-day behaviors, cycles

emotional_intelligence:
  - satisfaction_indicators: Explicit and implicit feedback
  - frustration_detection: Support need identification
  - trust_building: Relationship progression metrics
```

---

## 3. Ingestion Pipeline Architecture

### 3.1 High-Level Flow

```
┌─────────────────┐
│  Data Source    │
│  (Any Type)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Pre-Processor  │  ← Normalize format, extract metadata
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Comfort Index   │  ← User safety gate (CRITICAL)
│     Filter      │
└────────┬────────┘
         │
         ├──[PASS]───────────────────┐
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌──────────────┐
│  Provenance     │         │   Quarantine │
│    Tagger       │         │   (Rejected) │
└────────┬────────┘         └──────────────┘
         │
         ▼
┌─────────────────┐
│   Core Storage  │  ← Persistent layer
│  (Data Store)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Enrichment    │  ← Ontology mapping, relationships
│     Engine      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Distribution   │  ← Make available to all coaches
│     Layer       │
└─────────────────┘
```

### 3.2 Component Specifications

#### 3.2.1 Pre-Processor

**Purpose:** Convert raw data into normalized ingestion format

**Implementation:** `core/ingestion/preprocessor.py`

```python
class DataPreprocessor:
    """
    Normalize and prepare data for ingestion pipeline.
    """

    def process(self, raw_data: Dict[str, Any]) -> NormalizedData:
        """
        Returns:
            NormalizedData with:
            - source_type: Enum (CHAT, FILE, THIRD_PARTY, BEHAVIOR)
            - timestamp: ISO 8601
            - content: Structured payload
            - metadata: Source-specific attributes
            - sensitivity_hint: Initial privacy classification
        """
        pass
```

**Key Features:**
- Format detection and conversion
- Metadata extraction (EXIF, document properties)
- Content normalization (UTF-8, structured JSON)
- Initial sensitivity classification

#### 3.2.2 Comfort Index Filter

**Purpose:** User safety gate - only ingest data user is comfortable with

**Implementation:** `core/ingestion/comfort_filter.py`

**Logic:**
```python
def apply_comfort_filter(data: NormalizedData, user_id: str) -> FilterResult:
    """
    Apply user's comfort preferences before ingestion.

    Returns:
        FilterResult.PASS: Data can be ingested
        FilterResult.REVIEW: Needs user confirmation
        FilterResult.REJECT: Block ingestion
    """

    # Load user's comfort settings
    comfort_config = load_comfort_index(user_id)

    # Check sensitivity level
    if data.sensitivity_hint > comfort_config.max_sensitivity:
        return FilterResult.REJECT

    # Check data type permissions
    if data.source_type not in comfort_config.allowed_types:
        return FilterResult.REVIEW

    # Check specific content rules (PII, financial, health)
    if contains_restricted_content(data, comfort_config):
        return FilterResult.REVIEW

    return FilterResult.PASS
```

**Comfort Index Schema:**
```json
{
  "user_id": "USER123",
  "max_sensitivity": 7,
  "allowed_types": ["CHAT", "FILE", "BEHAVIOR"],
  "restricted_types": ["THIRD_PARTY"],
  "pii_policy": "anonymize",
  "financial_data": "block",
  "health_data": "allow_with_review",
  "third_party_consent": "explicit_only"
}
```

#### 3.2.3 Provenance Tagger

**Purpose:** Create complete audit trail for all ingested data

**Implementation:** `core/ingestion/provenance.py`

**Provenance Schema:**
```json
{
  "provenance_id": "prov_20251012_abc123",
  "data_id": "data_xyz789",
  "source": {
    "type": "CHAT",
    "origin": "head_coach_session",
    "session_id": "sess_456",
    "timestamp": "2025-10-12T14:32:15Z"
  },
  "chain_of_custody": [
    {
      "stage": "preprocessing",
      "timestamp": "2025-10-12T14:32:15.123Z",
      "processor": "preprocessor_v2.1"
    },
    {
      "stage": "comfort_filter",
      "timestamp": "2025-10-12T14:32:15.456Z",
      "result": "PASS",
      "filter_version": "comfort_v1.3"
    },
    {
      "stage": "storage",
      "timestamp": "2025-10-12T14:32:15.789Z",
      "storage_location": "data/users/USER123/ingested/"
    }
  ],
  "user_consent": {
    "implicit": true,
    "comfort_level": 6,
    "reviewed_by_user": false
  },
  "data_classification": {
    "sensitivity": 5,
    "categories": ["preference", "communication_style"],
    "retention_policy": "standard_7yr"
  }
}
```

#### 3.2.4 Core Storage

**Purpose:** Persistent, queryable data store

**Implementation:**
- `core/ingestion/storage.py`
- `data/users/{user_id}/ingested/` (file system)
- Future: Time-series DB for behavioral data

**Storage Organization:**
```
data/users/{user_id}/
├── ingested/
│   ├── chat/
│   │   ├── 2025-10/
│   │   │   ├── msg_001.json
│   │   │   └── msg_002.json
│   ├── files/
│   │   ├── uploads/
│   │   └── metadata/
│   ├── behavior/
│   │   ├── patterns.jsonl
│   │   └── metrics.jsonl
│   └── third_party/
│       └── attributed_data.jsonl
├── provenance/
│   └── audit_trail.jsonl
└── comfort_index.json
```

#### 3.2.5 Enrichment Engine

**Purpose:** Map ingested data to ontology and extract relationships

**Implementation:** `core/ingestion/enrichment.py`

**Process:**
1. **Container Mapping**: Identify relevant containers (BeliefDNA, CommStyleDNA, etc.)
2. **Trait Extraction**: Extract specific traits from data
3. **Relationship Discovery**: Find connections to existing data
4. **Confidence Scoring**: Assign confidence to all inferences
5. **Update Triggers**: Notify relevant systems of new data

**Example Enrichment:**
```json
{
  "data_id": "data_xyz789",
  "enrichment": {
    "mapped_containers": [
      {
        "container_id": "CommStyleDNA.informal_tone",
        "confidence": 0.82,
        "evidence": ["emoji usage", "casual vocabulary"]
      },
      {
        "container_id": "BeliefDNA.direct_communication_preference",
        "confidence": 0.71,
        "evidence": ["short responses", "question avoidance"]
      }
    ],
    "extracted_traits": {
      "emoji_frequency": 0.15,
      "avg_response_time_sec": 45,
      "preferred_session_length_min": 12
    },
    "relationships": [
      {
        "type": "supports",
        "target": "existing_belief_abc",
        "strength": 0.65
      }
    ]
  }
}
```

#### 3.2.6 Distribution Layer

**Purpose:** Make data available to all coaches and systems

**Implementation:** `core/ingestion/distribution.py`

**Distribution Mechanisms:**
1. **Event Bus**: Real-time notifications to active coaches
2. **Query Interface**: On-demand data retrieval
3. **Digest Generation**: Periodic summaries for background processes
4. **Cross-Coach Cache**: Shared memory for active session data

---

## 4. Core/HC Collaboration Logic

### 4.1 Responsibilities

**Core:**
- Persistent storage and retrieval
- Ontology mapping and enrichment
- Cross-coach data sharing
- Privacy and consent enforcement

**Head Coach:**
- Active session data collection
- Real-time behavioral observation
- User comfort monitoring
- Delegation coordination

### 4.2 Collaboration Protocol

```python
# HC initiates ingestion
async def hc_observe_and_ingest(user_id: str, observation: dict):
    """
    Head Coach observes user behavior and initiates ingestion.
    """
    # 1. HC normalizes observation
    normalized = await hc_normalize_observation(observation)

    # 2. HC passes to Core ingestion pipeline
    ingestion_request = {
        "user_id": user_id,
        "data": normalized,
        "source": "head_coach",
        "priority": "realtime"
    }

    # 3. Core processes through pipeline
    result = await core.ingest(ingestion_request)

    # 4. Core notifies HC of outcome
    if result.status == "ENRICHED":
        # HC receives enriched data for immediate use
        await hc_update_session_context(result.enriched_data)
    elif result.status == "NEEDS_REVIEW":
        # HC prompts user for consent
        await hc_request_user_consent(result.pending_data)

    return result
```

### 4.3 Integration Points

**Files to Update:**

1. **`ReDNACoreDemo/core/hc_orchestrator.py`**
   - Add ingestion hooks in conversation loop
   - Monitor user comfort in real-time
   - Trigger background ingestion for long-running observations

2. **`core/core_ingestion.py`** (NEW FILE)
   - Main ingestion pipeline orchestration
   - Coordinate all ingestion components
   - Manage ingestion queue and priority

3. **`UCN_RR_Demo/ucnrr_service_with_ai.py`**
   - Expose ingestion API endpoints
   - Handle file upload ingestion
   - Third-party data submission endpoints

4. **`prompts/core_ai.md`**
   - Document ingestion capabilities
   - Guide Core on data handling
   - Privacy and ethics guidelines

---

## 5. Comfort Index Integration

### 5.1 User Control Interface

Users must have full control over what data is ingested. The Comfort Index provides:

1. **Granular Permissions**: Per data type, sensitivity level
2. **Review Queues**: See pending data before ingestion
3. **Retroactive Control**: Delete or restrict already-ingested data
4. **Transparency**: Full audit trail visibility

### 5.2 Default Comfort Settings

**Conservative Defaults:**
```json
{
  "new_user_defaults": {
    "max_sensitivity": 5,
    "allowed_types": ["CHAT"],
    "requires_review": ["FILE", "THIRD_PARTY"],
    "blocked": ["BIOMETRIC", "LOCATION"],
    "auto_anonymize_pii": true
  }
}
```

### 5.3 Dynamic Comfort Adjustment

The system learns user comfort over time:
- User approves high-sensitivity data → increase comfort ceiling
- User rejects or deletes data → decrease threshold
- User explicitly adjusts settings → immediate effect

---

## 6. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Create `core/ingestion/` module structure
- [ ] Implement PreProcessor for chat and file data
- [ ] Build Comfort Index Filter with basic rules
- [ ] Create Provenance Tagger with audit logging

### Phase 2: Storage & Enrichment (Week 3-4)
- [ ] Implement Core Storage layer
- [ ] Build Enrichment Engine with ontology mapping
- [ ] Create Distribution Layer with event bus
- [ ] Add query interfaces for coaches

### Phase 3: Integration (Week 5-6)
- [ ] Update `hc_orchestrator.py` with ingestion hooks
- [ ] Create `core_ingestion.py` pipeline orchestrator
- [ ] Add API endpoints to `ucnrr_service_with_ai.py`
- [ ] Update `core_ai.md` with ingestion guidelines

### Phase 4: Third-Party & Advanced (Week 7-8)
- [ ] Build third-party data submission interface
- [ ] Implement cross-coach data sharing protocols
- [ ] Create user-facing Comfort Index UI
- [ ] Add retroactive data control features

---

## 7. Security & Privacy Considerations

### 7.1 Data Security
- All ingested data encrypted at rest (AES-256)
- In-transit encryption (TLS 1.3)
- Access control: Only authorized coaches and user
- Regular security audits of ingestion pipeline

### 7.2 Privacy by Design
- Minimal data collection (only what user consents to)
- Purpose limitation (data only used for stated purposes)
- Data minimization (delete unnecessary metadata)
- User rights: access, rectification, erasure, portability

### 7.3 Compliance
- GDPR: Right to be forgotten, data portability
- CCPA: Consumer privacy rights
- HIPAA considerations for health data (if applicable)

---

## 8. Metrics & Monitoring

### 8.1 Pipeline Health
- Ingestion throughput (items/sec)
- Processing latency (ms per stage)
- Error rates by stage
- Comfort Filter rejection rates

### 8.2 Data Quality
- Enrichment success rate
- Ontology mapping confidence scores
- Provenance completeness
- Cross-coach availability latency

### 8.3 User Trust
- Comfort Index adjustment frequency
- User review approval rates
- Data deletion requests
- Transparency dashboard usage

---

## 9. Testing Strategy

### 9.1 Unit Tests
- Each pipeline component independently
- Comfort Filter with various sensitivity levels
- Provenance chain integrity
- Enrichment accuracy

### 9.2 Integration Tests
- End-to-end ingestion flows
- Cross-coach data sharing
- Error recovery and retry logic
- User consent workflows

### 9.3 Privacy Tests
- Comfort Filter bypass attempts
- Unauthorized access attempts
- Data leakage between users
- Provenance audit completeness

---

## 10. Open Questions & Future Work

1. **Real-time vs. Batch Processing**: Balance between immediate ingestion and efficient batch processing
2. **Data Retention Policies**: How long to keep various data types?
3. **Cross-User Insights**: How to aggregate insights without compromising individual privacy?
4. **Machine Learning Integration**: Use ingested data to improve models while maintaining privacy
5. **Federated Learning**: Keep sensitive data local while still improving global models

---

## Appendix A: Data Flow Sequence Diagram

```
User ──Chat──> HC ──Observe──> PreProcessor
                                     │
                                     ▼
                              Comfort Filter ──[PASS]──> Provenance
                                     │                       │
                                     │                       ▼
                                [REJECT]              Core Storage
                                     │                       │
                                     ▼                       ▼
                               Quarantine            Enrichment
                                                           │
                                                           ▼
                                                    Distribution
                                                           │
                                          ┌────────────────┼────────────┐
                                          ▼                ▼            ▼
                                         HC           Other Coaches   Ontology
```

---

**Next Steps:**
1. Review this architecture with stakeholders
2. Create detailed component specifications for Codex implementation
3. Define API contracts between Core and HC
4. Design user-facing Comfort Index interface
5. Begin Phase 1 implementation
