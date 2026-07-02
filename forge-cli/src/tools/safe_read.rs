use async_trait::async_trait;
use forge_core::agent::{Tool, ToolError};
use forge_core::permission::ActionClassification;
use forge_core_security::sandbox::SandboxRoot;
use tokio::process::Command;

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
        let path =
            input
                .get("path")
                .and_then(|v| v.as_str())
                .ok_or_else(|| ToolError::InvalidInput {
                    detail: "missing 'path' field".into(),
                })?;
        if !sandbox.exists(path) {
            return Ok(serde_json::json!({"content": null, "path": path, "exists": false}));
        }
        let (_file, bytes) = sandbox
            .read_file(path)
            .map_err(|e| ToolError::ExecutionFailed {
                detail: format!("failed to read '{path}': {e}"),
            })?;
        let content = String::from_utf8(bytes).map_err(|e| ToolError::ExecutionFailed {
            detail: format!("invalid utf-8: {e}"),
        })?;
        let total_lines = content.lines().count();
        Ok(serde_json::json!({
            "content": content, "path": path, "exists": true, "total_lines": total_lines
        }))
    }
}

pub struct ListDirTool;

#[async_trait]
impl Tool for ListDirTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "list_dir"
    }
    fn description(&self) -> &'static str {
        "List files in a directory"
    }
    fn classification(&self) -> ActionClassification {
        ActionClassification::Safe
    }

    async fn call(
        &self,
        input: Self::Input,
        sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let path = input.get("path").and_then(|v| v.as_str()).unwrap_or(".");
        if let Ok(entry) = sandbox.open(path) {
            if let Ok(metadata) = entry.metadata() {
                let entries = vec![serde_json::json!({
                    "name": path,
                    "is_dir": metadata.is_dir(),
                    "is_file": metadata.is_file(),
                    "len": metadata.len()
                })];
                return Ok(serde_json::json!({"path": path, "entries": entries, "exists": true}));
            }
        }
        Ok(serde_json::json!({"path": path, "entries": [], "exists": false}))
    }
}

pub struct GlobTool;

#[async_trait]
impl Tool for GlobTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "glob"
    }
    fn description(&self) -> &'static str {
        "Find files matching a glob pattern"
    }
    fn classification(&self) -> ActionClassification {
        ActionClassification::Safe
    }

    async fn call(
        &self,
        input: Self::Input,
        _sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let pattern = input
            .get("pattern")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ToolError::InvalidInput {
                detail: "missing 'pattern' field".into(),
            })?;
        let max_results = input
            .get("max_results")
            .and_then(|v| v.as_u64())
            .unwrap_or(100) as usize;
        let mut matches: Vec<String> = glob::glob(pattern)
            .map_err(|e| ToolError::ExecutionFailed {
                detail: format!("invalid glob: {e}"),
            })?
            .filter_map(Result::ok)
            .map(|p| p.to_string_lossy().to_string())
            .collect();
        matches.sort();
        if matches.len() > max_results {
            matches.truncate(max_results);
            matches.push("... (narrow your pattern)".into());
        }
        Ok(serde_json::json!({"pattern": pattern, "matches": matches}))
    }
}

pub struct OpenFileWindowTool;

#[async_trait]
impl Tool for OpenFileWindowTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "open_file_window"
    }
    fn description(&self) -> &'static str {
        "Open a file showing a window of lines around a target line"
    }
    fn classification(&self) -> ActionClassification {
        ActionClassification::Safe
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
        let line_num = input.get("line").and_then(|v| v.as_u64()).unwrap_or(1) as usize;
        let window = input.get("window").and_then(|v| v.as_u64()).unwrap_or(20) as usize;
        if !sandbox.exists(path) {
            return Ok(serde_json::json!({"path": path, "exists": false}));
        }
        let (_file, bytes) = sandbox
            .read_file(path)
            .map_err(|e| ToolError::ExecutionFailed {
                detail: format!("cannot read '{path}': {e}"),
            })?;
        let content = String::from_utf8_lossy(&bytes);
        let lines: Vec<&str> = content.lines().collect();
        let total = lines.len();
        let start = if line_num > window {
            line_num - window - 1
        } else {
            0
        };
        let end = std::cmp::min(line_num + window, total);
        let window_lines: Vec<serde_json::Value> = lines[start..end]
            .iter()
            .enumerate()
            .map(|(i, line)| {
                serde_json::json!({
                    "line": start + i + 1,
                    "content": line,
                    "is_target": start + i + 1 == line_num
                })
            })
            .collect();
        Ok(serde_json::json!({
            "path": path, "exists": true, "total_lines": total,
            "window_start": start + 1, "window_end": end, "lines": window_lines
        }))
    }
}

pub struct SearchRepoTool;

#[async_trait]
impl Tool for SearchRepoTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "search_repo"
    }
    fn description(&self) -> &'static str {
        "Search files for a regex pattern using grep"
    }
    fn classification(&self) -> ActionClassification {
        ActionClassification::Exec
    }

    async fn call(
        &self,
        input: Self::Input,
        _sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let pattern = input
            .get("pattern")
            .and_then(|v| v.as_str())
            .ok_or_else(|| ToolError::InvalidInput {
                detail: "missing 'pattern' field".into(),
            })?;
        let max_results = input
            .get("max_results")
            .and_then(|v| v.as_u64())
            .unwrap_or(20) as usize;
        let root_dir = input.get("root").and_then(|v| v.as_str()).unwrap_or(".");

        // Block shell metacharacters to prevent injection
        if pattern.contains('$')
            || pattern.contains('`')
            || pattern.contains(';')
            || pattern.contains('|')
        {
            return Err(ToolError::InvalidInput {
                detail: "pattern contains shell metacharacters".into(),
            });
        }

        // NOTE: grep runs outside sandbox (cap_std Dir has no subprocess support).
        // Security relies on: (1) shell metacharacter blocking, (2) -- separator,
        // (3) grep reads only within root_dir.
        let output = Command::new("grep")
            .args([
                "-rn",
                "--include=*.rs",
                "--include=*.md",
                "--include=*.toml",
                "-m",
                &max_results.to_string(),
                "-e",
                pattern,
                "--",
                root_dir,
            ])
            .output()
            .await
            .map_err(|e| ToolError::ExecutionFailed {
                detail: format!("grep failed: {e}"),
            })?;

        let stdout = String::from_utf8_lossy(&output.stdout);
        let results: Vec<&str> = stdout.lines().collect();
        let truncated = results.len() > max_results;
        let shown: Vec<String> = results
            .iter()
            .take(max_results)
            .map(|s| (*s).to_string())
            .collect();
        Ok(serde_json::json!({
            "pattern": pattern, "results": shown,
            "total_matches": results.len(), "truncated": truncated
        }))
    }
}

pub struct RepoMapTool;

#[async_trait]
impl Tool for RepoMapTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str {
        "repo_map"
    }
    fn description(&self) -> &'static str {
        "Generate a tree view of the repository structure"
    }
    fn classification(&self) -> ActionClassification {
        ActionClassification::Exec
    }

    async fn call(
        &self,
        _input: Self::Input,
        _sandbox: &SandboxRoot,
    ) -> Result<Self::Output, ToolError> {
        let output = std::process::Command::new("tree")
            .args(["-L", "3", "--dirsfirst", "-I", ".git|target"])
            .output()
            .map_err(|e| ToolError::ExecutionFailed {
                detail: format!("tree failed: {e}"),
            })?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        Ok(serde_json::json!({"tree": stdout.to_string()}))
    }
}
