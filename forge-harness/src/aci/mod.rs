/// Agent-Computer Interface: tools and tool types for the forge harness.
///
/// This module defines the canonical tool implementations used by the forge
/// agent loop. Tools are moved here from forge-cli/src/tools.rs per Playbook 003
/// (SDK/Harness/Agent Split, Card 1).
pub mod tools;

pub use tools::*;
