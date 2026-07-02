use std::path::PathBuf;

use clap::{Args, Subcommand};
use forge_core::audit::AuditLog;

/// Inspect the forge audit log
#[derive(Args, Debug, Clone)]
pub struct AuditArgs {
    #[command(subcommand)]
    pub action: AuditAction,
}

#[derive(Subcommand, Debug, Clone)]
pub enum AuditAction {
    /// Show the audit log
    Show {
        /// Path to audit log file
        #[arg(long, default_value = ".forge/audit.json")]
        path: PathBuf,
    },
    /// Export the audit log as JSON
    Export {
        /// Path to audit log file
        #[arg(long, default_value = ".forge/audit.json")]
        path: PathBuf,
        /// Output file
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
}

fn event_type_name(event: &forge_core::AgentEvent) -> &'static str {
    use forge_core::AgentEvent::*;
    match event {
        RunStart(_) => "RunStart",
        RunEnd(_) => "RunEnd",
        RunError(_) => "RunError",
        ModelRequest(_) => "ModelRequest",
        ModelResponse(_) => "ModelResponse",
        ToolCall(_) => "ToolCall",
        ToolResult(_) => "ToolResult",
        PermissionRequest(_) => "PermissionRequest",
        PermissionDecision(_) => "PermissionDecision",
        FileEdit(_) => "FileEdit",
        VerifyStart(_) => "VerifyStart",
        VerifyEnd(_) => "VerifyEnd",
        Think(_) => "Think",
        Act(_) => "Act",
        Observe(_) => "Observe",
        Verify(_) => "Verify",
        TokenUsage(_) => "TokenUsage",
        StateUpdate(_) => "StateUpdate",
        Decide(_) => "Decide",
        Converge(_) => "Converge",
        PermissionGate(_) => "PermissionGate",
    }
}

/// Execute the `forge audit` subcommand
pub async fn execute(args: &AuditArgs) -> Result<String, String> {
    match &args.action {
        AuditAction::Show { path } => {
            let content = std::fs::read_to_string(path)
                .map_err(|e| format!("Failed to read audit log at '{}': {e}", path.display()))?;
            let log: AuditLog = serde_json::from_str(&content)
                .map_err(|e| format!("Failed to parse audit log: {e}"))?;
            let chain_valid = log.verify_chain();
            let mut output = format!(
                "Audit log: {} entries, chain valid: {}\n\n",
                log.entries.len(),
                chain_valid
            );
            for entry in &log.entries {
                output.push_str(&format!(
                    "  [{}] {} | {} | prev: {} | hash: {}\n",
                    entry.sequence,
                    event_type_name(&entry.event),
                    entry.stable_id,
                    entry.prev_hash,
                    entry.hash
                ));
            }
            Ok(output.trim().to_string())
        }
        AuditAction::Export { path, output } => {
            let content = std::fs::read_to_string(path)
                .map_err(|e| format!("Failed to read audit log at '{}': {e}", path.display()))?;
            match output {
                Some(out_path) => {
                    std::fs::write(out_path, &content)
                        .map_err(|e| format!("Failed to write export: {e}"))?;
                    Ok(format!("Exported to {}", out_path.display()))
                }
                None => Ok(content.trim().to_string()),
            }
        }
    }
}
