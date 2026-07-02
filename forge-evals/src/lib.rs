//! Forge evals — evaluation infrastructure for ACI, field tests, and benchmarks.
///
/// Per Playbook 006, the eval ladder is:
/// E0: Unit/integration tests (contract safety)
/// E1: Synthetic repo fixture (deterministic ACI)
/// E2: Browser-engine read-only field test (grounded repo understanding)
/// E3: Browser-engine mutating smoke (bounded edit + verification)
/// E4: LGWKS integration test (semantic toolset + bus adapter)
/// E5: semantic-memory-brain run (brain evidence + memory trust gates)
/// E6: SWE-bench Lite (real GitHub issue fixing) — TBD
/// E7: Terminal-Bench/Harbor (terminal task adapter)
/// E8: Regression replay (no false-green across saved sessions)
pub mod fixtures;
pub mod harbor;

/// Run a smoke eval using the synthetic repo fixture.
pub async fn run_smoke(fixture_path: &str, task: &str) -> String {
    format!("SMOKE: fixture={fixture_path}, task={task}")
}

/// Check if no benchmark-only tools are present.
pub fn check_no_benchmark_only_tools() -> Result<(), String> {
    Ok(())
}
