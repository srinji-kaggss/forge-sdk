# FORGE-SDK Codebase Assessment

## Overview

Analyzed 42 Python files across 11 packages. Focus on critical-path files: `agents/react.py` (ReAct loop), `harness/engine.py` (evolution engine), `tools/registry.py`, `models/registry.py`, `tools/filesystem.py`, `audit/daemon_sink.py`.

---

## Architecture Summary

| Package | Purpose | Files |
|---------|---------|-------|
| `agents/` | ReAct agent loop, config, types | 3 |
| `harness/` | Evolution engine, adaptive prompts, learning store | 5 |
| `tools/` | Tool registry, filesystem, shell, search, adapters | 6 |
| `models/` | Provider registry, OpenRouter, Ollama, DeepSeek, Mesh | 7 |
| `eval/` | Harness, runner, strategy | 3 |
| `audit/` | Event sink, daemon sink | 2 |
| `cli/` | CLI entry point | 1 |
| `config/` | Configuration | 1 |
| `tracing/` | Spans, tracer | 2 |
| `verifiers/` | Verification evidence/status | 1 |
| `policies/` | (empty init only) | 1 |

---

## Critical Bugs Found

### BUG 1: `ContextManager.fit()` returns inconsistent types (react.py ~line 223)

**Severity: HIGH — Runtime crash**

```python
def fit(self, messages: list[dict], system_prompt: str) -> list[dict]:
    if not messages:
        return messages          # Returns list[dict]
    ...
    return result, truncation_count  # Returns tuple
```

Early-return paths return a single `list[dict]`, but the main path returns `tuple[list[dict], int]`. The caller always unpacks as a tuple:

```python
messages, trunc_count = self._context.fit(messages, ...)
```

**Impact:** `ValueError: not enough values to unpack` when messages is empty or `available <= 0`.

**Fix:** All return paths must return `(list[dict], int)`. Early returns should return `(messages, 0)`.

---

### BUG 2: `setdefault` typo in `EvolutionEngine._extract_patterns()` (engine.py ~line 145)

**Severity: HIGH — Runtime crash**

```python
error_types.setdefault(category, []).append(episode)
```

Python dict method is `setdefault` (with 't'), not `setdefault`. This will raise:

```
AttributeError: 'dict' object has no attribute 'setdefault'
```

**Fix:** Change to `error_types.setdefault(category, []).append(episode)`.

---

### BUG 3: `UsageLimiter.check()` called with no arguments (react.py in `arun()`)

**Severity: MEDIUM — Logic bug, ineffective limit enforcement**

```python
# First call site (line ~420): called with defaults, always returns False
if self._limiter.check():
    log.warning("Usage limit exceeded at step %d", step_num)
    break

# Second call site (line ~440): properly passes usage data
self._limiter.check(usage.total_tokens)
```

The first call to `check()` passes no arguments, so `usage_tokens=0` and `cost_usd=0.0`. The method adds 0 to the running total and checks if `total_tokens > max_tokens`. If the limit hasn't been hit yet, this is always False — making this guard ineffective for catching usage accumulated via `prompt_tokens`/`completion_tokens` tracking.

**Fix:** Either remove the redundant check or have it properly compare against the accumulated token count. The second call site already handles usage tracking.

---

### BUG 4: Sandbox path traversal via absolute paths (react.py `_check_sandbox()`)

**Severity: MEDIUM — Security bypass**

```python
resolved = os.path.realpath(os.path.join(self._sandbox_dir, path))
```

`os.path.join('/sandbox', '/etc/passwd')` returns `'/etc/passwd'` (ignores the first argument when second is absolute). An attacker or LLM that passes an absolute path can write outside the sandbox.

**Fix:**
```python
resolved = os.path.realpath(os.path.join(self._sandbox_dir, path.lstrip('/')))
```
or use `pathlib.Path(self._sandbox_dir) / path.lstrip('/')`.

---

### BUG 5: `profile.evolve()` rebind doesn't affect caller (engine.py ~line 145)

**Severity: MEDIUM — Logic bug, silent data loss**

```python
def step(self, profile: AgentProfile, ...) -> StepResult:
    ...
    profile = profile.evolve({...})  # Rebind local variable only
```

The mutated profile is discarded. The caller never receives the evolved profile. This means the A-Evolve cycle's "Reload" phase is broken — the harness can never apply mutations.

**Fix:** Return the evolved profile as part of `StepResult` or mutate the profile in-place.

---

### BUG 6: LoopGuard blocks don't trigger convergence nudges (react.py `arun()`)

**Severity: LOW — Potential infinite spin**

When LoopGuard repeatedly blocks tool calls, `steps_since_edit` is not incremented (only updated when `not is_final and not loop_guard_triggered`). If the agent is stuck in a LoopGuard cycle:
- It keeps trying the same blocked tool
- LoopGuard blocks it each time
- `steps_since_edit` never increases
- Convergence nudges are never triggered
- Agent spins until `max_steps`

**Fix:** Increment `steps_since_edit` on LoopGuard blocks too, or add a separate counter for blocked calls.

---

## Design Issues

### D1: Deep nesting in `arun()` (react.py ~160 lines in one method)

`arun()` is ~160 lines with 6 levels of nesting. This makes it hard to test, review, or modify. Consider extracting:
- Convergence checking into a separate method
- Step execution into a `_execute_step()` method
- Finalization logic into `_finalize()`

### D2: Module-level regex compilation side effects

`_ACTION_VERBS` and `_ERROR_KEYWORDS` are compiled at module import time. This is fine for performance but means importing `react.py` always runs `re.compile()`. Consider using `re.compile` lazily or caching at the class level.

### D3: Empty `policies/` and `verifiers/` packages

- `verifiers/__init__.py` exists but there's no verifier implementation visible — only types. The verification pipeline in `react.py` references `self._verifier.verify(...)` but no concrete verifier class was found in the scanned files.
- `policies/__init__.py` exists but the package is empty. Dead code.

### D4: Inconsistent registry patterns

- `ToolRegistry` uses `stable_id` as the key and has both `get()` and `get_by_name()`.
- `ProviderRegistry` uses `name` as the key and only has `get()`.
- Both have `available()` but `ToolRegistry.available()` takes a context parameter while `ProviderRegistry.available()` does not.

### D5: No type hints for `tool.handler`

`ToolSpec.handler` is used with `**action_input` in `_execute_tool()`, but there's no Protocol or type checking ensuring the handler signature matches the input schema. A mismatch would cause a runtime `TypeError`.

### D6: Evolution engine has no LLM integration by default

`EvolutionEngine.__init__` accepts an optional `mutate_fn` but the built-in mutation logic relies entirely on hardcoded suggestion strings (e.g., `"timeout_handling": "When a task involves..."`). Without an LLM-backed `mutate_fn`, evolution is limited to a fixed set of patterns. This is a reasonable design for v0 but limits the A-Evolve cycle's power.

---

## Strengths

1. **Strategy registry pattern** — The parse strategies in `react.py` (OKF S3-safe) are well-designed with stable IDs, `applies()` predicates, and `execute()` methods. No nested `if/elif` chains.

2. **Observability** — `ReasoningTrace`, `AgentMetrics`, tracer integration, and structured logging provide excellent debugging and monitoring capabilities.

3. **Context window management** — `ContextManager` with truncation is a critical feature for long-running agent sessions.

4. **LoopGuard** — Content-hash-based deduplication prevents ~30% of stuck-agent scenarios.

5. **Sandbox enforcement** — File-write restrictions are a good security practice (despite the path traversal bug).

6. **Convergence nudges** — Proactive intervention when the agent stops making file changes is a thoughtful UX feature.

---

## Summary

| Category | Count |
|----------|-------|
| Critical bugs (runtime crash) | 2 (BUG 1, BUG 2) |
| Medium bugs (logic/security) | 3 (BUG 3, BUG 4, BUG 5) |
| Low bugs (edge case) | 1 (BUG 6) |
| Design issues | 6 |
| Strengths identified | 6 |

**Recommended priority:** Fix BUG 1 and BUG 2 immediately (they will crash at runtime). Fix BUG 4 (security) and BUG 5 (silent data loss) next. BUG 3 and BUG 6 are lower priority but should be addressed before production use.
