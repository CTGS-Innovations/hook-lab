# Claude Code Hook Bible

## Hook Events

| Event | When | Common Uses |
|-------|------|-------------|
| `UserPromptSubmit` | User sends message | Pre-processing, context injection |
| `Stop` | After Claude responds | Post-processing, learning, cleanup |
| `SubagentStart` | Subagent spawns | Monitoring |
| `SubagentStop` | Subagent completes | Capture results |
| `ToolCall` | Before tool executes | Validation, logging |
| `ToolResult` | After tool returns | Transform results |
| `Notification` | Async event | Background task completion |

## Hook Types

### Command Hooks
```json
{
  "type": "command",
  "command": "/path/to/script.sh",
  "timeout": 5
}
```

**Input**: JSON on stdin with event context
**Output**: JSON on stdout (optional)
**Exit codes**:
- 0 = success, continue
- 1 = error (logged, continues)
- 2 = block action

**Output schema**:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Injected into conversation",
    "systemMessage": "System-level message"
  }
}
```

### Prompt Hooks
```json
{
  "type": "prompt",
  "prompt": "Evaluate this and return JSON decision",
  "timeout": 30,
  "model": "haiku"
}
```

**Cost**: Haiku API call (input + output tokens)
**Use case**: Quick evaluations, decisions

### Agent Hooks
```json
{
  "type": "agent",
  "prompt": "Do complex multi-step task",
  "timeout": 120,
  "model": "haiku"
}
```

**Cost**: Full conversation (multiple turns possible)
**Use case**: Complex tasks, tool usage

## Critical Gotchas

### 1. Hooks in Same Array Run in PARALLEL
```json
{
  "hooks": [
    {"type": "command", "command": "first.sh"},
    {"type": "agent", "prompt": "uses first.sh output"}  // RACE CONDITION!
  ]
}
```

**Solution**: Use different events (Submit creates file, Stop reads it)

### 2. Subagent Hooks Don't Fire Inside Subagents
If you spawn a subagent, hooks in the main session don't monitor it.
Use `SubagentStop` to capture results after completion.

### 3. Exit Codes Matter
- exit 0 = success
- exit 1 = error (logged but continues)
- exit 2 = **BLOCK** (stops the triggering action)

### 4. Async Hooks
```json
{
  "type": "command",
  "command": "slow-task.sh",
  "async": true
}
```

Result delivered on NEXT turn, not immediately.

### 5. Settings.local.json Location
- `~/.claude/settings.local.json` (user settings)
- `.claude/settings.local.json` (project settings - takes precedence)

## Patterns

### Pattern 1: Silent Observer
```json
{
  "type": "command",
  "command": "logger.sh",  // Logs to file, no stdout
  "timeout": 2
}
```
Cost: ~0 tokens (no output)

### Pattern 2: Context Enrichment
```json
{
  "type": "command",
  "command": "python3 enrich.py",  // Returns additionalContext
  "timeout": 5
}
```
Cost: Tokens proportional to returned context

### Pattern 3: Gate Pattern (Cross-Event)
```json
{
  "UserPromptSubmit": [{
    "hooks": [{"type": "command", "command": "check-and-set-gate.sh"}]
  }],
  "Stop": [{
    "hooks": [{"type": "command", "command": "read-gate-maybe-trigger.sh"}]
  }]
}
```
Cost: 0 when no work, context tokens when work exists

### Pattern 4: Conditional Agent (Theoretical)
```json
{
  "hooks": [
    {
      "type": "command",
      "command": "[ -f /tmp/gate ] || exit 2"  // Block if no gate
    },
    {
      "type": "agent",
      "prompt": "Do work"  // Only runs if command succeeds
    }
  ]
}
```
**UNTESTED**: Does exit(2) stop the chain or just block the action?

## Input Schema (What Hooks Receive)

```json
{
  "session_id": "uuid",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/current/directory",
  "permission_mode": "acceptEdits",
  "hook_event_name": "UserPromptSubmit",

  // Event-specific fields:
  "user_prompt": "...",           // UserPromptSubmit
  "tool_name": "Read",            // ToolCall
  "tool_input": {...},            // ToolCall
  "agent_id": "abc123",           // SubagentStop
  "agent_transcript_path": "..."  // SubagentStop
}
```

## Output Schema (What Hooks Can Return)

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "## Context\n\nThis appears in conversation",
    "systemMessage": "System-level instruction"
  }
}
```

Or for decisions:
```json
{
  "decision": "approve",  // or "block"
  "reason": "Why"
}
```
