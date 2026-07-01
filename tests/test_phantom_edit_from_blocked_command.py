"""Regression test for a phantom-edit bug found via a live probe (v0.5.2
follow-up): running `forge run` with a task that required web research
produced a shell command blocked by the L2 network-egress check —

    curl -s "https://stripe.com/blog" 2>/dev/null | head -200 || echo "curl failed"

— which never executed, yet still self-reported "1 file(s) changed" and
Status: SUCCESS, because the stderr redirect "2>/dev/null" matched the
write-pattern regex `>\\s*(\\S+)` as if it were a real file write, and the
extraction ran regardless of whether the tool call had actually succeeded.

Run with: pytest tests/test_phantom_edit_from_blocked_command.py -v
"""

from __future__ import annotations

from forge_sdk.agents.react import ReactAgent

BLOCKED_CURL = 'curl -s "https://stripe.com/blog" 2>/dev/null | head -200 || echo "curl failed"'


def _agent() -> ReactAgent:
    return ReactAgent(model=object(), tools=object())


def test_blocked_shell_command_produces_no_phantom_edit():
    agent = _agent()
    edits = agent._extract_edits_from_observation(
        "shell",
        {"command": BLOCKED_CURL},
        "Tool failed: BLOCKED: network egress not allowed",
    )
    assert edits == []


def test_stderr_redirect_alone_is_never_a_write_target():
    """Even on a genuinely successful command, a bare 2>/dev/null must not
    be extracted as an edited file."""
    agent = _agent()
    edits = agent._extract_edits_from_observation(
        "shell",
        {"command": 'echo hi 2>/dev/null'},
        "hi",
    )
    assert edits == []


def test_real_stdout_redirect_on_success_is_still_extracted():
    """The fix must not break the legitimate case: a real `>` redirect on
    a command that actually succeeded is still a real edit."""
    agent = _agent()
    edits = agent._extract_edits_from_observation(
        "shell",
        {"command": "echo hi > out.txt"},
        "",
    )
    assert edits == ["out.txt"]


def test_failed_write_file_call_produces_no_phantom_edit():
    """Same root bug applies to write_file/create_file: a blocked/failed
    write must not be counted as an edit just because a path was named."""
    agent = _agent()
    edits = agent._extract_edits_from_observation(
        "write_file",
        {"path": "../escape.py", "content": "x = 1\n"},
        "Tool failed: BLOCKED: path outside sandbox",
    )
    assert edits == []
