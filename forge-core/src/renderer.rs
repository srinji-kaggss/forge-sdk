use crate::event::AgentEvent;

/// ADR-2: Renderers live in the CLI/TUI layer. SDK never imports ANSI codes.
/// This trait provides the bridge: forge-core defines the interface,
/// forge-cli/forge-tui provide the concrete implementations.
pub trait EventRenderer: Send {
    /// Called for every event emitted during a run.
    fn on_event(&mut self, event: &AgentEvent);
    /// Called when the run ends, with the final exit code.
    fn on_end(&mut self, exit_code: i32);
}
