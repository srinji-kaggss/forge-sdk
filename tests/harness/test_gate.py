"""Tests for the strict held-out validation gate.

Run with: pytest tests/harness/test_gate.py -v
"""

from __future__ import annotations

from forge_sdk.harness.adaptive import AdaptivePrompt
from forge_sdk.harness.engine import EvolutionEngine, StepResult
from forge_sdk.harness.gate import ValidationGate
from forge_sdk.harness.learning import Episode, LearningStore
from forge_sdk.harness.profiles import AgentProfile


def _always_succeed(task: str) -> bool:
    return True


def _always_fail(task: str) -> bool:
    return False


def _half_succeed(task: str) -> bool:
    return len(task) % 2 == 0


def _success_on(task: str) -> bool:
    return "good" in task


def _make_episode(episode_id: str, error: str, domain: str = "python") -> Episode:
    return Episode(
        id=episode_id,
        task=f"task for {episode_id}",
        outcome="failure",
        steps=[],
        tokens_used=0,
        duration_ms=0.0,
        error=error,
        domain=domain,
    )


class TestValidationGateEvaluate:
    def test_evaluate_all_pass(self):
        gate = ValidationGate(["task1", "task2"], _always_succeed)
        assert gate.evaluate(["task1", "task2"]) == 1.0

    def test_evaluate_all_fail(self):
        gate = ValidationGate(["task1", "task2"], _always_fail)
        assert gate.evaluate(["task1", "task2"]) == 0.0

    def test_evaluate_half_pass(self):
        gate = ValidationGate(["a", "bb"], _half_succeed)
        assert gate.evaluate(["a", "bb"]) == 0.5

    def test_evaluate_empty_tasks(self):
        gate = ValidationGate([], _always_succeed)
        assert gate.evaluate([]) == 1.0

    def test_evaluate_uses_default_set(self):
        gate = ValidationGate(["good task", "bad task"], _success_on)
        assert gate.evaluate() == 0.5

    def test_evaluate_override_default_set(self):
        gate = ValidationGate(["good task", "bad task"], _success_on)
        assert gate.evaluate(["good task"]) == 1.0


class TestValidationGateGate:
    def test_gate_accepts_when_strictly_better(self):
        gate = ValidationGate(["task"], _always_succeed)
        gate.set_baseline(0.5)
        result = StepResult(mutated=True, summary="test")
        assert gate.gate(result, 0.8) is True

    def test_gate_rejects_when_equal(self):
        gate = ValidationGate(["task"], _always_succeed)
        gate.set_baseline(0.5)
        result = StepResult(mutated=True, summary="test")
        assert gate.gate(result, 0.5) is False

    def test_gate_rejects_when_worse(self):
        gate = ValidationGate(["task"], _always_succeed)
        gate.set_baseline(0.5)
        result = StepResult(mutated=True, summary="test")
        assert gate.gate(result, 0.3) is False

    def test_gate_accepts_zero_to_nonzero(self):
        gate = ValidationGate(["task"], _always_succeed)
        gate.set_baseline(0.0)
        result = StepResult(mutated=True, summary="test")
        assert gate.gate(result, 0.2) is True

    def test_gate_rejects_when_baseline_is_perfect_and_stays_perfect(self):
        gate = ValidationGate(["task"], _always_succeed)
        gate.set_baseline(1.0)
        result = StepResult(mutated=True, summary="test")
        assert gate.gate(result, 1.0) is False

    def test_gate_rejects_drop_from_perfect(self):
        gate = ValidationGate(["task"], _always_succeed)
        gate.set_baseline(1.0)
        result = StepResult(mutated=True, summary="test")
        assert gate.gate(result, 0.5) is False


def _make_agent_fn(score_map: dict[str, bool]) -> ValidationGate:
    """Helper: make an agent_fn from a dict of task->success mapping."""
    def agent_fn(task: str) -> bool:
        return score_map.get(task, False)
    return ValidationGate(list(score_map.keys()), agent_fn)


class TestEngineGating:
    def test_engine_no_gate_still_mutates(self, tmp_path):
        """Without a gate set, engine behaves identically to before."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        result = engine.step(profile, prompt, episodes)
        assert result.mutated is True
        assert result.fragments_added == 1

    def test_gate_allows_improvement(self, tmp_path):
        """Gate commits mutations when validation score improves."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        # Agent succeeds only once evolved fragments exist in the prompt.
        # Before mutations: no evolved fragments → fails → score_before = 0.0
        # After mutations: evolved fragment added → succeeds → score_after = 1.0
        # Gate should accept (1.0 > 0.0).
        def agent_fn(task: str) -> bool:
            return any(f.source == "evolved" for f in prompt.fragments)

        gate = ValidationGate(["task1", "task2"], agent_fn)
        engine.set_validation_gate(gate)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        result = engine.step(profile, prompt, episodes, validation_tasks=["task1", "task2"])
        assert result.mutated is True
        assert result.gated is True
        assert result.validation_score_before == 0.0
        assert result.validation_score_after == 1.0

    def test_gate_blocks_regression(self, tmp_path):
        """Gate rolls back mutations when validation score doesn't improve."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        # Agent always fails — validation score will be 0.0 before AND after
        gate = ValidationGate(["task1", "task2"], _always_fail)
        engine.set_validation_gate(gate)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        result = engine.step(profile, prompt, episodes, validation_tasks=["task1", "task2"])
        assert result.mutated is False
        assert result.gated is True
        assert result.validation_score_before == 0.0
        assert result.validation_score_after == 0.0
        assert result.fragments_added == 0
        assert result.fragments_removed == 0
        assert result.knowledge_added == 0

    def test_gate_rolls_back_prompt_fragments(self, tmp_path):
        """When gate rejects, prompt fragments are restored to pre-mutation state."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        initial_count = prompt.fragment_count

        gate = ValidationGate(["task1", "task2"], _always_fail)
        engine.set_validation_gate(gate)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        engine.step(profile, prompt, episodes, validation_tasks=["task1", "task2"])
        assert prompt.fragment_count == initial_count, (
            "gate should have rolled back fragment additions"
        )

    def test_gate_rolls_back_knowledge(self, tmp_path):
        """When gate rejects, knowledge added during mutations is removed."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        initial_knowledge = len(store.get_knowledge())

        gate = ValidationGate(["task1", "task2"], _always_fail)
        engine.set_validation_gate(gate)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        engine.step(profile, prompt, episodes, validation_tasks=["task1", "task2"])
        assert len(store.get_knowledge()) == initial_knowledge, (
            "gate should have rolled back knowledge additions"
        )

    def test_gate_no_validation_tasks_ignored(self, tmp_path):
        """When no validation_tasks passed, gate is inactive even if set."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        gate = ValidationGate(["task1", "task2"], _always_fail)
        engine.set_validation_gate(gate)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        # No validation_tasks → gating_active=False
        result = engine.step(profile, prompt, episodes)
        assert result.mutated is True
        assert result.gated is False

    def test_gate_tie_falls_to_baseline(self, tmp_path):
        """Ties (equal before/after) are rejected per monotone-safe RSEA."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        # Agent always succeeds — score is 1.0 before AND after
        gate = ValidationGate(["task1", "task2"], _always_succeed)
        engine.set_validation_gate(gate)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        result = engine.step(profile, prompt, episodes, validation_tasks=["task1", "task2"])
        assert result.mutated is False
        assert result.gated is True
        assert result.validation_score_before == 1.0
        assert result.validation_score_after == 1.0

    def test_gate_validation_scores_in_result(self, tmp_path):
        """StepResult correctly reports validation scores and gated flag."""
        store = LearningStore(tmp_path / "memory")
        engine = EvolutionEngine(store)
        profile = AgentProfile(name="coder", domain="python")
        prompt = AdaptivePrompt(profile)

        gate = ValidationGate(["task1", "task2"], _always_fail)
        engine.set_validation_gate(gate)

        episodes = [
            _make_episode("ep-1", "ImportError: no module named foo"),
            _make_episode("ep-2", "ImportError: no module named bar"),
        ]

        result = engine.step(profile, prompt, episodes, validation_tasks=["task1", "task2"])
        assert result.gated is True
        assert isinstance(result.validation_score_before, float)
        assert isinstance(result.validation_score_after, float)
        assert result.validation_score_before == 0.0
        assert result.validation_score_after == 0.0
