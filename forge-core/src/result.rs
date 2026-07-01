use std::fmt;

use serde::{Deserialize, Serialize};

use crate::event::VerificationEvent;
use crate::step::AgentStep;

// ---------------------------------------------------------------------------
// FailureReason — 7 terminal break path discriminators
// ---------------------------------------------------------------------------

/// The 7 terminal break-path discriminators that can halt a run.
///
/// Every agent execution that terminates abnormally MUST produce a
/// `FailureReason` so that the caller has a machine-readable cause.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum FailureReason {
    /// The model returned an error or malformed response.
    ModelError(String),
    /// Token or cost usage exceeded the configured limit.
    UsageLimitExceeded,
    /// The convergence loop exhausted its allowed nudges without converging.
    ConvergenceFailure { nudges: u32, detail: String },
    /// The agent reached the maximum allowed step count.
    MaxStepsReached,
    /// A verification gate rejected the output.
    VerificationFailed { gate: String, detail: String },
    /// A permission gate denied the requested action.
    PermissionDenied { action: String, reason: String },
    /// Authentication with the model provider failed.
    AuthenticationFailure { provider: String, detail: String },
}

impl FailureReason {
    /// Returns `true` if the failure is potentially recoverable by retrying.
    ///
    /// The following are considered recoverable:
    /// - `ModelError` (transient model issues may resolve on retry)
    /// - `AuthenticationFailure` (credentials may be updated)
    ///
    /// The following are NOT recoverable and require human intervention:
    /// - `UsageLimitExceeded`, `ConvergenceFailure`, `MaxStepsReached`,
    ///   `VerificationFailed`, `PermissionDenied`
    pub fn is_recoverable(&self) -> bool {
        match self {
            Self::ModelError(_) | Self::AuthenticationFailure { .. } => true,
            Self::UsageLimitExceeded
            | Self::ConvergenceFailure { .. }
            | Self::MaxStepsReached
            | Self::VerificationFailed { .. }
            | Self::PermissionDenied { .. } => false,
        }
    }

    /// Returns a short, human-readable sentence describing the failure cause.
    pub fn causal_sentence(&self) -> String {
        match self {
            Self::ModelError(detail) => {
                let truncated: String = detail.chars().take(80).collect();
                format!("Model error: {}", truncated)
            }
            Self::UsageLimitExceeded => {
                "Usage limit exceeded — token or cost cap reached.".to_string()
            }
            Self::ConvergenceFailure { nudges, detail } => {
                let truncated: String = detail.chars().take(80).collect();
                format!("Convergence failed after {} nudges: {}", nudges, truncated)
            }
            Self::MaxStepsReached => {
                "Maximum step count reached without completing.".to_string()
            }
            Self::VerificationFailed { gate, detail } => {
                let truncated: String = detail.chars().take(80).collect();
                format!("Verification gate '{}' failed: {}", gate, truncated)
            }
            Self::PermissionDenied { action, reason } => {
                let truncated: String = reason.chars().take(80).collect();
                format!("Permission denied for '{}': {}", action, truncated)
            }
            Self::AuthenticationFailure { provider, detail } => {
                let truncated: String = detail.chars().take(80).collect();
                format!("Authentication failure with '{}': {}", provider, truncated)
            }
        }
    }
}

impl fmt::Display for FailureReason {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.causal_sentence())
    }
}

// ---------------------------------------------------------------------------
// ChangeManifest — record of what changed during a step
// ---------------------------------------------------------------------------

/// A record of all changes applied during a single step.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeManifest {
    pub files_changed: Vec<String>,
    pub files_created: Vec<String>,
    pub files_deleted: Vec<String>,
    pub commands_run: Vec<String>,
    pub summary: String,
}

impl ChangeManifest {
    pub fn new(
        files_changed: Vec<String>,
        files_created: Vec<String>,
        files_deleted: Vec<String>,
        commands_run: Vec<String>,
        summary: impl Into<String>,
    ) -> Self {
        let s: String = summary.into();
        let truncated: String = s.chars().take(80).collect();
        Self { files_changed, files_created, files_deleted, commands_run, summary: truncated }
    }
}

// ---------------------------------------------------------------------------
// VerificationEvidence — output of a single verification gate
// ---------------------------------------------------------------------------

/// The output of a single verification gate run.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationEvidence {
    pub gate: String,
    pub passed: bool,
    pub detail: String,
    pub event: Option<VerificationEvent>,
}

impl VerificationEvidence {
    pub fn new(gate: impl Into<String>, passed: bool, detail: impl Into<String>, event: Option<VerificationEvent>) -> Self {
        Self { gate: gate.into(), passed, detail: detail.into(), event }
    }
}

// ---------------------------------------------------------------------------
// RollbackPlan — instructions to undo a step
// ---------------------------------------------------------------------------

/// Instructions to undo a step that applied changes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RollbackPlan {
    pub description: String,
    pub paths_to_restore: Vec<String>,
    pub commands: Vec<String>,
}

impl RollbackPlan {
    pub fn new(description: impl Into<String>, paths_to_restore: Vec<String>, commands: Vec<String>) -> Self {
        Self { description: description.into(), paths_to_restore, commands }
    }
}

// ---------------------------------------------------------------------------
// AgentResult — the final outcome of an agent run
// ---------------------------------------------------------------------------

/// The final outcome of an agent run.
///
/// Carries optional verification evidence, a change manifest, and a
/// rollback plan alongside the success/failure status.
///
/// **Invariant:** When `success = false`, `failure_reason` MUST be `Some`.
/// This is documented but not type-enforced — callers should validate
/// with `validate_invariant()` before using the result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentResult {
    pub success: bool,
    /// The agent's final text output (required for CLI display).
    pub output: String,
    /// Ordered execution trace of steps (required by TUI Timeline).
    pub steps: Vec<AgentStep>,
    pub total_steps: u32,
    pub total_tokens: u64,
    pub total_cost: f64,
    pub duration_ms: u64,
    /// Correlation trace ID — every event in the run shares this.
    pub trace_id: String,
    /// Correlation run ID — scoped to a single execution.
    pub run_id: String,
    /// Which model actually ran (required by router.rs).
    pub model: String,
    /// Provider identifier (same reasoning as model).
    pub provider: String,
    /// Files that were touched during the run (required by VerificationContext).
    pub edits_made: Vec<String>,
    /// Named targets from the task that weren't found (EntityValidation gate).
    pub named_targets_missing: Vec<String>,
    pub failure_reason: Option<FailureReason>,
    pub verification: Vec<VerificationEvidence>,
    pub change_manifest: Option<ChangeManifest>,
    pub rollback_plan: Option<RollbackPlan>,
}

impl AgentResult {
    /// Create a successful AgentResult from completed steps.
    pub fn new_success(steps: &[AgentStep]) -> Self {
        Self {
            success: true,
            output: String::new(),
            steps: steps.to_vec(),
            total_steps: steps.len() as u32,
            total_tokens: 0,
            total_cost: 0.0,
            duration_ms: 0,
            trace_id: String::new(),
            run_id: String::new(),
            model: String::new(),
            provider: String::new(),
            edits_made: vec![],
            named_targets_missing: vec![],
            failure_reason: None,
            verification: vec![],
            change_manifest: None,
            rollback_plan: None,
        }
    }

    /// Create a premature shutdown AgentResult with a failure reason.
    pub fn new_premature_shutdown(reason: String, steps: &[AgentStep]) -> Self {
        Self {
            success: false,
            output: reason.clone(),
            steps: steps.to_vec(),
            total_steps: steps.len() as u32,
            total_tokens: 0,
            total_cost: 0.0,
            duration_ms: 0,
            trace_id: String::new(),
            run_id: String::new(),
            model: String::new(),
            provider: String::new(),
            edits_made: vec![],
            named_targets_missing: vec![],
            failure_reason: Some(FailureReason::MaxStepsReached),
            verification: vec![],
            change_manifest: None,
            rollback_plan: None,
        }
    }

    /// Validate the invariants that are not type-enforced.
    ///
    /// Returns `Ok(())` if all invariants hold, `Err(msg)` otherwise.
    /// - A failed run MUST carry a FailureReason.
    pub fn validate_invariant(&self) -> Result<(), String> {
        if !self.success && self.failure_reason.is_none() {
            return Err(
                "AgentResult invariant violated: failure_reason MUST be Some when success = false"
                    .into(),
            );
        }
        Ok(())
    }

    /// Returns a one-line summary of the result, truncated to 80 characters.
    ///
    /// Uses `.chars().take(80)` to respect Unicode grapheme boundaries rather
    /// than byte-slicing with `text[..n]`.
    pub fn char_count_aware_summary(&self) -> String {
        let msg = if self.success {
            format!(
                "Success -- {} steps, {} tokens, ${:.4}, {}ms",
                self.total_steps, self.total_tokens, self.total_cost, self.duration_ms
            )
        } else {
            let reason = self
                .failure_reason
                .as_ref()
                .map(|r| r.causal_sentence())
                .unwrap_or_else(|| "Unknown failure".to_string());
            format!(
                "Failed -- {} steps, {} tokens: {}",
                self.total_steps, self.total_tokens, reason
            )
        };
        msg.chars().take(80).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_failure_reason_recoverable() {
        assert!(FailureReason::ModelError("".into()).is_recoverable());
        assert!(FailureReason::AuthenticationFailure { provider: "".into(), detail: "".into() }.is_recoverable());
        assert!(!FailureReason::UsageLimitExceeded.is_recoverable());
        assert!(!FailureReason::MaxStepsReached.is_recoverable());
        assert!(!FailureReason::VerificationFailed { gate: "".into(), detail: "".into() }.is_recoverable());
        assert!(!FailureReason::PermissionDenied { action: "".into(), reason: "".into() }.is_recoverable());
        assert!(!FailureReason::ConvergenceFailure { nudges: 0, detail: "".into() }.is_recoverable());
    }

    #[test]
    fn test_failure_reason_causal_sentence() {
        let r = FailureReason::ModelError("timeout".into());
        assert!(r.causal_sentence().contains("timeout"));
        let r = FailureReason::UsageLimitExceeded;
        assert!(r.causal_sentence().contains("Usage limit"));
    }

    #[test]
    fn test_agent_result_round_trip() {
        let r = AgentResult {
            success: true,
            output: "done".into(),
            steps: vec![],
            total_steps: 5,
            total_tokens: 1000,
            total_cost: 0.05,
            duration_ms: 1200,
            trace_id: "trace-1".into(),
            run_id: "run-1".into(),
            model: "gemini-2.0-flash".into(),
            provider: "gemini".into(),
            edits_made: vec!["src/main.rs".into()],
            named_targets_missing: vec![],
            failure_reason: None,
            verification: vec![],
            change_manifest: None,
            rollback_plan: None,
        };
        assert!(r.validate_invariant().is_ok());
        assert!(r.char_count_aware_summary().contains("Success"));
    }

    #[test]
    fn test_agent_result_invariant_violation() {
        let r = AgentResult {
            success: false,
            output: String::new(),
            steps: vec![],
            total_steps: 0,
            total_tokens: 0,
            total_cost: 0.0,
            duration_ms: 0,
            trace_id: String::new(),
            run_id: String::new(),
            model: String::new(),
            provider: String::new(),
            edits_made: vec![],
            named_targets_missing: vec![],
            failure_reason: None,
            verification: vec![],
            change_manifest: None,
            rollback_plan: None,
        };
        assert!(r.validate_invariant().is_err());
    }

    #[test]
    fn test_agent_result_unicode_truncation() {
        let r = AgentResult {
            success: true,
            output: "✅".repeat(100),
            steps: vec![],
            total_steps: 5,
            total_tokens: 1000,
            total_cost: 0.05,
            duration_ms: 1200,
            trace_id: "trace-1".into(),
            run_id: "run-1".into(),
            model: "gemini-2.0-flash".into(),
            provider: "gemini".into(),
            edits_made: vec!["src/main.rs".into()],
            named_targets_missing: vec![],
            failure_reason: None,
            verification: vec![],
            change_manifest: None,
            rollback_plan: None,
        };
        let summary = r.char_count_aware_summary();
        assert!(summary.chars().count() <= 80);
    }
}
