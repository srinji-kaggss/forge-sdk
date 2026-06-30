# forge-sdk Test Results Report

**Date:** 2026-06-30  
**SDK Version:** 0.3.0  
**Python:** 3.14.6  
**Test Method:** Actual execution against live Ollama API (gemma3:4b)

---

## Executive Summary

| Category | Status |
|----------|--------|
| Existing smoke tests (46) | **ALL PASS** |
| User scenario 1 (echo tool) | **FAIL** — 3 distinct bugs |
| User scenario 2 (file ops) | **PASS** (after API fix) |
| User scenario 3 (error recovery) | **PASS** (after API fix) |
| User scenario 4 (LoopGuard) | **FAIL** — system prompt lacks schemas |
| User scenario 5 (audit trail) | **FAIL** — user API mismatches (3 methods) |
| OllamaProvider env fallback | **FAIL** — doesn't read OLLAMA_API_KEY from env |

---

## Test 1: Basic Agent Loop with Echo Tool

### Result: FAIL

### What happened
The agent ran 6 steps but **never successfully called the echo tool**. It tried `ECHO-001` (stable_id, not name) first, then `echo` with wrong parameter `{"param": "loop"}` three times, then LoopGuard blocked it.

### Actual errors

```
Step 1: action=ECHO-001
  → Error: Unknown tool 'ECHO-001'. Available tools: ['echo'].

Step 2-4: action=echo, action_input={"param": "loop"}
  → TypeError: echo_handler() got an unexpected keyword argument 'param'

Step 5: BLOCKED by LoopGuard (3 identical failing calls)
```

### Root causes

1. **System prompt lacks tool parameter schemas** (`src/forge_sdk/agents/react.py:73-103`):
   The `_build_system_prompt()` method only includes tool names and descriptions:
   ```python
   tool_descriptions.append(f"- {t.name} (id: {t.stable_id}): {t.description}")
   ```
   It does NOT include `t.input_schema` — so the model has no idea what parameters to pass. The model guessed `{"param": "loop"}` because it can't see the schema.

2. **Model confuses stable_id with tool name** (`src/forge_sdk/agents/react.py:121-130`):
   The agent prompt shows `(id: ECHO-001)` which the model interprets as the tool identifier. But `_execute_tool()` looks up by `name` (e.g., "echo"), not `stable_id`. The model used `ECHO-001` as the action name and got "Unknown tool".

3. **`_parse_response` fallback is too aggressive** (`src/forge_sdk/agents/react.py:105-119`):
   When the model returns raw JSON as text (not wrapped in a code block), the parser extracts the JSON but doesn't validate that the `action` field matches a known tool. It just passes through, causing a confusing "Unknown tool" error.

### Fix needed
Add `input_schema` to the system prompt tool descriptions, e.g.:
```python
tool_descriptions.append(
    f"- {t.name}: {t.description}\n"
    f"  Parameters: {json.dumps(t.input_schema)}"
)
```

---

## Test 2: Agent with File Operations

### Result: PASS (after API correction)

### What happened
The user's scenario used `get_file_tools()` which doesn't exist. The actual API exports `FILE_TOOLS` (a list). After correction, the agent successfully:
1. Called `write_file` with the correct path and content
2. Called `read_file` to verify
3. Finished with success

### User API mismatches
| User's code | Actual API | Error |
|-------------|-----------|-------|
| `from forge_sdk.tools.filesystem import get_file_tools` | `from forge_sdk.tools.filesystem import FILE_TOOLS` | ImportError |

### Agent behavior (corrected)
```
Step 1: write_file → "Written 44 bytes to /tmp/.../hello.py"
Step 2: read_file → verified content
Step 3: finish → success=True, edits=["/tmp/.../hello.py"]
```

---

## Test 3: Agent Error Recovery

### Result: PASS (after API correction)

### What happened
The agent correctly:
1. Tried `FAIL-001` (stable_id confusion again) → got "Unknown tool"
2. Tried `fail` → got `ValueError: Intentional failure`
3. Tried `succeed` → got `Success: recovered`
4. Finished successfully

### User API mismatches
| User's code | Actual API | Error |
|-------------|-----------|-------|
| `ToolSpec(parameters=...)` | `ToolSpec(input_schema=..., output_schema=...)` | TypeError |
| Sync handler `def handler(args)` | Async handler `async def handler(**kwargs)` | TypeError (on await) |

### Agent behavior (corrected)
The agent recovered from the error — it tried a different tool after `fail` raised an exception. This is the correct ReAct behavior. However, it still used `FAIL-001` (stable_id) first, showing the stable_id/name confusion is systemic.

---

## Test 4: LoopGuard Behavior

### Result: FAIL

### What happened
The agent ran only 1 step and exited without LoopGuard ever triggering. The model output raw JSON as its response (not wrapped in markdown), and the `_parse_response` extracted it — but used `LOOP-001` (stable_id) as the action name, which wasn't found. The agent then fell through to the finish fallback.

### Actual output (model response)
```json
{"thought": "The task is to echo the text 'loop'...", "action": "LOOP-001", "action_input": {"param": "loop"}}
```

### Root cause
Same as Test 1: the system prompt doesn't include tool schemas, so the model:
1. Can't see parameter names → guesses wrong parameters
2. Uses stable_id from the prompt `(id: LOOP-001)` as the action name → "Unknown tool"
3. Falls through to finish without actually calling any tool

### LoopGuard itself works correctly
Verified in unit tests — the guard blocks after `max_repeats` identical calls. The bug is that the agent never gets to the point of calling the same tool repeatedly because the model can't figure out how to call tools at all.

---

## Test 5: Audit Trail

### Result: FAIL (user API mismatches)

### User API mismatches
| User's code | Actual API | Error |
|-------------|-----------|-------|
| `log.append({"type": ..., "task": ...})` | `log.append(trace_id, entry_type, payload)` | TypeError |
| `log.query(limit=10)` | `log.get_entries(limit=10)` | AttributeError |
| `log.verify_chain()` | `log.verify_integrity()` | AttributeError |

### AuditLog works correctly with proper API
```python
log.append("trace-001", "agent.run.start", {"task": "test"})
log.append("trace-001", "tool.call", {"tool": "echo"})
events = log.get_entries(limit=10)  # → 2 events
violations = log.verify_integrity()  # → 0 violations
```

The hash-chain integrity verification works. Events are stored in SQLite and queryable by trace_id and entry_type.

---

## Bonus: OllamaProvider Environment Fallback

### Result: FAIL

### What happened
`OllamaProvider(model="gemma3:4b")` → 401 Unauthorized  
`OllamaProvider(model="gemma3:4b", api_key=key)` → Success

### Root cause
`OllamaProvider.__init__` defaults `api_key=""` and does NOT read `OLLAMA_API_KEY` from environment. But `ForgeConfig.resolve_api_key()` does read from env. This creates a usability gap:

- **ForgeConfig flow** (intended): reads env → `cfg.create_model()` → works
- **Direct OllamaProvider** (user's code): no env fallback → 401

### Fix needed
Either:
1. `OllamaProvider` should read `OLLAMA_API_KEY` from env as fallback, OR
2. Document that API key must be passed explicitly

---

## Bonus: Sync vs Async Handler Convention

### Result: FAIL (for sync handlers)

The `ToolSpec.handler` type is `Callable[..., Awaitable[ToolResult]]` — it MUST be an async function. The agent calls `await tool.handler(**action_input)`. A sync handler raises:
```
TypeError: An asyncio.Future, a coroutine or an awaitable is required
```

This is not documented. User scenarios all used sync handlers.

---

## Summary of All Bugs Found

### Critical (blocks agent from working)

| # | Bug | Location | Impact |
|---|-----|----------|--------|
| 1 | System prompt lacks tool parameter schemas | `react.py:73-103` | Model can't figure out what parameters to pass → all tool calls fail |
| 2 | Model uses stable_id as action name | `react.py:121-130` | "Unknown tool" errors on every call |

### Moderate (usability / robustness)

| # | Bug | Location | Impact |
|---|-----|----------|--------|
| 3 | OllamaProvider doesn't read OLLAMA_API_KEY from env | `ollama.py:16-26` | 401 Unauthorized when constructing directly |
| 4 | ToolSpec requires async handlers but not enforced | `types.py:58` | Sync handlers cause cryptic TypeError at runtime |
| 5 | No documentation of ToolSpec constructor fields | N/A | User guesses `parameters` instead of `input_schema` |

### Low (user-facing API mismatches, not SDK bugs)

| # | User's code | Actual API |
|---|-------------|-----------|
| 6 | `get_file_tools()` | `FILE_TOOLS` (list) |
| 7 | `AuditLog.append(dict)` | `AuditLog.append(trace_id, entry_type, payload)` |
| 8 | `log.query()` | `log.get_entries()` |
| 9 | `log.verify_chain()` | `log.verify_integrity()` |

---

## Recommended Fixes (Priority Order)

### Fix 1: Add tool schemas to system prompt
**File:** `src/forge_sdk/agents/react.py`  
**Lines:** 76-79

```python
# BEFORE
tool_descriptions.append(f"- {t.name} (id: {t.stable_id}): {t.description}")

# AFTER
tool_descriptions.append(
    f"- {t.name}: {t.description}\n"
    f"  Parameters: {json.dumps(t.input_schema, indent=2)}"
)
```

### Fix 2: Remove stable_id from tool descriptions in prompt
**File:** `src/forge_sdk/agents/react.py`  
**Lines:** 76-79

The `(id: ECHO-001)` in the prompt confuses the model into using stable_id as the action name. Remove it or label it clearly:

```python
# AFTER
tool_descriptions.append(
    f"- {t.name}: {t.description}\n"
    f"  Parameters: {json.dumps(t.input_schema)}"
)
```

### Fix 3: OllamaProvider env fallback
**File:** `src/forge_sdk/models/ollama.py`  
**Lines:** 16-26

```python
def __init__(self, api_key="", base_url="https://ollama.com", model="gemma3:4b"):
    import os
    self._api_key = api_key or os.environ.get("OLLAMA_API_KEY", "")
    # ... rest unchanged
```

### Fix 4: Validate handler is async at registration
**File:** `src/forge_sdk/tools/types.py`  
**Lines:** 42-58

```python
def __post_init__(self):
    import asyncio
    if not asyncio.iscoroutinefunction(self.handler):
        raise TypeError(
            f"Tool '{self.name}' handler must be async. "
            f"Got {type(self.handler).__name__}. Use 'async def' for handlers."
        )
```

---

## What Works Correctly

- **LoopGuard** — correctly blocks after max_repeats identical calls (verified in unit tests)
- **AuditLog** — hash-chain integrity works, append/query/verify_integrity all functional
- **File tools** — read_file, write_file, list_dir all work correctly with async handlers
- **Verifier pipeline** — syntactic, AST, entity validation gates all pass/fail correctly
- **False-green detection** — correctly flags tasks that imply edits but produce none
- **Agent error handling** — catches tool exceptions, returns structured error messages for AI consumption
- **Response parsing** — handles markdown code blocks, raw JSON, and plain text gracefully
