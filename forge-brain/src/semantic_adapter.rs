/// Read-only semantic-memory-brain adapter.
use crate::payload::{BrainEvidence, BrainQuery};

pub struct SemanticAdapter;

impl SemanticAdapter {
    pub fn doctor(db_path: &str) -> Result<MemoryHealth, String> {
        if !std::path::Path::new(db_path).exists() {
            return Ok(MemoryHealth {
                connected: false,
                db_path: db_path.to_string(),
                entry_count: 0,
                note: "Database not found; brain not initialized".into(),
            });
        }
        Ok(MemoryHealth {
            connected: true,
            db_path: db_path.to_string(),
            entry_count: 0,
            note: "Read-only adapter; rusqlite needed for queries".into(),
        })
    }

    pub fn query(_db_path: &str, _query: &BrainQuery) -> Result<Vec<BrainEvidence>, String> {
        Ok(vec![])
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct MemoryHealth {
    pub connected: bool,
    pub db_path: String,
    pub entry_count: u64,
    pub note: String,
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_doctor_nonexistent() {
        let h = SemanticAdapter::doctor("/nonexistent/brain.db").unwrap();
        assert!(!h.connected);
    }
    #[test]
    fn test_query_empty() {
        let r = SemanticAdapter::query("/tmp/x.db", &BrainQuery::new("test")).unwrap();
        assert!(r.is_empty());
    }
}
