# Hook Lab Test Runner

## Quick Start

```bash
./test-runner.sh reset   # Start fresh
./test-runner.sh next    # Run each test
```

## Test Matrix

| # | Name | Hook Type | Expected Δ Tokens | Proves |
|---|------|-----------|-------------------|--------|
| 0 | baseline | none | 0 | Control |
| 1 | test1 | command (silent) | **0** | Commands are free |
| 2 | test2 | command (context) | **~15** | Context = tokens |
| 3 | test3 | command×2 (gate) | **0 or ~15** | Gate pattern |
| 4 | test4 | agent (minimal) | **500-2000** | Agent baseline |
| 5 | test5 | cmd + agent | **???** | Agent self-gate |
| 6 | test6 | cmd exit(2) + agent | **0 or ???** | exit(2) blocks chain |

## Hypotheses

```
H1: Silent command = 0 tokens
H2: Context = proportional tokens
H3: Agent = fixed overhead (~500-2000)
H4: exit(2) blocks subsequent hooks ← CRITICAL
```

## Expected Results Table

After running all tests, compare:

```
./test-runner.sh compare baseline test1  # Should be Δ=0
./test-runner.sh compare baseline test2  # Should be Δ~15
./test-runner.sh compare baseline test4  # Agent overhead
./test-runner.sh compare test4 test6     # exit(2) blocking?
```

| Comparison | If H True | If H False |
|------------|-----------|------------|
| baseline→test1 | Δ = 0 | hidden command cost |
| baseline→test2 | Δ = ~15 | wrong context model |
| baseline→test4 | Δ = 500-2000 | - |
| test4→test6 | Δ = -agent | exit(2) doesn't block |

## Workflow

1. `./test-runner.sh next` → sets up test
2. `claude` → start fresh session
3. `hi` → send message
4. `/exit` → exit claude
5. `./test-runner.sh next` → record, advance
6. Repeat until done

## Commands

| Command | What it does |
|---------|--------------|
| `./test-runner.sh next` | Advance through tests |
| `./test-runner.sh status` | Show progress |
| `./test-runner.sh reset` | Start over |
| `./test-runner.sh compare A B` | Compare results |
