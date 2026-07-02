use async_trait::async_trait;
use forge_core::agent::{Tool, ToolError};
use forge_core::permission::ActionClassification;
use forge_core_security::sandbox::SandboxRoot;
use std::time::Duration;
use tokio::process::Command;
use tokio::time::timeout;

pub struct WriteFileTool;

#[async_trait]
impl Tool for WriteFileTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "write_file"
    }
    fn description(&self) -> &'static str {
        "Write content to a file"
    }
    fn classification(&self) -> ActionClassification {
        ActionClassification::LocalWrite
    }

    async fn call(
        &self,
        input: Self::Input,
        sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let path =
            input
                .get("path")
                .and_then(|v| v.as_str())
                .ok_or_else(|| ToolError::InvalidInput {
                    detail: "missing 'path' field".into(),
                })?;
        let content = input
            .get("content")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ToolError::InvalidInput {
                detail: "missing 'content' field".into(),
            })?;
        let mut file = sandbox
            .create(path)
            .map_err(|e| ToolError::ExecutionFailed {
                detail: format!("cannot create '{path}': {e}"),
            })?;
        use std::io::Write;
        file.write_all(content.as_bytes())
            .map_err(|e| ToolError::ExecutionFailed {
                detail: format!("cannot write '{path}': {e}"),
            })?;
        Ok(serde_json::json!({"path": path, "bytes_written": content.len()}))
    }
}

pub struct PatchFileTool;

#[async_trait]
impl Tool for PatchFileTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "patch_file"
    }
    fn description(&self) -> &'static str {
        "Apply a unified diff patch to a file"
    }
    fn classification(&self) -> ActionClassification {
        ActionClassification::LocalWrite
    }

    async fn call(
        &self,
        input: Self::Input,
        _sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let path =
            input
                .get("path")
                .and_then(|v| v.as_str())
                .ok_or_else(|| ToolError::InvalidInput {
                    detail: "missing 'path' field".into(),
                })?;
        let patch =
            input
                .get("patch")
                .and_then(|v| v.as_str())
                .ok_or_else(|| ToolError::InvalidInput {
                    detail: "missing 'patch' field".into(),
                })?;
        let patch_path = format!("{}.patch", path);
        std::fs::write(&patch_path, patch).map_err(|e| ToolError::ExecutionFailed {
            detail: format!("write patch: {e}"),
        })?;
        let out = std::process::Command::new("patch")
            .arg(path)
            .arg("-i")
            .arg(&patch_path)
            .output();
        let _ = std::fs::remove_file(&patch_path);
        match out {
            Ok(output) if output.status.success() => {
                Ok(serde_json::json!({"path": path, "applied": true}))
            }
            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr);
                Err(ToolError::ExecutionFailed {
                    detail: format!("patch failed: {stderr}"),
                })
            }
            Err(e) => Err(ToolError::ExecutionFailed {
                detail: format!("patch cmd: {e}"),
            }),
        }
    }
}

pub struct RunCommandTool;

#[async_trait]
impl Tool for RunCommandTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "run_command"
    }
    fn description(&self) -> &'static str {
        "Run a shell command"
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
        let timeout_secs = input.get("timeout").and_then(|v| v.as_u64()).unwrap_or(30);
        let parts: Vec<&str> = command.split_whitespace().collect();
        if parts.is_empty() {
            return Err(ToolError::InvalidInput {
                detail: "empty command".into(),
            });
        }
        let result = timeout(
            Duration::from_secs(timeout_secs),
            Command::new(parts[0]).args(&parts[1..]).output(),
        )
        .await;
        match result {
            Ok(Ok(output)) => {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let stderr = String::from_utf8_lossy(&output.stderr);
                Ok(serde_json::json!({
                    "exit_code": output.status.code(),
                    "stdout": stdout,
                    "stderr": stderr,
                    "success": output.status.success()
                }))
            }
            Ok(Err(e)) => Err(ToolError::ExecutionFailed {
                detail: format!("cmd failed: {e}"),
            }),
            Err(_) => Err(ToolError::ExecutionFailed {
                detail: "command timed out".into(),
            }),
        }
    }
}

pub struct BashTool;

#[async_trait]
impl Tool for BashTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "bash"
    }
    fn description(&self) -> &'static str {
        "Run a bash shell command"
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
        let timeout_secs = input.get("timeout").and_then(|v| v.as_u64()).unwrap_or(30);
        let result = timeout(
            Duration::from_secs(timeout_secs),
            Command::new("bash").arg("-c").arg(command).output(),
        )
        .await;
        match result {
            Ok(Ok(output)) => {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let stderr = String::from_utf8_lossy(&output.stderr);
                Ok(serde_json::json!({
                    "exit_code": output.status.code(),
                    "stdout": stdout,
                    "stderr": stderr,
                    "success": output.status.success()
                }))
            }
            Ok(Err(e)) => Err(ToolError::ExecutionFailed {
                detail: format!("bash failed: {e}"),
            }),
            Err(_) => Err(ToolError::ExecutionFailed {
                detail: "bash timed out".into(),
            }),
        }
    }
}
