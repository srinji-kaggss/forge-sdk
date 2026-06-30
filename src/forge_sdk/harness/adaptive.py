"""Adaptive system prompts — self-evolving prompts that learn from performance."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge_sdk.harness.profiles import AgentProfile


@dataclass
class PromptFragment:
    """A modular piece of the system prompt.

    Fragments are independently evolvable units that compose
    into the full system prompt. The engine can add, remove,
    modify, or reorder fragments based on performance.
    """

    id: str
    content: str
    priority: int = 0  # Higher = more important
    source: str = "manual"  # manual | evolved | memory
    generation: int = 0
    success_count: int = 0
    failure_count: int = 0

    @property
    def score(self) -> float:
        """Success rate for this fragment."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Neutral prior
        return self.success_count / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "priority": self.priority,
            "source": self.source,
            "generation": self.generation,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptFragment:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AdaptivePrompt:
    """Self-evolving system prompt that learns from task performance.

    The prompt is composed of fragments:
    1. Base prompt (from profile, never mutated)
    2. Domain fragments (loaded from profile domain)
    3. Learned fragments (accumulated from successful tasks)
    4. Context fragments (dynamically injected per task)

    The evolution engine can:
    - Add new fragments from successful patterns
    - Remove fragments that correlate with failures
    - Modify fragment content via LLM-driven mutation
    - Reorder fragments by priority/score
    """

    def __init__(self, profile: AgentProfile) -> None:
        self._profile = profile
        self._fragments: list[PromptFragment] = []
        self._context_overrides: dict[str, str] = {}
        self._load_profile_fragments()

    def _load_profile_fragments(self) -> None:
        """Initialize fragments from the profile's system prompt."""
        self._fragments = [
            PromptFragment(
                id="base",
                content=self._profile.system_prompt,
                priority=100,
                source="manual",
            )
        ]

    def compose(self, task: str | None = None) -> str:
        """Compose the full system prompt from fragments.

        Sorts by priority (descending), then by score (descending).
        Injects task-specific context if provided.
        """
        sorted_fragments = sorted(
            self._fragments,
            key=lambda f: (f.priority, f.score),
            reverse=True,
        )

        parts = []
        for frag in sorted_fragments:
            if frag.score < 0.2 and frag.source == "evolved":
                # Skip low-performing evolved fragments
                continue
            parts.append(frag.content)

        # Add context overrides
        if task:
            context = self._build_context(task)
            if context:
                parts.append(context)

        return "\n\n".join(parts)

    def _build_context(self, task: str) -> str:
        """Build task-specific context section."""
        lines = ["## Current Task Context"]
        lines.append(f"Task: {task}")

        if self._context_overrides:
            for key, value in self._context_overrides.items():
                lines.append(f"{key}: {value}")

        return "\n".join(lines)

    def add_fragment(
        self,
        content: str,
        fragment_id: str | None = None,
        priority: int = 50,
        source: str = "evolved",
    ) -> PromptFragment:
        """Add a new prompt fragment."""
        if fragment_id is None:
            fragment_id = f"frag-{len(self._fragments)}"

        frag = PromptFragment(
            id=fragment_id,
            content=content,
            priority=priority,
            source=source,
            generation=self._profile.generation,
        )
        self._fragments.append(frag)
        return frag

    def remove_fragment(self, fragment_id: str) -> bool:
        """Remove a fragment by ID. Returns True if found."""
        before = len(self._fragments)
        self._fragments = [f for f in self._fragments if f.id != fragment_id]
        return len(self._fragments) < before

    def update_fragment(self, fragment_id: str, **kwargs: Any) -> bool:
        """Update a fragment's fields. Returns True if found."""
        for frag in self._fragments:
            if frag.id == fragment_id:
                for key, value in kwargs.items():
                    if hasattr(frag, key):
                        setattr(frag, key, value)
                return True
        return False

    def record_outcome(self, fragment_id: str, success: bool) -> None:
        """Record a task outcome for a specific fragment."""
        for frag in self._fragments:
            if frag.id == fragment_id:
                if success:
                    frag.success_count += 1
                else:
                    frag.failure_count += 1
                return

    def set_context(self, key: str, value: str) -> None:
        """Set a context override for the next compose() call."""
        self._context_overrides[key] = value

    def clear_context(self) -> None:
        """Clear all context overrides."""
        self._context_overrides.clear()

    @property
    def fragment_count(self) -> int:
        return len(self._fragments)

    @property
    def fragments(self) -> list[PromptFragment]:
        return list(self._fragments)

    def get_low_performing(self, threshold: float = 0.3) -> list[PromptFragment]:
        """Get fragments with score below threshold."""
        return [f for f in self._fragments if f.score < threshold and f.source == "evolved"]

    def get_top_fragments(self, n: int = 5) -> list[PromptFragment]:
        """Get top N fragments by score."""
        return sorted(self._fragments, key=lambda f: f.score, reverse=True)[:n]

    def to_dict(self) -> dict[str, Any]:
        """Serialize full state."""
        return {
            "profile_name": self._profile.name,
            "fragments": [f.to_dict() for f in self._fragments],
            "context_overrides": self._context_overrides,
        }

    def save(self, path: str | Path) -> None:
        """Save prompt state to JSON."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    def load(self, path: str | Path) -> None:
        """Load prompt state from JSON."""
        data = json.loads(Path(path).read_text())
        self._fragments = [PromptFragment.from_dict(f) for f in data.get("fragments", [])]
        self._context_overrides = data.get("context_overrides", {})

    def reset(self) -> None:
        """Reset to profile defaults."""
        self._context_overrides.clear()
        self._load_profile_fragments()
