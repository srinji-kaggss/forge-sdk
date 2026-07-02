use async_trait::async_trait;
use forge_core::agent::{Tool, ToolError};
use forge_core::permission::ActionClassification;
use forge_core_security::sandbox::SandboxRoot;

pub struct GrepTool;

#[async_trait]
impl Tool for GrepTool {
    type Input = serde_json::Value;
    type Output = serde_json::Value;

    fn name(&self) -> &'static str { "grep" }
    fn description(&self) -> &'static str { "Line-by-line substring search (no regex)" }
    fn classification(&self) -> ActionClassification { ActionClassification::Safe }

    async fn call(&self, input: Self::Input, sandbox: &SandboxRoot) -> Result<Self::Output, ToolError> {
        let path = input.get("path").and_then(|v| v.as_str()).ok_or_else(|| {
            ToolError::InvalidInput { detail: "missing 'path' field".into() }
        })?;
        let query = input.get("query").and_then(|v| v.as_str()).ok_or_else(|| {
            ToolError::InvalidInput { detail: "missing 'query' field".into() }
        })?;
        if !sandbox.exists(path) {
            return Ok(serde_json::json!({"path": path, "exists": false}));
        }
        let (_file, bytes) = sandbox.read_file(path).map_err(|e| {
            ToolError::ExecutionFailed { detail: format!("read '{path}' failed: {e}") }
        })?;
        let content = String::from_utf8_lossy(&bytes);
        let mut results: Vec<serde_json::Value> = Vec::new();
        for (i, line) in content.lines().enumerate() {
            if line.contains(query) {
                results.push(serde_json::json!({"line": i + 1, "content": line}));
            }
        }
        Ok(serde_json::json!({
            "path": path, "query": query, "results": results,
            "total_matches": results.len(), "exists": true
        }))
    }
}
