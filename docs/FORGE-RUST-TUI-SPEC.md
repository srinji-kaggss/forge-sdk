# Forge Rust Port — TUI & Full Implementation Specification

**Version:** 1.0.0 (Rust)
**Python Baseline:** forge-sdk v0.7.0
**Rust SDK Foundation:** google-genai-rs v0.3.0, keel-core, MCP rust-sdk v1.7.0
**Palette (spine-based TUI):** Slate `#2c2c2c` / Cream `#f5f0e0` / Emerald `#50c878` / Amber `#ffbf00` / Ruby `#e0115f`
**Status:** ✅ FINALIZED — ready for Phase 1-6 execution

---

## Table of Contents

1. [Crate Architecture & File Tree](#1-crate-architecture--file-tree)
2. [forge-core: Foundational Types & Traits](#2-forge-core-foundational-types--traits)
3. [forge-core: Event Taxonomy (13 discriminators)](#3-forge-core-event-taxonomy-13-discriminators)
4. [forge-core: Permission Gate](#4-forge-core-permission-gate)
5. [forge-core: Five-Gate Verification Pipeline](#5-forge-core-five-gate-verification-pipeline)
6. [forge-core: FailureReason Enum & Honest Failures](#6-forge-core-failurereason-enum--honest-failures)
7. [forge-core: Session & Checkpointing](#7-forge-core-session--checkpointing)
8. [forge-core: Doctor (L0-L5 Escalation Ladder)](#8-forge-core-doctor-l0-l5-escalation-ladder)
9. [forge-cli: CLI Surface (clap derive)](#9-forge-cli-cli-surface-clap-derive)
10. [forge-tui: Spine-Based Terminal UI](#10-forge-tui-spine-based-terminal-ui)
11. [Anti-Duplication Boundary vs lgwks_ui](#11-anti-duplication-boundary-vs-lgwks_ui)
12. [Hardening Checklist from 7 Packs](#12-hardening-checklist-from-7-packs)
13. [Implementation Phases 1-6](#13-implementation-phases-1-6)
14. [Key Risks & Mitigations](#14-key-risks--mitigations)
15. [Migration Map: Python → Rust](#15-migration-map-python--rust)
16. [CI/CD Integration](#16-cicd-integration)

---


## 1. Crate Architecture & File Tree

### Workspace Layout

```
forge/
├── Cargo.workspace.toml          # Workspace root
├── forge-core/                    # Zero-dependency core types & traits
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs                 # Re-exports all public API
│       ├── event.rs               # AgentEvent enum (13 discriminators)
│       ├── result.rs              # AgentResult, FailureReason
│       ├── context.rs             # AgentContext (execution contract)
│       ├── step.rs                # AgentStep
│       ├── port.rs                # ModelPort trait
│       ├── agent.rs               # Agent trait
│       ├── permission.rs          # PermissionGate, PermissionStrategy, ActionClassification
│       ├── verifier.rs            # VerifierPipeline, VerificationEvidence, Five gates
│       ├── session.rs             # Session, SessionStore trait, checkpointing
│       ├── doctor.rs              # DoctorCheck, DoctorReport, EscalationRecord
│       ├── renderer.rs            # EventRenderer trait (ADR-2)
│       ├── tracer.rs              # Span, SpanKind, Tracer (observability)
│       ├── audit.rs               # AuditEntry, AuditLog, EventSink trait
│       └── security.rs            # Path safety, command safety, credential store detection
│
├── forge-gemini/                  # google-genai-rs -> ModelPort impl
│   ├── Cargo.toml                 # dep: google-genai-rs, forge-core
│   └── src/
│       └── lib.rs
│
├── forge-ollama/                  # reqwest REST -> ModelPort impl
│   ├── Cargo.toml                 # dep: reqwest, forge-core
│   └── src/
│       └── lib.rs
│
├── forge-openai/                  # reqwest REST -> ModelPort impl
│   ├── Cargo.toml                 # dep: reqwest, forge-core
│   └── src/
│       └── lib.rs
│
├── forge-cli/                     # clap binary: run, doctor, session, eval, audit
│   ├── Cargo.toml                 # dep: forge-core, clap, tokio, tracing, syntect
│   └── src/
│       ├── main.rs                # Entry point
│       ├── commands/
│       │   ├── run.rs             # forge run
│       │   ├── doctor.rs          # forge doctor
│       │   ├── session.rs         # forge session (list/checkpoint/resume/fork)
│       │   ├── eval.rs            # forge eval
│       │   └── audit.rs           # forge audit
│       └── render/
│           ├── text.rs            # TextRenderer (streaming ANSI, terminal)
│           ├── ndjson.rs          # NDJSONRenderer (machine pipe)
│           └── mod.rs
│
├── forge-tui/                     # Spine-based terminal UI (separate binary)
│   ├── Cargo.toml                 # dep: forge-core, forge-cli, crossterm, ratatui
│   └── src/
│       ├── main.rs                # Entry: forge-tui
│       ├── app.rs                 # App state machine (RUNNING/BROWSING/REVIEWING)
│       ├── spine.rs               # Spine renderer (┃ SPINE glyph + DOWN/OUT/CONVERGE)
│       ├── palette.rs             # Palette (Slate/Cream/Emerald/Amber/Ruby)
│       ├── anim.rs                # Minimal animation (frame-based, no dep)
│       ├── inspector.rs           # Drill-down inspector (per-event detail view)
│       ├── config_screen.rs       # TUI-based config editor (for H16 gap)
│       └── mod.rs
│
├── forge-mcp/                     # MCP rust-sdk integration
│   ├── Cargo.toml                 # dep: mcp-rust-sdk, forge-core
│   └── src/
│       └── lib.rs
│
├── forge-harness/                 # Eval harness (Python harness port)
│   ├── Cargo.toml                 # dep: forge-core, serde_yaml
│   └── src/
│       └── lib.rs
│
└── docs/
    ├── FORGE-RUST-TUI-SPEC.md     # This file
    ├── FORGE-RUST-PORT-GAP.md     # Pre-existing gap analysis
    ├── CHANGELOG.md               # Release notes
    └── PLAYBOOK.md                # Operations playbook
```

### Cargo Workspace Dependency Graph

```
forge-core ─────────────────────────────────────► (no external deps beyond async-trait + thiserror + serde + tokio)
  │
  ├─ forge-gemini ──── dep: forge-core, google-genai-rs
  ├─ forge-ollama ──── dep: forge-core, reqwest
  ├─ forge-openai ──── dep: forge-core, reqwest
  ├─ forge-cli ─────── dep: forge-core, forge-tui (optional), clap, tokio, tracing, syntect
  ├─ forge-tui ─────── dep: forge-core, crossterm, ratatui
  ├─ forge-mcp ─────── dep: forge-core, mcp-rust-sdk
  └─ forge-harness ── dep: forge-core, serde_yaml
```

### Core Dependencies (forge-core)

```toml
[dependencies]
async-trait = "0.1"
thiserror = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["rt", "macros"] }
uuid = { version = "1", features = ["v4", "serde"] }
```

**forge-core MUST remain minimal.** No reqwest, no chrono, no google-genai-rs. Those are provider-crate concerns.


## 2. forge-core: Foundational Types & Traits

### 2.1 AgentResult (the contract)

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentResult {
    pub success: bool,
    pub output: String,
    pub steps: Vec<AgentStep>,
    pub total_tokens: u64,
    pub total_cost: f64,
    pub trace_id: String,
    pub run_id: String,
    pub model: String,
    pub provider: String,
    pub artifacts: HashMap<String, serde_json::Value>,
    pub verification: Vec<VerificationEvidence>,
    pub edits_made: Vec<String>,
    pub named_targets_missing: Vec<String>,
    pub failure_reason: Option<FailureReason>,
    /// H15: Change manifest for CI/CD
    pub change_manifest: Option<ChangeManifest>,
}

impl AgentResult {
    /// char-count aware summary (fixes Python .len() vs Rust .chars().count() trap)
    pub fn char_count_aware_summary(&self) -> String {
        let status = if self.success { "SUCCESS" } else { "FAILED" };
        format!("{} | {} steps | {} tokens | verification: {} | {}...",
            status, self.steps.len(), self.total_tokens,
            self.verification_summary(),
            &self.output.chars().take(80).collect::<String>())
    }

    pub fn verification_summary(&self) -> String {
        let passed = self.verification.iter()
            .filter(|v| v.status == VerificationStatus::Passed).count();
        format!("{}/{}", passed, self.verification.len())
    }
}

/// H15: Change manifest for CI/CD integration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeManifest {
    pub change_id: String,
    pub author_or_agent: String,
    pub change_type: ChangeType,
    pub intent: String,
    pub non_goals: Vec<String>,
    pub behavior_delta: String,
    pub blast_radius: BlastRadius,
    pub invariants_touched: Vec<String>,
    pub tests_added_or_changed: Vec<String>,
    pub observability_delta: String,
    pub rollback: RollbackPlan,
    pub risk_level: RiskLevel,
    pub residual_unknowns: Vec<String>,
    pub source_evidence: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ChangeType {
    Bugfix, Feature, MechanicalRefactor, DependencyUpdate,
    Migration, Performance, Security, Documentation,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlastRadius {
    pub files: Vec<String>,
    pub symbols: Vec<String>,
    pub schemas: Vec<String>,
    pub configs: Vec<String>,
    pub runtime_paths: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RiskLevel { Low, Medium, High, Critical }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RollbackPlan {
    pub rollback_command: String,
    pub data_migration_required: bool,
    pub estimated_rollback_time_seconds: u32,
}
```

### 2.2 ModelPort Trait

```rust
#[async_trait]
pub trait ModelPort: Send + Sync {
    async fn generate(&self, prompt: &str) -> Result<String, ModelError>;
    async fn generate_with_tools(
        &self, prompt: &str, tools: &[ToolSpec],
    ) -> Result<ModelResponse, ModelError>;
    async fn count_tokens(&self, text: &str) -> Result<u64, ModelError>;
    fn model_name(&self) -> &str;
    fn provider_name(&self) -> &str;
}

#[derive(Debug, thiserror::Error)]
pub enum ModelError {
    #[error("Authentication failed: {0}")]
    Auth(String),
    #[error("Rate limited: {0}")]
    RateLimit(String),
    #[error("Model unavailable: {0}")]
    Unavailable(String),
    #[error("Invalid request: {0}")]
    InvalidRequest(String),
    #[error("Timeout after {0}s")]
    Timeout(u64),
    #[error("Provider error: {0}")]
    Provider(String),
}

#[derive(Debug, Clone)]
pub struct ModelResponse {
    pub text: String,
    pub tool_calls: Vec<ToolCall>,
}

#[derive(Debug, Clone)]
pub struct ToolCall {
    pub name: String,
    pub args: HashMap<String, serde_json::Value>,
    pub id: String,
}
```

### 2.3 Agent Trait + EventRenderer

```rust
#[async_trait]
pub trait Agent: Send + Sync {
    async fn run(&self, context: AgentContext) -> AgentResult;
    async fn run_with_events<F>(&self, context: AgentContext, on_event: F) -> AgentResult
    where F: Fn(AgentEvent) + Send + Sync + 'static;
}

/// ADR-2: Renderers live in the CLI layer. SDK never imports ANSI codes.
pub trait EventRenderer: Send {
    fn on_event(&mut self, event: &AgentEvent);
    fn on_end(&mut self, exit_code: i32);
}
```

### 2.4 ToolSpec / ToolResult / ToolHandler (with shell fix)

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub input_schema: serde_json::Value,
    pub stable_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub success: bool,
    pub output: String,
    pub error: String,
    pub exit_code: Option<i32>,
    pub metadata: HashMap<String, serde_json::Value>,
}

impl ToolResult {
    /// FORGE_FEEDBACK.md fix: always capture stdout+stderr+exit_code independently
    /// Never use string-parsed command strings. Use Command::new().arg().output().
    pub fn as_message(&self) -> String {
        if self.success { return self.output.clone(); }
        let mut parts = vec![format!("Tool failed (exit {}): {}", 
self.exit_code.unwrap_or(-1), self.error)];
        if !self.output.is_empty() {
            parts.push(format!("stdout: {}", self.output));
        }
        parts.join("\n")
    }
}

#[async_trait]
pub trait ToolHandler: Send + Sync {
    async fn call(&self, args: HashMap<String, serde_json::Value>) -> ToolResult;
}
```

**CRITICAL**: The ShellTool implementation MUST use `tokio::process::Command::new(cmd).args(cmd_args).output()`, never string parsing. This fixes the v0.7.0 shell-tool output-capture bug documented in FORGE_FEEDBACK.md.


## 3. forge-core: Event Taxonomy (13 discriminators)

### 3.1 AgentEvent Enum

```rust
/// ADR-1: The event stream is the architectural hinge.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum AgentEvent {
    // ── Lifecycle ──
    RunStart(RunStartEvent),
    RunEnd(RunEndEvent),
    RunError(RunErrorEvent),
    // ── Cognitive ──
    Think(ThinkEvent),
    // ── Action/Observation ──
    Act(ActionEvent),
    Observe(ObservationEvent),
    // ── Verification ──
    Verify(VerificationEvent),
    // ── Mutation ──
    FileEdit(FileEditEvent),
    // ── Accounting ──
    TokenUsage(TokenUsageEvent),
    // ── State ──
    StateUpdate(StateUpdateEvent),
    Decide(DecisionEvent),
    // ── Convergence ──
    Converge(ConvergenceEvent),
    // ── Permission ──
    PermissionGate(PermissionGateEvent),
}

// ── Correlation keys on EVERY event (H14) ──
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Correlation {
    pub trace_id: String,
    pub run_id: String,
    pub model: String,
    pub provider: String,
    pub config_version: String,
}
```

### 3.2 Event Payloads

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunStartEvent {
    pub correlation: Correlation,
    pub prompt: String,
    pub max_steps: u32,
    pub permission_mode: PermissionMode,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunEndEvent {
    pub correlation: Correlation,
    pub success: bool,
    pub total_steps: u32,
    pub total_tokens: u64,
    pub total_cost: f64,
    pub total_duration_ms: i64,
    pub edits_made: Vec<String>,
    pub failure_reason: Option<FailureReason>,
    pub change_manifest: Option<ChangeManifest>,  // H15
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunErrorEvent {
    pub correlation: Correlation,
    pub error_type: String,
    pub message: String,
    pub failure_reason: FailureReason,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThinkEvent {
    pub correlation: Correlation,
    pub content: String,
    pub goal: Option<String>,        // H12
    pub hypothesis: Option<String>,  // H12
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionEvent {
    pub correlation: Correlation,
    pub tool_name: String,
    pub tool_args: HashMap<String, serde_json::Value>,
    pub risk: Option<ActionRisk>,    // H12
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionRisk {
    pub blast_radius: Vec<String>,
    pub rollback_possible: bool,
    pub estimated_impact: RiskLevel,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ObservationEvent {
    pub correlation: Correlation,
    pub tool_name: String,
    pub result: ToolResult,
    pub uncertainty: Vec<UncertaintyClaim>,  // H12
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UncertaintyClaim {
    pub claim: String,
    pub missing_evidence: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationEvent {
    pub correlation: Correlation,
    pub gate_name: String,
    pub status: VerificationStatus,
    pub detail: String,
    pub evidence: Option<VerificationEvidence>,
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEditEvent {
    pub correlation: Correlation,
    pub file_path: String,
    pub diff: String,
    pub action: String,  // create / modify / delete
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenUsageEvent {
    pub correlation: Correlation,
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
    pub total_tokens: u64,
    pub cost: f64,
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateUpdateEvent {
    pub correlation: Correlation,
    pub key: String,
    pub old_value: Option<serde_json::Value>,
    pub new_value: serde_json::Value,
    pub reason: String,
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionEvent {
    pub correlation: Correlation,
    pub question: String,
    pub alternatives: Vec<String>,
    pub chosen: String,
    pub rationale: String,
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConvergenceEvent {
    pub correlation: Correlation,
    pub nudge_count: u32,
    pub converged: bool,
    pub final_agreement: String,
    pub step: u32,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionGateEvent {
    pub correlation: Correlation,
    pub action_label: String,
    pub classification: ActionClassification,
    pub permitted: bool,
    pub strategy: String,
    pub detail: String,
    pub step: u32,
    pub timestamp_ms: i64,
}
```

### 3.3 Event Surface Summary

| # | Discriminant | Purpose | Surface |
|---|-------------|---------|---------|
| 1 | RunStart | Run lifecycle begin | Operational |
| 2 | RunEnd | Run lifecycle end | Operational |
| 3 | RunError | Unrecoverable error | Operational |
| 4 | Think | Agent reasoning text | Cognitive |
| 5 | Act | Tool dispatch | Operational |
| 6 | Observe | Tool result | Operational |
| 7 | Verify | Verification gate result | Contextual |
| 8 | FileEdit | File mutation with diff | Contextual |
| 9 | TokenUsage | Token/cost accounting | Operational |
| 10 | StateUpdate | Plan/memory changes | Cognitive |
| 11 | Decide | Decision rationale | Cognitive |
| 12 | Converge | Multi-nudge convergence | Cognitive |
| 13 | PermissionGate | Permission evaluation | Contextual |


## 4. forge-core: Permission Gate

### 4.1 ActionClassification

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ActionClassification {
    Safe, LocalWrite, Destructive, NetworkOut,
    NetworkIn, Exec, GitHistory, Auth, Config, Install,
}
```

### 4.2 PermissionStrategy Trait

```rust
#[async_trait]
pub trait PermissionStrategy: Send + Sync + std::fmt::Debug {
    fn name(&self) -> &str;
    fn classification(&self) -> ActionClassification;
    async fn check(&self, ctx: &PermissionContext) -> PermissionVerdict;
}

#[derive(Debug, Clone)]
pub struct PermissionContext {
    pub action_label: String,
    pub classification: ActionClassification,
    pub tool_name: String,
    pub tool_args: HashMap<String, serde_json::Value>,
    pub cwd: PathBuf,
    pub sandbox_dir: Option<PathBuf>,
    pub files_read_in_session: Vec<PathBuf>,
    pub permission_mode: PermissionMode,
}

#[derive(Debug, Clone)]
pub enum PermissionVerdict {
    Allowed { reason: String },
    Denied { reason: String },
    NeedsApproval { prompt: String },
}
```

### 4.3 PermissionGate (state machine)

```rust
pub struct PermissionGate {
    mode: PermissionMode,
    anti_slop_strategies: Vec<Box<dyn PermissionStrategy>>,  // H13
    history: Vec<PermissionGateEvent>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum PermissionMode {
    Interactive,  // Prompt for non-safe actions
    Yolo,         // Auto-allow (anti-slop still active)
    Plan,         // Batch-approve upfront
}

impl PermissionGate {
    pub fn new(mode: PermissionMode) -> Self {
        Self {
            mode,
            anti_slop_strategies: Self::default_anti_slop(),
            history: Vec::new(),
        }
    }

    /// H13: Anti-slop hard gates — active in ALL modes
    fn default_anti_slop() -> Vec<Box<dyn PermissionStrategy>> {
        vec![
            Box::new(NoEditWithoutReadEvidence),
            Box::new(MustAddTestForFix),
            Box::new(NoTestDeletionWithoutReplacement),
            Box::new(ProtectedPaths),
        ]
    }

    pub async fn evaluate(&mut self, ctx: &PermissionContext) -> PermissionVerdict {
        // 1. Anti-slop runs first, always
        for s in &self.anti_slop_strategies {
            if let PermissionVerdict::Denied { .. } = s.check(ctx).await {
                return s.check(ctx).await;
            }
        }
        // 2. Mode-specific
        match self.mode {
            PermissionMode::Interactive => {
                if ctx.classification == ActionClassification::Safe {
                    PermissionVerdict::Allowed { reason: "safe".into() }
                } else {
                    PermissionVerdict::NeedsApproval { prompt: format!("Allow {}?", ctx.action_label) }
                }
            }
            PermissionMode::Yolo => PermissionVerdict::Allowed { reason: "yolo".into() },
            PermissionMode::Plan => PermissionVerdict::NeedsApproval { prompt: "batch".into() },
        }
    }
}
```


## 5. forge-core: Five-Gate Verification Pipeline

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GateKind {
    SyntaxCheck,   // L0: compiles
    LintAnalysis,  // L1: no anti-patterns
    TestExecution, // L2: tests pass
    PropertyCheck, // L3: proptest invariants
    FormalBound,   // L4: Lean formal bound
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationEvidence {
    pub gate: GateKind,
    pub stable_id: String,       // ai_semantic_rag_pack
    pub status: VerificationStatus,
    pub detail: String,
    pub output: String,
    pub duration_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum VerificationStatus { Passed, Failed, Skipped, Error }

#[async_trait]
pub trait VerificationGate: Send + Sync {
    fn kind(&self) -> GateKind;
    async fn verify(&self, ctx: &VerificationContext) -> VerificationEvidence;
}

pub struct VerifierPipeline {
    gates: Vec<Box<dyn VerificationGate>>,
}

impl VerifierPipeline {
    pub fn new() -> Self { Self { gates: Vec::new() } }
    pub fn add_gate<G: VerificationGate + 'static>(&mut self, gate: G) {
        self.gates.push(Box::new(gate));
    }
    pub fn with_default_gates() -> Self {
        let mut p = Self::new();
        p.add_gate(SyntaxCheckGate);     // L0
        p.add_gate(LintAnalysisGate);    // L1
        p.add_gate(TestExecutionGate);   // L2
        p.add_gate(PropertyCheckGate);   // L3
        p.add_gate(FormalBoundGate);     // L4
        p
    }
    pub async fn run_all(&self, ctx: &VerificationContext) -> Vec<VerificationEvidence> {
        let mut r = Vec::new();
        for g in &self.gates {
            let e = g.verify(ctx).await;
            r.push(e.clone());
            if e.status == VerificationStatus::Failed { break; }
        }
        r
    }
}
```

## 6. forge-core: FailureReason Enum & Honest Failures

```rust
/// ADR-3: Every break path sets this before returning.
/// Every variant is a typed failure, never a string.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum FailureReason {
    /// Model call failed (auth, rate limit, timeout)
    ModelError(String),
    /// Usage limits exceeded (tokens or cost)
    UsageLimitExceeded,
    /// Model not converging after repeated nudges
    ConvergenceFailure { nudges: u32, detail: String },
    /// Maximum step count reached without completion
    MaxStepsReached,
    /// A verification gate rejected the output
    VerificationFailed { gate: String, detail: String },
    /// Permission was denied mid-session
    PermissionDenied { action: String, reason: String },
    /// Authentication failure (distinct from model error)
    AuthenticationFailure { provider: String, detail: String },
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

### 6.1 LoopGuard (5 break paths)

```rust
pub struct LoopGuard {
    max_steps: u32,
    max_tokens: Option<u64>,
    max_cost: Option<f64>,
    convergence_threshold: u32,
    step_count: u32,
    total_tokens: u64,
    total_cost: f64,
    convergence_nudges: u32,
}

impl LoopGuard {
    pub fn new(ctx: &AgentContext) -> Self { /* ... */ }
    pub fn check(&mut self, step_tokens: u64, step_cost: f64) -> Result<(), FailureReason> {
        self.step_count += 1;
        self.total_tokens += step_tokens;
        self.total_cost += step_cost;
        if self.step_count > self.max_steps {
            return Err(FailureReason::MaxStepsReached);
        }
        if let Some(mt) = self.max_tokens { if self.total_tokens > mt { return Err(FailureReason::UsageLimitExceeded); } }
        if let Some(mc) = self.max_cost { if self.total_cost > mc { return Err(FailureReason::UsageLimitExceeded); } }
        Ok(())
    }
    pub fn nudge(&mut self) -> Result<(), FailureReason> {
        self.convergence_nudges += 1;
        if self.convergence_nudges > self.convergence_threshold {
            return Err(FailureReason::ConvergenceFailure { nudges: self.convergence_nudges, detail: "Model not converging".into() });
        }
        Ok(())
    }
}
```


## 7. forge-core: Session & Checkpointing

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Session {
    pub session_id: String,
    pub trace_id: String,
    pub run_id: String,
    pub created_at: i64,
    pub updated_at: i64,
    pub context: AgentContext,
    pub events: Vec<AgentEvent>,
    pub current_step: u32,
    pub status: SessionStatus,
    pub total_tokens: u64,
    pub total_cost: f64,
    pub checkpoint_path: Option<PathBuf>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SessionStatus { Active, Paused, Completed, Failed(FailureReason) }

#[async_trait]
pub trait SessionStore: Send + Sync {
    async fn save(&self, session: &Session) -> Result<String, SessionError>;
    async fn load(&self, session_id: &str) -> Result<Session, SessionError>;
    async fn list(&self) -> Result<Vec<SessionSummary>, SessionError>;
    async fn delete(&self, session_id: &str) -> Result<(), SessionError>;
}

#[derive(Debug, thiserror::Error)]
pub enum SessionError {
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("Storage: {0}")]
    Storage(String),
    #[error("Serialization: {0}")]
    Serialization(String),
}

/// Filesystem-backed store at ~/.forge/checkpoints/
pub struct FileSessionStore {
    base_dir: PathBuf,
}
```

## 8. forge-core: Doctor (L0-L5 Escalation Ladder)

```rust
#[async_trait]
pub trait DoctorCheck: Send + Sync {
    fn level(&self) -> u8;
    fn name(&self) -> &str;
    async fn run(&self) -> DoctorResult;
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DoctorResult {
    pub check_name: String,
    pub level: u8,
    pub status: DoctorStatus,
    pub message: String,
    pub suggestion: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum DoctorStatus { Pass, Fail, Warn, Skip }

pub struct DoctorEngine {
    checks: Vec<Box<dyn DoctorCheck>>,
}

impl DoctorEngine {
    pub fn new() -> Self { Self { checks: vec![
        Box::new(RuntimeCheck), Box::new(ConfigCheck),
        Box::new(ProviderAuthCheck), Box::new(ConnectivityCheck),
        Box::new(WriteTestCheck), Box::new(ModelSmokeCheck),
    ]}}
    pub async fn run_all(&self) -> DoctorReport {
        let mut r = Vec::new();
        for c in &self.checks {
            let result = c.run().await;
            r.push(result.clone());
            if result.status == DoctorStatus::Fail { break; }
        }
        DoctorReport { checks: r }
    }
}

/// Escalation ladder:
/// L0 = Runtime (rustc, cargo, OS)
/// L1 = Config (file exists, valid)
/// L2 = Provider Auth (API key, ping)
/// L3 = Connectivity (endpoint reachable)
/// L4 = Write Test (dir writable)
/// L5 = Full Model (short invocation)
```


## 9. forge-cli: CLI Surface (clap derive)

```rust
use clap::{Parser, Subcommand};

/// Forge — human-supervised AI code agent
#[derive(Parser)]
#[command(name = "forge", version, about)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    #[arg(global = true, short = 'o', long = "output-format", default_value = "text")]
    output_format: OutputFormat,
    #[arg(global = true, long = "json")]
    json: bool,
    #[arg(global = true, long = "permission-mode", default_value = "interactive")]
    permission_mode: PermissionMode,
    #[arg(global = true, long = "verify-command")]
    verify_command: Option<String>,
    #[arg(global = true, long = "sandbox")]
    sandbox: Option<PathBuf>,
    #[arg(global = true, short = 's', long = "max-steps", default_value = "25")]
    max_steps: u32,
    #[arg(global = true, long = "max-cost")]
    max_cost: Option<f64>,
    #[arg(global = true, long = "max-tokens")]
    max_tokens: Option<u64>,
    #[arg(global = true, long = "resume")]
    resume: Option<String>,
    #[arg(global = true, short = 'p', long = "provider", default_value = "gemini")]
    provider: String,
    #[arg(global = true, short = 'm', long = "model")]
    model: Option<String>,
    #[arg(global = true, short = 'e', long = "env")]
    env: Vec<String>,
    #[arg(global = true, long = "print")]
    print: bool,
}

#[derive(Subcommand)]
enum Commands {
    Run { prompt: Option<String>, #[arg(long)] stdin: bool },
    Doctor { #[arg(long)] json: bool, #[arg(long)] level: Option<u8> },
    Session { #[command(subcommand)] action: SessionAction },
    Eval { spec: Option<PathBuf>, #[arg(long)] list: bool },
    Audit { trace_id: Option<String>, #[arg(long)] list: bool, #[arg(long)] json: bool },
    /// New: Config management (H16 fix)
    Config { #[command(subcommand)] action: ConfigAction },
}

enum SessionAction { List, Show { id: String }, Delete { id: String } }
enum ConfigAction { Init, Show, Set { key: String, value: String } }
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic failure |
| 2 | Model/auth error |
| 3 | Verification failure |
| 4 | Permission denied |
| 5 | Config error |
| 6 | Doctor failure |
| 7 | Timeout |


## 10. forge-tui: Spine-Based Terminal UI

### 10.1 Design Philosophy

The forge-tui is **not a chat stream**. It is a **spine-based debugger** that shows the agent's thinking as a structured, browsable tree.

**Key principles:**
1. **Event stream is the source of truth** — TUI consumes the same AgentEvent stream as TextRenderer.
2. **Spine layout** — a fixed left SPINE (┃) anchors the view; content sprawls DOWN+OUT.
3. **Not chat** — no text box, no message bubble, no chat history. This is an inspectable agent trace.
4. **Zero new deps for non-TUI** — forge-tui is a separate binary. forge-cli runs without crossterm/ratatui.
5. **Degrades gracefully** — when piped, falls back to text output.
6. **NO_COLOR support** — respects NO_COLOR / CLICOLOR / CLICOLOR_FORCE env vars.

### 10.2 Screen Layout

```
┌─ Forge ───────────────────────────────────────────────────────────┐
│ ◆ RUNNING    [gemini:gemini-2.5-pro]                  12/25 steps  │
│                                                                    │
│ ┃ ◆ Think: "Looking at the user's request..."                      │
│ ┃   The user wants to add a new feature to the parser.              │
│ ┃ ▸ ReadFile path="src/parser.rs"                                  │
│ ┃   ┃ File content (245 lines) retrieved                            │
│ ┃   ┃ Exit code: 0                                                  │
│ ┃   ┗━ Reads complete. Understanding structure.                     │
│ ┃ ▸ RunTest cargo test --lib                                        │
│ ┃   ┃ PASS: 142 passed, 0 failed                                    │
│ ┃   ┗━ Tests green before changes.                                  │
│ ┃ ◆ Edit: "The parser needs a new token..."                         │
│ ┃   ┃ File: src/parser.rs (+15, -2)                                 │
│ ┃   ┗━ Edit complete. Verifying...                                  │
│ ┃ ◆ Verifying: Syntax → Lint → Tests → Property → Formal           │
│ ┃   ✓ Syntax: passed                                                 │
│ ┃   ⏳ Tests: running...                                             │
│                                                                    │
│ Status: ● RUNNING  Tokens: 12,345  Cost: $0.08  Duration: 34s     │
│ [Tab] Focus  [?] Help  [q] Quit  [↑↓] Scroll  [Enter] Inspect     │
└────────────────────────────────────────────────────────────────────┘
```

### 10.3 UI State Machine

```rust
pub enum AppState {
    Running { events_processed: u64, current_step: u32 },
    Browsing {
        selected_event: usize,
        scroll_offset: usize,
        view: BrowsingView,
    },
    Inspecting { event_index: usize, scroll_offset: usize },
}

pub enum BrowsingView {
    Timeline,     // Full event stream (default)
    Edits,        // Only FileEdit events
    Verifications, // Only VerificationEvents
    Summary,      // High-level summary
}
```

### 10.4 Glyph Set

| Glyph | Meaning | Context |
|-------|---------|---------|
| ┃ | SPINE | Fixed left column anchor |
| ◆ | Phase mark | Cognitive events |
| ▸ | OUT from spine | Action branches |
| ┗━ | CONVERGENCE | Return to spine after branch |
| ✓ | Passed | Verification success |
| ✗ | Failed | Verification failure |
| ⏳ | In progress | Pending operation |
| ● | Status dot | Footer indicator |
| ◇ | Sub-event | File edit hunk |

### 10.5 Key Bindings

| Key | Context | Action |
|-----|---------|--------|
| q/Ctrl+C | Any | Quit |
| ↑/↓ | Any | Scroll |
| PgUp/PgDn | Any | Page scroll |
| Enter | Browsing | Inspect selected event |
| Esc | Inspecting | Back to browsing |
| Tab | Any | Cycle focus |
| e | Browsing | Show Edits view |
| v | Browsing | Show Verifications view |
| t | Browsing | Show Timeline view |
| s | Browsing | Show Summary view |
| / | Browsing | Search events |
| ? | Any | Help overlay |
| [/] | Any | Zoom in/out |
| c | Main | Open config screen (H16) |


## 11. Anti-Duplication Boundary vs lgwks_ui

### 11.1 What We INSPIRE from lgwks_ui (do NOT copy)

| lgwks_ui Concept | forge-tui Translation | Why Not Copy |
|---|---|---|
| SPINE ┃ | Same glyph, same function | UI primitive, not code |
| DOWN+OUT sprawl | Same movement metaphor | UI pattern, not code |
| ┗━▴ convergence | ┗━ + ◆ convergence node | Different brand |
| Slate/Cream palette | Same hue family, diff hex | Different brand identity |
| Zero-dependency ANSI | crossterm + ratatui | forge-tui is separate binary |

### 11.2 What forge-tui Does DIFFERENTLY

| Aspect | lgwks_ui | forge-tui |
|---|---|---|
| Consumer | Research agent | Human supervising AI agent |
| Event model | Research phases | Agent lifecycle (think→act→observe→verify) |
| Permissions | None | Full PermissionGate |
| Diff rendering | None | Syntax-highlighted (syntect) |
| Config screen | None | Built-in config editor (H16) |
| Status bar | Minimal | Full run metadata |
| Key bindings | None (REPL) | Full keyboard nav |
| Output formats | Screen only | Text + NDJSON + JSON + Silent |
| Inspector mode | None | Per-event detail drill-down |

### 11.3 Code That MUST Be Original

- All `forge-tui/src/*.rs` files are new code, not copied from lgwks_ui.py
- Palette hex values are different from lgwks_ui's palette
- AppState is specific to agent supervision, not research browsing
- Key bindings, screen layout, event rendering purpose-built for forge's 13-event taxonomy

## 12. Hardening Checklist from 7 Packs

### 12.1 FORGE_FEEDBACK.md Fixes

| Lesson | Fix | Location |
|--------|-----|----------|
| Shell-tool output-capture bug | Command::new().arg().output(), never string parsing | ShellTool impl |
| byte-length vs char-length | .chars().take(n) not text[..n] | AgentResult, AgentContext |
| 2-dispatch pattern | Phase 1 = types, Phase 2 = tests | Implementation phases |
| Streaming output format | TextRenderer streams same events TUI consumes | forge-cli render/ |
| Permission-mode yolo | PermissionGate::Yolo + anti-slop still active | permission.rs |
| Never trust wrapper verdict | TUI shows raw exit code + stdout/stderr | forge-tui inspector |
| Config surface missing (H16) | forge config init/show/set; TUI config screen | forge-cli + forge-tui |

### 12.2 excellent_code_framework → All 10 proof obligations mapped

| Obligation | Implementation |
|------------|---------------|
| Grounding | correlation on every AgentEvent |
| Type safety | FailureReason enum, ActionClassification enum |
| Correctness | 5-gate verification pipeline |
| Invariant | Anti-slop hard gates always active |
| Boundary | Sandbox + protected paths |
| Resource | LoopGuard with max_steps/tokens/cost |
| Security | ProtectedPaths strategy |
| Observability | Correlation keys + Tracer |
| Falsifiability | PropertyCheck gate (proptest) |
| Locality | forge-core has 0 external deps |

### 12.3 human_like_corpus_model_os → 6 execution rules

| Rule | Implementation |
|------|---------------|
| read-state-before-action | NoEditWithoutReadEvidence anti-slop gate |
| update-state-after-change | StateUpdateEvent on every mutation |
| never-hide-failures | RunErrorEvent BEFORE break; failure_reason always set |
| preserve-raw-data | ToolResult carries raw stdout/stderr/exit_code |
| emit-manifest-for-outputs | RunEndEvent carries change_manifest |
| distinguish-THINK-from-PRINT | AgentEvent::Think separate from output text |

### 12.4 ai_semantic_rag_pack → DQS + strategy registry

- DQS formula via StrategyRegistry pattern (name → check)
- Strategy registry over if-chains: Vec<Box<dyn PermissionStrategy>>
- Escalation records over TODOs: DoctorEngine L0-L5
- Stable finding IDs: VerificationEvidence carries stable_id
- Spec-first: this document is source of truth

### 12.5 okf_dev_role_delta_pack-2 → role lattice

- forge-tui treats human as supervisor (SH), agent as worker (AI)
- DoctorEngine L0-L5 follows deterministic Markov-style policy
- ChangeManifest binds output to evidence/provenance/taint

### 12.6 debuggable_codebase_okf_2026 → executable knowledge graph

- Every break sets FailureReason; every event has Correlation
- Human debugging: forge-tui Browsing/Inspecting views
- AI-AI debugging: NDJSONRenderer + AuditLog
- Evidence: VerificationEvidence on every gate result
- Provenance: Correlation chain trace_id → run_id → event
- Reversible: ChangeManifest.rollback describes rollback command


## 13. Implementation Phases 1-6

### Phase 1: forge-core Types + Traits (week 1)

**Files to create:** forge-core/Cargo.toml, lib.rs, event.rs, result.rs, context.rs, step.rs, port.rs, agent.rs, renderer.rs

**Deliverable:** `cargo build` succeeds. All 13 event variants defined. All traits compile.

### Phase 2: forge-core Permission + Verification + Doctor + Session (week 1-2)

**Files to create:** permission.rs, verifier.rs, doctor.rs, session.rs, guard.rs, security.rs, tracer.rs, audit.rs

**Deliverable:** `cargo test` with unit tests for every PermissionVerdict, VerificationStatus, FailureReason, DoctorStatus, and LoopGuard break path.

### Phase 3: forge-cli (week 2-3)

**Files to create:** forge-cli/Cargo.toml, main.rs, commands/{run,doctor,session,eval,audit}.rs, render/{text,ndjson,mod}.rs

**Deliverable:** `forge run "hello"`, `forge doctor`, `forge session list` work. Tests with assert_cmd.

### Phase 4: forge-gemini (week 3)

**Files to create:** forge-gemini/Cargo.toml, lib.rs wrapping google-genai-rs Client → ModelPort impl

**Deliverable:** `forge run "hello" --provider gemini` streams events through TextRenderer or TUI.

### Phase 5: forge-tui (week 3-4)

**Files to create:** forge-tui/Cargo.toml, main.rs, app.rs, spine.rs, palette.rs, anim.rs, inspector.rs, config_screen.rs

**Deliverable:** `forge-tui` launches, shows live spine-based trace. Full keyboard nav.

### Phase 6: forge-ollama + forge-openai + forge-mcp + forge-harness (week 4-5)

**Files to create:** forge-ollama, forge-openai, forge-mcp, forge-harness crate directories

**Deliverable:** All providers work. MCP connector works. Eval harness runs benchmark.

## 14. Key Risks & Mitigations

| # | Risk | Mitigation |
|---|------|------------|
| 1 | AgentMode ≠ PermissionMode | forge-core has own PermissionGate |
| 2 | Event taxonomy mismatch | forge-core defines own AgentEvent; forge-gemini translates |
| 3 | Verifier depth (3 vs 5 gates) | forge-core defines own VerifierPipeline |
| 4 | No CLI precedent | forge-cli entirely new code using clap |
| 5 | Dependency hygiene | forge-core: only async-trait + thiserror + serde + tokio + uuid |
| 6 | TUI performance | Event batching; virtual scrolling; only visible events rendered |

## 15. Migration Map: Python → Rust

| Python file | Rust equivalent | Change |
|---|---|---|
| types.py | forge-core/event.rs, result.rs | Direct port |
| react.py | forge-core/agent.rs, guard.rs | Re-architecture to event-driven |
| events.py | forge-core/event.rs | 11→13 variants |
| cli/main.py | forge-cli/main.rs + commands/ | New (clap vs argparse) |
| cli/renderers.py | forge-cli/render/ | Direct port |
| cli/doctor.py | forge-core/doctor.rs | Port + harden L0-L5 |
| cli/permissions.py | forge-core/permission.rs | Port + anti-slop |
| cli/session.py | forge-core/session.rs | Port |
| cli/ansi.py | forge-tui/palette.rs | Replaced by crossterm/ratatui |
| models/gemini.py | forge-gemini/lib.rs | Wraps google-genai-rs |
| models/ollama.py | forge-ollama/lib.rs | Direct port (REST→REST) |
| tools/ | forge-core/security.rs | Port + fix shell-tool bug |
| harness/ | forge-harness/lib.rs | Port |

## 16. CI/CD Integration

### 16.1 Evidence Type Map

```rust
pub const EVIDENCE_TYPE_MAP: &[(&str, &str, &str)] = &[
    ("syntax_check",     "structural",  "Code compiles"),
    ("lint_analysis",    "structural",  "No anti-patterns"),
    ("test_execution",   "behavioral",  "Tests pass"),
    ("property_check",   "behavioral",  "Invariants via proptest"),
    ("formal_bound",     "formal",      "Lean-verifiable bound"),
];
```

### 16.2 CI Pipeline Gates

Every `forge run` with --output-format json or in CI emits a change_manifest.json:

```yaml
change_id: <uuid>
author_or_agent: forge
change_type: bugfix|feature|refactor
intent: What the agent was asked to do
blast_radius:
  files: [src/parser.rs]
  symbols: [NewToken]
rollback: git revert <commit>
```

CI gates (conceptual .github/workflows/forge-ci.yml):
```yaml
gates:
  - cargo build          # L0
  - cargo clippy         # L1
  - cargo test           # L2
  - cargo proptest       # L3
  - cargo lean-check     # L4 (optional)
```

### 16.3 Rust-skills Rules

| Category | Rules |
|----------|-------|
| err-* | thiserror for libs, anyhow for bins |
| own-* | Borrow > clone, Cow for optional, Arc<RwLock> over Mutex |
| async-* | tokio::spawn, FuturesUnordered, no blocking |
| cli-* | clap derive, meaningful exit codes, --json |
| test-* | proptest for property, assert_cmd for CLI, #[tokio::test] |
| mem-* | impl Trait over Box<dyn Trait> where possible |
| api-* | Builder pattern, #[non_exhaustive] on public structs |

---

*End of specification. This document is the single source of truth for forge Rust port v1.0.0.*

