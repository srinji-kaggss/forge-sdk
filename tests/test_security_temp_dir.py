"""Regression tests for issue #17 — an agent operating under a project
sandbox must still be able to read back files it wrote to the OS scratch
directory; the sandbox containment check used to block that unconditionally.

Run with: pytest tests/test_security_temp_dir.py -v
"""

from __future__ import annotations

import tempfile

from forge_sdk.security import _check_path_safety


def test_tmp_path_allowed_for_read_even_with_sandbox_set(tmp_path):
    sandbox = str(tmp_path / "project")
    scratch = tempfile.gettempdir() + "/forge-issue-17-scratch.txt"

    assert _check_path_safety(scratch, sandbox, sandbox, check_writes=False) is None


def test_tmp_path_allowed_for_write_even_with_sandbox_set(tmp_path):
    sandbox = str(tmp_path / "project")
    scratch = tempfile.gettempdir() + "/forge-issue-17-scratch.txt"

    assert _check_path_safety(scratch, sandbox, sandbox, check_writes=True) is None


def test_literal_tmp_path_allowed_even_with_sandbox_set(tmp_path):
    """The exact path the issue names: /tmp specifically (which on macOS is
    a symlink to /private/tmp, distinct from tempfile.gettempdir()'s
    per-user /var/folders/.../T/ dir -- both must work).
    """
    sandbox = str(tmp_path / "project")
    assert _check_path_safety("/tmp/forge-issue-17.txt", sandbox, sandbox, check_writes=True) is None
    assert _check_path_safety("/tmp/forge-issue-17.txt", sandbox, sandbox, check_writes=False) is None


def test_traversal_escape_via_tmp_is_still_blocked(tmp_path):
    """Issue #17's fix must not become a new escape hatch: a path that
    starts under /tmp but traverses back OUT (e.g. /tmp/../etc/passwd)
    resolves outside both the sandbox AND the temp root, and must still
    be blocked.
    """
    sandbox = str(tmp_path / "project")
    result = _check_path_safety("/tmp/../etc/passwd", sandbox, sandbox, check_writes=False)
    assert result is not None
    assert "BLOCKED" in result


def test_non_tmp_outside_sandbox_still_blocked():
    """Sanity check: the fix is scoped to the temp dir specifically, not a
    blanket sandbox bypass. pytest's own tmp_path fixture lives inside the
    system temp root, so this test deliberately uses a path that is neither
    the sandbox nor under any temp dir.
    """
    sandbox = "/Users/srinji/.forge-issue-17-sandbox-test"
    other_dir = "/Users/srinji/.forge-issue-17-not-sandboxed"
    result = _check_path_safety(f"{other_dir}/file.txt", sandbox, sandbox, check_writes=False)
    assert result is not None
    assert "BLOCKED" in result


def test_write_then_read_back_round_trip_under_sandbox(tmp_path):
    """End-to-end repro of issue #17's exact sequence: write to /tmp
    succeeds, then read it back also succeeds, under an active sandbox.
    """
    sandbox = str(tmp_path / "project")
    scratch_path = tempfile.gettempdir() + "/forge-issue-17-roundtrip.txt"

    write_check = _check_path_safety(scratch_path, sandbox, sandbox, check_writes=True)
    assert write_check is None

    with open(scratch_path, "w") as f:
        f.write("scratch output")

    try:
        read_check = _check_path_safety(scratch_path, sandbox, sandbox, check_writes=False)
        assert read_check is None
    finally:
        import os

        os.remove(scratch_path)
