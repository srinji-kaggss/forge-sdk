"""Regression test for a live-reproduced bug: compound shell commands using
&&, |, ;, or a "cd X &&" prefix silently no-op instead of running.

Found while dogfooding a real forge run: macOS ships a standalone
/usr/bin/cd binary, so shlex.split("cd /path && pytest ...") + shell=False
executes /usr/bin/cd with everything after it (including "pytest ...") as
ignored extra arguments — returning exit code 0 with EMPTY output. The real
command never ran, and the agent got a false success signal instead of an
honest error, which is exactly the failure class this whole harness is
meant to catch, not cause.

_check_command_safety() scans the raw command string via regex before any
execution-mode decision, so routing compound commands through `/bin/sh -c`
does not weaken that check — see tools/shell.py's module docstring.

Run with: pytest tests/test_shell_compound_commands.py -v
"""

from __future__ import annotations

from forge_sdk.tools.shell import _shell


async def test_cd_and_chain_actually_runs_the_second_command(tmp_path):
    marker = tmp_path / "marker.txt"
    marker.write_text("hello from the real command\n")

    result = await _shell(f"cd {tmp_path} && cat marker.txt", cwd=".")

    assert result.success is True
    assert "hello from the real command" in result.output


async def test_pipe_chain_actually_runs(tmp_path):
    result = await _shell("echo hello | wc -l", cwd=str(tmp_path))

    assert result.success is True
    assert result.output.strip() == "1"


async def test_semicolon_chain_actually_runs_both_commands(tmp_path):
    result = await _shell("echo first; echo second", cwd=str(tmp_path))

    assert result.success is True
    assert "first" in result.output
    assert "second" in result.output


async def test_simple_command_without_operators_still_uses_argv_path(tmp_path):
    """The fix must not change behavior for the common, operator-free case."""
    result = await _shell("echo plain", cwd=str(tmp_path))

    assert result.success is True
    assert result.output.strip() == "plain"


async def test_compound_command_still_blocked_by_command_safety(tmp_path):
    """The security boundary (_check_command_safety) must still apply to
    compound commands — routing through /bin/sh -c must not bypass L2/L3."""
    result = await _shell("echo safe && curl http://example.com", cwd=str(tmp_path))

    assert result.success is False
    assert "network egress" in result.error
