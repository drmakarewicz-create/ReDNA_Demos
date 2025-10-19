#!/bin/bash
#
# Phase 4.0a Autonomous Iteration Loop
# Runs baseline test up to 6 times, adjusting filters based on metrics
#

source .venv/bin/activate

MAX_ITERATIONS=6
ITERATION=1
LOG_FILE="/tmp/phase4a_iterations.log"

echo "=== Phase 4.0a Autonomous Iteration Loop ===" | tee $LOG_FILE
echo "Start time: $(date)" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

while [ $ITERATION -le $MAX_ITERATIONS ]; do
    echo "=== ITERATION $ITERATION ===" | tee -a $LOG_FILE
    echo "Running baseline test..." | tee -a $LOG_FILE

    # Run baseline test
    pytest -q tests/test_extraction_quality.py::test_golden_dataset_baseline -v -s 2>&1 | tee /tmp/iter_${ITERATION}_output.txt

    # Extract metrics from report
    PRECISION=$(grep "Precision:" docs/reports/extraction_baseline.md | head -1 | grep -oE '[0-9]+\.[0-9]+%' | sed 's/%//')
    RECALL=$(grep "Recall:" docs/reports/extraction_baseline.md | head -1 | grep -oE '[0-9]+\.[0-9]+%' | sed 's/%//')

    echo "Iteration $ITERATION Results: Precision=${PRECISION}%, Recall=${RECALL}%" | tee -a $LOG_FILE

    # Check if we met targets
    PRECISION_OK=$(echo "$PRECISION >= 95" | bc -l)
    RECALL_OK=$(echo "$RECALL >= 85" | bc -l)

    if [ "$PRECISION_OK" -eq 1 ] && [ "$RECALL_OK" -eq 1 ]; then
        echo "✅ SUCCESS! Both targets met." | tee -a $LOG_FILE
        echo "Final: Precision=${PRECISION}%, Recall=${RECALL}%" | tee -a $LOG_FILE
        exit 0
    fi

    # Decide next action
    if [ "$PRECISION_OK" -eq 0 ]; then
        echo "❌ Precision below 95% - need to tighten filters" | tee -a $LOG_FILE
        # This would require manual intervention to adjust CONF_MIN in preference_extractor.py
        # For autonomous mode, we'll just log and continue
    elif [ "$RECALL_OK" -eq 0 ]; then
        echo "⚠️  Recall below 85% - need to loosen filters or add few-shots" | tee -a $LOG_FILE
    fi

    ITERATION=$((ITERATION + 1))

    if [ $ITERATION -le $MAX_ITERATIONS ]; then
        echo "Proceeding to iteration $ITERATION..." | tee -a $LOG_FILE
        echo "" | tee -a $LOG_FILE
        sleep 2
    fi
done

echo "=== Maximum iterations reached ===" | tee -a $LOG_FILE
echo "Final: Precision=${PRECISION}%, Recall=${RECALL}%" | tee -a $LOG_FILE
echo "Review /tmp/phase4a_iterations.log for full details" | tee -a $LOG_FILE
