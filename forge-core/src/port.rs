use std::collections::HashMap;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use thiserror::Error;

// ---------------------------------------------------------------------------
// ModelError -- 6 variant error enum
// ---------------------------------------------------------------------------

/// Errors that can arise when interacting with a model provider.
#[derive(Debug, Clone, PartialEq, Eq, Error, Serialize, Deserialize)]
pub enum ModelError {
    /// The provider returned an authentication error.
    #[error("Authentication failed with provider: {0}")]
    Authentication(String),
    /// The provider returned a rate-limit or quota error.
    #[error("Rate limit exceeded: {0}")]
    RateLimit(String),
    /// The request timed out.
    #[error("Request timed out: {0}")]
    Timeout(String),
    /// The provider returned an internal server error.
    #[error("Provider error: {0}")]
    Provider(String),
    /// An invalid request was sent (e.g. malformed parameters).
    #[error("Invalid request: {0}")]
    InvalidRequest(String),
    /// A catch-all for unexpected or unknown errors.
    #[error("Unknown error: {0}")]
    Unknown(String),
}

// ---------------------------------------------------------------------------
// ToolSpec / ToolCall / ToolResult
// ---------------------------------------------------------------------------

/// Describes a tool that the model may invoke.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub parameters: serde_json::Value,
}

impl ToolSpec {
    pub fn new(name: impl Into<String>, description: impl Into<String>, parameters: serde_json::Value) -> Self {
        Self { name: name.into(), description: description.into(), parameters }
    }
}

/// A tool invocation issued by the model.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub name: String,
    pub arguments: HashMap<String, serde_json::Value>,
    pub id: Option<String>,
}

impl ToolCall {
    pub fn new(name: impl Into<String>, arguments: HashMap<String, serde_json::Value>, id: Option<String>) -> Self {
        Self { name: name.into(), arguments, id }
    }
}

/// The result of executing a tool call.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub call_id: Option<String>,
    pub success: bool,
    pub output: String,
}

impl ToolResult {
    pub fn new(call_id: Option<String>, success: bool, output: impl Into<String>) -> Self {
        Self { call_id, success, output: output.into() }
    }
}

// ---------------------------------------------------------------------------
// ModelResponse
// ---------------------------------------------------------------------------

/// The response from a model after a generation request.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelResponse {
    pub content: String,
    pub tool_calls: Vec<ToolCall>,
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub model: String,
}

impl ModelResponse {
    pub fn new(content: impl Into<String>, tool_calls: Vec<ToolCall>, input_tokens: u64, output_tokens: u64, model: impl Into<String>) -> Self {
        Self { content: content.into(), tool_calls, input_tokens, output_tokens, model: model.into() }
    }

    /// Total tokens consumed for this response.
    pub fn total_tokens(&self) -> u64 { self.input_tokens + self.output_tokens }
}

// ---------------------------------------------------------------------------
// ModelPort trait
// ---------------------------------------------------------------------------

/// The port (trait) that all model providers must implement.
///
/// This is the sole interface through which forge-core communicates with
/// language models. Providers such as forge-gemini, forge-ollama, etc.
/// implement this trait.
#[async_trait]
pub trait ModelPort: Send + Sync {
    async fn generate(&self, system: &str, messages: &[HashMap<String, String>]) -> Result<ModelResponse, ModelError>;
    async fn generate_with_tools(&self, system: &str, messages: &[HashMap<String, String>], tools: &[ToolSpec]) -> Result<ModelResponse, ModelError>;
    async fn count_tokens(&self, text: &str) -> Result<u64, ModelError>;
}

// ---------------------------------------------------------------------------
// ToolHandler trait
// ---------------------------------------------------------------------------

/// A handler that can execute tool calls and return results.
#[async_trait]
pub trait ToolHandler: Send + Sync {
    async fn execute(&self, call: &ToolCall) -> ToolResult;
}
