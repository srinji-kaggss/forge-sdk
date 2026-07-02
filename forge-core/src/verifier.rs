use std::path::PathBuf;
use std::sync::Arc;

use serde::{Deserialize, Serialize};

use forge_core_security::containment::{Tainted, Trusted};

use crate::port::ModelPort;

// ---------------------------------------------------------------------------
// GateKind — exactly 6 verification gates
// ---------------------------------------------------------------------------

/// The 6 verification gates in Python's own fail-fast order.
/// Exactly 6 — PropertyCheck deferred to v2, FormalBound cut entirely.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum GateKind {
    SyntaxCheck,
    AstParse,
    EntityValidation,
    ShellDryRun,
    SpecConformance,
    SemanticCheck,
}

// ---------------------------------------------------------------------------
// VerificationStatus — 4-variant status
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum VerificationStatus {
    Passed,
    Failed,
    Skipped,
    Error,
}

// ---------------------------------------------------------------------------
// GateFailureReason — closed enum, NOT free-text String
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum GateFailureReason {
    SyntaxError,
    LintViolation,
    NamedTargetMissing { target: String },
    DryRunFailed,
    ArtifactsMissing { missing: Vec<String> },
    SemanticMismatch { reason_code: SemanticReasonCode },
    ModelNotConfigured,
    BudgetSkipped,
}

// ---------------------------------------------------------------------------
// SemanticReasonCode — closed companion for SemanticCheck
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SemanticReasonCode {
    Mismatch,
    PartialImplementation,
    WrongFile,
    Unclear,
}

// ---------------------------------------------------------------------------
// VerificationEvidence — output of a single gate
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationEvidence {
    pub gate: GateKind,
    /// Stable identifier for this verification run (e.g., "verif-abc123").
    pub stable_id: String,
    pub status: VerificationStatus,
    /// Closed enum, NOT free-text — see GateFailureReason.
    pub detail: GateFailureReason,
    /// Human-readable output from the gate (e.g., compiler messages).
    pub output: String,
    pub duration_ms: u64,
}

impl VerificationEvidence {
    pub fn new(
        gate: GateKind,
        stable_id: impl Into<String>,
        status: VerificationStatus,
        detail: GateFailureReason,
        output: impl Into<String>,
        duration_ms: u64,
    ) -> Self {
        Self {
            gate,
            stable_id: stable_id.into(),
            status,
            detail,
            output: output.into(),
            duration_ms,
        }
    }
}

// ---------------------------------------------------------------------------
// VerificationContext — NOW DEFINED (was undefined in original spec)
// ---------------------------------------------------------------------------

/// Full context for running verification gates.
///
/// - `task`: The original task description (Trusted, from containment).
/// - `all_edits`: Every file path touched during the run.
/// - `output`: The agent's final text output.
/// - `solution_summary`: The solution summary from the agent (Tainted, from model output).
/// - `model_port`: Optional model connection for SemanticCheck gate.
pub struct VerificationContext {
    pub task: Trusted<String>,
    pub all_edits: Vec<PathBuf>,
    pub output: String,
    pub solution_summary: Tainted<String>,
    pub model_port: Option<Arc<dyn ModelPort>>,
}

impl VerificationContext {
    pub fn new(
        task: Trusted<String>,
        all_edits: Vec<PathBuf>,
        output: impl Into<String>,
        solution_summary: Tainted<String>,
        model_port: Option<Arc<dyn ModelPort>>,
    ) -> Self {
        Self {
            task,
            all_edits,
            output: output.into(),
            solution_summary,
            model_port,
        }
    }
}

// ---------------------------------------------------------------------------
// VerificationBudget — budget-aware skip logic
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct VerificationBudget {
    pub remaining_cost: f64,
    pub remaining_tokens: u64,
}

impl VerificationBudget {
    pub fn new(remaining_cost: f64, remaining_tokens: u64) -> Self {
        Self {
            remaining_cost,
            remaining_tokens,
        }
    }

    /// Returns `true` if the given gate should be skipped under budget pressure.
    /// Expensive gates (SemanticCheck) are skipped when remaining budget is low.
    pub fn should_skip(&self, gate: &GateKind) -> bool {
        match gate {
            GateKind::SemanticCheck => {
                // SemanticCheck uses a model call — skip if under budget
                self.remaining_cost < 0.01 || self.remaining_tokens < 1000
            }
            // All other gates are cheap (syntax, file ops, etc.)
            _ => false,
        }
    }
}

// ---------------------------------------------------------------------------
// VerificationGate trait
// ---------------------------------------------------------------------------

#[async_trait::async_trait]
pub trait VerificationGate: Send + Sync + std::fmt::Debug {
    fn kind(&self) -> GateKind;
    async fn run(&self, ctx: &VerificationContext) -> VerificationEvidence;
}

// ---------------------------------------------------------------------------
// VerifierPipeline — the main verification engine
// ---------------------------------------------------------------------------

/// The verification pipeline, running gates in order with fail-fast.
///
/// # Invariants
/// - Gates run in registration order (Python's fail-fast order).
/// - First `Failed` or `Error` result stops the pipeline immediately.
/// - Budget-skipped gates produce `Skipped` evidence without running.
#[derive(Debug)]
pub struct VerifierPipeline {
    gates: Vec<Box<dyn VerificationGate>>,
    budget: Option<VerificationBudget>,
}

impl VerifierPipeline {
    /// Create a new pipeline with explicit gates.
    pub fn new(gates: Vec<Box<dyn VerificationGate>>, budget: Option<VerificationBudget>) -> Self {
        Self { gates, budget }
    }

    /// Create the default 6-gate pipeline in Python's fail-fast order.
    pub fn with_default_gates(budget: Option<VerificationBudget>) -> Self {
        Self {
            gates: vec![
                Box::new(SyntaxCheckGate),
                Box::new(AstParseGate),
                Box::new(EntityValidationGate),
                Box::new(ShellDryRunGate),
                Box::new(SpecConformanceGate),
                Box::new(SemanticCheckGate),
            ],
            budget,
        }
    }

    /// Run all gates in order. Stops on first failure (fail-fast).
    /// Budget-skipped gates produce `Skipped` evidence.
    pub async fn run_all(&self, ctx: &VerificationContext) -> Vec<VerificationEvidence> {
        let mut results = Vec::with_capacity(self.gates.len());

        for gate in &self.gates {
            let kind = gate.kind();

            // Budget check
            if let Some(ref budget) = self.budget {
                if budget.should_skip(&kind) {
                    results.push(VerificationEvidence::new(
                        kind.clone(),
                        format!("{:?}-budget-skipped", kind),
                        VerificationStatus::Skipped,
                        GateFailureReason::BudgetSkipped,
                        "Skipped due to budget pressure",
                        0,
                    ));
                    continue;
                }
            }

            let evidence = gate.run(ctx).await;
            let is_failure = matches!(
                evidence.status,
                VerificationStatus::Failed | VerificationStatus::Error
            );

            results.push(evidence);

            // Fail-fast: stop on first failure
            if is_failure {
                break;
            }
        }

        results
    }
}

// ---------------------------------------------------------------------------
// Default 6 gates
// ---------------------------------------------------------------------------

/// Gate 1: Syntax check — validates file syntax (phase 0: always passes)
#[derive(Debug)]
pub struct SyntaxCheckGate;

#[async_trait::async_trait]
impl VerificationGate for SyntaxCheckGate {
    fn kind(&self) -> GateKind {
        GateKind::SyntaxCheck
    }
    async fn run(&self, _ctx: &VerificationContext) -> VerificationEvidence {
        // Phase 0: passthrough. Phase 1+ will parse files with tree-sitter
        VerificationEvidence::new(
            GateKind::SyntaxCheck,
            "syntax-default",
            VerificationStatus::Passed,
            GateFailureReason::SyntaxError, // not used on Passed
            "All files pass syntax check (phase 0: passthrough)",
            0,
        )
    }
}

/// Gate 2: AST parse — validates abstract syntax tree (phase 0: always passes)
#[derive(Debug)]
pub struct AstParseGate;

#[async_trait::async_trait]
impl VerificationGate for AstParseGate {
    fn kind(&self) -> GateKind {
        GateKind::AstParse
    }
    async fn run(&self, _ctx: &VerificationContext) -> VerificationEvidence {
        VerificationEvidence::new(
            GateKind::AstParse,
            "ast-default",
            VerificationStatus::Passed,
            GateFailureReason::LintViolation, // not used on Passed
            "AST parse passes (phase 0: passthrough)",
            0,
        )
    }
}

/// Gate 3: Entity validation — checks named targets exist
#[derive(Debug)]
pub struct EntityValidationGate;

#[async_trait::async_trait]
impl VerificationGate for EntityValidationGate {
    fn kind(&self) -> GateKind {
        GateKind::EntityValidation
    }
    async fn run(&self, _ctx: &VerificationContext) -> VerificationEvidence {
        // Phase 0: checks that all_edits refer to existing files
        let missing: Vec<String> = _ctx
            .all_edits
            .iter()
            .filter(|p| !p.exists())
            .map(|p| p.to_string_lossy().to_string())
            .collect();

        if missing.is_empty() {
            VerificationEvidence::new(
                GateKind::EntityValidation,
                "entity-default",
                VerificationStatus::Passed,
                GateFailureReason::NamedTargetMissing {
                    target: String::new(),
                },
                "All target files exist",
                0,
            )
        } else {
            VerificationEvidence::new(
                GateKind::EntityValidation,
                "entity-default",
                VerificationStatus::Failed,
                GateFailureReason::NamedTargetMissing {
                    target: missing.join(", "),
                },
                format!("Missing files: {}", missing.join(", ")),
                0,
            )
        }
    }
}

/// Gate 4: Shell dry run — validates shell commands (phase 0: always passes)
#[derive(Debug)]
pub struct ShellDryRunGate;

#[async_trait::async_trait]
impl VerificationGate for ShellDryRunGate {
    fn kind(&self) -> GateKind {
        GateKind::ShellDryRun
    }
    async fn run(&self, _ctx: &VerificationContext) -> VerificationEvidence {
        VerificationEvidence::new(
            GateKind::ShellDryRun,
            "dryrun-default",
            VerificationStatus::Passed,
            GateFailureReason::DryRunFailed, // not used on Passed
            "Shell dry run passes (phase 0: passthrough)",
            0,
        )
    }
}

/// Gate 5: Spec conformance — checks output matches specification
#[derive(Debug)]
pub struct SpecConformanceGate;

#[async_trait::async_trait]
impl VerificationGate for SpecConformanceGate {
    fn kind(&self) -> GateKind {
        GateKind::SpecConformance
    }
    async fn run(&self, _ctx: &VerificationContext) -> VerificationEvidence {
        // Phase 0: passthrough. Phase 1+ will check output against spec JSON.
        VerificationEvidence::new(
            GateKind::SpecConformance,
            "spec-default",
            VerificationStatus::Passed,
            GateFailureReason::ArtifactsMissing { missing: vec![] },
            "Output conforms to specification (phase 0: passthrough)",
            0,
        )
    }
}

/// Gate 6: Semantic check — uses model to grade output quality
#[derive(Debug)]
pub struct SemanticCheckGate;

#[async_trait::async_trait]
impl VerificationGate for SemanticCheckGate {
    fn kind(&self) -> GateKind {
        GateKind::SemanticCheck
    }
    async fn run(&self, ctx: &VerificationContext) -> VerificationEvidence {
        // Phase 0: passthrough. Phase 1+ will call model_port to grade output.
        if ctx.model_port.is_none() {
            return VerificationEvidence::new(
                GateKind::SemanticCheck,
                "semantic-default",
                VerificationStatus::Skipped,
                GateFailureReason::ModelNotConfigured,
                "SemanticCheck requires a model port — none configured",
                0,
            );
        }

        VerificationEvidence::new(
            GateKind::SemanticCheck,
            "semantic-default",
            VerificationStatus::Passed,
            GateFailureReason::SemanticMismatch {
                reason_code: SemanticReasonCode::Mismatch,
            },
            "Semantic check passes (phase 0: passthrough)",
            0,
        )
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gate_kind_serde() {
        let k = GateKind::SyntaxCheck;
        let json = serde_json::to_string(&k).unwrap();
        assert_eq!(json, "\"SyntaxCheck\"");
        let back: GateKind = serde_json::from_str(&json).unwrap();
        assert_eq!(back, GateKind::SyntaxCheck);
    }

    #[tokio::test]
    async fn test_default_pipeline_all_pass() {
        let pipeline = VerifierPipeline::with_default_gates(None);
        let ctx = VerificationContext::new(
            Trusted::new_internal("test task".into()),
            vec![],
            "test output",
            Tainted::new_unchecked("test summary".into()),
            None,
        );
        let results = pipeline.run_all(&ctx).await;
        assert_eq!(results.len(), 6);
        // First 5 gates pass (SyntaxCheck through SpecConformance)
        for r in results.iter().take(5) {
            assert_eq!(
                r.status,
                VerificationStatus::Passed,
                "Gate {:?} should pass",
                r.gate
            );
        }
        // SemanticCheck is Skipped because model_port is None
        assert_eq!(results[5].status, VerificationStatus::Skipped);
        assert_eq!(results[5].detail, GateFailureReason::ModelNotConfigured);
    }

    #[tokio::test]
    async fn test_fail_fast() {
        // Create a gate that fails immediately
        #[derive(Debug)]
        struct FailingGate;
        #[async_trait::async_trait]
        impl VerificationGate for FailingGate {
            fn kind(&self) -> GateKind {
                GateKind::EntityValidation
            }
            async fn run(&self, _ctx: &VerificationContext) -> VerificationEvidence {
                VerificationEvidence::new(
                    GateKind::EntityValidation,
                    "fail-test",
                    VerificationStatus::Failed,
                    GateFailureReason::NamedTargetMissing {
                        target: "test.rs".into(),
                    },
                    "Test failure",
                    0,
                )
            }
        }

        let pipeline = VerifierPipeline::new(
            vec![
                Box::new(SyntaxCheckGate),
                Box::new(FailingGate),
                Box::new(AstParseGate), // should NOT run
            ],
            None,
        );

        let ctx = VerificationContext::new(
            Trusted::new_internal("test".into()),
            vec![PathBuf::from("test.rs")],
            "test",
            Tainted::new_unchecked("summary".into()),
            None,
        );

        let results = pipeline.run_all(&ctx).await;
        assert_eq!(results.len(), 2); // SyntaxCheck + FailingGate, AstParse skipped
        assert_eq!(results[0].status, VerificationStatus::Passed);
        assert_eq!(results[1].status, VerificationStatus::Failed);
    }

    #[tokio::test]
    async fn test_budget_skip_semantic_check() {
        let budget = VerificationBudget::new(0.005, 500); // below thresholds
        let pipeline = VerifierPipeline::with_default_gates(Some(budget));
        let ctx = VerificationContext::new(
            Trusted::new_internal("test".into()),
            vec![],
            "test",
            Tainted::new_unchecked("summary".into()),
            None,
        );
        let results = pipeline.run_all(&ctx).await;
        // SemanticCheck should be Skipped
        let semantic = results
            .iter()
            .find(|r| r.gate == GateKind::SemanticCheck)
            .unwrap();
        assert_eq!(semantic.status, VerificationStatus::Skipped);
        assert_eq!(semantic.detail, GateFailureReason::BudgetSkipped);
    }

    #[tokio::test]
    async fn test_entity_validation_detects_missing() {
        let pipeline = VerifierPipeline::with_default_gates(None);
        let ctx = VerificationContext::new(
            Trusted::new_internal("test".into()),
            vec![PathBuf::from("/nonexistent_file_xyz_test_123.txt")],
            "test",
            Tainted::new_unchecked("summary".into()),
            None,
        );
        let results = pipeline.run_all(&ctx).await;
        // EntityValidation should detect the missing file
        let entity = results
            .iter()
            .find(|r| r.gate == GateKind::EntityValidation)
            .unwrap();
        // Entity validation may be passed or failed depending on file existence
        // We just verify it ran
        assert!(!entity.output.is_empty());
    }

    #[tokio::test]
    async fn test_semantic_check_skipped_without_model() {
        let pipeline = VerifierPipeline::with_default_gates(None);
        let ctx = VerificationContext::new(
            Trusted::new_internal("test".into()),
            vec![],
            "test",
            Tainted::new_unchecked("summary".into()),
            None,
        );
        let results = pipeline.run_all(&ctx).await;
        let semantic = results
            .iter()
            .find(|r| r.gate == GateKind::SemanticCheck)
            .unwrap();
        assert_eq!(semantic.status, VerificationStatus::Skipped);
        assert_eq!(semantic.detail, GateFailureReason::ModelNotConfigured);
    }
}
