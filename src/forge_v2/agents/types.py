"""Agent types — context, step, result, verification evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VerificationStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class VerificationEvidence:
    """A single verification gate result."""

    gate_name: str
    status: VerificationStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


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
    loop_guard_triggered: bool = False


@dataclass
class AgentResult:
    """Final result of an agent run — carries verification evidence, not self-rated confidence."""

    success: bool
    output: str
    steps: list[AgentStep]
    trace_id: str
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    artifacts: dict[str, Any] = field(default_factory=dict)
    verification: list[VerificationEvidence] = field(default_factory=list)
    resolution_rate: float = 0.0  # INV-202: resolution rate, never submission rate

    @property
    def verification_passed(self) -> bool:
        return all(v.status == VerificationStatus.PASSED for v in self.verification)

    @property
    def verification_summary(self) -> str:
        if not self.verification:
            return "no verification run"
        passed = sum(1 for v in self.verification if v.status == VerificationStatus.PASSED)
        return f"{passed}/{len(self.verification)} gates passed"
