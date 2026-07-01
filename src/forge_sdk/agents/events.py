"""Agent event stream dataclasses — the architectural hinge.

ADR-1: Every human- and machine-facing feature (live TUI, NDJSON output,
honest errors, diffs, background, checkpoints) is a *consumer* of this
single typed event stream. One source, many renderers.

ADR-2: The SDK stays pure; renderers live in the CLI layer.  ReactAgent
emits typed events via a callback(AgentEvent) -> None.  The CLI injects
a renderer.  The SDK never imports ANSI codes, never writes to stdout.

Each event is a plain dataclass with a `type` discriminator field for
wire-safe routing without isinstance chains.
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


@dataclass
class AgentEvent:
    """Base event emitted by the agent loop.

    Every event carries a ``type`` discriminator so consumers (renderers,
    checkpoints, machine pipelines) can route without an isinstance chain.
    """

    type: str
    step: int
    timestamp_ms: float = 0.0  # set at emit time
    # H14: correlation keys on every event — trace_id, run_id, model, provider
    correlation: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------


@dataclass
class RunStartEvent(AgentEvent):
    """Emitted once at the start of an agent run."""

    type: str = field(default="run_start", init=False)
    task: str = ""
    model: str = ""
    provider: str = ""
    run_id: str = ""
    step: int = field(default=0, init=False)


@dataclass
class RunEndEvent(AgentEvent):
    """Emitted once at the end of an agent run (success or failure)."""

    type: str = field(default="run_end", init=False)
    success: bool = False
    failure_reason: str = ""
    total_steps: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    edits_made: list[str] = field(default_factory=list)
    # H15: structured change manifest for CI/CD pipeline consumption
    change_manifest: dict | None = None


@dataclass
class RunErrorEvent(AgentEvent):
    """Emitted when the agent loop terminates with an unrecoverable error."""

    type: str = field(default="run_error", init=False)
    error: str = ""
    error_type: str = ""  # "model_error" | "usage_limit" | "convergence" | "max_steps"


# ---------------------------------------------------------------------------
# Agent reasoning events
# ---------------------------------------------------------------------------


@dataclass
class ThoughtEvent(AgentEvent):
    """Emitted when the agent produces reasoning text before acting."""

    type: str = field(default="thought", init=False)
    content: str = ""
    # H12: cognitive surface — what the agent is trying to achieve and why
    goal: str = ""
    hypothesis: str = ""


@dataclass
class ActionEvent(AgentEvent):
    """Emitted when the agent dispatches a tool call."""

    type: str = field(default="action", init=False)
    tool: str = ""
    tool_input: dict = field(default_factory=dict)
    # H12: contextual surface — risk metadata for the action
    risk: dict = field(default_factory=dict)  # {blast_radius, rollback, ...}


@dataclass
class ObservationEvent(AgentEvent):
    """Emitted when a tool returns its result."""

    type: str = field(default="observation", init=False)
    content: str = ""
    tool: str = ""
    is_error: bool = False
    # H12: cognitive surface — claims with missing evidence
    uncertainty: list[dict] = field(default_factory=list)  # [{claim, missing_evidence}, ...]


# ---------------------------------------------------------------------------
# Resource tracking
# ---------------------------------------------------------------------------


@dataclass
class TokenUsageEvent(AgentEvent):
    """Emitted when token usage data is available after a model call."""

    type: str = field(default="token_usage", init=False)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Verification events
# ---------------------------------------------------------------------------


@dataclass
class VerificationEvent(AgentEvent):
    """Emitted when a verification gate runs (finish branch only)."""

    type: str = field(default="verification", init=False)
    gate_name: str = ""
    status: str = ""  # "passed" | "failed"
    detail: str = ""
    # H5: maps to 10-evidence taxonomy (type_evidence, grounding_evidence,
    # total_correctness, invariant_preservation, falsifiability, etc.)
    evidence_type: str = ""


# ---------------------------------------------------------------------------
# File mutation events
# ---------------------------------------------------------------------------


@dataclass
class FileEditEvent(AgentEvent):
    """Emitted when the agent modifies a file on disk."""

    type: str = field(default="file_edit", init=False)
    path: str = ""
    action: str = ""  # "create" | "modify" | "delete"
    diff: str = ""


# ---------------------------------------------------------------------------
# Interpretability events (stubs — filled by future StateUpdate / Decision logic)
# ---------------------------------------------------------------------------


@dataclass
class StateUpdateEvent(AgentEvent):
    """Emitted when the agent changes its plan, memory, or assumptions.

    Currently a stub — no explicit state-update logic exists in the current
    arun() loop.  Emit points are reserved so renderers and downstream
    consumers can rely on the event type now.
    """

    type: str = field(default="state_update", init=False)
    kind: str = ""  # "memory_write" | "plan_update" | "assumption_change"
    before: str = ""
    after: str = ""


@dataclass
class DecisionEvent(AgentEvent):
    """Emitted when the agent chooses among tool alternatives.

    Currently a stub — no explicit decision-rationale logic exists in the
    current loop beyond the ad-hoc ``decision_rationale`` string logged
    inline.  Emit points are reserved.
    """

    type: str = field(default="decision", init=False)
    options: list[str] = field(default_factory=list)
    chosen: str = ""
    rationale: str = ""
    rejected_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Verification gate → evidence taxonomy mapping (H5)
# ---------------------------------------------------------------------------

EVIDENCE_TYPE_MAP = {
    "syntactic": "type_evidence",
    "entity": "grounding_evidence",
    "build_test": "total_correctness",
    "spec_conformance": "invariant_preservation",
    "semantic": "falsifiability",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_ms() -> float:
    """Return the current time as milliseconds since the epoch."""
    return _time.time() * 1000
