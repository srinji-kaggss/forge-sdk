use std::path::PathBuf;
use std::sync::Arc;

use clap::Args;
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

use crate::render::OutputFormat;
use crate::tools;

/// Run a forge agent task
#[derive(Args, Debug, Clone)]
pub struct RunArgs {
    /// Working directory (default: current dir)
    #[arg(long, default_value = ".")]
    pub cwd: PathBuf,

    /// Task description text
    #[arg(long)]
    pub task: String,

    /// Path to config file (defaults to standard locations)
    #[arg(long)]
    pub config: Option<PathBuf>,

    /// Permission mode: interactive, yolo, or plan
    #[arg(long, default_value = "interactive")]
    pub permission_mode: String,

    /// Output format: text, json, or stream-json
    #[arg(long, default_value = "json")]
    pub output_format: String,

    /// Verify command before execution
    #[arg(long)]
    pub verify_command: bool,

    /// Skip verification
    #[arg(long)]
    pub no_verify: bool,

    /// Maximum steps before forced stop
    #[arg(long)]
    pub max_steps: Option<u32>,

    /// Maximum tokens per response
    #[arg(long)]
    pub max_tokens: Option<u64>,

    /// Maximum cost ceiling (USD)
    #[arg(long)]
    pub max_cost: Option<f64>,

    /// Directory for session checkpoints
    #[arg(long)]
    pub checkpoint_dir: Option<PathBuf>,
}

/// Execute the `forge run` subcommand
pub async fn execute(args: &RunArgs) -> AgentResult {
    let start = std::time::Instant::now();

    // Resolve cwd
    let cwd = if args.cwd.as_os_str().is_empty() {
        std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
    } else {
        args.cwd.clone()
    };
    let canonical_cwd = std::fs::canonicalize(&cwd).unwrap_or(cwd);

    // Load config
    let config = match ForgeConfig::load(args.config.as_deref()) {
        Ok(config) => config,
        Err(err) => {
            return AgentResult {
                success: false,
                output: format!("Failed to load config: {err:?}"),
                steps: vec![],
                total_steps: 0,
                total_tokens: 0,
                total_cost: 0.0,
                duration_ms: start.elapsed().as_millis() as u64,
                trace_id: String::new(),
                run_id: String::new(),
                model: String::new(),
                provider: String::new(),
                edits_made: vec![],
                named_targets_missing: vec![],
                failure_reason: Some(FailureReason::ModelError(format!(
                    "Failed to load config: {err:?}"
                ))),
                verification: vec![],
                change_manifest: None,
                rollback_plan: None,
            };
        }
    };

    // Sandbox rooted at cwd
    let sandbox = match SandboxRoot::new(&canonical_cwd) {
        Ok(sandbox) => sandbox,
        Err(err) => {
            return AgentResult {
                success: false,
                output: format!(
                    "Failed to create sandbox at '{}': {err:?}",
                    canonical_cwd.display()
                ),
                steps: vec![],
                total_steps: 0,
                total_tokens: 0,
                total_cost: 0.0,
                duration_ms: start.elapsed().as_millis() as u64,
                trace_id: String::new(),
                run_id: String::new(),
                model: config.model.clone(),
                provider: config.provider.clone(),
                edits_made: vec![],
                named_targets_missing: vec![],
                failure_reason: Some(FailureReason::ModelError(format!(
                    "Failed to create sandbox at '{}': {err:?}",
                    canonical_cwd.display()
                ))),
                verification: vec![],
                change_manifest: None,
                rollback_plan: None,
            };
        }
    };

    // Parse permission mode
    let permission_mode = match args.permission_mode.as_str() {
        "interactive" => PermissionMode::Interactive,
        "yolo" => PermissionMode::Yolo,
        "plan" => PermissionMode::Plan,
        other => {
            return AgentResult {
                success: false,
                output: format!(
                    "Invalid permission mode: '{other}'. Use: interactive, yolo, or plan"
                ),
                steps: vec![],
                total_steps: 0,
                total_tokens: 0,
                total_cost: 0.0,
                duration_ms: start.elapsed().as_millis() as u64,
                trace_id: String::new(),
                run_id: String::new(),
                model: config.model.clone(),
                provider: config.provider.clone(),
                edits_made: vec![],
                named_targets_missing: vec![],
                failure_reason: Some(FailureReason::ModelError(format!(
                    "Invalid permission mode: '{other}'"
                ))),
                verification: vec![],
                change_manifest: None,
                rollback_plan: None,
            };
        }
    };

    // Build verifier pipeline
    let verifier = VerifierPipeline::with_default_gates(None);

    let max_steps = args.max_steps.unwrap_or(config.max_steps);
    let max_tokens = args.max_tokens.or(config.max_tokens);

    // Build agent state
    let mut state = AgentState {
        task: Trusted::new_internal(args.task.clone()),
        sandbox,
        cwd: canonical_cwd.clone(),
        steps: vec![],
        files_read_in_session: vec![],
        permission_mode: permission_mode.clone(),
        permission_gate: PermissionGate::new(permission_mode),
        verifier,
        model_port: None,
        total_tokens: 0,
        total_cost: 0.0,
        max_steps,
        max_tokens,
        max_cost: args.max_cost,
    };

    // Create provider
    let provider = match DeepSeekProvider::from_config(&config) {
        Ok(provider) => Arc::new(provider) as Arc<dyn ModelPort>,
        Err(err) => {
            return AgentResult {
                success: false,
                output: format!("Failed to initialize provider: {err:?}"),
                steps: vec![],
                total_steps: 0,
                total_tokens: 0,
                total_cost: 0.0,
                duration_ms: start.elapsed().as_millis() as u64,
                trace_id: String::new(),
                run_id: String::new(),
                model: config.model.clone(),
                provider: config.provider.clone(),
                edits_made: vec![],
                named_targets_missing: vec![],
                failure_reason: Some(FailureReason::ModelError(format!(
                    "Failed to initialize provider: {err:?}"
                ))),
                verification: vec![],
                change_manifest: None,
                rollback_plan: None,
            };
        }
    };

    // Build tools with cwd context
    let tools_list = tools::default_tools(&canonical_cwd);

    let mut agent = LifecycleAgent::new(provider, tools_list, vec![]);

    let (tx, mut rx) = tokio::sync::mpsc::channel::<AgentEvent>(100);

    // Spawn event drainer or streamer
    let output_fmt: OutputFormat = args.output_format.parse().unwrap_or(OutputFormat::Json);
    tokio::spawn(async move {
        if output_fmt == OutputFormat::StreamJson {
            while let Some(event) = rx.recv().await {
                if let Ok(line) = serde_json::to_string(&event) {
                    println!("{line}");
                }
            }
        } else {
            while rx.recv().await.is_some() {}
        }
    });

    let result = agent.run_with_events(&mut state, tx).await;

    // Run honest success classification before finalizing result
    let mut final_result = result;
    if final_result.success {
        agent.classify_result(&state, &mut final_result);
    }

    // If --checkpoint-dir, save session checkpoint
    if let Some(cp_dir) = &args.checkpoint_dir {
        let _ = std::fs::create_dir_all(cp_dir);
        let checkpoint_path = cp_dir.join("session_checkpoint.json");
        if let Ok(json) = serde_json::to_string_pretty(&final_result) {
            let _ = std::fs::write(&checkpoint_path, &json);
        }
    }

    final_result
}
