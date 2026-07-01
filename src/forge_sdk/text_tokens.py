"""Canonical file-path-token extraction.

Was two independently-maintained, byte-identical copies of the same regex —
`_FILE_PATH_TOKEN` in agents/react.py and `_SPEC_FILE_PATH_TOKEN` in
verifiers/__init__.py — each used to detect file targets named in a task
description. Both carried the same false positive: common English
abbreviations like "e.g." and "i.e." parse as a fake one-letter-extension
file ("e.g." -> stem "e", ext "g"), found live when a task's parenthetical
"(e.g. RATIFIED or ...)" was flagged as a missing edit target.
"""

from __future__ import annotations

import re

FILE_PATH_TOKEN = re.compile(r"\b[\w][\w./-]*\.[A-Za-z]{1,5}\b")

_NON_FILE_ABBREVIATIONS = frozenset({"e.g", "i.e"})


def is_real_file_token(token: str) -> bool:
    """False for common prose abbreviations FILE_PATH_TOKEN mismatches as files."""
    return token.lower() not in _NON_FILE_ABBREVIATIONS
