use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::event::{AgentEvent, Correlation};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub stable_id: String,
    pub correlation: Correlation,
    pub sequence: u64,
    pub event: AgentEvent,
    pub prev_hash: String,
    pub hash: String,
    pub timestamp_iso: String,
}

impl AuditEntry {
    pub fn compute_hash(&self) -> String {
        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.stable_id.hash(&mut hasher);
        self.sequence.hash(&mut hasher);
        self.correlation.trace_id.hash(&mut hasher);
        self.correlation.run_id.hash(&mut hasher);
        self.prev_hash.hash(&mut hasher);
        self.timestamp_iso.hash(&mut hasher);
        format!("{:016x}", hasher.finish())
    }
}

fn extract_correlation(event: &AgentEvent) -> Correlation {
    match event {
        AgentEvent::RunStart(e) => e.correlation.clone(),
        AgentEvent::RunEnd(e) => e.correlation.clone(),
        AgentEvent::RunError(e) => e.correlation.clone(),
        AgentEvent::Think(e) => e.correlation.clone(),
        AgentEvent::Act(e) => e.correlation.clone(),
        AgentEvent::Observe(e) => e.correlation.clone(),
        AgentEvent::Verify(e) => e.correlation.clone(),
        AgentEvent::FileEdit(e) => e.correlation.clone(),
        AgentEvent::TokenUsage(e) => e.correlation.clone(),
        AgentEvent::StateUpdate(e) => e.correlation.clone(),
        AgentEvent::Decide(e) => e.correlation.clone(),
        AgentEvent::Converge(e) => e.correlation.clone(),
        AgentEvent::PermissionGate(e) => e.correlation.clone(),
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLog {
    pub entries: Vec<AuditEntry>,
    pub path: Option<PathBuf>,
    pub tip_hash: Option<String>,
}

impl AuditLog {
    pub fn new() -> Self {
        Self {
            entries: vec![],
            path: None,
            tip_hash: None,
        }
    }

    pub fn append(&mut self, event: AgentEvent) -> &AuditEntry {
        let prev_hash = self.tip_hash.clone().unwrap_or_default();
        let sequence = self.entries.len() as u64;
        let correlation = extract_correlation(&event);
        let mut entry = AuditEntry {
            stable_id: format!("audit-{:04}", sequence),
            correlation,
            sequence,
            event,
            prev_hash,
            hash: String::new(),
            timestamp_iso: iso_now(),
        };
        entry.hash = entry.compute_hash();
        self.tip_hash = Some(entry.hash.clone());
        self.entries.push(entry);
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> bool {
        let mut expected_prev = String::new();
        for entry in &self.entries {
            if entry.hash != entry.compute_hash() {
                return false;
            }
            if entry.prev_hash != expected_prev {
                return false;
            }
            expected_prev = entry.hash.clone();
        }
        true
    }
}

impl Default for AuditLog {
    fn default() -> Self {
        Self::new()
    }
}

pub trait EventSink: Send + Sync {
    fn sink(&mut self, event: AgentEvent) -> AuditEntry;
}

impl EventSink for AuditLog {
    fn sink(&mut self, event: AgentEvent) -> AuditEntry {
        self.append(event).clone()
    }
}

fn iso_now() -> String {
    let d = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = d.as_secs();
    let days = secs / 86400;
    let t = secs % 86400;
    let h = t / 3600;
    let m = (t % 3600) / 60;
    let s = t % 60;
    let (y, mo, da) = days_to_date(days);
    format!("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z", y, mo, da, h, m, s)
}

fn days_to_date(mut days: u64) -> (u64, u64, u64) {
    let mut y = 1970u64;
    loop {
        let diy = if is_leap(y) { 366 } else { 365 };
        if days < diy {
            break;
        }
        days -= diy;
        y += 1;
    }
    let mdays = if is_leap(y) {
        [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    } else {
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    };
    let mut mo = 1u64;
    for &md in &mdays {
        if days < md {
            break;
        }
        days -= md;
        mo += 1;
    }
    (y, mo, days + 1)
}

fn is_leap(y: u64) -> bool {
    (y.is_multiple_of(4) && !y.is_multiple_of(100)) || y.is_multiple_of(400)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::event::{ActionEvent, ObservationEvent};

    #[test]
    fn test_audit_log_append() {
        let mut log = AuditLog::new();
        let entry = log.append(AgentEvent::Act(ActionEvent::default()));
        assert_eq!(entry.sequence, 0);
        assert_eq!(entry.stable_id, "audit-0000");
        assert_eq!(entry.prev_hash, "");
        assert!(!entry.hash.is_empty());
    }

    #[test]
    fn test_chain_integrity() {
        let mut log = AuditLog::new();
        log.append(AgentEvent::Act(ActionEvent::default()));
        log.append(AgentEvent::Observe(ObservationEvent::default()));
        assert!(log.verify_chain());
        assert_eq!(log.entries.len(), 2);
    }

    #[test]
    fn test_tamper_detected() {
        let mut log = AuditLog::new();
        log.append(AgentEvent::Act(ActionEvent::default()));
        log.append(AgentEvent::Observe(ObservationEvent::default()));
        log.entries[1].sequence = 999;
        assert!(!log.verify_chain());
    }

    #[test]
    fn test_event_sink_trait() {
        let mut log: Box<dyn EventSink> = Box::new(AuditLog::new());
        let entry = log.sink(AgentEvent::Act(ActionEvent::default()));
        assert_eq!(entry.sequence, 0);
    }

    #[test]
    fn test_empty_log_verify() {
        let log = AuditLog::new();
        assert!(log.verify_chain());
    }
}
