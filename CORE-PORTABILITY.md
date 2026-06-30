# CORE-PORTABILITY.md

**INV-107: Python is interim — keep core portable for edge/native end-state.**

This document classifies every module in `src/forge_sdk` by portability to non-Python targets (Rust, WASM, native edge).

---

## Module Classification Table

| Module | Classification | Reason | Dependencies |
|--------|---------------|--------|--------------|
| `agents/types.py` | EDGE-PORTABLE | Pure dataclasses (AgentContext, AgentStep, AgentResult). No I/O. | `dataclasses`, `typing` |
| `agents/__init__.py` | EDGE-PORTABLE | Protocol definition only. No logic. | `typing` |
| `agents/react.py` | NEEDS-PORT | Core loop logic is portable, but uses `asyncio` for concurrency. Re-hostable with async abstraction layer. | `asyncio`, `hashlib`, `json`, `re`, `logging` |
| `tools/types.py` | EDGE-PORTABLE | ToolResult (frozen dataclass) and ToolSpec (dataclass with JSON Schema). Protocol-typed. | `dataclasses`, `typing`, `collections.abc` |
| `tools/registry.py` | EDGE-PORTABLE | Pure in-memory registry. No I/O. | `typing` |
| `tools/filesystem.py` | NEEDS-PORT | File I/O operations. Abstractable via filesystem port layer. | `os`, `pathlib` |
| `tools/search.py` | NEEDS-PORT | `grep` shells out to `rg` (ripgrep). `glob` uses pathlib. Both need process abstraction. | `subprocess`, `pathlib` |
| `tools/shell.py` | NEEDS-PORT | Subprocess execution. Needs process isolation abstraction for WASM/edge. | `subprocess` |
| `models/types.py` | EDGE-PORTABLE | Pure dataclasses (Usage, ModelResponse, ModelChunk). No I/O. | `dataclasses` |
| `models/port.py` | EDGE-PORTABLE | **Protocol primitive.** ModelPort protocol definition only. | `typing` |
| `models/registry.py` | EDGE-PORTABLE | Pure in-memory registry. No I/O. | `typing` |
| `models/ollama.py` | NEEDS-PORT | HTTP client via `httpx`. Needs HTTP abstraction layer. | `httpx`, `json` |
| `models/deepseek.py` | NEEDS-PORT | HTTP client via `httpx`. Needs HTTP abstraction layer. | `httpx`, `os` |
| `models/openrouter.py` | NEEDS-PORT | HTTP client via `httpx`. Needs HTTP abstraction layer. | `httpx`, `os` |
| `verifiers/__init__.py` | NEEDS-PORT | Verification gates use `ast` (Python-specific), `subprocess` (shell dry-run). SemanticCheck uses ModelPort. | `ast`, `json`, `subprocess`, `time` |
| `tracing/span.py` | EDGE-PORTABLE | Pure dataclass with `to_dict()`. Timestamps from `time.time()` are stdlib-portable. | `time`, `uuid` |
| `tracing/tracer.py` | NEEDS-PORT | In-memory span management is portable. `export_jsonl()` writes files. | `json`, `uuid`, `pathlib` |
| `audit/__init__.py` | NEEDS-PORT | AuditLog uses `sqlite3` for persistence. Hash-chain logic is portable. | `hashlib`, `json`, `sqlite3`, `time`, `uuid` |
| `audit/eventsink.py` | EDGE-PORTABLE | **Protocol primitive.** EventSink protocol definition only. JSON-serializable payloads. | `typing` |
| `audit/daemon_sink.py` | NEEDS-PORT | Bridges to lgwks via subprocess. Batch buffer logic is portable. | `json`, `subprocess` |
| `eval/harness.py` | DEV-ONLY | Benchmark evaluation harness. Not needed in production edge. | `re`, `time`, `dataclasses` |
| `eval/runner.py` | DEV-ONLY | Test execution via subprocess. Development tooling only. | `subprocess`, `tempfile` |
| `config/__init__.py` | NEEDS-PORT | Loads from JSON files and env vars. Logic is portable; I/O layer needs abstraction. | `json`, `os`, `pathlib` |
| `cli/main.py` | DEV-ONLY | CLI entry point with argparse. Development tooling only. | `argparse`, `json`, `sys`, `time` |
| `policies/__init__.py` | EDGE-PORTABLE | Empty module. No code. | None |

---

## Three Protocol-Typed Primitives (Must Be Re-Hostable)

These are the canonical interfaces that any target language MUST implement:

### 1. `ModelPort` — `models/port.py:11`

```python
class ModelPort(Protocol):
    name: str
    provider: str
    context_window: int
    max_output: int
    supports_reasoning: bool
    def complete(messages, temperature, max_tokens, stop) -> ModelResponse
    def complete_stream(messages, temperature, max_tokens, stop) -> list[ModelChunk]
```

**Why it matters:** Every model provider (Ollama, DeepSeek, OpenRouter) implements this protocol. A Rust/WASM re-implementation needs trait/struct equivalents with the same method signatures. The JSON wire format for `messages`, `ModelResponse`, and `ModelChunk` is the portable contract.

### 2. `ToolSpec` — `tools/types.py:42`

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict   # JSON Schema
    output_schema: dict  # JSON Schema
    stable_id: str
    handler: Callable[..., Awaitable[ToolResult]]
```

**Why it matters:** Tool specifications are pure JSON Schema. The `handler` field is Python-specific, but the schema is portable. A Rust re-implementation would use a trait object for the handler while keeping the JSON schemas identical.

### 3. `EventSink` — `audit/eventsink.py:8`

```python
class EventSink(Protocol):
    def submit(event: dict[str, Any]) -> None
    def flush() -> None
```

**Why it matters:** The simplest protocol. Any target language implements `submit(dict)` and `flush()`. The contract is: payloads are plain JSON, no Python objects on the wire.

---

## Priority Porting Order

### Tier 1 — Port First (Core runtime, zero Python I/O)

These modules have ZERO Python-specific I/O dependencies. They are pure logic + data types:

1. **`models/types.py`** — `Usage`, `ModelResponse`, `ModelChunk` (frozen dataclasses → Rust structs)
2. **`models/port.py`** — `ModelPort` protocol (→ Rust trait)
3. **`models/registry.py`** — `ProviderRegistry` (→ Rust HashMap + trait objects)
4. **`tools/types.py`** — `ToolResult`, `ToolSpec` (→ Rust structs + trait)
5. **`tools/registry.py`** — `ToolRegistry` (→ Rust HashMap)
6. **`agents/types.py`** — `AgentContext`, `AgentStep`, `AgentResult` (→ Rust structs)
7. **`agents/__init__.py`** — `Agent` protocol (→ Rust trait)
8. **`tracing/span.py`** — `Span`, `SpanEvent`, `SpanKind`, `SpanStatus` (→ Rust structs + enums)
9. **`audit/eventsink.py`** — `EventSink` protocol (→ Rust trait)

### Tier 2 — Port Second (Needs I/O abstraction layer)

These modules work but depend on Python stdlib I/O. Create abstraction traits:

10. **`agents/react.py`** — ReAct loop. Needs async abstraction (tokio in Rust).
11. **`tools/filesystem.py`** — File ops. Needs `FileSystem` trait.
12. **`tools/search.py`** — grep/glob. Needs `ProcessRunner` trait.
13. **`tools/shell.py`** — Shell exec. Needs `ProcessRunner` trait.
14. **`tracing/tracer.py`** — Span management + JSONL export. Export needs file I/O abstraction.
15. **`audit/__init__.py`** — AuditLog. SQLite → any embedded DB or append-only file.
16. **`config/__init__.py`** — Config loading. JSON parse is portable; file/env I/O needs abstraction.

### Tier 3 — Port Third (Provider implementations)

HTTP client abstraction needed:

17. **`models/ollama.py`** — Ollama HTTP provider
18. **`models/deepseek.py`** — DeepSeek HTTP provider
19. **`models/openrouter.py`** — OpenRouter HTTP provider

### Tier 4 — Port Last (Verification pipeline)

Python-specific AST parsing:

20. **`verifiers/__init__.py`** — Gates use `ast.parse()` (Python-specific). SemanticCheck is portable (uses ModelPort). Need language-specific AST parsers for Rust target.

### Do Not Port (DEV-ONLY)

21. **`eval/harness.py`** — Benchmark evaluation
22. **`eval/runner.py`** — Test execution
23. **`cli/main.py`** — CLI entry point
24. **`policies/__init__.py`** — Empty

---

## Zero-Python Deps (Pure JSON / stdlib-only)

These modules have ZERO Python-only dependencies (no `httpx`, no `sqlite3`, no `subprocess`). They can be transpiled to JSON Schema definitions or pure logic in any language:

| Module | Why Zero-Deps |
|--------|---------------|
| `models/types.py` | Frozen dataclasses only. JSON-serializable by design. |
| `models/port.py` | Protocol definition only. No implementation. |
| `models/registry.py` | In-memory HashMap. No I/O. |
| `tools/types.py` | Dataclasses + JSON Schema dicts. |
| `tools/registry.py` | In-memory HashMap. No I/O. |
| `agents/types.py` | Dataclasses only. |
| `agents/__init__.py` | Protocol definition only. |
| `tracing/span.py` | Dataclass + `time.time()` (portable). |
| `audit/eventsink.py` | Protocol definition only. |
| `policies/__init__.py` | Empty. |

**Total: 10 modules** are fully zero-Python-deps.

---

## Migration Notes for Rust/WASM Re-Implementation

### 1. Protocol → Trait Mapping

Python `Protocol` maps directly to Rust `trait`:

```rust
// models/port.rs
pub trait ModelPort {
    fn name(&self) -> &str;
    fn provider(&self) -> &str;
    fn context_window(&self) -> usize;
    fn max_output(&self) -> usize;
    fn supports_reasoning(&self) -> bool;
    fn complete(&self, messages: &[Message], temperature: f64, max_tokens: Option<usize>, stop: Option<&[String]>) -> ModelResponse;
    fn complete_stream(&self, messages: &[Message], temperature: f64, max_tokens: Option<usize>, stop: Option<&[String]>) -> Vec<ModelChunk>;
}
```

### 2. Frozen Dataclass → Struct

Python `@dataclass(frozen=True)` maps to Rust `#[derive(Clone, Debug, Serialize, Deserialize)]`:

```rust
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModelResponse {
    pub content: String,
    pub reasoning: Option<String>,
    pub model: String,
    pub provider: String,
    pub usage: Usage,
    pub finish_reason: String,
    pub raw: serde_json::Value,
}
```

### 3. JSON Schema Contracts

The `input_schema` and `output_schema` fields in `ToolSpec` are already JSON Schema. These are language-agnostic. A Rust re-implementation validates tool inputs against these schemas using `jsonschema` crate.

### 4. Async Abstraction

Python's `asyncio` maps to:
- **Rust**: `tokio` or `async-std`
- **WASM**: JavaScript Promises via `wasm-bindgen`
- **Edge native**: Thread pool or event loop

The `ReactAgent.arun()` method is the hot loop. Its async core (model.complete → tool.execute → next step) translates directly to any async runtime.

### 5. HTTP Client Abstraction

All three model providers use `httpx.Client`. Create a port layer:

```rust
pub trait HttpClient {
    fn post(&self, url: &str, headers: &Headers, body: &[u8]) -> Response;
}
```

Implementations: `reqwest` (Rust), `fetch` (WASM), native sockets (edge).

### 6. Storage Abstraction

`AuditLog` uses SQLite. Alternatives for target platforms:
- **Rust**: `rusqlite` (same API), or `sled` (embedded KV)
- **WASM**: IndexedDB via `idb` crate, or in-memory + periodic flush
- **Edge**: Append-only JSONL file (no SQLite needed)

### 7. Process Isolation

`verifiers/__init__.py` and `tools/shell.py` use `subprocess`. For WASM/edge:
- Replace with sandboxed execution (WASM modules are inherently isolated)
- Or use `wasm-bindgen` for JavaScript host calls
- For Rust: `std::process::Command` or container-based isolation

### 8. Wire Format Stability

The JSON wire format between components is the portable contract. Document and freeze:

- `ModelResponse` JSON: `{"content": "...", "reasoning": "...", "model": "...", "provider": "...", "usage": {...}, "finish_reason": "..."}`
- `ToolResult` JSON: `{"success": true, "output": "...", "error": "...", "metadata": {...}}`
- `Span` JSON: `{"span_id": "...", "trace_id": "...", "name": "...", "kind": "...", "attributes": {...}}`
- `AuditEntry` JSON: `{"entry_id": "...", "timestamp": ..., "trace_id": "...", "entry_type": "...", "payload": {...}, "previous_hash": "...", "entry_hash": "..."}`

---

## Summary

| Category | Count | Modules |
|----------|-------|---------|
| EDGE-PORTABLE | 10 | types, protocols, registries, empty modules |
| NEEDS-PORT | 11 | I/O, HTTP, subprocess, SQLite, async |
| DEV-ONLY | 4 | eval, CLI, policies (empty) |
| **Total** | **25** | |

**Key insight:** 40% of the codebase (10/25 modules) is already zero-Python-deps and can be transpiled directly. The remaining 44% (11 modules) needs abstraction layers but the logic is portable. Only 16% (4 modules) is dev-only and can be excluded from edge builds.
