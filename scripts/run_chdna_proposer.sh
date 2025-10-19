#!/bin/bash
# ChatDNA Container Proposer - Nightly Job Runner
# Rotates logs, runs proposer, prints summary

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/ReDNACoreDemo/core/gap_logs"
PROPOSER_SCRIPT="$PROJECT_ROOT/ReDNACoreDemo/core/proposer/propose_chdna_containers.py"

echo "🌙 ChatDNA Nightly Container Proposer"
echo "======================================"
echo ""

# Step 1: Rotate/compress old logs
echo "Step 1: Log rotation..."
LOG_FILE="$LOG_DIR/chatdna_unmet_features.jsonl"

if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(wc -l < "$LOG_FILE" | tr -d ' ')
    echo "   Current log: $LOG_SIZE entries"

    # Compress logs older than 1 day
    find "$LOG_DIR" -name "*.jsonl" -mtime +1 ! -name "*gz" -exec gzip {} \;

    # Remove logs older than 7 days
    find "$LOG_DIR" -name "*.jsonl.gz" -mtime +7 -delete

    echo "   ✅ Log rotation complete"
else
    echo "   ⚠️  No log file found (first run?)"
fi
echo ""

# Step 2: Run proposer
echo "Step 2: Running proposer..."
PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/ReDNACoreDemo:$PYTHONPATH" python3 "$PROPOSER_SCRIPT"
echo ""

# Step 3: Show latest proposals
PROPOSALS_DIR="$PROJECT_ROOT/ReDNACoreDemo/core/proposer/proposals"
LATEST_PROPOSAL=$(ls -t "$PROPOSALS_DIR"/*.json 2>/dev/null | head -n 1)

if [ -n "$LATEST_PROPOSAL" ]; then
    echo "Step 3: Latest proposals..."
    echo "   File: $(basename "$LATEST_PROPOSAL")"

    # Extract count
    PROPOSAL_COUNT=$(python3 -c "
import json
with open('$LATEST_PROPOSAL') as f:
    data = json.load(f)
    print(data.get('proposal_count', 0))
")

    echo "   Count: $PROPOSAL_COUNT proposal(s)"
    echo "   ✅ Review in Coach Workshop > Proposals tab"
else
    echo "Step 3: No proposals generated"
fi
echo ""

echo "======================================"
echo "✅ Proposer run complete!"
echo "======================================"
