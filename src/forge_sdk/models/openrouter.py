"""OpenRouter provider — satisfies ModelPort protocol."""

from __future__ import annotations

import os
from typing import Any

import httpx

from forge_sdk.models.types import ModelChunk, ModelResponse, Usage, normalize_openai_tool_calls


class OpenRouterProvider:
    """OpenRouter API provider (openrouter.ai)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api",
        model: str = "deepseek/deepseek-v4-pro",
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=120.0)

    @property
    def name(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "openrouter"

    @property
    def context_window(self) -> int:
        return 1_000_000

    @property
    def max_output(self) -> int:
        return 384_000

    @property
    def supports_reasoning(self) -> bool:
        return True

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/forge-sdk",
            "X-Title": "Forge SDK",
        }

    def _build_payload(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int | None,
        stop: list[str] | None,
        tools: list[dict] | None = None,
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
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
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
            provider="openrouter",
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", ""),
            raw=data,
            tool_calls=normalize_openai_tool_calls(message.get("tool_calls")),
        )

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> ModelResponse:
        payload = self._build_payload(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop, tools=tools
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
        tools: list[dict] | None = None,
    ) -> list[ModelChunk]:
        payload = self._build_payload(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop, tools=tools
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
            import json

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
