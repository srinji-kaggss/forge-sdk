#![forbid(unsafe_code)]

//! # forge-core-security
//!
//! Compile-time-enforced security boundaries for the forge agent runtime.
//!
//! Implements SPEC-SECURITY-003 §3.2-§3.3: taint tracking via `Tainted<T>`/`Trusted<T>`,
//! containment classification via `ContainmentResult`, and capability-based filesystem
//! access via `SandboxRoot`. Ships independently from forge-core so the current Python
//! forge-sdk can call it via JSON-in/JSON-out subprocess pipe before the rest of the
//! Rust core exists (SPEC-SECURITY-003 §4 Phase 1 sequencing).

pub mod containment;
pub mod sandbox;
