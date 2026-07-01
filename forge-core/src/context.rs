use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// The execution contract for an agent run.
///
/// Carries all parameters that define the boundaries of an agent execution,
/// including task description, resource limits, environment variables, and
/// identity tracking via trace/run/session IDs.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentContext {
    /// The task description for the agent to execute.
    pub task: String,
    /// The current working directory for file operations.
    pub cwd: String,
    /// Maximum number of steps the agent may take.
    pub max_steps: u32,
    /// Maximum number of tokens the agent may consume.
    pub max_tokens: u64,
    /// Maximum cost in USD the agent may incur.
    pub max_cost: f64,
    /// Trace identifier for observability correlation.
    pub trace_id: String,
    /// Run identifier scoped to a single execution.
    pub run_id: String,
    /// Optional session identifier for multi-run sessions.
    pub session_id: Option<String>,
    /// The model identifier (e.g. "gemini-2.0-flash").
    pub model: String,
    /// The provider identifier (e.g. "gemini", "ollama").
    pub provider: String,
    /// Environment variables available to the agent (keys → values).
    pub env_vars: HashMap<String, String>,
}

impl AgentContext {
    /// Return a new `AgentContext` with all required fields.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        task: impl Into<String>,
        cwd: impl Into<String>,
        max_steps: u32,
        max_tokens: u64,
        max_cost: f64,
        trace_id: impl Into<String>,
        run_id: impl Into<String>,
        session_id: Option<String>,
        model: impl Into<String>,
        provider: impl Into<String>,
        env_vars: HashMap<String, String>,
    ) -> Self {
        Self {
            task: task.into(),
            cwd: cwd.into(),
            max_steps,
            max_tokens,
            max_cost,
            trace_id: trace_id.into(),
            run_id: run_id.into(),
            session_id,
            model: model.into(),
            provider: provider.into(),
            env_vars,
        }
    }

    /// Truncate the task description to at most `max_chars` characters.
    ///
    /// Uses `.chars().take(max_chars)` to respect Unicode grapheme boundaries
    /// rather than byte-slicing with `text[..n]`.
    pub fn char_count_aware_truncation(&mut self, max_chars: usize) {
        let truncated: String = self.task.chars().take(max_chars).collect();
        self.task = truncated;
    }
}
