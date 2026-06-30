"""DaemonEventSink — subprocess-isolated bridge to lgwks daemon event bus.

Edge-portable: communicates via JSON-serialized subprocess calls.
Does NOT import lgwks modules directly — invokes via subprocess.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

_BATCH_SIZE = 10
_TIMEOUT_S = 10


class DaemonEventSink:
    """Subprocess-isolated EventSink that bridges to lgwks daemon event bus.

    Satisfies the EventSink protocol without importing lgwks modules.
    All payloads are plain JSON — no Python objects or dataclasses on the wire.
    """

    def __init__(
        self,
        daemon_script: str = "lgwks_daemon_event",
        queue_name: str = "forge",
    ) -> None:
        self._script = daemon_script
        self._queue = queue_name
        self._buffer: list[dict[str, Any]] = []

    def submit(self, event: dict[str, Any]) -> None:
        """Buffer an event; auto-flush at batch threshold."""
        self._buffer.append(event)
        if len(self._buffer) >= _BATCH_SIZE:
            self.flush()

    def flush(self) -> None:
        """Submit buffered events via subprocess (JSON on stdin)."""
        if not self._buffer:
            return
        payload = json.dumps(self._buffer, default=str)
        try:
            subprocess.run(
                ["python", "-m", self._script, "enqueue", self._queue],
                input=payload.encode(),
                timeout=_TIMEOUT_S,
                check=False,
            )
        except Exception:
            logger.warning("DaemonEventSink flush failed; events lost", exc_info=True)
        finally:
            self._buffer.clear()
