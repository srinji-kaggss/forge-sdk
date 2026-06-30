"""Tool types and registry.

Quick start:
    from forge_sdk.tools import ToolRegistry, get_default_tools

    tools = ToolRegistry()
    for t in get_default_tools():
        tools.register(t)
"""

from forge_sdk.tools.types import ToolResult, ToolSpec
from forge_sdk.tools.registry import ToolRegistry


def get_default_tools() -> list[ToolSpec]:
    """Return all built-in tools (filesystem + search + shell)."""
    from forge_sdk.tools.filesystem import FILE_TOOLS
    from forge_sdk.tools.search import SEARCH_TOOLS
    from forge_sdk.tools.shell import SHELL_TOOL
    return FILE_TOOLS + SEARCH_TOOLS + [SHELL_TOOL]


__all__ = ["ToolResult", "ToolSpec", "ToolRegistry", "get_default_tools"]
