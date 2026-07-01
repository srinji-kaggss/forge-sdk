"""Validation gate — RSEA-style held-out validation for evolution mutations."""

from __future__ import annotations

from collections.abc import Callable

from forge_sdk.harness.engine import StepResult


class ValidationGate:
    """RSEA-style strict held-out validation gate.

    Only commits mutations that strictly improve performance on a held-out
    validation set. This prevents overfitting to the training distribution
    (Nguyen et al. 2026, arxiv:2606.28374).
    """

    def __init__(
        self,
        validation_set: list[str],
        agent_fn: Callable[[str], bool],
    ) -> None:
        self._validation_set = list(validation_set)
        self._agent_fn = agent_fn
        self._baseline_score: float = 0.0

    def evaluate(self, tasks: list[str] | None = None) -> float:
        """Run tasks through agent_fn and return pass rate (0.0–1.0)."""
        tasks = tasks if tasks is not None else self._validation_set
        if not tasks:
            return 1.0
        successes = sum(1 for t in tasks if self._agent_fn(t))
        return successes / len(tasks)

    def set_baseline(self, score: float) -> None:
        self._baseline_score = score

    def gate(self, mutations: StepResult, new_score: float) -> bool:
        """Strict gate: only commit if new_score > baseline score.

        Per SPEC-V5-001 §7.2: evolved state committed ONLY if strictly
        better on validation set (>, not >=). Ties fall back to baseline
        (monotone-safe, per RSEA).
        """
        return new_score > self._baseline_score
