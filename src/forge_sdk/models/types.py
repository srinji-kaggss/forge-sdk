"""Model response and chunk types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ModelResponse:
    """Unified response from any model provider."""

    content: str
    reasoning: str | None = None
    model: str = ""
    provider: str = ""
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelChunk:
    """A single streaming chunk."""

    delta: str = ""
    reasoning_delta: str = ""
    finish_reason: str | None = None
    usage: Usage | None = None
