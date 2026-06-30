"""EventSink protocol — edge-portable, JSON-serializable event submission."""

from __future__ import annotations

from typing import Any, Protocol


class EventSink(Protocol):
    """Protocol for event submission. Edge-portable: JSON-serializable payloads."""

    def submit(self, event: dict[str, Any]) -> None:
        """Submit a structured event. Must be JSON-serializable."""
        ...

    def flush(self) -> None:
        """Flush any buffered events."""
        ...
