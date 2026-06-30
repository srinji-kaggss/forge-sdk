"""Forge SDK: Agent-agnostic framework for building, observing, and evaluating AI coding agents.

Quick start:
    from forge_sdk import ReactAgent, OllamaProvider, ToolRegistry, AgentContext
    from forge_sdk.tools.filesystem import FILE_TOOLS

    model = OllamaProvider(model="gemma3:4b")
    tools = ToolRegistry()
    for t in FILE_TOOLS:
        tools.register(t)
    agent = ReactAgent(model=model, tools=tools)
    result = agent.run(AgentContext(task="Read /etc/hostname"))
"""

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext, AgentResult, AgentStep
from forge_sdk.audit import AuditLog
from forge_sdk.config import ForgeConfig
from forge_sdk.models.ollama import OllamaProvider
from forge_sdk.models.port import ModelPort
from forge_sdk.models.types import ModelChunk, ModelResponse
from forge_sdk.tools import ToolResult, ToolSpec
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.tracing.span import Span, SpanKind
from forge_sdk.tracing.tracer import Tracer

__all__ = [
    # Core agent
    "ReactAgent",
    "AgentContext",
    "AgentStep",
    "AgentResult",
    # Models
    "OllamaProvider",
    "ModelPort",
    "ModelResponse",
    "ModelChunk",
    # Tools
    "ToolSpec",
    "ToolResult",
    "ToolRegistry",
    # Observability
    "Tracer",
    "Span",
    "SpanKind",
    "AuditLog",
    # Config
    "ForgeConfig",
]
