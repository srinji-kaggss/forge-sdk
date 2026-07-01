use std::path::PathBuf;
use std::sync::Arc;

use async_trait::async_trait;
use serde::de::DeserializeOwned;
use serde::Serialize;

use forge_core_security::containment::Trusted;
use forge_core_security::sandbox::SandboxRoot;

use crate::event::AgentEvent;
use crate::permission::{
    ActionClassification, PermissionGate, PermissionMode,
};
use crate::port::ModelPort;
use crate::result::AgentResult;
use crate::step::AgentStep;
use crate::verifier::VerifierPipeline;

#[derive(Debug, Clone)]
pub enum ToolError {
    PermissionDenied { reason: String },
    ExecutionFailed { detail: String },
    SandboxViolation { detail: String },
    InvalidInput { detail: String },
}

#[async_trait]
pub trait Tool: Send + Sync {
    type Input: DeserializeOwned + Send;
    type Output: Serialize + Send;
    fn name(&self) -> &'static str;
    fn description(&self) -> &'static str;
    fn classification(&self) -> ActionClassification;
    async fn call(&self, input: Self::Input, sandbox: &SandboxRoot) -> Result<Self::Output, ToolError>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LifecycleStage { PreToolUse, PostToolUse, PreModelCall, PostModelCall }

pub enum HookAction {
    Continue,
    Shutdown,
    SkipToolUse { result: serde_json::Value },
}

#[async_trait]
pub trait LifecycleHook: Send + Sync {
    fn name(&self) -> &'static str;
    async fn on_stage(&self, stage: &LifecycleStage, state: &mut AgentState) -> HookAction;
}

pub struct AgentState {
    pub task: Trusted<String>,
    pub sandbox: SandboxRoot,
    pub cwd: PathBuf,
    pub steps: Vec<AgentStep>,
    pub files_read_in_session: Vec<PathBuf>,
    pub permission_mode: PermissionMode,
    pub permission_gate: PermissionGate,
    pub verifier: VerifierPipeline,
    pub model_port: Option<Arc<dyn ModelPort>>,
    pub total_tokens: u64,
    pub total_cost: f64,
    pub max_steps: u32,
    pub max_tokens: Option<u64>,
    pub max_cost: Option<f64>,
}

impl AgentState {
    pub fn should_stop(&self) -> Option<String> {
        if self.steps.len() as u32 >= self.max_steps {
            return Some(format!("Max steps ({}) reached", self.max_steps));
        }
        if let Some(mt) = self.max_tokens {
            if self.total_tokens >= mt { return Some(format!("Max tokens ({}) reached", mt)); }
        }
        if let Some(mc) = self.max_cost {
            if self.total_cost >= mc { return Some(format!("Max cost ({}) reached", mc)); }
        }
        None
    }
}

#[async_trait]
pub trait Agent: Send + Sync {
    async fn run(&mut self, state: &mut AgentState) -> AgentResult;
    async fn run_with_events(&mut self, state: &mut AgentState, event_tx: tokio::sync::mpsc::Sender<AgentEvent>) -> AgentResult;
}

pub struct LifecycleAgent {
    model_port: Arc<dyn ModelPort>,
    tools: Vec<Box<dyn Tool<Input = serde_json::Value, Output = serde_json::Value>>>,
    hooks: Vec<Box<dyn LifecycleHook>>,
}

impl LifecycleAgent {
    pub fn new(
        model_port: Arc<dyn ModelPort>,
        tools: Vec<Box<dyn Tool<Input = serde_json::Value, Output = serde_json::Value>>>,
        hooks: Vec<Box<dyn LifecycleHook>>,
    ) -> Self {
        Self { model_port, tools, hooks }
    }
    fn find_tool(&self, name: &str) -> Option<&dyn Tool<Input = serde_json::Value, Output = serde_json::Value>> {
        self.tools.iter().find(|t| t.name() == name).map(|b| b.as_ref())
    }
}

async fn run_hooks(
    hooks: &[Box<dyn LifecycleHook>],
    stage: &LifecycleStage,
    state: &mut AgentState,
) -> Result<(), String> {
    for hook in hooks {
        match hook.on_stage(stage, state).await {
            HookAction::Shutdown => {
                return Err(format!("Hook '{}' shutdown at {:?}", hook.name(), stage));
            }
            _ => continue,
        }
    }
    Ok(())
}

#[async_trait]
impl Agent for LifecycleAgent {
    async fn run(&mut self, state: &mut AgentState) -> AgentResult {
        loop {
            if let Some(reason) = state.should_stop() {
                return AgentResult::new_premature_shutdown(reason, &state.steps);
            }
            if let Err(reason) = run_hooks(&self.hooks, &LifecycleStage::PreModelCall, state).await {
                return AgentResult::new_premature_shutdown(reason, &state.steps);
            }
            let port: &dyn ModelPort = match state.model_port.as_ref() {
                Some(p) => p.as_ref(),
                None => self.model_port.as_ref(),
            };
            let mut user_msg = std::collections::HashMap::new();
            user_msg.insert("role".to_string(), "user".to_string());
            user_msg.insert("content".to_string(), state.task.as_inner().clone());
            let response = match port.generate("", &vec![user_msg]).await {
                Ok(r) => r,
                Err(e) => return AgentResult::new_premature_shutdown(
                    format!("Model error: {:?}", e), &state.steps,
                ),
            };
            state.total_tokens = state.total_tokens.saturating_add(response.total_tokens());
            state.total_cost += response.input_tokens as f64 * 0.000001
                + response.output_tokens as f64 * 0.000002;
            if let Err(reason) = run_hooks(&self.hooks, &LifecycleStage::PostModelCall, state).await {
                return AgentResult::new_premature_shutdown(reason, &state.steps);
            }
            let tool_calls = response.tool_calls;
            if tool_calls.is_empty() {
                return AgentResult::new_success(&state.steps);
            }
            for tc in &tool_calls {
                let mut skip_result = None;
                for hook in &self.hooks {
                    if let HookAction::SkipToolUse { result } =
                        hook.on_stage(&LifecycleStage::PreToolUse, state).await
                    {
                        skip_result = Some(result);
                    }
                }
                if let Err(reason) = run_hooks(&self.hooks, &LifecycleStage::PreToolUse, state).await {
                    return AgentResult::new_premature_shutdown(reason, &state.steps);
                }
                let ctx = crate::permission::PermissionContext {
                    action_label: format!("tool:{}", tc.name),
                    classification: crate::permission::ActionClassification::Safe,
                    tool_name: tc.name.clone(),
                    tool_args: tc.arguments.clone(),
                    cwd: state.cwd.clone(),
                    sandbox: state.sandbox.clone(),
                    files_read_in_session: state.files_read_in_session.clone(),
                    permission_mode: state.permission_mode.clone(),
                    task: state.task.clone(),
                };
                let _decision = state.permission_gate.evaluate(&ctx).await;
                let obs = if let Some(skip) = skip_result {
                    skip.to_string()
                } else if let Some(tool) = self.find_tool(&tc.name) {
                    let input = serde_json::json!(tc.arguments);
                    match tool.call(input, &state.sandbox).await {
                        Ok(o) => serde_json::to_string(&o).unwrap_or_else(|_| "{}".into()),
                        Err(e) => format!("Tool error: {:?}", e),
                    }
                } else {
                    format!("Unknown tool: {}", tc.name)
                };
                if let Err(reason) = run_hooks(&self.hooks, &LifecycleStage::PostToolUse, state).await {
                    return AgentResult::new_premature_shutdown(reason, &state.steps);
                }
                let step = crate::step::AgentStep::new(
                    state.steps.len() as u32,
                    &response.content,
                    &tc.name,
                    tc.arguments.clone(),
                    obs,
                    None,
                    response.input_tokens + response.output_tokens,
                    (response.input_tokens as f64 * 0.000001
                        + response.output_tokens as f64 * 0.000002),
                    Some(tc.name.clone()),
                    None,
                    false,
                    state.should_stop().is_some(),
                );
                state.steps.push(step);
            }
        }
    }

    async fn run_with_events(
        &mut self,
        state: &mut AgentState,
        event_tx: tokio::sync::mpsc::Sender<AgentEvent>,
    ) -> AgentResult {
        let _ = event_tx.try_send(AgentEvent::RunStart(
            crate::event::RunStartEvent {
                correlation: crate::event::Correlation {
                    trace_id: String::new(),
                    run_id: String::new(),
                    model: String::new(),
                    provider: String::new(),
                    config_version: String::new(),
                },
                task: state.task.as_inner().clone(),
                model: String::new(),
                provider: String::new(),
                max_steps: state.max_steps,
                max_tokens: state.max_tokens.unwrap_or(0),
            }
        ));
        let result = self.run(state).await;
        let _ = event_tx.try_send(AgentEvent::RunEnd(
            crate::event::RunEndEvent {
                correlation: crate::event::Correlation {
                    trace_id: String::new(),
                    run_id: String::new(),
                    model: String::new(),
                    provider: String::new(),
                    config_version: String::new(),
                },
                success: result.success,
                total_steps: result.total_steps,
                total_tokens: result.total_tokens,
                total_cost: result.total_cost,
                duration_ms: 0,
            }
        ));
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tool_error_debug() {
        let e = ToolError::PermissionDenied { reason: "test".into() };
        assert!(format!("{:?}", e).contains("PermissionDenied"));
    }

    #[test]
    fn test_lifecycle_stage_eq() {
        assert_eq!(LifecycleStage::PreToolUse, LifecycleStage::PreToolUse);
        assert_ne!(LifecycleStage::PreToolUse, LifecycleStage::PostToolUse);
    }

    #[test]
    fn test_agent_state_should_stop() {
        let sb = SandboxRoot::new(std::env::current_dir().unwrap()).unwrap();
        let task = Trusted::new_internal("test".into());
        let gate = PermissionGate::new(PermissionMode::Yolo);
        let vp = VerifierPipeline::with_default_gates(None);
        let mut state = AgentState {
            task, sandbox: sb, cwd: PathBuf::from("/tmp"),
            steps: vec![], files_read_in_session: vec![],
            permission_mode: PermissionMode::Yolo, permission_gate: gate,
            verifier: vp, model_port: None, total_tokens: 0, total_cost: 0.0,
            max_steps: 3, max_tokens: None, max_cost: None,
        };
        assert!(state.should_stop().is_none());
        let mut args = std::collections::HashMap::new();
        args.insert("x".into(), serde_json::Value::String("y".into()));
        state.steps.push(AgentStep::new(0, "t", "a", args, "o", None, 0, 0.0, None, None, false, false));
        state.steps.push(AgentStep::new(1, "t", "a", std::collections::HashMap::new(), "o", None, 0, 0.0, None, None, false, false));
        state.steps.push(AgentStep::new(2, "t", "a", std::collections::HashMap::new(), "o", None, 0, 0.0, None, None, false, false));
        assert!(state.should_stop().is_some());
    }
}
