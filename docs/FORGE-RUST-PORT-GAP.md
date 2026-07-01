# Forge Rust Port — Gap Analysis

**Source of truth:** `google-genai-rs` v0.3.0 (already ports forge patterns), MCP `rust-sdk` v1.7.0, `keel-core`, `rust-skills` (265 rules, 26 categories)
**Python baseline:** `FORGE-EXPERIENCE-SPEC.md` (5 phases, 10 hardening amendments)
**Goal:** After merging Python implementation, re-host forge v1 core to Rust

---

## What Already Exists (the foundation)

### google-genai-rs v0.3.0 — forge patterns already ported

| Forge Python concept | Rust equivalent | File | Status |
|---|---|---|---|
| Event types | AgentEvent + EventKind | `agents/event.rs` | ⚠️ Has ToolCaller discriminator; missing THINK/OBSERVE/DECIDE/StateUpdate |
| Verification pipeline | VerifierGate + VerificationContext | `agents/verifier.rs` | ⚠️ 3-gate only (forge has 5) |
| Session/context | AgentState + SessionService | `agents/session.rs` | ⚠️ Key-value only, no execution contract fields |
| Agent loop | Runner + Agent trait | `agents/runner.rs` | ✅ Trait-based, async, session lifecycle |
| LoopGuard | Branch-level hash dedup | `agents/parallel.rs` | ✅ Hash-based repeat detection |
| Adaptive learning | AdaptiveSystemPrompt + LearningStore | `agents/adaptive.rs` | ✅ Full port with confidence scores |
| Parse strategies | parse() / parse_with_retry() | `agents/parse.rs` | ✅ Schema validation |
| MCP connector | McpConnector | `agents/mcp.rs` | ✅ |
| Tool registry | DeferredTool + DeferredToolRegistry | `agents/tool_search.rs` | ✅ |
| Escalation ladder | EscalationRecord (L0-L5) | `sem/escalation.rs` | ✅ |
| Strategy registry | StrategyRegistry pattern | `sem/registry.rs` | ✅ |
| Context packet | AI_CONTEXT_PACKET | `sem/context.rs` | ✅ |
| Taint/provenance | TaintGate + ProvenanceRecord | `sem/taint.rs` | ✅ |
| Energy/quality | EnergyFunction + QualityVector | `anchor/energy.rs` | ✅ |
| Agent mode | AgentMode (Chat/Task/SingleTurn) | `agents/mode.rs` | ⚠️ Collab mode ≠ tool-permission mode |

### MCP rust-sdk v1.7.0
- Full MCP protocol: tools, prompts, resources, tasks, progress, auth
- Multiple transports: stdio, HTTP, SSE, WebSocket, Unix socket, named pipes
- WASI/WASM support, Rust 2024 edition

### keel-core
- Functional safety engine, policy engine, verification seals
- Tree-sitter code analysis, supply chain tracking

---

## Critical Gaps (must fill for MVP Rust forge)

### 1. PermissionGate — tool-level permission state machine (L5a, H1, H6, H7)
- **Current state:** google-genai-rs has `AgentMode` (Chat/Task/SingleTurn) for collab-mode. This is NOT tool-permission-mode.
- **Needed:** `PermissionGate` with `PermissionStrategy` trait, `PermissionContext` struct, `ActionClassification` enum
- **Hard guardrails:** Protected paths (~/.ssh, ~/.aws, ~/.config) NEVER auto-allowed
- **Classification:** Must factor blast-radius (touches_auth, touches_config, touches_production, reversibility, evidence_available) per H1

### 2. Honest failure taxonomy (L4)
- **Current state:** `EventKind::Error` exists but is a flat enum variant with no structured cause
- **Needed:** `FailureReason` enum on `AgentResult`:
```rust
pub enum FailureReason {
    ModelError(String),
    UsageLimitExceeded,
    ConvergenceFailure { nudges: u32 },
    MaxStepsReached,
    VerificationFailed { gate: String, detail: String },
}
```
- Every break path must set this before returning — no lying about failures

### 3. CLI surface (L2-L5)
- **Current state:** google-genai-rs is library-only, no binary
- **Needed:** `clap`-based CLI with subcommands: run, doctor, session, eval, audit
- Flags: `--output-format`, `--print`, `--sandbox`, `--verify-command`, `--no-verify`, `--max-tokens`, `--max-cost`, `--permission-mode`, `--privacy-mode`
- Output renderers: `TextRenderer` (streaming ANSI) + `NDJSONRenderer` (machine pipe)
- Must respect `NO_COLOR` + `isatty`

### 4. Event taxonomy upgrade (L3, H2)
- **Current state:** `EventKind` = UserMessage, AgentReply, ToolCall, ToolResult, DelegationRequest, DelegationResult, Error, Final
- **Needed:** Add THINK, OBSERVE, StateUpdate, Decision variants
- Missing renderer pipeline: `trait EventRenderer { fn on_event(&self, event: &AgentEvent); fn on_end(&self, exit_code: i32); }`

### 5. forge doctor (L4, H4, H8)
- **Current state:** No self-diagnosis
- **Needed:** L0-L5 escalation checks, `--json` NDJSON output, `--docs` stub, EscalationRecord creation before model ping
- `escalation.rs` has the record type, just needs the doctor binary

### 6. Session execution contract (L5b, H3)
- **Current state:** `AgentState` is HashMap<String, Value> — unstructured
- **Needed:** Typed `Session` struct with execution contract fields: objective, current_phase, assumptions, constraints, evidence[], unresolved_questions[], next_actions[], stop_conditions[]
- `validate_execution_contract()` method that returns violations

### 7. Verifier expansion (L2, H5)
- **Current state:** 3-gate (syntactic → semantic → provenance)
- **Needed:** 5-gate (syntactic → AST → entity → build/test → spec-conformance → semantic)
- Map to 10-evidence taxonomy: grounding, type, correctness, invariant, boundary, resource, security, observability, falsifiability, locality

### 8. AgentResult with failure_reason propagation
- **Current state:** `AgentEvent` carries events but there is no terminal `AgentResult` struct
- **Needed:** `AgentResult { success, output, steps, trace_id, total_tokens, total_cost, verification[], edits_made[], named_targets_missing[], failure_reason }`

---

## Architecture: Recommended Workspace (Option C — Hybrid)

```
forge-rs/
├── Cargo.toml              (workspace)
├── forge-core/             Traits + types only (zero provider deps)
│   ├── src/
│   │   ├── lib.rs
│   │   ├── agent.rs         Agent trait, AgentResult, FailureReason
│   │   ├── event.rs         All 11 event variants + EventRenderer trait
│   │   ├── model.rs         ModelPort trait (complete, complete_stream)
│   │   ├── permission.rs    PermissionGate, PermissionStrategy, PermissionContext, ActionClassification
│   │   ├── session.rs       Session with execution contract, SessionStore trait
│   │   ├── verifier.rs      Multi-gate VerifierPipeline, VerificationEvidence
│   │   ├── guard.rs         LoopGuard, UsageLimiter, ContextManager
│   │   └── doctor.rs        DoctorCheck, DoctorReport, EscalationRecord
│   └── Cargo.toml           Deps: async-trait, thiserror, serde, serde_json, tokio(rt+macros)
├── forge-gemini/           google-genai-rs → ModelPort impl
├── forge-ollama/           reqwest REST → ModelPort impl
├── forge-openai/           reqwest REST → ModelPort impl
├── forge-cli/              clap binary: run, doctor, session, eval, audit
│   ├── src/
│   │   ├── main.rs          CLI entry point
│   │   ├── render.rs        TextRenderer, NDJSONRenderer (implements EventRenderer)
│   │   └── commands/        run.rs, doctor.rs, session.rs, eval.rs, audit.rs
│   └── Cargo.toml           Deps: forge-core, clap, tokio(full), tracing, dirs
└── forge-mcp/              MCP rust-sdk integration
```

### Core dependencies (forge-core)
```toml
[dependencies]
async-trait = "0.1"
thiserror = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["rt", "macros"] }
uuid = { version = "1", features = ["v4", "serde"] }
```

### Rust-skills rules to enforce
| Category | Key rules |
|---|---|
| `err-*` | `thiserror` for lib errors, `anyhow` for binaries |
| `own-*` | Borrow > clone, `Cow` for optional ownership, `Arc<RwLock<T>>` over `Mutex<T>` |
| `async-*` | `tokio::spawn` for concurrency, `FuturesUnordered`, avoid blocking in async |
| `cli-*` | `clap` derive API, meaningful exit codes, `--json` for machine consumers |
| `test-*` | `proptest` for property-based, integration tests for CLI, `#[tokio::test]` |
| `mem-*` | `impl Trait` over `Box<dyn Trait>` where possible, prefer stack allocation |
| `api-*` | Builder pattern for config, `#[non_exhaustive]` on public structs |

---

## Implementation Order (post-Python merge)

1. **forge-core types + traits** (no providers yet)
   - `FailureReason`, `AgentEvent` (all variants), `AgentResult`
   - `ModelPort`, `Agent`, `EventRenderer` traits
   - `PermissionGate`, `PermissionStrategy`, `PermissionContext`, `ActionClassification`
   - `Session` with execution contract
   - `VerifierPipeline` (5 gates)
   - `LoopGuard`, `ContextManager`

2. **forge-cli** (human surface)
   - clap CLI: `forge run`, `forge doctor`, `forge session`, `forge eval`, `forge audit`
   - TextRenderer + NDJSONRenderer
   - Exit codes + `NO_COLOR` + `isatty`

3. **forge-gemini** (first provider)
   - Wrap google-genai-rs Client in ModelPort trait
   - Wire to forge-cli

4. **forge-ollama + forge-openai** (additional providers)

5. **forge-mcp** (tool ecosystem)

---

## Key Risks

1. **`AgentMode` ≠ `PermissionMode`**: google-genai-rs has collab modes, forge needs tool-permission modes. Do NOT conflate.
2. **Event taxonomy mismatch**: google-genai-rs tracks USER→AGENT→TOOL→DELEGATION. Forge tracks THINK→ACT→OBSERVE→VERIFY→DECIDE→PRINT. Must extend (either enrich google-genai-rs EventKind or build forge-core's own event system that wraps it).
3. **Verifier depth**: 3 gates in Rust vs 5+ in Python. Needs expansion.
4. **No CLI precedent**: google-genai-rs is library-only. CLI is entirely new.
5. **Dependency hygiene**: forge-core must stay minimal (async-trait + thiserror + serde + tokio only). No reqwest, no chrono, no google-genai.
