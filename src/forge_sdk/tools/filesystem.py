"""File system tools — read, write, list.

v0.4.0: File size limits, path containment, encoding awareness.
"""

from __future__ import annotations

import os
from pathlib import Path

from forge_sdk.tools import ToolResult, ToolSpec

# Max file size for reads (10MB)
MAX_READ_BYTES = 10 * 1024 * 1024

# Paths that should never be written to
FORBIDDEN_PATHS = ("/etc", "/usr", "/var", "/sys", "/proc", "/dev")


async def _read_file(path: str) -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"File not found: {p}",
                metadata={"suggestion": f"Check if the file exists. Try list_dir on the parent directory: {p.parent}"},
            )
        if not p.is_file():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a file (it's a directory): {p}",
                metadata={"suggestion": f"Use list_dir to see contents of {p}"},
            )
        # Size check
        file_size = p.stat().st_size
        if file_size > MAX_READ_BYTES:
            return ToolResult(
                success=False,
                output="",
                error=f"File too large ({file_size} bytes, max {MAX_READ_BYTES})",
                metadata={"suggestion": "Read a specific section or use grep to find relevant parts"},
            )
        content = p.read_text(encoding="utf-8", errors="replace")
        return ToolResult(
            success=True,
            output=content,
            metadata={"path": str(p), "size": len(content), "lines": content.count("\n") + 1},
        )
    except PermissionError:
        return ToolResult(success=False, output="", error=f"Permission denied: {path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def _write_file(path: str, content: str) -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        # Path containment: block writes to system directories
        for forbidden in FORBIDDEN_PATHS:
            if str(p).startswith(forbidden):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Write to system directory blocked: {p}",
                    metadata={"suggestion": "Write to a user directory instead (e.g., ~/, /tmp/)"},
                )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True,
            output=f"Written {len(content)} bytes ({content.count(chr(10)) + 1} lines) to {p}",
            metadata={"path": str(p), "bytes": len(content)},
        )
    except PermissionError:
        return ToolResult(
            success=False,
            output="",
            error=f"Permission denied: {path}",
            metadata={"suggestion": "Check file permissions or try a different path"},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def _list_dir(path: str = ".") -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a directory: {p}",
                metadata={"suggestion": f"Use read_file to read {p} if it's a file"},
            )
        entries = sorted(os.listdir(p))
        formatted = []
        for e in entries[:200]:  # Limit to 200 entries
            full = p / e
            try:
                if full.is_dir():
                    formatted.append(f"  {e}/")
                else:
                    size = full.stat().st_size if full.exists() else 0
                    formatted.append(f"  {e}  ({size} bytes)")
            except (PermissionError, OSError):
                formatted.append(f"  {e}  (inaccessible)")
        if len(entries) > 200:
            formatted.append(f"  ... and {len(entries) - 200} more entries")
        output = f"Contents of {p} ({len(entries)} entries):\n" + "\n".join(formatted) if formatted else f"Empty directory: {p}"
        return ToolResult(
            success=True,
            output=output,
            metadata={"path": str(p), "count": len(entries)},
        )
    except PermissionError:
        return ToolResult(success=False, output="", error=f"Permission denied: {path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


FILE_TOOLS = [
    ToolSpec(
        name="read_file",
        description=(
            "Read the full contents of a file at the given path.\n\n"
            "Best for: reading source code, config files, text files, any file you need to understand.\n"
            "Not recommended for: listing directory contents (use list_dir), finding files by pattern (use glob).\n"
            "Common mistakes: passing a directory path (use list_dir instead), not handling missing files.\n"
            "Output: the raw file content as a string. Large files may be truncated."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path (e.g. 'src/main.py', '/etc/hosts')",
                },
            },
            "required": ["path"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The file contents as a string"},
            },
        },
        stable_id="TOOL-FILE-READ-001",
        handler=_read_file,
    ),
    ToolSpec(
        name="write_file",
        description=(
            "Write content to a file, creating parent directories if needed.\n\n"
            "Best for: creating new files, overwriting existing files, writing code or config.\n"
            "Not recommended for: appending to files (read then write), editing single lines (read, modify, write).\n"
            "Common mistakes: forgetting to include the full content (this overwrites, not appends).\n"
            "Output: confirmation with byte count and line count."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative file path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "The full content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "Confirmation message with byte/line count"},
            },
        },
        stable_id="TOOL-FILE-WRITE-001",
        handler=_write_file,
    ),
    ToolSpec(
        name="list_dir",
        description=(
            "List files and directories at the given path, showing size info.\n\n"
            "Best for: exploring directory structure, finding what files exist before reading them.\n"
            "Not recommended for: finding files by name pattern (use glob), reading file contents (use read_file).\n"
            "Common mistakes: passing a file path instead of a directory.\n"
            "Output: formatted list with directories marked with / and file sizes."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: current directory)",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "entries": {"type": "array", "items": {"type": "string"}},
            },
        },
        stable_id="TOOL-FILE-LIST-001",
        handler=_list_dir,
    ),
]
