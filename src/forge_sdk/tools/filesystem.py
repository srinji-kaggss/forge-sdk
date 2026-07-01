"""File system tools — read, write, list.

v0.5.1: Defense-in-depth via forge_sdk.security. Read path checking added.
Sensitive paths (dotfiles, credentials) blocked on both read and write.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from forge_sdk.security import _check_path_safety
from forge_sdk.tools import ToolResult, ToolSpec

# Max file size for reads (10MB)
MAX_READ_BYTES = 10 * 1024 * 1024

# Issue #21: LLMs writing a "small edit" to a large file sometimes rewrite
# the whole file and elide the unchanged parts with a placeholder comment
# instead of reproducing them, silently destroying the rest of the file
# while still reporting success. Catch both symptoms before they hit disk.
_ELISION_MARKERS = re.compile(
    r"(remains?\s+(the\s+)?(same|identical|unchanged)"
    r"|rest\s+of\s+(the\s+)?file\s+(remains|unchanged)"
    r"|\.\.\.\s*\(?unchanged\)?"
    r"|previous\s+(file\s+)?content\s+(remains|unchanged)"
    r"|\[?\s*(rest|remainder)\s+of\s+(the\s+)?(file|code)\s*(omitted|elided)?\s*\]?\.\.\.)",
    re.IGNORECASE,
)

# An existing file shrinking to less than this fraction of its prior size
# without an explicit force=True is treated as a likely lazy-rewrite, not
# an intentional edit.
_SHRINK_RATIO_THRESHOLD = 0.5
_SHRINK_MIN_OLD_BYTES = 200


async def _read_file(path: str) -> ToolResult:
    try:
        # L1+L5: Security check — read path safety
        violation = _check_path_safety(path, ".", check_writes=False)
        if violation:
            return ToolResult(
                success=False, output="", error=violation, metadata={"path": path, "blocked": True}
            )

        p = Path(path).expanduser().resolve()
        if not p.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"File not found: {p}",
                metadata={
                    "suggestion": f"Check if the file exists. Try list_dir on the parent directory: {p.parent}"
                },
            )
        if not p.is_file():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a file (it's a directory): {p}",
                metadata={"suggestion": f"Use list_dir to see contents of {p}"},
            )
        file_size = p.stat().st_size
        if file_size > MAX_READ_BYTES:
            return ToolResult(
                success=False,
                output="",
                error=f"File too large ({file_size} bytes, max {MAX_READ_BYTES})",
                metadata={
                    "suggestion": "Read a specific section or use grep to find relevant parts"
                },
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


async def _write_file(path: str, content: str, force: bool = False) -> ToolResult:
    try:
        # L1+L5: Security check — write path safety
        violation = _check_path_safety(path, ".", check_writes=True)
        if violation:
            return ToolResult(
                success=False, output="", error=violation, metadata={"path": path, "blocked": True}
            )

        p = Path(path).expanduser().resolve()

        elision_match = _ELISION_MARKERS.search(content)
        if elision_match and not force:
            return ToolResult(
                success=False,
                output="",
                error=(
                    f"Refused: content contains an elision placeholder "
                    f"({elision_match.group(0)!r}) instead of real file "
                    f"content. This is a known lazy-rewrite failure mode — "
                    f"write the FULL content or use a patch tool for partial "
                    f"edits. Pass force=true only if this text is genuinely "
                    f"intended."
                ),
                metadata={"path": str(p), "blocked": True, "reason": "elision_marker"},
            )

        if p.exists() and p.is_file() and not force:
            old_len = p.stat().st_size
            new_len = len(content.encode("utf-8"))
            if old_len >= _SHRINK_MIN_OLD_BYTES and new_len < old_len * _SHRINK_RATIO_THRESHOLD:
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        f"Refused: new content ({new_len} bytes) is less than "
                        f"{_SHRINK_RATIO_THRESHOLD:.0%} of the existing file's size "
                        f"({old_len} bytes). This usually means a partial/lossy "
                        f"rewrite rather than an intentional shrink. Use a patch "
                        f"tool for a scoped edit, or pass force=true to write "
                        f"this content anyway."
                    ),
                    metadata={
                        "path": str(p),
                        "blocked": True,
                        "reason": "shrink_guard",
                        "old_bytes": old_len,
                        "new_bytes": new_len,
                    },
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
        output = (
            f"Contents of {p} ({len(entries)} entries):\n" + "\n".join(formatted)
            if formatted
            else f"Empty directory: {p}"
        )
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
                "force": {
                    "type": "boolean",
                    "description": (
                        "Set true to bypass the lazy-rewrite guard (elision "
                        "placeholder detection / large shrink-ratio check) "
                        "when a drastic intentional rewrite is genuinely "
                        "intended. Default false."
                    ),
                },
            },
            "required": ["path", "content"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "Confirmation message with byte/line count",
                },
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
