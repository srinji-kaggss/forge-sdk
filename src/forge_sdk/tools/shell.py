"""Shell execution tool — runs commands in a subprocess.

v0.5.1: Defense-in-depth security via forge_sdk.security module.
Allowlist-based path checking. Network egress blocked.

v0.6.1: found live — argv-mode execution (shlex.split + shell=False) silently
no-ops on ANY compound command ("cd X && real_cmd", pipes, ";"-chains): macOS
ships a real standalone /usr/bin/cd binary, so shlex.split("cd X && cmd")
produces ['cd', 'X', '&&', 'cmd', ...] and subprocess.run(shell=False) happily
executes /usr/bin/cd with all of '&&', 'cmd', ... as ignored extra arguments —
returning EXIT CODE 0 with EMPTY OUTPUT. real_cmd never ran, and the agent got
a false success signal, not an honest error. This is strictly worse than the
shell=True path it replaced.

_check_command_safety() below runs a regex scan over the RAW command string,
before any shlex/shell parsing — so it enforces the same L2/L3/L4 blocklist
regardless of how the command is subsequently executed. Routing compound
commands through a real shell (`/bin/sh -c`) therefore does not weaken that
check; it only makes shell operators actually mean what they say instead of
silently doing nothing. Simple, operator-free commands still run via the
original shlex/argv path unchanged.
"""

from __future__ import annotations

import re
import shlex
import subprocess

from forge_sdk.security import _check_command_safety, _check_path_safety
from forge_sdk.tools import ToolResult, ToolSpec

# Characters/sequences that only mean something to a real shell — a raw
# argv exec (shell=False) either ignores them as literal tokens or, worse,
# hands them to a standalone binary that shares a builtin's name (cd, echo)
# and silently no-ops. Detected on the RAW string, same as _check_command_safety.
_SHELL_OPERATOR_PATTERN = re.compile(r"&&|\|\||[|;<>]|\$\(|`|\bcd\s")


async def _shell(command: str, cwd: str = ".", timeout: int = 60) -> ToolResult:
    timeout = min(max(timeout, 1), 300)

    # L2+L3: Security check via centralized layer
    violation = _check_command_safety(command)
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

    # Compound commands (&&, |, ;, cd-prefix, redirects, substitution) need a
    # real shell to mean what they say — see the module docstring. The security
    # boundary is _check_command_safety() above, which already scanned the raw
    # string; this only decides HOW the (already-approved) command executes.
    if _SHELL_OPERATOR_PATTERN.search(command):
        popen_args: list[str] | str = ["/bin/sh", "-c", command]
    else:
        try:
            popen_args = shlex.split(command)
        except ValueError as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Command parse failed (unbalanced quotes): {exc}. Fix the quoting.",
                metadata={"command": command, "blocked": True},
            )

    try:
        result = subprocess.run(
            popen_args,
            shell=False,  # even the compound-command path: explicit argv to /bin/sh -c, not shell=True
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}" if output else result.stderr

        if result.returncode == 0:
            return ToolResult(
                success=True,
                output=output.strip() or "(no output)",
                metadata={"exit_code": result.returncode, "command": command},
            )
        else:
            suggestion = ""
            if result.returncode == 127:
                suggestion = "Command not found. Check if the program is installed."
            elif result.returncode == 126:
                suggestion = "Permission denied. Check file permissions."
            elif result.returncode == 2:
                suggestion = "Misuse of shell command. Check syntax and arguments."
            elif "No such file" in result.stderr:
                suggestion = "Path not found. Check the file/directory path."

            return ToolResult(
                success=False,
                output=output.strip(),
                error=f"Exit code {result.returncode}",
                metadata={
                    "exit_code": result.returncode,
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
