# ReDNA Backup Index

This document tracks all timestamped backups of the ReDNA workspace.

## Format

Each entry includes:
- **Timestamp**: UTC timestamp (YYYYMMDDTHHMMSSZ)
- **Tarball**: Backup file name
- **SHA256**: Checksum for integrity verification
- **Git Branch**: Associated release branch
- **Git Tag**: Associated release tag
- **Size**: Tarball size
- **Description**: Key features included in backup

## Backups

### 20251021T142201Z - Phase 10.2 Lock-In

- **Tarball**: `ReDNA_Phase10.2_20251021T142201Z.tar.gz`
- **SHA256**: `156a8141226dee35bbc02640bde3fd3da31ba0bd4fa8f7c0f4af2f8ce0b3c4e3`
- **Git Branch**: `release/phase10.2.20251021T142201Z`
- **Git Tag**: `v2.0.0-phase10.2.20251021T142201Z`
- **Size**: 5.3MB
- **Description**: Complete Phase 10.2 implementation including:
  - RR reference population system (SYNTHETIC/ACTUAL sources)
  - Synthetic universe recalibration (Phase 10.2.3)
  - Consent health endpoint + CI workflow
  - Auto-curiosity with LLM integration
  - Belief graph + Why-cards system
  - DevX RR Reference panel
  - Shape harmonizer for trait normalization
  - UCN/RR adapter with reference-percentile mode
  - 214 files changed, 139,884 insertions

**Contents:**
- Environment: Python/Node versions, pip freeze, .env, FlagsAndDefaults.json
- Core artifacts: seed_ontology.json, reference_pop/ (8 CDF files), users/ data
- Documentation: All markdown files, Intel/ directory
- Verification: Core API health, RR reference status

**Restore Command:**
```bash
tar -xzf backups/ReDNA_Phase10.2_20251021T142201Z.tar.gz -C /tmp/restore
rsync -a /tmp/restore/Phase10.2.20251021T142201Z/core/ data/
rsync -a /tmp/restore/Phase10.2.20251021T142201Z/env/.env .env
git checkout v2.0.0-phase10.2.20251021T142201Z
# Restart services
```

---

## Backup Procedure

To create a new backup, follow the procedure in [RELEASE_NOTES_v2.0.0-phase10.2.20251021T142201Z.md](../RELEASE_NOTES_v2.0.0-phase10.2.20251021T142201Z.md#rollback-procedure) or the backup script:

1. Quiesce services
2. Create timestamped backup directory
3. Capture environment (env vars, versions, .env, flags)
4. Copy core artifacts (ontology, reference_pop, users)
5. Copy documentation (docs/, Intel/)
6. Capture verification outputs (health endpoints)
7. Pack into tarball and generate SHA256
8. Create Git release branch and tag
9. Push to remote
10. Update this index

---

## Retention Policy

- **Keep indefinitely**: Major version releases (v2.0.0, v3.0.0, etc.)
- **Keep 90 days**: Minor version releases (v2.1.0, v2.2.0, etc.)
- **Keep 30 days**: Patch releases (v2.0.1, v2.0.2, etc.)
- **Keep 7 days**: Development backups (pre-release)

---

## Storage

- **Location**: `backups/` directory (local, not committed to Git)
- **Ignored by Git**: Ensured via `.gitignore` entry
- **Offsite Backup**: [Specify cloud storage location if applicable]

---

## Verification

To verify backup integrity:

```bash
shasum -a 256 -c backups/ReDNA_Phase10.2_20251021T142201Z.tar.gz.sha256
```

To inspect backup contents without extracting:

```bash
tar -tzf backups/ReDNA_Phase10.2_20251021T142201Z.tar.gz | less
```

---

## Notes

- Backups exclude `data/users/*/media/*` (large photo files)
- `.env` file included in backup but NOT committed to Git
- Synthetic reference populations (~3.4MB) included
- User data (JSONL files) included
