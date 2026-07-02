/// Steering profile — deterministic control surfaces for agent behavior.
///
/// Per Playbook 004 Card 4: support deterministic steering now through
/// mode, allowed/denied tools, output contract, evidence depth, verification
/// strictness, user preference claims, and law bundles.
///
/// True activation steering comes later for compatible model ports.
use serde::{Deserialize, Serialize};

/// Complete steering profile for a run.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SteeringProfile {
    /// Runtime mode: chat, plan, patch, surgery, eval, replay
    pub mode: String,
    /// Tools explicitly allowed (empty = all not denied)
    pub allowed_tools: Vec<String>,
    /// Tools explicitly denied
    pub denied_tools: Vec<String>,
    /// Output format contract
    pub output_contract: OutputContract,
    /// How much evidence to surface
    pub evidence_depth: EvidenceDepth,
    /// How strict verification should be
    pub verification_strictness: VerificationStrictness,
    /// User preference claims (high-trust)
    pub user_preference_claims: Vec<String>,
    /// Law bundles to inject
    pub law_bundle: Vec<String>,
}

/// Output format contract.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum OutputContract {
    Text,
    Json,
    StreamJson,
}

/// How much evidence to surface in output.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum EvidenceDepth {
    /// No evidence in output
    None,
    /// Summary-level evidence only
    Summary,
    /// Full evidence with citations
    Full,
}

/// Verification strictness level.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum VerificationStrictness {
    /// No verification
    None,
    /// Normal verification (error on fail)
    Normal,
    /// Strict verification (block on any warning)
    Strict,
}

impl Default for SteeringProfile {
    fn default() -> Self {
        Self {
            mode: "chat".into(),
            allowed_tools: vec![],
            denied_tools: vec![],
            output_contract: OutputContract::Json,
            evidence_depth: EvidenceDepth::Summary,
            verification_strictness: VerificationStrictness::Normal,
            user_preference_claims: vec![],
            law_bundle: vec![],
        }
    }
}

impl SteeringProfile {
    /// Create a steering profile for plan mode (read-only, inspection allowed).
    pub fn plan_mode() -> Self {
        Self {
            mode: "plan".into(),
            denied_tools: vec![
                "write_file".into(),
                "patch_file".into(),
                "run_command".into(),
            ],
            evidence_depth: EvidenceDepth::Full,
            verification_strictness: VerificationStrictness::Normal,
            ..Self::default()
        }
    }

    /// Create a steering profile for patch mode (bounded edits, verification required).
    pub fn patch_mode() -> Self {
        Self {
            mode: "patch".into(),
            denied_tools: vec!["run_command".into()],
            evidence_depth: EvidenceDepth::Full,
            verification_strictness: VerificationStrictness::Strict,
            ..Self::default()
        }
    }

    /// Check if a tool is allowed by this profile.
    pub fn is_tool_allowed(&self, tool_name: &str) -> bool {
        if self.denied_tools.iter().any(|t| t == tool_name) {
            return false;
        }
        if self.allowed_tools.is_empty() {
            return true;
        }
        self.allowed_tools.iter().any(|t| t == tool_name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_plan_mode_denies_mutation() {
        let profile = SteeringProfile::plan_mode();
        assert!(profile.is_tool_allowed("list_dir"));
        assert!(profile.is_tool_allowed("search_repo"));
        assert!(!profile.is_tool_allowed("write_file"));
        assert!(!profile.is_tool_allowed("run_command"));
    }

    #[test]
    fn test_patch_mode_allows_edits() {
        let profile = SteeringProfile::patch_mode();
        assert!(profile.is_tool_allowed("write_file"));
        assert!(profile.is_tool_allowed("patch_file"));
        assert!(!profile.is_tool_allowed("run_command"));
    }

    #[test]
    fn test_default_allows_all() {
        let profile = SteeringProfile::default();
        assert!(profile.is_tool_allowed("any_tool"));
    }
}
