use serde::{Deserialize, Serialize};

use crate::event::AgentEvent;

/// A single step in an agent execution trace.
///
/// Captures the full think-act-observe cycle along with cost accounting
/// and an optional canonical event representation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentStep {
    /// Zero-indexed step number within the run.
    pub index: u32,
    /// The agent's reasoning / thought for this step.
    pub thought: String,
    /// The action (tool name or high-level action description).
    pub action: String,
    /// The input provided to the action.
    pub action_input: String,
    /// The observation returned after performing the action.
    pub observation: String,
    /// Optional exit code from a command execution.
    pub exit_code: Option<i32>,
    /// Number of tokens consumed during this step.
    pub tokens_used: u64,
    /// Cost incurred during this step.
    pub cost: f64,
    /// Name of the tool invoked (if any).
    pub tool_name: Option<String>,
    /// Canonical event representation of this step, if materialized.
    pub event: Option<AgentEvent>,
}

impl AgentStep {
    /// Create a new `AgentStep`.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        index: u32,
        thought: impl Into<String>,
        action: impl Into<String>,
        action_input: impl Into<String>,
        observation: impl Into<String>,
        exit_code: Option<i32>,
        tokens_used: u64,
        cost: f64,
        tool_name: Option<String>,
        event: Option<AgentEvent>,
    ) -> Self {
        Self {
            index,
            thought: thought.into(),
            action: action.into(),
            action_input: action_input.into(),
            observation: observation.into(),
            exit_code,
            tokens_used,
            cost,
            tool_name,
            event,
        }
    }
}
