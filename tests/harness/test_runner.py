"""Tests for HarnessRunner — agent wiring, placeholder fallback, and classmethod factory."""

from __future__ import annotations

import tempfile

from forge_sdk.agents.types import AgentContext, AgentResult
from forge_sdk.harness.runner import Agent, HarnessRunner


def _dummy_result(success: bool = True, output: str = "done", total_tokens: int = 42) -> AgentResult:
    return AgentResult(
        success=success,
        output=output,
        steps=[],
        trace_id="test",
        total_tokens=total_tokens,
    )


def test_placeholder_when_no_agent_and_no_fn():
    """Neither agent nor agent_fn → placeholder failure result."""
    runner = HarnessRunner(base_path=tempfile.mkdtemp())
    result = runner.run("do something")
    assert not result.success
    assert "No agent" in result.output


def test_agent_fn_is_called():
    """agent_fn receives context and system_prompt."""
    tmp = tempfile.mkdtemp()

    def fake_agent(ctx: AgentContext, prompt: str) -> AgentResult:
        assert ctx.task == "write tests"
        assert "write" in prompt
        return _dummy_result(output="tests written")

    runner = HarnessRunner(agent_fn=fake_agent, base_path=tmp)
    result = runner.run("write tests")
    assert result.success
    assert result.output == "tests written"
    assert result.tokens_used == 42


def test_agent_object_with_run():
    """Passing an agent object (duck-typed) calls agent.run(context)."""
    tmp = tempfile.mkdtemp()

    class FakeAgent:
        def run(self, context: AgentContext) -> AgentResult:
            assert context.task == "deploy"
            assert context.cwd == tmp
            return _dummy_result(output="deployed")

    runner = HarnessRunner(agent=FakeAgent(), base_path=tmp)
    result = runner.run("deploy")
    assert result.success
    assert result.output == "deployed"


def test_agent_protocol_isinstance_check():
    """The Agent protocol should be runtime-checkable."""
    class HasRun:
        def run(self, ctx: AgentContext) -> AgentResult:
            return _dummy_result()

    assert isinstance(HasRun(), Agent)


def test_agent_takes_precedence_over_agent_fn():
    """When both agent and agent_fn are set, agent.run() is used."""
    tmp = tempfile.mkdtemp()

    def fn_should_not_be_called(ctx: AgentContext, prompt: str) -> AgentResult:
        raise AssertionError("agent_fn was called instead of agent")

    class PreferredAgent:
        def run(self, context: AgentContext) -> AgentResult:
            return _dummy_result(output="agent was used")

    runner = HarnessRunner(
        agent=PreferredAgent(),
        agent_fn=fn_should_not_be_called,
        base_path=tmp,
    )
    result = runner.run("test")
    assert result.success
    assert result.output == "agent was used"


def test_with_react_agent_classmethod(tmp_path):
    """with_react_agent() creates a runner with a ReactAgent wired in."""
    runner = HarnessRunner.with_react_agent(base_path=str(tmp_path))
    assert runner._agent is not None
    assert runner._agent_fn is None

    # ReactAgent.run() is callable
    assert callable(runner._agent.run)


def test_runner_saves_episode_and_tokens():
    """RunResult.tokens_used aligns with Episode.tokens_used."""
    tmp = tempfile.mkdtemp()

    def tracked_agent(ctx: AgentContext, prompt: str) -> AgentResult:
        return _dummy_result(total_tokens=99, output="tracked")

    runner = HarnessRunner(agent_fn=tracked_agent, base_path=tmp)
    result = runner.run("track tokens")
    assert result.tokens_used == 99

    episodes = runner.store.get_episodes(limit=5)
    assert len(episodes) == 1
    assert episodes[0].tokens_used == 99


def test_exception_during_agent_produces_failure():
    """If agent.run() raises, the runner wraps it into a failure result."""
    tmp = tempfile.mkdtemp()

    class BrokenAgent:
        def run(self, context: AgentContext) -> AgentResult:
            raise RuntimeError("something went wrong")

    runner = HarnessRunner(agent=BrokenAgent(), base_path=tmp)
    result = runner.run("crash")
    assert not result.success
    assert "Error" in result.output
    assert "something went wrong" in result.output
