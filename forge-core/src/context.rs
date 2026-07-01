use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// The execution contract for an agent run.
///
/// Carries all parameters that define the boundaries of an agent execution,
/// including task description, resource limits, conversation history, and
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
    /// Conversation history — required for multi-turn agent loops.
    /// Each element is a JSON value representing one message (e.g. {"role": "user", "content": "..."}).
    pub messages: Vec<serde_json::Value>,
    /// Current step counter — incremented each loop iteration.
    /// Used by LoopGuard checks and display ("12/25 steps").
    pub step_count: u32,
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
        messages: Vec<serde_json::Value>,
        step_count: u32,
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
            messages,
            step_count,
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_context_round_trip() {
        let ctx = AgentContext::new(
            "test task",
            "/tmp",
            10,
            1000,
            0.05,
            "trace-1",
            "run-1",
            Some("session-1".into()),
            "gemini-2.0-flash",
            "gemini",
            HashMap::new(),
            vec![],
            0,
        );
        assert_eq!(ctx.task, "test task");
        assert_eq!(ctx.max_steps, 10);
        assert_eq!(ctx.step_count, 0);
        assert!(ctx.messages.is_empty());
    }

    #[test]
    fn test_context_truncation() {
        let mut ctx = AgentContext::new(
            "a".repeat(200),
            "/tmp",
            10,
            1000,
            0.05,
            "trace-1",
            "run-1",
            None,
            "gemini-2.0-flash",
            "gemini",
            HashMap::new(),
            vec![],
            0,
        );
        ctx.char_count_aware_truncation(50);
        assert!(ctx.task.chars().count() <= 50);
    }

    #[test]
    fn test_context_messages() {
        let msg = serde_json::json!({"role": "user", "content": "hello"});
        let ctx = AgentContext::new(
            "test",
            "/tmp",
            10,
            1000,
            0.05,
            "trace-1",
            "run-1",
            None,
            "gemini-2.0-flash",
            "gemini",
            HashMap::new(),
            vec![msg.clone()],
            5,
        );
        assert_eq!(ctx.messages.len(), 1);
        assert_eq!(ctx.step_count, 5);
    }
}
