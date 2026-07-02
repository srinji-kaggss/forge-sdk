/// Topological payload types — structured input to the agent loop.
///
/// Before a model call, the harness builds a `TopologicalPayload` from:
/// - task text
/// - repo map
/// - governance files (AGENTS.md, README, specs)
/// - brain query
/// - OKF query
/// - user profile/preference claims
/// - permission mode
use serde::{Deserialize, Serialize};

/// Query parameters for brain/OKF lookup.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BrainQuery {
    pub task: String,
    pub cwd: String,
    pub repo: Option<String>,
    pub domains: Vec<String>,
    pub max_results: usize,
}

impl BrainQuery {
    pub fn new(task: impl Into<String>) -> Self {
        Self {
            task: task.into(),
            cwd: std::env::current_dir()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string(),
            repo: None,
            domains: vec![],
            max_results: 10,
        }
    }
}

/// Evidence returned by a brain or OKF query.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BrainEvidence {
    pub source: String,
    pub source_class: String,
    pub trust_level: TrustLevel,
    pub summary: String,
    pub locator: String,
    pub content_hash: Option<String>,
}

/// Trust level for evidence (monotonic).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum TrustLevel {
    Low,
    MediumHigh,
    High,
}

/// The topological payload — structured context for model calls.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TopologicalPayload {
    pub task: String,
    pub intent: MeaningFrame,
    pub constraints: Vec<ProofObligation>,
    pub preferences: Vec<ProofObligation>,
    pub laws: Vec<ProofObligation>,
    pub repo_evidence: Vec<BrainEvidence>,
    pub memory_evidence: Vec<BrainEvidence>,
    pub proof_obligations: Vec<ProofObligation>,
    pub steering_profile: Option<SteeringProfile>,
}

/// Intention/decomposition frame for the task.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MeaningFrame {
    pub primary_intent: String,
    pub sub_intents: Vec<String>,
    pub domain_hints: Vec<String>,
}

/// A typed claim with proof obligation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofObligation {
    pub invariant: String,
    pub claim: String,
    pub evidence_required: String,
    pub status: ObligationStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ObligationStatus {
    Asserted,
    Verified,
    Disputed,
    Refuted,
}

/// Steering profile — deterministic mode configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SteeringProfile {
    pub mode: String,
    pub allowed_tools: Vec<String>,
    pub denied_tools: Vec<String>,
    pub output_contract: OutputContract,
    pub evidence_depth: EvidenceDepth,
    pub verification_strictness: VerificationStrictness,
    pub law_bundle: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum EvidenceDepth {
    None,
    Summary,
    Full,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum VerificationStrictness {
    None,
    Normal,
    Strict,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum OutputContract {
    Text,
    Json,
    StreamJson,
}

impl TopologicalPayload {
    pub fn new(task: impl Into<String>) -> Self {
        Self {
            task: task.into(),
            intent: MeaningFrame {
                primary_intent: String::new(),
                sub_intents: vec![],
                domain_hints: vec![],
            },
            constraints: vec![],
            preferences: vec![],
            laws: vec![],
            repo_evidence: vec![],
            memory_evidence: vec![],
            proof_obligations: vec![],
            steering_profile: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_topological_payload_builder() {
        let p = TopologicalPayload::new("test task");
        assert_eq!(p.task, "test task");
        assert!(p.proof_obligations.is_empty());
    }

    #[test]
    fn test_brain_query_default() {
        let q = BrainQuery::new("find relevant context");
        assert_eq!(q.task, "find relevant context");
        assert_eq!(q.max_results, 10);
    }

    #[test]
    fn test_trust_level_ordering() {
        assert!(TrustLevel::Low < TrustLevel::MediumHigh);
        assert!(TrustLevel::MediumHigh < TrustLevel::High);
    }
}
