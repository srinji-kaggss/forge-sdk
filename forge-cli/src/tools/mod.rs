pub mod gated_mutation;
pub mod grep;
pub mod safe_read;

use forge_core::agent::Tool;
use std::path::PathBuf;

pub use gated_mutation::{BashTool, PatchFileTool, RunCommandTool, WriteFileTool};
pub use grep::GrepTool;
pub use safe_read::{
    GlobTool, ListDirTool, OpenFileWindowTool, ReadFileTool, RepoMapTool, SearchRepoTool,
};

/// Build the default set of ACI tools with the given working directory context.
pub fn default_tools(
    _cwd: &PathBuf,
) -> Vec<Box<dyn Tool<Input = serde_json::Value, Output = serde_json::Value>>> {
    vec![
        Box::new(ReadFileTool),
        Box::new(GrepTool),
        Box::new(ListDirTool),
        Box::new(GlobTool),
        Box::new(OpenFileWindowTool),
        Box::new(SearchRepoTool),
        Box::new(RepoMapTool),
        Box::new(WriteFileTool),
        Box::new(PatchFileTool),
        Box::new(RunCommandTool),
        Box::new(BashTool),
    ]
}
