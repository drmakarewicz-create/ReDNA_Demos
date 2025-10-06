# Analytics Dashboards Guide

**Last Updated:** 2025-10-04
**Version:** 1.0

---

## 📊 Overview

The Analytics Dashboards provide comprehensive metrics across four key areas:
1. **Coach Analytics** — Usage patterns, engagement, session durations
2. **Curiosity Coverage** — Trait family coverage, gaps, UCN distribution
3. **Ops Compliance** — Schedule adherence, success rates, missed operations
4. **System Health** — Uptime, latency, error rates, storage

**Location:** Dev Explorer → Analytics

---

## 🎯 Quick Start

### Accessing Analytics

1. Launch Dev Explorer: `streamlit run ExplorerDev/explorer_dev.py`
2. Navigate to **Analytics** section in sidebar
3. Select dashboard tab (Coach / Curiosity / Ops / System Health)

### First-Time Setup

Analytics dashboards require data collection to be active:

```python
# Enable analytics collection (automatic for most operations)
from ReDNACoreDemo.core import analytics_collector

# Log a coach session (done automatically by Head Coach)
analytics_collector.log_coach_session(
    user_id="demo_user",
    coach_id="head_coach",
    message_count=10,
    duration_seconds=300,
    engagement_score=0.8,
)

# Log ops execution (done automatically by scheduler)
analytics_collector.log_ops_execution(
    operation_type="holistic_review",
    scheduled_time="2025-10-04T10:00:00Z",
    actual_time="2025-10-04T10:02:15Z",
    status="completed",
    duration_seconds=135.2,
    user_id="demo_user",
)

# Log system health (done automatically by service pings)
analytics_collector.log_system_health(
    service_name="UCNRR",
    status="online",
    latency_ms=45.2,
    error_count=0,
    request_count=15,
)
```

---

## 👥 Coach Analytics Dashboard

### Purpose
Track which coaches are used most, engagement quality, and session durations.

### Metrics

#### 1. Coach Switch Frequency
**What it measures:** How often each coach is used
**Formula:** Count of sessions per coach
**Time range:** 7 / 14 / 30 / 60 / 90 days

**Use cases:**
- Identify most/least popular coaches
- Detect unused personas
- Plan persona development priorities

**Example:**
```
head_coach:        45 sessions
photo_coach:       32 sessions
relationship_coach: 28 sessions
padna_coach:        15 sessions
```

#### 2. Engagement Scores
**What it measures:** Quality of user engagement per coach
**Formula:** Average engagement score (0.0-1.0) per coach
**Interpretation:**
- **0.7-1.0**: High engagement (green) — users deeply engaged
- **0.4-0.7**: Moderate engagement (orange) — acceptable
- **0.0-0.4**: Low engagement (red) — may need improvement

**Use cases:**
- Identify which coaches create the most engaging experiences
- Detect coaches needing tone/voice improvements
- Correlate engagement with feature usage

#### 3. Session Durations
**What it measures:** Average time users spend with each coach
**Formula:** Average session length in minutes
**Time range:** Configurable (7-90 days)

**Use cases:**
- Identify coaches that hold user attention
- Detect drop-off patterns
- Optimize conversation pacing

### Workflows

#### View Coach Performance
1. Navigate to **Analytics → Coach Analytics**
2. Select time period (e.g., "Last 30 days")
3. Review bar charts for switch frequency and engagement
4. Identify underperforming coaches

#### Export Coach Data
1. Scroll to bottom of Coach Analytics dashboard
2. Click "📥 Export Coach Analytics (JSON)"
3. Save file for reporting or further analysis

**Export format:**
```json
{
  "switch_frequency": {
    "head_coach": 45,
    "photo_coach": 32
  },
  "engagement_scores": {
    "head_coach": 0.82,
    "photo_coach": 0.75
  },
  "session_durations": {
    "head_coach": 8.5,
    "photo_coach": 6.2
  },
  "generated_at": "2025-10-04T15:30:00Z",
  "period_days": 30
}
```

---

## 🧠 Curiosity Coverage Dashboard

### Purpose
Analyze trait coverage, identify gaps, and visualize curiosity distribution.

### Metrics

#### 1. Coverage by Trait Family
**What it measures:** Percentage of traits with data (UCN > 0) per family
**Formula:** `(traits_with_data / total_traits) * 100`

**Color coding:**
- **Green** (≥80%): Excellent coverage
- **Yellow** (50-79%): Moderate coverage
- **Red** (<50%): Poor coverage, needs attention

**Example:**
```
Family               Total  With Data  Coverage %  Avg UCN  Avg Curiosity
PhotoPreferences     25     22         88.0%       0.65     0.42
PersonalityProfile   30     18         60.0%       0.52     0.58
RelationshipTraits   20     8          40.0%       0.35     0.72
```

#### 2. Coverage Gaps
**What it measures:** Traits with low certainty (UCN < 0.3)
**Purpose:** Identify traits needing more evidence

**Use cases:**
- Prioritize data collection efforts
- Generate targeted nudges for gap traits
- Plan holistic review focus areas

#### 3. Overall Coverage Summary
**Metrics displayed:**
- **Total Traits**: Sum of all traits across families
- **Traits with Data**: Count of traits with UCN > 0
- **Overall Coverage**: Percentage across all families
- **Coverage Gaps**: Count of traits with UCN < 0.3

### Workflows

#### Identify Coverage Gaps for a User
1. Navigate to **Analytics → Curiosity Coverage**
2. Select user from dropdown
3. Review "Coverage by Trait Family" table
4. Scroll to "Coverage Gaps" section
5. Export gaps list for targeted campaigns

#### Compare Coverage Across Users
1. Open Analytics tab in one browser window
2. Select User A, note coverage percentages
3. Select User B in same window
4. Compare coverage patterns
5. Use findings to inform personalized strategies

---

## ⏱️ Ops Compliance Dashboard

### Purpose
Monitor scheduled operations, track success rates, and identify missed schedules.

### Metrics

#### 1. Schedule Adherence
**What it measures:** On-time vs. late vs. missed operations
**Tolerance:** Within 5 minutes of scheduled time = "on-time"

**Categories:**
- **On-Time**: Executed within 5 minutes of schedule
- **Late**: Executed >5 minutes after schedule
- **Missed**: Did not execute

**Formula:**
```
on_time_percentage = (on_time / total) * 100
```

**Example:**
```
Total Operations: 120
On-Time:          98 (81.7%)
Late:             18 (15.0%)
Missed:           4  (3.3%)
```

#### 2. Success Rates by Operation Type
**What it measures:** Percentage of successful completions per operation
**Formula:** `(completed / total) * 100`

**Operation types:**
- `holistic_review` — UCN/RR recalculation
- `nudge_enqueue` — Automated nudge generation
- `feedback_aggregate` — Feedback score computation
- `health_check` — Service ping operations

**Example:**
```
Operation Type       Success Rate
holistic_review      95.2%
nudge_enqueue        92.8%
feedback_aggregate   98.5%
health_check         88.1%
```

#### 3. Recent Operations
**What it shows:** Last 20 operations with status
**Fields:** Operation type, scheduled time, actual time, status, user

### Workflows

#### Review Missed Operations
1. Navigate to **Analytics → Ops Compliance**
2. Check "Missed" count in summary metrics
3. Scroll to "Recent Operations" table
4. Filter for `status = "missed"`
5. Investigate root causes (service downtime, scheduling conflicts)

#### Improve Success Rates
1. Identify operations with <90% success rate
2. Click on low-performing operation type
3. Review recent failures in "Recent Operations"
4. Correlate with System Health metrics (service downtime)
5. Implement fixes (retry logic, better error handling)

---

## 💚 System Health Dashboard

### Purpose
Monitor service uptime, latency, error rates, and storage usage.

### Metrics

#### 1. Service Uptime
**What it measures:** Percentage of time each service was online
**Formula:** `(online_count / total_checks) * 100`

**Services monitored:**
- **UCNRR**: UCN/RR computation service
- **Core**: ReDNA Core storage and APIs
- **LLM**: Language model inference service

**Color coding:**
- **Green** (≥99%): Excellent uptime
- **Orange** (<99%): Degraded, needs attention

**Example:**
```
Service  Uptime %
UCNRR    99.8%
Core     99.5%
LLM      98.2%  ⚠️ (degraded)
```

#### 2. Latency Percentiles
**What it measures:** Request latency distribution
**Percentiles:**
- **p50** (median): Half of requests complete faster
- **p95**: 95% of requests complete faster
- **p99**: 99% of requests complete faster (worst case)

**Use cases:**
- Detect performance regressions
- Set SLA thresholds
- Identify slow services

**Example:**
```
Service  p50    p95     p99
UCNRR    25ms   120ms   350ms
Core     15ms   80ms    200ms
LLM      450ms  1200ms  2500ms
```

#### 3. Error Rates
**What it measures:** Percentage of requests resulting in errors
**Formula:** `(error_count / request_count) * 100`

**Acceptable thresholds:**
- **<1%**: Normal operation
- **1-5%**: Warning, investigate
- **>5%**: Critical, immediate action required

#### 4. Storage Usage
**What it measures:** Disk space used by data directories (MB)

**Directories tracked:**
- `users` — Live user ReDNA data
- `dev_users` — Development/testing data
- `audit_logs` — Change history
- `dev_logs` — Trace and diagnostic logs

### Workflows

#### Investigate Service Degradation
1. Navigate to **Analytics → System Health**
2. Identify service with <99% uptime
3. Check latency percentiles for same service
4. Review error rates
5. Correlate with Ops Compliance (missed operations)
6. Fix root cause (restart service, scale resources)

#### Monitor Storage Growth
1. Check storage usage metrics
2. Identify fast-growing directories
3. Implement cleanup policies:
   - Archive old audit logs
   - Purge dev_logs older than 30 days
   - Export and compress historical user data

---

## 📥 Exporting Analytics Data

All dashboards support JSON export for reporting and analysis.

### Export Formats

#### Coach Analytics
```json
{
  "switch_frequency": {...},
  "engagement_scores": {...},
  "session_durations": {...},
  "generated_at": "ISO 8601 timestamp",
  "period_days": 30
}
```

#### Curiosity Coverage
```json
{
  "user_id": "demo_user",
  "coverage_metrics": [...],
  "coverage_gaps": [...],
  "generated_at": "ISO 8601 timestamp"
}
```

#### Ops Compliance
```json
{
  "success_rates": {...},
  "adherence": {...},
  "generated_at": "ISO 8601 timestamp",
  "period_days": 30
}
```

#### System Health
```json
{
  "uptime": {...},
  "error_rates": {...},
  "storage_sizes": {...},
  "generated_at": "ISO 8601 timestamp",
  "period_hours": 24
}
```

### Integration with CI/CD

```bash
# Example: Export and check ops compliance in CI pipeline
python -c "
from ReDNACoreDemo.core import analytics_collector
import json

adherence = analytics_collector.compute_schedule_adherence(days_back=7)
if adherence['missed'] > 5:
    raise RuntimeError(f\"Too many missed operations: {adherence['missed']}\")

print(json.dumps(adherence, indent=2))
"
```

---

## 🔧 Troubleshooting

### "No data available"

**Cause:** Analytics collection not active
**Solution:**
1. Verify services are running and logging metrics
2. Check analytics paths exist:
   - `data/analytics/` (write-protect OFF)
   - `data/dev_analytics/` (write-protect ON)
3. Manually trigger data collection (see Quick Start)

### "Failed to compute metrics"

**Cause:** Import errors or missing dependencies
**Solution:**
1. Verify `analytics_collector.py` is in `ReDNACoreDemo/core/`
2. Check Python imports: `from ReDNACoreDemo.core import analytics_collector`
3. Restart Streamlit if module was recently added

### Metrics seem stale

**Cause:** Data not being logged in real-time
**Solution:**
1. Integrate analytics logging into your workflows
2. Add logging calls to:
   - Head Coach session handlers
   - Holistic scheduler
   - Service ping functions
3. See "Data Collection Integration" section below

---

## 🔌 Data Collection Integration

### Logging Coach Sessions

Integrate into Head Coach chat loop:

```python
from ReDNACoreDemo.core import analytics_collector
from datetime import datetime

session_start = datetime.now()
message_count = 0

# ... chat loop ...
message_count += 1

session_end = datetime.now()
duration = (session_end - session_start).total_seconds()
engagement = calculate_engagement_score(messages)  # Your logic

analytics_collector.log_coach_session(
    user_id=user_id,
    coach_id=coach_id,
    message_count=message_count,
    duration_seconds=duration,
    engagement_score=engagement,
)
```

### Logging Ops Execution

Integrate into holistic scheduler:

```python
from ReDNACoreDemo.core import analytics_collector, holistic_scheduler
from datetime import datetime, timezone

scheduled_time = datetime.now(timezone.utc).isoformat()

try:
    start = datetime.now()
    result = holistic_scheduler.run_holistic_for_user(user_id)
    end = datetime.now()
    duration = (end - start).total_seconds()

    analytics_collector.log_ops_execution(
        operation_type="holistic_review",
        scheduled_time=scheduled_time,
        actual_time=datetime.now(timezone.utc).isoformat(),
        status="completed" if result["ok"] else "failed",
        duration_seconds=duration,
        user_id=user_id,
    )
except Exception:
    analytics_collector.log_ops_execution(
        operation_type="holistic_review",
        scheduled_time=scheduled_time,
        actual_time=datetime.now(timezone.utc).isoformat(),
        status="failed",
        user_id=user_id,
    )
```

### Logging System Health

Integrate into service ping loop:

```python
from ReDNACoreDemo.core import analytics_collector
import requests
import time

for service in ["UCNRR", "Core", "LLM"]:
    try:
        start = time.time()
        response = requests.get(f"{base_url}/health", timeout=5)
        latency = (time.time() - start) * 1000  # Convert to ms

        analytics_collector.log_system_health(
            service_name=service,
            status="online" if response.status_code == 200 else "degraded",
            latency_ms=latency,
            error_count=0 if response.status_code == 200 else 1,
            request_count=1,
        )
    except requests.RequestException:
        analytics_collector.log_system_health(
            service_name=service,
            status="offline",
            error_count=1,
            request_count=1,
        )
```

---

## 📊 Best Practices

### 1. Regular Monitoring
- Review Analytics dashboards **weekly** for trends
- Set up alerts for:
  - Ops compliance <85%
  - Service uptime <95%
  - Error rates >5%

### 2. Data Retention
- Keep analytics logs for **90 days**
- Archive older data to compressed backups
- Purge dev_analytics more aggressively (30 days)

### 3. Baseline Comparison
- Export analytics monthly for baseline comparison
- Track improvements over time
- Document changes that impact metrics

### 4. Demo Preparation
- Run Analytics dashboard review before demos
- Ensure services show >99% uptime
- Check for coverage gaps in demo users
- Verify ops compliance is >90%

---

## 📚 Related Documentation

- [Dev_Explorer_Guide.md](Dev_Explorer_Guide.md) — Full Dev Explorer user guide
- [Dev_Explorer_Architecture.md](Dev_Explorer_Architecture.md) — Technical architecture
- [Observability Tab](Dev_Explorer_Guide.md#5️⃣-observability) — Traces, logs, testing
- [Governance Tab](Dev_Explorer_Guide.md#6️⃣-governance--audit) — Audit logs, compliance

---

**Version History:**
- **1.0** (2025-10-04): Initial release with Coach, Curiosity, Ops, System Health dashboards
