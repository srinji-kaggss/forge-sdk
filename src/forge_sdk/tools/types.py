"""Tool types — ToolSpec and ToolResult.

Designed for AI consumption: structured error recovery, token efficiency,
and AI-native descriptions (firecrawl pattern).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool execution — data for reasoning, not rendering.

    For AI consumers:
    - output: the actual data (stripped of nulls/empty values)
    - error: structured error with recovery guidance
    - metadata: provenance, confidence, suggested_next_actions
    """

    success: bool
    output: str
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def as_message(self) -> str:
        """Format for AI consumption — clean, token-efficient."""
        if self.success:
            return self.output
        parts = [f"Tool failed: {self.error}"]
        if self.metadata.get("suggestion"):
            parts.append(f"Try: {self.metadata['suggestion']}")
        if self.metadata.get("candidates"):
            parts.append(f"Alternatives: {self.metadata['candidates']}")
        return "\n".join(parts)


@dataclass
class ToolSpec:
    """A registered tool with schema and handler.

    AI-native description pattern (from firecrawl research):
    - description: what it does + when to use + when NOT to use + common mistakes
    - input_schema: JSON Schema with examples
    - output_schema: what the AI should expect back
    - stable_id: deterministic ID for tracking across runs
    """

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
