#![forbid(unsafe_code)]

//! # forge-core
//!
//! Zero-heavy-dependency core library for the forge agent runtime.
//!
//! This crate provides foundational types and traits used by all forge
//! components: events, results, context, steps, and model ports.

pub mod agent;
pub mod audit;
pub mod config;
pub mod context;
pub mod doctor;
pub mod event;
pub mod experience;
pub mod guard;
pub mod okf;
pub mod permission;
pub mod port;
pub mod renderer;
pub mod result;
pub mod router;
pub mod semantic;
pub mod session;
pub mod step;
pub mod tracer;
pub mod verifier;

// -- re-exports: event -------------------------------------------------------
pub use event::{
    ActionEvent, AgentEvent, ConvergenceEvent, Correlation, DecisionEvent, FileEditEvent,
    ModelRequestEvent, ModelResponseEvent, ModelUsageEvent, ObservationEvent,
    PermissionDecisionEvent, PermissionGateEvent, PermissionRequestEvent, RunEndEvent,
    RunErrorEvent, RunStartEvent, StateUpdateEvent, ThinkEvent, TokenUsageEvent, ToolCallEvent,
    ToolResultEvent, VerificationEvent, VerifyEndEvent, VerifyStartEvent,
};

// -- re-exports: result ------------------------------------------------------
pub use result::{AgentResult, ChangeManifest, FailureReason, RollbackPlan, VerificationEvidence};

// -- re-exports: context -----------------------------------------------------
pub use context::AgentContext;

// -- re-exports: step --------------------------------------------------------
pub use step::AgentStep;

// -- re-exports: port --------------------------------------------------------
pub use port::{ModelError, ModelPort, ModelResponse, ToolCall, ToolHandler, ToolResult, ToolSpec};
