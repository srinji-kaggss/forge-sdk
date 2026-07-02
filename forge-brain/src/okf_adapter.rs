//! Read-only OKF index adapter.
use crate::payload::{BrainEvidence, BrainQuery};

pub struct OkfIndexAdapter {
    db_path: String,
}

impl OkfIndexAdapter {
    pub fn open(path: &str) -> Result<Self, String> {
        if !std::path::Path::new(path).exists() {
            return Err(format!("OKF database not found: {path}"));
        }
        Ok(Self {
            db_path: path.to_string(),
        })
    }

    pub fn doctor(&self) -> Result<IndexHealth, String> {
        Ok(IndexHealth {
            connected: false,
            schema: "unified.agent.brain.index.v2".into(),
            entry_count: 0,
            table_list: vec![
                "rag_unified".into(),
                "rag_metadata".into(),
                "index_metadata".into(),
            ],
            note: "DEGRADED: rusqlite backend not wired. All queries return NotImplemented. Install rusqlite and wire schema: unified.agent.brain.index.v2".into(),
        })
    }

    pub fn query(&self, _query: &BrainQuery) -> Result<Vec<BrainEvidence>, String> {
        Err("NotImplemented: OKF index queries require rusqlite backend. Schema: unified.agent.brain.index.v2".into())
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct IndexHealth {
    pub connected: bool,
    pub schema: String,
    pub entry_count: u64,
    pub table_list: Vec<String>,
    pub note: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_okf_adapter_open_missing() {
        assert!(OkfIndexAdapter::open("/nonexistent/db").is_err());
    }
    #[test]
    fn test_okf_doctor_reports_degraded() {
        let a = OkfIndexAdapter::open("/tmp").unwrap();
        let health = a.doctor().unwrap();
        assert!(!health.connected, "Should report not connected without rusqlite");
        assert_eq!(health.schema, "unified.agent.brain.index.v2");
        assert!(health.note.contains("DEGRADED"), "Note should indicate degraded state");
    }

    #[test]
    fn test_okf_query_returns_not_implemented() {
        let a = OkfIndexAdapter::open("/tmp").unwrap();
        let q = crate::BrainQuery { task: "test".into(), cwd: ".".into(), repo: None, domains: vec![], max_results: 10 };
        let result = a.query(&q);
        assert!(result.is_err(), "Query should fail without rusqlite");
        assert!(result.unwrap_err().contains("NotImplemented"), "Error should say NotImplemented");
    }
}
