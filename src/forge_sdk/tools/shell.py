"""Shell execution tool — runs commands in a subprocess.

v0.4.0: Uses shell=False by default (shlex.split), audit logging, timeout validation.
"""

from __future__ import annotations

import shlex
import subprocess

from forge_sdk.tools import ToolResult, ToolSpec

# Paths that commands must not read/write/execute on
_SENSITIVE_PATHS = ("/etc/passwd", "/etc/shadow", "/etc/sudoers", "/root/", "/proc/", "/sys/")
_DANGEROUS_CMDS = ("rm -rf", "dd ", "mkfs", ":(){ :|:& };:", "> /dev/sda")


def _check_command_safety(command: str) -> str | None:
    """Return error message if command is unsafe, else None."""
    cmd_lower = command.lower()
    # Block dangerous command patterns
    for d in _DANGEROUS_CMDS:
        if d in cmd_lower:
            return f"BLOCKED: dangerous command pattern '{d}'"
    # Block commands targeting sensitive files
    for path in _SENSITIVE_PATHS:
        if path in command:
            return f"BLOCKED: command targets sensitive path '{path}'"
    return None


async def _shell(command: str, cwd: str = ".", timeout: int = 60) -> ToolResult:
    # Validate timeout
    timeout = min(max(timeout, 1), 300)

    # Security check
    violation = _check_command_safety(command)
    if violation:
        import logging
        logging.getLogger("forge.tools.shell").warning("BLOCKED: %s", violation)
        return ToolResult(success=False, output="", error=violation,
                          metadata={"command": command, "blocked": True})

    # Audit log every command
    import logging
    logging.getLogger("forge.tools.shell").warning("SHELL: %s (cwd=%s)", command, cwd)

    # Try shell=False first (safer)
    try:
        args = shlex.split(command)
        use_shell = False
    except ValueError:
        # Complex command — fall back to shell=True but warn
        args = command
        use_shell = True
        logging.getLogger("forge.tools.shell").warning(
            "SHELL: shlex.split failed, using shell=True for: %s", command[:100]
        )

    try:
        result = subprocess.run(
            args,
            shell=use_shell,
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
                "suggestion": "Increase timeout, use a simpler command, or break the task into smaller steps",
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
