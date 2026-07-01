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
| REQ-CTX-001 | context.rs | AgentContext has max_steps, max_tokens, max_cost | Unit test | SIL2 |
| REQ-PORT-001 | port.rs | ModelPort trait with generate/generate_with_tools/count_tokens | Provider test | SIL2 |
| REQ-PORT-002 | port.rs | ModelError covers 6 variants | Match exhaustiveness | SIL2 |
| REQ-AGENT-001 | agent.rs | Agent trait with run/run_with_events | Smoke test | SIL3 |
| REQ-PERM-001 | permission.rs | PermissionGate in 3 modes (interactive/yolo/plan) | Unit all 3 | SIL3 |
| REQ-PERM-002 | permission.rs | Anti-slop gates active in ALL modes | Unit test | SIL3 |
| REQ-PERM-003 | permission.rs | ActionClassification covers 10 categories | Match exhaustiveness | SIL2 |
| REQ-VER-001 | verifier.rs | 5-gate pipeline (Syntax→Lint→Tests→Property→Formal) | Integration test | SIL3 |
| REQ-VER-002 | verifier.rs | Fail-fast on gate failure | Unit test | SIL2 |
| REQ-VER-003 | verifier.rs | VerificationEvidence carries stable_id | Unit test | SIL2 |
| REQ-SESS-001 | session.rs | Session save/load/list/delete | Integration test | SIL2 |
| REQ-SESS-002 | session.rs | FileSessionStore at ~/.forge/checkpoints/ | Unit test | SIL2 |
| REQ-DOC-001 | doctor.rs | L0-L5 DoctorEngine with escalation ladder | Integration test | SIL2 |
| REQ-DOC-002 | doctor.rs | DoctorStatus covers 4 variants | Match exhaustiveness | SIL1 |
| REQ-GRD-001 | guard.rs | LoopGuard with 5 break paths | Unit all 5 | SIL3 |
| REQ-GRD-002 | guard.rs | Convergence failure after N nudges | Unit test | SIL2 |
| REQ-SEC-001 | security.rs | Command::new().arg().output() NOT string parsing | Static analysis | SIL3 |
| REQ-SEC-002 | security.rs | Path traversal blocked | Unit test | SIL3 |
| REQ-SEC-003 | security.rs | NO_COLOR respected | Unit test | SIL1 |
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

