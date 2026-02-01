#!/bin/bash
# EXPERIMENTAL: Manipulate settings.local.json to control agent execution
#
# Theory: If we can break/fix settings.local.json, we can:
# - Disable agent hooks when no work pending (FREE)
# - Enable agent hooks only when work exists (PAY only when needed)
#
# This is speculative - Claude Code might:
# - Cache settings at startup (won't work)
# - Re-read settings per-hook (might work)
# - Detect corruption and fail (unknown behavior)

SETTINGS_FILE="/home/corey/hook-lab/.claude/settings.local.json"
BACKUP_FILE="/home/corey/hook-lab/results/settings-backup.json"
GATE_FILE="/home/corey/hook-lab/results/work-gate"
LOG_FILE="/home/corey/hook-lab/results/hook-fires.log"

# Read stdin (discard)
cat > /dev/null

echo "[$(date -Iseconds)] settings-breaker fired" >> "$LOG_FILE"

# Check if we should enable or disable agents
if [ -f "$GATE_FILE" ]; then
    # Work pending - restore valid settings (enable agents)
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$SETTINGS_FILE"
        echo "[$(date -Iseconds)] settings-breaker: restored valid settings" >> "$LOG_FILE"
    fi
else
    # No work - break settings (disable agents?)
    # Option 1: Add syntax error
    # Option 2: Remove agent hooks section
    # Option 3: Set agent timeout to 0

    # For now, just log - this is experimental
    echo "[$(date -Iseconds)] settings-breaker: would break settings here" >> "$LOG_FILE"
fi

exit 0
