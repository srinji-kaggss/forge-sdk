"""Ollama provider — satisfies ModelPort protocol.

Supports both local Ollama (default) and Ollama Cloud.
Local: OllamaProvider(model="gemma3:4b") — uses http://localhost:11434
Cloud: OllamaProvider(model="gemma3:4b", base_url="https://ollama.com", api_key="...")
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from forge_sdk.models.types import ModelChunk, ModelResponse, Usage


class OllamaProvider:
    """Ollama API provider. Defaults to local Ollama server."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "http://localhost:11434",
        model: str = "gemma3:4b",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=120.0)
        # Ollama cloud uses the OpenAI-compatible endpoint
        # Read from env if not explicitly provided (Bug #3 fix)
        self._api_key = api_key or os.environ.get("OLLAMA_API_KEY", "")

    @property
    def name(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "ollama"

    @property
    def context_window(self) -> int:
        return 128_000

    @property
    def max_output(self) -> int:
        return 32_000

    @property
    def supports_reasoning(self) -> bool:
        return False

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_payload(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int | None,
        stop: list[str] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop
        return payload

    def _parse_response(self, data: dict[str, Any]) -> ModelResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        reasoning = message.get("reasoning_content") or message.get("thinking")
        usage_data = data.get("usage", {})
        return ModelResponse(
            content=content,
            reasoning=reasoning,
            model=data.get("model", self._model),
            provider="ollama",
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", ""),
            raw=data,
        )

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> ModelResponse:
        payload = self._build_payload(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop
        )
        resp = self._client.post(
            f"{self._base_url}/v1/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    def complete_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> list[ModelChunk]:
        payload = self._build_payload(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop
        )
        payload["stream"] = True
        resp = self._client.post(
            f"{self._base_url}/v1/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        chunks: list[ModelChunk] = []
        for line in resp.text.splitlines():
            if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                continue
            data = json.loads(line[6:])
            choice = data.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            chunks.append(
                ModelChunk(
                    delta=delta.get("content", ""),
                    reasoning_delta=delta.get("reasoning_content", "") or delta.get("thinking", ""),
                    finish_reason=choice.get("finish_reason"),
                )
            )
        return chunks
