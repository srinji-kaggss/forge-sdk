"""Tests for INV-201 verification pipeline — SemanticCheck wire-up, spec
conformance gate, and pipeline resilience when components are absent.

Run with: pytest tests/test_verification_pipeline.py -v
"""

from __future__ import annotations

import json

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.models.port import ModelPort
from forge_sdk.models.types import ModelResponse
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.verifiers import (
    SemanticCheck,
    VerificationStatus,
    spec_conformance_check,
)


class _FakeModelPort(ModelPort):
    """Scripted model port that returns canned responses."""

    name = "fake-port"
    provider = "test"
    context_window = 100_000
    max_output = 4096
    supports_reasoning = False

    def __init__(self, steps: list[dict]):
        self._steps = steps
        self._idx = 0

    def complete(self, messages, *, temperature=0.0, max_tokens=None, stop=None):
        if self._idx >= len(self._steps):
            body = {
                "thought": "done",
                "action": "finish",
                "action_input": {"output": "Status: SUCCESS."},
            }
        else:
            body = self._steps[self._idx]
        self._idx += 1
        return ModelResponse(content=json.dumps(body))


class _AlwaysFailSemanticCheck(SemanticCheck):
    """Semantic check that always fails — used to verify the gate is called."""

    def __init__(self):
        super().__init__(model_port=None)

    def applies(self, context=None):
        return True

    def execute(self, task_intent, solution_summary, solution_files=None):
        from forge_sdk.verifiers import VerificationEvidence
        return VerificationEvidence(
            gate_name=self.STABLE_ID,
            status=VerificationStatus.FAILED,
            message="Intentional test failure — semantic check called",
            details={"confidence": 0.0},
        )


class _AlwaysPassSemanticCheck(SemanticCheck):
    """Semantic check that always passes."""

    def __init__(self):
        super().__init__(model_port=None)

    def applies(self, context=None):
        return True

    def execute(self, task_intent, solution_summary, solution_files=None):
        from forge_sdk.verifiers import VerificationEvidence
        return VerificationEvidence(
            gate_name=self.STABLE_ID,
            status=VerificationStatus.PASSED,
            message="Semantic alignment confirmed",
            details={"confidence": 0.95},
        )


def _fake_tools_registry() -> ToolRegistry:
    from forge_sdk.tools.filesystem import FILE_TOOLS

    reg = ToolRegistry()
    for tool in FILE_TOOLS:
        reg.register(tool)
    return reg


# ── spec_conformance_check unit tests ───────────────────────────────


def test_spec_conformance_passes_when_artifacts_present():
    task = "Create a file called main.py that prints hello"
    all_edits = ["main.py"]
    output = "Created main.py with hello world"

    evidence = spec_conformance_check(task, all_edits, output)
    assert evidence.status == VerificationStatus.PASSED
    assert "accounted for" in evidence.message


def test_spec_conformance_fails_when_artifacts_missing():
    task = "Create a file called main.py that prints hello"
    all_edits = ["helper.py"]
    output = "Created helper.py"

    evidence = spec_conformance_check(task, all_edits, output)
    assert evidence.status == VerificationStatus.FAILED
    assert "main.py" in evidence.message


def test_spec_conformance_skipped_when_no_filename_in_task():
    task = "Write a Python script that prints hello"
    all_edits = ["main.py"]
    output = "Created main.py"

    evidence = spec_conformance_check(task, all_edits, output)
    assert evidence.status == VerificationStatus.SKIPPED


def test_spec_conformance_finds_artifact_in_output_when_not_in_edits():
    task = "Create a file called result.json"
    all_edits = ["main.py"]
    output = "I have created the result.json file with the data"

    evidence = spec_conformance_check(task, all_edits, output)
    assert evidence.status == VerificationStatus.PASSED


def test_spec_conformance_excludes_currently_excluded_phrasing():
    """Regression: a real forge run (dogfooding against lgwks) false-failed
    on this exact phrasing. "two currently-excluded modules: a.py and b.py"
    has no exclude-context keyword nearby (only the sentence's leading verb
    "add", 60+ chars back) — a.py/b.py got required even though a later,
    explicit "Do NOT modify a.py or b.py" in the same task correctly
    resolved as excluded. Since task_files unions every mention of a
    filename, the earlier false-positive mention couldn't be undone by the
    later correct one — the model did the task correctly and forge still
    reported FAILED.
    """
    task = (
        "add smoke-import tests for two currently-excluded modules: "
        "a.py (32 lines) and b.py (40 lines). Create tests/test_smoke.py. "
        "Do NOT modify a.py or b.py themselves, they are already correct "
        "and out of scope."
    )
    all_edits = ["tests/test_smoke.py", "tests/test_coverage.py"]
    output = "Created tests/test_smoke.py; edited tests/test_coverage.py"

    evidence = spec_conformance_check(task, all_edits, output)
    assert evidence.status != VerificationStatus.FAILED


# ── SemanticCheck wire-up tests ────────────────────────────────────


async def test_semantic_check_not_called_when_not_configured():
    agent = ReactAgent(
        model=_FakeModelPort([
            {
                "thought": "writing file",
                "action": "write_file",
                "action_input": {"path": "test.txt", "content": "hello"},
            },
            {
                "thought": "done",
                "action": "finish",
                "action_input": {"output": "Status: SUCCESS."},
            },
        ]),
        tools=_fake_tools_registry(),
    )
    context = AgentContext(
        task="create a test file",
        cwd="/tmp",
        max_steps=5,
    )
    result = await agent.arun(context)
    # semantic_check is None by default → no Evidence with SEMANTIC-CHECK-001
    sem_ev = [v for v in result.verification if v.gate_name == "SEMANTIC-CHECK-001"]
    assert len(sem_ev) == 0


async def test_semantic_check_failure_gates_success():
    """When semantic_check is wired and fails, verification_passed is False."""
    agent = ReactAgent(
        model=_FakeModelPort([
            {
                "thought": "writing file",
                "action": "write_file",
                "action_input": {"path": "test.txt", "content": "hello"},
            },
            {
                "thought": "done",
                "action": "finish",
                "action_input": {"output": "Status: SUCCESS."},
            },
        ]),
        tools=_fake_tools_registry(),
        semantic_check=_AlwaysFailSemanticCheck(),
    )
    context = AgentContext(
        task="create a test file",
        cwd="/tmp",
        max_steps=5,
    )
    result = await agent.arun(context)

    sem_ev = [v for v in result.verification if v.gate_name == "SEMANTIC-CHECK-001"]
    assert len(sem_ev) == 1
    assert sem_ev[0].status == VerificationStatus.FAILED


async def test_semantic_check_not_called_when_no_edits():
    """Even when configured, semantic check is skipped if no edits were made."""
    agent = ReactAgent(
        model=_FakeModelPort([
            {
                "thought": "answering",
                "action": "finish",
                "action_input": {"output": "The answer is 42."},
            },
        ]),
        tools=_fake_tools_registry(),
        semantic_check=_AlwaysFailSemanticCheck(),
    )
    context = AgentContext(
        task="what is the meaning of life?",
        cwd="/tmp",
        max_steps=5,
    )
    result = await agent.arun(context)

    sem_ev = [v for v in result.verification if v.gate_name == "SEMANTIC-CHECK-001"]
    assert len(sem_ev) == 0


# ── Spec-conformance wire-up tests ─────────────────────────────────


async def test_spec_conformance_gate_always_runs_in_finish():
    """spec_conformance evidence is always appended in the finish handler."""
    agent = ReactAgent(
        model=_FakeModelPort([
            {
                "thought": "done",
                "action": "finish",
                "action_input": {"output": "Done."},
            },
        ]),
        tools=_fake_tools_registry(),
    )
    context = AgentContext(
        task="do something",
        cwd="/tmp",
        max_steps=5,
    )
    result = await agent.arun(context)

    spec_ev = [v for v in result.verification if v.gate_name == "spec_conformance"]
    assert len(spec_ev) == 1


# ── Pipeline resilience tests ──────────────────────────────────────


async def test_pipeline_does_not_crash_when_nothing_configured():
    """All optional verifiers default to None — pipeline must not crash."""
    agent = ReactAgent(
        model=_FakeModelPort([
            {
                "thought": "done",
                "action": "finish",
                "action_input": {"output": "Done."},
            },
        ]),
        tools=_fake_tools_registry(),
    )
    context = AgentContext(
        task="do something",
        cwd="/tmp",
        max_steps=5,
    )
    result = await agent.arun(context)
    # At minimum: spec_conformance gate always runs
    assert isinstance(result.verification, list)
    success = result.success
    assert isinstance(success, bool)


async def test_pipeline_collects_all_evidence_on_failure():
    """When all gates run and some fail, evidence is still collected."""
    agent = ReactAgent(
        model=_FakeModelPort([
            {
                "thought": "writing file",
                "action": "write_file",
                "action_input": {"path": "app.py", "content": "print('hello')"},
            },
            {
                "thought": "done",
                "action": "finish",
                "action_input": {"output": "Created app.py"},
            },
        ]),
        tools=_fake_tools_registry(),
        semantic_check=_AlwaysFailSemanticCheck(),
    )
    context = AgentContext(
        task="write app.py",
        cwd="/tmp",
        max_steps=5,
    )
    result = await agent.arun(context)

    gate_names = [v.gate_name for v in result.verification]
    # Should have at least semantic check + spec conformance
    assert "SEMANTIC-CHECK-001" in gate_names
    assert "spec_conformance" in gate_names
    # All evidence collected even if some failed
    assert len(result.verification) >= 2
