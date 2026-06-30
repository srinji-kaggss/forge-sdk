"""Regression test for LgwksToolAdapter — no shell=True fallback on shlex failure.

Run with: pytest tests/test_adapters.py -v
"""

from __future__ import annotations

from forge_sdk.tools.adapters import LgwksToolAdapter


async def test_unbalanced_quotes_blocked_not_shell_true():
    """A command string that fails shlex.split must be rejected outright,
    never silently retried with shell=True (the exact F3/AUDIT-MATRIX-001
    bug class). The wrapped lgwks_fn must never be invoked in this case.
    """
    called = False

    async def lgwks_fn(**kwargs):
        nonlocal called
        called = True
        return {"success": True, "output": "should not run"}

    adapter = LgwksToolAdapter(
        stable_id="TEST-001",
        name="test_tool",
        description="test",
        lgwks_fn=lgwks_fn,
    )
    spec = adapter.to_tool_spec()

    result = await spec.handler(command="echo 'unterminated")

    assert called is False
    assert result.success is False
    assert result.metadata.get("blocked") is True
    assert "shell=True fallback is disabled" in result.error


async def test_balanced_command_parsed_with_shell_false():
    """A well-formed command string is split safely and shell stays False."""
    received: dict = {}

    async def lgwks_fn(**kwargs):
        received.update(kwargs)
        return {"success": True, "output": "ok"}

    adapter = LgwksToolAdapter(
        stable_id="TEST-002",
        name="test_tool",
        description="test",
        lgwks_fn=lgwks_fn,
    )
    spec = adapter.to_tool_spec()

    result = await spec.handler(command="echo hello world")

    assert result.success is True
    assert received["command"] == ["echo", "hello", "world"]
    assert received["shell"] is False
