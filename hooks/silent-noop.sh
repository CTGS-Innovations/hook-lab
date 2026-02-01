#!/bin/bash
# Test 1: Silent no-op command hook
# Hypothesis: This costs 0 tokens

# Read stdin (required - hook provides JSON)
cat > /dev/null

# Log that we fired (for verification)
echo "[$(date -Iseconds)] silent-noop fired" >> /home/corey/hook-lab/results/hook-fires.log

# Exit silently - no stdout, exit 0
exit 0
