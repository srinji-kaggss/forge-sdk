"""Audit log — independent observer with hash-chain integrity.

Also exports EventSink (protocol) and DaemonEventSink (subprocess-isolated bridge).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit entry with hash-chain integrity."""

    entry_id: str
    timestamp: float
    trace_id: str
    entry_type: str  # "llm_call", "tool_use", "decision", "eval_result"
    payload: dict[str, Any]
    previous_hash: str
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "entry_type": self.entry_type,
            "payload": self.payload,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


def _compute_hash(previous_hash: str, payload: dict) -> str:
    """SHA-256 hash of previous_hash + serialized payload."""
    raw = previous_hash + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class AuditLog:
    """Append-only audit log with hash-chain integrity."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else Path.home() / ".forge" / "audit.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_entries (
                entry_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                trace_id TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_entries(trace_id)
        """)
        self._conn.commit()

    def _last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT entry_hash FROM audit_entries ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return row["entry_hash"] if row else "0" * 64

    def append(
        self,
        trace_id: str,
        entry_type: str,
        payload: dict[str, Any],
    ) -> AuditEntry:
        """Append a new entry to the audit log."""
        previous_hash = self._last_hash()
        entry_hash = _compute_hash(previous_hash, payload)
        entry = AuditEntry(
            entry_id=uuid.uuid4().hex[:16],
            timestamp=time.time(),
            trace_id=trace_id,
            entry_type=entry_type,
            payload=payload,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        self._conn.execute(
            "INSERT INTO audit_entries VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry.entry_id,
                entry.timestamp,
                entry.trace_id,
                entry.entry_type,
                json.dumps(entry.payload, default=str),
                entry.previous_hash,
                entry.entry_hash,
            ),
        )
        self._conn.commit()
        return entry

    def verify_integrity(self) -> list[str]:
        """Verify hash-chain integrity. Returns list of violations."""
        rows = self._conn.execute("SELECT * FROM audit_entries ORDER BY timestamp ASC").fetchall()
        violations = []
        prev_hash = "0" * 64
        for i, row in enumerate(rows):
            if row["previous_hash"] != prev_hash:
                violations.append(f"Entry {row['entry_id']} (index {i}): previous_hash mismatch")
            payload = json.loads(row["payload"])
            expected_hash = _compute_hash(prev_hash, payload)
            if row["entry_hash"] != expected_hash:
                violations.append(
                    f"Entry {row['entry_id']} (index {i}): hash mismatch (possible tampering)"
                )
            prev_hash = row["entry_hash"]
        return violations

    def get_entries(
        self,
        trace_id: str | None = None,
        entry_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        query = "SELECT * FROM audit_entries"
        params: list[Any] = []
        conditions = []
        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)
        if entry_type:
            conditions.append("entry_type = ?")
            params.append(entry_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [
            AuditEntry(
                entry_id=row["entry_id"],
                timestamp=row["timestamp"],
                trace_id=row["trace_id"],
                entry_type=row["entry_type"],
                payload=json.loads(row["payload"]),
                previous_hash=row["previous_hash"],
                entry_hash=row["entry_hash"],
            )
            for row in rows
        ]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM audit_entries").fetchone()[0]

    def close(self) -> None:
        self._conn.close()


# Re-export protocol and daemon bridge
from forge_sdk.audit.daemon_sink import DaemonEventSink  # noqa: E402
from forge_sdk.audit.eventsink import EventSink  # noqa: E402
