#!/bin/bash
# Hook Lab Test Runner - Simple state machine
# Just run: ./test-runner.sh next

set -e

LAB_DIR="/home/corey/hook-lab"
SETTINGS_FILE="$LAB_DIR/.claude/settings.local.json"
STATE_FILE="$LAB_DIR/results/test-state.json"
HOOK_FIRES="$LAB_DIR/results/hook-fires.log"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

mkdir -p "$LAB_DIR/.claude" "$LAB_DIR/results"

# Get latest hook-lab session ID
get_latest_session() {
    local sessions_dir="$HOME/.claude/projects/-home-corey-hook-lab"
    if [ -d "$sessions_dir" ]; then
        ls -t "$sessions_dir"/*.jsonl 2>/dev/null | head -1 | xargs -r basename | sed 's/.jsonl$//'
    fi
}

# Read state with Python
read_state() {
    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
print(state.get('$1', ''))
"
}

# The main next command
do_next() {
    local step=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['step'])")
    local phase=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['phase'])")
    local total=$(python3 -c "import json; print(len(json.load(open('$STATE_FILE'))['tests']))")

    # If we're awaiting record, record first then advance
    if [ "$phase" = "awaiting_record" ]; then
        local test_name=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['tests'][$step]['name'])")
        local session_id=$(get_latest_session)

        if [ -z "$session_id" ]; then
            echo -e "${YELLOW}No new session found. Did you run claude and say 'hi'?${NC}"
            echo -e "Restart claude, say hi, exit, then run ./test-runner.sh next"
            exit 1
        fi

        # Record it
        python3 -c "
import json
from datetime import datetime
with open('$STATE_FILE') as f:
    state = json.load(f)
state['sessions']['$test_name'] = {
    'session_id': '$session_id',
    'timestamp': datetime.now().isoformat()
}
state['step'] = $step + 1
state['phase'] = 'ready'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"
        echo -e "${GREEN}✓ Recorded $test_name${NC}"

        # Quick stats
        "$LAB_DIR/analyze-hooks.py" "$session_id" 2>/dev/null | grep -E "(Input tokens|Output tokens)" | head -2
        echo ""

        # Update step for next iteration
        step=$((step + 1))
    fi

    # Check if done
    if [ "$step" -ge "$total" ]; then
        echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  ALL TESTS COMPLETE!${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "Run comparisons:"
        echo -e "  ./test-runner.sh compare baseline test1"
        echo -e "  ./test-runner.sh compare baseline test2"
        echo -e "  etc."
        exit 0
    fi

    # Setup next test
    local test_name=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['tests'][$step]['name'])")
    local test_config=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['tests'][$step]['config'] or '')")
    local test_desc=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['tests'][$step]['desc'])")
    local remaining=$((total - step))

    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  TEST: $test_name - $test_desc${NC}"
    echo -e "${CYAN}  ($remaining of $total remaining)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

    # Install config (or remove for baseline)
    if [ -z "$test_config" ]; then
        rm -f "$SETTINGS_FILE"
        echo -e "${DIM}Config: none (baseline)${NC}"
    else
        cp "$LAB_DIR/tests/$test_config" "$SETTINGS_FILE"
        echo -e "${DIM}Config: $test_config${NC}"
    fi
    rm -f "$HOOK_FIRES"

    # Mark awaiting
    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
state['phase'] = 'awaiting_record'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"

    echo ""
    echo -e "${YELLOW}→ claude, hi, /exit, ./t${NC}"
    echo ""
}

# Compare two tests
compare_tests() {
    local test1="$1"
    local test2="$2"

    local session1=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['sessions'].get('$test1',{}).get('session_id',''))")
    local session2=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['sessions'].get('$test2',{}).get('session_id',''))")

    if [ -z "$session1" ] || [ -z "$session2" ]; then
        echo "Missing session for $test1 or $test2"
        exit 1
    fi

    "$LAB_DIR/analyze-hooks.py" --compare "$session1" "$session2"
}

# Show status
show_status() {
    local step=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['step'])")
    local phase=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['phase'])")
    local total=$(python3 -c "import json; print(len(json.load(open('$STATE_FILE'))['tests']))")

    echo -e "${CYAN}Step $step of $total, phase: $phase${NC}"
    echo ""
    echo "Recorded sessions:"
    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
for name, data in state.get('sessions', {}).items():
    print(f'  {name}: {data[\"session_id\"][:8]}...')
"
}

# Reset to start
do_reset() {
    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
state['step'] = 0
state['phase'] = 'ready'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"
    rm -f "$SETTINGS_FILE" "$HOOK_FIRES"
    echo -e "${GREEN}Reset to beginning${NC}"
}

case "${1:-next}" in
    next)
        do_next
        ;;
    compare)
        compare_tests "$2" "$3"
        ;;
    status)
        show_status
        ;;
    reset)
        do_reset
        ;;
    *)
        echo "Usage: ./test-runner.sh [next|status|reset|compare A B]"
        ;;
esac
