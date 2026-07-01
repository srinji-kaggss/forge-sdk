"""Agent types — context, step, result.

INV-201: result carries verification evidence[], not self-rated confidence.
INV-202: success = resolution (verification passed), not submission.
INV-208: failure_reason carries the truthful terminal cause of a FAILED run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


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
    """Final result of an agent run.

    INV-201: verification[] carries evidence of which gates passed.
    INV-202: success = verification passed (resolution), not self-rated confidence.
    INV-208: failure_reason is the truthful terminal cause of a FAILED run.
    """

    success: bool
    output: str
    steps: list[AgentStep]
    trace_id: str
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    artifacts: dict[str, Any] = field(default_factory=dict)
    verification: list[Any] = field(default_factory=list)  # list[VerificationEvidence]
    edits_made: list[str] = field(default_factory=list)  # file paths modified during run
    named_targets_missing: list[str] = field(
        default_factory=list
    )  # files named in the task but never edited (advisory, see v0.5.2)
    # Previously a model-auth failure ("Illegal header value b'Bearer '") was
    # caught, logged, discarded, and the human was told "Max steps reached" —
    # the wrong reason. This field carries the real cause so the CLI (and any
    # machine consumer) can report it honestly. Empty string on SUCCESS.
    failure_reason: str = ""

    @property
    def verification_summary(self) -> str:
        """Human-readable verification status."""
        if not self.verification:
            return "no verification run"
        passed = sum(1 for v in self.verification if v.status.value == "passed")
        return f"{passed}/{len(self.verification)} gates passed"

    @property
    def summary(self) -> str:
        """One-line summary for AI consumption."""
        return (
            f"{'SUCCESS' if self.success else 'FAILED'} | "
            f"{len(self.steps)} steps | "
            f"{self.total_tokens} tokens | "
            f"verification: {self.verification_summary} | "
            f"{self.output[:80]}..."
        )
