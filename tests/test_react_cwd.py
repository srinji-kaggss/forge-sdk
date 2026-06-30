"""Regression tests for issue #23 — AgentContext.cwd must actually scope
tool calls, not just sit there decoratively while tools resolve relative
paths against the process's real os.getcwd().

Run with: pytest tests/test_react_cwd.py -v
"""

from __future__ import annotations

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry


def _agent(tools: object | None = None) -> ReactAgent:
    # _resolve_cwd's cwd-handling logic touches no model/tool state
    # directly, so a dummy model/tools placeholder is enough for the
    # pure-function tests; _execute_tool tests need a real registry.
    return ReactAgent(model=object(), tools=tools if tools is not None else object())


def _real_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for tool in FILE_TOOLS:
        reg.register(tool)
    return reg


def test_resolve_cwd_rewrites_relative_path_to_context_cwd(tmp_path):
    agent = _agent()
    other_repo = tmp_path / "lgwks"
    other_repo.mkdir()

    resolved = agent._resolve_cwd("read_file", {"path": "lgwks_agent.py"}, str(other_repo))

    assert resolved["path"] == str((other_repo / "lgwks_agent.py").resolve())


def test_resolve_cwd_injects_default_param_when_absent():
    """list_dir/grep/glob/run_tests/shell etc. have a path-ish param that
    defaults to "." in the handler signature — when the LLM omits it
    entirely, that default must resolve to context.cwd, not os.getcwd().
    """
    agent = _agent()

    resolved = agent._resolve_cwd("list_dir", {}, "/Users/srinji/some-repo")
    assert resolved["path"] == "/Users/srinji/some-repo"

    resolved_shell = agent._resolve_cwd("shell", {"command": "git status"}, "/Users/srinji/some-repo")
    assert resolved_shell["cwd"] == "/Users/srinji/some-repo"
    assert resolved_shell["command"] == "git status"  # untouched


def test_resolve_cwd_leaves_absolute_paths_alone():
    agent = _agent()
    resolved = agent._resolve_cwd("read_file", {"path": "/etc/hosts"}, "/Users/srinji/some-repo")
    assert resolved["path"] == "/etc/hosts"


def test_resolve_cwd_noop_when_context_cwd_is_dot():
    """Default AgentContext.cwd == "." — must not change existing
    single-process behavior for callers who never set cwd at all.
    """
    agent = _agent()
    action_input = {"path": "foo.py"}
    resolved = agent._resolve_cwd("read_file", action_input, ".")
    assert resolved is action_input  # short-circuited, not even copied


async def test_execute_tool_scopes_relative_path_to_context_cwd(tmp_path):
    """End-to-end at the real dispatch boundary: same relative path, same
    AgentContext(cwd=...), two different repos -- must read from the repo
    named in context.cwd, reproducing the exact two-repo repro in issue #23
    but asserting it now resolves correctly instead of describing the
    wrong repo.
    """
    forge_like = tmp_path / "forge"
    forge_like.mkdir()
    (forge_like / "marker.py").write_text("FORGE_MARKER = 1\n")

    lgwks_like = tmp_path / "logicalworks-"
    lgwks_like.mkdir()
    (lgwks_like / "marker.py").write_text("LGWKS_MARKER = 1\n")

    agent = _agent(tools=_real_registry())
    context = AgentContext(task="describe this repo", cwd=str(lgwks_like))

    observation = await agent._execute_tool("read_file", {"path": "marker.py"}, context)

    assert "LGWKS_MARKER" in observation
    assert "FORGE_MARKER" not in observation
