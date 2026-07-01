use std::path::PathBuf;
use std::sync::Arc;

use clap::Parser;
use forge_core::agent::{Agent, AgentState, LifecycleAgent};
use forge_core::config::ForgeConfig;
use forge_core::event::AgentEvent;
use forge_core::permission::{PermissionGate, PermissionMode};
use forge_core::port::{ModelError, ModelPort, ModelResponse, ToolSpec};
use forge_core::verifier::VerifierPipeline;
use forge_core_security::containment::Trusted;
use forge_core_security::sandbox::SandboxRoot;

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------
#[derive(Parser)]
struct Cli {
    /// Path to config file (defaults to standard locations)
    #[arg(long)]
    config: Option<PathBuf>,

    /// Task description text
    #[arg(long)]
    task: String,
}

// ---------------------------------------------------------------------------
// Mock model port — returns an empty response so the agent loop terminates
// immediately without actually calling any LLM provider.
// ---------------------------------------------------------------------------
struct MockModelPort;

#[async_trait::async_trait]
impl ModelPort for MockModelPort {
    async fn generate(
        &self,
        _system: &str,
        _messages: &[std::collections::HashMap<String, String>],
    ) -> Result<ModelResponse, ModelError> {
        Ok(ModelResponse::new("", vec![], 0, 0, "mock"))
    }

    async fn generate_with_tools(
        &self,
        _system: &str,
        _messages: &[std::collections::HashMap<String, String>],
        _tools: &[ToolSpec],
    ) -> Result<ModelResponse, ModelError> {
        Ok(ModelResponse::new("", vec![], 0, 0, "mock"))
    }

    async fn count_tokens(&self, _text: &str) -> Result<u64, ModelError> {
        Ok(0)
    }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    // Load config — uses defaults / env overrides when no file given
    let config = ForgeConfig::load(cli.config.as_deref()).expect("Failed to load config");

    // Sandbox rooted at the config's working directory
    let sandbox = SandboxRoot::new(&config.cwd).expect("Failed to create sandbox");

    let mut state = AgentState {
        task: Trusted::new_internal(cli.task),
        sandbox,
        cwd: config.cwd.clone(),
        steps: vec![],
        files_read_in_session: vec![],
        permission_mode: PermissionMode::Yolo,
        permission_gate: PermissionGate::new(PermissionMode::Yolo),
        verifier: VerifierPipeline::with_default_gates(None),
        model_port: None,
        total_tokens: 0,
        total_cost: 0.0,
        max_steps: config.max_steps,
        max_tokens: config.max_tokens,
        max_cost: None,
    };

    let model_port: Arc<dyn ModelPort> = Arc::new(MockModelPort);
    let mut agent = LifecycleAgent::new(model_port, vec![], vec![]);

    let (tx, mut rx) = tokio::sync::mpsc::channel::<AgentEvent>(100);

    // Drain events in background so the event sender never stalls
    tokio::spawn(async move {
        while rx.recv().await.is_some() {}
    });

    let result = agent.run_with_events(&mut state, tx).await;

    println!(
        "{}",
        serde_json::to_string_pretty(&result).expect("Failed to serialize result")
    );
}
