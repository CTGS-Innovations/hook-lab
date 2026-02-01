#!/bin/bash
# Gate checker: Check if work is pending, set up for agent
# Part of the zero-cost scheduler pattern

GATE_FILE="/home/corey/hook-lab/results/work-gate"
TASK_FILE="/home/corey/hook-lab/results/pending-task.json"
LOG_FILE="/home/corey/hook-lab/results/hook-fires.log"

# Read stdin (discard)
cat > /dev/null

# Log
echo "[$(date -Iseconds)] gate-checker fired" >> "$LOG_FILE"

# Check if work is pending (simulated via file existence)
if [ -f "$TASK_FILE" ]; then
    # Work pending - create gate for next hook
    echo "WORK_PENDING" > "$GATE_FILE"
    echo "[$(date -Iseconds)] gate-checker: work pending, gate created" >> "$LOG_FILE"
else
    # No work - remove gate if exists
    rm -f "$GATE_FILE"
    echo "[$(date -Iseconds)] gate-checker: no work" >> "$LOG_FILE"
fi

# Always exit silently - no stdout = FREE
exit 0
