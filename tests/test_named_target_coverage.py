"""Regression tests for the partial-completion-over-claim detector (v0.5.2).

See blackbox2/PLAYBOOK-forge-fanout.md §9 and CHANGELOG.md [0.5.2] for the
real-world failure this is modeled on: two forge runs against lgwks issue
#349 each named two files to edit, wrote only one, and still reported full
success — because the existing zero-edits safety net only fires when zero
files were touched, not when some-but-not-all were.

This is an advisory heuristic, not a hard gate (false positives are
expected and accepted — see _named_edit_targets' docstring), so these tests
check both directions: real omissions get flagged, and read-only mentions
of a file do not.

Run with: pytest tests/test_named_target_coverage.py -v
"""

from __future__ import annotations

import json

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.models.types import ModelResponse
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry


def _agent() -> ReactAgent:
    return ReactAgent(model=object(), tools=object())


# Modeled directly on the real prompt shape from the fan-out batch's
# Failure Class B repro (lgwks_phase, lgwks_keyvault — both qwen3-235b).
_REAL_SHAPE_TASK = (
    "First read lgwks_phase.py fully to learn the real PhaseResult field "
    "names. Create tests/test_lgwks_phase_coverage.py with two tests "
    "exercising PhaseResult and verdict_from_phases using the real field "
    "names. Then remove the 'lgwks_phase' line from the EXCLUDED dict in "
    "tests/test_module_coverage.py. Do not touch any other file. Do not "
    "modify lgwks_phase.py itself."
)


def test_named_edit_targets_excludes_read_only_mention():
    agent = _agent()
    targets = agent._named_edit_targets(_REAL_SHAPE_TASK)
    assert "lgwks_phase.py" not in targets


def test_named_edit_targets_includes_both_real_edit_targets():
    agent = _agent()
    targets = agent._named_edit_targets(_REAL_SHAPE_TASK)
    assert "tests/test_lgwks_phase_coverage.py" in targets
    assert "tests/test_module_coverage.py" in targets


def test_missing_named_targets_flags_the_real_repro_shape():
    """The actual failure: only the new test file was written, the
    EXCLUDED-list edit was silently dropped."""
    agent = _agent()
    all_edits = ["tests/test_lgwks_phase_coverage.py"]
    missing = agent._missing_named_targets(_REAL_SHAPE_TASK, all_edits)
    assert missing == ["tests/test_module_coverage.py"]


def test_missing_named_targets_empty_when_both_targets_present():
    agent = _agent()
    all_edits = ["tests/test_lgwks_phase_coverage.py", "tests/test_module_coverage.py"]
    assert agent._missing_named_targets(_REAL_SHAPE_TASK, all_edits) == []


def test_missing_named_targets_matches_on_basename_not_full_path():
    """all_edits paths are often relative to a different cwd than the task
    text assumes (e.g. './tests/x.py' vs 'tests/x.py') — match by basename
    too, not just exact string equality, or every genuine success on a
    nested path would false-positive."""
    agent = _agent()
    all_edits = ["./tests/test_lgwks_phase_coverage.py", "/abs/path/tests/test_module_coverage.py"]
    assert agent._missing_named_targets(_REAL_SHAPE_TASK, all_edits) == []


def test_missing_named_targets_never_flags_a_read_only_mention():
    """Negative control: lgwks_phase.py is mentioned but explicitly
    excluded — it must never appear in the missing list even though it's
    never in all_edits."""
    agent = _agent()
    all_edits = ["tests/test_lgwks_phase_coverage.py", "tests/test_module_coverage.py"]
    missing = agent._missing_named_targets(_REAL_SHAPE_TASK, all_edits)
    assert "lgwks_phase.py" not in missing


def test_single_target_task_with_no_omission_is_clean():
    agent = _agent()
    task = "Create tests/test_foo.py with a smoke-import test for foo.py."
    all_edits = ["tests/test_foo.py"]
    assert agent._missing_named_targets(task, all_edits) == []


class _OneOfTwoEditsModel:
    """Scripted model reproducing the real Failure Class B shape end-to-end:
    writes the first named target, then claims finish without touching the
    second named target at all."""

    name = "fake"
    provider = "fake"
    context_window = 100_000
    max_output = 4096
    supports_reasoning = False

    def __init__(self):
        self._step = 0

    def complete(self, messages, *, temperature=0.0, max_tokens=None, stop=None):
        self._step += 1
        if self._step == 1:
            body = {
                "thought": "writing the new test file",
                "action": "write_file",
                "action_input": {"path": "tests/test_foo_coverage.py", "content": "def test_x(): pass\n"},
            }
            return ModelResponse(content=json.dumps(body))
        body = {
            "thought": "done, both edits made",
            "action": "finish",
            "action_input": {"output": "Created tests/test_foo_coverage.py and updated tests/test_module_coverage.py"},
        }
        return ModelResponse(content=json.dumps(body))


def _write_file_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for tool in FILE_TOOLS:
        reg.register(tool)
    return reg


async def test_arun_flags_but_does_not_fail_a_partial_completion(tmp_path):
    """The real-world repro, end to end: model writes 1 of 2 named targets
    and claims finish. success stays True (advisory, not a hard gate — see
    module docstring) but named_targets_missing is populated and the output
    carries a visible REVIEW FLAG, so a human reviewer can't miss it."""
    model = _OneOfTwoEditsModel()
    agent = ReactAgent(model=model, tools=_write_file_registry())
    task = (
        "Create tests/test_foo_coverage.py with a test for foo.py. Then "
        "remove the 'foo' line from EXCLUDED in tests/test_module_coverage.py."
    )
    context = AgentContext(task=task, cwd=str(tmp_path), max_steps=5)

    result = await agent.arun(context)

    assert result.success is True
    assert result.named_targets_missing == ["tests/test_module_coverage.py"]
    assert "REVIEW FLAG" in result.output
    assert "tests/test_module_coverage.py" in result.output


async def test_arun_no_flag_when_all_named_targets_are_edited(tmp_path):
    model_steps = [
        json.dumps({
            "thought": "writing it",
            "action": "write_file",
            "action_input": {"path": "tests/test_foo_coverage.py", "content": "def test_x(): pass\n"},
        }),
        json.dumps({"thought": "done", "action": "finish", "action_input": {"output": "wrote the file"}}),
    ]

    class _SingleTargetModel:
        name = "fake"
        provider = "fake"
        context_window = 100_000
        max_output = 4096
        supports_reasoning = False

        def __init__(self):
            self._step = 0

        def complete(self, messages, *, temperature=0.0, max_tokens=None, stop=None):
            response = model_steps[self._step]
            self._step += 1
            return ModelResponse(content=response)

    agent = ReactAgent(model=_SingleTargetModel(), tools=_write_file_registry())
    context = AgentContext(
        task="Create tests/test_foo_coverage.py with a test for foo.py.",
        cwd=str(tmp_path),
        max_steps=5,
    )

    result = await agent.arun(context)

    assert result.success is True
    assert result.named_targets_missing == []
    assert "REVIEW FLAG" not in result.output
