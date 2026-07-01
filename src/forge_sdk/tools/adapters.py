"""Tool adapters — bridge between lgwks native tools and forge ToolSpec.

lgwks tools are plain async functions: `async def tool_fn(args: dict) -> dict`
forge tools are ToolSpec with stable_id, name, description, handler.
This adapter bridges the two.
"""

from __future__ import annotations

import logging
import shlex
from collections.abc import Awaitable, Callable
from typing import Any

from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.tools.types import ToolResult, ToolSpec


class LgwksToolAdapter:
    """Wraps an lgwks native tool function as a forge ToolSpec.

    lgwks tools return plain dicts: {"success": bool, "output": str, ...}
    This adapter converts that to a ToolResult.
    """

    def __init__(
        self,
        stable_id: str,
        name: str,
        description: str,
        lgwks_fn: Callable[..., Awaitable[dict]],
        input_schema: dict | None = None,
        output_schema: dict | None = None,
    ) -> None:
        self._stable_id = stable_id
        self._name = name
        self._description = description
        self._fn = lgwks_fn
        self._input_schema = input_schema or {
            "type": "object",
            "properties": {},
        }
        self._output_schema = output_schema or {
            "type": "object",
            "properties": {
                "output": {"type": "string"},
            },
        }

    def to_tool_spec(self) -> ToolSpec:
        """Convert to forge ToolSpec."""
        fn = self._fn
        _log = logging.getLogger("forge.tools.adapters")

        async def handler(**kwargs: Any) -> ToolResult:
            try:
                # Sanitize shell commands to prevent injection
                if "command" in kwargs:
                    command = kwargs["command"]
                    _log.warning("SHELL COMMAND: %s", command)
                    try:
                        kwargs["command"] = shlex.split(command)
                        kwargs["shell"] = False
                    except ValueError as exc:
                        return ToolResult(
                            success=False,
                            output="",
                            error=f"Command parse failed (unbalanced quotes): {exc}. "
                            f"Fix the quoting. shell=True fallback is disabled for security.",
                            metadata={"command": command, "blocked": True},
                        )

                result = await fn(**kwargs)
                return ToolResult(
                    success=result.get("success", True),
                    output=result.get("output", str(result)),
                    error=str(result.get("error", "")),
                    metadata=result,
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=str(e),
                    metadata={"exception": type(e).__name__},
                )

        return ToolSpec(
            stable_id=self._stable_id,
            name=self._name,
            description=self._description,
            input_schema=self._input_schema,
            output_schema=self._output_schema,
            handler=handler,
        )


def wrap_lgwks_file_tools() -> list[ToolSpec]:
    """Wrap lgwks file tools as forge ToolSpecs."""
    try:
        from lgwks import files as lgwks_files  # pyright: ignore[reportMissingImports]
    except ImportError:
        return []

    adapters: list[ToolSpec] = []
    tool_defs = [
        (
            "LGWKS-FILE-READ-001",
            "lgwks_read_file",
            "Read file content via lgwks",
            getattr(lgwks_files, "read_file", None),
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                },
                "required": ["path"],
            },
        ),
        (
            "LGWKS-FILE-WRITE-001",
            "lgwks_write_file",
            "Write file content via lgwks",
            getattr(lgwks_files, "write_file", None),
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        ),
        (
            "LGWKS-FILE-LIST-001",
            "lgwks_list_dir",
            "List directory contents via lgwks",
            getattr(lgwks_files, "list_dir", None),
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                },
            },
        ),
    ]

    for stable_id, name, desc, fn, schema in tool_defs:
        if fn is not None:
            adapters.append(
                LgwksToolAdapter(
                    stable_id=stable_id,
                    name=name,
                    description=desc,
                    lgwks_fn=fn,
                    input_schema=schema,
                ).to_tool_spec()
            )

    return adapters


def wrap_lgwks_shell_tools() -> list[ToolSpec]:
    """Wrap lgwks shell tools as forge ToolSpecs."""
    try:
        from lgwks import do as lgwks_do  # pyright: ignore[reportMissingImports]
    except ImportError:
        return []

    adapters: list[ToolSpec] = []
    run_fn = getattr(lgwks_do, "run", None)
    if run_fn is not None:
        adapters.append(
            LgwksToolAdapter(
                stable_id="LGWKS-SHELL-001",
                name="lgwks_shell",
                description="Execute shell command via lgwks",
                lgwks_fn=run_fn,
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute",
                        },
                    },
                    "required": ["command"],
                },
            ).to_tool_spec()
        )

    return adapters


def wrap_lgwks_search_tools() -> list[ToolSpec]:
    """Wrap lgwks search tools as forge ToolSpecs."""
    try:
        from lgwks import search as lgwks_search  # pyright: ignore[reportMissingImports]
    except ImportError:
        return []

    adapters: list[ToolSpec] = []
    search_fn = getattr(lgwks_search, "search", None)
    if search_fn is not None:
        adapters.append(
            LgwksToolAdapter(
                stable_id="LGWKS-SEARCH-001",
                name="lgwks_search",
                description="Search files via lgwks",
                lgwks_fn=search_fn,
                input_schema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Search pattern (regex or glob)",
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory to search in",
                        },
                    },
                    "required": ["pattern"],
                },
            ).to_tool_spec()
        )

    return adapters


def register_lgwks_tools(registry: ToolRegistry) -> int:
    """Register all lgwks tool adapters in a forge ToolRegistry.

    Returns the number of tools registered.
    """
    count = 0
    for adapter_fn in [
        wrap_lgwks_file_tools,
        wrap_lgwks_shell_tools,
        wrap_lgwks_search_tools,
    ]:
        for tool_spec in adapter_fn():
            registry.register(tool_spec)
            count += 1
    return count
