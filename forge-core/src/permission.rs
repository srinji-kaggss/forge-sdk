use std::collections::HashMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// ActionClassification — 10-class action taxonomy
// ---------------------------------------------------------------------------

/// The 10-class action taxonomy.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum ActionClassification {
    Safe,
    LocalWrite,
    Destructive,
    NetworkOut,
    NetworkIn,
    Exec,
    GitHistory,
    Auth,
    Config,
    Install,
}

// ---------------------------------------------------------------------------
// PermissionContext — the full context for a permission decision
// ---------------------------------------------------------------------------

/// All available context for making a permission decision.
///
/// Not Clone: `SandboxRoot` is intentionally non-Clone for capability security.
/// Each consumer must own its own SandboxRoot or share via `Arc`.
#[derive(Debug)]
pub struct PermissionContext {
    pub action_label: String,
    pub classification: ActionClassification,
    pub tool_name: String,
    pub tool_args: HashMap<String, serde_json::Value>,
    pub cwd: PathBuf,
    pub sandbox: forge_core_security::sandbox::SandboxRoot,
    pub files_read_in_session: Vec<PathBuf>,
    pub permission_mode: PermissionMode,
    pub task: forge_core_security::containment::Trusted<String>,
}

// ---------------------------------------------------------------------------
// PermissionMode — session-level posture
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum PermissionMode {
    Interactive,
    Plan,
    Yolo,
}

// ---------------------------------------------------------------------------
// DenyReason — closed enum for machine-readable denial cause
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum DenyReason {
    HardDenyRule { rule_id: String },
    NoReadEvidence,
    TestDeletionWithoutReplacement,
    OutsideSandbox,
    QuarantinedContent,
    NeedsExplicitIntent { classification: ActionClassification },
    UsageLimitExceeded,
}

// ---------------------------------------------------------------------------
// PolicyTier — governs whether Yolo mode can override a rule
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum PolicyTier {
    HardDeny,
    SoftDeny,
    Allow,
    Environment,
}

// ---------------------------------------------------------------------------
// PermissionDecision — exactly 2 variants
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PermissionDecision {
    Allow { updated_input: Option<serde_json::Value> },
    Deny { reason: DenyReason, interrupt: bool },
}

// ---------------------------------------------------------------------------
// PermissionStrategy — trait for anti-slop checks
// ---------------------------------------------------------------------------

#[async_trait::async_trait]
pub trait PermissionStrategy: Send + Sync + std::fmt::Debug {
    fn name(&self) -> &str;
    async fn check(&self, ctx: &PermissionContext) -> Option<DenyReason>;
}


// ---------------------------------------------------------------------------
// PermissionGate — the main permission decision engine
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub struct PermissionGate {
    mode: PermissionMode,
    anti_slop_strategies: Vec<Box<dyn PermissionStrategy>>,
    policy: HashMap<ActionClassification, PolicyTier>,
    history: Vec<PermissionGateEvent>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionGateEvent {
    pub action_label: String,
    pub classification: ActionClassification,
    pub decision: PermissionDecision,
    pub timestamp_iso: String,
}

impl PermissionGate {
    pub fn new(mode: PermissionMode) -> Self {
        let mut policy = HashMap::new();
        policy.insert(ActionClassification::Destructive, PolicyTier::HardDeny);
        policy.insert(ActionClassification::NetworkIn, PolicyTier::HardDeny);
        policy.insert(ActionClassification::Auth, PolicyTier::SoftDeny);
        policy.insert(ActionClassification::Exec, PolicyTier::SoftDeny);
        policy.insert(ActionClassification::Install, PolicyTier::SoftDeny);
        policy.insert(ActionClassification::GitHistory, PolicyTier::SoftDeny);
        policy.insert(ActionClassification::LocalWrite, PolicyTier::SoftDeny);
        policy.insert(ActionClassification::NetworkOut, PolicyTier::SoftDeny);
        policy.insert(ActionClassification::Config, PolicyTier::SoftDeny);
        policy.insert(ActionClassification::Safe, PolicyTier::Allow);
        Self { mode, anti_slop_strategies: vec![], policy, history: vec![] }
    }

    pub fn add_strategy(&mut self, strategy: Box<dyn PermissionStrategy>) {
        self.anti_slop_strategies.push(strategy);
    }

    pub fn set_policy(&mut self, classification: ActionClassification, tier: PolicyTier) {
        self.policy.insert(classification, tier);
    }

    pub async fn evaluate(&mut self, ctx: &PermissionContext) -> PermissionDecision {
        let tier = self.policy.get(&ctx.classification)
            .cloned()
            .unwrap_or(PolicyTier::SoftDeny);

        match tier {
            PolicyTier::HardDeny => {
                return self.record_decision(ctx, PermissionDecision::Deny {
                    reason: DenyReason::HardDenyRule { rule_id: "hard_deny_classification".into() },
                    interrupt: false,
                });
            }
            PolicyTier::Allow => {
                return self.record_decision(ctx, PermissionDecision::Allow { updated_input: None });
            }
            PolicyTier::Environment => {
                return self.record_decision(ctx, PermissionDecision::Allow { updated_input: None });
            }
            PolicyTier::SoftDeny => {}
        }

        for strategy in &self.anti_slop_strategies {
            if let Some(reason) = strategy.check(ctx).await {
                return self.record_decision(ctx, PermissionDecision::Deny { reason, interrupt: false });
            }
        }

        match self.mode {
            PermissionMode::Yolo => PermissionDecision::Allow { updated_input: None },
            PermissionMode::Plan | PermissionMode::Interactive => {
                match ctx.classification {
                    ActionClassification::Safe => PermissionDecision::Allow { updated_input: None },
                    _ => PermissionDecision::Deny {
                        reason: DenyReason::NeedsExplicitIntent {
                            classification: ctx.classification.clone(),
                        },
                        interrupt: true,
                    },
                }
            }
        }
    }

    fn record_decision(&mut self, ctx: &PermissionContext, decision: PermissionDecision) -> PermissionDecision {
        self.history.push(PermissionGateEvent {
            action_label: ctx.action_label.clone(),
            classification: ctx.classification.clone(),
            decision: decision.clone(),
            timestamp_iso: "2026-07-01T00:00:00Z".to_string(),
        });
        decision
    }

    pub fn history(&self) -> &[PermissionGateEvent] {
        &self.history
    }
}

// ---------------------------------------------------------------------------
// NoReadEvidenceStrategy — built-in anti-slop
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub struct NoReadEvidenceStrategy;

#[async_trait::async_trait]
impl PermissionStrategy for NoReadEvidenceStrategy {
    fn name(&self) -> &str { "NoReadEvidence" }
    async fn check(&self, ctx: &PermissionContext) -> Option<DenyReason> {
        if ctx.classification != ActionClassification::LocalWrite { return None; }
        let target = ctx.tool_args.get("path").and_then(|v| v.as_str())?;
        let target_path = PathBuf::from(target);
        if !ctx.files_read_in_session.contains(&target_path) {
            return Some(DenyReason::NoReadEvidence);
        }
        None
    }
}


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use forge_core_security::sandbox::SandboxRoot;

    fn make_sandbox() -> SandboxRoot {
        SandboxRoot::new(std::env::current_dir().unwrap()).unwrap()
    }

    fn make_ctx(
        classification: ActionClassification,
        mode: PermissionMode,
        tool_args: HashMap<String, serde_json::Value>,
    ) -> PermissionContext {
        let sandbox = make_sandbox();
        let sandbox2 = SandboxRoot::new(std::env::current_dir().unwrap()).unwrap();
        PermissionContext {
            action_label: "test".into(),
            classification,
            tool_name: "test_tool".into(),
            tool_args,
            cwd: std::env::current_dir().unwrap(),
            sandbox: sandbox2,
            files_read_in_session: vec![],
            permission_mode: mode,
            task: forge_core_security::containment::Trusted::new_internal("test task".into()),
        }
    }

    #[test]
    fn test_hard_deny_overrides_yolo() {
        let mut gate = PermissionGate::new(PermissionMode::Yolo);
        let ctx = make_ctx(
            ActionClassification::Destructive,
            PermissionMode::Yolo,
            HashMap::new(),
        );
        let decision = tokio_test::block_on(gate.evaluate(&ctx));
        match decision {
            PermissionDecision::Deny { reason, interrupt } => {
                assert!(!interrupt);
                assert_eq!(
                    reason,
                    DenyReason::HardDenyRule { rule_id: "hard_deny_classification".to_string() }
                );
            }
            _ => panic!("HardDeny should block even in Yolo mode"),
        }
    }

    #[test]
    fn test_safe_always_allowed() {
        let mut gate = PermissionGate::new(PermissionMode::Interactive);
        let ctx = make_ctx(
            ActionClassification::Safe,
            PermissionMode::Interactive,
            HashMap::new(),
        );
        let decision = tokio_test::block_on(gate.evaluate(&ctx));
        assert!(matches!(decision, PermissionDecision::Allow { .. }));
    }

    #[test]
    fn test_yolo_allows_soft_deny() {
        let mut gate = PermissionGate::new(PermissionMode::Yolo);
        let ctx = make_ctx(
            ActionClassification::Exec,
            PermissionMode::Yolo,
            HashMap::new(),
        );
        let decision = tokio_test::block_on(gate.evaluate(&ctx));
        assert!(matches!(decision, PermissionDecision::Allow { .. }));
    }

    #[test]
    fn test_interactive_denies_non_safe() {
        let mut gate = PermissionGate::new(PermissionMode::Interactive);
        let ctx = make_ctx(
            ActionClassification::LocalWrite,
            PermissionMode::Interactive,
            HashMap::new(),
        );
        let decision = tokio_test::block_on(gate.evaluate(&ctx));
        match decision {
            PermissionDecision::Deny { interrupt, .. } => {
                assert!(interrupt);
            }
            _ => panic!("Interactive should deny non-safe with interrupt"),
        }
    }

    #[test]
    fn test_decision_history_recorded() {
        let mut gate = PermissionGate::new(PermissionMode::Interactive);
        let ctx = make_ctx(
            ActionClassification::Safe,
            PermissionMode::Interactive,
            HashMap::new(),
        );
        let _ = tokio_test::block_on(gate.evaluate(&ctx));
        assert_eq!(gate.history().len(), 1);
    }

    #[test]
    fn test_policy_override() {
        let mut gate = PermissionGate::new(PermissionMode::Yolo);
        gate.set_policy(ActionClassification::Safe, PolicyTier::HardDeny);
        let ctx = make_ctx(
            ActionClassification::Safe,
            PermissionMode::Yolo,
            HashMap::new(),
        );
        let decision = tokio_test::block_on(gate.evaluate(&ctx));
        match decision {
            PermissionDecision::Deny { reason, .. } => {
                assert_eq!(
                    reason,
                    DenyReason::HardDenyRule { rule_id: "hard_deny_classification".to_string() }
                );
            }
            _ => panic!("HardDeny override should block even Safe + Yolo"),
        }
    }

    #[test]
    fn test_noread_evidence_strategy() {
        let mut gate = PermissionGate::new(PermissionMode::Yolo);
        gate.add_strategy(Box::new(NoReadEvidenceStrategy));
        let mut args = HashMap::new();
        args.insert("path".into(), serde_json::Value::String("unread_file.rs".into()));
        let ctx = make_ctx(
            ActionClassification::LocalWrite,
            PermissionMode::Yolo,
            args,
        );
        let decision = tokio_test::block_on(gate.evaluate(&ctx));
        match decision {
            PermissionDecision::Deny { reason, .. } => {
                assert_eq!(reason, DenyReason::NoReadEvidence);
            }
            _ => panic!("NoReadEvidence should block edit without prior read"),
        }
    }
}
