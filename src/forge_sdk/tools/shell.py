"""Shell execution tool — runs commands in a subprocess.

No real shell is ever invoked (no shell=True, no /bin/sh -c). Compound
operators (&&, ||, ;, |) and a leading `cd` are interpreted directly by this
module as a small argv-only state machine, so they mean what they say
without reopening shell metacharacter expansion ($(...), backticks,
globbing) as an execution path. Redirects (<, >) are not supported — a
command using them is rejected with a clear error rather than silently
mishandled.

History: a prior fix for compound commands silently no-op'ing (macOS ships
a standalone /usr/bin/cd that changes its own cwd and exits 0, doing
nothing useful) routed any operator-bearing command through `/bin/sh -c`.
That reintroduced real shell execution behind a regex denylist
(_check_command_safety) which is provably incomplete — command
substitution + an unlisted interpreter bypasses it trivially. This version
fixes the original no-op bug without reopening that class of bug.
"""

from __future__ import annotations

import shlex
import subprocess

from forge_sdk.security import _check_command_safety, _check_path_safety
from forge_sdk.tools import ToolResult, ToolSpec

_OPERATORS = ("&&", "||", ";", "|")
_UNSUPPORTED_OPERATORS = ("<", ">", ">>", "<<")


def _resolve_cd_target(target: str, cwd: str) -> str:
    """Resolve a `cd` argument against the running pipeline's current cwd
    (never the shell's real cwd — cd is a builtin here, not a process)."""
    from pathlib import Path as _Path

    expanded = _Path(target).expanduser()
    resolved = expanded if expanded.is_absolute() else _Path(cwd) / expanded
    try:
        return str(resolved.resolve())
    except OSError:
        return str(resolved)


def _tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="&|;<>")
    lexer.whitespace_split = True
    return list(lexer)


def _split_segments(tokens: list[str]) -> list[tuple[str, list[str]]]:
    """Split into (connecting_operator, argv) pairs. The first segment's
    operator is "". Segments joined by "|" form one pipeline — the caller
    groups those back together; this only separates on all four operators
    so each stage's argv is isolated from the operator tokens themselves.
    """
    segments: list[tuple[str, list[str]]] = []
    current: list[str] = []
    op = ""
    for tok in tokens:
        if tok in _OPERATORS:
            segments.append((op, current))
            current = []
            op = tok
        else:
            current.append(tok)
    segments.append((op, current))
    return segments


def _group_pipelines(
    segments: list[tuple[str, list[str]]],
) -> list[tuple[str, list[list[str]]]]:
    """Fold consecutive "|"-joined segments into one pipeline entry, keyed
    by the operator that preceded the pipeline's first stage (;/&&/||/"")."""
    pipelines: list[tuple[str, list[list[str]]]] = []
    for op, argv in segments:
        if op == "|" and pipelines:
            pipelines[-1][1].append(argv)
        else:
            pipelines.append((op, [argv]))
    return pipelines


def _run_pipeline(stages: list[list[str]], cwd: str, timeout: int) -> subprocess.CompletedProcess:
    """Run one or more argv stages connected by real pipes (never a shell)."""
    if len(stages) == 1:
        return subprocess.run(
            stages[0], shell=False, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )

    procs: list[subprocess.Popen] = []
    prev_stdout = None
    for argv in stages:
        proc = subprocess.Popen(
            argv,
            shell=False,
            cwd=cwd,
            stdin=prev_stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if prev_stdout is not None:
            prev_stdout.close()
        prev_stdout = proc.stdout
        procs.append(proc)

    stdout, stderr = procs[-1].communicate(timeout=timeout)
    for proc in procs[:-1]:
        proc.wait(timeout=timeout)
    return subprocess.CompletedProcess(
        stages[-1], procs[-1].returncode, stdout.decode(), stderr.decode()
    )


async def _shell(command: str, cwd: str = ".", timeout: int = 60) -> ToolResult:
    timeout = min(max(timeout, 1), 300)

    # L2+L3: Security check via centralized layer
    violation = _check_command_safety(command, cwd)
    if violation:
        import logging

        logging.getLogger("forge.tools.shell").warning("BLOCKED: %s", violation)
        return ToolResult(
            success=False,
            output="",
            error=violation,
            metadata={"command": command, "blocked": True},
        )

    # L1: Check cwd is not sensitive
    cwd_violation = _check_path_safety(cwd, ".", check_writes=False)
    if cwd_violation:
        return ToolResult(
            success=False,
            output="",
            error=cwd_violation,
            metadata={"command": command, "blocked": True},
        )

    # Audit log
    import logging

    logging.getLogger("forge.tools.shell").warning("SHELL: %s (cwd=%s)", command, cwd)

    try:
        tokens = _tokenize(command)
    except ValueError as exc:
        return ToolResult(
            success=False,
            output="",
            error=f"Command parse failed (unbalanced quotes): {exc}. Fix the quoting.",
            metadata={"command": command, "blocked": True},
        )

    for tok in tokens:
        if tok in _UNSUPPORTED_OPERATORS:
            return ToolResult(
                success=False,
                output="",
                error=f"Redirect operator '{tok}' is not supported. "
                f"Write output with the write_file tool instead.",
                metadata={"command": command, "blocked": True},
            )

    pipelines = _group_pipelines(_split_segments(tokens))
    if not pipelines or not pipelines[0][1][0]:
        return ToolResult(success=False, output="", error="Empty command")

    current_cwd = cwd
    returncode = 0
    last_stderr = ""
    output_parts: list[str] = []

    try:
        for op, stages in pipelines:
            if op == "&&" and returncode != 0:
                continue
            if op == "||" and returncode == 0:
                continue

            first_stage = stages[0]
            if len(stages) == 1 and first_stage and first_stage[0] == "cd":
                target = first_stage[1] if len(first_stage) > 1 else "~"
                target = str(_resolve_cd_target(target, current_cwd))
                cd_violation = _check_path_safety(target, current_cwd, check_writes=False)
                if cd_violation:
                    returncode = 1
                    output_parts.append(f"[stderr]\ncd: {cd_violation}")
                else:
                    current_cwd = target
                    returncode = 0
                continue

            result = _run_pipeline(stages, current_cwd, timeout)
            returncode = result.returncode
            last_stderr = result.stderr
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(f"[stderr]\n{result.stderr}")

        output = "\n".join(part for part in output_parts if part)

        if returncode == 0:
            return ToolResult(
                success=True,
                output=output.strip() or "(no output)",
                metadata={"exit_code": returncode, "command": command},
            )
        else:
            suggestion = ""
            if returncode == 127:
                suggestion = "Command not found. Check if the program is installed."
            elif returncode == 126:
                suggestion = "Permission denied. Check file permissions."
            elif returncode == 2:
                suggestion = "Misuse of shell command. Check syntax and arguments."
            elif "No such file" in last_stderr:
                suggestion = "Path not found. Check the file/directory path."

            return ToolResult(
                success=False,
                output=output.strip(),
                error=f"Exit code {returncode}",
                metadata={
                    "exit_code": returncode,
                    "command": command,
                    "suggestion": suggestion,
                },
            )
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            output="",
            error=f"Command timed out after {timeout}s",
            metadata={
                "suggestion": "Increase timeout, use a simpler command, "
                "or break the task into smaller steps",
                "timeout": timeout,
            },
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


SHELL_TOOL = ToolSpec(
    name="shell",
    description=(
        "Execute a shell command and return its output (stdout + stderr).\n\n"
        "Best for: running build commands, git operations, pip/npm install, "
        "file operations not covered by other tools, system checks.\n"
        "Not recommended for: reading files (use read_file), searching code (use grep), "
        "writing files (use write_file) — use specialized tools when available.\n"
        "Common mistakes: not quoting arguments with spaces, using absolute paths when relative works, "
        "not handling errors from the output.\n"
        "Output: stdout and stderr combined. Exit code 0 = success.\n\n"
        "Example: {'command': 'git log --oneline -5', 'cwd': '/path/to/repo'}"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute (supports pipes, redirects, etc.)",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command (default: current directory)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 60, max: 300)",
            },
        },
        "required": ["command"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "output": {"type": "string", "description": "Combined stdout and stderr"},
            "exit_code": {"type": "integer", "description": "Process exit code (0 = success)"},
        },
    },
    stable_id="TOOL-SHELL-EXEC-001",
    handler=_shell,
)
