#![allow(dead_code)]

//! Forge-brain: Read-only bridge to semantic-memory-brain and OKF index.
//!
//! Per Playbook 004: No writes to external indexes; every piece of evidence
//! has source, trust level, and locator.
#![allow(dead_code)]

pub mod okf_adapter;
pub mod semantic_adapter;
pub mod payload;
pub mod steering;

pub use payload::{TopologicalPayload, ProofObligation, MeaningFrame, BrainQuery, BrainEvidence};
pub use steering::{SteeringProfile, EvidenceDepth, VerificationStrictness, OutputContract};
pub use okf_adapter::OkfIndexAdapter;
pub use semantic_adapter::SemanticAdapter;
