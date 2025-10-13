# Comfort Index Integration Specification

**Version:** 1.0
**Date:** 2025-10-12
**Purpose:** User safety and control layer for data ingestion

---

## 1. Overview

The Comfort Index is the critical safety gate that ensures users maintain full control over what data is ingested, processed, and stored by the ReDNA system. It acts as a privacy-first filter that respects user boundaries and builds trust through transparency.

### Core Principles

1. **User Autonomy**: Users decide what data flows into the system
2. **Privacy by Default**: Conservative defaults, explicit opt-in for sensitive data
3. **Transparency**: Clear visibility into what data is collected and why
4. **Dynamic Adjustment**: Learns user preferences over time
5. **Retroactive Control**: Users can modify or delete data post-ingestion

---

## 2. Comfort Index Schema

### 2.1 Configuration Structure

```json
{
  "user_id": "USER123",
  "version": "1.0",
  "last_updated": "2025-10-12T14:32:00Z",
  "global_settings": {
    "max_sensitivity_level": 7,
    "auto_review_threshold": 6,
    "default_action": "review",
    "pii_handling": "anonymize"
  },
  "data_type_permissions": {
    "chat_content": {
      "enabled": true,
      "max_sensitivity": 8,
      "auto_approve": true
    },
    "chat_metadata": {
      "enabled": true,
      "includes": ["timing", "length", "emoji_count"],
      "excludes": ["ip_address", "device_fingerprint"]
    },
    "file_uploads": {
      "enabled": true,
      "max_file_size_mb": 50,
      "allowed_types": ["pdf", "txt", "md", "jpg", "png"],
      "blocked_types": ["exe", "sh", "bin"],
      "scan_for_pii": true
    },
    "behavioral_data": {
      "enabled": true,
      "granularity": "session_level",
      "includes": ["session_frequency", "engagement_metrics"],
      "excludes": ["exact_timestamps", "device_identifiers"]
    },
    "third_party_data": {
      "enabled": false,
      "requires_explicit_consent": true,
      "allowed_sources": [],
      "approval_required": true
    },
    "biometric_data": {
      "enabled": false,
      "blocked": true
    },
    "location_data": {
      "enabled": false,
      "blocked": true
    },
    "financial_data": {
      "enabled": false,
      "requires_explicit_consent": true
    },
    "health_data": {
      "enabled": false,
      "requires_explicit_consent": true
    }
  },
  "content_filters": {
    "pii_detection": {
      "enabled": true,
      "action": "anonymize",
      "patterns": [
        {
          "type": "email",
          "action": "redact",
          "preserve_domain": false
        },
        {
          "type": "phone",
          "action": "redact"
        },
        {
          "type": "ssn",
          "action": "block"
        },
        {
          "type": "credit_card",
          "action": "block"
        },
        {
          "type": "address",
          "action": "anonymize_to_city"
        },
        {
          "type": "full_name",
          "action": "allow",
          "note": "User's own name allowed"
        }
      ]
    },
    "sensitive_topics": {
      "enabled": true,
      "topics": [
        {
          "name": "financial_accounts",
          "action": "review",
          "keywords": ["bank account", "routing number", "account number"]
        },
        {
          "name": "passwords_credentials",
          "action": "block",
          "keywords": ["password", "passphrase", "api key", "token"]
        },
        {
          "name": "medical_records",
          "action": "review",
          "keywords": ["diagnosis", "prescription", "medical history"]
        }
      ]
    }
  },
  "temporal_policies": {
    "retention": {
      "default_days": 2555,
      "overrides": {
        "chat_content": 3650,
        "behavioral_data": 1825,
        "third_party_data": 365
      }
    },
    "review_frequency": {
      "prompt_user_every_days": 90,
      "last_review": "2025-10-01"
    }
  },
  "learning_preferences": {
    "adapt_to_user_behavior": true,
    "auto_adjust_thresholds": true,
    "learning_rate": 0.1,
    "require_explicit_confirmation": false
  },
  "notification_preferences": {
    "notify_on_block": true,
    "notify_on_anonymization": false,
    "notify_on_third_party_request": true,
    "weekly_digest": true
  }
}
```

### 2.2 Default Configuration (New Users)

```json
{
  "global_settings": {
    "max_sensitivity_level": 5,
    "auto_review_threshold": 4,
    "default_action": "review",
    "pii_handling": "anonymize"
  },
  "data_type_permissions": {
    "chat_content": {
      "enabled": true,
      "max_sensitivity": 5,
      "auto_approve": true
    },
    "chat_metadata": {
      "enabled": true,
      "includes": ["length", "emoji_count"]
    },
    "file_uploads": {
      "enabled": false,
      "requires_explicit_consent": true
    },
    "behavioral_data": {
      "enabled": true,
      "granularity": "session_level"
    },
    "third_party_data": {
      "enabled": false,
      "blocked": true
    }
  }
}
```

---

## 3. Sensitivity Level Taxonomy

### 3.1 Sensitivity Scale (1-10)

```yaml
1_public_information:
  description: "Publicly available, no privacy concern"
  examples:
    - Public facts
    - Common knowledge
    - Published articles
  action: Auto-approve

2_general_preferences:
  description: "General preferences, minimal personal info"
  examples:
    - Favorite color
    - Communication style preference
    - Time zone
  action: Auto-approve

3_personal_opinions:
  description: "Personal views and opinions"
  examples:
    - Beliefs about topics
    - Preferences on issues
    - General life philosophy
  action: Auto-approve

4_behavioral_patterns:
  description: "Usage patterns and behaviors"
  examples:
    - Session frequency
    - Engagement metrics
    - Response timing patterns
  action: Auto-approve with notification

5_emotional_content:
  description: "Emotional states and personal feelings"
  examples:
    - Mood expressions
    - Frustrations
    - Joy and excitement
  action: Review if threshold set low

6_personal_relationships:
  description: "Information about relationships"
  examples:
    - Family dynamics
    - Friendship quality
    - Relationship challenges
  action: Review for most users

7_career_financial:
  description: "Career and financial situation (general)"
  examples:
    - Job satisfaction
    - Career goals
    - Financial stress (no specific numbers)
  action: Review

8_health_wellness:
  description: "Health and wellness information (general)"
  examples:
    - Exercise habits
    - Sleep quality
    - Stress levels
  action: Review, possible explicit consent

9_sensitive_personal:
  description: "Highly sensitive personal information"
  examples:
    - Specific financial details
    - Detailed health conditions
    - Legal issues
  action: Explicit consent required

10_protected_information:
  description: "Legally protected or extremely sensitive"
  examples:
    - SSN, passwords, credentials
    - Medical diagnoses
    - Account numbers
  action: Block by default
```

### 3.2 Dynamic Sensitivity Assignment

The system automatically assigns sensitivity levels based on content analysis:

```python
def calculate_sensitivity(data: NormalizedData) -> int:
    """
    Calculate sensitivity level for incoming data.
    """
    base_sensitivity = get_base_sensitivity(data.source_type)

    # Scan for PII patterns
    pii_boost = scan_for_pii(data.content)

    # Check for sensitive keywords
    keyword_boost = check_sensitive_keywords(data.content)

    # Consider data type
    type_boost = get_type_sensitivity_boost(data.source_type)

    # Calculate final score
    final_sensitivity = min(
        base_sensitivity + pii_boost + keyword_boost + type_boost,
        10
    )

    return final_sensitivity

# Example sensitivity boosts
PII_SENSITIVITY_BOOST = {
    "email": +2,
    "phone": +2,
    "ssn": +5,
    "credit_card": +5,
    "address": +3,
    "medical_record": +4
}

KEYWORD_SENSITIVITY_BOOST = {
    "password": +5,
    "diagnosis": +3,
    "account number": +4,
    "salary": +2,
    "therapy": +2
}
```

---

## 4. Filter Implementation

### 4.1 Core Filter Logic

```python
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass

class FilterAction(Enum):
    PASS = "pass"
    REVIEW = "review"
    BLOCK = "block"
    ANONYMIZE = "anonymize"
    REDACT = "redact"

@dataclass
class FilterResult:
    action: FilterAction
    reason: str
    modified_data: Optional[Any] = None
    requires_user_consent: bool = False
    suggested_sensitivity: Optional[int] = None

class ComfortIndexFilter:
    """
    Main comfort index filter implementation.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.config = self.load_config(user_id)

    def apply_filter(self, data: NormalizedData) -> FilterResult:
        """
        Apply comfort index filter to incoming data.

        Returns FilterResult indicating action to take.
        """
        # Step 1: Calculate sensitivity
        sensitivity = self.calculate_sensitivity(data)

        # Step 2: Check global threshold
        if sensitivity > self.config.global_settings.max_sensitivity_level:
            return FilterResult(
                action=FilterAction.BLOCK,
                reason=f"Sensitivity {sensitivity} exceeds max {self.config.global_settings.max_sensitivity_level}",
                requires_user_consent=True
            )

        # Step 3: Check data type permissions
        data_type = data.source_type.value
        if data_type not in self.config.data_type_permissions:
            return FilterResult(
                action=FilterAction.REVIEW,
                reason=f"Data type {data_type} not in allowed list"
            )

        type_config = self.config.data_type_permissions[data_type]
        if not type_config.enabled:
            return FilterResult(
                action=FilterAction.BLOCK,
                reason=f"Data type {data_type} is disabled"
            )

        # Step 4: Check type-specific sensitivity
        if sensitivity > type_config.max_sensitivity:
            return FilterResult(
                action=FilterAction.REVIEW,
                reason=f"Sensitivity {sensitivity} exceeds type max {type_config.max_sensitivity}",
                requires_user_consent=True
            )

        # Step 5: Apply content filters
        content_result = self.apply_content_filters(data)
        if content_result.action != FilterAction.PASS:
            return content_result

        # Step 6: Check if requires explicit consent
        if type_config.get('requires_explicit_consent'):
            if not self.has_explicit_consent(data):
                return FilterResult(
                    action=FilterAction.REVIEW,
                    reason=f"Type {data_type} requires explicit user consent",
                    requires_user_consent=True
                )

        # Step 7: Auto-review threshold
        if sensitivity >= self.config.global_settings.auto_review_threshold:
            if not type_config.get('auto_approve', False):
                return FilterResult(
                    action=FilterAction.REVIEW,
                    reason=f"Sensitivity {sensitivity} requires review"
                )

        # All checks passed
        return FilterResult(
            action=FilterAction.PASS,
            reason="Passed all comfort checks"
        )

    def apply_content_filters(self, data: NormalizedData) -> FilterResult:
        """
        Apply PII detection and sensitive topic filters.
        """
        content = data.content

        # PII detection
        pii_result = self.detect_and_handle_pii(content)
        if pii_result.action != FilterAction.PASS:
            return pii_result

        # Sensitive topic detection
        topic_result = self.check_sensitive_topics(content)
        if topic_result.action != FilterAction.PASS:
            return topic_result

        return FilterResult(
            action=FilterAction.PASS,
            reason="Content filters passed"
        )

    def detect_and_handle_pii(self, content: str) -> FilterResult:
        """
        Detect PII in content and apply configured action.
        """
        pii_config = self.config.content_filters.pii_detection
        if not pii_config.enabled:
            return FilterResult(action=FilterAction.PASS, reason="PII detection disabled")

        detected_pii = []
        modified_content = content

        for pattern in pii_config.patterns:
            matches = self.find_pii_pattern(content, pattern.type)
            if matches:
                detected_pii.append(pattern.type)

                if pattern.action == "block":
                    return FilterResult(
                        action=FilterAction.BLOCK,
                        reason=f"Blocked due to {pattern.type} detection"
                    )
                elif pattern.action == "redact":
                    modified_content = self.redact_pattern(modified_content, matches)
                elif pattern.action == "anonymize":
                    modified_content = self.anonymize_pattern(modified_content, matches, pattern)

        if detected_pii:
            return FilterResult(
                action=FilterAction.ANONYMIZE,
                reason=f"PII detected and handled: {', '.join(detected_pii)}",
                modified_data=modified_content
            )

        return FilterResult(action=FilterAction.PASS, reason="No PII detected")

    def check_sensitive_topics(self, content: str) -> FilterResult:
        """
        Check for sensitive topics based on keyword matching.
        """
        topics_config = self.config.content_filters.sensitive_topics
        if not topics_config.enabled:
            return FilterResult(action=FilterAction.PASS, reason="Topic detection disabled")

        content_lower = content.lower()

        for topic in topics_config.topics:
            for keyword in topic.keywords:
                if keyword.lower() in content_lower:
                    if topic.action == "block":
                        return FilterResult(
                            action=FilterAction.BLOCK,
                            reason=f"Blocked due to sensitive topic: {topic.name}"
                        )
                    elif topic.action == "review":
                        return FilterResult(
                            action=FilterAction.REVIEW,
                            reason=f"Review required for topic: {topic.name}"
                        )

        return FilterResult(action=FilterAction.PASS, reason="No sensitive topics detected")

    def find_pii_pattern(self, content: str, pii_type: str) -> list:
        """
        Find PII patterns using regex.
        """
        import re

        patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
            "credit_card": r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            "address": r'\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd)\b',
        }

        if pii_type in patterns:
            return re.findall(patterns[pii_type], content, re.IGNORECASE)

        return []

    def redact_pattern(self, content: str, matches: list) -> str:
        """
        Redact matched patterns with [REDACTED].
        """
        for match in matches:
            content = content.replace(match, "[REDACTED]")
        return content

    def anonymize_pattern(self, content: str, matches: list, pattern: dict) -> str:
        """
        Anonymize matched patterns based on pattern config.
        """
        if pattern.type == "address":
            # Extract city only
            for match in matches:
                # Simplified: would use geocoding in production
                city_part = match.split()[-3] if len(match.split()) > 3 else "[City]"
                content = content.replace(match, f"{city_part}")
        elif pattern.type == "email":
            for match in matches:
                if pattern.get("preserve_domain"):
                    parts = match.split("@")
                    content = content.replace(match, f"[user]@{parts[1]}")
                else:
                    content = content.replace(match, "[email]")
        else:
            # Default: generic anonymization
            content = self.redact_pattern(content, matches)

        return content
```

### 4.2 Integration with Ingestion Pipeline

```python
async def ingestion_pipeline_with_comfort(data: NormalizedData, user_id: str):
    """
    Ingestion pipeline with Comfort Index integration.
    """
    # Initialize filter
    comfort_filter = ComfortIndexFilter(user_id)

    # Apply filter
    filter_result = comfort_filter.apply_filter(data)

    # Handle result
    if filter_result.action == FilterAction.PASS:
        # Proceed with ingestion
        return await continue_ingestion(data)

    elif filter_result.action == FilterAction.ANONYMIZE:
        # Use modified data
        data.content = filter_result.modified_data
        return await continue_ingestion(data)

    elif filter_result.action == FilterAction.REVIEW:
        # Queue for user review
        return await queue_for_user_review(data, filter_result)

    elif filter_result.action == FilterAction.BLOCK:
        # Log and quarantine
        await quarantine_data(data, filter_result.reason)
        await notify_user_if_configured(user_id, "Data blocked", filter_result.reason)
        return {
            "status": "blocked",
            "reason": filter_result.reason
        }
```

---

## 5. User Review Queue

### 5.1 Review Queue Structure

```json
{
  "user_id": "USER123",
  "review_queue": [
    {
      "queue_id": "review_20251012_abc123",
      "timestamp": "2025-10-12T14:32:15Z",
      "data_preview": {
        "source_type": "FILE_UPLOAD",
        "filename": "resume.pdf",
        "size_kb": 245,
        "contains_pii": ["email", "phone", "address"]
      },
      "filter_result": {
        "sensitivity": 7,
        "reason": "File upload requires review",
        "suggested_action": "anonymize_pii"
      },
      "user_options": [
        {
          "action": "approve_as_is",
          "description": "Ingest file with all content"
        },
        {
          "action": "approve_anonymized",
          "description": "Ingest with PII anonymized",
          "default": true
        },
        {
          "action": "reject",
          "description": "Do not ingest this file"
        }
      ],
      "status": "pending",
      "expires_at": "2025-10-19T14:32:15Z"
    }
  ]
}
```

### 5.2 User Review API

```python
# GET /api/comfort/review-queue/{user_id}
def get_review_queue(user_id: str) -> dict:
    """
    Retrieve pending items in user's review queue.
    """
    queue = load_review_queue(user_id)
    return {
        "count": len(queue.items),
        "items": queue.items,
        "oldest_item_age_hours": calculate_age(queue.items[0]) if queue.items else 0
    }

# POST /api/comfort/review-queue/{queue_id}/decision
def submit_review_decision(queue_id: str, decision: dict) -> dict:
    """
    User submits decision on queued item.

    decision = {
        "action": "approve_anonymized",
        "remember_preference": true,
        "apply_to_similar": false
    }
    """
    item = load_queue_item(queue_id)

    if decision.action == "approve_as_is":
        # Continue ingestion with original data
        result = continue_ingestion(item.original_data)

    elif decision.action == "approve_anonymized":
        # Continue with anonymized data
        anonymized = anonymize_data(item.original_data)
        result = continue_ingestion(anonymized)

    elif decision.action == "reject":
        # Quarantine and delete
        result = quarantine_data(item.original_data)

    # Update comfort config if requested
    if decision.remember_preference:
        update_comfort_config(item.user_id, decision, item.data_type)

    # Mark queue item as resolved
    mark_resolved(queue_id, decision)

    return {
        "status": "resolved",
        "action_taken": decision.action,
        "result": result
    }
```

---

## 6. Dynamic Learning

### 6.1 Learning from User Behavior

The Comfort Index learns and adapts based on user actions:

```python
def update_comfort_from_user_behavior(user_id: str, event: dict):
    """
    Adjust comfort settings based on user behavior.
    """
    config = load_comfort_config(user_id)

    if not config.learning_preferences.adapt_to_user_behavior:
        return  # Learning disabled

    learning_rate = config.learning_preferences.learning_rate

    # User approved high-sensitivity item
    if event.type == "review_approved" and event.sensitivity > config.max_sensitivity_level:
        # Gradually increase threshold
        new_threshold = config.max_sensitivity_level + (learning_rate * 1)
        config.max_sensitivity_level = min(new_threshold, 10)
        log_adaptation(user_id, "Increased sensitivity threshold", new_threshold)

    # User rejected low-sensitivity item
    elif event.type == "review_rejected" and event.sensitivity < config.max_sensitivity_level:
        # Decrease threshold for this data type
        data_type = event.data_type
        if data_type in config.data_type_permissions:
            type_config = config.data_type_permissions[data_type]
            new_max = type_config.max_sensitivity - (learning_rate * 2)
            type_config.max_sensitivity = max(new_max, 1)
            log_adaptation(user_id, f"Decreased {data_type} threshold", new_max)

    # User manually adjusted settings
    elif event.type == "manual_adjustment":
        # Reset learning to respect explicit user intent
        config.learning_preferences.last_manual_adjustment = now()
        log_adaptation(user_id, "User manually adjusted settings", None)

    save_comfort_config(user_id, config)
```

### 6.2 Proactive Suggestions

```python
def generate_comfort_suggestions(user_id: str) -> list:
    """
    Generate suggestions to improve user's comfort configuration.
    """
    config = load_comfort_config(user_id)
    history = load_review_history(user_id)
    suggestions = []

    # Frequently approved data type
    for data_type, stats in history.type_stats.items():
        if stats.approval_rate > 0.9 and stats.review_count > 10:
            if not config.data_type_permissions[data_type].auto_approve:
                suggestions.append({
                    "type": "enable_auto_approve",
                    "data_type": data_type,
                    "reason": f"You've approved {stats.review_count} {data_type} items. Enable auto-approve?",
                    "confidence": 0.9
                })

    # Overly restrictive settings
    if history.block_rate > 0.5:
        suggestions.append({
            "type": "relax_threshold",
            "reason": "Your current settings block a lot of data. Consider increasing threshold.",
            "suggested_new_threshold": config.max_sensitivity_level + 1,
            "confidence": 0.7
        })

    return suggestions
```

---

## 7. Transparency & Audit

### 7.1 User Dashboard

Users should have a dashboard showing:

1. **Current Settings Summary**
   - Active data types
   - Sensitivity thresholds
   - PII handling policies

2. **Recent Activity**
   - Items ingested (last 30 days)
   - Items blocked
   - Items awaiting review

3. **Data Inventory**
   - What data is stored
   - When it was collected
   - How it's being used

4. **Privacy Timeline**
   - Visual representation of data collection over time
   - Ability to drill down and review specific periods

### 7.2 Audit Log

Complete audit trail of all comfort-related actions:

```json
{
  "user_id": "USER123",
  "audit_log": [
    {
      "timestamp": "2025-10-12T14:32:15Z",
      "event_type": "filter_applied",
      "data_id": "data_xyz789",
      "result": "PASS",
      "sensitivity": 5,
      "reason": "Passed all checks"
    },
    {
      "timestamp": "2025-10-12T15:45:22Z",
      "event_type": "data_blocked",
      "data_id": "data_abc456",
      "result": "BLOCK",
      "sensitivity": 9,
      "reason": "Exceeded max sensitivity threshold"
    },
    {
      "timestamp": "2025-10-12T16:12:33Z",
      "event_type": "user_review_decision",
      "queue_id": "review_abc123",
      "decision": "approve_anonymized",
      "remember_preference": true
    },
    {
      "timestamp": "2025-10-12T16:12:34Z",
      "event_type": "config_updated",
      "change": "Increased file_upload max_sensitivity from 6 to 7",
      "trigger": "user_review_decision"
    }
  ]
}
```

---

## 8. Integration Points

### 8.1 Files to Create/Modify

1. **NEW: `core/ingestion/comfort_filter.py`**
   - Main ComfortIndexFilter class
   - PII detection logic
   - Sensitive topic matching

2. **NEW: `core/ingestion/comfort_config.py`**
   - Configuration loader/saver
   - Default config generator
   - Config validation

3. **NEW: `core/ingestion/review_queue.py`**
   - Review queue management
   - User decision handling
   - Queue expiration logic

4. **MODIFY: `core/core_ingestion.py`**
   - Add comfort filter to pipeline
   - Handle filter results
   - Route to review queue

5. **NEW: `data/users/{user_id}/comfort_index.json`**
   - Per-user comfort configuration

6. **NEW: `data/users/{user_id}/review_queue.json`**
   - Per-user review queue

7. **NEW: `UCN_RR_Demo/routes/comfort.py`**
   - API endpoints for comfort management
   - Review queue endpoints
   - Config update endpoints

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
def test_comfort_filter_pass():
    """Test that low-sensitivity data passes."""
    filter = ComfortIndexFilter("TEST_USER")
    data = create_test_data(sensitivity=3, type="chat_content")
    result = filter.apply_filter(data)
    assert result.action == FilterAction.PASS

def test_comfort_filter_block_high_sensitivity():
    """Test that high-sensitivity data is blocked."""
    filter = ComfortIndexFilter("TEST_USER")
    data = create_test_data(sensitivity=10, type="biometric_data")
    result = filter.apply_filter(data)
    assert result.action == FilterAction.BLOCK

def test_pii_detection_email():
    """Test email detection and redaction."""
    filter = ComfortIndexFilter("TEST_USER")
    data = create_test_data(content="Contact me at john@example.com")
    result = filter.detect_and_handle_pii(data.content)
    assert result.action == FilterAction.ANONYMIZE
    assert "john@example.com" not in result.modified_data

def test_user_review_approval():
    """Test that user approval continues ingestion."""
    queue_id = create_review_item("TEST_USER", test_data)
    decision = {"action": "approve_as_is", "remember_preference": False}
    result = submit_review_decision(queue_id, decision)
    assert result.status == "resolved"
    assert data_was_ingested(test_data)
```

### 9.2 Integration Tests

```python
async def test_end_to_end_comfort_flow():
    """Test complete flow from ingestion to comfort filtering."""
    user_id = "TEST_USER"
    data = create_test_chat_data(user_id, "Tell me about your health.")

    # Submit ingestion
    result = await ingestion_pipeline_with_comfort(data, user_id)

    # Should require review due to health topic
    assert result.status == "needs_review"

    # Retrieve from review queue
    queue = get_review_queue(user_id)
    assert len(queue.items) == 1

    # User approves
    decision = submit_review_decision(queue.items[0].queue_id, {
        "action": "approve_as_is",
        "remember_preference": True
    })

    # Data should now be ingested
    assert decision.status == "resolved"
    ingested_data = retrieve_ingested_data(user_id, data.id)
    assert ingested_data is not None
```

---

## 10. Privacy & Compliance

### 10.1 GDPR Compliance

- **Right to Access**: Users can view all ingested data
- **Right to Rectification**: Users can correct ingested data
- **Right to Erasure**: Users can delete data via Comfort Index
- **Right to Restriction**: Users can temporarily block ingestion
- **Right to Portability**: Users can export all data
- **Right to Object**: Users can object to specific processing

### 10.2 CCPA Compliance

- **Notice at Collection**: Users informed what data is collected
- **Right to Know**: Users can see categories and specific pieces of data
- **Right to Delete**: Deletion requests honored
- **Right to Opt-Out**: Users can disable any data type
- **Right to Non-Discrimination**: Service not degraded if users restrict data

---

## 11. Future Enhancements

1. **Context-Aware Filtering**: Adjust sensitivity based on conversation context
2. **Federated Comfort**: Share comfort preferences across devices/platforms
3. **AI-Powered PII Detection**: Use ML models for better PII detection
4. **Differential Privacy**: Add mathematical privacy guarantees
5. **Encrypted Computation**: Process data without decrypting
6. **Biometric Consent**: Use biometric authentication for high-sensitivity approvals

---

## Summary

The Comfort Index is the cornerstone of user trust in the ReDNA system. By providing:
- **Granular control** over data ingestion
- **Transparent operation** with full audit trails
- **Dynamic learning** that adapts to user preferences
- **Privacy-first defaults** that protect users by default

We ensure that users feel safe and in control while enabling the system to learn and improve their experience.

**Next Steps:**
1. Implement ComfortIndexFilter class
2. Create user-facing comfort configuration UI
3. Build review queue system
4. Add transparency dashboard
5. Integrate with main ingestion pipeline
