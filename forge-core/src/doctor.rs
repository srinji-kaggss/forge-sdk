use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::time::SystemTime;

#[async_trait]
pub trait DoctorCheck: Send + Sync {
    fn level(&self) -> u8;
    fn name(&self) -> &str;
    async fn run(&self) -> DoctorResult;
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DoctorResult {
    pub level: u8,
    pub label: String,
    pub status: DoctorStatus,
    pub detail: String,
    pub duration_ms: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum DoctorStatus {
    Pass,
    Fail,
    Warn,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DoctorReport {
    pub checks: Vec<DoctorResult>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscalationRecord {
    pub escalation_level: String,
    pub timestamp_iso: String,
    pub provider: String,
    pub model: String,
    pub reason: String,
    pub prior_checks_passed: u32,
    pub prior_checks_total: u32,
}

pub struct DoctorEngine {
    checks: Vec<Box<dyn DoctorCheck>>,
}

impl DoctorEngine {
    pub fn new() -> Self {
        Self {
            checks: vec![
                Box::new(PythonVersionCheck),
                Box::new(ConfigAndApiKeyCheck),
                Box::new(TraceAndAuditDirCheck),
                Box::new(WorkingDirectoryCheck),
                Box::new(ProviderConnectivityAndModelPingCheck),
            ],
        }
    }

    pub async fn run_all(&self) -> DoctorReport {
        let mut r = Vec::new();
        for c in &self.checks {
            let result = c.run().await;
            r.push(result.clone());
            if result.status == DoctorStatus::Fail {
                break;
            }
        }
        DoctorReport { checks: r }
    }
}

impl Default for DoctorEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug)]
pub struct PythonVersionCheck;
#[async_trait]
impl DoctorCheck for PythonVersionCheck {
    fn level(&self) -> u8 {
        0
    }
    fn name(&self) -> &str {
        "Rust toolchain"
    }
    async fn run(&self) -> DoctorResult {
        let start = SystemTime::now();
        // Phase 0: check that rustc is installed
        let ok = std::process::Command::new("rustc")
            .arg("--version")
            .output()
            .is_ok();
        let ms = start.elapsed().unwrap_or_default().as_secs_f64() * 1000.0;
        if ok {
            DoctorResult {
                level: 0,
                label: "Rust toolchain".into(),
                status: DoctorStatus::Pass,
                detail: "rustc found".into(),
                duration_ms: ms,
            }
        } else {
            DoctorResult {
                level: 0,
                label: "Rust toolchain".into(),
                status: DoctorStatus::Fail,
                detail: "rustc not found on PATH".into(),
                duration_ms: ms,
            }
        }
    }
}

#[derive(Debug)]
pub struct ConfigAndApiKeyCheck;
#[async_trait]
impl DoctorCheck for ConfigAndApiKeyCheck {
    fn level(&self) -> u8 {
        1
    }
    fn name(&self) -> &str {
        "Config + API key"
    }
    async fn run(&self) -> DoctorResult {
        let start = SystemTime::now();
        let forge_dir = dirs_or_placeholder();
        let config_path = std::path::Path::new(&forge_dir).join("config.json");
        let config_ok = config_path.exists();
        let api_key = std::env::var("FORGE_API_KEY").ok();
        let key_ok = api_key.is_some() && !api_key.as_ref().unwrap().is_empty();
        let ms = start.elapsed().unwrap_or_default().as_secs_f64() * 1000.0;
        if config_ok && key_ok {
            DoctorResult {
                level: 1,
                label: "Config + API key".into(),
                status: DoctorStatus::Pass,
                detail: format!("Config: {}, API key: present", config_path.display()),
                duration_ms: ms,
            }
        } else {
            let mut issues = Vec::new();
            if !config_ok {
                issues.push("config missing".to_string());
            }
            if !key_ok {
                issues.push("FORGE_API_KEY not set".to_string());
            }
            DoctorResult {
                level: 1,
                label: "Config + API key".into(),
                status: DoctorStatus::Fail,
                detail: issues.join(", "),
                duration_ms: ms,
            }
        }
    }
}

#[derive(Debug)]
pub struct TraceAndAuditDirCheck;
#[async_trait]
impl DoctorCheck for TraceAndAuditDirCheck {
    fn level(&self) -> u8 {
        2
    }
    fn name(&self) -> &str {
        "Trace + audit dirs"
    }
    async fn run(&self) -> DoctorResult {
        let start = SystemTime::now();
        let forge_dir = format!(
            "{}/.forge",
            std::env::var("HOME").unwrap_or_else(|_| "/tmp".into())
        );
        let trace_dir = std::path::Path::new(&forge_dir).join("traces");
        let audit_dir = std::path::Path::new(&forge_dir).join("audit");
        let trace_writable = std::fs::create_dir_all(&trace_dir).is_ok();
        let audit_writable = std::fs::create_dir_all(&audit_dir).is_ok();
        let ms = start.elapsed().unwrap_or_default().as_secs_f64() * 1000.0;
        if trace_writable && audit_writable {
            DoctorResult {
                level: 2,
                label: "Trace + audit dirs".into(),
                status: DoctorStatus::Pass,
                detail: format!(
                    "trace: {}, audit: {}",
                    trace_dir.display(),
                    audit_dir.display()
                ),
                duration_ms: ms,
            }
        } else {
            DoctorResult {
                level: 2,
                label: "Trace + audit dirs".into(),
                status: DoctorStatus::Fail,
                detail: "Cannot create trace/audit directories".into(),
                duration_ms: ms,
            }
        }
    }
}

#[derive(Debug)]
pub struct WorkingDirectoryCheck;
#[async_trait]
impl DoctorCheck for WorkingDirectoryCheck {
    fn level(&self) -> u8 {
        3
    }
    fn name(&self) -> &str {
        "Working directory"
    }
    async fn run(&self) -> DoctorResult {
        let start = SystemTime::now();
        let cwd = std::env::current_dir();
        let ms = start.elapsed().unwrap_or_default().as_secs_f64() * 1000.0;
        match cwd {
            Ok(dir) if dir.is_dir() => DoctorResult {
                level: 3,
                label: "Working directory".into(),
                status: DoctorStatus::Pass,
                detail: format!("{}", dir.display()),
                duration_ms: ms,
            },
            _ => DoctorResult {
                level: 3,
                label: "Working directory".into(),
                status: DoctorStatus::Fail,
                detail: "Current directory not accessible".into(),
                duration_ms: ms,
            },
        }
    }
}

#[derive(Debug)]
pub struct ProviderConnectivityAndModelPingCheck;
#[async_trait]
impl DoctorCheck for ProviderConnectivityAndModelPingCheck {
    fn level(&self) -> u8 {
        4
    }
    fn name(&self) -> &str {
        "Provider + model ping"
    }
    async fn run(&self) -> DoctorResult {
        let start = SystemTime::now();
        let api_key = std::env::var("FORGE_API_KEY").ok();
        let ms = start.elapsed().unwrap_or_default().as_secs_f64() * 1000.0;
        if api_key.is_none() || api_key.as_ref().unwrap().is_empty() {
            return DoctorResult {
                level: 4,
                label: "Provider + model ping".into(),
                status: DoctorStatus::Warn,
                detail: "No API key configured — skipping model ping".into(),
                duration_ms: ms,
            };
        }
        // Phase 0: just report that key is present. Phase 1+ will make a real API call.
        DoctorResult {
            level: 4,
            label: "Provider + model ping".into(),
            status: DoctorStatus::Pass,
            detail: "API key present (model ping deferred to Phase 1)".into(),
            duration_ms: ms,
        }
    }
}

fn dirs_or_placeholder() -> String {
    format!(
        "{}/.forge",
        std::env::var("HOME").unwrap_or_else(|_| "/tmp".into())
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_python_version_check() {
        let check = PythonVersionCheck;
        let result = check.run().await;
        assert_eq!(result.level, 0);
        assert!(result.duration_ms >= 0.0);
    }

    #[tokio::test]
    async fn test_all_5_checks_run_and_failfast() {
        let engine = DoctorEngine::new();
        let report = engine.run_all().await;
        // Checks run in order L0-L4. First Fail stops the pipeline (fail-fast).
        // L1 (ConfigAndApiKeyCheck) will likely fail in most environments
        // because FORGE_API_KEY is not set, so we get L0 + L1 = 2 results.
        assert!(!report.checks.is_empty());
        assert!(report.checks.len() <= 5);
        // Verify ordering: L0, L1, ...
        for (i, check) in report.checks.iter().enumerate() {
            assert_eq!(check.level as usize, i);
        }
    }

    #[tokio::test]
    async fn test_doctor_status_variants() {
        assert_ne!(DoctorStatus::Pass, DoctorStatus::Fail);
        assert_ne!(DoctorStatus::Pass, DoctorStatus::Warn);
    }

    #[tokio::test]
    async fn test_working_dir_check_passes() {
        let check = WorkingDirectoryCheck;
        let result = check.run().await;
        assert_eq!(result.status, DoctorStatus::Pass);
    }
}
