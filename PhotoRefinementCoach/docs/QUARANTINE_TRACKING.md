# Quarantine Tracking System

## Overview

The Quarantine Tracking System automatically captures and manages trait paths that couldn't be mapped to official PaDNA containers during import. This provides a systematic way to evolve the schema over time based on real user data patterns.

## Architecture

### Components

1. **`quarantine_tracker.py`** - Core tracking module
   - Records quarantined items from imports
   - Categorizes paths by type (Behavioral, Style, Movement, etc.)
   - Maintains statistics and occurrence counts
   - Provides review and decision management

2. **`quarantine_registry.json`** - Persistent storage
   - Located at: `PhotoRefinementCoach/data/quarantine_registry.json`
   - Stores all quarantined paths with metadata
   - Tracks occurrence counts, example values, users, sources
   - Maintains status (pending, mapped, promoted, rejected)

3. **`review_quarantine.py`** - CLI review tool
   - View statistics and listings
   - Export paths for human review
   - Import review decisions
   - Mark individual paths

### Integration

The system is automatically integrated into the import flow in `importer.py`. Every time an import occurs, quarantined items are logged to the registry.

## Workflow

### 1. Automatic Collection

When users import data containing unmapped paths, the system automatically:
- Captures the path, value, and context
- Categorizes the path
- Increments occurrence counts
- Records which users/sources used the path

### 2. Review Process

Periodically review accumulated quarantined paths:

```bash
# View statistics
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py stats

# List pending paths
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py list

# Export for detailed review
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py export review.json
```

### 3. Decision Making

For each quarantined path, decide:

**OPTION A: PROMOTE** - Create a new PaDNA container
- Path represents a genuinely new trait concept
- Not covered by existing PaDNA paths
- Has clear value for the system
- Example: `BehavioralDNA.SocialProjection` → Promote to `PaDNA.PersonalityDNA.SocialStyle`

**OPTION B: MAP** - Create an alias to existing path
- Concept already exists in PaDNA under different name
- Create a path mapping for convenience
- Example: `BehavioralDNA.Posture` → Map to `PaDNA.MovementDNA.Posture`

**OPTION C: REJECT** - Mark as not relevant
- Path is noise or not applicable
- Won't be supported in the system
- Document reason for future reference

### 4. Apply Decisions

Edit the exported review file with decisions:

```json
{
  "path": "BehavioralDNA.Posture",
  "category": "Behavioral",
  "occurrence_count": 15,
  "example_values": ["Confident posture", "Slouched"],
  "decision": {
    "status": "mapped",
    "suggested_mapping": "PaDNA.MovementDNA.Posture",
    "notes": "Mapped to existing movement DNA path"
  }
}
```

Then import decisions:

```bash
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py import review.json
```

### 5. Implement Changes

Based on decisions:

**For MAPPED paths:**
```yaml
# Add to ReDNACoreDemo/data/config/path_mappings.yaml
aliases:
  "BehavioralDNA.Posture": "PaDNA.MovementDNA.Posture"
  "BehavioralDNA.SocialProjection": "PaDNA.PersonalityDNA.SocialStyle"
```

**For PROMOTED paths:**
1. Add to traits registry: `ReDNACoreDemo/data/config/traits_registry.yaml`
2. Update schema documentation
3. Add to UI displays if needed

## CLI Tool Reference

### View Statistics

```bash
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py stats
```

Shows:
- Total unique paths and occurrences
- Breakdown by category and status
- Most frequent paths
- Last update timestamp

### List Pending Paths

```bash
# All pending paths
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py list

# Filter by category
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py list --category Behavioral

# Limit results
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py list --limit 20
```

### Export for Review

```bash
# Export all pending
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py export review.json

# Export by category
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py export behavioral.json --category Behavioral
```

### Import Decisions

```bash
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py import review.json
```

### Mark Individual Path

```bash
# Mark as mapped
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py mark \
  "BehavioralDNA.Posture" \
  --status mapped \
  --mapping "PaDNA.MovementDNA.Posture" \
  --notes "Maps to existing movement path"

# Mark as promoted
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py mark \
  "StyleContext.EraInference" \
  --status promoted \
  --notes "New PaDNA container for era/style context"
```

### Clear Resolved Paths

```bash
# Remove all mapped/promoted/rejected paths from registry
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py clear --confirm
```

## Path Categories

The system automatically categorizes paths:

- **Behavioral** - Behavior, posture, social patterns
- **Style** - Fashion, era, aesthetic markers
- **Personality** - Personality traits, social projection
- **Movement** - Posture, gestures, movement patterns
- **Context** - Settings, environments, situations
- **PaDNA** - Already using PaDNA prefix (edge cases)
- **Other** - Uncategorized

## Data Model

### Registry Structure

```json
{
  "schema_version": "1.0",
  "last_updated": "2025-10-03T12:26:13.826027",
  "statistics": {
    "total_unique_paths": 5,
    "total_occurrences": 10,
    "paths_by_category": {"Behavioral": 2, "Style": 3},
    "paths_by_status": {"pending": 5}
  },
  "quarantined_paths": {
    "BehavioralDNA.Posture": {
      "path": "BehavioralDNA.Posture",
      "first_seen": "2025-10-03T10:00:00",
      "last_seen": "2025-10-03T12:00:00",
      "occurrence_count": 15,
      "example_values": ["Confident posture"],
      "sources": ["photo-import", "manual-entry"],
      "users": ["user1", "user2"],
      "status": "pending",
      "notes": "",
      "suggested_mapping": null,
      "category": "Behavioral"
    }
  }
}
```

### Path Status Values

- **pending** - Not yet reviewed
- **mapped** - Decided to create alias to existing path
- **promoted** - Decided to create new PaDNA container
- **rejected** - Decided not to support

## Best Practices

### Regular Review

- Review quarantine weekly or monthly depending on import volume
- Prioritize paths with high occurrence counts
- Look for patterns across multiple users

### Decision Guidelines

1. **Frequency Matters** - Paths used by multiple users/sources warrant attention
2. **Semantic Clarity** - Path should have clear, unambiguous meaning
3. **Schema Fit** - Should fit logically within PaDNA structure
4. **Avoid Duplication** - Check if concept already exists under different name

### Maintaining Quality

- Document reasons for all decisions
- Keep rejected paths with notes for future reference
- Clear resolved paths periodically to keep registry focused
- Update path mappings immediately after marking as "mapped"

## Integration with AI

Future enhancement: Feed quarantined paths to AI for automatic suggestions:

```python
from PhotoRefinementCoach.src.quarantine_tracker import get_tracker

tracker = get_tracker()
pending = tracker.get_pending_paths()

# Send to AI for analysis
suggestions = ai_suggest_mappings(pending)

# Apply with human review
for suggestion in suggestions:
    tracker.mark_path_status(
        suggestion['path'],
        suggestion['status'],
        suggestion['notes'],
        suggestion['mapping']
    )
```

## Files and Locations

```
PhotoRefinementCoach/
├── src/
│   ├── quarantine_tracker.py      # Core tracking module
│   └── importer.py                 # Auto-logs quarantined items
├── scripts/
│   └── review_quarantine.py        # CLI review tool
├── data/
│   ├── quarantine_registry.json    # Persistent storage
│   └── quarantine_review.json      # Exported for review
└── docs/
    └── QUARANTINE_TRACKING.md      # This file
```

## Example Workflow

```bash
# 1. User imports data (automatically tracked)
# 2. Review what's been collected
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py stats

# 3. Export for review
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py export review.json

# 4. Edit review.json with decisions
# 5. Import decisions
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py import review.json

# 6. For mapped paths, add to path_mappings.yaml
# 7. For promoted paths, update traits_registry.yaml

# 8. Clear resolved paths
.venv/bin/python PhotoRefinementCoach/scripts/review_quarantine.py clear --confirm
```

## Troubleshooting

**Registry not updating?**
- Check file permissions on `quarantine_registry.json`
- Verify imports are actually completing (check for errors)
- Look for exceptions in `importer.py` quarantine tracking block

**Paths not being captured?**
- Ensure they're quarantined (not just validation errors)
- Check that reason includes "unmapped"
- Verify `record_quarantine()` is being called

**Tool errors?**
- Use correct Python interpreter: `.venv/bin/python`
- Check registry JSON is valid
- Review traceback for specific error

## Future Enhancements

- [ ] AI-powered path suggestion
- [ ] Web UI for review process
- [ ] Automatic frequency-based promotion
- [ ] Integration with schema version control
- [ ] Batch operations for similar paths
- [ ] Visualization of path relationships
