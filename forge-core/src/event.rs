/// Correlation keys carried by every event — ADR-1 (hash-chain observable).
///
/// Every event in the forge system carries a `Correlation` so that the full
/// event stream can be traced, replayed, and audited as a hash chain.
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct Correlation {
    pub trace_id: String,
    pub run_id: String,
    pub model: String,
    pub provider: String,
    pub config_version: String,
}

/// The ONE event enum — 13 discriminators. Every human- and machine-facing
/// feature consumes this event stream (ADR-1).
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
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

// ---------------------------------------------------------------------------
// Payload structs
// ---------------------------------------------------------------------------

/// Fired when a run begins.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct RunStartEvent {
    pub correlation: Correlation,
    pub task: String,
    pub model: String,
    pub provider: String,
    pub max_steps: u32,
    pub max_tokens: u64,
}

impl RunStartEvent {
    pub fn new(
        correlation: Correlation,
        task: impl Into<String>,
        model: impl Into<String>,
        provider: impl Into<String>,
        max_steps: u32,
        max_tokens: u64,
    ) -> Self {
        Self {
            correlation,
            task: task.into(),
            model: model.into(),
            provider: provider.into(),
            max_steps,
            max_tokens,
        }
    }
}

/// Fired when a run completes successfully.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct RunEndEvent {
    pub correlation: Correlation,
    pub success: bool,
    pub total_steps: u32,
    pub total_tokens: u64,
    pub total_cost: f64,
    pub duration_ms: u64,
}

impl RunEndEvent {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        correlation: Correlation,
        success: bool,
        total_steps: u32,
        total_tokens: u64,
        total_cost: f64,
        duration_ms: u64,
    ) -> Self {
        Self {
            correlation,
            success,
            total_steps,
            total_tokens,
            total_cost,
            duration_ms,
        }
    }
}

/// Fired when a run terminates with an error.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct RunErrorEvent {
    pub correlation: Correlation,
    pub error: String,
    pub failure_reason: String,
}

impl RunErrorEvent {
    pub fn new(
        correlation: Correlation,
        error: impl Into<String>,
        failure_reason: impl Into<String>,
    ) -> Self {
        Self {
            correlation,
            error: error.into(),
            failure_reason: failure_reason.into(),
        }
    }
}

/// Fired when the agent performs a reasoning / thought step.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ThinkEvent {
    pub correlation: Correlation,
    pub thought: String,
    pub tokens_used: u64,
}

impl ThinkEvent {
    pub fn new(correlation: Correlation, thought: impl Into<String>, tokens_used: u64) -> Self {
        Self {
            correlation,
            thought: thought.into(),
            tokens_used,
        }
    }
}

/// Fired when the agent performs an action (tool call).
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct ActionEvent {
    pub correlation: Correlation,
    pub action: String,
    pub action_input: String,
    pub tool_name: String,
}

impl ActionEvent {
    pub fn new(
        correlation: Correlation,
        action: impl Into<String>,
        action_input: impl Into<String>,
        tool_name: impl Into<String>,
    ) -> Self {
        Self {
            correlation,
            action: action.into(),
            action_input: action_input.into(),
            tool_name: tool_name.into(),
        }
    }
}

/// Fired when the agent receives an observation (tool output).
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct ObservationEvent {
    pub correlation: Correlation,
    pub observation: String,
    pub exit_code: i32,
}

impl ObservationEvent {
    pub fn new(correlation: Correlation, observation: impl Into<String>, exit_code: i32) -> Self {
        Self {
            correlation,
            observation: observation.into(),
            exit_code,
        }
    }
}

/// Fired when a verification gate runs.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct VerificationEvent {
    pub correlation: Correlation,
    pub gate: String,
    pub status: String,
    pub detail: String,
}

impl VerificationEvent {
    pub fn new(
        correlation: Correlation,
        gate: impl Into<String>,
        status: impl Into<String>,
        detail: impl Into<String>,
    ) -> Self {
        Self {
            correlation,
            gate: gate.into(),
            status: status.into(),
            detail: detail.into(),
        }
    }
}

/// Fired when a file edit is applied.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FileEditEvent {
    pub correlation: Correlation,
    pub path: String,
    pub diff: String,
    pub action_type: String,
}

impl FileEditEvent {
    pub fn new(
        correlation: Correlation,
        path: impl Into<String>,
        diff: impl Into<String>,
        action_type: impl Into<String>,
    ) -> Self {
        Self {
            correlation,
            path: path.into(),
            diff: diff.into(),
            action_type: action_type.into(),
        }
    }
}

/// Fired when token usage is tracked.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TokenUsageEvent {
    pub correlation: Correlation,
    pub tokens_used: u64,
    pub cost: f64,
    pub total_tokens: u64,
    pub total_cost: f64,
}

impl TokenUsageEvent {
    pub fn new(
        correlation: Correlation,
        tokens_used: u64,
        cost: f64,
        total_tokens: u64,
        total_cost: f64,
    ) -> Self {
        Self {
            correlation,
            tokens_used,
            cost,
            total_tokens,
            total_cost,
        }
    }
}

/// Fired when the agent's internal state is updated.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct StateUpdateEvent {
    pub correlation: Correlation,
    pub key: String,
    pub old_value: String,
    pub new_value: String,
}

impl StateUpdateEvent {
    pub fn new(
        correlation: Correlation,
        key: impl Into<String>,
        old_value: impl Into<String>,
        new_value: impl Into<String>,
    ) -> Self {
        Self {
            correlation,
            key: key.into(),
            old_value: old_value.into(),
            new_value: new_value.into(),
        }
    }
}

/// Fired when the agent makes a decision.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct DecisionEvent {
    pub correlation: Correlation,
    pub decision: String,
    pub confidence: f64,
    pub alternatives: Vec<String>,
}

impl DecisionEvent {
    pub fn new(
        correlation: Correlation,
        decision: impl Into<String>,
        confidence: f64,
        alternatives: Vec<String>,
    ) -> Self {
        Self {
            correlation,
            decision: decision.into(),
            confidence,
            alternatives,
        }
    }
}

/// Fired when the agent converges after a branch.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ConvergenceEvent {
    pub correlation: Correlation,
    pub converged: bool,
    pub evidence: String,
}

impl ConvergenceEvent {
    pub fn new(correlation: Correlation, converged: bool, evidence: impl Into<String>) -> Self {
        Self {
            correlation,
            converged,
            evidence: evidence.into(),
        }
    }
}

/// Fired when a permission gate rules on an action.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct PermissionGateEvent {
    pub correlation: Correlation,
    pub action: String,
    pub verdict: String,
    pub reason: String,
}

impl PermissionGateEvent {
    pub fn new(
        correlation: Correlation,
        action: impl Into<String>,
        verdict: impl Into<String>,
        reason: impl Into<String>,
    ) -> Self {
        Self {
            correlation,
            action: action.into(),
            verdict: verdict.into(),
            reason: reason.into(),
        }
    }
}
