"""File system tools — read, write, list."""

from __future__ import annotations

import os
from pathlib import Path

from forge_sdk.tools import ToolResult, ToolSpec


async def _read_file(path: str) -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        content = p.read_text(encoding="utf-8", errors="replace")
        return ToolResult(
            success=True, output=content, metadata={"path": str(p), "size": len(content)}
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def _write_file(path: str, content: str) -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True, output=f"Written {len(content)} bytes to {p}", metadata={"path": str(p)}
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def _list_dir(path: str = ".") -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        entries = sorted(os.listdir(p))
        output = "\n".join(entries)
        return ToolResult(
            success=True, output=output, metadata={"path": str(p), "count": len(entries)}
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


FILE_TOOLS = [
    ToolSpec(
        name="read_file",
        description="Read the contents of a file at the given path.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"}
            },
            "required": ["path"],
        },
        output_schema={"type": "object", "properties": {"content": {"type": "string"}}},
        stable_id="TOOL-FILE-READ-001",
        handler=_read_file,
    ),
    ToolSpec(
        name="write_file",
        description="Write content to a file. Creates parent dirs if needed.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        stable_id="TOOL-FILE-WRITE-001",
        handler=_write_file,
    ),
    ToolSpec(
        name="list_dir",
        description="List files and directories at the given path.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
        },
        output_schema={
            "type": "object",
            "properties": {"entries": {"type": "array", "items": {"type": "string"}}},
        },
        stable_id="TOOL-FILE-LIST-001",
        handler=_list_dir,
    ),
]
