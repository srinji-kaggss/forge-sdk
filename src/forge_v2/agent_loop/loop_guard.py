"""LoopGuard — INV-204: halt on repeated identical tool calls.

Prevents the ~30% stuck rate (Blueprint Proof 3). Hashes tool name + args;
if the same call appears `max_repeats` times, the loop halts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class LoopGuard:
    """Tracks tool call history and triggers on repetition."""

    max_repeats: int = 3
    _call_counts: dict[str, int] = field(default_factory=dict)
    _call_history: list[str] = field(default_factory=list)

    @staticmethod
    def _hash_call(tool_name: str, tool_input: dict) -> str:
        raw = json.dumps({"tool": tool_name, "input": tool_input}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def check(self, tool_name: str, tool_input: dict) -> bool:
        """Check if this call should be blocked. Returns True if BLOCKED."""
        call_hash = self._hash_call(tool_name, tool_input)
        count = self._call_counts.get(call_hash, 0) + 1
        self._call_counts[call_hash] = count
        self._call_history.append(call_hash)
        return count > self.max_repeats

    def reset(self) -> None:
        """Reset guard state (e.g. on new task)."""
        self._call_counts.clear()
        self._call_history.clear()

    @property
    def total_calls(self) -> int:
        return len(self._call_history)

    @property
    def unique_calls(self) -> int:
        return len(self._call_counts)

    def repeated_calls(self) -> list[tuple[str, int]]:
        """Return calls that exceeded the repeat limit (blocked calls)."""
        return [
            (h, c)
            for h, c in self._call_counts.items()
            if c > self.max_repeats
        ]
