mod tools;


use std::path::PathBuf;
use std::sync::Arc;

use clap::Parser;
use forge_core::agent::{Agent, AgentState, LifecycleAgent};
use forge_core::config::ForgeConfig;
use forge_core::event::AgentEvent;
use forge_core::permission::{PermissionGate, PermissionMode};
use forge_core::port::ModelPort;
use forge_core::result::{AgentResult, FailureReason};
use forge_core::verifier::VerifierPipeline;
use forge_core_security::containment::Trusted;
use forge_core_security::sandbox::SandboxRoot;
use forge_providers::deepseek::DeepSeekProvider;
use std::process::ExitCode;

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
// Entry point
// ---------------------------------------------------------------------------
#[tokio::main]
async fn main() -> ExitCode {
    let cli = Cli::parse();

    // Load config — uses defaults / env overrides when no file given
    let config = match ForgeConfig::load(cli.config.as_deref()) {
        Ok(config) => config,
        Err(err) => {
            return emit_result(config_failure(format!("Failed to load config: {err:?}")));
        }
    };

    // Sandbox rooted at the config's working directory
    let sandbox = match SandboxRoot::new(&config.cwd) {
        Ok(sandbox) => sandbox,
        Err(err) => {
            return emit_result(config_failure(format!(
                "Failed to create sandbox at '{}': {err:?}",
                config.cwd.display()
            )));
        }
    };

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

    let provider = match DeepSeekProvider::from_config(&config) {
        Ok(provider) => Arc::new(provider),
        Err(err) => return emit_result(provider_failure(&config, err)),
    };
    let mut agent = LifecycleAgent::new(
        provider as Arc<dyn ModelPort>,
        tools::default_tools(),
        vec![],
    );

    let (tx, mut rx) = tokio::sync::mpsc::channel::<AgentEvent>(100);

    // Drain events in background so the event sender never stalls
    tokio::spawn(async move { while rx.recv().await.is_some() {} });

    let result = agent.run_with_events(&mut state, tx).await;

    emit_result(result)
}

fn emit_result(result: AgentResult) -> ExitCode {
    match serde_json::to_string_pretty(&result) {
        Ok(json) => println!("{json}"),
        Err(err) => {
            eprintln!("Failed to serialize AgentResult: {err}");
            return ExitCode::from(2);
        }
    }
    if result.success {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

fn config_failure(output: String) -> AgentResult {
    AgentResult {
        success: false,
        output: output.clone(),
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
        failure_reason: Some(FailureReason::ModelError(output)),
        verification: vec![],
        change_manifest: None,
        rollback_plan: None,
    }
}

fn provider_failure(config: &ForgeConfig, err: forge_core::port::ModelError) -> AgentResult {
    let failure_reason = match &err {
        forge_core::port::ModelError::Authentication(detail) => {
            FailureReason::AuthenticationFailure {
                provider: config.provider.clone(),
                detail: detail.clone(),
            }
        }
        _ => FailureReason::ModelError(format!("{err:?}")),
    };
    AgentResult {
        success: false,
        output: failure_reason.causal_sentence(),
        steps: vec![],
        total_steps: 0,
        total_tokens: 0,
        total_cost: 0.0,
        duration_ms: 0,
        trace_id: String::new(),
        run_id: String::new(),
        model: config.model.clone(),
        provider: config.provider.clone(),
        edits_made: vec![],
        named_targets_missing: vec![],
        failure_reason: Some(failure_reason),
        verification: vec![],
        change_manifest: None,
        rollback_plan: None,
    }
}
