# NEXT-FOR-CLINE.md — Bounded Dispatch Chunks for Cline

**Date:** 2026-07-01  
**Dispatcher:** Claude (Simulator, post-hardening-review)  
**Status:** Phase A (fix real gaps in landed code) + Phase B (implement per reconciled specs)  
**Prerequisites:** Read CLAUDE-REVIEW.md §8 first, then §7.1-§7.8 for context on spec corrections.

---

## Phase A: Fix What Already Landed (Critical, Do First)

Code landed in `forge-core/` (commit b7040ac, "752 lines Rust, compiles clean") has real gaps found in review. These three chunks close them exactly—do not remove anything already there, only add missing fields.

### A1: Add Missing Fields to `AgentResult`

**Task:** AgentResult is missing 8 fields that specs require and downstream code (VerificationContext, CLI renderers, routers) will depend on.

**Scope:**
- File: `forge-core/src/result.rs`
- Add these fields to `AgentResult` struct (do not remove: `success, total_steps, total_tokens, total_cost, duration_ms, failure_reason, verification, change_manifest, rollback_plan` — all stay):
  - `pub output: String` — the agent's final text output (not a nice-to-have, required for CLI display)
  - `pub steps: Vec<AgentStep>` — ordered execution trace (required by TUI Timeline, SpecConformance gate)
  - `pub trace_id: String` — correlation ID (required by every other event type in the spec; missing here breaks the chain)
  - `pub run_id: String` — run-scoped correlation (same reasoning as trace_id)
  - `pub model: String` — which model actually ran (required by router.rs, IMPLEMENTATION_PLAYBOOK.md §2.8)
  - `pub provider: String` — provider identifier (same reasoning as model)
  - `pub edits_made: Vec<String>` — files touched (required by VerificationContext.all_edits, SpecConformance gate)
  - `pub named_targets_missing: Vec<String>` — targets from task that weren't found (backs EntityValidation gate)

**Done when:**
```bash
cd forge-core && cargo build 2>&1 | grep -q "Finished"
```
And a unit test round-trips the struct with all new fields set:
```bash
cd forge-core && cargo test result::tests 2>&1 | grep -q "test result: ok"
```

---

### A2: Add Missing Fields to `AgentContext`

**Task:** AgentContext is missing 2 fields required for multi-turn loops and step tracking.

**Scope:**
- File: `forge-core/src/context.rs`
- Add these fields (do not remove: `task, cwd, max_steps, max_tokens, max_cost, trace_id, run_id, session_id, model, provider, env_vars` — all stay):
  - `pub messages: Vec<serde_json::Value>` — conversation history (required to drive multi-turn loops; Python type: `list[dict]`)
  - `pub step_count: u32` — current step counter (required by LoopGuard checks and TUI display "12/25 steps")

**Done when:**
```bash
cd forge-core && cargo build 2>&1 | grep -q "Finished"
```
And a unit test confirms both fields serialize/deserialize correctly and LoopGuard reads step_count:
```bash
cd forge-core && cargo test context::tests 2>&1 | grep -q "test result: ok"
```

---

### A3: Fix `AgentStep.action_input` from String Back to Structured Map + Add Missing Fields

**Task:** AgentStep.action_input was collapsed to a plain `String` (JSON blob), losing structure TUI inspectors and audit-replays need. Also missing `is_final` and `loop_guard_triggered` flags.

**Scope:**
- File: `forge-core/src/step.rs`
- Change field:
  - `action_input: String` → `action_input: HashMap<String, serde_json::Value>` (restore structure for per-arg display and risk classification)
- Add fields (do not remove: `index, thought, action, observation, exit_code, tokens_used, cost, tool_name, event` — all stay):
  - `pub is_final: bool` — marks a "finish" action (vs mid-loop steps)
  - `pub loop_guard_triggered: bool` — set `true` only when LoopGuard forced a stop (this distinguishes normal finish from forced break, required by VerificationContext logic)

**Done when:**
```bash
cd forge-core && cargo build 2>&1 | grep -q "Finished"
```
And a unit test confirms action_input round-trips as a HashMap and both new bool fields default correctly:
```bash
cd forge-core && cargo test step::tests 2>&1 | grep -q "test result: ok"
```

---

## Phase B: Implement Per Reconciled Specs

After Phase A compiles clean, these chunks implement the next layer. Each depends on its predecessor.

### B1: Implement `forge-core-security` Crate (New, Per SPEC-SECURITY-003)

**Task:** Create a new crate housing compile-time taint tracking (`Tainted<T>`/`Trusted<T>`), containment results, and sandbox capabilities—the foundational security boundary SPEC-SECURITY-003 §3.2-§3.3 specifies. This crate ships independently (JSON-pipe to Python in Phase 1, embedded in agent.rs later).

**Scope:**
- Create new crate directory: `forge-core-security/`
- Create `forge-core-security/Cargo.toml` with dependencies (⚠️ versions corrected 2026-07-01 — verified live against crates.io, do not use the versions in any earlier draft of this file, none of these were checked against the real registry when first written):
  - `cap-std = "4"` (real max version `4.0.2` as of this check — Bytecode Alliance capability filesystem)
  - `serde = { version = "1", features = ["derive"] }`
  - `serde_json = "1"`
  - `untrusted_value = "0.3"` (real max version `0.3.2` as of this check — the compile-time taint newtype primitive)
- Implement `src/lib.rs` with two modules:
  - **`containment.rs`**: Per SPEC-SECURITY-003 §3.2
    - `pub struct Tainted<T>(T)` — no public constructor except from raw I/O
    - `pub struct Trusted<T>(T)` — the ONLY thing prompt-construction accepts
    - `pub enum ContainmentResult { Safe { category: Category, risk_score: f32 }, Quarantined { risk_score: f32 } }`
    - `pub enum Category { TimeoutHandling, PermissionErrors, ... }` — closed enum, one variant per containment class
    - Implement `Tainted::contain()` method that returns `ContainmentResult`
  - **`sandbox.rs`**: Per SPEC-SECURITY-003 §3.3
    - `pub struct SandboxRoot(cap_std::fs::Dir)` — wraps the capability
    - `pub fn open(&self, relative_path: &str) -> io::Result<File>` — the ONLY filesystem entry point; no function to forget to call, no absolute paths possible
    - Unit tests: legitimate relative access, absolute-path rejection (must fail to compile/return Error), symlink-escape rejection, temp-dir allowance (per existing Python behavior)

**Done when:**
```bash
cd forge-core-security && cargo build 2>&1 | grep -q "Finished"
```
And all three gate tests pass:
```bash
cd forge-core-security && cargo test 2>&1 | grep -q "test result: ok"
```

---

### B2: Implement `permission.rs` in forge-core (Per Reconciled FORGE-RUST-TUI-SPEC §4)

**Task:** Implement the permission decision engine with reconciled `PermissionDecision`/`DenyReason`/`PolicyTier` enums (SPEC-SECURITY-003 §3.4, not the old `PermissionVerdict`). Depends on forge-core-security landing first.

**Scope:**
- File: `forge-core/src/permission.rs`
- Implement (from FORGE-RUST-TUI-SPEC.md §4.1-§4.4):
  - `pub enum ActionClassification { Safe, LocalWrite, Destructive, NetworkOut, NetworkIn, Exec, GitHistory, Auth, Config, Install }`
  - `pub struct PermissionContext { action_label: String, classification: ActionClassification, tool_name: String, tool_args: HashMap<String, serde_json::Value>, cwd: PathBuf, sandbox: forge_core_security::SandboxRoot, files_read_in_session: Vec<PathBuf>, permission_mode: PermissionMode, task: forge_core_security::Trusted<String> }`
  - `pub enum PermissionDecision { Allow { updated_input: Option<serde_json::Value> }, Deny { reason: DenyReason, interrupt: bool } }` — exactly 2 variants, no 3rd "NeedsApproval" (that's now `Deny` with `interrupt: true`)
  - `pub enum DenyReason { HardDenyRule { rule_id: &'static str }, NoReadEvidence, TestDeletionWithoutReplacement, OutsideSandbox, QuarantinedContent, NeedsExplicitIntent { classification: ActionClassification }, UsageLimitExceeded }`
  - `pub enum PolicyTier { HardDeny, SoftDeny, Allow, Environment }`
  - `pub struct PermissionGate { mode: PermissionMode, anti_slop_strategies: Vec<Box<dyn PermissionStrategy>>, policy: HashMap<ActionClassification, PolicyTier>, history: Vec<PermissionGateEvent> }`
  - `pub enum PermissionMode { Interactive, Yolo, Plan }` — existing, port as-is
  - Implement `PermissionGate::default_anti_slop()` with exactly 2 strategies: `NoEditWithoutReadEvidence` and `NoTestDeletionWithoutReplacement` (the old `MustAddTestForFix`/`ProtectedPaths` were either non-existent in Python or belong in HardDeny policy, not strategies — see CLAUDE-REVIEW.md §7.4)
  - Implement `PermissionGate::default_policy()` mapping ActionClassification → PolicyTier per FORGE-RUST-TUI-SPEC §4.3
  - Implement `PermissionGate::evaluate(&mut self, ctx: &PermissionContext) -> PermissionDecision` with the 3-step logic in FORGE-RUST-TUI-SPEC §4.3 (anti-slop first, then PolicyTier lookup, then mode-specific handling)

**Done when:**
```bash
cd forge-core && cargo build 2>&1 | grep -q "Finished"
```
And unit tests pass all 3 modes (Interactive/Yolo/Plan) plus HardDeny overriding Yolo:
```bash
cd forge-core && cargo test permission::tests 2>&1 | grep -q "test result: ok"
```

---

### B3: Implement `verifier.rs` in forge-core (Per Reconciled FORGE-RUST-TUI-SPEC §5)

**Task:** Implement the 6-gate verification pipeline with corrected gate names, resolved `VerificationContext` (was undefined), and closed `GateFailureReason` enum (replaces free-text detail). Note: `PropertyCheck` deferred to v2, `FormalBound` cut entirely (see CLAUDE-REVIEW.md §7.5).

**Scope:**
- File: `forge-core/src/verifier.rs`
- Implement (from FORGE-RUST-TUI-SPEC.md §5):
  - `pub enum GateKind { SyntaxCheck, AstParse, EntityValidation, ShellDryRun, SpecConformance, SemanticCheck }` — exactly 6, no PropertyCheck placeholder
  - `pub struct VerificationEvidence { gate: GateKind, stable_id: String, status: VerificationStatus, detail: GateFailureReason, output: String, duration_ms: u64 }` — `detail` is NOW a closed enum, not a free-text String
  - `pub enum VerificationStatus { Passed, Failed, Skipped, Error }`
  - `pub enum GateFailureReason { SyntaxError, LintViolation, NamedTargetMissing { target: String }, DryRunFailed, ArtifactsMissing { missing: Vec<String> }, SemanticMismatch { reason_code: SemanticReasonCode }, ModelNotConfigured, BudgetSkipped }`
  - `pub enum SemanticReasonCode { Mismatch, PartialImplementation, WrongFile, Unclear }` — the closed companion for SemanticCheck's grading-model output
  - `pub struct VerificationContext { task: Trusted<String>, all_edits: Vec<PathBuf>, output: String, solution_summary: Tainted<String>, model_port: Option<Arc<dyn ModelPort>> }` — NOW DEFINED (was undefined in original spec)
  - `pub struct VerificationBudget { remaining_cost: f64, remaining_tokens: u64 }` with `should_skip(gate)` returning true for expensive gates (SemanticCheck/PropertyCheck) under budget pressure
  - `pub struct VerifierPipeline { gates: Vec<Box<dyn VerificationGate>>, budget: Option<VerificationBudget> }`
  - `pub fn with_default_gates() -> Self` creating the 6-gate pipeline in Python's own fail-fast order
  - `pub async fn run_all(&self, ctx: &VerificationContext) -> Vec<VerificationEvidence>` with fail-fast on first failure and budget-aware skips

**Done when:**
```bash
cd forge-core && cargo build 2>&1 | grep -q "Finished"
```
And unit tests confirm all 6 gates integrate, fail-fast works, and budget skip logic is correct:
```bash
cd forge-core && cargo test verifier::tests 2>&1 | grep -q "test result: ok"
```

---

## Summary

**Phase A (now):** Three small, surgical additions to `context.rs`, `result.rs`, `step.rs`. Each is `cargo build` + one simple test. Total time: ~30 minutes.

**Phase B (after A lands clean):** Three implementation chunks in order (B1 → B2 → B3), each building on the prior. B1 is a new crate (~200 lines), B2 is ~300 lines of permission logic, B3 is ~400 lines of gate traits + pipeline. Standard dispatch complexity per project.

**What's already done:** Phase 0 types landed (event.rs, the core event taxonomy). Phase 0 code review found these 3 gaps; this doc fixes them without rewriting anything.

**What happens next:** Once Phase A+B land, Phase 2 (the agent-loop rewrite per SPEC-SECURITY-003 §4) starts—that's the real integration work where forge-core-security's types get wired into permission checks and tool calls. But the foundation is mechanical and small.

**Critical discipline:** Do NOT add anything beyond what's listed. Do NOT invent new fields or restructure existing ones. Do NOT merge these chunks into each other. Each is independently verifiable—dispatch them one at a time and verify `cargo build` + the named test before moving to the next.
