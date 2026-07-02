pub mod gated_mutation;
pub mod safe_read;
pub mod grep;

use std::path::PathBuf;
use forge_core::agent::Tool;

pub use safe_read::{ReadFileTool, ListDirTool, GlobTool, OpenFileWindowTool, SearchRepoTool, RepoMapTool};
pub use gated_mutation::{PatchFileTool, WriteFileTool, RunCommandTool, BashTool};
pub use grep::GrepTool;

/// Build the default set of ACI tools with the given working directory context.
pub fn default_tools(_cwd: &PathBuf) -> Vec<Box<dyn Tool<Input = serde_json::Value, Output = serde_json::Value>>> {
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

