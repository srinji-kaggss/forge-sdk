"""Regression test for a live crash: some providers return content=None on a
tool-only turn (no text). That crashed the whole run with an unhandled
TypeError at response.content[:500] (the tracer span), losing all prior
work for the step with no AgentResult at all — not even an honest failure.

Run with: pytest tests/test_none_content_response.py -v
"""

from __future__ import annotations

import json

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.models.types import ModelResponse
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry


class _NoneContentThenFinishModel:
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
            return ModelResponse(content=None)
        body = {"thought": "done", "action": "finish", "action_input": {"output": "ok"}}
        return ModelResponse(content=json.dumps(body))


def _write_file_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for tool in FILE_TOOLS:
        reg.register(tool)
    return reg


async def test_arun_survives_none_content_response(tmp_path):
    agent = ReactAgent(model=_NoneContentThenFinishModel(), tools=_write_file_registry())
    context = AgentContext(task="say hello", cwd=str(tmp_path), max_steps=5)

    result = await agent.arun(context)

    assert result.success is True
