#!/usr/bin/env python3
"""
Test 2: Context injection command hook
Hypothesis: This costs tokens = size of additionalContext
"""
import json
import sys
from datetime import datetime

# Read stdin
try:
    data = json.load(sys.stdin)
except:
    data = {}

# Log that we fired
with open("/home/corey/hook-lab/results/hook-fires.log", "a") as f:
    f.write(f"[{datetime.now().isoformat()}] context-inject fired\n")

# Return context - THIS should cost tokens
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": data.get("hook_event_name", "Unknown"),
        "additionalContext": "## Hook Test\n\nThis is injected context. X tokens."
    }
}))

sys.exit(0)
