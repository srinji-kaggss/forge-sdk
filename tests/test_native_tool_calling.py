"""Regression tests for native provider tool-calling.

Root cause this replaces: forge asked models to emit free-text JSON and
regex-parsed it (_PARSE_STRATEGIES), which is why every parse bug found
this session (literal control chars, unescaped quotes, XML instead of
JSON, phantom finish-without-write) was reachable at all. Native
tool-calling uses each provider's own constrained decoding, which
guarantees a schema-valid call — there is nothing left for forge to
regex-parse when the provider returns one.

Run with: pytest tests/test_native_tool_calling.py -v
"""

from __future__ import annotations

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.models.types import ModelResponse, normalize_openai_tool_calls
from forge_sdk.models.vertex import VertexProvider
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry


# ── normalize_openai_tool_calls ─────────────────────────────────────


def test_normalize_openai_tool_calls_parses_arguments_string():
    raw = [{"id": "call_1", "function": {"name": "write_file", "arguments": '{"path": "x.txt"}'}}]
    result = normalize_openai_tool_calls(raw)
    assert result == [{"id": "call_1", "name": "write_file", "arguments": {"path": "x.txt"}}]


def test_normalize_openai_tool_calls_tolerates_literal_control_chars():
    """Same live bug class as react.py's strict=False fix, but for the
    arguments string specifically."""
    raw = [{"id": "1", "function": {"name": "write_file", "arguments": '{"content": "line1\nline2"}'}}]
    result = normalize_openai_tool_calls(raw)
    assert result[0]["arguments"]["content"] == "line1\nline2"


def test_normalize_openai_tool_calls_empty_when_none():
    assert normalize_openai_tool_calls(None) == []
    assert normalize_openai_tool_calls([]) == []


def test_normalize_openai_tool_calls_defaults_to_empty_dict_on_malformed_json():
    raw = [{"id": "1", "function": {"name": "write_file", "arguments": "not json at all {"}}]
    result = normalize_openai_tool_calls(raw)
    assert result == [{"id": "1", "name": "write_file", "arguments": {}}]


# ── Vertex/Gemini native tool-calling translation ───────────────────


def test_vertex_converts_openai_tools_to_gemini_declarations():
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        }
    ]
    declarations = VertexProvider._openai_tools_to_gemini_declarations(openai_tools)
    assert declarations == [
        {
            "functionDeclarations": [
                {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                }
            ]
        }
    ]


def test_vertex_build_payload_includes_tools_when_provided(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setattr("forge_sdk.models.vertex._fetch_access_token", lambda: "fake-token")
    provider = VertexProvider()
    tools = [{"type": "function", "function": {"name": "finish", "parameters": {}}}]

    payload = provider._build_payload(
        [{"role": "user", "content": "hi"}], temperature=0.0, max_tokens=None, stop=None, tools=tools
    )

    assert payload["tools"] == [{"functionDeclarations": [{"name": "finish", "description": "", "parameters": {}}]}]


def test_vertex_parse_response_extracts_function_call(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setattr("forge_sdk.models.vertex._fetch_access_token", lambda: "fake-token")
    provider = VertexProvider()
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [{"functionCall": {"name": "write_file", "args": {"path": "x.txt", "content": "hi"}}}]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {},
    }

    response = provider._parse_response(data)

    assert response.tool_calls == [{"id": "", "name": "write_file", "arguments": {"path": "x.txt", "content": "hi"}}]
    assert response.content == ""  # no text parts, only a functionCall part


def test_vertex_parse_response_no_tool_calls_when_text_only(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setattr("forge_sdk.models.vertex._fetch_access_token", lambda: "fake-token")
    provider = VertexProvider()
    data = {
        "candidates": [{"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}],
        "usageMetadata": {},
    }

    response = provider._parse_response(data)

    assert response.tool_calls == []
    assert response.content == "hello"


# ── End-to-end: ReactAgent dispatches directly from tool_calls ─────


class _NativeToolCallModel:
    """Fake provider that returns a native tool_calls response instead of
    free-text JSON — proves the agent loop dispatches from it directly
    without ever touching _parse_response (no JSON in `content` at all,
    so any text-parsing path would fail outright)."""

    name = "fake-native"
    provider = "fake"
    context_window = 100_000
    max_output = 4096
    supports_reasoning = False

    def __init__(self):
        self._step = 0
        self.received_messages: list[list[dict]] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=None, stop=None, tools=None):
        self.received_messages.append(list(messages))  # snapshot -- react.py mutates the same list in place
        self._step += 1
        if self._step == 1:
            return ModelResponse(
                content="",
                tool_calls=[
                    {"id": "1", "name": "write_file", "arguments": {"path": "test.txt", "content": "hello"}}
                ],
            )
        return ModelResponse(
            content="",
            tool_calls=[{"id": "2", "name": "finish", "arguments": {"output": "Status: SUCCESS."}}],
        )


def _fake_tools_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for tool in FILE_TOOLS:
        reg.register(tool)
    return reg


async def test_agent_dispatches_directly_from_native_tool_calls(tmp_path):
    """The model's response.content is empty (no JSON at all) on both
    steps -- any text-parsing path would produce garbage or a parse
    failure. Assert on the dispatch itself, not overall `success` (that
    also depends on the unrelated verify-gate, which has nothing to detect
    in a bare tmp dir with no Cargo.toml/pyproject.toml)."""
    agent = ReactAgent(model=_NativeToolCallModel(), tools=_fake_tools_registry())
    context = AgentContext(task="create a test file", cwd=str(tmp_path), max_steps=5)

    result = await agent.arun(context)

    assert (tmp_path / "test.txt").read_text() == "hello"
    assert result.edits_made == ["test.txt"]
    assert result.steps[0].action == "write_file"
    assert result.steps[1].action == "finish"
    assert result.steps[1].is_final is True


async def test_native_tool_call_leaves_a_readable_trace_in_message_history(tmp_path):
    """Live bug: a native tool call leaves response.content empty, so the
    assistant turn recorded in `messages` was blank -- on the next turn the
    model had no way to tell "Tool output: ..." was the result of its OWN
    prior action, and in a real run this produced a stuck loop re-issuing
    the exact same call the LoopGuard had already blocked. Assert the
    second complete() call's message history contains a real record of
    what was called, not an empty assistant turn.
    """
    model = _NativeToolCallModel()
    agent = ReactAgent(model=model, tools=_fake_tools_registry())
    context = AgentContext(task="create a test file", cwd=str(tmp_path), max_steps=5)

    await agent.arun(context)

    assert len(model.received_messages) == 2
    second_call_messages = model.received_messages[1]
    assistant_turns = [m for m in second_call_messages if m["role"] == "assistant"]
    assert len(assistant_turns) == 1
    assert assistant_turns[0]["content"] != ""
    assert "write_file" in assistant_turns[0]["content"]


def test_tool_schemas_includes_synthetic_finish_tool():
    agent = ReactAgent(model=object(), tools=_fake_tools_registry())
    schemas = agent._tool_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "finish" in names
    assert "write_file" in names
