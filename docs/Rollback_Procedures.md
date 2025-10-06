
# Rollback Procedures

**Last Updated:** 2025-10-04

This document describes rollback paths for major state changes in the ReDNA system.

---

## 🎯 Overview

All critical system changes maintain rollback capability through:
1. **Before/After Logging** - Changes logged with complete before state
2. **Backup Files** - Automatic `.bak` creation before writes
3. **Audit Trails** - JSONL append-only logs for change history
4. **Provenance Tracking** - All changes tagged with source and timestamp

---

## 📋 Rollback-Enabled Components

### 1. RR Baseline Configurations

**Location:** `ReDNACoreDemo/data/config/rr_baselines.yaml`
**Audit Log:** `data/dev_logs/rr_baselines_changes.log`
**Backup:** `rr_baselines.yaml.bak`

#### Rollback Procedure

```python
from ExplorerDev import rr_baseline_utils
from ExplorerDev.write_utils import WriteProtectContext

# 1. Load change history
changes = rr_baseline_utils.load_change_log(repo_root, limit=10)

# 2. Select target change (e.g., change #3)
target_change = changes[2]  # 0-indexed
before_state = target_change["before"]

# 3. Restore (requires write_protect=false)
context = WriteProtectContext(write_protect=False)
rr_baseline_utils.save_demo_baselines(
    repo_root,
    before_state,
    context,
    previous=None,  # Will log this rollback
)

# 4. Verify
current = rr_baseline_utils.load_demo_config(repo_root)
assert current == before_state, "Rollback verification failed"
```

**Safety Checks:**
- ✅ Automatic backup before write
- ✅ Change logged to audit trail
- ✅ Validation on load
- ✅ `WRITE_PROTECT` guard

---

### 2. CReDNA Registry

**Location:** `data/dev_config/credna/registry.yaml`
**Audit Log:** `data/dev_logs/credna_import_history.jsonl`
**Backup:** `registry.yaml.bak`

#### Rollback Procedure

```python
from ExplorerDev.credna import credna_store
from ExplorerDev.write_utils import WriteProtectContext

# 1. Load backup directly
backup_path = credna_store.registry_path(repo_root).with_suffix(".yaml.bak")
import yaml
with backup_path.open("r") as f:
    previous_registry = yaml.safe_load(f)

# 2. Restore
context = WriteProtectContext(write_protect=False)
credna_store.save_registry(previous_registry, context)

# 3. Verify
current = credna_store.load_registry(context)
assert current["schema_version"] == previous_registry["schema_version"]
```

**Safety Checks:**
- ✅ Versioning with `schema_version`
- ✅ Automatic backup
- ✅ Import validation before save
- ✅ Write-protect mode

---

### 3. User ReDNA State

**Location:** `data/storage/users/{user_id}/resolved.json`
**Audit Log:** Holistic review in `last_holistic.json`
**Backup:** `resolved.json.bak`

#### Rollback Procedure

```python
from ReDNACoreDemo.core import storage

# 1. Load backup
user_dir = storage.get_user_dir("user123")
backup_path = user_dir / "resolved.json.bak"

import json
with backup_path.open("r") as f:
    previous_resolved = json.load(f)

# 2. Restore (also need evidence and observations)
evidence_backup = user_dir / "evidence.jsonl.bak"
obs_backup = user_dir / "observations.json.bak"

with evidence_backup.open("r") as f:
    previous_evidence = json.load(f)

with obs_backup.open("r") as f:
    previous_obs = json.load(f)

# 3. Write (creates new backup of current state)
storage.write_user_state(
    "user123",
    previous_resolved,
    previous_evidence,
    previous_obs,
)
```

**Safety Checks:**
- ✅ Holistic review timestamps tracked
- ✅ Atomic write with temp file
- ✅ Backup before overwrite
- ✅ Provenance in traits

---

### 4. Nudge Store State

**Location:** `data/dev_mailbox/{user_id}/inbox.json`
**Audit Log:** `data/dev_logs/nudge_actions.jsonl`
**Backup:** `inbox.json.bak`

#### Rollback Procedure

```python
from ExplorerFinal.core import nudge_store

# Nudges are append-only (archive) + mutable inbox
# Rollback = restore from backup + replay archive

# 1. Load backup inbox
import json
from pathlib import Path

user_mailbox = Path("data/dev_mailbox/user123")
backup_path = user_mailbox / "inbox.json.bak"

with backup_path.open("r") as f:
    previous_inbox = json.load(f)

# 2. Write directly (requires write_protect=False in production)
(user_mailbox / "inbox.json").write_text(
    json.dumps(previous_inbox, indent=2)
)

# 3. Verify by listing
inbox = nudge_store.list_inbox("user123", write_protect=False)
assert len(inbox) == len(previous_inbox)
```

**Safety Checks:**
- ✅ Archive never deleted (append-only)
- ✅ Actions logged separately
- ✅ Duplicate detection prevents re-enqueue
- ✅ Rate limiting

---

### 5. Head Coach Ops Schedule

**Location:** `data/dev_mailbox/{user_id}/ops.json`
**Audit Log:** `data/dev_logs/head_coach_ops_changes.jsonl`
**Backup:** `ops.json.bak`

#### Rollback Procedure

```python
from ExplorerFinal.core import nudge_store

# 1. Load from backup
backup_path = Path("data/dev_mailbox/user123/ops.json.bak")
with backup_path.open("r") as f:
    previous_ops = json.load(f)

# 2. Restore using API
from ExplorerFinal.core.nudge_store import _save_ops

_save_ops("user123", previous_ops, write_protect=False)

# 3. Verify
current_ops = nudge_store.load_ops("user123", write_protect=False)
assert len(current_ops["entries"]) == len(previous_ops["entries"])
```

**Safety Checks:**
- ✅ Entry IDs stable across saves
- ✅ Schema versioning
- ✅ Next-run recalculation on load

---

## ⚠️ Rollback Best Practices

### Before Rollback

1. **Verify Current State** - Understand what will be lost
2. **Check Audit Log** - Confirm target rollback point
3. **Create Manual Backup** - Extra safety layer
4. **Disable WRITE_PROTECT** - Required for writes

```bash
export WRITE_PROTECT=false
```

5. **Stop Services** - Prevent concurrent writes

### During Rollback

1. **Single Component at a Time** - Don't rollback multiple systems simultaneously
2. **Verify After Each Step** - Load and inspect restored state
3. **Log the Rollback** - Document why and when

### After Rollback

1. **Re-enable WRITE_PROTECT** - Restore safety

```bash
export WRITE_PROTECT=true
```

2. **Verify System Health** - Run smoke tests
3. **Monitor for Issues** - Watch logs for cascading problems
4. **Document Incident** - Record what happened and resolution

---

## 🔐 Safety Mechanisms

### Automatic Backup Strategy

All critical files use this pattern:

```python
def _write_json_array(path: Path, rows: Sequence[Any]) -> None:
    # 1. Create temp file
    tmp_path = path.with_suffix(".tmp")

    # 2. Backup existing
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)

    # 3. Write to temp
    with tmp_path.open("w") as f:
        json.dump(list(rows), f, indent=2)

    # 4. Atomic rename
    os.replace(tmp_path, path)
```

**Benefits:**
- ✅ Never corrupts original on failure
- ✅ Always have last-known-good backup
- ✅ Atomic operation prevents partial writes

### Audit Trail Format

All changes logged as:

```json
{
  "timestamp": "2025-10-04T12:34:56Z",
  "action": "update_rr_baselines",
  "user": "admin",
  "before": { "defaults": {"mean_ucn": 0.45} },
  "after": { "defaults": {"mean_ucn": 0.50} },
  "reason": "Demo configuration update"
}
```

**Append-Only** - Never delete audit entries

---

## 🚨 Emergency Rollback

If system is in critical state and automated rollback fails:

### Manual Restore from Backup

```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos

# Example: Restore RR baselines
cp ReDNACoreDemo/data/config/rr_baselines.yaml.bak \
   ReDNACoreDemo/data/config/rr_baselines.yaml

# Example: Restore user state
cp data/storage/users/demo_user/resolved.json.bak \
   data/storage/users/demo_user/resolved.json
```

### Full System Restore from iCloud Backup

```bash
# Use existing backup script
./quick_backup_to_icloud.sh

# Locate backup in iCloud
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups

# Identify target backup (by timestamp)
ls -lt | head -10

# Restore entire directory
cp -r backup_YYYYMMDD_HHMMSS/* /Users/davidmakarewicz/Documents/ReDNA_Demos/data/
```

---

## 📊 Rollback Testing

Test rollback procedures regularly:

```bash
# Run with WRITE_PROTECT=true first (dry run)
export WRITE_PROTECT=true
python scripts/test_rollback.py

# Then test actual rollback in dev environment
export WRITE_PROTECT=false
python scripts/test_rollback.py --execute
```

---

## 📞 Support

If rollback procedures fail:
1. Check `data/dev_logs/` for audit trails
2. Review `.bak` files for restore candidates
3. Consult iCloud backups for disaster recovery
4. Document issue for procedure improvement

---

**End of Rollback Procedures**
