use std::collections::HashMap;

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
    /// Structured input provided to the action (HashMap, not JSON blob).
    /// Restored from String to HashMap per Claude review: TUI inspector
    /// and audit-replay need per-arg access for display and risk classification.
    pub action_input: HashMap<String, serde_json::Value>,
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
    /// Whether this step is the final step in the run.
    pub is_final: bool,
    /// Whether the loop guard triggered on this step (distinguishes normal
    /// finish from a forced stop).
    pub loop_guard_triggered: bool,
}

impl AgentStep {
    /// Create a new `AgentStep`.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        index: u32,
        thought: impl Into<String>,
        action: impl Into<String>,
        action_input: HashMap<String, serde_json::Value>,
        observation: impl Into<String>,
        exit_code: Option<i32>,
        tokens_used: u64,
        cost: f64,
        tool_name: Option<String>,
        event: Option<AgentEvent>,
        is_final: bool,
        loop_guard_triggered: bool,
    ) -> Self {
        Self {
            index,
            thought: thought.into(),
            action: action.into(),
            action_input,
            observation: observation.into(),
            exit_code,
            tokens_used,
            cost,
            tool_name,
            event,
            is_final,
            loop_guard_triggered,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_step_round_trip() {
        let mut args = HashMap::new();
        args.insert(
            "path".into(),
            serde_json::Value::String("src/main.rs".into()),
        );
        args.insert(
            "pattern".into(),
            serde_json::Value::String("fn main".into()),
        );

        let step = AgentStep::new(
            0,
            "I need to find the main function",
            "SearchFile",
            args,
            "Found at line 10",
            Some(0),
            100,
            0.005,
            Some("search".into()),
            None,
            false,
            false,
        );
        assert_eq!(step.index, 0);
        assert!(step.action_input.contains_key("path"));
        assert!(!step.is_final);
    }
}
