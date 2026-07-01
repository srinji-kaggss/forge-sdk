"""Harness runner — orchestrates the solve → observe → evolve → gate → reload cycle."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from forge_sdk.agents.types import AgentContext, AgentResult
from forge_sdk.harness.adaptive import AdaptivePrompt
from forge_sdk.harness.engine import EvolutionEngine, StepResult
from forge_sdk.harness.learning import Episode, LearningStore
from forge_sdk.harness.profiles import AgentProfile


@runtime_checkable
class Agent(Protocol):
    """Duck-typed protocol for any agent that can run tasks."""

    def run(self, context: AgentContext) -> AgentResult:
        ...


@dataclass
class RunResult:
    """Result of a harness run cycle."""

    task: str
    success: bool
    steps: int = 0
    output: str = ""
    tokens_used: int = 0
    duration_ms: float = 0.0
    evolution: StepResult | None = None
    episode_id: str = ""
    edits_made: list[str] = field(default_factory=list)


class HarnessRunner:
    """Orchestrates the full agent lifecycle with self-improvement.

    The runner is the top-level entry point that ties together:
    - AgentProfile (identity and configuration)
    - AdaptivePrompt (self-evolving system prompt)
    - LearningStore (episodic and semantic memory)
    - EvolutionEngine (mutation logic)

    Usage:
        profile = AgentProfile(name="coder", domain="python")
        runner = HarnessRunner(profile)

        # Run a single task
        result = runner.run("Fix the bug in main.py")

        # Run evolution cycle
        runner.evolve()

        # Inspect learning
        print(runner.store.stats)
    """

    def __init__(
        self,
        profile: AgentProfile | None = None,
        prompt: AdaptivePrompt | None = None,
        store: LearningStore | None = None,
        engine: EvolutionEngine | None = None,
        agent_fn: Callable[[AgentContext, str], AgentResult] | None = None,
        agent: Agent | None = None,
        base_path: str | Path = ".harness",
    ) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self._profile = profile or AgentProfile()
        self._prompt = prompt or AdaptivePrompt(self._profile)
        self._store = store or LearningStore(self._base / "memory")
        self._engine = engine or EvolutionEngine(self._store)
        self._agent_fn = agent_fn
        self._agent = agent

        # Run history
        self._runs: list[RunResult] = []
        self._current_generation = self._profile.generation
        self._validation_set: list[str] | None = None

    @classmethod
    def with_react_agent(
        cls,
        profile: AgentProfile | None = None,
        tools: Any = None,
        base_path: str | Path = ".harness",
        **agent_kwargs: Any,
    ) -> HarnessRunner:
        """Create a HarnessRunner wired to a pre-configured ReactAgent."""
        from forge_sdk.agents.react import ReactAgent
        from forge_sdk.harness.profiles import AgentProfile as Profile

        resolved_profile = profile or Profile()
        agent = ReactAgent(
            model=agent_kwargs.pop("model", None),
            tools=tools or [],
            **agent_kwargs,
        )
        return cls(
            profile=resolved_profile,
            agent=agent,
            base_path=base_path,
        )

    def run(
        self,
        task: str,
        evolve_after: bool = True,
        max_steps: int | None = None,
        **kwargs: Any,
    ) -> RunResult:
        """Run a task through the harness.

        1. Compose the adaptive prompt
        2. Execute the task via the agent function
        3. Record the episode
        4. Optionally evolve
        """
        start_time = time.time()
        episode_id = f"ep-{uuid.uuid4().hex[:12]}"

        # Compose prompt with task context
        self._prompt.set_context("task_type", self._classify_task(task))
        system_prompt = self._prompt.compose(task)

        # Execute via agent or agent function
        if self._agent is None and self._agent_fn is None:
            result = RunResult(
                task=task,
                success=False,
                output="No agent or agent_fn configured. Set agent or agent_fn in HarnessRunner.",
                episode_id=episode_id,
                duration_ms=(time.time() - start_time) * 1000,
            )
            self._runs.append(result)
            return result

        try:
            context = AgentContext(
                task=task,
                cwd=str(self._base),
                max_steps=max_steps or self._profile.max_steps,
            )
            if self._agent is not None:
                agent_result = self._agent.run(context)
            else:
                agent_result = self._agent_fn(context, system_prompt)  # type: ignore[union-attr]

            result = RunResult(
                task=task,
                success=agent_result.success,
                steps=len(agent_result.steps),
                output=agent_result.output,
                tokens_used=agent_result.total_tokens,
                duration_ms=(time.time() - start_time) * 1000,
                episode_id=episode_id,
                edits_made=agent_result.edits_made,
            )

        except Exception as exc:
            result = RunResult(
                task=task,
                success=False,
                output=f"Error: {exc}",
                episode_id=episode_id,
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Record episode
        episode = Episode(
            id=episode_id,
            task=task,
            outcome="success" if result.success else "failure",
            steps=[{"step": i} for i in range(result.steps)],
            tokens_used=result.tokens_used,
            duration_ms=result.duration_ms,
            error=result.output if not result.success else None,
            domain=self._profile.domain,
            generation=self._current_generation,
        )
        self._store.record_episode(episode)

        # Update prompt fragment scores
        for frag in self._prompt.fragments:
            self._prompt.record_outcome(frag.id, result.success)

        # Evolve if requested
        if evolve_after:
            evolution = self.evolve()
            result.evolution = evolution

        self._runs.append(result)
        return result

    def set_validation_set(self, tasks: list[str]) -> None:
        self._validation_set = tasks

    def evolve(self) -> StepResult:
        """Run one evolution step."""
        episodes = self._store.get_episodes(limit=20)
        kwargs = {}
        if self._validation_set is not None:
            kwargs["validation_tasks"] = self._validation_set
        return self._engine.step(self._profile, self._prompt, episodes, **kwargs)

    def evolve_loop(
        self,
        tasks: list[str],
        cycles: int = 5,
        batch_size: int = 3,
    ) -> list[StepResult]:
        """Run full evolution loop over multiple tasks and cycles.

        Mimics A-Evolve's solve → observe → evolve → gate → reload cycle.
        """
        results: list[StepResult] = []

        for _cycle in range(cycles):
            # Sample tasks for this cycle
            cycle_tasks = self._sample_tasks(tasks, batch_size)

            # Solve: run all tasks
            for task in cycle_tasks:
                self.run(task, evolve_after=False)

            # Observe + Evolve: run one evolution step
            step_result = self.evolve()
            results.append(step_result)

            # Check convergence
            if not step_result.mutated:
                # No mutations needed — converged
                break

        return results

    def _classify_task(self, task: str) -> str:
        """Simple task classification for prompt context."""
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["fix", "bug", "error", "debug"]):
            return "debugging"
        elif any(kw in task_lower for kw in ["write", "create", "implement", "build"]):
            return "creation"
        elif any(kw in task_lower for kw in ["review", "check", "analyze", "audit"]):
            return "review"
        elif any(kw in task_lower for kw in ["search", "find", "look", "research"]):
            return "research"
        elif any(kw in task_lower for kw in ["refactor", "optimize", "improve"]):
            return "refactoring"
        else:
            return "general"

    def _sample_tasks(self, tasks: list[str], n: int) -> list[str]:
        """Sample n tasks, prioritizing those the agent struggles with."""
        if len(tasks) <= n:
            return tasks
        # Simple: take last n (most recent)
        return tasks[-n:]

    # --- Inspection ---

    @property
    def profile(self) -> AgentProfile:
        return self._profile

    @property
    def prompt(self) -> AdaptivePrompt:
        return self._prompt

    @property
    def store(self) -> LearningStore:
        return self._store

    @property
    def engine(self) -> EvolutionEngine:
        return self._engine

    @property
    def runs(self) -> list[RunResult]:
        return list(self._runs)

    @property
    def stats(self) -> dict[str, Any]:
        """Aggregate run statistics."""
        total = len(self._runs)
        successes = sum(1 for r in self._runs if r.success)
        return {
            "total_runs": total,
            "success_rate": successes / total if total > 0 else 0.0,
            "avg_duration_ms": (
                sum(r.duration_ms for r in self._runs) / total if total > 0 else 0
            ),
            "avg_tokens": (
                sum(r.tokens_used for r in self._runs) / total if total > 0 else 0
            ),
            "generation": self._current_generation,
            "fragment_count": self._prompt.fragment_count,
            "knowledge_count": len(self._store.get_knowledge()),
        }

    # --- Persistence ---

    def save(self) -> None:
        """Save all harness state."""
        self._profile.save(self._base / "profile.json")
        self._prompt.save(self._base / "prompt.json")
        self._store.save_all()
        self._engine.save_history(self._base / "evolution.json")

    def load(self) -> None:
        """Load all harness state."""
        profile_path = self._base / "profile.json"
        if profile_path.exists():
            self._profile = AgentProfile.from_file(profile_path)
            self._prompt = AdaptivePrompt(self._profile)
            self._prompt.load(self._base / "prompt.json")
