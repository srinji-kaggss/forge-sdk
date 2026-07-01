use std::collections::HashMap;
use std::path::{Path, PathBuf};
use serde::{Deserialize, Serialize};
/// Ported from src/forge_sdk/cli/session.py::SessionState.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SessionState {
    pub session_id: String,
    pub task: String,
    pub model: String,
    pub step_count: u32,
    pub tool_calls_made: Vec<String>,
    pub files_touched: Vec<String>,
    pub errors: Vec<String>,
    pub token_usage: HashMap<String, serde_json::Value>,
    pub cost_usd: f64,
    pub checkpoint_step: u32,
    pub timestamp: f64,
    pub extra: HashMap<String, serde_json::Value>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionSummary {
    pub session_id: String,
    pub task: String,
    pub steps: u32,
    pub timestamp: f64,
    pub file: PathBuf,
}
#[derive(Debug, Clone)]
pub enum SessionError {
    Io(String),
    Serde(String),
    NotFound(String),
}

impl From<std::io::Error> for SessionError {
    fn from(e: std::io::Error) -> Self {
        SessionError::Io(e.to_string())
    }
}

impl From<serde_json::Error> for SessionError {
    fn from(e: serde_json::Error) -> Self {
        SessionError::Serde(e.to_string())
    }
}
/// Save checkpoint with prune-on-save (keeps at most max_checkpoints).
pub fn checkpoint_save(
    state: &mut SessionState,
    checkpoint_dir: &Path,
    max_checkpoints: usize,
) -> Result<PathBuf, SessionError> {
    state.checkpoint_step = state.step_count;
    state.timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64();
    let file_name = format!("{}.json", state.session_id);
    let file_path = checkpoint_dir.join(&file_name);
    let json = serde_json::to_string_pretty(&state)
        .map_err(|e| SessionError::Serde(e.to_string()))?;
    std::fs::create_dir_all(checkpoint_dir)
        .map_err(|e| SessionError::Io(e.to_string()))?;
    std::fs::write(&file_path, &json)
        .map_err(|e| SessionError::Io(e.to_string()))?;
    // Prune: keep only max_checkpoints most recent
    let mut entries: Vec<_> = std::fs::read_dir(checkpoint_dir)
        .map_err(|e| SessionError::Io(e.to_string()))?
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().map(|x| x == "json").unwrap_or(false))
        .collect();
    entries.sort_by_key(|e| e.path().metadata().and_then(|m| m.modified()).ok());
    while entries.len() > max_checkpoints {
        if let Some(oldest) = entries.first() {
            let _ = std::fs::remove_file(oldest.path());
        }
        entries.remove(0);
    }
    Ok(file_path)
}
/// Restore checkpoint with partial-match glob fallback.
pub fn checkpoint_restore(
    session_id: &str,
    checkpoint_dir: &Path,
) -> Result<Option<SessionState>, SessionError> {
    // Exact match first
    let exact_path = checkpoint_dir.join(format!("{}.json", session_id));
    if exact_path.exists() {
        let data = std::fs::read_to_string(&exact_path)
            .map_err(|e| SessionError::Io(e.to_string()))?;
        let state: SessionState = serde_json::from_str(&data)
            .map_err(|e| SessionError::Serde(e.to_string()))?;
        return Ok(Some(state));
    }
    // Partial-match glob fallback: {session_id}*.json, most recent wins
    let prefix = format!("{}.", session_id);
    let mut candidates: Vec<(std::time::SystemTime, PathBuf)> = Vec::new();
    if let Ok(dir) = std::fs::read_dir(checkpoint_dir) {
        for entry in dir.filter_map(|e| e.ok()) {
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with(&prefix) && name.ends_with(".json") {
                if let Ok(meta) = entry.metadata() {
                    if let Ok(mtime) = meta.modified() {
                        candidates.push((mtime, entry.path()));
                    }
                }
            }
        }
    }
    candidates.sort_by(|a, b| b.0.cmp(&a.0)); // most recent first
    if let Some((_, path)) = candidates.into_iter().next() {
        let data = std::fs::read_to_string(&path)
            .map_err(|e| SessionError::Io(e.to_string()))?;
        let state: SessionState = serde_json::from_str(&data)
            .map_err(|e| SessionError::Serde(e.to_string()))?;
        return Ok(Some(state));
    }
    Ok(None)
}
/// List checkpoints with task truncated to 80 chars.
pub fn list_checkpoints(checkpoint_dir: &Path) -> Vec<SessionSummary> {
    let mut summaries = Vec::new();
    if let Ok(dir) = std::fs::read_dir(checkpoint_dir) {
        for entry in dir.filter_map(|e| e.ok()) {
            let path = entry.path();
            if path.extension().map(|x| x == "json").unwrap_or(false) {
                if let Ok(data) = std::fs::read_to_string(&path) {
                    if let Ok(state) = serde_json::from_str::<SessionState>(&data) {
                        summaries.push(SessionSummary {
                            session_id: state.session_id,
                            task: state.task.chars().take(80).collect(),
                            steps: state.step_count,
                            timestamp: state.timestamp,
                            file: path,
                        });
                    }
                }
            }
        }
    }
    summaries.sort_by(|a, b| b.timestamp.partial_cmp(&a.timestamp).unwrap_or(std::cmp::Ordering::Equal));
    summaries
}
