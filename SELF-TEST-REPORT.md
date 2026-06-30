# Forge Agent Self-Test Report — v0.4.0 Real Execution

**Date**: 2026-06-30
**Task**: Use forge-sdk ReactAgent (gemma3:4b via Ollama Cloud) to write tests for lgwks issue #349
**Result**: Agent fails to complete the task. 5 distinct failures identified.

---

## Failure Summary

| # | Category | Severity | Description |
|---|----------|----------|-------------|
| F1 | **Agent Dispatch** | CRITICAL | Agent emits `finish` with JSON payload instead of calling `write_file` — nested JSON problem |
| F2 | **Agent Code Quality** | HIGH | Generated test code hallucinates (re-defines module code locally, missing imports, broken regex) |
| F3 | **Provider Auth** | HIGH | OllamaProvider doesn't read `OLLAMA_API_KEY` from env (Bug #3 — FIXED) |
| F4 | **Shell Security** | HIGH | Shell tool uses `shell=True` with `shlex.split` fallback — shell builtins fail (Bug #6 — FIXED) |
| F5 | **Test Coverage** | MEDIUM | Tests use shell builtins (`exit 1`) that don't work with `shell=False` (FIXED) |

---

## F1: Nested JSON Problem (CRITICAL)

**Observed**: Agent Step 4 output:
```json
{
  "thought": "...",
  "action": "finish",
  "action_input": {
    "output": "{\"thought\": \"...\", \"action\": \"write_file\", \"action_input\": {...}}"
  }
}
```

**Expected**: The agent should emit:
```json
{
  "thought": "...",
  "action": "write_file",
  "action_input": {"path": "...", "content": "..."}
}
```

**Root Cause**: The model (gemma3:4b) correctly constructs the `write_file` call in its reasoning, but then wraps it inside a `finish` action's `output` field. The parser finds the outermost `{...}` which is the `finish` action, not the nested `write_file`.

**Impact**: The agent NEVER actually calls tools for file creation/editing. It only reads files (Steps 1-3) then emits a `finish` with the intended tool call as a string.

**Fix Required**: 
1. Modify `_parse_response` to detect and unwrap nested JSON
2. Or add post-processing: if `finish` action's output contains a valid tool call JSON, execute it instead
3. Or strengthen the system prompt to prevent nesting

---

## F2: Generated Code Quality (HIGH)

The agent's generated test (inside the `finish` output) has multiple issues:

1. **Missing imports**: No `import unittest`, no `import lgwks_redact`
2. **Re-defines module code**: Instead of importing `SECRET_RE` and `scrub` from the module, it re-defines them locally with a broken regex
3. **Broken regex**: Uses `\\s` (escaped backslash) instead of `\s` — the regex won't match
4. **No sys.path setup**: Unlike the reference test pattern

**Impact**: Even if the file were written, the test would fail immediately.

---

## F3: OllamaProvider Env Reading (FIXED)

**Before**: `self._api_key = api_key` — empty string if not explicitly passed
**After**: `self._api_key = api_key or os.environ.get("OLLAMA_API_KEY", "")`

**Impact**: 401 Unauthorized when constructing OllamaProvider without explicit api_key

---

## F4: Shell Tool Security (FIXED)

**Before**: `subprocess.run(command, shell=True)` — command injection vulnerability
**After**: `shlex.split(command)` with `shell=False` default, fallback to `shell=True` for complex commands

**New behavior**: Shell builtins (`exit`, `source`, `alias`) fail with "No such file or directory" when run without a shell. This is correct security behavior.

---

## F5: Test Shell Builtins (FIXED)

**Before**: Tests used `exit 1` and `exit 127` as failing commands
**After**: Tests use `false` (a real executable) and `nonexistent_command_xyz_12345`

---

## Agent Execution Trace

```
Step 1: read_file(lgwks_redact.py) → SUCCESS (32 lines read)
Step 2: read_file(lgwks_proc.py) → SUCCESS (40 lines read)
Step 3: read_file(test_algorithms.py) → SUCCESS (reference pattern)
Step 4: finish(output=<write_file JSON as string>) → FAILURE (no file written)
```

**edits_made**: [] (empty — no files modified)
**Verification**: "Agent completed without modifying any files. Task implies code changes were expected."

---

## Recommendations

### Immediate (v0.4.0)
1. **Fix nested JSON parsing**: Add unwrapping logic in `_parse_response`
2. **Add `_task_implies_edits` check to finish action**: If task requires code changes, `finish` without edits should be flagged
3. **Write tests manually** for issue #349 (done — 28 tests passing)

### v0.4.1
4. **Add structured output validation**: Verify model output matches expected JSON schema before parsing
5. **Add retry on malformed output**: If parse fails, re-prompt with error message
6. **Add tool call verification**: After executing a tool, verify the result matches expected schema

### v0.5.0
7. **Add checkpoint/resume**: Save agent state after each step for debugging
8. **Add reasoning trace export**: Full JSONL trace of every decision
9. **Add cost tracking**: Per-step token usage and cost

---

## Files Modified

### forge-sdk
- `src/forge_sdk/models/ollama.py` — Added `os.environ.get("OLLAMA_API_KEY")` fallback
- `src/forge_sdk/tools/shell.py` — `shell=True` → `shlex.split()` + audit logging
- `src/forge_sdk/tools/filesystem.py` — Added file size limits, path containment
- `tests/test_smoke.py` — Fixed shell builtin tests

### lgwks
- `tests/test_lgwks_redact.py` — NEW: 18 tests for credential redaction
- `tests/test_lgwks_proc.py` — NEW: 10 tests for subprocess invocation
- `tests/test_module_coverage.py` — Removed lgwks_redact and lgwks_proc from EXCLUDED

---

## Test Results

### forge-sdk (46/46 passing)
```
tests/test_smoke.py::test_tool_spec_schema PASSED
tests/test_smoke.py::test_tool_spec_applies PASSED
tests/test_smoke.py::test_tool_result_as_message PASSED
...
tests/test_smoke.py::test_false_green_verification_fails_with_edit_task PASSED
```

### lgwks new tests (28/28 passing)
```
tests/test_lgwks_redact.py::TestSecretRe (9 tests) PASSED
tests/test_lgwks_redact.py::TestScrub (9 tests) PASSED
tests/test_lgwks_proc.py::TestIsGitRepo (4 tests) PASSED
tests/test_lgwks_proc.py::TestRunGit (6 tests) PASSED
```

### Module coverage gate (2/2 passing)
```
tests/test_module_coverage.py::test_every_called_module_has_a_test_import PASSED
tests/test_module_coverage.py::test_excluded_list_is_honest PASSED
```
Debt reduced: 19 → 17 modules remaining
