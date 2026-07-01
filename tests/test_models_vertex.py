"""Tests for the Vertex AI (Gemini) model provider.

Run with: pytest tests/test_models_vertex.py -v
"""

from __future__ import annotations

import pytest

from forge_sdk.models import registry
from forge_sdk.models.vertex import VertexAuthError, VertexProvider


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict):
        self._payload = payload
        self.last_url = None
        self.last_headers = None
        self.last_json = None

    def post(self, url, *, headers, json):
        self.last_url = url
        self.last_headers = headers
        self.last_json = json
        return _FakeResponse(self._payload)


def _make_provider(monkeypatch, **kwargs) -> VertexProvider:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "lgwks-gpu-lane")
    monkeypatch.setattr(
        "forge_sdk.models.vertex._fetch_access_token", lambda: "fake-token"
    )
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
    assert "northamerica-northeast1" in provider._base_url
    assert provider._location == "northamerica-northeast1"


def test_location_env_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "northamerica-northeast2")
    provider = _make_provider(monkeypatch)
    assert "northamerica-northeast2" in provider._base_url


def test_to_gemini_contents_splits_system_and_maps_roles():
    messages = [
        {"role": "system", "content": "You are a reviewer."},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    system_instruction, contents = VertexProvider._to_gemini_contents(messages)
    assert system_instruction == {"parts": [{"text": "You are a reviewer."}]}
    assert contents == [
        {"role": "user", "parts": [{"text": "hello"}]},
        {"role": "model", "parts": [{"text": "hi there"}]},
    ]


def test_to_gemini_contents_no_system_messages():
    messages = [{"role": "user", "content": "hello"}]
    system_instruction, contents = VertexProvider._to_gemini_contents(messages)
    assert system_instruction is None
    assert contents == [{"role": "user", "parts": [{"text": "hello"}]}]


def test_complete_parses_response_and_sends_expected_payload(monkeypatch):
    provider = _make_provider(monkeypatch)
    fake_client = _FakeClient(
        {
            "candidates": [
                {
                    "content": {"parts": [{"text": "the answer"}], "role": "model"},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }
    )
    provider._client = fake_client

    response = provider.complete(
        [{"role": "user", "content": "what is 2+2"}], temperature=0.2, max_tokens=100
    )

    assert response.content == "the answer"
    assert response.provider == "vertex"
    assert response.finish_reason == "STOP"
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15
    assert fake_client.last_url.endswith(":generateContent")
    assert fake_client.last_headers["Authorization"] == "Bearer fake-token"
    assert fake_client.last_json["generationConfig"]["temperature"] == 0.2
    assert fake_client.last_json["generationConfig"]["maxOutputTokens"] == 100


def test_complete_handles_empty_candidates(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider._client = _FakeClient({"candidates": []})

    response = provider.complete([{"role": "user", "content": "hi"}])

    assert response.content == ""
    assert response.finish_reason == ""


def test_complete_stream_wraps_single_chunk(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider._client = _FakeClient(
        {
            "candidates": [
                {
                    "content": {"parts": [{"text": "streamed"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {},
        }
    )

    chunks = provider.complete_stream([{"role": "user", "content": "hi"}])

    assert len(chunks) == 1
    assert chunks[0].delta == "streamed"
    assert chunks[0].finish_reason == "STOP"


def test_access_token_is_cached_across_calls(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "lgwks-gpu-lane")
    call_count = {"n": 0}

    def _fake_fetch():
        call_count["n"] += 1
        return f"token-{call_count['n']}"

    monkeypatch.setattr("forge_sdk.models.vertex._fetch_access_token", _fake_fetch)
    provider = VertexProvider()

    first = provider._access_token()
    second = provider._access_token()

    assert first == second == "token-1"
    assert call_count["n"] == 1
