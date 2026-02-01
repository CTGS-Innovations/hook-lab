#!/bin/bash
# Hook Lab Test Runner
# Usage: ./run-test.sh <test-number>

set -e

LAB_DIR="/home/corey/hook-lab"
SETTINGS_FILE="$HOME/.claude/settings.local.json"
BACKUP_FILE="$LAB_DIR/results/settings-backup.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

show_help() {
    echo -e "${CYAN}Hook Lab Test Runner${NC}"
    echo ""
    echo "Usage: ./run-test.sh <test-number|command>"
    echo ""
    echo "Tests:"
    echo "  1  - Baseline silent command (should be FREE)"
    echo "  2  - Context injection (measure context cost)"
    echo "  3  - Command gate pattern"
    echo "  4  - Minimal agent (measure baseline agent cost)"
    echo "  5  - Conditional agent"
    echo "  6  - Permission block pattern"
    echo ""
    echo "Commands:"
    echo "  list      - Show available tests"
    echo "  backup    - Backup current settings"
    echo "  restore   - Restore backed up settings"
    echo "  clear     - Clear result logs"
    echo "  logs      - Show hook fire logs"
    echo "  trigger   - Create work gate (for conditional tests)"
    echo ""
}

backup_settings() {
    if [ -f "$SETTINGS_FILE" ]; then
        cp "$SETTINGS_FILE" "$BACKUP_FILE"
        echo -e "${GREEN}✓ Settings backed up${NC}"
    else
        echo -e "${YELLOW}No settings file to backup${NC}"
    fi
}

restore_settings() {
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$SETTINGS_FILE"
        echo -e "${GREEN}✓ Settings restored${NC}"
    else
        echo -e "${RED}✗ No backup found${NC}"
    fi
}

clear_logs() {
    rm -f "$LAB_DIR/results/"*.log
    rm -f "$LAB_DIR/results/work-gate"
    rm -f "$LAB_DIR/results/pending-task.json"
    echo -e "${GREEN}✓ Logs cleared${NC}"
}

show_logs() {
    if [ -f "$LAB_DIR/results/hook-fires.log" ]; then
        echo -e "${CYAN}=== Hook Fire Log ===${NC}"
        cat "$LAB_DIR/results/hook-fires.log"
    else
        echo -e "${YELLOW}No hook fires logged yet${NC}"
    fi
}

create_trigger() {
    echo '{"task": "test-task", "action": "log-hello"}' > "$LAB_DIR/results/pending-task.json"
    echo -e "${GREEN}✓ Work trigger created${NC}"
    echo "  File: $LAB_DIR/results/pending-task.json"
}

run_test() {
    local test_num=$1
    local test_file="$LAB_DIR/tests/0${test_num}-*.json"

    # Find the test file
    test_file=$(ls $test_file 2>/dev/null | head -1)

    if [ -z "$test_file" ] || [ ! -f "$test_file" ]; then
        echo -e "${RED}✗ Test $test_num not found${NC}"
        exit 1
    fi

    echo -e "${CYAN}=== Running Test $test_num ===${NC}"
    echo "Config: $test_file"
    echo ""

    # Show test description
    grep -E '"_comment"|"_theory"' "$test_file" | sed 's/.*: "/  /' | sed 's/",$//'

    echo ""
    echo -e "${YELLOW}Installing test settings...${NC}"

    # Backup current settings first
    backup_settings

    # Install test settings
    cp "$test_file" "$SETTINGS_FILE"
    echo -e "${GREEN}✓ Test settings installed${NC}"

    echo ""
    echo -e "${CYAN}Next steps:${NC}"
    echo "1. Start a NEW Claude session: ${GREEN}claude${NC}"
    echo "2. Send a test prompt: ${GREEN}Say hi${NC}"
    echo "3. Check hook fires: ${GREEN}./run-test.sh logs${NC}"
    echo "4. When done: ${GREEN}./run-test.sh restore${NC}"
    echo ""
}

# Make hooks executable
chmod +x "$LAB_DIR/hooks/"*.sh 2>/dev/null || true

# Create results dir
mkdir -p "$LAB_DIR/results"

# Parse command
case "${1:-help}" in
    help|--help|-h)
        show_help
        ;;
    list)
        echo -e "${CYAN}Available tests:${NC}"
        ls -1 "$LAB_DIR/tests/"*.json | while read f; do
            name=$(basename "$f")
            comment=$(grep '"_comment"' "$f" | sed 's/.*: "/  /' | sed 's/",$//')
            echo -e "  ${GREEN}$name${NC}"
            echo "$comment"
        done
        ;;
    backup)
        backup_settings
        ;;
    restore)
        restore_settings
        ;;
    clear)
        clear_logs
        ;;
    logs)
        show_logs
        ;;
    trigger)
        create_trigger
        ;;
    [1-6])
        run_test "$1"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
