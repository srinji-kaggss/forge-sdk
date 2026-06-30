"""Regression tests for issue #24 — explicit read-only instructions must
override the positive action-verb/error-keyword heuristic used to decide
whether a task without file edits should be marked success:false.

Run with: pytest tests/test_task_implies_edits.py -v
"""

from __future__ import annotations

from forge_sdk.agents.react import ReactAgent


def _agent() -> ReactAgent:
    return ReactAgent(model=object(), tools=object())


def test_explicit_read_only_task_with_bug_keyword_does_not_imply_edits():
    """The exact issue #24 repro shape: an audit task that says 'bug' and
    'security' but is explicitly read-only.
    """
    agent = _agent()
    task = (
        "READ-ONLY audit: investigate this subsystem for security bugs and "
        "produce a markdown report. Do NOT edit any file."
    )
    assert agent._task_implies_edits(task) is False


def test_report_only_phrasing_does_not_imply_edits():
    agent = _agent()
    task = "Summarize what this repo does. Report only, no file changes."
    assert agent._task_implies_edits(task) is False


def test_dont_modify_phrasing_does_not_imply_edits():
    agent = _agent()
    task = "Look for the root cause of this crash. Don't modify any files, just explain."
    assert agent._task_implies_edits(task) is False


def test_plain_edit_task_still_implies_edits():
    """Sanity check: the fix must not blanket-disable the heuristic."""
    agent = _agent()
    assert agent._task_implies_edits("Fix the bug in lgwks_search.py") is True
    assert agent._task_implies_edits("Implement the missing validation logic") is True


def test_scoped_exclusion_naming_another_file_still_implies_edits():
    """Real repro: a bounded edit task that scopes OUT a specific other file
    ("don't touch any other file", "don't modify X.py itself") must still be
    treated as an edit task — these are scoping guardrails on a real edit
    task, not a blanket read-only statement, and conflating them silently
    disabled the zero-edits-but-task-implied-edits safety net.
    """
    agent = _agent()
    task = (
        "Add a regression test file tests/test_x.py. "
        "Do not touch any other file. Do not modify lgwks_redact.py itself."
    )
    assert agent._task_implies_edits(task) is True


def test_plain_research_task_without_negation_still_uses_keyword_heuristic():
    """No read-only marker present -> existing keyword-based behavior is
    unchanged (this task class genuinely is ambiguous without an explicit
    read-only statement, which is exactly why issue #24 asked for callers
    to state it explicitly rather than asking the heuristic to guess harder).
    """
    agent = _agent()
    assert agent._task_implies_edits("There is a critical security vulnerability here") is True
