"""Self-learning store — episodic and semantic memory for agent evolution."""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator


@dataclass
class Episode:
    """A recorded task execution with outcome.

    Episodes are the raw material for learning. Each one captures:
    - What the agent was asked to do
    - What it actually did (steps, tools used)
    - Whether it succeeded and why
    - What it should learn from this
    """

    id: str
    task: str
    outcome: str  # success | failure | partial
    steps: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    tokens_used: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    lesson: str | None = None  # What to learn from this
    domain: str = "general"
    timestamp: float = field(default_factory=time.time)
    generation: int = 0

    @property
    def success(self) -> bool:
        return self.outcome == "success"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Episode:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Knowledge:
    """Generalized knowledge derived from multiple episodes.

    Knowledge is the distilled wisdom from episodes. It captures
    patterns, rules, and heuristics that apply across tasks.
    """

    id: str
    rule: str  # The learned rule or heuristic
    confidence: float = 0.5  # 0.0-1.0, updated with evidence
    evidence_count: int = 0
    domain: str = "general"
    source_episodes: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def strengthen(self, episode_id: str, positive: bool) -> None:
        """Update confidence based on new evidence."""
        self.evidence_count += 1
        self.source_episodes.append(episode_id)
        self.last_updated = time.time()

        # Bayesian-ish update
        if positive:
            self.confidence = min(0.99, self.confidence + 0.1 * (1 - self.confidence))
        else:
            self.confidence = max(0.01, self.confidence - 0.1 * self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Knowledge:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


class LearningStore:
    """Persistent store for episodic and semantic memory.

    File-system backed (JSONL for append-only logs, JSON for state).
    Designed for the evolution loop — fast append, fast query, fast save.

    Directory structure:
        memory/
        ├── episodes.jsonl      # Append-only episode log
        ├── knowledge.json      # Current knowledge base
        ├── stats.json          # Aggregate statistics
        └── index.json          # Fast lookup index
    """

    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)
        self._episodes_file = self._base / "episodes.jsonl"
        self._knowledge_file = self._base / "knowledge.json"
        self._stats_file = self._base / "stats.json"

        # In-memory caches
        self._episodes: list[Episode] = []
        self._knowledge: list[Knowledge] = []
        self._stats: dict[str, Any] = {"total_episodes": 0, "total_knowledge": 0}

        self._load()

    def _load(self) -> None:
        """Load existing data from disk."""
        if self._episodes_file.exists():
            for line in self._episodes_file.read_text().splitlines():
                if line.strip():
                    self._episodes.append(Episode.from_dict(json.loads(line)))

        if self._knowledge_file.exists():
            data = json.loads(self._knowledge_file.read_text())
            self._knowledge = [Knowledge.from_dict(k) for k in data]

        if self._stats_file.exists():
            self._stats = json.loads(self._stats_file.read_text())

    # --- Episodes ---

    def record_episode(self, episode: Episode) -> None:
        """Append an episode to the log."""
        self._episodes.append(episode)
        with open(self._episodes_file, "a") as f:
            f.write(json.dumps(episode.to_dict()) + "\n")
        self._stats["total_episodes"] = len(self._episodes)
        self._save_stats()

    def get_episodes(
        self,
        domain: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
    ) -> list[Episode]:
        """Query episodes with optional filters."""
        results = self._episodes
        if domain:
            results = [e for e in results if e.domain == domain]
        if outcome:
            results = [e for e in results if e.outcome == outcome]
        return results[-limit:]

    def get_recent_failures(self, n: int = 10) -> list[Episode]:
        """Get the N most recent failure episodes."""
        failures = [e for e in self._episodes if not e.success]
        return failures[-n:]

    def get_recent_successes(self, n: int = 10) -> list[Episode]:
        """Get the N most recent success episodes."""
        successes = [e for e in self._episodes if e.success]
        return successes[-n:]

    # --- Knowledge ---

    def add_knowledge(self, knowledge: Knowledge) -> None:
        """Add a new knowledge entry."""
        self._knowledge.append(knowledge)
        self._save_knowledge()
        self._stats["total_knowledge"] = len(self._knowledge)
        self._save_stats()

    def update_knowledge(self, knowledge_id: str, episode_id: str, positive: bool) -> bool:
        """Update existing knowledge with new evidence."""
        for k in self._knowledge:
            if k.id == knowledge_id:
                k.strengthen(episode_id, positive)
                self._save_knowledge()
                return True
        return False

    def get_knowledge(
        self,
        domain: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[Knowledge]:
        """Query knowledge with optional filters."""
        results = self._knowledge
        if domain:
            results = [k for k in results if k.domain == domain]
        results = [k for k in results if k.confidence >= min_confidence]
        return sorted(results, key=lambda k: k.confidence, reverse=True)[:limit]

    def get_confident_rules(self, min_confidence: float = 0.7) -> list[Knowledge]:
        """Get high-confidence knowledge rules."""
        return self.get_knowledge(min_confidence=min_confidence)

    # --- Stats ---

    @property
    def stats(self) -> dict[str, Any]:
        """Aggregate statistics."""
        total = len(self._episodes)
        successes = sum(1 for e in self._episodes if e.success)
        return {
            "total_episodes": total,
            "success_rate": successes / total if total > 0 else 0.0,
            "total_knowledge": len(self._knowledge),
            "avg_tokens": (
                sum(e.tokens_used for e in self._episodes) / total if total > 0 else 0
            ),
            "domains": list(set(e.domain for e in self._episodes)),
        }

    # --- Persistence ---

    def _save_knowledge(self) -> None:
        self._knowledge_file.write_text(
            json.dumps([k.to_dict() for k in self._knowledge], indent=2)
        )

    def _save_stats(self) -> None:
        self._stats_file.write_text(json.dumps(self._stats, indent=2))

    def save_all(self) -> None:
        """Force save all state."""
        self._save_knowledge()
        self._save_stats()

    def clear(self) -> None:
        """Clear all memory (dangerous)."""
        self._episodes.clear()
        self._knowledge.clear()
        self._stats = {"total_episodes": 0, "total_knowledge": 0}
        self._episodes_file.write_text("")
        self._save_knowledge()
        self._save_stats()
