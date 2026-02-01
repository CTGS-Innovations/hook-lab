#!/bin/bash
# Gate reader: Check gate and conditionally output to trigger agent
# This is the decision point - output something or stay silent

GATE_FILE="/home/corey/hook-lab/results/work-gate"
TASK_FILE="/home/corey/hook-lab/results/pending-task.json"
LOG_FILE="/home/corey/hook-lab/results/hook-fires.log"

# Read stdin (discard)
cat > /dev/null

# Log
echo "[$(date -Iseconds)] gate-reader fired" >> "$LOG_FILE"

# Check gate
if [ -f "$GATE_FILE" ]; then
    # Gate exists - we need to trigger the agent somehow
    #
    # OPTION A: Output context that includes the task
    #   - Costs tokens for the context
    #   - Agent sees it in additionalContext
    #
    # OPTION B: Output JSON that signals agent to read task file
    #   - Minimal token cost
    #   - Agent reads task file itself
    #
    # OPTION C: Do nothing, let separate agent hook read gate
    #   - But agent hooks run in parallel...

    TASK=$(cat "$TASK_FILE" 2>/dev/null || echo '{}')

    # Clean up gate (one-shot)
    rm -f "$GATE_FILE"
    rm -f "$TASK_FILE"

    echo "[$(date -Iseconds)] gate-reader: executing task" >> "$LOG_FILE"

    # Output minimal signal - agent will do the work
    # This is the token cost we're measuring
    echo "{\"hookSpecificOutput\": {\"additionalContext\": \"TASK: $TASK\"}}"
else
    echo "[$(date -Iseconds)] gate-reader: no gate, silent exit" >> "$LOG_FILE"
    # No gate - stay silent = FREE
fi

exit 0
