"""Regression tests for the malformed-action-parse bug found while
ground-truthing forge's trust level before delegating real lgwks work to it:
a model response that LOOKS like a tool call attempt ("Tool: write_file\\n
Arguments: {...}") but isn't valid {"action": ...} JSON was silently
classified by _parse_response's fallback as a legitimate `finish`, so the
agent reported Status: SUCCESS with 0 tool calls and 0 files written.

Run with: pytest tests/test_parse_failure_retry.py -v
"""

from __future__ import annotations

import json

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.models.types import ModelResponse
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry

# The exact real-world malformed response observed in production: braces
# are present (so a JSON strategy claims applicability) but the payload has
# no top-level "action" key.
MALFORMED_TOOL_CALL = (
    'Tool: write_file\nArguments: {"path": "out.py", "content": "x = 1\\n"}'
)


def _agent() -> ReactAgent:
    return ReactAgent(model=object(), tools=object())


def test_parse_response_flags_malformed_tool_call_not_finish():
    """The core fix: braces-but-no-action content must not silently become
    a 'finish' action."""
    agent = _agent()
    parsed = agent._parse_response(MALFORMED_TOOL_CALL)
    assert parsed["action"] == "__parse_failed__"


def test_parse_response_genuine_prose_finish_unaffected():
    """A real finish message with no braces at all must still finish
    normally — the fix must not break legitimate completions."""
    agent = _agent()
    parsed = agent._parse_response("I have completed the task, no changes were needed.")
    assert parsed["action"] == "finish"


class _MalformedThenRecoversModel:
    """Scripted model: malformed tool-call text, then (after the harness's
    corrective nudge) a valid write_file call, then finish."""

    name = "fake"
    provider = "fake"
    context_window = 100_000
    max_output = 4096
    supports_reasoning = False

    def __init__(self):
        self._step = 0

    def complete(self, messages, *, temperature=0.0, max_tokens=None, stop=None, tools=None):
        self._step += 1
        if self._step == 1:
            return ModelResponse(content=MALFORMED_TOOL_CALL)
        if self._step == 2:
            body = {
                "thought": "retrying with correct format",
                "action": "write_file",
                "action_input": {"path": "out.py", "content": "x = 1\n"},
            }
            return ModelResponse(content=json.dumps(body))
        body = {"thought": "done", "action": "finish", "action_input": {"output": "wrote out.py"}}
        return ModelResponse(content=json.dumps(body))


class _AlwaysMalformedModel:
    """Scripted model: never produces a parseable action."""

    name = "fake"
    provider = "fake"
    context_window = 100_000
    max_output = 4096
    supports_reasoning = False

    def complete(self, messages, *, temperature=0.0, max_tokens=None, stop=None, tools=None):
        return ModelResponse(content=MALFORMED_TOOL_CALL)


def _write_file_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for tool in FILE_TOOLS:
        reg.register(tool)
    return reg


async def test_arun_recovers_after_one_malformed_response(tmp_path):
    """End-to-end: the agent must not report SUCCESS on the malformed step,
    but must recover via the corrective retry and genuinely write the file."""
    model = _MalformedThenRecoversModel()
    agent = ReactAgent(model=model, tools=_write_file_registry())
    context = AgentContext(task="add out.py", cwd=str(tmp_path), max_steps=5)

    result = await agent.arun(context)

    assert result.success is True
    assert (tmp_path / "out.py").read_text() == "x = 1\n"


async def test_arun_fails_honestly_when_model_never_recovers(tmp_path):
    """Before the fix, this exact scenario (and the real repro it's modeled
    on) reported Status: SUCCESS despite zero tool calls and zero files
    written. Now it must report failure, not a false positive."""
    model = _AlwaysMalformedModel()
    agent = ReactAgent(model=model, tools=_write_file_registry())
    context = AgentContext(task="add out.py", cwd=str(tmp_path), max_steps=5)

    result = await agent.arun(context)

    assert result.success is False
    assert not (tmp_path / "out.py").exists()
