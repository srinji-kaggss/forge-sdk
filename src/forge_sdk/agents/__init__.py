"""Agent protocol — all agents must satisfy this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from forge_sdk.agents.types import AgentContext, AgentResult


@runtime_checkable
class Agent(Protocol):
    """Protocol that all agent implementations MUST satisfy."""

    def run(self, context: AgentContext) -> AgentResult: ...
