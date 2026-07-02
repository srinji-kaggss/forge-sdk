/// Brain adapter trait — read-only bridge to external memory/index sources.
///
/// Per Playbook 004 (Brain And Topological Payload), forge-brain is a read-only
/// bridge to semantic-memory-brain and the OKF index. It never writes to
/// external indexes.
pub trait BrainAdapter: Send + Sync {
    /// Run a diagnostic health check against the brain backend.
    fn doctor(&self) -> Result<BrainHealth, String>;

    /// Query the brain for evidence relevant to the given query.
    fn query(&self, query: &BrainQuery) -> Result<Vec<BrainEvidence>, String>;
}

/// Brain health report.
#[derive(Debug, Clone, serde::Serialize)]
pub struct BrainHealth {
    pub connected: bool,
    pub entry_count: u64,
    pub backend: String,
    pub schema: String,
    pub details: Vec<String>,
}

/// Query parameters for brain lookup.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BrainQuery {
    pub task: String,
    pub cwd: String,
    pub repo: Option<String>,
    pub domains: Vec<String>,
    pub max_results: usize,
}

impl BrainQuery {
    pub fn new(task: impl Into<String>) -> Self {
        Self {
            task: task.into(),
            cwd: std::env::current_dir()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string(),
            repo: None,
            domains: vec![],
            max_results: 10,
        }
    }
}

/// A piece of evidence returned by a brain query.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BrainEvidence {
    pub source: String,
    pub source_class: String,
    pub trust_level: String,
    pub summary: String,
    pub locator: String,
    pub content_hash: Option<String>,
}
