"""Tool types — ToolSpec and ToolResult."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSpec:
    """A registered tool with schema and handler."""

    name: str
    description: str
    input_schema: dict  # JSON Schema
    output_schema: dict  # JSON Schema
    stable_id: str  # e.g. TOOL-FILE-READ-001
    handler: Callable[..., Awaitable[ToolResult]]

    def applies(self, context: Any = None) -> bool:
        """Override to conditionally enable/disable this tool."""
        return True

    def to_prompt_schema(self) -> dict:
        """Convert to OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
