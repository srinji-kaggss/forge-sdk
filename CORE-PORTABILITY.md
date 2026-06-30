# CORE-PORTABILITY.md — INV-107 Edge/Portability Classification

Python is v1 scaffolding. The final runtime is native (Rust/WASM). This document classifies every module by re-hostability.

## Classification Legend

- **edge-portable**: No Python-only deps in hot path. Can be ported to Rust/WASM as-is.
- **needs-port**: Has Python-specific dependencies that need native equivalents.
- **dev-only**: CLI, dev tools, test infrastructure. Not part of the runtime core.

## Module Classification

### Hot Path (step loop / model call / tool dispatch)

| Module | Status | Notes |
|--------|--------|-------|
| `agent_loop/react.py` | **edge-portable** | Async core, no Python-only deps. asyncio → tokio/wasm-bindgen. |
| `agent_loop/loop_guard.py` | **edge-portable** | Pure hash + dict. Trivially portable. |
| `agents/types.py` | **edge-portable** | Dataclasses → serde structs. JSON-serializable. |
| `policy/__init__.py` | **edge-portable** | Pure data + time. No I/O beyond dict operations. |
| `verifiers/__init__.py` | **needs-port** | Uses `subprocess` for shell_dry_run, `ast` for parsing. Rust: `syn` crate, `std::process`. |
| `memory/__init__.py` | **needs-port** | SQLite via Python sqlite3. Rust: `rusqlite` or `sled`. |
| `events/__init__.py` | **needs-port** | SQLite event store. Same as memory. |

### Protocol Layer (portability seams — must stay JSON-serializable)

| Module | Status | Notes |
|--------|--------|-------|
| `models/port.py` (v1) | **edge-portable** | Protocol + dataclasses. JSON on the wire. |
| `tools/types.py` (v1) | **edge-portable** | ToolSpec/ToolResult are plain data. |
| `tracing/span.py` (v1) | **edge-portable** | GenAI semantic conventions. Pure data. |
| `audit/__init__.py` (v1) | **needs-port** | SQLite hash-chain. Port with `rusqlite`. |

### Dev/CLI Layer (not part of runtime core)

| Module | Status | Notes |
|--------|--------|-------|
| `cli/main.py` (v1) | **dev-only** | Click CLI. Not shipped to edge. |
| `eval/harness.py` (v1) | **dev-only** | Eval infrastructure. Runs on host, not edge. |
| `eval/runner.py` (v1) | **dev-only** | Subprocess test runner. Host-only. |
| `config/__init__.py` (v1) | **dev-only** | Env/file config. Edge gets config via API. |

## Portability Rules

1. **Tool I/O + event payloads = plain JSON** (no Python objects on the wire)
2. **No Python-only deps in hot path** — confine `asyncio`, `sqlite3`, `subprocess` to needs-port or dev-only
3. **Protocol boundaries stay typed + JSON-serializable** — these are the seams where Rust/WASM plugs in
4. **Edge binary**: single static binary, no GC, cold-start < 50ms, WASM embeddable

## Rust Equivalent Map

| Python | Rust | WASM |
|--------|------|------|
| `asyncio` | `tokio` | `wasm-bindgen-futures` |
| `sqlite3` | `rusqlite` / `sled` | `sql.js` |
| `hashlib` | `sha2` | `ring` |
| `subprocess` | `std::process` | N/A (no process in WASM) |
| `dataclasses` | `serde` structs | `serde` |
| `json` | `serde_json` | `serde_json` |
| `re` | `regex` | `regex` (WASM via wasm-pack) |
