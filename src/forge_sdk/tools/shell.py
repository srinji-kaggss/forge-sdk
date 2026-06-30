"""Shell execution tool — runs commands in a subprocess."""

from __future__ import annotations

import subprocess

from forge_sdk.tools import ToolResult, ToolSpec


async def _shell(command: str, cwd: str = ".", timeout: int = 60) -> ToolResult:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}" if output else result.stderr
        return ToolResult(
            success=result.returncode == 0,
            output=output.strip(),
            metadata={"exit_code": result.returncode},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output="", error=f"Command timed out after {timeout}s")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


SHELL_TOOL = ToolSpec(
    name="shell",
    description="Execute a shell command and return its output.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "cwd": {"type": "string", "description": "Working directory"},
            "timeout": {"type": "integer", "description": "Timeout in seconds"},
        },
        "required": ["command"],
    },
    output_schema={
        "type": "object",
        "properties": {"output": {"type": "string"}, "exit_code": {"type": "integer"}},
    },
    stable_id="TOOL-SHELL-EXEC-001",
    handler=_shell,
)
