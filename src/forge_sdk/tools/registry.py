"""Typed tool registry — strategy pattern over conditionals."""

from __future__ import annotations

from typing import Any

from forge_sdk.tools.types import ToolSpec


class ToolRegistry:
    """Registry of tools. Each tool is a strategy with a stable_id key."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.stable_id] = tool

    def get(self, stable_id: str) -> ToolSpec | None:
        return self._tools.get(stable_id)

    def get_by_name(self, name: str) -> ToolSpec | None:
        for tool in self._tools.values():
            if tool.name == name:
                return tool
        return None

    def available(self, context: Any = None) -> list[ToolSpec]:
        """Return all tools whose `applies()` predicate passes."""
        return [t for t in self._tools.values() if t.applies(context)]

    def to_prompt_schemas(self, context: Any = None) -> list[dict]:
        """Convert available tools to OpenAI function-calling schemas."""
        return [t.to_prompt_schema() for t in self.available(context)]

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())
