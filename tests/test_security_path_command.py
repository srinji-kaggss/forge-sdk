"""Regression tests for two live, execution-verified gaps this session:

1. `_check_command_safety` did raw-substring matching on unresolved command
   text only, so any credential store not literally enumerated in
   SENSITIVE_READ_PATHS sailed through unblocked. Verified failing case
   (2026-07-01, opus): `cat ~/.cline/data/settings/settings.json` returned
   ALLOWED. Fixed by (a) a generic credential-filename classifier in
   _is_sensitive_path, and (b) resolving shlex-tokenized path arguments
   through the same resolver the filesystem tools use, instead of a second,
   weaker, raw-text-only check.
2. `git_diff`/`git_status` in verify_intel.py built a shell command string
   via f-string interpolation of an agent-controlled `path` argument and ran
   it through `create_subprocess_shell` — real shell injection, reproduced
   with a crafted path before the fix. Fixed by switching to
   `create_subprocess_exec` (argv list, no shell interpretation) plus a
   `_check_path_safety` gate.

Run with: pytest tests/test_security_path_command.py -v
"""

from __future__ import annotations

from forge_sdk.security import _check_command_safety, _is_sensitive_path
from forge_sdk.tools.advanced.verify_intel import git_status


def test_check_command_safety_blocks_cline_credential_store():
    """Exact verified-failing case: a credential store not in the static
    SENSITIVE_READ_PATHS enumeration must still be blocked."""
    violation = _check_command_safety("cat ~/.cline/data/settings/settings.json")
    assert violation is not None


def test_check_command_safety_blocks_other_unenumerated_agent_credential_stores():
    """Generalization check: the fix must not be a second single-app
    enumeration in disguise — unrelated app names must be caught too."""
    for cmd in (
        "cat ~/.cursor/auth/token.json",
        "cat ~/.codeium/session_secret",
        "less ~/.continue/config/credentials.json",
    ):
        assert _check_command_safety(cmd) is not None, f"not blocked: {cmd}"


def test_check_command_safety_still_allows_benign_dotfiles():
    """The generic classifier must not be so broad it blocks ordinary
    project dotfiles that aren't credential stores."""
    assert _check_command_safety("cat ./.gitignore") is None
    assert _check_command_safety("ls -la .") is None


def test_is_sensitive_path_generic_classifier_direct():
    assert _is_sensitive_path("~/.cline/data/settings/settings.json") is not None
    assert _is_sensitive_path("./README.md") is None


async def test_git_status_rejects_shell_metacharacter_payload(tmp_path):
    """Regression for the create_subprocess_shell injection: a path
    argument crafted to break out of the git command must not execute,
    regardless of whether git itself treats the literal string as a
    (non-matching) pathspec and reports success. The security property is
    non-execution, not the tool's success/failure field.
    """
    marker = tmp_path / "pwned.txt"
    payload = f"; echo INJECTED > {marker} #"

    await git_status(payload)

    assert not marker.exists(), "shell injection executed — marker file was created"


async def test_git_status_normal_path_still_works():
    """`path` is a pathspec filter on the existing repo (original
    semantics), not a cwd to run git in — use a real in-repo relative path.
    """
    result = await git_status("README.md")

    assert result.success is True
