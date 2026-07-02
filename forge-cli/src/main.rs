mod commands;
pub mod render;
pub mod tools;

use std::path::PathBuf;

use clap::{Parser, Subcommand};
use forge_core::result::AgentResult;
use std::process::ExitCode;

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------
#[derive(Parser)]
#[command(name = "forge", about = "Forge agent runtime")]
struct Cli {
    #[command(subcommand)]
    command: ForgeCommand,
}

#[derive(Subcommand)]
enum ForgeCommand {
    /// Run a forge agent task
    Run(commands::run::RunArgs),
    /// Run diagnostic checks
    Doctor(commands::doctor::DoctorArgs),
    /// Manage sessions
    Session(commands::session::SessionArgs),
    /// Inspect the audit log
    Audit(commands::audit::AuditArgs),
    /// Evaluation commands
    Eval(EvalArgs),
}

/// Evaluation subcommand (smoke)
#[derive(clap::Args, Debug, Clone)]
struct EvalArgs {
    #[command(subcommand)]
    action: EvalAction,
}

#[derive(Subcommand, Debug, Clone)]
enum EvalAction {
    /// Run a smoke test
    Smoke {
        /// Working directory
        #[arg(long, default_value = ".")]
        cwd: PathBuf,
        /// Task for the smoke test
        #[arg(long, default_value = "List the files in the current directory")]
        task: String,
        /// Output format
        #[arg(long, default_value = "json")]
        output_format: String,
    },
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
#[tokio::main]
async fn main() -> ExitCode {
    let cli = Cli::parse();

    match cli.command {
        ForgeCommand::Run(args) => {
            let result = commands::run::execute(&args).await;
            emit_result(result)
        }
        ForgeCommand::Doctor(args) => {
            let use_json = args.json;
            let report = commands::doctor::execute(&args).await;
            if use_json {
                match serde_json::to_string_pretty(&report) {
                    Ok(json) => println!("{json}"),
                    Err(err) => {
                        eprintln!("Failed to serialize doctor report: {err}");
                        return ExitCode::from(2);
                    }
                }
            }
            ExitCode::SUCCESS
        }
        ForgeCommand::Session(args) => match commands::session::execute(&args).await {
            Ok(output) => {
                println!("{output}");
                ExitCode::SUCCESS
            }
            Err(err) => {
                eprintln!("Session error: {err}");
                ExitCode::from(1)
            }
        },
        ForgeCommand::Audit(args) => match commands::audit::execute(&args).await {
            Ok(output) => {
                println!("{output}");
                ExitCode::SUCCESS
            }
            Err(err) => {
                eprintln!("Audit error: {err}");
                ExitCode::from(1)
            }
        },
        ForgeCommand::Eval(args) => match args.action {
            EvalAction::Smoke {
                cwd,
                task,
                output_format,
            } => {
                let run_args = commands::run::RunArgs {
                    cwd,
                    task,
                    config: None,
                    permission_mode: "yolo".to_string(),
                    output_format,
                    verify_command: false,
                    no_verify: true,
                    max_steps: Some(3),
                    max_tokens: Some(500),
                    max_cost: Some(0.01),
                    checkpoint_dir: None,
                };
                let result = commands::run::execute(&run_args).await;
                emit_result(result)
            }
        },
    }
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
