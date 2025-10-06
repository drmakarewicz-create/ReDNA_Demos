# Old Versions Archive

**Date Archived:** 2025-10-04
**Reason:** Cleanup of broken backups and timestamped directories

---

## Archived Directories

### ExplorerFinal_broken_1758381738
- **Archived:** 2025-10-04
- **Date Created:** 2024-09-24 (inferred from timestamp)
- **Reason:** Broken backup of ExplorerFinal
- **Status:** Non-functional backup
- **Active Replacement:** `ExplorerFinal/` (in root)

### 2025-09-19_20-38-36
- **Archived:** 2025-10-04
- **Date Created:** 2025-09-19 20:38:36
- **Reason:** Timestamped backup directory (unclear origin)
- **Status:** Legacy backup
- **Notes:** Check contents if recovery needed

---

## Recovery Instructions

If any archived directory is needed:

1. Check what the directory contains:
   ```bash
   ls -la archive/old_versions/[directory-name]
   ```

2. If specific files are needed, copy them out:
   ```bash
   cp archive/old_versions/[directory-name]/[file] [destination]
   ```

3. **DO NOT** restore entire directories without reviewing contents

---

## Active Codebase Locations

| Old Backup | Current Active Location |
|------------|-------------------------|
| `ExplorerFinal_broken_*` | `ExplorerFinal/` (root) |

---

*For questions, consult Core_Benchmarks_Roadmap.md or Legacy_Cleanup_Audit.md*
