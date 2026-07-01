---
okf: exdoc.document.v2
id: DOC-FORGE-001
title: Forge Rust Port — Implementation Playbook (Almost-Code Spec)
status: active
criticality: L3
audience:
  - ai_agent
  - human_engineer
  - reviewer
purpose:
  - Provide implementation-ready specifications for all forge-core modules
  - Enable parallel agent execution with zero ambiguity
  - Serve as truth source for SOC2/DO178C/IEC61508 certification traceability
owner: forge-engineering-team
review_cadence: on_change
interpretability:
  parse_mode: markdown_with_yaml_frontmatter
  normative_sections:
    - Requirements
    - Implementation
    - Verification
    - Failure Modes
research_logging_required: true
traces:
  requirements:
    - FORGE-RUST-TUI-SPEC.md
    - CHANGE_ORDER_MAP.md
    - TOPOLOGICAL_MAP.md
  design:
    - REFACTORED-PLAN-COMPLETE.md
  code: forge-core/src/
  tests: forge-harness/tests/
---

# Forge Rust Port — Implementation Playbook

<!-- CLAIM:CORE-001 MUST forge-core has zero heavyweight dependencies beyond async-trait, thiserror, serde, serde_json, tokio(rt+macros), uuid(v4+serde) -->
<!-- EVIDENCE:CORE-001 package=Cargo.toml, type=static_analysis -->
<!-- CLAIM:CORE-002 MUST all 16 forge-core modules compile independently without circular deps -->
<!-- EVIDENCE:CORE-002 package=lib.rs, type=static_analysis -->
<!-- CLAIM:CORE-003 MUST every AgentEvent carries Correlation keys (trace_id, run_id, model, provider) -->
<!-- EVIDENCE:CORE-003 package=event.rs, type=unit_test -->
<!-- CLAIM:CORE-004 MUST FailureReason variants cover all 7 terminal break paths -->
<!-- EVIDENCE:CORE-004 package=result.rs, type=unit_test -->

## 1. Architecture (DO-178C DAL A / IEC 61508 SIL 3 / SOC 2 Type II)

### 1.1 Three-Stack Architecture

```
CLI LAYER:  forge-cli (clap)  |  forge-tui (crossterm+ratatui)
                |                      |
CORE LAYER:  forge-core (zero-heavy-dep library)
                |
PROVIDERS:   forge-gemini | forge-ollama | forge-openai | forge-mcp
```

### 1.2 Requirements Traceability Matrix

| REQ-ID | Module | Requirement | Verification | SIL |
|--------|--------|-------------|-------------|-----|
| REQ-EVT-001 | event.rs | 13 discriminators with Correlation | Unit test each variant | SIL2 |
| REQ-EVT-002 | event.rs | Every event serializes to JSON | Serialize test | SIL2 |
| REQ-RES-001 | result.rs | AgentResult carries verification[] | Unit test | SIL3 |
| REQ-RES-002 | result.rs | FailureReason covers 7 variants | Match exhaustiveness | SIL3 |
| REQ-RES-003 | result.rs | .chars().take(n) not text[..n] | Unicode test | SIL2 |
| REQ-CTX-001 | context.rs | AgentContext has max_steps (ported); max_tokens/max_cost (⚠️ NEW fields, not in Python original — see §2.3) | Unit test | SIL2 |
| REQ-PORT-001 | port.rs | ModelPort trait with generate/generate_with_tools/count_tokens | Provider test | SIL2 |
| REQ-PORT-002 | port.rs | ModelError covers 6 variants | Match exhaustiveness | SIL2 |
| REQ-AGENT-001 | agent.rs | Agent trait with run/run_with_events | Smoke test | SIL3 |
| REQ-PERM-001 | permission.rs | PermissionGate in 3 modes (interactive/yolo/plan) | Unit all 3 | SIL3 |
| REQ-PERM-002 | permission.rs | Anti-slop gates active in ALL modes | Unit test | SIL3 |
| REQ-PERM-003 | permission.rs | ActionClassification covers 10 categories | Match exhaustiveness | SIL2 |
| REQ-VER-001 | verifier.rs | 6-gate pipeline (⚠️ CORRECTED 2026-07-01, was "5-gate Syntax→Lint→Tests→Property→Formal": real Python has 6 gates — SyntaxCheck→AstParse→EntityValidation→ShellDryRun→SpecConformance→SemanticCheck; PropertyCheck deferred to v2, FormalBound cut — see FORGE-RUST-TUI-SPEC.md §5) | Integration test | SIL3 |
| REQ-VER-002 | verifier.rs | Fail-fast on gate failure, budget-aware skip for SemanticCheck/PropertyCheck under pressure (NEW clause 2026-07-01) | Unit test | SIL2 |
| REQ-VER-003 | verifier.rs | VerificationEvidence carries stable_id + closed GateFailureReason (NEW 2026-07-01, replaces free-text detail) | Unit test | SIL2 |
| REQ-VER-004 | verifier.rs | VerificationContext defined with task/all_edits/output/solution_summary/model_port (⚠️ NEW ID 2026-07-01 — was undefined) | Unit test | SIL2 |
| REQ-SESS-001 | session.rs | Session save/load/list/delete | Integration test | SIL2 |
| REQ-SESS-002 | session.rs | FileSessionStore at ~/.forge/checkpoints/ | Unit test | SIL2 |
| REQ-DOC-001 | doctor.rs | L0-L5 DoctorEngine with escalation ladder | Integration test | SIL2 |
| REQ-DOC-002 | doctor.rs | DoctorStatus covers 4 variants | Match exhaustiveness | SIL1 |
| REQ-GRD-001 | guard.rs | LoopGuard with 5 break paths | Unit all 5 | SIL3 |
| REQ-GRD-002 | guard.rs | Convergence failure after N nudges | Unit test | SIL2 |
| REQ-SEC-001 | security.rs | Command::new().arg().output() NOT string parsing | Static analysis | SIL3 |
| REQ-SEC-002 | security.rs | Path traversal blocked | Unit test | SIL3 |
| REQ-SEC-003 | security.rs | NO_COLOR respected | Unit test | SIL1 |
| REQ-SEC-004 | security.rs | Sensitive read/write path denylist (⚠️ NEW ID, added 2026-07-01 — real Python security.py has this, original playbook never named it) | Unit test per entry | SIL3 |
| REQ-SEC-005 | security.rs | Network-egress command patterns blocked (curl/wget/nc/ssh/scp/etc.) (⚠️ NEW ID, same reason) | Unit test per pattern | SIL3 |
| REQ-SEC-006 | security.rs | Untrusted text reaches a prompt ONLY via `.category`, never `.raw_text`/`.truncated_excerpt` (⚠️ NEW ID, same reason — see §2.6, this is the GH #25 fix) | Unit + type-level test | SIL3 |
| REQ-TRC-001 | tracer.rs | Span with SpanKind, start/end timestamps | Unit test | SIL2 |
| REQ-TRC-002 | tracer.rs | TraceId propagation across spans | Integration test | SIL2 |
| REQ-AUD-001 | audit.rs | AuditEntry with hash chain | Unit test | SIL3 |
| REQ-AUD-002 | audit.rs | AuditLog append-only | Integration test | SIL3 |
| REQ-CFG-001 | config.rs | Config load/save at ~/.forge/config.json | Unit test | SIL2 |
| REQ-CFG-002 | config.rs | forge config init/show/set CLI commands | CLI test | SIL2 |
| REQ-RTR-001 | router.rs | AutoRouter with retry-backoff | Unit test | SIL2 |
| REQ-RTR-002 | router.rs | Model fallback chain on 429/404 | Integration test | SIL2 |
| REQ-SEM-001 | semantic.rs | SemanticLabel 8 variants + MeaningFrame | Unit test | SIL2 |
| REQ-OKF-001 | okf.rs | OkfDoc parse into ClaimGraph/InvariantIndex/ProofObligationQueue | Integration test | SIL2 |
| REQ-EXP-001 | experience.rs | Episode schema matching event-experience.schema.json | Schema conformance | SIL2 |

### 1.3 Failure Modes and Effects Analysis (FMEA)

| Module | Failure Mode | Effect | Cause | Detection | SIL | Mitigation |
|--------|-------------|--------|-------|-----------|-----|------------|
| event.rs | Missing Correlation | Broken traceability | Serialization bug | Tracer validation | SIL2 | .chars().take(n) |
| result.rs | FailureReason omitted | False success | Branch without set | Compiler lint | SIL3 | Exhaustive match gate |
| permission.rs | Gate allows when denied | Unsafe action | Logic error | Anti-slop | SIL3 | Dual verification |
| verifier.rs | Gate passes when failed | False verification | Test flake | Redundant gate | SIL3 | Evidence chain cross-check |
| session.rs | Corrupted checkpoint | Data loss | Write crash | CRC + atomic write | SIL2 | Crash recovery |
| guard.rs | Loop never breaks | Infinite or hung agent | Bug | Timeout watchdogs | SIL3 | Multiple break paths |
| security.rs | Command injection | RCE | Shell parsing | Static analysis | SIL3 | Command::new().arg() |
| security.rs | Untrusted text spliced into a prompt as free text | Prompt injection (this is the real GH #25 bug class, already fixed once in Python — see §2.6) | A sanitizer returns a plain String instead of a typed ContainmentResult, so a caller can compose the wrong field | Type-level: no free-text field reaches a prompt-construction call site | SIL3 | ContainmentResult typed boundary — category is the only field composable into a prompt |
| audit.rs | Tampered entry | No detection | Hash collision | Chain integrity | SIL3 | SHA-256 chain |

---

## 2. forge-core Module Specifications (Almost-Code)

### 2.1 event.rs — 13 Event Discriminators

**Purpose:** Single architectural hinge. Every human- and machine-facing feature consumes this event stream. ADR-1.

**Requirements:** REQ-EVT-001, REQ-EVT-002

**Implementation Contract:**

```rust
// The ONE enum. All 13 variants. No more, no less.
// Every variant carries Correlation { trace_id, run_id, model, provider, config_version }.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum AgentEvent {
    RunStart(RunStartEvent),
    RunEnd(RunEndEvent),
    RunError(RunErrorEvent),
    Think(ThinkEvent),
    Act(ActionEvent),
    Observe(ObservationEvent),
    Verify(VerificationEvent),
    FileEdit(FileEditEvent),
    TokenUsage(TokenUsageEvent),
    StateUpdate(StateUpdateEvent),
    Decide(DecisionEvent),
    Converge(ConvergenceEvent),
    PermissionGate(PermissionGateEvent),
}

// Each payload struct is a plain data container. No methods except new().
// All fields public for JSON serialization.
```

**Verification:**
- Unit test: every variant round-trips through JSON
- Unit test: every variant carries Correlation with non-empty fields
- Property test: serialization is lossless for all variants

**Failure Modes:**
| Mode | Effect | Mitigation |
|------|--------|------------|
| Missing variant | Compile error | Match exhaustiveness |
| Empty Correlation | Broken traceability | new() validates fields |
| JSON serde failure | Wire format break | #[serde(deny_unknown_fields)] |

### 2.2 result.rs — AgentResult + FailureReason

**Purpose:** The contract between agent and consumer. Every run produces exactly one AgentResult.

**Requirements:** REQ-RES-001, REQ-RES-002, REQ-RES-003

**Implementation Contract:**

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentResult {
    pub success: bool,
    pub output: String,                              // .chars().take(80) for summary
    pub steps: Vec<AgentStep>,                       // ordered execution trace
    pub total_tokens: u64,
    pub total_cost: f64,
    pub trace_id: String,
    pub run_id: String,
    pub model: String,
    pub provider: String,
    pub artifacts: HashMap<String, serde_json::Value>,
    pub verification: Vec<VerificationEvidence>,      // REQ-RES-001
    pub edits_made: Vec<String>,
    pub named_targets_missing: Vec<String>,
    pub failure_reason: Option<FailureReason>,        // REQ-RES-002: 7 variants
    pub change_manifest: Option<ChangeManifest>,      // H15
    pub semantic_labels: Vec<SemanticLabel>,           // REQ-SEM-001
    pub episode: Option<Episode>,                     // REQ-EXP-001
    pub partial_output: bool,                         // FORGE_FEEDBACK.md fix
}

// char_count_aware_summary() uses .chars().take(80) NOT text[..80]
impl AgentResult {
    pub fn char_count_aware_summary(&self) -> String {
        let status = if self.success { "SUCCESS" } else { "FAILED" };
        format!("{} | {} steps | {} tokens | verification: {} | {}...",
            status, self.steps.len(), self.total_tokens,
            self.verification_summary(),
            &self.output.chars().take(80).collect::<String>())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum FailureReason {
    ModelError(String),                   // provider returned error
    UsageLimitExceeded,                   // tokens or cost cap
    ConvergenceFailure { nudges: u32, detail: String }, // not converging
    MaxStepsReached,                      // step count exceeded
    VerificationFailed { gate: String, detail: String }, // gate rejected
    PermissionDenied { action: String, reason: String }, // gate blocked
    AuthenticationFailure { provider: String, detail: String }, // auth failed
}

impl FailureReason {
    pub fn is_recoverable(&self) -> bool {
        matches!(self, Self::ConvergenceFailure { .. } | Self::MaxStepsReached)
    }
    pub fn causal_sentence(&self) -> String {
        match self {
            Self::ModelError(e) => format!("model_error: {}", e),
            Self::UsageLimitExceeded => "usage_limit_exceeded".into(),
            Self::ConvergenceFailure { nudges, detail } =>
                format!("convergence_failure: {} nudges — {}", nudges, detail),
            Self::MaxStepsReached => "max_steps_reached".into(),
            Self::VerificationFailed { gate, detail } =>
                format!("verification_failed at '{}': {}", gate, detail),
            Self::PermissionDenied { action, reason } =>
                format!("permission_denied '{}': {}", action, reason),
            Self::AuthenticationFailure { provider, detail } =>
                format!("auth_failure {}: {}", provider, detail),
        }
    }
}
```

**Verification:**
- Unit test: each of 7 FailureReason variants round-trips through JSON
- Unit test: is_recoverable() returns correct values
- Unit test: causal_sentence() produces non-empty string for each
- Property test: FailureReason never empty string (typed enum guarantee)
- Unicode test: .chars().take(n) on multi-byte strings

---

### 2.2b step.rs — AgentStep

**⚠️ Second gap found alongside AgentContext**: `step.rs` is one of the 5 `phase_0_types` files (per the Implementation Sequence below) and `AgentResult.steps: Vec<AgentStep>` (§2.2) depends on it, but — like `AgentContext` — it is never actually defined anywhere in this spec, only named in the file tree. Ground truth: `src/forge_sdk/agents/types.py::AgentStep` (real, verified, no gaps).

**Implementation Contract:**

```rust
// Direct port of src/forge_sdk/agents/types.py::AgentStep.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentStep {
    pub step_number: u32,
    pub thought: String,
    pub action: String,              // tool name or "finish"
    pub action_input: HashMap<String, serde_json::Value>,
    pub observation: String,
    pub is_final: bool,
    pub loop_guard_triggered: bool,
}
```

**Verification:** JSON round-trip test; unit test that `LoopGuard`-triggered steps set `loop_guard_triggered: true` (this is how a consumer distinguishes a normal finish from a forced stop — don't let it default to always-false).

### 2.3 context.rs — AgentContext

**Purpose:** the mutable state threaded through the agent loop — Agent::run(ctx), LoopGuard::new(ctx), and every ToolHandler call read from this.

**⚠️ Gap found 2026-07-01 (Claude hardening pass), not in the original spec**: neither this playbook nor FORGE-RUST-TUI-SPEC.md ever actually DEFINES `AgentContext` — it's referenced 6 times (Agent trait, LoopGuard::new, Session.context) but never given a field list. Ground truth is `src/forge_sdk/agents/types.py::AgentContext` (real, verified): `task: str, cwd: str, max_steps: int, step_count: int, messages: list[dict], artifacts: dict`. **Also found: REQ-CTX-001 below (from the original playbook) claims AgentContext carries `max_tokens`/`max_cost` — false, those live on `ForgeConfig` (§2.7), not `AgentContext`, in the real Python.** Since `LoopGuard::new(ctx: &AgentContext)` (§6.1 of the master spec) genuinely needs a token/cost ceiling to check, this Rust port makes a deliberate, flagged EXTENSION beyond the straight Python port: add `max_tokens: Option<u64>` and `max_cost: Option<f64>` to `AgentContext`, populated from the same CLI flags (`--max-tokens`/`--max-cost`) that already exist in §9. This is not a port — it's a new field, added because the Rust LoopGuard design requires it and Python's `LoopGuard`-equivalent reads those limits from a different object. Flag it as such in code comments so a future reader doesn't assume it was ported.

**Requirements:** REQ-CTX-001 (corrected: max_steps is ported; max_tokens/max_cost are a new, intentional extension, not a port)

**Implementation Contract:**

```rust
// Ported from src/forge_sdk/agents/types.py::AgentContext, + 2 new fields
// (max_tokens, max_cost) not present in the Python original — see gap note above.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentContext {
    pub task: String,
    pub cwd: PathBuf,
    pub max_steps: u32,
    pub step_count: u32,
    pub messages: Vec<serde_json::Value>,     // Python: list[dict[str, Any]]
    pub artifacts: HashMap<String, serde_json::Value>,
    // NEW, not in Python AgentContext — populated from CLI --max-tokens/--max-cost
    pub max_tokens: Option<u64>,
    pub max_cost: Option<f64>,
}
```

**Verification:** unit test round-trips through JSON; unit test confirms LoopGuard::new(&ctx) reads max_tokens/max_cost correctly when set and treats None as "no ceiling" (matches CLI flags being optional, §9).

### 2.4 tracer.rs — Span, SpanKind, SpanStatus, Tracer

**Purpose:** observability primitive. Every AgentEvent's Correlation.trace_id is produced/consumed here.

**Ground truth**: direct, verified port of `src/forge_sdk/tracing/span.py` (real, complete — 4 types, no gaps).

**Implementation Contract:**

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SpanKind { Llm, Tool, Agent, Internal }   // Python: SpanKind.LLM/TOOL/AGENT/INTERNAL

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SpanStatus { Ok, Error, Unset }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpanEvent {
    pub name: String,
    pub timestamp_ms: i64,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Span {
    pub span_id: String,             // Python: uuid4().hex[:16]
    pub trace_id: String,            // Python: uuid4().hex
    pub parent_span_id: Option<String>,
    pub name: String,
    pub kind: SpanKind,
    pub start_time_ms: i64,
    pub end_time_ms: Option<i64>,
    pub attributes: HashMap<String, serde_json::Value>,
    pub events: Vec<SpanEvent>,
    pub status: SpanStatus,
}

impl Span {
    pub fn finish(&mut self, status: SpanStatus) { /* sets end_time_ms = now, self.status = status */ }
    pub fn add_event(&mut self, name: &str, attributes: HashMap<String, serde_json::Value>) { /* push SpanEvent */ }
    pub fn duration_ms(&self) -> Option<i64> { self.end_time_ms.map(|e| e - self.start_time_ms) }
}

pub struct Tracer {
    spans: Vec<Span>,
}
```

**Verification:** unit test `finish()` sets end_time+status; unit test `duration_ms()` returns None while running, Some after finish; JSON round-trip test matches Python's `to_dict()` field names/shape (`span_id`, `trace_id`, `parent_span_id`, `name`, `kind`, `start_time`, `status`, `attributes`, conditionally `end_time`/`duration_ms`/`events`) for CI/audit-consumer compatibility.

### 2.5 audit.rs — AuditEntry, AuditLog, hash-chain integrity

**Purpose:** SOC-PI-02's evidence ("Hash chain test") and REQ-AUD-001/002. This is the module that makes forge's audit trail tamper-evident — load-bearing for the "Confidentiality"/"Processing Integrity" claims in §3 of REFACTORED-PLAN-COMPLETE.md.

**Ground truth**: direct, verified port of `src/forge_sdk/audit/__init__.py` (real, complete, SQLite-backed — 173 lines, no gaps). Interesting side-note for the merger design (see REFACTORED-PLAN-COMPLETE.md Part 8): this hash-chain design (`entry_hash = sha256(previous_hash + sorted-json(payload))`, genesis `"0"*64`) is structurally the same append-only hash-chain shape as lgwks's OWN `lgwks_cognition.py` (verified real in CLAUDE-REVIEW.md §7.3) — two independent, compatible implementations of the same pattern. Worth deciding later whether forge's audit chain and lgwks's cognition-log chain should ever be the SAME chain (shared trace_id linking them, per Part 8) rather than two parallel ones — not resolved here, flagged for the Director.

**Implementation Contract:**

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub entry_id: String,           // Python: uuid4().hex[:16]
    pub timestamp: f64,
    pub trace_id: String,
    pub entry_type: String,         // "llm_call" | "tool_use" | "decision" | "eval_result"
    pub payload: serde_json::Value,
    pub previous_hash: String,
    pub entry_hash: String,
}

/// sha256(previous_hash + serde_json::to_string with SORTED keys of payload).
/// MUST sort keys — Python uses json.dumps(payload, sort_keys=True); an
/// unsorted Rust serialization would produce a different hash for
/// semantically-identical payloads and silently break chain verification
/// against any Python-written entries during the migration window.
fn compute_hash(previous_hash: &str, payload: &serde_json::Value) -> String { /* ... */ }

pub struct AuditLog {
    conn: rusqlite::Connection,      // or a forge-core-appropriate SQLite binding — see H-note below
}

impl AuditLog {
    pub fn open(db_path: &Path) -> Result<Self, SessionError> { /* CREATE TABLE IF NOT EXISTS audit_entries(...) + idx on trace_id, mirrors Python schema exactly */ }
    fn last_hash(&self) -> String { /* SELECT entry_hash ORDER BY timestamp DESC LIMIT 1, else "0".repeat(64) */ }
    pub fn append(&self, trace_id: &str, entry_type: &str, payload: serde_json::Value) -> Result<AuditEntry, SessionError> { /* ... */ }
    pub fn verify_integrity(&self) -> Vec<String> { /* walk ASC, recompute each hash, collect violation strings — mirrors Python exactly, including message text, since tooling/tests may grep for it */ }
    pub fn get_entries(&self, trace_id: Option<&str>, entry_type: Option<&str>, limit: u32) -> Vec<AuditEntry> { /* ... */ }
    pub fn count(&self) -> u64 { /* ... */ }
}
```

**⚠️ Dependency note**: this needs a SQLite binding (`rusqlite`) — not currently in forge-core's zero-heavy-dep list (async-trait/thiserror/serde/tokio/uuid). `rusqlite` is a real, mature, widely-used crate (already a dependency of the SIBLING `semantic-memory-brain` Rust port in this same project, per its Cargo.toml — so it's not a novel choice for this codebase). Flag for Director approval alongside `genai`/`reqwest` (CLAUDE-REVIEW.md §7.1) rather than assume it's pre-approved just because forge-core's dependency list didn't originally mention it.

**Verification:** unit test hash-chain continuity (3 sequential appends, verify_integrity() returns empty); unit test tamper detection (mutate one stored payload directly in the DB, verify_integrity() flags it); unit test genesis hash is exactly 64 zero chars, matching Python.

### 2.6 security.rs — SUPERSEDED 2026-07-01, moved to forge-core-security per SPEC-SECURITY-003

**⚠️ This section previously specced a free-function `check_path_safety`/`check_command_safety` + plain-struct `ContainmentResult` design, ported directly from `security.py`. That draft is now superseded, not just relocated — it conflicts with an already-Director-approved, already-merged design (`specs/SPEC-SECURITY-003-rust-core-compile-time-containment.md`, PR #35, with Phase-0 Python stopgaps PR #36/#37 already landed) that this 9→8-crate spec predates and never incorporated. Per CLAUDE.md prime directive 3 (one canonical implementation, kill duplicates), SPEC-SECURITY-003 wins — it is the more recent, Director-approved, partially-already-implemented plan. Read that document in full before touching anything security-related in this port; the summary below is not a substitute for it.**

**What changes, concretely, vs. the superseded draft above:**

1. **Free functions → compile-time-enforced newtypes.** The old draft's `check_path_safety(path, cwd, sandbox_dir, check_writes) -> Result<(), PathSafetyError>` is a runtime check a caller can forget to invoke — exactly the same "convention, not enforcement" weakness SPEC-SECURITY-002 named for the Python original. SPEC-SECURITY-003 §3.2 replaces this with `Tainted<T>` / `Trusted<T>` newtypes (built on the approved `untrusted_value` crate's `UntrustedValue<T>`, whose inner field is private — there is no code path that extracts a raw `T` without going through `.sanitize_with(fn)`). A `PromptFragment { content: Trusted<String> }` constructor call with a `Tainted<String>` **fails to compile** — a type error, not a lint warning that a busy contributor can miss. This is the concrete, buildable form of the Director's "near-zero natural text by output time" principle: it's not a style guideline, it's a type the compiler enforces.
2. **Path denylist → capability object.** The old draft's `SENSITIVE_READ_PATHS`/`SENSITIVE_WRITE_PATHS` const-array port inherits Python's actual, demonstrated failure mode: SPEC-SECURITY-003 §0.1 found live, this session, that `security.py`'s real denylist misses `.cline/data/settings/settings.json` (a real credential store not on the hardcoded list) — Claude Code's own semantic auto-mode classifier caught it; the path denylist did not. §3.3 replaces the denylist-as-primary-mechanism with `SandboxRoot` wrapping the approved `cap-std` crate's `Dir` capability: every file open is *relative to* a capability, and there is no API that accepts an absolute or sandbox-escaping path at all — "the illegal access has no function to call," not "a function that checks and (hopefully) rejects." `SENSITIVE_READ_PATHS`-style awareness becomes a secondary, defense-in-depth signal inside `SandboxRoot::open`, not the primary containment.
3. **`ContainmentResult` gets one field removed, not renamed.** SPEC-SECURITY-003 §3.2's version is `enum ContainmentResult { Safe { category: Category, risk_score: f32 }, Quarantined { risk_score: f32 } }` — note `Quarantined` carries **no text field at all**. The superseded draft above kept `raw_text`/`truncated_excerpt` on every variant "for logs only," which is weaker: a field that exists can still be reached by a determined or careless caller, even if documented as forbidden. Removing it from the quarantined case entirely (nothing to leak, structurally) is the stricter, correct version — apply this pattern project-wide per the Director's "unhackable" framing: **prefer removing a field over documenting it as forbidden, wherever the call site genuinely never needs it.**
4. **`check_command_safety`'s dangerous/network pattern lists stay** (L2/L3 in the old numbering) — SPEC-SECURITY-003 doesn't replace these, they're a real, still-needed defense-in-depth layer; they just live inside `forge-core-security`'s `SafetyGate`-trait-shaped checks (§3.1, reusing the same trait *pattern*, not a dependency, as `keel-core`'s already-shipped `gates.rs` — `Kleene::{True, False, Unknown}` with `Unknown` failing closed) rather than as bare free functions in forge-core.
5. **Crate location changed**, not just the internals: this logic now lives in the **separate `forge-core-security` crate** (FORGE-RUST-TUI-SPEC.md §1, added same pass), not `forge-core`. This is deliberate, not incidental — SPEC-SECURITY-003 Phase 1 ships it as a **Python-callable module first** (a subprocess JSON pipe: `{op, args}` → `{verdict, ...}` on stdin/stdout via `serde_json`) so the *currently-shipping* Python `forge-sdk` gets this hardening before the rest of the Rust core exists. Nesting it inside `forge-core` would block that on the whole Rust core landing first, defeating the sequencing SPEC-SECURITY-003 §4 lays out.

**Requirements:** REQ-SEC-001/002/003 (from the original playbook) and REQ-SEC-004/005/006 (added last pass) all still apply, but now trace to `forge-core-security` rather than `forge-core::security.rs` — update the traceability matrix's `Module` column for these six rows when this crate is scaffolded (not done in this doc pass, since the exact file layout — `containment.rs` vs `sandbox.rs` split — is specced in FORGE-RUST-TUI-SPEC.md §1, not restated here).

**Phased delivery** (per SPEC-SECURITY-003 §4/§6, already Director-approved — do not re-plan this, execute it): Phase 0 (Python-only stopgaps) is **done** — PR #36 (`.cline`/`.cursor` added to `SENSITIVE_READ_PATHS`) and PR #37 (`SemanticCheck` migrated off the delimiter-wrapper onto `contain_untrusted_text()`) both merged 2026-07-01. Phase 1 (`forge-core-security` crate itself: `Tainted`/`Trusted`, `ContainmentResult`, `SandboxRoot`) is **not yet started** — this is the next real chunk, dispatchable per SPEC-SECURITY-003 §6's P1-A/P1-B/P1-C breakdown, which is already bounded and ready (do not re-derive a dispatch prompt for this — one already exists there).

**Verification:** SPEC-SECURITY-002 §6's 10-case adversarial table (encoding obfuscation, paraphrase, translation, homoglyph, payload-splitting, roleplay, leetspeak, indirect/tool-output injection, delimiter-forgery) re-run against the Rust crate, per SPEC-SECURITY-003 §5 — plus a `trybuild`-style **negative-compilation test** asserting that constructing a `PromptFragment` from a `Tainted<String>` directly is a compile error, not a runtime failure. Do not report this phase done without an actual failed-build artifact proving that assertion, per that spec's own evidence bar.

### 2.7 config.rs — ForgeConfig (H16 fix)

**Purpose:** closes FORGE_FEEDBACK.md's documented H16 gap — real config plumbing exists in Python (`ForgeConfig.load()`/env-var overrides) but zero CLI surface (`forge --help` has no `config` subcommand) ever calls `.save()`. This Rust port must ship the CLI surface, not just the struct.

**Ground truth**: `src/forge_sdk/config/__init__.py::ForgeConfig` (real, complete dataclass + `load()`).

**Implementation Contract:**

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForgeConfig {
    pub provider: String,           // default "deepseek" in Python — reconsider default for this project (project-laws L1 names zai/ollama-cloud as the approved lane; carrying Python's "deepseek" default forward unexamined would be a silent policy drift)
    pub model: String,
    pub api_key: String,
    pub base_url: String,
    pub temperature: f64,
    pub max_tokens: Option<u64>,
    pub max_steps: u32,             // default 50, matches AgentContext.max_steps default
    pub cwd: PathBuf,
    pub eval_limit: Option<u32>,
    pub eval_benchmark: String,
    pub trace_dir: PathBuf,
    pub audit_db: PathBuf,
    pub config_file: Option<PathBuf>,
}

impl ForgeConfig {
    /// Load from ~/.forge/config.json (or an explicit path), then apply env
    /// overrides. MUST preserve the Python source's own hard-won lesson
    /// (see its inline comment): FORGE_API_KEY is the ONLY generic API-key
    /// env override — do NOT map provider-specific keys (DEEPSEEK_API_KEY,
    /// OPENROUTER_API_KEY, etc.) to the same `api_key` field here, or
    /// whichever env var is read last silently clobbers the other (the
    /// exact bug the Python comment documents: "a stale OPENROUTER_API_KEY
    /// -> 401 against deepseek"). Provider-aware key resolution stays a
    /// separate, later step (resolve_api_key()-equivalent in forge-providers).
    pub fn load(config_file: Option<&Path>) -> Result<Self, SessionError> { /* ... */ }
    pub fn save(&self, path: &Path) -> Result<(), SessionError> { /* the method Python has but nothing ever calls — THIS gap is what H16 fixes */ }
}
```

CLI surface (already declared in FORGE-RUST-TUI-SPEC.md §9's `ConfigAction` enum — `Init | Show | Set { key, value }` — just needs real handlers wired to `ForgeConfig::load`/`save` in `forge-cli/src/commands/config.rs`; no new design needed here, the gap was purely "nobody wired the button").

**Verification:** unit test env-override precedence (file value present, env var present → env wins, matches Python); regression test confirming a provider-specific key env var (e.g. a hypothetical `OPENROUTER_API_KEY`) does NOT get mapped onto `.api_key` by this module (guards the exact clobbering bug the Python comment warns about); CLI integration test: `forge config init` creates the file, `forge config show` reads it back, `forge config set key value` persists.

### 2.8 router.rs — AutoRouter (NEW code — no Python precedent, do not imply one exists)

**⚠️ Unlike every other module in this section, there is no real Python file to port.** FORGE_FEEDBACK.md's own 2026-07-01 "no automatic free-model routing/fallback" entry documents this as a live, real, currently-unsolved gap in the shipped Python SDK — "None of this exists today — it's fully manual." Any spec/agent output that frames router.rs as a "port" is wrong; it's new design, grounded in real observed failure data.

**Ground truth for the failure modes this must handle** (all independently confirmed live during this project's own dispatch history, per FORGE_FEEDBACK.md): (a) HTTP 429 with a real, server-provided `retry_after_seconds` — a genuine bounded backoff, not an account block; (b) HTTP 404 from a free model, plausibly OpenRouter Zero-Data-Retention policy filtering (Director's diagnosis, not independently confirmed at the API level — flag it as such in code comments too); (c) both failure modes are currently indistinguishable to a caller without manual iteration through a model list.

**Implementation Contract:**

```rust
pub struct AutoRouter {
    candidates: Vec<String>,        // ordered model-id fallback list for a request
    dead_this_session: HashSet<String>,  // models that 404'd — don't retry them this run
}

#[derive(Debug, Clone)]
pub enum RouteFailure {
    RateLimited { retry_after_seconds: u64 },   // honor this exact backoff once, per FORGE_FEEDBACK.md (b)
    NotFound,                                    // drop from candidate list for the session, try next
    Other(ModelError),
}

impl AutoRouter {
    pub async fn dispatch(&mut self, prompt: &str, tools: &[ToolSpec]) -> Result<(ModelResponse, String /* model actually used */), FailureReason> {
        // (a) on RateLimited: sleep retry_after_seconds once, retry same model once, then fall through
        // (b) on NotFound: mark dead_this_session, try next candidate immediately, no retry
        // (c) ALWAYS surface which model actually served the response (FORGE_FEEDBACK.md gap (d):
        //     "surfaces which model actually ran... isn't guessing") — this is a real, named
        //     requirement, not an implementation detail to skip
    }
}
```

**Language-cost-aware extension (see REFACTORED-PLAN-COMPLETE.md Part 10, added same hardening pass)**: `AutoRouter`'s candidate ordering should additionally consult `forge-catalog`'s models.dev data + this project's own audit-log-derived tokens-per-`(model, detected_language)` history, preferring the empirically cheapest capable model for non-English-heavy requests — not just the first model in a static list. Same struct, one more input signal; not a separate module.

**Verification:** unit test each `RouteFailure` variant is handled per (a)/(b)/(c) above; integration test against a mock provider that returns 429-with-retry-after then succeeds; integration test confirming a `NotFound` model is never retried twice in one session; unit test that the final result always carries the actually-used model string, never leaves it implicit.

---

### 2.37 Implementation Sequence (for parallel agents)

```yaml
phase_0_types:
  - event.rs (requires: nothing)
  - result.rs (requires: nothing)
  - context.rs (requires: nothing)
  - port.rs (requires: nothing)
  - step.rs (requires: nothing)

phase_1_traits:
  - agent.rs (requires: event, result, context, port)
  - renderer.rs (requires: event)
  - permission.rs (requires: event, result)

phase_2_subsystems:
  - verifier.rs (requires: event, result)
  - session.rs (requires: event, result)
  - doctor.rs (requires: nothing)
  - guard.rs (requires: context)
  - security.rs (requires: nothing)
  - tracer.rs (requires: event)
  - audit.rs (requires: event, tracer)

phase_3_incremental:
  - config.rs (requires: nothing — NEW file)
  - router.rs (requires: port — NEW file)
  - semantic.rs (requires: nothing — NEW file)
  - okf.rs (requires: nothing — NEW file)
  - experience.rs (requires: event, semantic — NEW file)

phase_4_lib_rs:
  - lib.rs (requires: ALL — re-exports all public API)
```

---

## 3. SOC 2 Type II Control Evidence

| Control ID | Trust Criterion | forge Module | Evidence | Collection Method |
|-----------|----------------|-------------|----------|-------------------|
| SOC-SEC-01 | Access Control | permission.rs | Anti-slop tests pass | CI gate |
| SOC-SEC-02 | Logical Security | security.rs | Path traversal test | CI gate |
| SOC-AVAIL-01 | Availability | session.rs | Checkpoint save/restore test | Integration test |
| SOC-AVAIL-02 | Availability | guard.rs | LoopGuard timeout test | Unit test |
| SOC-PI-01 | Processing Integrity | verifier.rs | 5-gate pipeline test | Integration test |
| SOC-PI-02 | Processing Integrity | audit.rs | Hash chain test | Unit test |
| SOC-CONF-01 | Confidentiality | port.rs | No outbound telemetry test | Network test |
| SOC-CONF-02 | Confidentiality | config.rs | Local-only config test | Unit test |
| SOC-PRIV-01 | Privacy | session.rs | User-delete checkpoints test | CLI test |
| SOC-PRIV-02 | Privacy | config.rs | Configurable retention test | Unit test |

---

## 4. AI Context Packet

<!-- AI_CONTEXT_PACKET -->
```yaml
task: Implement forge-core Rust modules
relevant_runtime_path: forge-experience/forge-core/src/
relevant_module_contracts:
  - forge-core: zero-heavy-dep library
  - forge-cli: consumes forge-core events
  - forge-tui: separate binary, crossterm+ratatui
  - forge-gemini: google-genai-rs wrapper
allowed_change_shapes:
  - Add new variants to AgentEvent enum (with Correlation)
  - Add new FailureReason variants (with is_recoverable + causal_sentence)
  - Add new PermissionStrategy implementations
  - Add new VerificationGate implementations
forbidden_change_shapes:
  - Adding heavyweight dependencies to forge-core
  - Removing Correlation from events
  - Using string-parsed command execution (Command::new().arg().output() only)
  - Using text[..n] byte slicing on strings
  - Removing anti-slop from PermissionGate::Yolo
  - Skipping FailureReason on break paths
impacted_tests: forge-harness/tests/
impacted_docs:
  - docs/FORGE-RUST-TUI-SPEC.md
  - docs/CHANGE_ORDER_MAP.md
  - docs/TOPOLOGICAL_MAP.md
  - docs/IMPLEMENTATION_PLAYBOOK.md
uncertainty:
  - forge-core lib.rs re-export organization
  - Feature-gating for semantic/okf/experience types
  - Router auto-fallback ordering policy
escalation_required:
  - Adding new external dependency to forge-core
  - Modifying AgentEvent enum (backward-compat concern)
  - Changing FailureReason::is_recoverable semantics
```
<!-- END_AI_CONTEXT_PACKET -->

---

*This document is the implementation-ready truth source for the forge Rust port v1.0.0.*
*Every REQUIREMENT ID connects to a TEST ID in forge-harness/tests/.*
*Every FAILURE MODE has a MITIGATION.*
*Every CLAIM has EVIDENCE.*

