"""Agent types — context, step, result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Mutable state passed through the agent loop."""

    task: str
    cwd: str = "."
    max_steps: int = 50
    step_count: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentStep:
    """A single step in the agent loop."""

    step_number: int
    thought: str
    action: str  # tool name or "finish"
    action_input: dict[str, Any]
    observation: str = ""
    is_final: bool = False


@dataclass
class AgentResult:
    """Final result of an agent run."""

    success: bool
    output: str
    steps: list[AgentStep]
    trace_id: str
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    artifacts: dict[str, Any] = field(default_factory=dict)
