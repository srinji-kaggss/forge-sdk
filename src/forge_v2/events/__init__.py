"""Event Bus — append-only event stream for all observations/actions/results.

L1 from OKF spec: "append-only event stream for all observations/actions/results"
Schema: Event{id, ts, actor, capability, input_hash, output_hash, risk, cost, parent_ids}
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(Enum):
    OBSERVATION = "observation"
    ACTION = "action"
    RESULT = "result"
    DECISION = "decision"
    MEMORY_WRITE = "memory_write"
    MEMORY_READ = "memory_read"
    TOOL_LEASE = "tool_lease"
    TOOL_DENIAL = "tool_denial"
    VERIFICATION = "verification"
    ERROR = "error"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Event:
    """Immutable event record — the atomic unit of the harness."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: float = field(default_factory=time.time)
    event_type: EventType = EventType.OBSERVATION
    actor: str = ""  # agent, subagent, user, system
    capability: str = ""  # tool name, memory operation, etc.
    input_hash: str = ""  # SHA-256 of input payload
    output_hash: str = ""  # SHA-256 of output payload
    risk: RiskLevel = RiskLevel.LOW
    cost_tokens: int = 0
    cost_usd: float = 0.0
    parent_ids: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "actor": self.actor,
            "capability": self.capability,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "risk": self.risk.value,
            "cost_tokens": self.cost_tokens,
            "cost_usd": self.cost_usd,
            "parent_ids": list(self.parent_ids),
            "payload": self.payload,
            "metadata": self.metadata,
        }


def hash_payload(payload: Any) -> str:
    """SHA-256 hash of any JSON-serializable payload."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class EventBus:
    """Append-only event store backed by SQLite."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else Path.home() / ".forge" / "events.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT,
                capability TEXT,
                input_hash TEXT,
                output_hash TEXT,
                risk TEXT,
                cost_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                parent_ids TEXT,
                payload TEXT,
                metadata TEXT
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)"
        )
        self._conn.commit()

    def emit(self, event: Event) -> Event:
        """Append an event to the store."""
        self._conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.timestamp,
                event.event_type.value,
                event.actor,
                event.capability,
                event.input_hash,
                event.output_hash,
                event.risk.value,
                event.cost_tokens,
                event.cost_usd,
                json.dumps(event.parent_ids),
                json.dumps(event.payload, default=str),
                json.dumps(event.metadata, default=str),
            ),
        )
        self._conn.commit()
        return event

    def query(
        self,
        event_type: EventType | None = None,
        actor: str | None = None,
        capability: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query events with filters."""
        conditions = []
        params: list[Any] = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type.value)
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if capability:
            conditions.append("capability = ?")
            params.append(capability)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        query = "SELECT * FROM events"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [
            Event(
                event_id=r["event_id"],
                timestamp=r["timestamp"],
                event_type=EventType(r["event_type"]),
                actor=r["actor"] or "",
                capability=r["capability"] or "",
                input_hash=r["input_hash"] or "",
                output_hash=r["output_hash"] or "",
                risk=RiskLevel(r["risk"]),
                cost_tokens=r["cost_tokens"],
                cost_usd=r["cost_usd"],
                parent_ids=tuple(json.loads(r["parent_ids"])) if r["parent_ids"] else (),
                payload=json.loads(r["payload"]) if r["payload"] else {},
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
            )
            for r in rows
        ]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def total_cost(self) -> tuple[int, float]:
        row = self._conn.execute(
            "SELECT SUM(cost_tokens), SUM(cost_usd) FROM events"
        ).fetchone()
        return (row[0] or 0, row[1] or 0.0)

    def close(self) -> None:
        self._conn.close()
