"""Code search tools — grep and glob."""

from __future__ import annotations

import subprocess
from pathlib import Path

from forge_sdk.tools import ToolResult, ToolSpec


async def _grep(pattern: str, path: str = ".", include: str = "") -> ToolResult:
    try:
        cmd = ["rg", "--no-heading", "--line-number"]
        if include:
            cmd.extend(["--glob", include])
        cmd.extend([pattern, path])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        return ToolResult(success=result.returncode == 0, output=output)
    except FileNotFoundError:
        return ToolResult(success=False, output="", error="ripgrep (rg) not installed")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def _glob(pattern: str, path: str = ".") -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        matches = sorted(str(m) for m in p.glob(pattern))
        output = "\n".join(matches) if matches else "No matches"
        return ToolResult(success=True, output=output, metadata={"count": len(matches)})
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


SEARCH_TOOLS = [
    ToolSpec(
        name="grep",
        description="Search file contents using ripgrep regex patterns.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in"},
                "include": {
                    "type": "string",
                    "description": "File glob pattern to filter (e.g. '*.py')",
                },
            },
            "required": ["pattern"],
        },
        output_schema={"type": "object", "properties": {"matches": {"type": "string"}}},
        stable_id="TOOL-SEARCH-GREP-001",
        handler=_grep,
    ),
    ToolSpec(
        name="glob",
        description="Find files matching a glob pattern.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                "path": {"type": "string", "description": "Root directory"},
            },
            "required": ["pattern"],
        },
        output_schema={
            "type": "object",
            "properties": {"files": {"type": "array", "items": {"type": "string"}}},
        },
        stable_id="TOOL-SEARCH-GLOB-001",
        handler=_glob,
    ),
]
