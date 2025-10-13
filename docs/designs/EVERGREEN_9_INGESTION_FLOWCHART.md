# Evergreen 9: Data Ingestion Pipeline - Visual Flowchart

**Version:** 1.0
**Date:** 2025-10-12

---

## Complete Ingestion Pipeline Flow

```
                    DATA INGESTION PIPELINE
                    ========================

┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
├─────────────┬──────────────┬─────────────┬──────────────────────┤
│   Chat      │   Files      │  Behavior   │   Third-Party        │
│  Patterns   │   Uploads    │  Metrics    │   Data               │
└──────┬──────┴──────┬───────┴──────┬──────┴─────────┬────────────┘
       │             │               │                │
       └─────────────┴───────────────┴────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │         PRE-PROCESSOR                      │
       │  ┌─────────────────────────────────┐      │
       │  │ • Format Detection              │      │
       │  │ • Normalization (UTF-8, JSON)   │      │
       │  │ • Metadata Extraction           │      │
       │  │ • Initial Sensitivity Hint      │      │
       │  └─────────────────────────────────┘      │
       └───────────────────┬───────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   NormalizedData       │
              │  {                     │
              │    source_type,        │
              │    timestamp,          │
              │    content,            │
              │    metadata,           │
              │    sensitivity_hint    │
              │  }                     │
              └────────────┬───────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │      COMFORT INDEX FILTER                  │
       │      (USER SAFETY GATE)                    │
       │  ┌─────────────────────────────────┐      │
       │  │ 1. Load User Comfort Config     │      │
       │  │ 2. Check Sensitivity Level      │      │
       │  │ 3. Verify Data Type Permission  │      │
       │  │ 4. Scan for Restricted Content  │      │
       │  │ 5. Apply User-Specific Rules    │      │
       │  └─────────────────────────────────┘      │
       └───────────┬──────────────┬─────────────────┘
                   │              │
          [PASS] ──┘              └── [REJECT/REVIEW]
             │                              │
             │                              ▼
             │                    ┌──────────────────┐
             │                    │   QUARANTINE     │
             │                    │   or             │
             │                    │   USER REVIEW    │
             │                    │   QUEUE          │
             │                    └──────────────────┘
             │
             ▼
       ┌───────────────────────────────────────────┐
       │      PROVENANCE TAGGER                     │
       │  ┌─────────────────────────────────┐      │
       │  │ Generate Audit Record:          │      │
       │  │ • Unique Provenance ID          │      │
       │  │ • Source Attribution            │      │
       │  │ • Chain of Custody              │      │
       │  │ • Consent Record                │      │
       │  │ • Classification Labels         │      │
       │  │ • Timestamp Trail               │      │
       │  └─────────────────────────────────┘      │
       └───────────────────┬───────────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │       CORE STORAGE                         │
       │  ┌─────────────────────────────────┐      │
       │  │ Persistent Layer:               │      │
       │  │ • Write to file system          │      │
       │  │ • Index for fast retrieval      │      │
       │  │ • Replicate for redundancy      │      │
       │  │ • Encrypt at rest (AES-256)     │      │
       │  └─────────────────────────────────┘      │
       └───────────────────┬───────────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │      ENRICHMENT ENGINE                     │
       │  ┌─────────────────────────────────┐      │
       │  │ 1. Ontology Mapping             │      │
       │  │    ├─ Identify Containers       │      │
       │  │    ├─ Extract Traits            │      │
       │  │    └─ Assign Confidence         │      │
       │  │                                 │      │
       │  │ 2. Relationship Discovery       │      │
       │  │    ├─ Link to Existing Data     │      │
       │  │    ├─ Find Contradictions       │      │
       │  │    └─ Detect Patterns           │      │
       │  │                                 │      │
       │  │ 3. Context Enhancement          │      │
       │  │    ├─ Temporal Context          │      │
       │  │    ├─ Cross-Domain Links        │      │
       │  │    └─ Behavioral Implications   │      │
       │  └─────────────────────────────────┘      │
       └───────────────────┬───────────────────────┘
                           │
                           ▼
       ┌───────────────────────────────────────────┐
       │      DISTRIBUTION LAYER                    │
       │  ┌─────────────────────────────────┐      │
       │  │ Make Data Available:            │      │
       │  │ • Event Bus (Real-time)         │      │
       │  │ • Query Interface (On-demand)   │      │
       │  │ • Digest Generation (Batch)     │      │
       │  │ • Cross-Coach Cache (Shared)    │      │
       │  └─────────────────────────────────┘      │
       └───────┬─────────────┬────────────┬─────────┘
               │             │            │
               ▼             ▼            ▼
         ┌─────────┐   ┌─────────┐  ┌─────────┐
         │   HC    │   │  Other  │  │ Ontology│
         │         │   │ Coaches │  │ Systems │
         └─────────┘   └─────────┘  └─────────┘


═══════════════════════════════════════════════════════════════
                    DETAILED STAGE FLOWS
═══════════════════════════════════════════════════════════════
```

---

## Stage 1: Pre-Processing Detail

```
┌──────────────────────────────────────────────────────────────┐
│                    PRE-PROCESSOR LOGIC                        │
└──────────────────────────────────────────────────────────────┘

Input: Raw Data (any format)
         │
         ▼
    ┌────────────────┐
    │ Detect Format  │
    └────┬───────────┘
         │
    ┌────┴─────────────────────────────────┐
    │                                       │
    ▼                                       ▼
┌─────────┐                          ┌──────────┐
│  Text   │                          │  Binary  │
└────┬────┘                          └─────┬────┘
     │                                     │
     ├─ Plain Text                         ├─ Image (EXIF extract)
     ├─ JSON                               ├─ PDF (text extract)
     ├─ Markdown                           └─ Document (metadata)
     └─ CSV                                     │
         │                                      │
         └──────────────┬───────────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │  Normalize to    │
              │  Standard JSON   │
              └─────────┬────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ Extract Metadata │
              │ • Timestamp      │
              │ • Source         │
              │ • Format         │
              │ • Size           │
              └─────────┬────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ Sensitivity Hint │
              │ Quick Scan:      │
              │ • PII keywords   │
              │ • Financial      │
              │ • Health         │
              │ • Location       │
              └─────────┬────────┘
                        │
                        ▼
                NormalizedData Output
```

---

## Stage 2: Comfort Filter Decision Tree

```
┌──────────────────────────────────────────────────────────────┐
│               COMFORT INDEX FILTER FLOW                       │
└──────────────────────────────────────────────────────────────┘

NormalizedData Input
         │
         ▼
    ┌──────────────────────┐
    │ Load User Comfort    │
    │ Configuration        │
    └─────────┬────────────┘
              │
              ▼
    ┌──────────────────────┐      NO
    │ Sensitivity ≤ Max?   │──────────┐
    └─────────┬────────────┘          │
              │ YES                   │
              ▼                       │
    ┌──────────────────────┐          │
    │ Data Type Allowed?   │──────────┤
    └─────────┬────────────┘   NO     │
              │ YES                   │
              ▼                       │
    ┌──────────────────────┐          │
    │ Check PII Rules      │          │
    └─────────┬────────────┘          │
              │                       │
         ┌────┴────┐                  │
         │         │                  │
    PII Found   No PII                │
         │         │                  │
         ▼         │                  │
    ┌─────────┐   │                  │
    │Anonymize│   │                  │
    │ Policy? │   │                  │
    └────┬────┘   │                  │
         │        │                  │
    YES  │   NO   │                  │
         │   │    │                  │
         ▼   │    │                  │
    Anonymize│    │                  │
         │   │    │                  │
         └───┴────┘                  │
              │                      │
              ▼                      │
    ┌──────────────────────┐         │
    │ Third-Party Source?  │         │
    └─────────┬────────────┘         │
              │                      │
         YES  │   NO                 │
              │   │                  │
              ▼   │                  │
    ┌──────────────────────┐         │
    │ Explicit Consent     │         │
    │ Required?            │         │
    └─────────┬────────────┘         │
              │                      │
         YES  │   NO                 │
              │   │                  │
              ▼   │                  │
         USER     │                  │
         REVIEW ◄─┘                  │
         QUEUE                       │
              │                      │
              │                      │
         ┌────┴──────────────────────┘
         │
         ▼
    [DECISION]
         │
    ┌────┴────┬─────────┐
    │         │         │
  PASS     REVIEW    REJECT
    │         │         │
    ▼         ▼         ▼
Continue   Queue   Quarantine
Pipeline   User     (Log &
          Review    Notify)
```

---

## Stage 3: Provenance Tagging Structure

```
┌──────────────────────────────────────────────────────────────┐
│                  PROVENANCE RECORD CREATION                   │
└──────────────────────────────────────────────────────────────┘

Data (Passed Comfort Filter)
         │
         ▼
    ┌──────────────────────────────┐
    │ Generate Provenance ID       │
    │ Format: prov_YYYYMMDD_hash   │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Record Source Attribution    │
    │ • Origin System              │
    │ • Session Context            │
    │ • User Identity              │
    │ • Timestamp (ISO 8601)       │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Build Chain of Custody       │
    │ For Each Processing Stage:   │
    │   • Stage Name               │
    │   • Timestamp                │
    │   • Processor Version        │
    │   • Result/Outcome           │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Record Consent Status        │
    │ • Implicit/Explicit          │
    │ • Comfort Level Applied      │
    │ • User Review Required?      │
    │ • Date/Time of Consent       │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Apply Data Classification    │
    │ • Sensitivity Score (1-10)   │
    │ • Category Tags              │
    │ • Retention Policy           │
    │ • Access Controls            │
    └─────────┬────────────────────┘
              │
              ▼
    Write to Provenance Store
    (Immutable Audit Log)
```

---

## Stage 4: Enrichment Process

```
┌──────────────────────────────────────────────────────────────┐
│                    ENRICHMENT ENGINE FLOW                     │
└──────────────────────────────────────────────────────────────┘

Stored Data + Provenance
         │
         ▼
╔════════════════════════════════════════╗
║   PHASE 1: ONTOLOGY MAPPING            ║
╚════════════════════════════════════════╝
         │
         ▼
    ┌──────────────────────────────┐
    │ Analyze Content              │
    │ • NLP/Semantic Analysis      │
    │ • Pattern Recognition        │
    │ • Context Extraction         │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Identify Relevant Containers │
    │ Query: container_patterns_v5 │
    │                              │
    │ Examples:                    │
    │ • BeliefDNA.core_values.*    │
    │ • CommStyleDNA.tone.*        │
    │ • BehaviorDNA.patterns.*     │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Extract Specific Traits      │
    │ For each container:          │
    │ • Trait name                 │
    │ • Trait value                │
    │ • Confidence score (0-1)     │
    │ • Evidence citations         │
    └─────────┬────────────────────┘
              │
              ▼
╔════════════════════════════════════════╗
║   PHASE 2: RELATIONSHIP DISCOVERY      ║
╚════════════════════════════════════════╝
         │
         ▼
    ┌──────────────────────────────┐
    │ Query Existing User Data     │
    │ • Load user ontology graph   │
    │ • Retrieve recent beliefs    │
    │ • Get behavior history       │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Find Connections             │
    │ Relationship Types:          │
    │ • Supports                   │
    │ • Contradicts                │
    │ • Refines                    │
    │ • Exemplifies                │
    │ • Implies                    │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Detect Patterns              │
    │ • Temporal patterns          │
    │ • Behavioral clusters        │
    │ • Belief evolution           │
    │ • Preference drift           │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Identify Conflicts           │
    │ • Contradictory beliefs      │
    │ • Inconsistent behaviors     │
    │ • Changed preferences        │
    │ • Flag for resolution        │
    └─────────┬────────────────────┘
              │
              ▼
╔════════════════════════════════════════╗
║   PHASE 3: CONTEXT ENHANCEMENT         ║
╚════════════════════════════════════════╝
         │
         ▼
    ┌──────────────────────────────┐
    │ Add Temporal Context         │
    │ • Time of day effects        │
    │ • Day of week patterns       │
    │ • Seasonal variations        │
    │ • Life event correlation     │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Cross-Domain Linking         │
    │ • Health → Mood              │
    │ • Work → Relationships       │
    │ • Goals → Actions            │
    │ • Values → Decisions         │
    └─────────┬────────────────────┘
              │
              ▼
    ┌──────────────────────────────┐
    │ Behavioral Implications      │
    │ • Predict future actions     │
    │ • Suggest interventions      │
    │ • Identify opportunities     │
    │ • Flag risks                 │
    └─────────┬────────────────────┘
              │
              ▼
    Generate Enriched Data Package
```

---

## Stage 5: Distribution Mechanisms

```
┌──────────────────────────────────────────────────────────────┐
│                    DISTRIBUTION LAYER                         │
└──────────────────────────────────────────────────────────────┘

Enriched Data Package
         │
         ▼
    ┌──────────────────────────────┐
    │ Distribution Router          │
    │ Determine Target Systems     │
    └─────────┬────────────────────┘
              │
         ┌────┴─────┬───────────┬─────────────┐
         │          │           │             │
         ▼          ▼           ▼             ▼
    ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
    │ Event  │ │ Query  │ │ Digest  │ │  Cache   │
    │  Bus   │ │ Index  │ │Generator│ │  Update  │
    └────┬───┘ └────┬───┘ └────┬────┘ └─────┬────┘
         │          │          │            │
         │          │          │            │
    Real-time   On-Demand  Batch        Shared
    Publish     Store      Schedule      Memory
         │          │          │            │
         ▼          ▼          ▼            ▼
    ┌────────────────────────────────────────┐
    │        CONSUMER SYSTEMS                │
    ├─────────┬──────────┬───────────────────┤
    │   HC    │  Coaches │  Ontology Systems │
    └─────────┴──────────┴───────────────────┘

Event Bus Flow:
    Enriched Data
         │
         ▼
    ┌──────────────────┐
    │ Publish Event    │
    │ Topic: user_data │
    └────────┬─────────┘
             │
        ┌────┴─────┬─────────┐
        ▼          ▼         ▼
    Subscriber  Subscriber  Subscriber
    (HC)       (RC)        (Ontology)
        │          │         │
        ▼          ▼         ▼
    Process    Process    Process
    Update     Update     Update

Query Interface Flow:
    Coach Request
         │
         ▼
    ┌──────────────────┐
    │ Query API        │
    │ GET /user/{id}/  │
    │     recent_data  │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Check Access     │
    │ Permissions      │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Retrieve from    │
    │ Storage/Index    │
    └────────┬─────────┘
             │
             ▼
    Return Enriched Data
```

---

## Core/HC Collaboration Sequence

```
┌──────────────────────────────────────────────────────────────┐
│          HC AND CORE COLLABORATION PROTOCOL                   │
└──────────────────────────────────────────────────────────────┘

┌─────┐                                              ┌──────┐
│ HC  │                                              │ Core │
└──┬──┘                                              └───┬──┘
   │                                                     │
   │ 1. Observe User Behavior                           │
   │    (chat, timing, emotion)                         │
   │                                                     │
   │ 2. Normalize Observation                           │
   │    → NormalizedData                                │
   │                                                     │
   │ 3. Submit Ingestion Request                        │
   │────────────────────────────────────────────────────>│
   │    POST /ingest                                    │
   │    { user_id, data, source, priority }             │
   │                                                     │
   │                                     4. Pre-Process  │
   │                                        (format,     │
   │                                         metadata)   │
   │                                                     │
   │                                  5. Comfort Filter  │
   │                                     (safety check)  │
   │                                                     │
   │                       ┌─────────────────────────────┤
   │                       │ Decision:                   │
   │                       │ PASS / REVIEW / REJECT      │
   │                       └─────────────────────────────┤
   │                                                     │
   │              6a. If NEEDS_REVIEW                    │
   │<────────────────────────────────────────────────────│
   │    { status: "NEEDS_REVIEW",                       │
   │      pending_data, reason }                         │
   │                                                     │
   │ 7. Prompt User for Consent                          │
   │    (HC shows comfort dialog)                        │
   │                                                     │
   │ 8. User Response                                    │
   │    (approve/reject)                                 │
   │                                                     │
   │ 9. Submit User Decision                             │
   │────────────────────────────────────────────────────>│
   │    POST /ingest/consent                            │
   │    { data_id, decision }                            │
   │                                                     │
   │                           10. Continue or Reject    │
   │                                                     │
   │              6b. If PASS                            │
   │                               11. Provenance Tag    │
   │                               12. Store             │
   │                               13. Enrich            │
   │                               14. Distribute        │
   │                                                     │
   │ 15. Receive Enriched Data                           │
   │<────────────────────────────────────────────────────│
   │    { status: "ENRICHED",                           │
   │      enriched_data, containers,                     │
   │      relationships }                                │
   │                                                     │
   │ 16. Update Session Context                          │
   │     (HC uses new insights)                          │
   │                                                     │
   │ 17. Continue Conversation                           │
   │     (with richer context)                           │
   │                                                     │

Async Background Ingestion:

┌─────┐                                              ┌──────┐
│ HC  │                                              │ Core │
└──┬──┘                                              └───┬──┘
   │                                                     │
   │ 1. Observe Long-Term Pattern                       │
   │    (e.g., session frequency,                       │
   │     response timing trends)                        │
   │                                                     │
   │ 2. Queue Background Ingestion                      │
   │────────────────────────────────────────────────────>│
   │    POST /ingest/async                              │
   │    { user_id, behavioral_summary,                  │
   │      priority: "low" }                             │
   │                                                     │
   │ 3. Acknowledgment                                   │
   │<────────────────────────────────────────────────────│
   │    { queued: true, job_id }                        │
   │                                                     │
   │                          4. Process in Background   │
   │                             (when resources avail)  │
   │                                                     │
   │                          5. Complete Enrichment     │
   │                                                     │
   │ 6. Event Bus Notification                           │
   │<────────────────────────────────────────────────────│
   │    TOPIC: user_data_updated                        │
   │    { user_id, job_id, new_insights }               │
   │                                                     │
   │ 7. HC Updates Internal Model                        │
   │    (ready for next session)                         │
   │                                                     │
```

---

## Error Handling & Recovery

```
┌──────────────────────────────────────────────────────────────┐
│              ERROR HANDLING FLOW                              │
└──────────────────────────────────────────────────────────────┘

Any Stage Failure
         │
         ▼
    ┌──────────────────┐
    │ Catch Exception  │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Log Error        │
    │ • Stage          │
    │ • Data ID        │
    │ • Exception      │
    │ • Stack Trace    │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐      NO
    │ Retryable?       │────────┐
    └────────┬─────────┘        │
             │ YES              │
             ▼                  │
    ┌──────────────────┐        │
    │ Retry Counter    │        │
    │ < Max Retries?   │        │
    └────────┬─────────┘        │
             │ YES              │
             ▼                  │
    ┌──────────────────┐        │
    │ Exponential      │        │
    │ Backoff Wait     │        │
    └────────┬─────────┘        │
             │                  │
             ▼                  │
    Retry Stage                 │
             │                  │
             └──────────┬───────┘
                        │
                        ▼
    ┌──────────────────────────┐
    │ Move to Dead Letter Queue│
    └────────┬─────────────────┘
             │
             ▼
    ┌──────────────────┐
    │ Notify Admin     │
    │ Alert System     │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Update User if   │
    │ User-Facing      │
    │ Impact           │
    └──────────────────┘
```

---

## Metrics & Monitoring Dashboard

```
┌──────────────────────────────────────────────────────────────┐
│              INGESTION PIPELINE METRICS                       │
└──────────────────────────────────────────────────────────────┘

Real-Time Metrics:

┌────────────────────────────────┐
│ Throughput                     │
│ ▓▓▓▓▓▓▓▓▓▓░░░░░░  1,234 items/s│
└────────────────────────────────┘

┌────────────────────────────────┐
│ Pipeline Latency (p95)         │
│ ▓▓▓░░░░░░░░░░░░░  152 ms       │
└────────────────────────────────┘

┌────────────────────────────────┐
│ Comfort Filter Pass Rate       │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░  94.3%        │
└────────────────────────────────┘

┌────────────────────────────────┐
│ Enrichment Success Rate        │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░  89.7%        │
└────────────────────────────────┘

Stage Breakdown:

┌─────────────┬──────────┬──────────┬──────────┐
│ Stage       │ Avg (ms) │ p95 (ms) │ p99 (ms) │
├─────────────┼──────────┼──────────┼──────────┤
│ PreProcess  │    15    │    28    │    45    │
│ Comfort     │    22    │    41    │    67    │
│ Provenance  │     8    │    12    │    18    │
│ Storage     │    45    │    78    │   112    │
│ Enrichment  │   125    │   234    │   456    │
│ Distribution│    18    │    32    │    51    │
└─────────────┴──────────┴──────────┴──────────┘

Error Rates:

┌────────────────────────────────┐
│ Total Errors (last hour)       │
│ ██░░░░░░░░░░░░░░  12 (0.02%)   │
│                                │
│ By Stage:                      │
│ • PreProcess:   2              │
│ • Comfort:      0              │
│ • Storage:      4              │
│ • Enrichment:   5              │
│ • Distribution: 1              │
└────────────────────────────────┘
```

---

## Summary

This flowchart provides complete visual documentation of the data ingestion pipeline, including:

1. **Main Pipeline Flow**: Source → Pre-Process → Comfort → Provenance → Storage → Enrichment → Distribution
2. **Detailed Stage Logic**: Decision trees and processing steps for each stage
3. **Collaboration Protocol**: Sequence diagrams for HC/Core interaction
4. **Error Handling**: Resilience and recovery mechanisms
5. **Monitoring**: Real-time metrics and observability

**Next Steps:**
- Use this flowchart as implementation guide for Codex
- Reference during code reviews to ensure architectural compliance
- Update as pipeline evolves with new features
- Share with stakeholders for system understanding
