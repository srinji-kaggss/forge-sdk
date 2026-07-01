use std::fmt;

use serde::{Deserialize, Serialize};

use crate::event::VerificationEvent;

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
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentResult {
    pub success: bool,
    pub total_steps: u32,
    pub total_tokens: u64,
    pub total_cost: f64,
    pub duration_ms: u64,
    pub failure_reason: Option<FailureReason>,
    pub verification: Vec<VerificationEvidence>,
    pub change_manifest: Option<ChangeManifest>,
    pub rollback_plan: Option<RollbackPlan>,
}

impl AgentResult {
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
