"""Regression tests for filesystem tools — write_file lazy-rewrite guard.

Run with: pytest tests/test_filesystem.py -v
"""

from __future__ import annotations

from forge_sdk.tools.filesystem import _write_file


async def test_write_file_blocks_elision_marker(tmp_path):
    """Regression for issue #21: refuse content containing a literal
    elision placeholder instead of real file content.
    """
    target = tmp_path / "search.py"
    target.write_text("def search():\n    return 1\n")

    bad_content = (
        "def search():\n"
        "    return 2\n\n"
        "# [Previous file content remains identical until the search() function]\n"
    )
    result = await _write_file(str(target), bad_content)

    assert result.success is False
    assert result.metadata["reason"] == "elision_marker"
    # File on disk must be untouched.
    assert target.read_text() == "def search():\n    return 1\n"


async def test_write_file_blocks_large_shrink(tmp_path):
    """Regression for issue #21: refuse a drastic shrink of an existing
    file (the lgwks_files.py 171->21 line case) without an explicit force.
    """
    target = tmp_path / "files.py"
    target.write_text("x = 1\n" * 100)  # 600 bytes

    result = await _write_file(str(target), "x = 1\n")  # 6 bytes

    assert result.success is False
    assert result.metadata["reason"] == "shrink_guard"
    assert target.read_text() == "x = 1\n" * 100


async def test_write_file_force_bypasses_shrink_guard(tmp_path):
    """An explicit force=True still allows an intentional drastic rewrite."""
    target = tmp_path / "files.py"
    target.write_text("x = 1\n" * 100)

    result = await _write_file(str(target), "x = 1\n", force=True)

    assert result.success is True
    assert target.read_text() == "x = 1\n"


async def test_write_file_normal_edit_unaffected(tmp_path):
    """Sanity check: a normal same-size-ish edit to an existing file, or
    creating a new file, is unaffected by the guard.
    """
    target = tmp_path / "new.py"
    result = await _write_file(str(target), "print('hello')\n")
    assert result.success is True
    assert target.read_text() == "print('hello')\n"

    result2 = await _write_file(str(target), "print('hello world')\n")
    assert result2.success is True
    assert target.read_text() == "print('hello world')\n"
