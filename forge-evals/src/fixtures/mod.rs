/// Synthetic repo fixture for deterministic ACI evaluation.
///
/// Creates a temporary directory with:
/// - README.md
/// - Rust source file with a known bug
/// - Failing test
/// - Expected edit
/// - Verification command
use std::path::Path;

/// Create a synthetic repo fixture at the given path.
pub fn create_repo_fixture(path: &Path) -> Result<(), String> {
    let src_dir = path.join("src");
    std::fs::create_dir_all(&src_dir).map_err(|e| format!("Cannot create dir: {e}"))?;

    // README
    std::fs::write(
        path.join("README.md"),
        "# Repo Driving Fixture\n\nTest repo for Forge ACI evaluation.\n",
    )
    .map_err(|e| format!("Cannot write README: {e}"))?;

    // Cargo.toml
    std::fs::write(
        path.join("Cargo.toml"),
        r#"[package]
name = "repo-fixture"
version = "0.1.0"
edition = "2021"

[dependencies]
"#,
    )
    .map_err(|e| format!("Cannot write Cargo.toml: {e}"))?;

    // Rust source with off-by-one bug
    std::fs::write(
        src_dir.join("main.rs"),
        r#"/// Returns the sum of numbers from 1 to n (inclusive).
/// BUG: starts from i32::from(n) instead of iterating.
pub fn sum_to_n(n: u32) -> u32 {
    let mut sum = 0;
    for i in 0..=n {
        sum += i;
    }
    sum
}

fn main() {
    println!("{}", sum_to_n(5));
}
"#,
    )
    .map_err(|e| format!("Cannot write main.rs: {e}"))?;

    // Tests directory
    let tests_dir = path.join("tests");
    std::fs::create_dir_all(&tests_dir).map_err(|e| format!("Cannot create tests dir: {e}"))?;

    // Test that fails (expects sum_to_n to exist)
    std::fs::write(
        tests_dir.join("test_fix.rs"),
        r#"use repo_fixture::sum_to_n;

#[test]
fn test_sum_to_n() {
    assert_eq!(sum_to_n(5), 15);
    assert_eq!(sum_to_n(0), 0);
    assert_eq!(sum_to_n(1), 1);
}
"#,
    )
    .map_err(|e| format!("Cannot write test: {e}"))?;

    // Verification script
    std::fs::write(
        path.join("verify.sh"),
        "#!/bin/sh\ncargo test 2>&1\necho \"Exit: $?\"\n",
    )
    .map_err(|e| format!("Cannot write verify.sh: {e}"))?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_repo_fixture() {
        let dir = std::env::temp_dir().join("_forge_test_fixture");
        let _ = std::fs::remove_dir_all(&dir);
        create_repo_fixture(&dir).unwrap();
        assert!(dir.join("README.md").exists());
        assert!(dir.join("src/main.rs").exists());
        assert!(dir.join("tests/test_fix.rs").exists());
        assert!(dir.join("verify.sh").exists());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
