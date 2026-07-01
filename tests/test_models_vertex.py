"""Tests for the Vertex AI (Gemini) model provider, built on the official
google-genai SDK.

Run with: pytest tests/test_models_vertex.py -v
"""

from __future__ import annotations

import pytest
from google.genai import types as genai_types

from forge_sdk.models import registry
from forge_sdk.models.vertex import VertexAuthError, VertexProvider


def _make_provider(monkeypatch, **kwargs) -> VertexProvider:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "lgwks-gpu-lane")
    return VertexProvider(**kwargs)


def test_vertex_registered_in_registry():
    assert "vertex" in registry.available()
    assert registry.get("vertex") is VertexProvider


def test_requires_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(VertexAuthError):
        VertexProvider()


def test_defaults_to_montreal_region(monkeypatch):
    provider = _make_provider(monkeypatch)
    assert provider._location == "northamerica-northeast1"


def test_location_env_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "northamerica-northeast2")
    provider = _make_provider(monkeypatch)
    assert provider._location == "northamerica-northeast2"


def test_to_gemini_contents_splits_system_and_maps_roles():
    messages = [
        {"role": "system", "content": "You are a reviewer."},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    system_instruction, contents = VertexProvider._to_gemini_contents(messages)
    assert system_instruction == "You are a reviewer."
    assert contents == [
        {"role": "user", "parts": [{"text": "hello"}]},
        {"role": "model", "parts": [{"text": "hi there"}]},
    ]


def test_to_gemini_contents_no_system_messages():
    messages = [{"role": "user", "content": "hello"}]
    system_instruction, contents = VertexProvider._to_gemini_contents(messages)
    assert system_instruction is None
    assert contents == [{"role": "user", "parts": [{"text": "hello"}]}]


def test_openai_tools_to_gemini_tool_converts_schema():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        }
    ]
    tool = VertexProvider._openai_tools_to_gemini_tool(tools)
    assert len(tool.function_declarations) == 1
    decl = tool.function_declarations[0]
    assert decl.name == "read_file"
    assert decl.description == "Read a file"


def _fake_response(*, text: str = "", function_calls: list | None = None, finish_reason=genai_types.FinishReason.STOP):
    parts = []
    if text:
        parts.append(genai_types.Part(text=text))
    for name, args in function_calls or []:
        parts.append(genai_types.Part(function_call=genai_types.FunctionCall(name=name, args=args)))
    return genai_types.GenerateContentResponse(
        candidates=[
            genai_types.Candidate(
                content=genai_types.Content(role="model", parts=parts) if parts else None,
                finish_reason=finish_reason,
            )
        ],
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10, candidates_token_count=5, total_token_count=15
        ),
    )


def test_complete_parses_text_response(monkeypatch):
    provider = _make_provider(monkeypatch)
    monkeypatch.setattr(
        provider._client.models, "generate_content", lambda **kwargs: _fake_response(text="the answer")
    )

    response = provider.complete([{"role": "user", "content": "what is 2+2"}])

    assert response.content == "the answer"
    assert response.provider == "vertex"
    assert response.finish_reason == "STOP"
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15
    assert response.tool_calls == []


def test_complete_parses_function_call_response(monkeypatch):
    provider = _make_provider(monkeypatch)
    monkeypatch.setattr(
        provider._client.models,
        "generate_content",
        lambda **kwargs: _fake_response(function_calls=[("write_file", {"path": "x.txt", "content": "hi"})]),
    )

    response = provider.complete([{"role": "user", "content": "write a file"}])

    assert response.content == ""
    assert response.tool_calls == [{"id": "", "name": "write_file", "arguments": {"path": "x.txt", "content": "hi"}}]


def test_complete_handles_empty_candidates(monkeypatch):
    provider = _make_provider(monkeypatch)
    empty = genai_types.GenerateContentResponse(candidates=[], usage_metadata=None)
    monkeypatch.setattr(provider._client.models, "generate_content", lambda **kwargs: empty)

    response = provider.complete([{"role": "user", "content": "hi"}])

    assert response.content == ""
    assert response.finish_reason == ""
    assert response.usage.prompt_tokens == 0


def test_complete_passes_tools_and_system_instruction_through(monkeypatch):
    provider = _make_provider(monkeypatch)
    captured = {}

    def fake_generate_content(**kwargs):
        captured.update(kwargs)
        return _fake_response(text="ok")

    monkeypatch.setattr(provider._client.models, "generate_content", fake_generate_content)
    tools = [{"type": "function", "function": {"name": "finish", "parameters": {}}}]

    provider.complete(
        [{"role": "system", "content": "be terse"}, {"role": "user", "content": "hi"}],
        temperature=0.2,
        max_tokens=100,
        tools=tools,
    )

    assert captured["model"] == "gemini-2.5-flash"
    config = captured["config"]
    assert config.temperature == 0.2
    assert config.max_output_tokens == 100
    assert config.system_instruction == "be terse"
    assert len(config.tools) == 1
    assert config.tools[0].function_declarations[0].name == "finish"


def test_complete_stream_wraps_single_chunk(monkeypatch):
    provider = _make_provider(monkeypatch)
    monkeypatch.setattr(
        provider._client.models, "generate_content", lambda **kwargs: _fake_response(text="streamed")
    )

    chunks = provider.complete_stream([{"role": "user", "content": "hi"}])

    assert len(chunks) == 1
    assert chunks[0].delta == "streamed"
    assert chunks[0].finish_reason == "STOP"
