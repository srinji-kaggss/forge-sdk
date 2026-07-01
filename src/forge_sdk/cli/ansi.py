"""Tiny ANSI styling helper — zero dependencies (L5).

Auto-disables color when stdout is not a TTY or when NO_COLOR is set, so
`forge run` output stays copy-pasteable in logs, pipes, and CI. This is the
only place rendering touches escape codes; renderers consume the helpers
below and never hard-code raw bytes.
"""

from __future__ import annotations

import os
import sys

# Reset
_RESET = "\033[0m"

# Foreground SGR codes
_CODES = {
    "dim": "\033[2m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
}


def supports_color(stream: object | None = None) -> bool:
    """True only when color won't corrupt piped/CI output.

    Respects the de-facto `NO_COLOR` convention (https://no-color.org/).
    Defaults to inspecting ``sys.stdout``; pass a stream with ``isatty`` to
    check a specific one.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    target = stream if stream is not None else sys.stdout
    isatty = getattr(target, "isatty", None)
    return bool(isatty and isatty())


def style(text: str, *names: str, stream: object | None = None) -> str:
    """Wrap ``text`` in the named styles, no-op when color is disabled."""
    if not supports_color(stream):
        return text
    prefix = "".join(_CODES[n] for n in names if n in _CODES)
    if not prefix:
        return text
    return f"{prefix}{text}{_RESET}"


# Convenience wrappers for common styles
def dim(text: str) -> str:
    return style(text, "dim")


def bold(text: str) -> str:
    return style(text, "bold")


def green(text: str) -> str:
    return style(text, "green")


def red(text: str) -> str:
    return style(text, "red")


def yellow(text: str) -> str:
    return style(text, "yellow")


def blue(text: str) -> str:
    return style(text, "blue")


def success(text: str) -> str:
    return style(text, "green", "bold")


def error(text: str) -> str:
    return style(text, "red", "bold")


def info(text: str) -> str:
    return style(text, "blue")


def warn(text: str) -> str:
    return style(text, "yellow")
