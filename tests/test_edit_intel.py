"""Regression tests for edit-intel tools — syntax guard on every write.

Run with: pytest tests/test_edit_intel.py -v
"""

from __future__ import annotations

from forge_sdk.tools.advanced.edit_intel import (
    insert_at,
    multi_edit,
    patch_line,
    patch_symbol,
)

GOOD_FILE = '''def foo():
    return 1


def bar():
    if True:
        return 2
    return 3
'''


async def test_patch_line_refuses_broken_indentation(tmp_path):
    """Regression for issue #22: patching a line that leaves an `if` with
    no body must be refused, not written.
    """
    target = tmp_path / "mod.py"
    target.write_text(GOOD_FILE)

    # Line 7 is the if's only body line ("        return 2"). Dedenting it
    # out of the if leaves the if with no indented block at all.
    result = await patch_line(str(target), 7, "    return 2")  # dedented out of the if
    assert result.success is False
    assert result.metadata["reason"] == "syntax_check"
    assert target.read_text() == GOOD_FILE  # untouched


async def test_patch_symbol_refuses_broken_output(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text(GOOD_FILE)

    # New body with bad indentation relative to what patch_symbol assembles
    # (it indents every line uniformly, so an internal dedent inside the
    # body breaks parsing).
    bad_body = "if True:\nreturn 2"  # second line will be mis-indented after uniform-indent
    result = await patch_symbol(str(target), "bar", bad_body)
    assert result.success is False
    assert result.metadata["reason"] == "syntax_check"
    assert target.read_text() == GOOD_FILE


async def test_insert_at_refuses_broken_output(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text(GOOD_FILE)

    result = await insert_at(str(target), 1, "    this is not valid python (((")
    assert result.success is False
    assert result.metadata["reason"] == "syntax_check"
    assert target.read_text() == GOOD_FILE


async def test_multi_edit_stops_on_first_failure_and_reports_failure(tmp_path):
    """Regression for issue #22: multi_edit must not report success:true
    when a sub-edit was refused, and must not keep applying edits against
    a file state the caller never reasoned about.
    """
    target = tmp_path / "mod.py"
    target.write_text(GOOD_FILE)

    edits = [
        {"type": "line", "line_number": 2, "new_content": "    return 1  # ok"},
        {"type": "line", "line_number": 7, "new_content": "    return 2"},  # breaks the if
        {"type": "line", "line_number": 8, "new_content": "    return 99"},  # would never get here
    ]
    result = await multi_edit(str(target), edits)

    assert result.success is False
    assert result.metadata["edits_applied"] == 1
    assert result.metadata["edits_requested"] == 3
    # First edit landed, second was refused, third never attempted — file
    # must still parse.
    import ast
    ast.parse(target.read_text())


async def test_multi_edit_happy_path_unaffected(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text(GOOD_FILE)

    edits = [
        {"type": "line", "line_number": 2, "new_content": "    return 100"},
    ]
    result = await multi_edit(str(target), edits)
    assert result.success is True
    assert "return 100" in target.read_text()
