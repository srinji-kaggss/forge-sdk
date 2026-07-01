#![forbid(unsafe_code)]

//! # forge-core
//!
//! Zero-heavy-dependency core library for the forge agent runtime.
//!
//! This crate provides foundational types and traits used by all forge
//! components: events, results, context, steps, and model ports.

pub mod context;
pub mod event;
pub mod port;
pub mod result;
pub mod step;

// -- re-exports: event -------------------------------------------------------
pub use event::{
    ActionEvent, AgentEvent, ConvergenceEvent, Correlation, DecisionEvent,
    FileEditEvent, ObservationEvent, PermissionGateEvent, RunEndEvent,
    RunErrorEvent, RunStartEvent, StateUpdateEvent, ThinkEvent,
    TokenUsageEvent, VerificationEvent,
};

// -- re-exports: result ------------------------------------------------------
pub use result::{
    AgentResult, ChangeManifest, FailureReason, RollbackPlan, VerificationEvidence,
};

// -- re-exports: context -----------------------------------------------------
pub use context::AgentContext;

// -- re-exports: step --------------------------------------------------------
pub use step::AgentStep;

// -- re-exports: port --------------------------------------------------------
pub use port::{
    ModelError, ModelPort, ModelResponse, ToolCall, ToolHandler, ToolResult,
    ToolSpec,
};
