use std::path::PathBuf;

use clap::{Args, Subcommand};
use forge_core::session::{checkpoint_restore, list_checkpoints};

/// Manage forge sessions
#[derive(Args, Debug, Clone)]
pub struct SessionArgs {
    #[command(subcommand)]
    pub action: SessionAction,
}

#[derive(Subcommand, Debug, Clone)]
pub enum SessionAction {
    /// List all sessions
    List {
        /// Checkpoint directory
        #[arg(long, default_value = ".forge/checkpoints")]
        checkpoint_dir: PathBuf,
    },
    /// Show a specific session
    Show {
        /// Session ID
        #[arg()]
        session_id: String,
        /// Checkpoint directory
        #[arg(long, default_value = ".forge/checkpoints")]
        checkpoint_dir: PathBuf,
    },
    /// Resume a session
    Resume {
        /// Session ID
        #[arg()]
        session_id: String,
        /// Checkpoint directory
        #[arg(long, default_value = ".forge/checkpoints")]
        checkpoint_dir: PathBuf,
    },
}

/// Execute the `forge session` subcommand
pub async fn execute(args: &SessionArgs) -> Result<String, String> {
    match &args.action {
        SessionAction::List { checkpoint_dir } => {
            let summaries = list_checkpoints(checkpoint_dir);
            if summaries.is_empty() {
                return Ok("No sessions found.".to_string());
            }
            let mut output = String::new();
            for s in &summaries {
                output.push_str(&format!(
                    "{} | steps: {} | task: {} | file: {}\n",
                    s.session_id, s.steps, s.task, s.file.display()
                ));
            }
            Ok(output.trim().to_string())
        }
        SessionAction::Show {
            session_id,
            checkpoint_dir,
        } => {
            let state = checkpoint_restore(session_id, checkpoint_dir)
                .map_err(|e| format!("Failed to restore session: {e:?}"))?;
            match state {
                Some(s) => {
                    let json = serde_json::to_string_pretty(&s)
                        .map_err(|e| format!("Serialization error: {e}"))?;
                    Ok(json)
                }
                None => Err(format!("Session '{}' not found", session_id)),
            }
        }
        SessionAction::Resume {
            session_id,
            checkpoint_dir,
        } => {
            let state = checkpoint_restore(session_id, checkpoint_dir)
                .map_err(|e| format!("Failed to restore session: {e:?}"))?;
            match state {
                Some(s) => {
                    let msg = format!(
                        "Session '{}' restored ({} steps). Ready to resume.",
                        s.session_id, s.step_count
                    );
                    Ok(msg)
                }
                None => Err(format!("Session '{}' not found", session_id)),
            }
        }
    }
}
