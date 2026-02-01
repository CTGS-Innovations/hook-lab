#!/usr/bin/env python3
"""
Claude Session Token Analyzer
Analyzes Claude Code session files to extract comprehensive token usage.

Usage:
    ./analyze-session.py <session-id-or-path>
    ./analyze-session.py --latest [project-path]
    ./analyze-session.py --compare <session1> <session2>
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
DIM = '\033[2m'
NC = '\033[0m'


def find_session_file(identifier: str, project_path: str = None) -> Path:
    """Find a session file by ID or path."""
    # Direct path
    if os.path.exists(identifier):
        return Path(identifier)

    # Search in projects
    claude_dir = Path.home() / '.claude' / 'projects'

    if project_path:
        # Convert project path to Claude's naming convention
        safe_name = project_path.replace('/', '-')
        project_dir = claude_dir / safe_name
        if project_dir.exists():
            session_file = project_dir / f"{identifier}.jsonl"
            if session_file.exists():
                return session_file

    # Search all projects
    for project_dir in claude_dir.iterdir():
        if project_dir.is_dir():
            session_file = project_dir / f"{identifier}.jsonl"
            if session_file.exists():
                return session_file

    raise FileNotFoundError(f"Session not found: {identifier}")


def find_latest_session(project_path: str = None) -> Path:
    """Find the most recent session file."""
    claude_dir = Path.home() / '.claude' / 'projects'
    latest = None
    latest_mtime = 0

    search_dirs = []
    if project_path:
        safe_name = project_path.replace('/', '-')
        project_dir = claude_dir / safe_name
        if project_dir.exists():
            search_dirs = [project_dir]
    else:
        search_dirs = [d for d in claude_dir.iterdir() if d.is_dir()]

    for project_dir in search_dirs:
        for f in project_dir.glob('*.jsonl'):
            if f.stat().st_mtime > latest_mtime:
                latest_mtime = f.stat().st_mtime
                latest = f

    if not latest:
        raise FileNotFoundError("No sessions found")
    return latest


def parse_session(session_path: Path) -> dict:
    """Parse a session file and extract all relevant data."""
    entries = []
    with open(session_path) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Build UUID relationship map
    uuid_map = {}
    for entry in entries:
        if 'uuid' in entry:
            uuid_map[entry['uuid']] = entry

    # Extract data
    result = {
        'session_id': session_path.stem,
        'file_path': str(session_path),
        'entry_count': len(entries),
        'messages': [],
        'totals': {
            'input_tokens': 0,
            'output_tokens': 0,
            'cache_creation_input_tokens': 0,
            'cache_read_input_tokens': 0,
            'thinking_tokens': 0,
        },
        'by_request': defaultdict(lambda: {
            'input_tokens': 0,
            'output_tokens': 0,
            'cache_creation_input_tokens': 0,
            'cache_read_input_tokens': 0,
        }),
        'user_prompts': [],
        'api_calls': 0,
        'tool_uses': [],
        'thinking_blocks': 0,
    }

    seen_request_ids = set()

    for entry in entries:
        entry_type = entry.get('type')

        # Track user prompts
        if entry_type == 'user':
            msg = entry.get('message', {})
            if isinstance(msg, dict):
                content = msg.get('content', '')
                if isinstance(content, str) and content:
                    result['user_prompts'].append(content[:100])

        # Track assistant messages with usage
        if entry_type == 'assistant':
            msg = entry.get('message', {})
            request_id = entry.get('requestId', '')

            # Count unique API calls
            if request_id and request_id not in seen_request_ids:
                seen_request_ids.add(request_id)
                result['api_calls'] += 1

            # Extract usage
            usage = msg.get('usage', {})
            if usage:
                # Only count each request_id once for totals
                req_data = result['by_request'][request_id]

                for key in ['input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens']:
                    val = usage.get(key, 0)
                    if val > req_data[key]:
                        # Update if this message has more tokens (streaming updates)
                        result['totals'][key] += val - req_data[key]
                        req_data[key] = val

            # Track content types
            content = msg.get('content', [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        content_type = item.get('type')
                        if content_type == 'thinking':
                            result['thinking_blocks'] += 1
                        elif content_type == 'tool_use':
                            tool_name = item.get('name', 'unknown')
                            result['tool_uses'].append(tool_name)

    return result


def calculate_cost(totals: dict) -> dict:
    """Calculate estimated costs based on token counts.

    Pricing (as of 2024, may change):
    - Opus: $15/M input, $75/M output
    - Cache read: $1.50/M (10% of input)
    - Cache creation: $18.75/M (125% of input)
    """
    # Opus pricing
    input_rate = 15.0 / 1_000_000
    output_rate = 75.0 / 1_000_000
    cache_read_rate = 1.50 / 1_000_000
    cache_create_rate = 18.75 / 1_000_000

    return {
        'input_cost': totals['input_tokens'] * input_rate,
        'output_cost': totals['output_tokens'] * output_rate,
        'cache_read_cost': totals['cache_read_input_tokens'] * cache_read_rate,
        'cache_create_cost': totals['cache_creation_input_tokens'] * cache_create_rate,
        'total_cost': (
            totals['input_tokens'] * input_rate +
            totals['output_tokens'] * output_rate +
            totals['cache_read_input_tokens'] * cache_read_rate +
            totals['cache_creation_input_tokens'] * cache_create_rate
        )
    }


def print_session_report(data: dict):
    """Print a formatted report for a session."""
    print(f"\n{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Claude Session Analysis{NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")

    print(f"\n{YELLOW}Session:{NC} {data['session_id']}")
    print(f"{DIM}{data['file_path']}{NC}")

    print(f"\n{YELLOW}Overview:{NC}")
    print(f"  Entries:         {data['entry_count']}")
    print(f"  API calls:       {data['api_calls']}")
    print(f"  User prompts:    {len(data['user_prompts'])}")
    print(f"  Tool uses:       {len(data['tool_uses'])}")
    print(f"  Thinking blocks: {data['thinking_blocks']}")

    totals = data['totals']
    print(f"\n{YELLOW}Token Usage:{NC}")
    print(f"  Input tokens:          {totals['input_tokens']:>10,}")
    print(f"  Output tokens:         {totals['output_tokens']:>10,}")
    print(f"  Cache creation:        {totals['cache_creation_input_tokens']:>10,}")
    print(f"  Cache read:            {totals['cache_read_input_tokens']:>10,}")

    total_input = totals['input_tokens'] + totals['cache_creation_input_tokens'] + totals['cache_read_input_tokens']
    print(f"  {GREEN}Total input context:{NC}    {total_input:>10,}")
    print(f"  {GREEN}Total output:{NC}           {totals['output_tokens']:>10,}")

    costs = calculate_cost(totals)
    print(f"\n{YELLOW}Estimated Cost (Opus pricing):{NC}")
    print(f"  Input:        ${costs['input_cost']:.4f}")
    print(f"  Output:       ${costs['output_cost']:.4f}")
    print(f"  Cache read:   ${costs['cache_read_cost']:.4f}")
    print(f"  Cache create: ${costs['cache_create_cost']:.4f}")
    print(f"  {GREEN}Total:        ${costs['total_cost']:.4f}{NC}")

    if data['user_prompts']:
        print(f"\n{YELLOW}User Prompts:{NC}")
        for i, prompt in enumerate(data['user_prompts'][:5], 1):
            truncated = prompt[:60] + '...' if len(prompt) > 60 else prompt
            print(f"  {i}. {DIM}{truncated}{NC}")
        if len(data['user_prompts']) > 5:
            print(f"  {DIM}... and {len(data['user_prompts']) - 5} more{NC}")

    if data['tool_uses']:
        tool_counts = defaultdict(int)
        for tool in data['tool_uses']:
            tool_counts[tool] += 1
        print(f"\n{YELLOW}Tools Used:{NC}")
        for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {tool}: {count}")

    print()


def compare_sessions(data1: dict, data2: dict):
    """Compare two sessions."""
    print(f"\n{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Session Comparison{NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")

    print(f"\n{YELLOW}Session 1:{NC} {data1['session_id']}")
    print(f"{YELLOW}Session 2:{NC} {data2['session_id']}")

    print(f"\n{YELLOW}{'Metric':<25} {'Session 1':>12} {'Session 2':>12} {'Diff':>12}{NC}")
    print("-" * 63)

    metrics = [
        ('API calls', 'api_calls', None),
        ('User prompts', 'user_prompts', len),
        ('Tool uses', 'tool_uses', len),
        ('Input tokens', 'input_tokens', None),
        ('Output tokens', 'output_tokens', None),
        ('Cache creation', 'cache_creation_input_tokens', None),
        ('Cache read', 'cache_read_input_tokens', None),
    ]

    for label, key, transform in metrics:
        if transform:
            v1 = transform(data1.get(key, []))
            v2 = transform(data2.get(key, []))
        elif key in data1.get('totals', {}):
            v1 = data1['totals'][key]
            v2 = data2['totals'][key]
        else:
            v1 = data1.get(key, 0)
            v2 = data2.get(key, 0)

        diff = v2 - v1
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        color = RED if diff > 0 else GREEN if diff < 0 else NC
        print(f"  {label:<23} {v1:>12,} {v2:>12,} {color}{diff_str:>12}{NC}")

    cost1 = calculate_cost(data1['totals'])
    cost2 = calculate_cost(data2['totals'])
    diff = cost2['total_cost'] - cost1['total_cost']
    diff_str = f"+${diff:.4f}" if diff > 0 else f"-${abs(diff):.4f}"
    color = RED if diff > 0 else GREEN if diff < 0 else NC
    print(f"  {'Estimated cost':<23} ${cost1['total_cost']:>11.4f} ${cost2['total_cost']:>11.4f} {color}{diff_str:>12}{NC}")

    print()


def main():
    args = sys.argv[1:]

    if not args or args[0] in ['-h', '--help']:
        print(__doc__)
        sys.exit(0)

    if args[0] == '--latest':
        project = args[1] if len(args) > 1 else None
        session_path = find_latest_session(project)
        data = parse_session(session_path)
        print_session_report(data)

    elif args[0] == '--compare':
        if len(args) < 3:
            print("Usage: --compare <session1> <session2>")
            sys.exit(1)
        path1 = find_session_file(args[1])
        path2 = find_session_file(args[2])
        data1 = parse_session(path1)
        data2 = parse_session(path2)
        print_session_report(data1)
        print_session_report(data2)
        compare_sessions(data1, data2)

    elif args[0] == '--list':
        project = args[1] if len(args) > 1 else None
        claude_dir = Path.home() / '.claude' / 'projects'

        if project:
            safe_name = project.replace('/', '-')
            search_dirs = [claude_dir / safe_name]
        else:
            search_dirs = [d for d in claude_dir.iterdir() if d.is_dir()]

        print(f"\n{CYAN}Available Sessions:{NC}\n")
        for project_dir in sorted(search_dirs):
            if project_dir.is_dir():
                sessions = list(project_dir.glob('*.jsonl'))
                if sessions:
                    print(f"{YELLOW}{project_dir.name}{NC}")
                    for s in sorted(sessions, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                        mtime = datetime.fromtimestamp(s.stat().st_mtime)
                        print(f"  {s.stem}  {DIM}{mtime:%Y-%m-%d %H:%M}{NC}")
                    if len(sessions) > 5:
                        print(f"  {DIM}... and {len(sessions) - 5} more{NC}")
                    print()

    else:
        # Single session analysis
        session_path = find_session_file(args[0])
        data = parse_session(session_path)
        print_session_report(data)

        # Output JSON if requested
        if '--json' in args:
            print(json.dumps({
                'session_id': data['session_id'],
                'totals': data['totals'],
                'api_calls': data['api_calls'],
                'costs': calculate_cost(data['totals'])
            }, indent=2))


if __name__ == '__main__':
    main()
