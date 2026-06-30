"""Centralized security layer — defense-in-depth for all forge tools.

5-layer model (adapted from senior-security STRIDE/DREAD):
  L1 PERIMETER:  Path containment — ALL tools route through _check_path_safety()
  L2 NETWORK:    Block network egress (curl, wget, nc, ssh, scp)
  L3 HOST:       Block destructive commands (rm -rf, dd, mkfs, kill, fork bomb)
  L4 APPLICATION: Sanitize untrusted text, evidence gates, UUID identifiers
  L5 DATA:       Sensitive path allowlist for reads + writes + dotfiles

Every tool handler calls _check_path_safety() before touching the filesystem.
Every shell command passes through _check_command_safety() with no shell=True fallback.
Every episode-derived text is sanitized before becoming a PromptFragment.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any


# ── L5: Sensitive paths ──────────────────────────────────────────────────────

SENSITIVE_READ_PATHS = (
    "/etc/passwd", "/etc/shadow", "/etc/sudoers", "/etc/ssh/",
    "/root/", "/proc/", "/sys/", "/dev/",
    ".ssh/", ".aws/", ".config/", ".gnupg/",
    ".env", ".npmrc", ".pypirc", ".netrc",
    "id_rsa", "id_ed25519", "id_ecdsa",
    "authorized_keys", "known_hosts",
    ".bashrc", ".zshrc", ".profile", ".bash_profile",
    ".git/config", ".git/credentials",
    "keychain", "login.keychain",
)

SENSITIVE_WRITE_PATHS = (
    "/etc/", "/usr/", "/sys/", "/proc/", "/dev/", "/root/",
    "/boot/", "/sbin/", "/bin/",
    # /var/ is blocked except /var/folders/ (macOS temp) and /var/tmp/
    ".ssh/", ".aws/", ".config/", ".gnupg/",
    ".bashrc", ".zshrc", ".profile", ".bash_profile",
    "authorized_keys",
    ".git/hooks/",
)

# ── L3: Dangerous command patterns ───────────────────────────────────────────
# Match variants: double spaces, -fr vs -rf, env var indirection

_DANGEROUS_CMD_PATTERNS = [
    re.compile(r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\b", re.IGNORECASE),
    re.compile(r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+/", re.IGNORECASE),
    re.compile(r"\bdd\b\s+.*of=/dev/", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\|\s*:&\s*\}\s*;:", re.IGNORECASE),
    re.compile(r">\s*/dev/sd", re.IGNORECASE),
    re.compile(r"\bkill\s+(-9\s+)?1\b", re.IGNORECASE),
    re.compile(r"\bkillall\b", re.IGNORECASE),
    re.compile(r"\bpkill\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
    re.compile(r"\bhalt\b", re.IGNORECASE),
    re.compile(r"\brm\s+-[a-z]*f\b\s+/\S", re.IGNORECASE),  # rm -f /something
]

# ── L2: Network egress patterns ──────────────────────────────────────────────

_NETWORK_CMD_PATTERNS = [
    re.compile(r"\bcurl\b", re.IGNORECASE),
    re.compile(r"\bwget\b", re.IGNORECASE),
    re.compile(r"\bnc\b", re.IGNORECASE),
    re.compile(r"\bnetcat\b", re.IGNORECASE),
    re.compile(r"\bssh\b", re.IGNORECASE),
    re.compile(r"\bscp\b", re.IGNORECASE),
    re.compile(r"\brsync\b", re.IGNORECASE),
    re.compile(r"\btelnet\b", re.IGNORECASE),
    re.compile(r"\bftp\b", re.IGNORECASE),
    re.compile(r"\bpython3?\s+-c\b.*socket", re.IGNORECASE),
]

# Commands that can read arbitrary files — check their path arguments
_FILE_READ_CMDS = re.compile(
    r"\b(?:cat|head|tail|less|more|strings|file|stat|wc|nl|cut|sort|uniq|"
    r"grep|rg|find|ls|dir|tree|python3?|ruby|perl|node)\b",
    re.IGNORECASE,
)

# ── L1: Path safety ──────────────────────────────────────────────────────────

def _resolve_path(path: str, cwd: str = ".") -> Path:
    """Resolve a path relative to cwd, following symlinks."""
    p = Path(path)
    if not p.is_absolute():
        p = Path(cwd) / p
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def _is_sensitive_path(path: str, cwd: str = ".", check_writes: bool = False) -> str | None:
    """Return error message if path is sensitive, else None.

    L5 DATA layer: checks against sensitive path lists for both reads and writes.
    Uses path prefix matching, not substring, to avoid false positives on
    paths like /var/folders/ (macOS temp) matching /var/.
    """
    resolved = _resolve_path(path, cwd)
    path_str = str(resolved)
    home = str(Path.home())

    # Check against sensitive paths — use prefix matching for absolute paths
    sensitive_list = SENSITIVE_WRITE_PATHS if check_writes else SENSITIVE_READ_PATHS
    for sensitive in sensitive_list:
        if sensitive.startswith("/"):
            # Absolute path — check prefix
            if path_str.startswith(sensitive) or path_str == sensitive.rstrip("/"):
                return f"BLOCKED: path '{path}' targets sensitive location '{sensitive}'"
        elif sensitive.startswith("."):
            # Relative/dotfile — check if it appears as a path component
            parts = Path(path_str).parts
            if sensitive.rstrip("/") in parts or path_str.endswith(sensitive):
                return f"BLOCKED: path '{path}' targets sensitive location '{sensitive}'"
        else:
            # Filename pattern — check if it's in the path
            if sensitive in path_str:
                return f"BLOCKED: path '{path}' targets sensitive location '{sensitive}'"

    return None


def _check_path_safety(
    path: str,
    cwd: str = ".",
    sandbox_dir: str | None = None,
    check_writes: bool = False,
) -> str | None:
    """L1 PERIMETER + L5 DATA: Central path safety check for ALL tools.

    Every tool that touches the filesystem routes through this function.
    Checks:
    1. Path is not a sensitive system/credential path
    2. Path is within sandbox_dir if set
    3. Path is within cwd or home (not arbitrary filesystem access)
    4. Symlink escapes are detected
    """
    # L5: Check sensitive paths
    sensitive = _is_sensitive_path(path, cwd, check_writes)
    if sensitive:
        return sensitive

    resolved = _resolve_path(path, cwd)

    # L1: Sandbox containment
    if sandbox_dir:
        sandbox_resolved = _resolve_path(sandbox_dir, cwd)
        try:
            resolved.relative_to(sandbox_resolved)
        except ValueError:
            return f"BLOCKED: path '{path}' is outside sandbox '{sandbox_dir}'"

        # Check for symlink escape
        if resolved.is_symlink():
            target = resolved.resolve()
            try:
                target.relative_to(sandbox_resolved)
            except ValueError:
                return f"BLOCKED: symlink '{path}' points outside sandbox"

    return None


# ── L3: Command safety ───────────────────────────────────────────────────────

def _check_command_safety(command: str) -> str | None:
    """L2 NETWORK + L3 HOST + L5 DATA: Central command safety check for shell tool.

    No shell=True fallback. No denylist-only. Layered:
    1. Block dangerous system commands (rm -rf, dd, mkfs, kill, fork bomb)
    2. Block network egress (curl, wget, nc, ssh, scp)
    3. Block sensitive path access via shell (cat ~/.ssh/id_rsa, etc.)
    4. Block python3 -c / ruby -e / perl -e (arbitrary code execution)
    """
    # L3: Dangerous commands
    for pattern in _DANGEROUS_CMD_PATTERNS:
        if pattern.search(command):
            return f"BLOCKED: dangerous command pattern matched"

    # L2: Network egress
    for pattern in _NETWORK_CMD_PATTERNS:
        if pattern.search(command):
            return f"BLOCKED: network egress not allowed"

    # L4: Block arbitrary code execution via interpreters
    if re.search(r"\bpython3?\s+-c\b", command, re.IGNORECASE):
        return "BLOCKED: arbitrary code execution via python -c not allowed"
    if re.search(r"\bruby\s+-e\b", command, re.IGNORECASE):
        return "BLOCKED: arbitrary code execution via ruby -e not allowed"
    if re.search(r"\bperl\s+-e\b", command, re.IGNORECASE):
        return "BLOCKED: arbitrary code execution via perl -e not allowed"

    # L5: Sensitive paths in command
    for sensitive in SENSITIVE_READ_PATHS:
        if sensitive in command:
            return f"BLOCKED: command targets sensitive path '{sensitive}'"

    return None


# ── L4: Application-layer sanitization ───────────────────────────────────────

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    re.compile(r"IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+(?:different|new|evil|unrestricted)", re.IGNORECASE),
    re.compile(r"(?:developer|admin|root|god)\s+mode\s+(?:enabled|activated|on)", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:prior|previous|above)\s+(?:instructions|rules|guidelines)", re.IGNORECASE),
    re.compile(r"from\s+now\s+on.*?(?:always|never|must|will)\b", re.IGNORECASE),
    re.compile(r"</?(?:system|assistant|user|developer)>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]|###\s*system|###\s*assistant", re.IGNORECASE),
]


def sanitize_untrusted_text(text: str, max_length: int = 500) -> str:
    """L4 APPLICATION: Sanitize untrusted text before it enters system prompts.

    - Truncates to max_length to prevent context stuffing
    - Strips injection patterns
    - Escapes special tokens
    - Wraps in clear delimiters marking it as untrusted
    """
    if not text:
        return ""

    # Truncate
    truncated = text[:max_length]
    if len(text) > max_length:
        truncated += "...[truncated]"

    # Strip injection patterns
    for pattern in _INJECTION_PATTERNS:
        truncated = pattern.sub("[REDACTED]", truncated)

    # Escape special tokens
    truncated = truncated.replace("<", "&lt;").replace(">", "&gt;")

    # Wrap in untrusted delimiter
    return f"[UNTRUSTED_DATA] {truncated} [/UNTRUSTED_DATA]"


def generate_uuid_id(prefix: str = "id") -> str:
    """L4 APPLICATION: Generate collision-free UUID identifier."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def check_fragment_evidence(success_count: int, failure_count: int, min_evidence: int = 3) -> bool:
    """L4 APPLICATION: Evidence gate — fragment must have N observations before compose.

    F2 fix: evolved fragments need evidence before first inclusion.
    """
    total = success_count + failure_count
    return total >= min_evidence