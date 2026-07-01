use std::env;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::session::SessionError;

// ---------------------------------------------------------------------------
// ForgeConfig — ported from forge_sdk/config/__init__.py
// ---------------------------------------------------------------------------

/// Core configuration for a forge agent session.
///
/// Defaults are: provider = "deepseek", model = "deepseek-chat",
/// temperature = 0.7, max_steps = 50.
///
/// # Environment overrides
///
/// When loading from a file, the following environment variables take
/// precedence over the file values (but **never** clobber from wrong‑provider
/// env vars such as `DEEPSEEK_API_KEY` or `OPENROUTER_API_KEY`):
///
/// | Env var             | Field           |
/// |---------------------|-----------------|
/// | `FORGE_API_KEY`     | `api_key`       |
/// | `FORGE_PROVIDER`    | `provider`      |
/// | `FORGE_MODEL`       | `model`         |
/// | `FORGE_BASE_URL`    | `base_url`      |
/// | `FORGE_TEMPERATURE` | `temperature`   |
/// | `FORGE_MAX_TOKENS`  | `max_tokens`    |
/// | `FORGE_MAX_STEPS`   | `max_steps`     |
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForgeConfig {
    /// LLM provider name.
    #[serde(default = "default_provider")]
    pub provider: String,

    /// Model identifier.
    #[serde(default = "default_model")]
    pub model: String,

    /// API key for the configured provider.
    #[serde(default)]
    pub api_key: String,

    /// Base URL for the provider API.
    #[serde(default = "default_base_url")]
    pub base_url: String,

    /// Sampling temperature (0.0 – 2.0).
    #[serde(default = "default_temperature")]
    pub temperature: f64,

    /// Maximum tokens allowed per response.
    #[serde(default)]
    pub max_tokens: Option<u64>,

    /// Maximum chained execution steps before forced stop.
    #[serde(default = "default_max_steps")]
    pub max_steps: u32,

    /// Working directory for the session.
    #[serde(default = "default_cwd")]
    pub cwd: PathBuf,

    /// Optional evaluation limit.
    #[serde(default)]
    pub eval_limit: Option<u32>,

    /// Evaluation benchmark name.
    #[serde(default = "default_eval_benchmark")]
    pub eval_benchmark: String,

    /// Directory where execution traces are written.
    #[serde(default = "default_trace_dir")]
    pub trace_dir: PathBuf,

    /// Path to the audit database file.
    #[serde(default = "default_audit_db")]
    pub audit_db: PathBuf,

    /// Path to the config file this was loaded from.
    #[serde(skip)]
    pub config_file: Option<PathBuf>,
}

// ---------------------------------------------------------------------------
// Default helpers (module-level functions used by serde default = "...")
// ---------------------------------------------------------------------------

fn default_provider() -> String {
    "deepseek".to_string()
}
fn default_model() -> String {
    "deepseek-chat".to_string()
}
fn default_base_url() -> String {
    String::new()
}
fn default_temperature() -> f64 {
    0.7
}
fn default_max_steps() -> u32 {
    50
}
fn default_cwd() -> PathBuf {
    PathBuf::from(".")
}
fn default_eval_benchmark() -> String {
    "default".to_string()
}
fn default_trace_dir() -> PathBuf {
    PathBuf::from(".forge/traces")
}
fn default_audit_db() -> PathBuf {
    PathBuf::from(".forge/audit.db")
}

impl Default for ForgeConfig {
    fn default() -> Self {
        Self {
            provider: default_provider(),
            model: default_model(),
            api_key: String::new(),
            base_url: default_base_url(),
            temperature: default_temperature(),
            max_tokens: None,
            max_steps: default_max_steps(),
            cwd: default_cwd(),
            eval_limit: None,
            eval_benchmark: default_eval_benchmark(),
            trace_dir: default_trace_dir(),
            audit_db: default_audit_db(),
            config_file: None,
        }
    }
}

impl ForgeConfig {
    /// Return a config initialised with only the hard-coded defaults (no file,
    /// no env overrides).
    pub fn defaults() -> Self {
        Self::default()
    }

    /// Load configuration from an optional JSON file, then overlay
    /// environment overrides (FORGE_* variables only).
    ///
    /// * `config_file` — If `Some(path)`, read that file. If `None`, try
    ///   `~/.forge/config.json`. If neither path exists, return default config
    ///   with env overrides applied.
    pub fn load(config_file: Option<&Path>) -> Result<Self, SessionError> {
        let path = match config_file {
            Some(p) => Some(p.to_path_buf()),
            None => {
                let home = dirs_or_default();
                let p = home.join(".forge").join("config.json");
                if p.exists() { Some(p) } else { None }
            }
        };

        let mut config = match &path {
            Some(p) if p.exists() => {
                let content = std::fs::read_to_string(p)?;
                let mut cfg: Self = serde_json::from_str(&content)?;
                cfg.config_file = Some(p.clone());
                cfg
            }
            _ => Self::defaults(),
        };

        // Apply environment overrides (FORGE_* only).
        if let Ok(val) = env::var("FORGE_API_KEY") {
            config.api_key = val;
        }
        if let Ok(val) = env::var("FORGE_PROVIDER") {
            config.provider = val;
        }
        if let Ok(val) = env::var("FORGE_MODEL") {
            config.model = val;
        }
        if let Ok(val) = env::var("FORGE_BASE_URL") {
            config.base_url = val;
        }
        if let Ok(val) = env::var("FORGE_TEMPERATURE") {
            if let Ok(parsed) = val.parse::<f64>() {
                config.temperature = parsed;
            }
        }
        if let Ok(val) = env::var("FORGE_MAX_TOKENS") {
            if let Ok(parsed) = val.parse::<u64>() {
                config.max_tokens = Some(parsed);
            }
        }
        if let Ok(val) = env::var("FORGE_MAX_STEPS") {
            if let Ok(parsed) = val.parse::<u32>() {
                config.max_steps = parsed;
            }
        }

        Ok(config)
    }

    /// Persist this config as pretty-printed JSON at `path`, creating parent
    /// directories as necessary.
    pub fn save(&self, path: &Path) -> Result<(), SessionError> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let json = serde_json::to_string_pretty(self)?;
        std::fs::write(path, json)?;
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn dirs_or_default() -> PathBuf {
    env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::test_helpers::{EnvGuard, ScratchDir};
    use super::*;
    use std::env;

    #[test]
    fn test_defaults() {
        let cfg = ForgeConfig::defaults();
        assert_eq!(cfg.provider, "deepseek");
        assert_eq!(cfg.model, "deepseek-chat");
        assert_eq!(cfg.api_key, "");
        assert_eq!(cfg.base_url, "");
        assert_eq!(cfg.temperature, 0.7);
        assert_eq!(cfg.max_tokens, None);
        assert_eq!(cfg.max_steps, 50);
        assert_eq!(cfg.cwd, PathBuf::from("."));
        assert_eq!(cfg.eval_limit, None);
        assert_eq!(cfg.eval_benchmark, "default");
        assert_eq!(cfg.trace_dir, PathBuf::from(".forge/traces"));
        assert_eq!(cfg.audit_db, PathBuf::from(".forge/audit.db"));
        assert!(cfg.config_file.is_none());
    }

    #[test]
    fn test_save_and_reload_all_env_patterns() {
        // Combined test to avoid parallel env-var races.
        // Tests: defaults, env-override, no-clobber, save-reload, env-after-save

        let _key_g = EnvGuard::new("FORGE_API_KEY");
        let _prov_g = EnvGuard::new("OPENROUTER_API_KEY");
        let _temp_g = EnvGuard::new("FORGE_TEMPERATURE");

        // -- test: defaults -------------------------------------------------------
        let def = ForgeConfig::defaults();
        assert_eq!(def.provider, "deepseek");
        assert_eq!(def.model, "deepseek-chat");
        assert_eq!(def.api_key, "");
        assert_eq!(def.base_url, "");
        assert!((def.temperature - 0.7).abs() < 1e-9);
        assert_eq!(def.max_tokens, None);
        assert_eq!(def.max_steps, 50);
        assert_eq!(def.cwd, PathBuf::from("."));
        assert_eq!(def.eval_limit, None);
        assert_eq!(def.eval_benchmark, "default");
        assert_eq!(def.trace_dir, PathBuf::from(".forge/traces"));
        assert_eq!(def.audit_db, PathBuf::from(".forge/audit.db"));
        assert!(def.config_file.is_none());

        // -- test: env-override + no-provider-key-clobber -------------------------
        env::set_var("FORGE_API_KEY", "forge-test-key-12345");
        let cfg = ForgeConfig::load(None).unwrap();
        assert_eq!(cfg.api_key, "forge-test-key-12345");

        env::set_var("OPENROUTER_API_KEY", "sk-or-v1-should-not-clobber");
        let cfg2 = ForgeConfig::load(None).unwrap();
        assert_eq!(cfg2.api_key, "forge-test-key-12345",
            "api_key must NOT be overwritten by OPENROUTER_API_KEY");

        // -- test: save and reload ------------------------------------------------
        env::remove_var("FORGE_API_KEY");
        let tmp = ScratchDir::new("forge-config-test");
        let config_path = tmp.path().join("config.json");

        let original = ForgeConfig {
            provider: "openrouter".into(), model: "anthropic/claude-3.5-sonnet".into(),
            api_key: "sk-or-v1-test".into(), base_url: "https://openrouter.ai/api/v1".into(),
            temperature: 0.3, max_tokens: Some(4096), max_steps: 100,
            cwd: PathBuf::from("/tmp/work"), eval_limit: Some(10),
            eval_benchmark: "spec-bench".into(), trace_dir: PathBuf::from("/tmp/traces"),
            audit_db: PathBuf::from("/tmp/audit.db"), config_file: None,
        };
        original.save(&config_path).unwrap();
        assert!(config_path.exists());

        let loaded = ForgeConfig::load(Some(&config_path)).unwrap();
        assert_eq!(loaded.provider, original.provider);
        assert_eq!(loaded.model, original.model);
        assert_eq!(loaded.api_key, original.api_key);
        assert_eq!(loaded.base_url, original.base_url);
        assert_eq!(loaded.temperature, original.temperature);
        assert_eq!(loaded.max_tokens, original.max_tokens);
        assert_eq!(loaded.max_steps, original.max_steps);
        assert_eq!(loaded.cwd, original.cwd);
        assert_eq!(loaded.eval_limit, original.eval_limit);
        assert_eq!(loaded.eval_benchmark, original.eval_benchmark);
        assert_eq!(loaded.trace_dir, original.trace_dir);
        assert_eq!(loaded.audit_db, original.audit_db);
        assert_eq!(loaded.config_file, Some(config_path.clone()));

        // -- test: env override after reload --------------------------------------
        env::set_var("FORGE_TEMPERATURE", "0.1");
        let loaded2 = ForgeConfig::load(Some(&config_path)).unwrap();
        assert!(
            (loaded2.temperature - 0.1).abs() < 1e-9,
            "env FORGE_TEMPERATURE should override file value: got {}",
            loaded2.temperature
        );
    }
}

#[cfg(test)]
mod test_helpers {
    use std::env;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};

    pub(super) struct EnvGuard {
        key: String,
        old: Option<String>,
    }
    impl EnvGuard {
        pub(super) fn new(key: &str) -> Self {
            let old = env::var(key).ok();
            Self { key: key.to_string(), old }
        }
    }
    impl Drop for EnvGuard {
        fn drop(&mut self) {
            match &self.old {
                Some(v) => env::set_var(&self.key, v),
                None => env::remove_var(&self.key),
            }
        }
    }

    /// Minimal std-only stand-in for `tempfile::TempDir`: creates a uniquely
    /// named directory under `std::env::temp_dir()` and removes it on drop.
    pub(super) struct ScratchDir {
        path: PathBuf,
    }
    impl ScratchDir {
        pub(super) fn new(prefix: &str) -> Self {
            static COUNTER: AtomicU64 = AtomicU64::new(0);
            let n = COUNTER.fetch_add(1, Ordering::SeqCst);
            let path = env::temp_dir().join(format!(
                "{prefix}-{}-{n}",
                std::process::id()
            ));
            std::fs::create_dir_all(&path).unwrap();
            Self { path }
        }
        pub(super) fn path(&self) -> &Path {
            &self.path
        }
    }
    impl Drop for ScratchDir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.path);
        }
    }
}

