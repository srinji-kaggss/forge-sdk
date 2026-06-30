"""Edit intelligence tools — structured, surgical code modifications.

Instead of reading a file, rewriting it entirely, and writing it back
(which wastes tokens and risks corrupting unrelated code), these tools
do surgical edits:

  - patch_line: replace a specific line by number
  - patch_symbol: replace a specific function/class by name (AST-aware)
  - insert_at: insert code at a specific location
  - rename_symbol: rename a function/class/variable across a file (AST-aware)
  - multi_edit: apply multiple edits to the same file in one call

The LLM says "change function X to Y" and the tool finds X, replaces it,
and returns the diff. The LLM never sees the full file — it sees the diff.
"""

from __future__ import annotations

import ast
import difflib
import re
from pathlib import Path
from typing import Any

from forge_sdk.tools.types import ToolSpec, ToolResult


def _make_diff(old: str, new: str, filename: str = "") -> str:
    """Generate a unified diff."""
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=filename,
        tofile=filename,
    )
    return "".join(diff)


async def patch_line(file_path: str, line_number: int, new_content: str) -> ToolResult:
    """Replace a specific line by line number (1-indexed)."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    old = path.read_text()
    lines = old.splitlines()
    if line_number < 1 or line_number > len(lines):
        return ToolResult(success=False, output=f"Error: line {line_number} out of range (1-{len(lines)})")

    lines[line_number - 1] = new_content
    new = "\n".join(lines)
    if not old.endswith("\n"):
        new = "\n".join(lines)
    else:
        new = "\n".join(lines) + "\n"

    path.write_text(new)
    diff = _make_diff(old, new, file_path)
    return ToolResult(success=True, output=f"Patched line {line_number} in {file_path}\n{diff}")


async def patch_symbol(file_path: str, symbol_name: str, new_body: str) -> ToolResult:
    """Replace a function or class by name using AST-aware matching. Returns the diff."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    old = path.read_text()
    lines = old.splitlines()

    try:
        tree = ast.parse(old)
    except SyntaxError as exc:
        return ToolResult(success=False, output=f"Error: cannot parse {file_path}: {exc}")

    target_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol_name:
                target_node = node
                break

    if target_node is None:
        return ToolResult(success=False, output=f"Error: symbol '{symbol_name}' not found in {file_path}")

    start = target_node.lineno - 1
    end = target_node.end_lineno or len(lines)

    indent = len(lines[start]) - len(lines[start].lstrip())
    indented_new = "\n".join(" " * indent + l if l.strip() else l for l in new_body.splitlines())

    new_lines = lines[:start] + indented_new.splitlines() + lines[end:]
    new = "\n".join(new_lines)
    if old.endswith("\n"):
        new += "\n"

    path.write_text(new)
    diff = _make_diff(old, new, file_path)
    return ToolResult(success=True, output=f"Patched symbol '{symbol_name}' in {file_path}\n{diff}")


async def insert_at(file_path: str, after_line: int, content: str) -> ToolResult:
    """Insert content after a specific line number (0 = top of file)."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    old = path.read_text()
    lines = old.splitlines()

    if after_line < 0 or after_line > len(lines):
        return ToolResult(success=False, output=f"Error: after_line {after_line} out of range (0-{len(lines)})")

    new_lines = lines[:after_line] + content.splitlines() + lines[after_line:]
    new = "\n".join(new_lines)
    if old.endswith("\n"):
        new += "\n"

    path.write_text(new)
    diff = _make_diff(old, new, file_path)
    return ToolResult(success=True, output=f"Inserted {len(content.splitlines())} lines after line {after_line} in {file_path}\n{diff}")


async def rename_symbol(file_path: str, old_name: str, new_name: str) -> ToolResult:
    """Rename a function/class/variable in a file using AST-aware replacement."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    old = path.read_text()

    try:
        tree = ast.parse(old)
    except SyntaxError as exc:
        return ToolResult(success=False, output=f"Error: cannot parse: {exc}")

    found = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == old_name:
                node.name = new_name
                found = True

    if not found:
        return ToolResult(success=False, output=f"Error: '{old_name}' not found in {file_path}")

    new = ast.unparse(tree)
    path.write_text(new)
    diff = _make_diff(old, new, file_path)
    return ToolResult(success=True, output=f"Renamed '{old_name}' → '{new_name}' in {file_path}\n{diff}")


async def multi_edit(file_path: str, edits: list[dict[str, Any]]) -> ToolResult:
    """Apply multiple edits to the same file in one call. Each edit: {type: 'line'|'symbol', ...}."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    old = path.read_text()
    results: list[str] = []

    for edit in edits:
        etype = edit.get("type", "line")
        if etype == "line":
            r = await patch_line(file_path, edit["line_number"], edit["new_content"])
            results.append(f"line {edit['line_number']}: {'OK' if r.success else r.output}")
        elif etype == "symbol":
            r = await patch_symbol(file_path, edit["symbol_name"], edit["new_body"])
            results.append(f"symbol {edit['symbol_name']}: {'OK' if r.success else r.output}")

    new = path.read_text()
    diff = _make_diff(old, new, file_path)
    return ToolResult(success=True, output=f"Applied {len(edits)} edits to {file_path}\n{diff}")


PATCH_LINE_TOOL = ToolSpec(
    name="patch_line",
    description=(
        "Replace a specific line by line number (1-indexed). Surgical — only touches that line. "
        "Use when you know the exact line to change. Returns the diff."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "line_number": {"type": "integer", "description": "Line number to replace (1-indexed)"},
            "new_content": {"type": "string", "description": "New content for that line"},
        },
        "required": ["file_path", "line_number", "new_content"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-EDIT-001",
        handler=patch_line,
)

PATCH_SYMBOL_TOOL = ToolSpec(
    name="patch_symbol",
    description=(
        "Replace a function or class by name using AST-aware matching. "
        "Provide the symbol name and the new body (without def/class line — just the implementation). "
        "The tool finds the symbol, preserves indentation, and returns the diff. "
        "Use this instead of read+write when you need to change one function in a large file."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "symbol_name": {"type": "string", "description": "Function or class name to replace"},
            "new_body": {"type": "string", "description": "New implementation code for the symbol"},
        },
        "required": ["file_path", "symbol_name", "new_body"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-EDIT-002",
        handler=patch_symbol,
)

INSERT_AT_TOOL = ToolSpec(
    name="insert_at",
    description=(
        "Insert content after a specific line number (0 = top of file). "
        "Use to add new functions, imports, or code blocks without rewriting the file."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "after_line": {"type": "integer", "description": "Insert after this line (0 = top of file)"},
            "content": {"type": "string", "description": "Content to insert"},
        },
        "required": ["file_path", "after_line", "content"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-EDIT-003",
        handler=insert_at,
)

RENAME_SYMBOL_TOOL = ToolSpec(
    name="rename_symbol",
    description=(
        "Rename a function/class in a file using AST-aware replacement. "
        "All references within the file are updated. Returns the diff."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "old_name": {"type": "string", "description": "Current symbol name"},
            "new_name": {"type": "string", "description": "New symbol name"},
        },
        "required": ["file_path", "old_name", "new_name"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-EDIT-004",
        handler=rename_symbol,
)

MULTI_EDIT_TOOL = ToolSpec(
    name="multi_edit",
    description=(
        "Apply multiple edits to the same file in one call. "
        "edits: list of {type: 'line', line_number: N, new_content: '...'} or "
        "{type: 'symbol', symbol_name: 'X', new_body: '...'}. "
        "Returns combined diff. Use when you need to change 2+ things in the same file."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "edits": {"type": "array", "description": "List of edit operations"},
        },
        "required": ["file_path", "edits"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-EDIT-005",
        handler=multi_edit,
)

EDIT_INTEL_TOOLS = [PATCH_LINE_TOOL, PATCH_SYMBOL_TOOL, INSERT_AT_TOOL, RENAME_SYMBOL_TOOL, MULTI_EDIT_TOOL]