use forge_core::permission::{PermissionGate, PermissionMode};
use forge_core::config::ForgeConfig;

pub struct HarnessBuilder {
    permission_mode: PermissionMode,
    config: Option<ForgeConfig>,
}

impl HarnessBuilder {
    pub fn new() -> Self {
        Self { permission_mode: PermissionMode::Yolo, config: None }
    }
    pub fn with_permission_mode(mut self, mode: PermissionMode) -> Self {
        self.permission_mode = mode;
        self
    }
    pub fn with_config(mut self, config: ForgeConfig) -> Self {
        self.config = Some(config);
        self
    }
    pub fn build(self) -> Result<AssembledHarness, BuildError> {
        let config = self.config.unwrap_or_default();
        let pm = self.permission_mode.clone();
        let gate = PermissionGate::new(pm.clone());
        Ok(AssembledHarness { gate, config, permission_mode: pm })
    }
}

impl Default for HarnessBuilder { fn default() -> Self { Self::new() } }

pub struct AssembledHarness {
    pub gate: PermissionGate,
    pub config: ForgeConfig,
    pub permission_mode: PermissionMode,
}

#[derive(Debug, thiserror::Error)]
pub enum BuildError {
    #[error("Config error: {0}")]
    Config(String),
}
