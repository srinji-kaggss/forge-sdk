"""Code intelligence tools — AST-aware codebase understanding.

The agent doesn't read files linearly. It queries a semantic graph:
  - "What calls function X?" → call_graph
  - "What does class Y inherit from?" → symbol_graph
  - "If I change file Z, what breaks?" → impact_analysis
  - "Find all functions matching pattern" → symbol_search

This is the markov puzzle: the agent picks a node, sees its edges,
decides which edge to follow next. The tool does the AST parsing.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from forge_sdk.tools.types import ToolSpec, ToolResult


def _parse_python_file(path: str) -> dict[str, Any]:
    """Parse a Python file into structured entities."""
    try:
        source = Path(path).read_text()
        tree = ast.parse(source)
    except Exception as exc:
        return {"error": str(exc), "path": path}

    entities: list[dict[str, Any]] = []
    imports: list[dict[str, str]] = []
    calls: list[dict[str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            ret = ast.unparse(node.returns) if node.returns else None
            entities.append({
                "type": "function",
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno or node.lineno,
                "args": args,
                "returns": ret,
                "docstring": ast.get_docstring(node),
                "decorators": [ast.unparse(d) for d in node.decorator_list],
            })
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            methods = [
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            entities.append({
                "type": "class",
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno or node.lineno,
                "bases": bases,
                "methods": methods,
                "docstring": ast.get_docstring(node),
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"module": alias.name, "alias": alias.asname, "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append({"module": mod, "name": alias.name, "alias": alias.asname, "line": node.lineno})
        elif isinstance(node, ast.Call):
            try:
                func_name = ast.unparse(node.func)
                calls.append({"function": func_name, "line": node.lineno})
            except Exception:
                pass

    return {
        "path": path,
        "lines": len(source.splitlines()),
        "entities": entities,
        "imports": imports,
        "calls": calls,
    }


def _build_codebase_graph(root: str, max_files: int = 200) -> dict[str, Any]:
    """Build a lightweight codebase graph from Python files."""
    root_path = Path(root)
    py_files = []
    for p in root_path.rglob("*.py"):
        if any(skip in str(p) for skip in [".venv", "__pycache__", ".git", "node_modules", "site-packages"]):
            continue
        py_files.append(p)
        if len(py_files) >= max_files:
            break

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    file_index: dict[str, dict] = {}

    for pyf in py_files:
        rel = str(pyf.relative_to(root_path))
        parsed = _parse_python_file(str(pyf))
        file_index[rel] = parsed

        for ent in parsed.get("entities", []):
            nodes.append({
                "id": f"{rel}::{ent['name']}",
                "type": ent["type"],
                "name": ent["name"],
                "file": rel,
                "line": ent["line"],
            })

        for imp in parsed.get("imports", []):
            edges.append({
                "source": rel,
                "target": imp["module"],
                "type": "imports",
            })

        for call in parsed.get("calls", []):
            edges.append({
                "source": rel,
                "target": call["function"],
                "type": "calls",
                "line": call["line"],
            })

    return {
        "root": root,
        "files_scanned": len(py_files),
        "nodes": nodes,
        "edges": edges,
        "file_index": file_index,
    }


async def symbol_search(pattern: str, path: str = ".", symbol_type: str = "") -> ToolResult:
    """Search for functions/classes/methods matching a regex pattern across the codebase."""
    root = Path(path)
    results: list[dict[str, Any]] = []

    for pyf in root.rglob("*.py"):
        if any(skip in str(pyf) for skip in [".venv", "__pycache__", ".git", "site-packages"]):
            continue
        rel = str(pyf.relative_to(root))
        parsed = _parse_python_file(str(pyf))
        for ent in parsed.get("entities", []):
            if symbol_type and ent["type"] != symbol_type:
                continue
            if re.search(pattern, ent["name"], re.IGNORECASE):
                results.append({
                    "name": ent["name"],
                    "type": ent["type"],
                    "file": rel,
                    "line": ent["line"],
                    "docstring": (ent.get("docstring") or "")[:120],
                })

    return ToolResult(
        success=True,
        output=json.dumps({"matches": len(results), "results": results[:50]}, indent=2),
    )


async def call_graph(symbol: str, path: str = ".", direction: str = "callers") -> ToolResult:
    """Find callers or callees of a symbol. direction=callers (who calls X) or callees (what X calls)."""
    graph = _build_codebase_graph(path)
    results: list[dict[str, str]] = []

    if direction == "callers":
        for edge in graph["edges"]:
            if edge["type"] == "calls" and symbol in edge["target"]:
                results.append({"file": edge["source"], "line": edge.get("line", 0), "calls": edge["target"]})
    else:
        for node in graph["nodes"]:
            if node["name"] == symbol:
                file_data = graph["file_index"].get(node["file"], {})
                for call in file_data.get("calls", []):
                    if call["line"] >= node["line"] and call["line"] <= node.get("end_line", call["line"]):
                        results.append({"file": node["file"], "line": call["line"], "calls": call["function"]})

    return ToolResult(
        success=True,
        output=json.dumps({"symbol": symbol, "direction": direction, "matches": len(results), "results": results[:30]}, indent=2),
    )


async def impact_analysis(file_path: str, path: str = ".") -> ToolResult:
    """Analyze what would be impacted if a file changes. Returns importers and dependents."""
    graph = _build_codebase_graph(path)
    rel = file_path

    importers: list[str] = []
    dependents: list[str] = []

    for edge in graph["edges"]:
        if edge["type"] == "imports":
            mod = edge["target"].replace(".", "/")
            if mod in rel or rel.replace("/", ".").replace(".py", "") in edge["target"]:
                if edge["source"] not in importers:
                    importers.append(edge["source"])

    for node in graph["nodes"]:
        if node["file"] == rel:
            for edge in graph["edges"]:
                if edge["type"] == "calls" and node["name"] in edge["target"]:
                    if edge["source"] != rel and edge["source"] not in dependents:
                        dependents.append(edge["source"])

    return ToolResult(
        success=True,
        output=json.dumps({
            "file": rel,
            "importers": importers[:20],
            "dependents": dependents[:20],
            "total_impact": len(importers) + len(dependents),
        }, indent=2),
    )


async def code_structure(file_path: str) -> ToolResult:
    """Get the structured AST of a file: all functions, classes, imports, calls. No raw source — just structure."""
    parsed = _parse_python_file(file_path)
    return ToolResult(
        success=True,
        output=json.dumps(parsed, indent=2),
    )


SYMBOL_SEARCH_TOOL = ToolSpec(
    name="symbol_search",
    description=(
        "Search for functions/classes/methods matching a regex pattern across the codebase. "
        "Returns structured results: name, type, file, line, docstring. "
        "Use this instead of grep when you need semantic understanding (only functions/classes, not raw text). "
        "Parameters: pattern (regex), path (root dir, default '.'), symbol_type ('function' or 'class' or empty for both)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to match symbol names"},
            "path": {"type": "string", "description": "Root directory to search (default: current dir)"},
            "symbol_type": {"type": "string", "description": "Filter: 'function', 'class', or empty for both"},
        },
        "required": ["pattern"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-CODE-001",
        handler=symbol_search,
)

CALL_GRAPH_TOOL = ToolSpec(
    name="call_graph",
    description=(
        "Find callers or callees of a symbol in the codebase. "
        "direction='callers' shows who calls this symbol. direction='callees' shows what this symbol calls. "
        "Returns file:line for each match. Use for impact analysis before refactoring."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Function or class name to analyze"},
            "path": {"type": "string", "description": "Root directory (default: '.')"},
            "direction": {"type": "string", "description": "'callers' (who calls X) or 'callees' (what X calls)"},
        },
        "required": ["symbol"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-CODE-002",
        handler=call_graph,
)

IMPACT_ANALYSIS_TOOL = ToolSpec(
    name="impact_analysis",
    description=(
        "Analyze what breaks if a file changes. Returns importers (files that import it) "
        "and dependents (files that call its symbols). Use BEFORE editing a file to understand blast radius."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "File path relative to root"},
            "path": {"type": "string", "description": "Root directory (default: '.')"},
        },
        "required": ["file_path"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-CODE-003",
        handler=impact_analysis,
)

CODE_STRUCTURE_TOOL = ToolSpec(
    name="code_structure",
    description=(
        "Get the structured AST of a file: all functions, classes, imports, and calls. "
        "No raw source code — just the structure. Use this instead of read_file when you need "
        "to understand a file's architecture without reading every line. "
        "Returns: entities (name, type, line, args, returns, docstring), imports, calls."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the Python file"},
        },
        "required": ["file_path"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-CODE-004",
        handler=code_structure,
)

CODE_INTEL_TOOLS = [SYMBOL_SEARCH_TOOL, CALL_GRAPH_TOOL, IMPACT_ANALYSIS_TOOL, CODE_STRUCTURE_TOOL]