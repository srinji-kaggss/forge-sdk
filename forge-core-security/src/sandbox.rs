use std::io::{self, Read};
use std::path::Path;

use cap_std::ambient_authority;
use cap_std::fs::Dir;

// ---------------------------------------------------------------------------
// SandboxRoot — capability-based filesystem access
// ---------------------------------------------------------------------------
//
// SPEC-SECURITY-003 §3.3. The ONLY filesystem entry point given to tool
// handlers. There is no path-safety FUNCTION to forget to call, because there
// is no other way to open a file.
//
// SandboxRoot wraps cap_std::fs::Dir, which enforces that all paths are
// relative and within the root directory. Absolute paths, symlink escapes,
// and ".." traversals are rejected at the OS level by the capability model.

/// Capability-based filesystem root.
///
/// Wraps `cap_std::fs::Dir` — the Bytecode Alliance's capability-oriented
/// directory handle. `open()` is the ONLY method for accessing files.
/// No absolute paths, no symlink escapes, no path-safety function to forget.
#[derive(Debug)]
pub struct SandboxRoot {
    dir: Dir,
}

impl SandboxRoot {
    /// Open a new sandbox rooted at `path`.
    ///
    /// `path` MUST be a real directory on disk. Returns `io::Error` if the
    /// directory doesn't exist or isn't accessible.
    ///
    /// This is the ONLY way to create a SandboxRoot — once constructed, all
    /// file access is capability-bounded to this directory subtree.
    pub fn new(path: impl AsRef<Path>) -> io::Result<Self> {
        let dir = Dir::open_ambient_dir(path.as_ref(), ambient_authority())?;
        Ok(Self { dir })
    }

    /// Open a file at `relative_path` within the sandbox root.
    ///
    /// `relative_path` MUST be a relative path. Absolute paths, ".."
    /// traversals, and symlink escapes are rejected by the capability model.
    ///
    /// This is the ONLY filesystem entry point for tool handlers.
    pub fn open(&self, relative_path: impl AsRef<Path>) -> io::Result<cap_std::fs::File> {
        self.dir.open(relative_path.as_ref())
    }

    /// Read the entire contents of a file at `relative_path`.
    ///
    /// Convenience wrapper combining `open()` + `read_to_end()`.
    /// Returns `(File, Vec<u8>)` so the caller can inspect the File handle.
    pub fn read_file(&self, relative_path: impl AsRef<Path>) -> io::Result<(cap_std::fs::File, Vec<u8>)> {
        let mut file = self.open(relative_path)?;
        let mut buf = Vec::new();
        file.read_to_end(&mut buf)?;
        Ok((file, buf))
    }

    /// Create a file at `relative_path` within the sandbox root.
    pub fn create(&self, relative_path: impl AsRef<Path>) -> io::Result<cap_std::fs::File> {
        self.dir.create(relative_path.as_ref())
    }

    /// Returns `true` if a file or directory exists at `relative_path`.
    pub fn exists(&self, relative_path: impl AsRef<Path>) -> bool {
        self.dir.open(relative_path.as_ref()).is_ok()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[test]
    fn test_sandbox_open_relative() {
        let cwd = env::current_dir().unwrap();
        let sandbox = SandboxRoot::new(&cwd).unwrap();
        let result = sandbox.open("Cargo.toml");
        assert!(result.is_ok(), "Should open Cargo.toml in current dir");
    }

    #[test]
    fn test_sandbox_open_nonexistent() {
        let cwd = env::current_dir().unwrap();
        let sandbox = SandboxRoot::new(&cwd).unwrap();
        let result = sandbox.open("nonexistent_file_xyz.txt");
        assert!(result.is_err(), "Should fail on nonexistent file");
    }

    #[test]
    fn test_sandbox_create_and_read() {
        let cwd = env::current_dir().unwrap();
        let sandbox = SandboxRoot::new(&cwd).unwrap();
        let test_path = "_test_sandbox_file.tmp";
        let _ = std::fs::remove_file(test_path);
        let mut file = sandbox.create(test_path).unwrap();
        use std::io::Write;
        write!(file, "hello sandbox").unwrap();
        drop(file);
        assert!(sandbox.exists(test_path));
        let (_file, contents) = sandbox.read_file(test_path).unwrap();
        assert_eq!(&contents, b"hello sandbox");
        std::fs::remove_file(test_path).unwrap();
    }

    #[test]
    fn test_sandbox_new_fails_on_nonexistent_dir() {
        let result = SandboxRoot::new("/tmp/nonexistent_dir_xyz_abc_test");
        assert!(result.is_err(), "Should fail on nonexistent root dir");
    }
}
