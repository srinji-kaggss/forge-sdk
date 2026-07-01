"""Model response and chunk types."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ModelResponse:
    """Unified response from any model provider.

    tool_calls: native provider tool/function calls, normalized to OpenAI's
    shape regardless of source API — [{"id": str, "name": str, "arguments":
    dict}, ...]. Empty when the provider wasn't given tools, doesn't support
    them, or chose to respond in plain text instead of calling a tool.
    """

    content: str
    reasoning: str | None = None
    model: str = ""
    provider: str = ""
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ModelChunk:
    """A single streaming chunk."""

    delta: str = ""
    reasoning_delta: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None


def normalize_openai_tool_calls(raw_tool_calls: list[dict] | None) -> list[dict[str, Any]]:
    """Normalize an OpenAI-shaped `message.tool_calls` array into forge's
    canonical form. Shared by every OpenAI-compatible provider (deepseek,
    openrouter) so there is one place that parses `function.arguments`
    (a JSON *string*, not an object) instead of each provider re-parsing it
    slightly differently. strict=False for the same reason react.py's
    parser uses it: a model can emit an unescaped control character inside
    an argument string without that being a real structural error.
    """
    if not raw_tool_calls:
        return []
    normalized = []
    for call in raw_tool_calls:
        function = call.get("function", {})
        arguments_str = function.get("arguments", "{}")
        try:
            arguments = json.loads(arguments_str, strict=False)
        except (json.JSONDecodeError, ValueError):
            arguments = {}
        normalized.append(
            {
                "id": call.get("id", ""),
                "name": function.get("name", ""),
                "arguments": arguments if isinstance(arguments, dict) else {},
            }
        )
    return normalized
