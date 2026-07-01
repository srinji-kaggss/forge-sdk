"""Code search tools — grep and glob.

v0.5.1: Path safety via forge_sdk.security for sandbox containment.
AI-native tool descriptions. grep uses ripgrep (rg) for fast regex search.
glob uses Python's pathlib for pattern matching.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from forge_sdk.security import _check_path_safety
from forge_sdk.tools import ToolResult, ToolSpec


async def _grep(pattern: str, path: str = ".", include: str = "") -> ToolResult:
    try:
        # L1: Path safety check
        violation = _check_path_safety(path, ".", check_writes=False)
        if violation:
            return ToolResult(success=False, output="", error=violation, metadata={"blocked": True})

        cmd = ["rg", "--no-heading", "--line-number", "--color=never"]
        if include:
            cmd.extend(["--glob", include])
        cmd.extend([pattern, path])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            # Count matches for metadata
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return ToolResult(
                success=True,
                output=result.stdout.strip(),
                metadata={"matches": len(lines), "pattern": pattern, "path": path},
            )
        elif result.returncode == 1:
            return ToolResult(
                success=True,
                output=f"No matches for '{pattern}' in {path}",
                metadata={"matches": 0},
            )
        else:
            return ToolResult(success=False, output="", error=result.stderr.strip())
    except FileNotFoundError:
        return ToolResult(
            success=False,
            output="",
            error="ripgrep (rg) not installed",
            metadata={"suggestion": "Install ripgrep: brew install ripgrep / apt install ripgrep"},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            output="",
            error="Search timed out (30s)",
            metadata={"suggestion": "Try a more specific pattern or narrower path"},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def _glob(pattern: str, path: str = ".") -> ToolResult:
    try:
        # L1: Path safety check
        violation = _check_path_safety(path, ".", check_writes=False)
        if violation:
            return ToolResult(success=False, output="", error=violation, metadata={"blocked": True})

        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a directory: {p}",
                metadata={"suggestion": f"Use read_file to read {p} if it's a file"},
            )
        matches = sorted(str(m) for m in p.glob(pattern))
        if not matches:
            return ToolResult(
                success=True,
                output=f"No files match '{pattern}' in {p}",
                metadata={"count": 0, "pattern": pattern},
            )
        output = f"Found {len(matches)} files matching '{pattern}':\n" + "\n".join(matches)
        return ToolResult(
            success=True,
            output=output,
            metadata={"count": len(matches), "pattern": pattern, "path": str(p)},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


SEARCH_TOOLS = [
    ToolSpec(
        name="grep",
        description=(
            "Search file contents using ripgrep regex patterns.\n\n"
            "Best for: finding where a function/class/variable is defined or used, "
            "searching for patterns across codebase, finding TODOs/FIXMEs.\n"
            "Not recommended for: finding files by name (use glob), reading a specific file (use read_file).\n"
            "Common mistakes: using grep instead of rg syntax, not narrowing scope with --include.\n"
            "Output: file:line:content for each match. Use --include '*.py' to filter by file type.\n\n"
            "Example: {'pattern': 'def calculate_total', 'path': 'src/', 'include': '*.py'}"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for (ripgrep syntax)",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
                "include": {
                    "type": "string",
                    "description": "File glob filter (e.g. '*.py', '*.{ts,js}')",
                },
            },
            "required": ["pattern"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "matches": {"type": "string", "description": "file:line:content for each match"},
            },
        },
        stable_id="TOOL-SEARCH-GREP-001",
        handler=_grep,
    ),
    ToolSpec(
        name="glob",
        description=(
            "Find files matching a glob pattern (like **/*.py for all Python files).\n\n"
            "Best for: finding files by name/type, discovering project structure, "
            "locating config files, finding all files matching a pattern.\n"
            "Not recommended for: searching file contents (use grep), reading file contents (use read_file).\n"
            "Common mistakes: forgetting ** for recursive search (use **/*.py, not *.py).\n"
            "Output: list of matching file paths.\n\n"
            "Example: {'pattern': '**/*.py', 'path': 'src/'}"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (** for recursive, e.g. '**/*.py', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Root directory to search from (default: current directory)",
                },
            },
            "required": ["pattern"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "files": {"type": "array", "items": {"type": "string"}},
            },
        },
        stable_id="TOOL-SEARCH-GLOB-001",
        handler=_glob,
    ),
]
