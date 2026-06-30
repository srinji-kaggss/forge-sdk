"""Memory System — L8: working/episodic/semantic/procedural tiers.

Working memory: current loop, minutes TTL.
Episodic memory: task history, verifier-gated.
Semantic memory: repo facts, source-grounded.
Procedural memory: skills, repeated-success-gated.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryTier(Enum):
    WORKING = "working"      # current loop, ephemeral
    EPISODIC = "episodic"    # task history, verifier-gated
    SEMANTIC = "semantic"    # repo facts, source-grounded
    PROCEDURAL = "procedural"  # skills, repeated-success-gated


@dataclass(frozen=True)
class MemoryEntry:
    """A single memory record."""

    entry_id: str
    tier: MemoryTier
    content: str
    source: str = ""  # file path, URL, or "agent"
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


class MemorySystem:
    """L8: tiered memory with invalidation triggers."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else Path.home() / ".forge" / "memory.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        # Working memory is ephemeral — reset on startup
        self._working: list[MemoryEntry] = []

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                entry_id TEXT PRIMARY KEY,
                tier TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                confidence REAL DEFAULT 1.0,
                created_at REAL,
                accessed_at REAL,
                access_count INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_tier ON memories(tier)"
        )
        self._conn.commit()

    def write(
        self,
        content: str,
        tier: MemoryTier,
        source: str = "",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Write a memory entry."""
        import uuid
        entry = MemoryEntry(
            entry_id=uuid.uuid4().hex[:12],
            tier=tier,
            content=content,
            source=source,
            confidence=confidence,
            metadata=metadata or {},
        )

        if tier == MemoryTier.WORKING:
            self._working.append(entry)
        else:
            self._conn.execute(
                "INSERT OR REPLACE INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.entry_id,
                    entry.tier.value,
                    entry.content,
                    entry.source,
                    entry.confidence,
                    entry.created_at,
                    entry.accessed_at,
                    entry.access_count,
                    json.dumps(entry.metadata, default=str),
                ),
            )
            self._conn.commit()

        return entry

    def read(
        self,
        tier: MemoryTier | None = None,
        query: str = "",
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Read memory entries with optional filtering."""
        if tier == MemoryTier.WORKING:
            results = self._working[-limit:]
            if query:
                results = [e for e in results if query.lower() in e.content.lower()]
            return results

        conditions = []
        params: list[Any] = []
        if tier:
            conditions.append("tier = ?")
            params.append(tier.value)
        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        rows = self._conn.execute(
            f"SELECT * FROM memories{where} ORDER BY accessed_at DESC LIMIT ?",
            params,
        ).fetchall()

        return [
            MemoryEntry(
                entry_id=r["entry_id"],
                tier=MemoryTier(r["tier"]),
                content=r["content"],
                source=r["source"] or "",
                confidence=r["confidence"],
                created_at=r["created_at"],
                accessed_at=r["accessed_at"],
                access_count=r["access_count"],
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
            )
            for r in rows
        ]

    def invalidate(self, entry_id: str) -> bool:
        """Remove a memory entry."""
        # Check working memory
        for i, e in enumerate(self._working):
            if e.entry_id == entry_id:
                self._working.pop(i)
                return True
        # Check persistent
        self._conn.execute("DELETE FROM memories WHERE entry_id = ?", (entry_id,))
        self._conn.commit()
        return True

    def count(self, tier: MemoryTier | None = None) -> int:
        if tier == MemoryTier.WORKING:
            return len(self._working)
        if tier:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE tier = ?", (tier.value,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0]

    def close(self) -> None:
        self._conn.close()
