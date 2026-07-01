"""Renderers for the Forge event stream.

ADR-2: Renderers live in the CLI layer. The SDK never touches stdout,
ANSI codes, or output formats. Each renderer consumes AgentEvent objects
from the event callback and renders them to the terminal, a file, or a
machine-readable stream.

Two renderers are provided:
  - TextRenderer: streaming human-readable output with ANSI styling
  - NDJSONRenderer: one JSON object per event line for machine consumers
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Any, Protocol, runtime_checkable

from forge_sdk.cli.ansi import style

# ---------------------------------------------------------------------------
# Renderer protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Renderer(Protocol):
    """Protocol for event stream consumers."""

    def on_event(self, event: Any) -> None: ...
    def on_end(self, exit_code: int) -> None: ...


# ---------------------------------------------------------------------------
# TextRenderer — streaming human-readable with ANSI
# ---------------------------------------------------------------------------

_EVENT_ICONS: dict[str, str] = {
    "run_start": "\u25b6",
    "run_end": "\u25a0",
    "run_error": "\u2717",
    "thought": "\U0001f4ad",
    "action": "\u26a1",
    "observation": "\U0001f4e4",
    "token_usage": "\U0001f4ca",
    "verification": "\u2705",
    "file_edit": "\U0001f4dd",
    "state_update": "\U0001f504",
    "decision": "\U0001f9e0",
}

_VERIFY_ICONS: dict[str, str] = {
    "passed": "\u2705",
    "failed": "\u274c",
}


class TextRenderer:
    """Streaming human-readable output with ANSI styling."""

    def __init__(self, out: Any = None) -> None:
        self._out = out or sys.stdout
        self._run_start_ms: float | None = None

    def on_event(self, event: Any) -> None:
        et = getattr(event, "type", "unknown")
        if et == "run_start":
            self._run_start_ms = getattr(event, "timestamp_ms", 0.0)
            self._print_header(event)
            return
        self._render_event(event)

    def on_end(self, exit_code: int) -> None:
        if exit_code != 0:
            self._writeln(style(f"\nRun failed with exit code {exit_code}.", "red", "bold"))
        self._out.flush()

    def _time_prefix(self, ts: float) -> str:
        if self._run_start_ms is not None:
            rel_s = (ts - self._run_start_ms) / 1000.0
            return f"[{rel_s:7.1f}s]"
        return " " * 9

    def _step_tag(self, step: int) -> str:
        return f" [{style(f'#{step}', 'dim')}]" if step else ""

    def _render_event(self, event: Any) -> None:
        et = getattr(event, "type", "unknown")
        ts = getattr(event, "timestamp_ms", 0.0)
        step = getattr(event, "step", 0)
        tp = self._time_prefix(ts)
        st = self._step_tag(step)

        if et == "run_error":
            msg = getattr(event, "error", "")
            etype = getattr(event, "error_type", "")
            icon = _EVENT_ICONS.get(et, "\u2022")
            self._writeln(
                f"{tp} {style(icon + ' ERROR', 'red', 'bold')}{st}  "
                f"{style(etype, 'yellow')} \u2014 {msg}"
            )

        elif et == "run_end":
            ok = getattr(event, "success", False)
            label = "SUCCESS" if ok else "FAILED"
            color = "green" if ok else "red"
            sc = getattr(event, "total_steps", 0)
            tk = getattr(event, "total_tokens", 0)
            cs = getattr(event, "total_cost_usd", 0.0)
            self._writeln("")
            self._writeln(
                f"{tp} {style(_EVENT_ICONS[et], color, 'bold')} "
                f"{style(label, color, 'bold')}  "
                f"{style(f'{sc} steps', 'dim')}  "
                f"{style(f'{tk} tokens', 'dim')}  "
                f"{style(f'${cs:.4f}', 'dim')}"
            )

        elif et == "thought":
            c = getattr(event, "content", "")
            d = c[:200] + ("..." if len(c) > 200 else "")
            self._writeln(
                f"{tp} {style(_EVENT_ICONS[et] + ' Thought', 'blue')}{st}  {style(d, 'dim')}"
            )

        elif et == "action":
            tool = getattr(event, "tool", "")
            self._writeln(
                f"{tp} {style(_EVENT_ICONS[et] + ' Action', 'cyan')}{st}  {style(tool, 'bold')}"
            )

        elif et == "observation":
            c = getattr(event, "content", "")
            is_err = getattr(event, "is_error", False)
            tool = getattr(event, "tool", "")
            color = "red" if is_err else "green"
            d = c[:120] + ("..." if len(c) > 120 else "")
            self._writeln(
                f"{tp} {style(_EVENT_ICONS[et], color)} "
                f"{style(f'Obs ({tool})', color)}{st}  {style(d, 'dim')}"
            )

        elif et == "token_usage":
            total = getattr(event, "total_tokens", 0)
            self._writeln(
                f"{tp} {style(_EVENT_ICONS[et] + ' Tokens', 'magenta')}{st}  "
                f"{style(str(total), 'bold')} tokens used"
            )

        elif et == "verification":
            gate = getattr(event, "gate_name", "")
            status = getattr(event, "status", "")
            detail = getattr(event, "detail", "")
            vi = _VERIFY_ICONS.get(status, "\u2753")
            color = "green" if status == "passed" else "red"
            self._writeln(
                f"{tp} {style(vi + ' Verify', color)}{st}  "
                f"{style(gate, 'bold')} \u2014 {style(status, color)}"
            )
            if detail:
                self._writeln(f"{' ' * 9}          {style(detail[:120], 'dim')}")

        elif et == "file_edit":
            path = getattr(event, "path", "")
            action = getattr(event, "action", "")
            self._writeln(
                f"{tp} {style(_EVENT_ICONS[et] + ' Edit', 'yellow')}{st}  "
                f"{style(action, 'bold')} {style(path, 'dim')}"
            )

        elif et in ("state_update", "decision"):
            icon = _EVENT_ICONS.get(et, "\u2022")
            detail = getattr(event, "kind", "") or getattr(event, "chosen", "")
            self._writeln(
                f"{tp} {style(icon, 'yellow')}{st}  {style(et, 'bold')} {style(detail, 'dim')}"
            )

        else:
            self._writeln(f"{tp} [{et}]{st}")

        self._out.flush()

    def _print_header(self, event: Any) -> None:
        task = getattr(event, "task", "")
        model = getattr(event, "model", "")
        provider = getattr(event, "provider", "")
        run_id = getattr(event, "run_id", "")
        self._writeln(style("\u2501" * 50, "dim"))
        self._writeln(f"  {style('Task:', 'bold')}   {task[:120]}")
        self._writeln(f"  {style('Model:', 'bold')}  {model} ({provider})")
        self._writeln(f"  {style('Run:', 'bold')}    {style(run_id, 'dim')}")
        self._writeln(style("\u2501" * 50, "dim"))
        self._writeln("")

    def _writeln(self, text: str) -> None:
        print(text, file=self._out)


# ---------------------------------------------------------------------------
# NDJSONRenderer — machine-readable newline-delimited JSON
# ---------------------------------------------------------------------------


class NDJSONRenderer:
    """Streaming machine-readable output: one JSON object per event line.

    Drops None/empty fields to keep output compact.  Flushes after every
    event so consumers (jq, log shippers, checkpoint writers) receive
    each line as soon as it is emitted.
    """

    def __init__(self, out: Any = None) -> None:
        self._out = out or sys.stdout

    def on_event(self, event: Any) -> None:
        d = _compact_dict(event)
        print(json.dumps(d, ensure_ascii=False, default=str), file=self._out)
        self._out.flush()

    def on_end(self, exit_code: int) -> None:
        print(
            json.dumps({"type": "exit", "exit_code": exit_code}),
            file=self._out,
        )
        self._out.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compact_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass to a dict, dropping None/empty values."""
    d: dict[str, Any] = {}
    for k, v in asdict(obj).items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        # Keep booleans and numeric types
        if isinstance(v, (bool, int, float)):
            d[k] = v
        else:
            d[k] = v
    return d
