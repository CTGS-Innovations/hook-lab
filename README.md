# Hook Cost Lab

Isolated test environment for measuring Claude Code hook costs and building a zero-cost scheduler pattern.

## Hypothesis

1. **Command hooks cost 0 tokens** when they exit silently (exit 0, no stdout)
2. **Command hooks can gate agent execution** by manipulating files/state
3. **A hybrid command-guard-agent pattern** creates a free scheduler

## Test Structure

```
hook-lab/
├── hooks/              # Test hook implementations
│   ├── silent-noop.sh          # Baseline: silent exit 0
│   ├── context-inject.py       # Returns additionalContext
│   ├── gate-checker.sh         # Checks if work is pending
│   └── gate-breaker.sh         # Manipulates settings to block agents
├── tests/              # Test configurations
│   ├── 01-baseline-silent.json     # Measure silent command cost
│   ├── 02-context-inject.json      # Measure context injection cost
│   ├── 03-command-gate-agent.json  # Hybrid pattern
│   └── 04-settings-breaker.json    # Settings manipulation test
├── docs/               # Reference material
│   ├── HOOK-BIBLE.md           # Hook patterns & gotchas
│   └── COST-MODEL.md           # Token cost analysis
├── results/            # Test outputs
└── settings.local.json # Test Claude Code settings
```

## The Zero-Cost Scheduler Pattern

```
┌─────────────────────────────────────────────────────────────┐
│ UserPromptSubmit (every prompt)                             │
│   └── Command hook: check Redis/file for work               │
│       ├── No work → exit 0 (FREE)                           │
│       └── Work pending → write gate file, exit 0 (FREE)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Stop (after Claude responds)                                │
│   └── Command hook: check gate file                         │
│       ├── No gate → exit 0 (FREE)                           │
│       └── Gate exists → ???                                 │
│           Option A: Output triggers agent (COST)            │
│           Option B: Break settings to disable agent (FREE?) │
│           Option C: Permission block trick (FREE?)          │
└─────────────────────────────────────────────────────────────┘
```

## Key Questions

1. Does returning NOTHING from command hook = 0 tokens?
2. Can we conditionally "enable" an agent hook via command output?
3. Can we break/fix settings.local.json mid-conversation?
4. What's the minimum viable agent prompt cost?

## Running Tests

```bash
cd /home/corey/hook-lab
# Copy test settings to Claude Code
cp tests/01-baseline-silent.json ~/.claude/settings.local.json

# Start new Claude session
claude

# Check results
cat results/test-01.log
```
