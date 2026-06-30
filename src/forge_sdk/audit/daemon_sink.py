"""DaemonEventSink — subprocess-isolated bridge to lgwks daemon event bus.

Edge-portable: communicates via JSON-serialized subprocess calls.
Does NOT import lgwks modules directly — invokes via subprocess.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
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
        if not re.match(r'^[a-zA-Z0-9_-]+$', queue_name):
            raise ValueError(f"Invalid queue_name: {queue_name!r}. Must match [a-zA-Z0-9_-]+")
        self._script = daemon_script
        self._queue = queue_name
        self._buffer: list[dict[str, Any]] = []

    def submit(self, event: dict[str, Any]) -> None:
        """Buffer an event; auto-flush at batch threshold."""
        self._buffer.append(event)
        self._write_wal()
        if len(self._buffer) >= _BATCH_SIZE:
            self.flush()

    def _write_wal(self) -> None:
        """Write buffered events to disk before flush for crash recovery."""
        wal_path = os.path.join(tempfile.gettempdir(), f"forge_eventsink_{self._queue}.wal")
        with open(wal_path, "w") as f:
            json.dump(self._buffer, f)

    def _clear_wal(self) -> None:
        wal_path = os.path.join(tempfile.gettempdir(), f"forge_eventsink_{self._queue}.wal")
        if os.path.exists(wal_path):
            os.remove(wal_path)

    def flush(self) -> None:
        """Submit buffered events via subprocess (JSON on stdin)."""
        if not self._buffer:
            return
        payload = json.dumps(self._buffer, default=str)
        try:
            result = subprocess.run(
                ["python", "-m", self._script, "enqueue", self._queue],
                input=payload.encode(),
                timeout=_TIMEOUT_S,
                capture_output=True,
            )
            if result.returncode == 0:
                self._buffer.clear()
                self._clear_wal()
            else:
                logger.warning("DaemonEventSink flush failed (rc=%d): %s", result.returncode, result.stderr[:200])
                # Keep buffer for retry — don't lose events
        except Exception as e:
            logger.warning("DaemonEventSink flush exception: %s", e)
            # Don't clear buffer — events preserved for retry
