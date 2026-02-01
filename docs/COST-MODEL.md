# Hook Token Cost Model

## Hypothesis

| Hook Type | Condition | Expected Cost |
|-----------|-----------|---------------|
| Command | Silent exit (no stdout, exit 0) | **0 tokens** |
| Command | Returns additionalContext | **~tokens in context** |
| Command | Returns systemMessage | **~tokens in message** |
| Command | Blocks (exit 2) | **~tokens in block message** |
| Prompt | Any | **Input + Output tokens (Haiku)** |
| Agent | Any | **Full conversation tokens (model)** |

## Cost Formula

```
Total Hook Cost = Σ(visible_output_tokens) + Σ(llm_call_tokens)

Where:
- visible_output_tokens = additionalContext + systemMessage + block messages
- llm_call_tokens = prompt hooks + agent hooks (input + output per turn)
```

## The Zero-Cost Scheduler

If command hooks with silent exit cost 0 tokens, then:

```
Cost = 0                          (when no work pending)
Cost = agent_cost                 (when work exists)
```

This is optimal - you only pay when there's actual work to do.

## Test Results

### Test 1: Silent Command (baseline)
```
Config: silent-noop.sh on UserPromptSubmit
Expected: 0 additional tokens
Actual: [TO BE MEASURED]
```

### Test 2: Context Injection
```
Config: context-inject.py returns ~50 chars of context
Expected: ~15-20 tokens (context size)
Actual: [TO BE MEASURED]
```

### Test 3: Command Gate Pattern
```
Config: gate-checker on Submit, gate-reader on Stop
Expected: 0 tokens when no work, ~context tokens when work exists
Actual: [TO BE MEASURED]
```

### Test 4: Minimal Agent
```
Config: Agent with "Return {done: true}"
Expected: ~100-200 tokens minimum (system prompt + response)
Actual: [TO BE MEASURED]
```

## Measurement Method

1. Start fresh Claude session
2. Note starting token count (if visible) or conversation length
3. Send simple prompt: "Say hi"
4. Note ending token count
5. Compare across test configurations

Alternative: Use Claude Code's cost tracking or billing to measure actual costs.

## Key Questions to Answer

1. **Does silent command = 0 tokens?**
   - If yes: Free scheduler is viable
   - If no: Need to understand overhead

2. **What's the minimum agent cost?**
   - System prompt overhead
   - Minimum response
   - This is the "price" of triggering work

3. **Can exit(2) block subsequent hooks?**
   - If yes: Permission block pattern works
   - If no: Need different approach

4. **Does Claude Code cache settings.local.json?**
   - If cached: Can't manipulate mid-session
   - If re-read: Settings manipulation viable
