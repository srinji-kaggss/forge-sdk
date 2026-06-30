---
okf: research_log.v1
id: RL-FORGE-001
title: Agent Self-Test Failures — lgwks issue #349
date: 2026-06-30
actor: forge-agent (gemma3:4b via Ollama Cloud)
task: Write tests for lgwks_redact and lgwks_proc
status: completed_with_failures
---

# Research Log: Agent Self-Test on lgwks issue #349

## Hypothesis

Using forge-sdk's own ReactAgent to work on a real lgwks issue will reveal framework bugs that hypothetical testing missed.

## Method

1. Selected lgwks issue #349 (backfill 19 untested modules)
2. Chose two smallest modules: `lgwks_redact` (32 lines) and `lgwks_proc` (40 lines)
3. Configured ReactAgent with 4 tools: read_file, write_file, list_dir, run_command
4. Ran agent against Ollama Cloud (gemma3:4b) with the task prompt
5. Observed agent behavior, logged failures

## Raw Data

### Run 1: Before fixes (4 steps, 0 edits)

```
Step 1: read_file(lgwks_redact.py) → SUCCESS
Step 2: read_file(lgwks_proc.py) → SUCCESS
Step 3: read_file(test_algorithms.py) → SUCCESS
Step 4: finish(output=<write_file JSON string>) → FAILURE
```

**edits_made**: [] (empty)
**Failure**: Agent emitted `finish` with `write_file` JSON as string in output field.

### Run 2: After OllamaProvider env fix (4 steps, 0 edits)

Same behavior. The agent still emits `finish` with nested JSON.

### Run 3: After nested JSON unwrapper (4 steps, 0 edits)

The unwrapper correctly identifies the inner `write_file`, but the outer action is still `finish`, so `is_final = True` and the tool is never executed.

### Run 4: After first-valid-json strategy (5 steps, 1 edit)

```
Step 1-3: read files → SUCCESS
Step 4: write_file(test_lgwks_redact.py) → SUCCESS (1308 bytes written)
Step 5: finish(output=<write_file for proc>) → FAILURE (second tool call lost)
```

**edits_made**: ['/Users/srinji/logicalworks-/tests/test_lgwks_redact.py']
**Improvement**: First tool call now executes. Second tool call still lost.

### Run 5: After full strategy refactor (13 steps, 3 edits)

```
Step 1-3: read files → SUCCESS
Step 4: write_file(test_lgwks_redact.py) → SUCCESS
Step 5: write_file(test_lgwks_proc.py) → SUCCESS
Step 6-8: run_command(pytest) → FAILED (exit code 2, syntax errors in generated code)
Step 9: read_file(test_lgwks_redact.py) → SUCCESS
Step 10: write_file(fixed test_lgwks_redact.py) → SUCCESS
Step 11: read_file(test_lgwks_proc.py) → SUCCESS
Step 12: run_command(pytest) → BLOCKED (LoopGuard: same args 3x)
Step 13: finish(summary) → SUCCESS
```

**edits_made**: 3 files modified
**LoopGuard**: Correctly triggered after 3 identical pytest runs
**Agent behavior**: Graceful finish with summary instead of crash

## Observations

1. **Nested JSON problem (F1)**: gemma3:4b emits tool calls inside `finish` action's output field. The model constructs the correct call in reasoning but wraps it in `finish`. Fixed by: (a) unwrapping nested JSON, (b) finding first valid JSON object in concatenated output.

2. **Code quality (F2)**: gemma3:4b generates test code with syntax errors (nested quotes, missing imports, broken regex). Expected for 4B model. The framework handles this gracefully — LoopGuard prevents infinite retry loops.

3. **Provider auth (F3)**: OllamaProvider didn't read `OLLAMA_API_KEY` from env. Fixed by adding `os.environ.get()` fallback.

4. **Shell security (F4)**: `shell=True` allowed command injection. Fixed by using `shlex.split()` with `shell=False` default.

5. **Strategy pattern (refactor)**: Replaced nested if/elif chains with typed strategy registry (PARSE-001 through PARSE-003). Each strategy has stable ID, `applies()`, and `execute()`. Debug logging traces which strategy matched.

## Next Steps

1. **v0.4.1**: Add structured output validation — verify model output matches JSON schema before parsing
2. **v0.4.1**: Add retry on malformed output — re-prompt with error message
3. **v0.5.0**: Add checkpoint/resume — save agent state after each step
4. **v0.5.0**: Add reasoning trace export — full JSONL of every decision

## Conclusion

The hypothesis was confirmed: self-testing revealed 5 bugs that hypothetical analysis missed. The framework is now sound (strategy registry, nested JSON unwrapping, LoopGuard, env reading). The model (gemma3:4b) can follow the ReAct pattern but generates low-quality code — this is a model limitation, not a framework bug.
