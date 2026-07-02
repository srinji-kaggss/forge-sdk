use async_trait::async_trait;
use forge_core::agent::{Tool, ToolError};
use forge_core::permission::ActionClassification;
use forge_core_security::sandbox::SandboxRoot;
use std::path::{Component, Path, PathBuf};
use std::time::Duration;
use tokio::process::Command;
use tokio::time::timeout;

fn sandbox_relative_path(path: &str) -> Result<&Path, ToolError> {
    let path = Path::new(path);
    if path.is_absolute()
        || path
            .components()
            .any(|c| matches!(c, Component::ParentDir | Component::Prefix(_)))
    {
        return Err(ToolError::SandboxViolation {
            detail: format!("path must stay within sandbox: {}", path.display()),
        });
    }
    Ok(path)
}

fn sandbox_host_path(sandbox: &SandboxRoot, path: &Path) -> Result<PathBuf, ToolError> {
    let joined = sandbox.root_path().join(path);
    if !joined.starts_with(sandbox.root_path()) {
        return Err(ToolError::SandboxViolation {
            detail: format!("path escaped sandbox: {}", path.display()),
        });
    }
    Ok(joined)
}

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
        sandbox: &SandboxRoot,
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
        let target_path = sandbox_relative_path(path)?;
        let patch_path = PathBuf::from(format!("{}.patch", path));
        let patch_path =
            sandbox_relative_path(patch_path.to_str().ok_or_else(|| ToolError::InvalidInput {
                detail: "patch path is not valid UTF-8".into(),
            })?)?;
        let patch_host_path = sandbox_host_path(sandbox, patch_path)?;
        std::fs::write(&patch_host_path, patch).map_err(|e| ToolError::ExecutionFailed {
            detail: format!("write patch: {e}"),
        })?;
        let out = Command::new("patch")
            .current_dir(sandbox.root_path())
            .arg(target_path)
            .arg("-i")
            .arg(patch_path)
            .output()
            .await;
        let _ = std::fs::remove_file(&patch_host_path);
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

#[cfg(test)]
mod tests {
    use super::*;

    fn sandbox() -> SandboxRoot {
        let dir = std::env::temp_dir().join(format!(
            "forge_cli_gated_mutation_test_{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        SandboxRoot::new(&dir).unwrap()
    }

    #[tokio::test]
    async fn patch_file_rejects_parent_traversal() {
        let tool = PatchFileTool;
        let input = serde_json::json!({
            "path": "../outside.txt",
            "patch": ""
        });
        let err = tool.call(input, &sandbox()).await.unwrap_err();
        assert!(matches!(err, ToolError::SandboxViolation { .. }));
    }
}
