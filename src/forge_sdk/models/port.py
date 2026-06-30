"""ModelPort protocol and provider registry."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from forge_sdk.models.types import ModelChunk, ModelResponse


@runtime_checkable
class ModelPort(Protocol):
    """Protocol that all model providers MUST satisfy."""

    @property
    def name(self) -> str: ...

    @property
    def provider(self) -> str: ...

    @property
    def context_window(self) -> int: ...

    @property
    def max_output(self) -> int: ...

    @property
    def supports_reasoning(self) -> bool: ...

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> ModelResponse: ...

    def complete_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> list[ModelChunk]: ...
