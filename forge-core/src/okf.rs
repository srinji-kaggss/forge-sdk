use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// ClaimStatus — 4 truth-evaluation states
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ClaimStatus {
    Asserted,
    Verified,
    Disputed,
    Refuted,
}

impl ClaimStatus {
    /// Return all statuses a claim may transition to from `self`.
    pub fn permitted_transitions(&self) -> Vec<ClaimStatus> {
        match self {
            Self::Asserted => vec![Self::Verified, Self::Disputed],
            Self::Verified => vec![Self::Disputed, Self::Refuted],
            Self::Disputed => vec![Self::Asserted, Self::Verified, Self::Refuted],
            Self::Refuted => vec![Self::Asserted],
        }
    }

    /// Attempt a state transition.
    pub fn transition_to(self, target: ClaimStatus) -> Result<ClaimStatus, ClaimStatus> {
        if self.permitted_transitions().contains(&target) {
            Ok(target)
        } else {
            Err(self)
        }
    }
}

// ---------------------------------------------------------------------------
// InvariantBound — 5 constraint discriminators
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum InvariantBound {
    PreCondition,
    PostCondition,
    LoopInvariant,
    TypeConstraint,
    SafetyProperty,
}

// ---------------------------------------------------------------------------
// ObligationStatus — 4 proof-progress states
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ObligationStatus {
    Open,
    InProgress,
    Proved,
    Deferred,
}

// ---------------------------------------------------------------------------
// OkfDocType — 7 document discriminators
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OkfDocType {
    Requirement,
    Solution,
    Interface,
    SafetyCase,
    VerificationPlan,
    Architecture,
    TestPlan,
}

// ---------------------------------------------------------------------------
// Claim
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Claim {
    pub id: String,
    pub statement: String,
    pub status: ClaimStatus,
    pub evidence: Vec<String>,
}

// ---------------------------------------------------------------------------
// Invariant
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Invariant {
    pub id: String,
    pub expression: String,
    pub bound_type: InvariantBound,
    pub source_locations: Vec<String>,
}

// ---------------------------------------------------------------------------
// ProofObligation
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProofObligation {
    pub id: String,
    pub claim_id: String,
    pub description: String,
    pub status: ObligationStatus,
}

// ---------------------------------------------------------------------------
// OkfDoc
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OkfDoc {
    pub id: String,
    pub title: String,
    pub okf_type: OkfDocType,
    pub claims: Vec<Claim>,
    pub invariants: Vec<Invariant>,
    pub proof_obligations: Vec<ProofObligation>,
    pub created_at: String,
    pub source_path: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_okf_doc_round_trip() {
        let doc = OkfDoc {
            id: "okf-001".into(),
            title: "Safety Requirements".into(),
            okf_type: OkfDocType::SafetyCase,
            claims: vec![Claim {
                id: "c-001".into(),
                statement: "System shall not allow arbitrary code execution".into(),
                status: ClaimStatus::Asserted,
                evidence: vec!["sandbox.rs".into()],
            }],
            invariants: vec![Invariant {
                id: "i-001".into(),
                expression: "sandbox_root.canonicalize(path).is_ok()".into(),
                bound_type: InvariantBound::PreCondition,
                source_locations: vec!["sandbox.rs:42".into()],
            }],
            proof_obligations: vec![ProofObligation {
                id: "po-001".into(),
                claim_id: "c-001".into(),
                description: "Prove sandbox prevents path traversal".into(),
                status: ObligationStatus::Open,
            }],
            created_at: "2026-07-01T00:00:00Z".into(),
            source_path: Some("/spec/safety.md".into()),
        };
        let json = serde_json::to_string(&doc).unwrap();
        let restored: OkfDoc = serde_json::from_str(&json).unwrap();
        assert_eq!(doc, restored);
    }

    #[test]
    fn test_claim_status_transitions() {
        assert!(ClaimStatus::Asserted.transition_to(ClaimStatus::Verified).is_ok());
        assert!(ClaimStatus::Asserted.transition_to(ClaimStatus::Refuted).is_err());
        assert!(ClaimStatus::Verified.transition_to(ClaimStatus::Disputed).is_ok());
        assert!(ClaimStatus::Refuted.transition_to(ClaimStatus::Asserted).is_ok());
    }

    #[test]
    fn test_invariant_all_variants() {
        let variants = vec![
            InvariantBound::PreCondition,
            InvariantBound::PostCondition,
            InvariantBound::LoopInvariant,
            InvariantBound::TypeConstraint,
            InvariantBound::SafetyProperty,
        ];
        assert_eq!(variants.len(), 5);
        for v in &variants {
            let json = serde_json::to_string(v).unwrap();
            let restored: InvariantBound = serde_json::from_str(&json).unwrap();
            assert_eq!(*v, restored);
        }
    }

    #[test]
    fn test_proof_obligation_link() {
        let claim = Claim {
            id: "c-001".into(),
            statement: "test".into(),
            status: ClaimStatus::Asserted,
            evidence: vec![],
        };
        let obligation = ProofObligation {
            id: "po-001".into(),
            claim_id: claim.id.clone(),
            description: "Prove test".into(),
            status: ObligationStatus::Open,
        };
        assert_eq!(obligation.claim_id, claim.id);
    }

    #[test]
    fn test_okf_doc_type_all_variants() {
        let types = [
            OkfDocType::Requirement,
            OkfDocType::Solution,
            OkfDocType::Interface,
            OkfDocType::SafetyCase,
            OkfDocType::VerificationPlan,
            OkfDocType::Architecture,
            OkfDocType::TestPlan,
        ];
        assert_eq!(types.len(), 7);
    }
}
