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
pub enum LifecycleStage {
    PreToolUse,
    PostToolUse,
    PreModelCall,
    PostModelCall,
}

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
        if let Some(max_tokens) = self.max_tokens {
            if self.total_tokens >= max_tokens {
                return Some(format!("Max tokens ({}) reached", max_tokens));
            }
        }
        if let Some(max_cost) = self.max_cost {
            if self.total_cost >= max_cost {
                return Some(format!("Max cost ({}) reached", max_cost));
            }
        }
        None
    }
}

#[async_trait]
pub trait Agent: Send + Sync {
    async fn run(&mut self, state: &mut AgentState) -> AgentResult;
    async fn run_with_events(
        &mut self,
        state: &mut AgentState,
        event_tx: tokio::sync::mpsc::Sender<AgentEvent>,
    ) -> AgentResult;
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

#[async_trait]
impl Agent for LifecycleAgent {
    async fn run(&mut self, state: &mut AgentState) -> AgentResult {
        let _ = self; // placeholder
        AgentResult::new_success(&state.steps)
    }

    async fn run_with_events(
        &mut self,
        state: &mut AgentState,
        _event_tx: tokio::sync::mpsc::Sender<AgentEvent>,
    ) -> AgentResult {
        self.run(state).await
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use forge_core_security::sandbox::SandboxRoot;

    #[test]
    fn test_tool_error_debug() {
        let e = ToolError::PermissionDenied { reason: "test".into() };
        assert!(format!("{:?}", e).contains("PermissionDenied"));
    }

    #[test]
    fn test_lifecycle_stage_equality() {
        assert_eq!(LifecycleStage::PreToolUse, LifecycleStage::PreToolUse);
        assert_ne!(LifecycleStage::PreToolUse, LifecycleStage::PostToolUse);
    }

    #[test]
    fn test_hook_action_types() {
        match HookAction::Continue {
            HookAction::Continue => {}
            _ => panic!("wrong variant"),
        }
    }
}
