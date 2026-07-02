use forge_core::agent::Tool;

/// Re-export forge-cli tools when forge-cli is available.
pub fn default_tools() -> Vec<Box<dyn Tool<Input = serde_json::Value, Output = serde_json::Value>>>
{
    // Stub: forge-cli provides the real tool implementations.
    // When used standalone, forge-harness registers no extra tools.
    vec![]
}
