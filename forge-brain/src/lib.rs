//! Forge-brain: Read-only bridge to semantic-memory-brain and OKF index.
//!
//! Per Playbook 004: No writes to external indexes; every piece of evidence
//! has source, trust level, and locator.
#![allow(dead_code)]

pub mod okf_adapter;
pub mod payload;
pub mod semantic_adapter;
pub mod steering;

pub use okf_adapter::OkfIndexAdapter;
pub use payload::{BrainEvidence, BrainQuery, MeaningFrame, ProofObligation, TopologicalPayload};
pub use semantic_adapter::SemanticAdapter;
pub use steering::{EvidenceDepth, OutputContract, SteeringProfile, VerificationStrictness};
