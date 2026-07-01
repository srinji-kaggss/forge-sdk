"""Regression test for a live-reproduced bug: compound shell commands using
&&, |, ;, or a "cd X &&" prefix silently no-op instead of running.

Found while dogfooding a real forge run: macOS ships a standalone
/usr/bin/cd binary, so shlex.split("cd /path && pytest ...") + shell=False
executes /usr/bin/cd with everything after it (including "pytest ...") as
ignored extra arguments — returning exit code 0 with EMPTY output. The real
command never ran, and the agent got a false success signal instead of an
honest error, which is exactly the failure class this whole harness is
meant to catch, not cause.

Fixed once by routing operator-bearing commands through `/bin/sh -c` — that
reopened real shell execution behind a regex denylist and was itself a real,
reproduced vulnerability (see
test_command_substitution_cannot_achieve_arbitrary_execution below). Fixed
again by interpreting &&/||/;/| and `cd` directly as an argv-only state
machine — see tools/shell.py's module docstring for the current design.

Run with: pytest tests/test_shell_compound_commands.py -v
"""

from __future__ import annotations

import base64

from forge_sdk.security import _check_command_safety
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
    compound commands."""
    result = await _shell("echo safe && curl http://example.com", cwd=str(tmp_path))

    assert result.success is False
    assert "network egress" in result.error


async def test_command_substitution_cannot_achieve_arbitrary_execution(tmp_path):
    """Regression for a real, execution-proven vulnerability in the prior
    fix for this file: routing operator-bearing commands through
    `/bin/sh -c` reintroduced real shell semantics behind a regex denylist
    (_check_command_safety), which is provably incomplete — no pattern in
    L2/L3 names a base64-decoded, dynamically-constructed command. Proven
    live: `echo safe; $(echo <base64 of an arbitrary command> | base64 -d
    | sh)` created a marker file when run through the /bin/sh -c path,
    with `_check_command_safety` returning no violation at all. This test
    fails if that class of bypass is ever reintroduced.
    """
    marker = tmp_path / "marker.txt"
    encoded = base64.b64encode(f"touch {marker}".encode()).decode()
    payload = f"echo build-step-1; $(echo {encoded} | base64 -d | sh) ; echo build-step-2"

    assert _check_command_safety(payload) is None, (
        "expected this payload to be invisible to the regex denylist — "
        "that's the whole point of the regression"
    )

    await _shell(payload, cwd=str(tmp_path))

    assert not marker.exists(), "command substitution achieved arbitrary execution"
