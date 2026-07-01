"""Eval harness — orchestrates benchmark evaluation with registered strategies."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from forge_sdk.audit import AuditLog
from forge_sdk.eval.runner import TestResult, TestRunner
from forge_sdk.models.port import ModelPort
from forge_sdk.tracing.tracer import Tracer


@dataclass
class EvalProblem:
    """A single evaluation problem."""

    task_id: str
    prompt: str
    test_code: str
    entry_point: str = ""
    solution: str = ""  # reference solution (if available)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result for a single problem."""

    task_id: str
    passed: bool
    generated_code: str
    test_result: TestResult
    latency_ms: float
    tokens_used: int = 0


@dataclass
class EvalReport:
    """Aggregated eval results.

    INV-202: reports resolution rate, never submission rate.
    Resolution = the fix actually worked (test passed), not that the agent finished.
    """

    benchmark: str
    total: int
    passed: int  # = resolved (INV-202)
    failed: int
    errors: int
    resolution_rate: float  # INV-202: renamed from pass_rate
    avg_latency_ms: float
    total_tokens: int
    results: list[EvalResult]
    timestamp: float = field(default_factory=time.time)

    @property
    def pass_rate(self) -> float:
        """Backwards compat alias — but resolution_rate is canonical."""
        return self.resolution_rate

    @property
    def summary(self) -> str:
        """One-line summary for AI consumption."""
        return (
            f"{self.benchmark}: {self.passed}/{self.total} resolved "
            f"({self.resolution_rate:.1%}) | "
            f"{self.failed} failed, {self.errors} errors | "
            f"avg {self.avg_latency_ms:.0f}ms | "
            f"{self.total_tokens} tokens"
        )


class CodeExtractor:
    """Strategy-based code extraction. Registered as a policy, not hardcoded."""

    def __init__(self) -> None:
        self._strategies: list[tuple[str, Callable[..., Any]]] = []

    def register(self, name: str, extractor: Callable[..., Any]) -> None:
        self._strategies.append((name, extractor))

    def extract(self, response: str, entry_point: str) -> str:
        """Try each strategy in order until one produces valid code."""
        for _name, strategy in self._strategies:
            try:
                result = strategy(response, entry_point)
                if result and len(result.strip()) > 10:
                    return result
            except Exception:
                continue
        # Fallback: return raw response
        return response


def _extract_from_code_block(response: str, entry_point: str) -> str:
    """Extract code from markdown code blocks."""
    patterns = [
        r"```python\n(.*?)```",
        r"```\n(.*?)```",
        r"```py\n(.*?)```",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            # Return the block that contains the entry point
            for match in matches:
                if entry_point in match:
                    return match.strip()
            return matches[0].strip()
    return ""


def _extract_function(response: str, entry_point: str) -> str:
    """Extract the function definition from response."""
    if not entry_point:
        return ""
    pattern = rf"(def {re.escape(entry_point)}\(.*?\n(?:    .*\n)*)"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(0).strip()
    return ""


def _extract_after_instruction(response: str, entry_point: str) -> str:
    """Extract code after common instruction patterns."""
    markers = ["Here is", "Here's", "The solution", "The function", "```"]
    for marker in markers:
        idx = response.find(marker)
        if idx >= 0:
            candidate = response[idx:]
            if "```" in candidate:
                return _extract_from_code_block(candidate, entry_point)
    return ""


# Default extractor with registered strategies
default_extractor = CodeExtractor()
default_extractor.register("code_block", _extract_from_code_block)
default_extractor.register("function", _extract_function)
default_extractor.register("after_instruction", _extract_after_instruction)


class EvalHarness:
    """Orchestrates benchmark evaluation."""

    def __init__(
        self,
        model: ModelPort,
        tracer: Tracer | None = None,
        audit: AuditLog | None = None,
        extractor: CodeExtractor | None = None,
        runner: TestRunner | None = None,
    ) -> None:
        self._model = model
        self._tracer = tracer or Tracer()
        self._audit = audit
        self._extractor = extractor or default_extractor
        self._runner = runner or TestRunner()

    def _build_prompt(self, problem: EvalProblem) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are an expert Python programmer. Write a complete solution "
                    "for the given problem. Return ONLY the code, no explanations. "
                    "The code must be a single function that matches the given signature."
                ),
            },
            {"role": "user", "content": problem.prompt},
        ]

    def eval_problem(self, problem: EvalProblem) -> EvalResult:
        """Evaluate a single problem."""
        start = time.time()

        # Get model response
        messages = self._build_prompt(problem)
        span = self._tracer.start_span(name="eval.llm_call")
        response = self._model.complete(messages, temperature=0.0)
        self._tracer.finish_span(span)

        # Extract code
        code = self._extractor.extract(response.content, problem.entry_point)

        # Run test
        test_result = self._runner.run(code, problem.test_code)

        latency = (time.time() - start) * 1000

        # Audit
        if self._audit:
            self._audit.append(
                trace_id=self._tracer.trace_id,
                entry_type="eval_result",
                payload={
                    "benchmark": "unknown",
                    "task_id": problem.task_id,
                    "passed": test_result.passed,
                    "latency_ms": latency,
                    "tokens": response.usage.total_tokens,
                },
            )

        return EvalResult(
            task_id=problem.task_id,
            passed=test_result.passed,
            generated_code=code,
            test_result=test_result,
            latency_ms=latency,
            tokens_used=response.usage.total_tokens,
        )

    def run_benchmark(
        self,
        problems: list[EvalProblem],
        benchmark_name: str = "unknown",
        limit: int | None = None,
    ) -> EvalReport:
        """Run a full benchmark."""
        subset = problems[:limit] if limit else problems
        results: list[EvalResult] = []
        total_tokens = 0
        total_latency = 0.0

        for i, problem in enumerate(subset):
            print(f"  [{i + 1}/{len(subset)}] {problem.task_id}...", end=" ", flush=True)
            result = self.eval_problem(problem)
            results.append(result)
            total_tokens += result.tokens_used
            total_latency += result.latency_ms
            status = "PASS" if result.passed else "FAIL"
            print(f"{status} ({result.latency_ms:.0f}ms)")

        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed and not r.test_result.timed_out)
        errors = sum(1 for r in results if r.test_result.timed_out)

        return EvalReport(
            benchmark=benchmark_name,
            total=len(subset),
            passed=passed,
            failed=failed,
            errors=errors,
            resolution_rate=passed / len(subset) if subset else 0.0,  # INV-202
            avg_latency_ms=total_latency / len(subset) if subset else 0.0,
            total_tokens=total_tokens,
            results=results,
        )

    def load_humaneval(self, split: str = "test") -> list[EvalProblem]:
        """Load HumanEval problems from HuggingFace datasets."""
        try:
            from datasets import load_dataset

            ds: Any = load_dataset("openai/openai_humaneval", split=split)
            problems: list[EvalProblem] = []
            for row in ds:  # type: ignore[reportUnknownVariableType]
                problems.append(
                    EvalProblem(
                        task_id=row["task_id"],
                        prompt=row["prompt"],
                        test_code=row["test"],
                        entry_point=row["entry_point"],
                        solution=row.get("canonical_solution", ""),
                    )
                )
            return problems
        except Exception as e:
            raise RuntimeError(f"Failed to load HumanEval: {e}") from e

    def load_mbpp(self, split: str = "test") -> list[EvalProblem]:
        """Load MBPP problems from HuggingFace datasets."""
        try:
            from datasets import load_dataset

            ds: Any = load_dataset("google-research-datasets/mbpp", split=split)
            problems: list[EvalProblem] = []
            for row in ds:  # type: ignore[reportUnknownVariableType]
                problems.append(
                    EvalProblem(
                        task_id=f"MBPP_{row['task_id']}",
                        prompt=row["prompt"],
                        test_code="\n".join(row["test"]),
                        entry_point=row.get("entry_point", ""),
                    )
                )
            return problems
        except Exception as e:
            raise RuntimeError(f"Failed to load MBPP: {e}") from e
