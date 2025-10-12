#!/usr/bin/env bash
set -euo pipefail

# ReDNA Backup Retention & Cleanup Script
# Manages backup retention with dry-run safety and configurable policies
# Usage:
#   retention_cleanup.sh              # Dry-run (shows what would be deleted)
#   retention_cleanup.sh --apply      # Actually delete old backups
#   retention_cleanup.sh --apply --force  # Delete even if <24h old (keeps newest)

# Configuration via environment variables with sane defaults
BACKUP_LOCAL_DIR="${REDNA_BACKUP_LOCAL_DIR:-$HOME/Documents/ReDNA_Demos/backups}"
BACKUP_ICLOUD_DIR="${REDNA_BACKUP_ICLOUD_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups}"
LOCAL_RETENTION_DAYS="${REDNA_BACKUP_LOCAL_DAYS:-30}"
ICLOUD_RETENTION_DAYS="${REDNA_BACKUP_ICLOUD_DAYS:-60}"

# Parse command-line arguments
DRY_RUN=true
FORCE_DELETE=false

for arg in "$@"; do
    case $arg in
        --apply)
            DRY_RUN=false
            ;;
        --force)
            FORCE_DELETE=true
            ;;
        --help|-h)
            cat << 'EOF'
ReDNA Backup Retention & Cleanup

Usage:
  retention_cleanup.sh [OPTIONS]

Options:
  (none)      Dry-run mode (default) - shows what would be deleted
  --apply     Actually delete old backups
  --force     Allow deletion of files <24h old (still keeps newest)
  --help      Show this help message

Environment Variables:
  REDNA_BACKUP_LOCAL_DIR      Local backup directory (default: ~/Documents/ReDNA_Demos/backups)
  REDNA_BACKUP_ICLOUD_DIR     iCloud backup directory
  REDNA_BACKUP_LOCAL_DAYS     Local retention days (default: 30)
  REDNA_BACKUP_ICLOUD_DAYS    iCloud retention days (default: 60)

Examples:
  # Show what would be deleted
  bash scripts/backups/retention_cleanup.sh

  # Actually delete old backups
  bash scripts/backups/retention_cleanup.sh --apply

  # Force deletion of files <24h old (keeps newest)
  bash scripts/backups/retention_cleanup.sh --apply --force

Exit Codes:
  0 - Success (green)
  2 - Warnings (yellow)
  3 - Errors (red)
EOF
            exit 0
            ;;
    esac
done

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Status tracking
EXIT_CODE=0
WARNINGS=0
ERRORS=0

echo "🗑️  ReDNA Backup Retention & Cleanup"
echo "===================================="
echo ""
if $DRY_RUN; then
    echo -e "${BLUE}Mode: DRY-RUN (no files will be deleted)${NC}"
else
    echo -e "${YELLOW}Mode: APPLY (files will be deleted)${NC}"
fi
if $FORCE_DELETE; then
    echo -e "${YELLOW}Force mode enabled (allows <24h deletion, keeps newest)${NC}"
fi
echo ""
echo "Configuration:"
echo "  Local retention:  $LOCAL_RETENTION_DAYS days"
echo "  iCloud retention: $ICLOUD_RETENTION_DAYS days"
echo ""

# Function to get file modification time (cross-platform)
get_file_mtime() {
    local file="$1"
    if [ "$(uname)" = "Darwin" ]; then
        stat -f %m "$file" 2>/dev/null || echo "0"
    else
        stat -c %Y "$file" 2>/dev/null || echo "0"
    fi
}

# Function to get human-readable age
get_age_days() {
    local file="$1"
    local mtime=$(get_file_mtime "$file")
    local now=$(date +%s)
    local age_seconds=$((now - mtime))
    local age_days=$((age_seconds / 86400))
    echo "$age_days"
}

# Function to get total size of files
get_total_size() {
    local files=("$@")
    if [ ${#files[@]} -eq 0 ]; then
        echo "0"
        return
    fi
    du -ch "${files[@]}" 2>/dev/null | grep total | cut -f1 || echo "0"
}

# Function to find newest file in directory
find_newest_file() {
    local dir="$1"
    local pattern="$2"

    if [ ! -d "$dir" ]; then
        echo ""
        return
    fi

    # Find all matching files and get the newest by modification time
    find "$dir" -name "$pattern" -type f 2>/dev/null | while read -r file; do
        echo "$(get_file_mtime "$file") $file"
    done | sort -rn | head -1 | cut -d' ' -f2-
}

# Function to scan directory and find candidates for deletion
scan_dir() {
    local dir="$1"
    local retention_days="$2"
    local label="$3"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}$label${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ ! -d "$dir" ]; then
        echo -e "${YELLOW}⚠️  Directory not found: $dir${NC}"
        ((WARNINGS++))
        EXIT_CODE=2
        echo ""
        return
    fi

    local pattern="redna_backup_*.tar.gz"
    local all_files=()
    local candidates=()
    local newest_file=""

    # Find all backup files
    while IFS= read -r file; do
        all_files+=("$file")
    done < <(find "$dir" -name "$pattern" -type f 2>/dev/null)

    local total_count=${#all_files[@]}

    if [ $total_count -eq 0 ]; then
        echo "  No backups found"
        echo ""
        return
    fi

    # Find newest file (always keep)
    newest_file=$(find_newest_file "$dir" "$pattern")

    # Find candidates older than retention days
    local current_time=$(date +%s)
    local cutoff_time=$((current_time - (retention_days * 86400)))

    for file in "${all_files[@]}"; do
        local mtime=$(get_file_mtime "$file")
        local age_days=$(get_age_days "$file")

        # Skip if this is the newest file
        if [ "$file" = "$newest_file" ]; then
            continue
        fi

        # Check if older than retention period
        if [ "$mtime" -lt "$cutoff_time" ]; then
            # Check 24h safety unless force mode
            if ! $FORCE_DELETE; then
                local age_hours=$((age_days * 24))
                if [ "$age_hours" -lt 24 ]; then
                    continue  # Skip files less than 24h old unless --force
                fi
            fi
            candidates+=("$file")
        fi
    done

    local candidate_count=${#candidates[@]}
    local keep_count=$((total_count - candidate_count))

    # Calculate sizes
    local total_size="0"
    local candidate_size="0"

    if [ $total_count -gt 0 ]; then
        total_size=$(get_total_size "${all_files[@]}")
    fi

    if [ $candidate_count -gt 0 ]; then
        candidate_size=$(get_total_size "${candidates[@]}")
    fi

    # Get oldest and newest timestamps
    local oldest_file=""
    local newest_age="0"
    local oldest_age="0"

    if [ -n "$newest_file" ]; then
        newest_age=$(get_age_days "$newest_file")
    fi

    # Find oldest file
    for file in "${all_files[@]}"; do
        local age=$(get_age_days "$file")
        if [ -z "$oldest_file" ] || [ "$age" -gt "$oldest_age" ]; then
            oldest_file="$file"
            oldest_age="$age"
        fi
    done

    # Print summary
    echo "  📊 Summary:"
    echo "     Total backups: $total_count (size: $total_size)"
    echo "     Newest backup: ${newest_age}d ago"
    echo "     Oldest backup: ${oldest_age}d ago"
    echo "     Keep: $keep_count backups"

    if [ $candidate_count -gt 0 ]; then
        if $DRY_RUN; then
            echo -e "     ${YELLOW}Would delete: $candidate_count backups (size: $candidate_size)${NC}"
        else
            echo -e "     ${RED}Will delete: $candidate_count backups (size: $candidate_size)${NC}"
        fi
        echo ""
        echo "  📋 Candidates for deletion:"
        for file in "${candidates[@]}"; do
            local age=$(get_age_days "$file")
            local size=$(du -h "$file" 2>/dev/null | cut -f1 || echo "N/A")
            local basename=$(basename "$file")
            echo "     - $basename (${age}d old, $size)"
        done
    else
        echo -e "     ${GREEN}✅ No files to delete${NC}"
    fi

    echo ""

    # Store candidates in global array for deletion
    if [ $candidate_count -gt 0 ] && ! $DRY_RUN; then
        for file in "${candidates[@]}"; do
            DELETE_QUEUE+=("$file")
        done
    fi

    # Export stats for reporting
    echo "$total_count|$keep_count|$candidate_count|$candidate_size|$newest_age|$oldest_age" > "/tmp/retention_${label// /_}.stats"
}

# Function to delete candidates
delete_candidates() {
    local files=("$@")
    local deleted=0
    local failed=0

    if [ ${#files[@]} -eq 0 ]; then
        return
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${RED}Deleting Files${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    for file in "${files[@]}"; do
        local basename=$(basename "$file")
        if rm -f "$file" 2>/dev/null; then
            echo -e "  ${GREEN}✅${NC} Deleted: $basename"
            ((deleted++))
        else
            echo -e "  ${RED}❌${NC} Failed to delete: $basename"
            ((failed++))
            ((ERRORS++))
            EXIT_CODE=3
        fi
    done

    echo ""
    echo "  Summary: $deleted deleted, $failed failed"
    echo ""
}

# Main execution
DELETE_QUEUE=()

# Scan local backups
scan_dir "$BACKUP_LOCAL_DIR" "$LOCAL_RETENTION_DAYS" "Local Backups"

# Scan iCloud backups
scan_dir "$BACKUP_ICLOUD_DIR" "$ICLOUD_RETENTION_DAYS" "iCloud Backups"

# Delete if in apply mode
if ! $DRY_RUN && [ ${#DELETE_QUEUE[@]} -gt 0 ]; then
    delete_candidates "${DELETE_QUEUE[@]}"
fi

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Final Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if $DRY_RUN; then
    echo -e "${BLUE}Mode: DRY-RUN${NC}"
    echo "  No files were deleted"
    echo "  Run with --apply to actually delete files"
else
    echo -e "${YELLOW}Mode: APPLY${NC}"
    echo "  Files have been deleted"
fi

echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}Status: ❌ ERRORS ($ERRORS)${NC}"
    EXIT_CODE=3
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Status: ⚠️  WARNINGS ($WARNINGS)${NC}"
    EXIT_CODE=2
else
    echo -e "${GREEN}Status: ✅ SUCCESS${NC}"
    EXIT_CODE=0
fi

echo ""
echo "Exit code: $EXIT_CODE"
echo ""

exit $EXIT_CODE
