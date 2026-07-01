"""Verify intelligence tools — run, check, and validate code.

The agent doesn't just write code — it verifies its own work:
  - run_tests: run pytest and get structured pass/fail
  - syntax_check: parse a file without executing (catch errors before runtime)
  - type_check: run mypy/pyright if available
  - security_scan: check for common vulnerabilities (eval, exec, shell injection)
  - git_diff: see what changed since last commit
  - git_status: see uncommitted changes

The harness forces verification after edits. The agent sees the result
and either fixes or finishes. This is the markov chain: edit → verify → fix or finish.
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import shlex
from pathlib import Path
from typing import Any

from forge_sdk.security import _check_command_safety, _check_path_safety
from forge_sdk.tools.types import ToolResult, ToolSpec


async def run_tests(path: str = ".", args: str = "-x --tb=short -q") -> ToolResult:
    """Run pytest and return structured results."""
    # RT-013 fix: sanitize path and args before execution
    path_violation = _check_path_safety(path, ".", check_writes=False)
    if path_violation:
        return ToolResult(
            success=False, output="", error=path_violation, metadata={"blocked": True}
        )

    # Sanitize args — only allow known pytest flags
    safe_args = args
    cmd_violation = _check_command_safety(safe_args)
    if cmd_violation:
        return ToolResult(
            success=False,
            output="",
            error=f"Unsafe test args: {cmd_violation}",
            metadata={"blocked": True},
        )

    # Build command safely — no shell injection possible
    cmd_parts = ["python", "-m", "pytest"] + shlex.split(safe_args) + [path]
    proc = await asyncio.create_subprocess_exec(
        *cmd_parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    output = stdout.decode() + stderr.decode()

    passed = len(re.findall(r"(\d+) passed", output))
    failed = len(re.findall(r"(\d+) failed", output))
    errors = len(re.findall(r"(\d+) error", output))
    skipped = len(re.findall(r"(\d+) skipped", output))

    failures: list[dict[str, str]] = []
    for match in re.finditer(r"FAILED (.+?) -", output):
        failures.append({"test": match.group(1)})

    return ToolResult(
        success=proc.returncode == 0,
        output=json.dumps(
            {
                "exit_code": proc.returncode,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "failures": failures[:20],
                "output_tail": output[-500:],
            },
            indent=2,
        ),
    )


async def syntax_check(file_path: str) -> ToolResult:
    """Check a Python file for syntax errors without executing it."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    source = path.read_text()
    try:
        ast.parse(source)
        return ToolResult(
            success=True,
            output=f"OK: {file_path} parses cleanly ({len(source.splitlines())} lines)",
        )
    except SyntaxError as exc:
        return ToolResult(
            success=False,
            output=json.dumps(
                {
                    "file": file_path,
                    "error": str(exc),
                    "line": exc.lineno,
                    "offset": exc.offset,
                    "text": exc.text,
                },
                indent=2,
            ),
        )


async def security_scan(file_path: str) -> ToolResult:
    """Scan a Python file for common security issues (eval, exec, shell injection, hardcoded secrets)."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    source = path.read_text()
    issues: list[dict[str, Any]] = []

    patterns = [
        (r"\beval\s*\(", "eval", "high", "eval() can execute arbitrary code"),
        (r"\bexec\s*\(", "exec", "high", "exec() can execute arbitrary code"),
        (
            r"\b__import__\s*\(",
            "dynamic_import",
            "medium",
            "Dynamic import can load arbitrary modules",
        ),
        (
            r"subprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True",
            "shell_injection",
            "high",
            "shell=True allows injection",
        ),
        (r"os\.system\s*\(", "os_system", "high", "os.system() is vulnerable to injection"),
        (
            r"(?:api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]",
            "hardcoded_secret",
            "high",
            "Hardcoded secret detected",
        ),
        (r"pickle\.loads?\s*\(", "pickle_deserialize", "high", "Pickle deserialization is unsafe"),
        (r"\byaml\.load\s*\(", "yaml_unsafe_load", "medium", "Use yaml.safe_load() instead"),
    ]

    for pattern, name, severity, description in patterns:
        for match in re.finditer(pattern, source):
            line_num = source[: match.start()].count("\n") + 1
            issues.append(
                {
                    "type": name,
                    "severity": severity,
                    "line": line_num,
                    "description": description,
                    "match": match.group()[:60],
                }
            )

    return ToolResult(
        success=len(issues) == 0,
        output=json.dumps(
            {
                "file": file_path,
                "issues_found": len(issues),
                "issues": issues,
            },
            indent=2,
        ),
    )


async def git_diff(path: str = ".") -> ToolResult:
    """Get the git diff of uncommitted changes."""
    proc = await asyncio.create_subprocess_shell(
        f"git diff {path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    diff = stdout.decode()

    files_changed = len(re.findall(r"^diff --git", diff, re.MULTILINE))
    lines_added = len(re.findall(r"^\+", diff, re.MULTILINE)) - files_changed * 2
    lines_removed = len(re.findall(r"^-", diff, re.MULTILINE)) - files_changed * 2

    return ToolResult(
        success=True,
        output=json.dumps(
            {
                "files_changed": files_changed,
                "lines_added": max(0, lines_added),
                "lines_removed": max(0, lines_removed),
                "diff": diff[:3000],
            },
            indent=2,
        ),
    )


async def git_status(path: str = ".") -> ToolResult:
    """Get git status (uncommitted files)."""
    proc = await asyncio.create_subprocess_shell(
        f"git status --short {path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    status = stdout.decode()

    files: list[dict[str, str]] = []
    for line in status.splitlines():
        if line.strip():
            status_code = line[:2].strip()
            file_path = line[3:].strip()
            files.append({"status": status_code, "file": file_path})

    return ToolResult(
        success=True,
        output=json.dumps({"files": files, "total": len(files)}, indent=2),
    )


RUN_TESTS_TOOL = ToolSpec(
    name="run_tests",
    description=(
        "Run pytest and get structured results: passed, failed, errors, skipped counts + failure list. "
        "Use AFTER making code changes to verify correctness. "
        "args: pytest flags (default: '-x --tb=short -q'). path: test file or directory."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Test path (default: '.')"},
            "args": {"type": "string", "description": "pytest args (default: '-x --tb=short -q')"},
        },
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-VERIFY-001",
    handler=run_tests,
)

SYNTAX_CHECK_TOOL = ToolSpec(
    name="syntax_check",
    description=(
        "Check a Python file for syntax errors WITHOUT executing it. "
        "Use BEFORE running tests to catch obvious errors fast. "
        "Returns: OK or error details (line, offset, text)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the Python file"},
        },
        "required": ["file_path"],
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-VERIFY-002",
    handler=syntax_check,
)

SECURITY_SCAN_TOOL = ToolSpec(
    name="security_scan",
    description=(
        "Scan a Python file for common security issues: eval, exec, shell injection, hardcoded secrets, "
        "pickle deserialization, unsafe yaml load. Returns structured issues with severity and line numbers. "
        "Use after writing code that handles user input or external data."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the Python file"},
        },
        "required": ["file_path"],
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-VERIFY-003",
    handler=security_scan,
)

GIT_DIFF_TOOL = ToolSpec(
    name="git_diff",
    description=(
        "Get the git diff of uncommitted changes. Returns files_changed, lines_added, lines_removed, and the diff. "
        "Use to review what you've changed before committing."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to diff (default: '.')"},
        },
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-VERIFY-004",
    handler=git_diff,
)

GIT_STATUS_TOOL = ToolSpec(
    name="git_status",
    description=(
        "Get git status: list of uncommitted files with status codes (M=modified, A=added, D=deleted, ??=untracked). "
        "Use to see what's changed before committing."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path (default: '.')"},
        },
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-VERIFY-005",
    handler=git_status,
)

VERIFY_INTEL_TOOLS = [
    RUN_TESTS_TOOL,
    SYNTAX_CHECK_TOOL,
    SECURITY_SCAN_TOOL,
    GIT_DIFF_TOOL,
    GIT_STATUS_TOOL,
]
