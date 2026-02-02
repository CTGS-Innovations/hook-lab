#!/bin/bash
# Fully automated hook lab test runner
# Runs all tests without user intervention

set -e

LAB_DIR="/home/corey/hook-lab"
STATE_FILE="$LAB_DIR/results/test-state.json"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

cd "$LAB_DIR"

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  AUTOMATED HOOK LAB TEST RUNNER${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Full reset - clear old sessions too
python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
state['step'] = 0
state['phase'] = 'ready'
state['sessions'] = {}
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"
rm -f "$LAB_DIR/.claude/settings.local.json" "$LAB_DIR/results/hook-fires.log"
echo -e "${GREEN}Reset complete - cleared all previous sessions${NC}"

# Get total test count
total=$(python3 -c "import json; print(len(json.load(open('$STATE_FILE'))['tests']))")

for ((i=0; i<total; i++)); do
    # Setup next test
    ./test-runner.sh next

    test_name=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['tests'][$i]['name'])")
    echo -e "${YELLOW}Running claude for: $test_name${NC}"

    # Run claude with "hi" in print mode (sends message, prints response, exits)
    # Run from LAB_DIR so sessions go to the right project folder
    timeout 120s claude -p "hi" 2>/dev/null || true

    echo -e "${GREEN}Done with $test_name${NC}"
    echo ""
done

# Record final test
./test-runner.sh next

echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  AUTOMATED RUN COMPLETE${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
