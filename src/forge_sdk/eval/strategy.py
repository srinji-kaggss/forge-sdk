"""Eval strategy — model strategy registry for eval bars.

Allows different models to be tried in sequence or parallel
during evaluation, similar to how tools are registered.
"""

from __future__ import annotations

from typing import Any, Protocol

from forge_sdk.eval.harness import EvalHarness, EvalReport
from forge_sdk.models.port import ModelPort


class EvalStrategy(Protocol):
    """Protocol for eval strategies — how to evaluate a model."""

    @property
    def stable_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    def applies(self, context: Any = None) -> bool: ...

    def execute(
        self,
        model: ModelPort,
        dataset: str = "openai_humaneval",
        limit: int = 10,
    ) -> EvalReport: ...


class DefaultEvalStrategy:
    """Default eval strategy — run HumanEval via EvalHarness."""

    STABLE_ID = "EVAL-DEFAULT-001"

    @property
    def stable_id(self) -> str:
        return self.STABLE_ID

    @property
    def name(self) -> str:
        return "default_humaneval"

    def applies(self, context: Any = None) -> bool:
        return True

    def execute(
        self,
        model: ModelPort,
        dataset: str = "openai_humaneval",
        limit: int = 10,
    ) -> EvalReport:
        harness = EvalHarness(model=model)
        if dataset == "openai_humaneval":
            problems = harness.load_humaneval()
        elif dataset == "mbpp":
            problems = harness.load_mbpp()
        else:
            raise ValueError(f"Unknown dataset: {dataset}")
        return harness.run_benchmark(problems, benchmark_name=dataset, limit=limit)


class EvalBar:
    """Registry of eval strategies — try multiple models in sequence."""

    def __init__(self) -> None:
        self._strategies: dict[str, EvalStrategy] = {}

    def register(self, strategy: EvalStrategy) -> None:
        self._strategies[strategy.stable_id] = strategy

    def get(self, stable_id: str) -> EvalStrategy | None:
        return self._strategies.get(stable_id)

    def available(self, context: Any = None) -> list[EvalStrategy]:
        return [s for s in self._strategies.values() if s.applies(context)]

    def run_all(
        self,
        model: ModelPort,
        dataset: str = "openai_humaneval",
        limit: int = 10,
    ) -> dict[str, EvalReport]:
        """Run all available eval strategies and return results keyed by stable_id."""
        results = {}
        for strategy in self.available():
            results[strategy.stable_id] = strategy.execute(model, dataset, limit)
        return results


default_eval_bar = EvalBar()
default_eval_bar.register(DefaultEvalStrategy())
