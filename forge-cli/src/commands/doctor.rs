use clap::Args;
use forge_core::doctor::{DoctorEngine, DoctorReport, DoctorStatus};

/// Run forge diagnostics
#[derive(Args, Debug, Clone)]
pub struct DoctorArgs {
    /// Output as JSON
    #[arg(long)]
    pub json: bool,
}

/// Execute the `forge doctor` subcommand
pub async fn execute(args: &DoctorArgs) -> DoctorReport {
    let engine = DoctorEngine::new();
    let report = engine.run_all().await;
    if !args.json {
        for check in &report.checks {
            let status_str = match check.status {
                DoctorStatus::Pass => "PASS",
                DoctorStatus::Fail => "FAIL",
                DoctorStatus::Warn => "WARN",
            };
            println!(
                "[{:>4}] {}: {} ({:.0}ms)",
                status_str, check.label, check.detail, check.duration_ms
            );
        }
    }
    report
}
