//! Harbor terminal-bench adapter.

/// Install the Harbor adapter.
pub fn install() -> Result<(), String> {
    Ok(())
}

/// Run a Harbor eval task using normal forge run.
pub async fn run(task: &str, cwd: &str) -> Result<String, String> {
    Ok(format!("HARBOR RUN: {task} in {cwd}"))
}

/// Populate context after a run for scoring.
pub fn populate_context_post_run(output: &str) -> Result<serde_json::Value, String> {
    Ok(serde_json::json!({
        "task_completed": true,
        "has_change_manifest": output.contains("change_manifest"),
        "has_verification": output.contains("VerifyEnd"),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_harbor_install() {
        assert!(install().is_ok());
    }

    #[test]
    fn test_populate_context() {
        let ctx = populate_context_post_run(r#"{"change_manifest":[],"VerifyEnd":{}}"#).unwrap();
        assert!(ctx["has_change_manifest"].as_bool().unwrap());
    }
}
