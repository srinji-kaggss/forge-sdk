"""Regression test — CLI trace_dir/audit_db must scope to --cwd, not the
process's real os.getcwd().

Found while running a concurrent batch of `forge run` invocations from a
single shared launch directory: every task's traces landed in that shared
directory's .forge/traces/ instead of each task's own --cwd, making
per-task forensics on a concurrent batch impossible. Issue #23 fixed this
for tool-call paths (AgentContext.cwd) but never touched the CLI's own
trace/audit path construction.

Run with: pytest tests/test_cli_trace_cwd.py -v
"""

from __future__ import annotations

from pathlib import Path

from forge_sdk.cli.main import scope_path_to_cwd


def test_relative_path_scopes_to_run_cwd():
    run_cwd = Path("/tmp/task-a")
    assert scope_path_to_cwd(".forge/traces", run_cwd) == run_cwd / ".forge/traces"


def test_absolute_path_left_untouched():
    run_cwd = Path("/tmp/task-a")
    assert scope_path_to_cwd("/var/log/forge/traces", run_cwd) == Path("/var/log/forge/traces")


def test_two_concurrent_cwds_do_not_collide():
    """The exact real repro: two concurrent `forge run --cwd X` invocations
    sharing the default relative trace_dir must not write to the same place.
    """
    a = scope_path_to_cwd(".forge/traces", Path("/tmp/task-a"))
    b = scope_path_to_cwd(".forge/traces", Path("/tmp/task-b"))
    assert a != b
    assert str(a).startswith("/tmp/task-a")
    assert str(b).startswith("/tmp/task-b")
