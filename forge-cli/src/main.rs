mod tools;

use std::path::PathBuf;
use std::sync::Arc;

use clap::{Parser, Subcommand};
use forge_core::agent::{Agent, AgentState, LifecycleAgent};
use forge_core::config::ForgeConfig;
use forge_core::doctor::DoctorEngine;
use forge_core::event::AgentEvent;
use forge_core::permission::{PermissionGate, PermissionMode};
use forge_core::port::ModelPort;
use forge_core::result::{AgentResult, FailureReason};
use forge_core::session::{checkpoint_restore, list_checkpoints};
use forge_core::verifier::VerifierPipeline;
use forge_core_security::containment::Trusted;
use forge_core_security::sandbox::SandboxRoot;
use forge_providers::deepseek::DeepSeekProvider;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "forge", version)]
struct Cli {
    #[command(subcommand)]
    command: ForgeCommand,
}

#[derive(Subcommand)]
enum ForgeCommand {
    Run {
        #[arg(long)]
        task: String,
        #[arg(long)]
        config: Option<PathBuf>,
        #[arg(long)]
        cwd: Option<PathBuf>,
        #[arg(long, default_value = "yolo")]
        permission_mode: String,
        #[arg(long, default_value = "json")]
        output_format: String,
        #[arg(long)]
        max_steps: Option<u32>,
        #[arg(long)]
        max_tokens: Option<u64>,
    },
    Doctor {
        #[arg(long)]
        json: bool,
        #[arg(long)]
        config: Option<PathBuf>,
    },
    Session {
        #[command(subcommand)]
        action: SessionAction,
    },
}

#[derive(Subcommand)]
enum SessionAction {
    List {
        #[arg(long)]
        dir: Option<PathBuf>,
    },
    Show {
        session_id: String,
        #[arg(long)]
        dir: Option<PathBuf>,
    },
    Resume {
        session_id: String,
        #[arg(long)]
        dir: Option<PathBuf>,
    },
}

#[tokio::main]
async fn main() -> ExitCode {
    let cli = Cli::parse();
    match cli.command {
        ForgeCommand::Run { task, config, cwd, permission_mode, output_format, max_steps, max_tokens } =>
            cmd_run(task, config, cwd, &permission_mode, &output_format, max_steps, max_tokens).await,
        ForgeCommand::Doctor { json, config } => cmd_doctor(json, config).await,
        ForgeCommand::Session { action } => cmd_session(action),
    }
}

async fn cmd_run(
    task: String, config_path: Option<PathBuf>, cwd: Option<PathBuf>,
    permission_mode: &str, output_format: &str,
    max_steps: Option<u32>, max_tokens: Option<u64>,
) -> ExitCode {
    let mut config = match ForgeConfig::load(config_path.as_deref()) {
        Ok(c) => c,
        Err(e) => return emit_result(config_failure(format!("Failed to load config: {e:?}"))),
    };
    if let Some(c) = cwd { config.cwd = c; }
    if let Some(ms) = max_steps { config.max_steps = ms; }
    if let Some(mt) = max_tokens { config.max_tokens = Some(mt); }
    let mode = match permission_mode.to_lowercase().as_str() {
        "interactive" => PermissionMode::Interactive,
        "plan" => PermissionMode::Plan,
        _ => PermissionMode::Yolo,
    };
    let sandbox = match SandboxRoot::new(&config.cwd) {
        Ok(s) => s,
        Err(e) => return emit_result(config_failure(format!("Sandbox at '{}': {e:?}", config.cwd.display()))),
    };
    let mut state = AgentState {
        task: Trusted::new_internal(task),
        sandbox, cwd: config.cwd.clone(),
        steps: vec![], files_read_in_session: vec![],
        permission_mode: mode.clone(),
        permission_gate: PermissionGate::new(mode),
        verifier: VerifierPipeline::with_default_gates(None),
        model_port: None,
        total_tokens: 0, total_cost: 0.0,
        max_steps: config.max_steps,
        max_tokens: config.max_tokens,
        max_cost: None,
    };
    let provider = match DeepSeekProvider::from_config(&config) {
        Ok(p) => Arc::new(p),
        Err(e) => return emit_result(provider_failure(&config, e)),
    };
    let mut agent = LifecycleAgent::new(provider as Arc<dyn ModelPort>, tools::default_tools(), vec![]);
    if output_format == "stream-json" {
        let (tx, mut rx) = tokio::sync::mpsc::channel::<AgentEvent>(100);
        let handle = tokio::spawn(async move {
            while let Some(event) = rx.recv().await {
                if let Ok(line) = serde_json::to_string(&event) {
                    println!("{line}");
                }
            }
        });
        let result = agent.run_with_events(&mut state, tx).await;
        handle.await.ok();
        emit_result(result)
    } else {
        let (tx, mut rx) = tokio::sync::mpsc::channel::<AgentEvent>(100);
        tokio::spawn(async move { while rx.recv().await.is_some() {} });
        let result = agent.run_with_events(&mut state, tx).await;
        emit_result(result)
    }
}

async fn cmd_doctor(json: bool, config_path: Option<PathBuf>) -> ExitCode {
    let _config = match ForgeConfig::load(config_path.as_deref()) {
        Ok(c) => c,
        Err(e) => { eprintln!("Config: {e:?}"); return ExitCode::from(2); }
    };
    let engine = DoctorEngine::new();
    let report = engine.run_all().await;
    if json {
        match serde_json::to_string_pretty(&report) {
            Ok(j) => println!("{j}"),
            Err(e) => { eprintln!("Doctor serialize: {e}"); return ExitCode::from(2); }
        }
    } else {
        println!("=== Forge Doctor Report ===");
        for c in &report.checks {
            let sc = match c.status {
                forge_core::doctor::DoctorStatus::Pass => "\u{2705}",
                forge_core::doctor::DoctorStatus::Fail => "\u{274C}",
                forge_core::doctor::DoctorStatus::Warn => "\u{26A0}\u{FE0F}",
            };
            println!("  {sc} [L{}] {}: {} ({:.0}ms)", c.level, c.label, c.detail, c.duration_ms);
        }
    }
    ExitCode::SUCCESS
}

fn cmd_session(action: SessionAction) -> ExitCode {
    let default_dir = dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".forge").join("checkpoints");
    match action {
        SessionAction::List { dir } => {
            let dir = dir.unwrap_or(default_dir);
            let summaries = list_checkpoints(&dir);
            if summaries.is_empty() {
                println!("No sessions in {}", dir.display());
            } else {
                for s in &summaries {
                    println!("{} | steps={} | {}", s.session_id, s.steps, s.task);
                }
            }
        }
        SessionAction::Show { session_id, dir } => {
            let dir = dir.unwrap_or(default_dir);
            match checkpoint_restore(&session_id, &dir) {
                Ok(Some(state)) => {
                    if let Ok(j) = serde_json::to_string_pretty(&state) { println!("{j}"); }
                }
                Ok(None) => eprintln!("Session '{session_id}' not found in {}", dir.display()),
                Err(e) => eprintln!("Error: {e:?}"),
            }
        }
        SessionAction::Resume { session_id, dir: _ } => {
            eprintln!("Resume not yet implemented for '{session_id}'");
            return ExitCode::from(1);
        }
    }
    ExitCode::SUCCESS
}

fn emit_result(result: AgentResult) -> ExitCode {
    match serde_json::to_string_pretty(&result) {
        Ok(j) => println!("{j}"),
        Err(e) => { eprintln!("Serialize: {e}"); return ExitCode::from(2); }
    }
    if result.success { ExitCode::SUCCESS } else { ExitCode::from(1) }
}

fn config_failure(output: String) -> AgentResult {
    AgentResult {
        success: false, output: output.clone(),
        steps: vec![], total_steps: 0, total_tokens: 0, total_cost: 0.0, duration_ms: 0,
        trace_id: String::new(), run_id: String::new(),
        model: String::new(), provider: String::new(),
        edits_made: vec![], named_targets_missing: vec![],
        failure_reason: Some(FailureReason::ModelError(output)),
        verification: vec![], change_manifest: None, rollback_plan: None,
    }
}

fn provider_failure(config: &ForgeConfig, err: forge_core::port::ModelError) -> AgentResult {
    let fr = match &err {
        forge_core::port::ModelError::Authentication(d) => FailureReason::AuthenticationFailure {
            provider: config.provider.clone(), detail: d.clone(),
        },
        _ => FailureReason::ModelError(format!("{err:?}")),
    };
    AgentResult {
        success: false, output: fr.causal_sentence(),
        steps: vec![], total_steps: 0, total_tokens: 0, total_cost: 0.0, duration_ms: 0,
        trace_id: String::new(), run_id: String::new(),
        model: config.model.clone(), provider: config.provider.clone(),
        edits_made: vec![], named_targets_missing: vec![],
        failure_reason: Some(fr),
        verification: vec![], change_manifest: None, rollback_plan: None,
    }
}
