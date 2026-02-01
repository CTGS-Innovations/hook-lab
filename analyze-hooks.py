#!/usr/bin/env python3
"""
Hook Cost Analyzer for Hook Lab
Analyzes Claude Code sessions to isolate and measure hook-specific token costs.

Usage:
    ./analyze-hooks.py                    # Analyze latest hook-lab session
    ./analyze-hooks.py <session-id>       # Analyze specific session
    ./analyze-hooks.py --compare <s1> <s2> # Compare baseline vs hook session
    ./analyze-hooks.py --baseline         # Show baseline (no-hook) sessions

Hook Types:
    - command: Shell scripts, cost = additionalContext/systemMessage tokens added
    - prompt:  LLM call (usually haiku), cost = input + output tokens
    - agent:   Full agent LLM call, cost = full conversation tokens
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ANSI colors
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
MAGENTA = '\033[0;35m'
DIM = '\033[2m'
BOLD = '\033[1m'
NC = '\033[0m'

# Hook Lab paths
HOOK_LAB = Path('/home/corey/hook-lab')
CLAUDE_PROJECTS = Path.home() / '.claude' / 'projects'
HOOK_LAB_PROJECT = CLAUDE_PROJECTS / '-home-corey-hook-lab'


def get_hook_lab_sessions() -> list:
    """Get all hook-lab sessions sorted by modification time."""
    if not HOOK_LAB_PROJECT.exists():
        return []

    sessions = []
    for f in HOOK_LAB_PROJECT.glob('*.jsonl'):
        sessions.append({
            'id': f.stem,
            'path': f,
            'mtime': f.stat().st_mtime,
            'modified': datetime.fromtimestamp(f.stat().st_mtime)
        })

    return sorted(sessions, key=lambda x: x['mtime'], reverse=True)


def parse_session(session_path: Path) -> dict:
    """Parse a session file and categorize API calls."""
    entries = []
    with open(session_path) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    result = {
        'session_id': session_path.stem,
        'file_path': str(session_path),
        'entry_count': len(entries),

        # Separate by source
        'main_agent': {
            'api_calls': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'cache_creation': 0,
            'cache_read': 0,
            'models': defaultdict(int),
        },
        'hooks': {
            'command': {'count': 0, 'context_tokens': 0},
            'prompt': {'count': 0, 'input_tokens': 0, 'output_tokens': 0},
            'agent': {'count': 0, 'input_tokens': 0, 'output_tokens': 0},
        },

        # Raw data for analysis
        'api_calls_by_model': defaultdict(list),
        'user_prompts': [],
        'tool_uses': [],
        'additional_context': [],
    }

    seen_request_ids = {}  # Track max tokens per request

    for entry in entries:
        entry_type = entry.get('type')

        # Track user prompts
        if entry_type == 'user':
            msg = entry.get('message', {})
            if isinstance(msg, dict):
                content = msg.get('content', '')
                if isinstance(content, str) and content:
                    result['user_prompts'].append({
                        'content': content[:200],
                        'timestamp': entry.get('timestamp'),
                    })

        # Track assistant messages with usage
        if entry_type == 'assistant':
            msg = entry.get('message', {})
            request_id = entry.get('requestId', '')
            model = msg.get('model', 'unknown')
            usage = msg.get('usage', {})

            if usage and request_id:
                # Track per-request (take max values due to streaming)
                current = seen_request_ids.get(request_id, {
                    'model': model,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cache_creation': 0,
                    'cache_read': 0,
                })

                current['input_tokens'] = max(current['input_tokens'], usage.get('input_tokens', 0))
                current['output_tokens'] = max(current['output_tokens'], usage.get('output_tokens', 0))
                current['cache_creation'] = max(current['cache_creation'], usage.get('cache_creation_input_tokens', 0))
                current['cache_read'] = max(current['cache_read'], usage.get('cache_read_input_tokens', 0))

                seen_request_ids[request_id] = current

            # Track tool uses
            content = msg.get('content', [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        result['tool_uses'].append(item.get('name', 'unknown'))

    # Categorize API calls
    for req_id, data in seen_request_ids.items():
        model = data['model']

        # Heuristic: haiku = hook, opus/sonnet = main agent (or hook agent)
        # This is imperfect - we need more data to refine
        is_hook = 'haiku' in model.lower()

        result['api_calls_by_model'][model].append(data)

        if is_hook:
            # Likely a prompt hook
            result['hooks']['prompt']['count'] += 1
            result['hooks']['prompt']['input_tokens'] += data['input_tokens'] + data['cache_read']
            result['hooks']['prompt']['output_tokens'] += data['output_tokens']
        else:
            # Main agent (or agent hook - need more heuristics)
            result['main_agent']['api_calls'] += 1
            result['main_agent']['input_tokens'] += data['input_tokens']
            result['main_agent']['output_tokens'] += data['output_tokens']
            result['main_agent']['cache_creation'] += data['cache_creation']
            result['main_agent']['cache_read'] += data['cache_read']
            result['main_agent']['models'][model] += 1

    return result


def calculate_cost(tokens: dict, model: str = 'opus') -> float:
    """Calculate cost based on model pricing."""
    # Pricing per 1M tokens (as of 2024)
    pricing = {
        'opus': {'input': 15.0, 'output': 75.0, 'cache_read': 1.50, 'cache_create': 18.75},
        'sonnet': {'input': 3.0, 'output': 15.0, 'cache_read': 0.30, 'cache_create': 3.75},
        'haiku': {'input': 0.25, 'output': 1.25, 'cache_read': 0.025, 'cache_create': 0.3125},
    }

    p = pricing.get(model, pricing['opus'])

    cost = 0
    cost += tokens.get('input_tokens', 0) * p['input'] / 1_000_000
    cost += tokens.get('output_tokens', 0) * p['output'] / 1_000_000
    cost += tokens.get('cache_read', 0) * p['cache_read'] / 1_000_000
    cost += tokens.get('cache_creation', 0) * p['cache_create'] / 1_000_000

    return cost


def print_session_analysis(data: dict):
    """Print detailed hook cost analysis."""
    print(f"\n{CYAN}{'═' * 65}{NC}")
    print(f"{CYAN}  Hook Lab Session Analysis{NC}")
    print(f"{CYAN}{'═' * 65}{NC}")

    print(f"\n{YELLOW}Session:{NC} {data['session_id']}")
    print(f"{DIM}{data['file_path']}{NC}")

    # Overview
    print(f"\n{YELLOW}Overview:{NC}")
    print(f"  Total entries:    {data['entry_count']}")
    print(f"  User prompts:     {len(data['user_prompts'])}")
    print(f"  Tool uses:        {len(data['tool_uses'])}")

    # Main Agent costs
    main = data['main_agent']
    print(f"\n{YELLOW}Main Agent (Opus):{NC}")
    print(f"  API calls:        {main['api_calls']}")
    print(f"  Input tokens:     {main['input_tokens']:,}")
    print(f"  Output tokens:    {main['output_tokens']:,}")
    print(f"  Cache creation:   {main['cache_creation']:,}")
    print(f"  Cache read:       {main['cache_read']:,}")

    main_cost = calculate_cost({
        'input_tokens': main['input_tokens'],
        'output_tokens': main['output_tokens'],
        'cache_creation': main['cache_creation'],
        'cache_read': main['cache_read'],
    }, 'opus')
    print(f"  {GREEN}Estimated cost:   ${main_cost:.4f}{NC}")

    # Hook costs
    hooks = data['hooks']
    print(f"\n{YELLOW}Hook Costs:{NC}")

    # Command hooks
    cmd = hooks['command']
    print(f"\n  {BLUE}Command hooks:{NC}")
    print(f"    Count:          {cmd['count']}")
    print(f"    Context tokens: {cmd['context_tokens']}")
    print(f"    {DIM}(Command hooks are FREE unless they inject context){NC}")

    # Prompt hooks
    prompt = hooks['prompt']
    print(f"\n  {MAGENTA}Prompt hooks (Haiku):{NC}")
    print(f"    Count:          {prompt['count']}")
    print(f"    Input tokens:   {prompt['input_tokens']:,}")
    print(f"    Output tokens:  {prompt['output_tokens']:,}")
    prompt_cost = calculate_cost({
        'input_tokens': prompt['input_tokens'],
        'output_tokens': prompt['output_tokens'],
    }, 'haiku')
    print(f"    {GREEN}Estimated cost: ${prompt_cost:.6f}{NC}")

    # Agent hooks
    agent = hooks['agent']
    print(f"\n  {RED}Agent hooks:{NC}")
    print(f"    Count:          {agent['count']}")
    print(f"    Input tokens:   {agent['input_tokens']:,}")
    print(f"    Output tokens:  {agent['output_tokens']:,}")
    agent_cost = calculate_cost({
        'input_tokens': agent['input_tokens'],
        'output_tokens': agent['output_tokens'],
    }, 'haiku')  # Default to haiku for agent hooks
    print(f"    {GREEN}Estimated cost: ${agent_cost:.6f}{NC}")

    # API calls by model
    print(f"\n{YELLOW}API Calls by Model:{NC}")
    for model, calls in data['api_calls_by_model'].items():
        total_in = sum(c['input_tokens'] + c['cache_read'] for c in calls)
        total_out = sum(c['output_tokens'] for c in calls)
        print(f"  {model}:")
        print(f"    Calls: {len(calls)}, Input: {total_in:,}, Output: {total_out:,}")

    # User prompts
    if data['user_prompts']:
        print(f"\n{YELLOW}User Prompts:{NC}")
        for i, p in enumerate(data['user_prompts'][:5], 1):
            text = p['content'][:60].replace('\n', ' ')
            print(f"  {i}. {DIM}{text}...{NC}")

    # Summary
    total_cost = main_cost + prompt_cost + agent_cost
    print(f"\n{CYAN}{'─' * 65}{NC}")
    print(f"{BOLD}Total Session Cost: ${total_cost:.4f}{NC}")
    print(f"  Main agent: ${main_cost:.4f}")
    print(f"  Hooks:      ${prompt_cost + agent_cost:.6f}")
    print()


def compare_sessions(baseline: dict, test: dict):
    """Compare baseline (no hooks) vs test (with hooks) session."""
    print(f"\n{CYAN}{'═' * 65}{NC}")
    print(f"{CYAN}  Hook Cost Comparison{NC}")
    print(f"{CYAN}{'═' * 65}{NC}")

    print(f"\n{YELLOW}Baseline:{NC} {baseline['session_id']}")
    print(f"{YELLOW}Test:    {NC} {test['session_id']}")

    print(f"\n{YELLOW}{'Metric':<30} {'Baseline':>12} {'Test':>12} {'Diff':>12}{NC}")
    print("─" * 68)

    comparisons = [
        ('User prompts', len(baseline['user_prompts']), len(test['user_prompts'])),
        ('API calls (main)', baseline['main_agent']['api_calls'], test['main_agent']['api_calls']),
        ('Input tokens', baseline['main_agent']['input_tokens'], test['main_agent']['input_tokens']),
        ('Output tokens', baseline['main_agent']['output_tokens'], test['main_agent']['output_tokens']),
        ('Cache creation', baseline['main_agent']['cache_creation'], test['main_agent']['cache_creation']),
        ('Cache read', baseline['main_agent']['cache_read'], test['main_agent']['cache_read']),
        ('Prompt hooks', baseline['hooks']['prompt']['count'], test['hooks']['prompt']['count']),
        ('Hook input tokens', baseline['hooks']['prompt']['input_tokens'], test['hooks']['prompt']['input_tokens']),
        ('Hook output tokens', baseline['hooks']['prompt']['output_tokens'], test['hooks']['prompt']['output_tokens']),
    ]

    for label, base_val, test_val in comparisons:
        diff = test_val - base_val
        if diff > 0:
            diff_str = f"{GREEN}+{diff:,}{NC}"
        elif diff < 0:
            diff_str = f"{RED}{diff:,}{NC}"
        else:
            diff_str = f"{DIM}0{NC}"
        print(f"  {label:<28} {base_val:>12,} {test_val:>12,} {diff_str:>20}")

    # Cost comparison
    base_cost = calculate_cost(baseline['main_agent'], 'opus')
    test_cost = calculate_cost(test['main_agent'], 'opus')
    hook_cost = calculate_cost({
        'input_tokens': test['hooks']['prompt']['input_tokens'],
        'output_tokens': test['hooks']['prompt']['output_tokens'],
    }, 'haiku')

    print(f"\n{YELLOW}Cost Analysis:{NC}")
    print(f"  Baseline cost:     ${base_cost:.4f}")
    print(f"  Test cost (main):  ${test_cost:.4f}")
    print(f"  Hook cost:         ${hook_cost:.6f}")
    print(f"  {BOLD}Overhead:           ${test_cost - base_cost + hook_cost:.4f}{NC}")
    print()


def list_sessions():
    """List all hook-lab sessions."""
    sessions = get_hook_lab_sessions()

    print(f"\n{CYAN}Hook Lab Sessions:{NC}\n")

    if not sessions:
        print(f"  {DIM}No sessions found in hook-lab{NC}")
        print(f"  {DIM}Start Claude from /home/corey/hook-lab to create sessions{NC}")
        return

    for s in sessions:
        print(f"  {s['id']}")
        print(f"    {DIM}Modified: {s['modified']:%Y-%m-%d %H:%M:%S}{NC}")
    print()


def main():
    args = sys.argv[1:]

    if not args:
        # Analyze latest session
        sessions = get_hook_lab_sessions()
        if not sessions:
            print(f"{RED}No hook-lab sessions found{NC}")
            sys.exit(1)
        data = parse_session(sessions[0]['path'])
        print_session_analysis(data)

    elif args[0] in ['-h', '--help']:
        print(__doc__)

    elif args[0] == '--list':
        list_sessions()

    elif args[0] == '--compare':
        if len(args) < 3:
            print("Usage: --compare <baseline-session> <test-session>")
            sys.exit(1)

        base_path = HOOK_LAB_PROJECT / f"{args[1]}.jsonl"
        test_path = HOOK_LAB_PROJECT / f"{args[2]}.jsonl"

        if not base_path.exists():
            print(f"{RED}Baseline session not found: {args[1]}{NC}")
            sys.exit(1)
        if not test_path.exists():
            print(f"{RED}Test session not found: {args[2]}{NC}")
            sys.exit(1)

        baseline = parse_session(base_path)
        test = parse_session(test_path)
        compare_sessions(baseline, test)

    else:
        # Analyze specific session
        session_id = args[0]
        session_path = HOOK_LAB_PROJECT / f"{session_id}.jsonl"

        if not session_path.exists():
            print(f"{RED}Session not found: {session_id}{NC}")
            print(f"Use --list to see available sessions")
            sys.exit(1)

        data = parse_session(session_path)
        print_session_analysis(data)


if __name__ == '__main__':
    main()
