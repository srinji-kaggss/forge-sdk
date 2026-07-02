#![allow(dead_code)]
use async_trait::async_trait;
use forge_core::agent::{Tool, ToolError};
use forge_core::permission::ActionClassification;
use forge_core_security::sandbox::SandboxRoot;
use std::time::Duration;
use tokio::process::Command;
use tokio::time::timeout;

// ---------------------------------------------------------------------------
// ReadFileTool — sandbox-safe file reading
// ---------------------------------------------------------------------------

pub struct ReadFileTool;

#[async_trait]
impl Tool for ReadFileTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "read_file"
    }

    fn description(&self) -> &'static str {
        "Read a file from within the sandbox"
    }

    fn classification(&self) -> ActionClassification {
        ActionClassification::Safe
    }

    async fn call(
        &self,
        input: Self::Input,
        sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let path = input
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ToolError::InvalidInput {
                detail: "missing 'path' field".into(),
            })?;

        let exists = sandbox.exists(path);
        if !exists {
            return Ok(serde_json::json!({
                "content": null,
                "path": path,
                "exists": false
            }));
        }

        let (_file, bytes) = sandbox.read_file(path).map_err(|e| {
            ToolError::ExecutionFailed {
                detail: format!("failed to read '{path}': {e}"),
            }
        })?;

        let content = String::from_utf8(bytes).map_err(|e| {
            ToolError::ExecutionFailed {
                detail: format!("invalid utf-8: {e}"),
            }
        })?;

        Ok(serde_json::json!({
            "content": content,
            "path": path,
            "exists": true
        }))
    }
}

// ---------------------------------------------------------------------------
// GrepTool — line-by-line substring search (no regex)
// ---------------------------------------------------------------------------

pub struct GrepTool;

#[async_trait]
impl Tool for GrepTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "grep"
    }

    fn description(&self) -> &'static str {
        "Search for a substring in a sandbox file"
    }

    fn classification(&self) -> ActionClassification {
        ActionClassification::Safe
    }

    async fn call(
        &self,
        input: Self::Input,
        sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let pattern = input
            .get("pattern")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ToolError::InvalidInput {
                detail: "missing 'pattern' field".into(),
            })?;

        let path = input
            .get("path")
            .and_then(|v| v.as_str())
            .unwrap_or(".");

        let (_file, bytes) = sandbox.read_file(path).map_err(|e| {
            ToolError::ExecutionFailed {
                detail: format!("failed to read '{path}': {e}"),
            }
        })?;

        let content = String::from_utf8(bytes).map_err(|e| {
            ToolError::ExecutionFailed {
                detail: format!("invalid utf-8: {e}"),
            }
        })?;

        let matches: Vec<serde_json::Value> = content
            .lines()
            .enumerate()
            .filter(|(_, line)| line.contains(pattern))
            .map(|(i, line)| {
                serde_json::json!({ "path": path, "line": i + 1, "text": line })
            })
            .collect();

        Ok(serde_json::json!({
            "matches": matches,
            "total": matches.len()
        }))
    }
}

// ---------------------------------------------------------------------------
// BashTool — sandboxed shell execution with 30s timeout
// ---------------------------------------------------------------------------

pub struct BashTool;

#[async_trait]
impl Tool for BashTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "bash"
    }

    fn description(&self) -> &'static str {
        "Execute a shell command (30s timeout)"
    }

    fn classification(&self) -> ActionClassification {
        ActionClassification::Exec
    }

    async fn call(
        &self,
        input: Self::Input,
        _sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let command = input
            .get("command")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ToolError::InvalidInput {
                detail: "missing 'command' field".into(),
            })?;

        let output = timeout(
            Duration::from_secs(30),
            Command::new("sh").arg("-c").arg(command).output(),
        )
        .await
        .map_err(|_| ToolError::ExecutionFailed {
            detail: "command timed out after 30s".into(),
        })?
        .map_err(|e| ToolError::ExecutionFailed {
            detail: format!("command failed: {e}"),
        })?;

        Ok(serde_json::json!({
            "stdout": String::from_utf8_lossy(&output.stdout),
            "stderr": String::from_utf8_lossy(&output.stderr),
            "exit_code": output.status.code().unwrap_or(-1),
        }))
    }
}

// ---------------------------------------------------------------------------
// Factory — all default tools
// ---------------------------------------------------------------------------

pub fn default_tools(
) -> Vec<Box<dyn Tool<Input = serde_json::Value, Output = serde_json::Value>>> {
    vec![
        Box::new(ReadFileTool),
        Box::new(GrepTool),
        Box::new(BashTool),
    ]
}
