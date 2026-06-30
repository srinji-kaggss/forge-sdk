"""Evolution engine — A-Evolve style mutation for agent profiles and prompts."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from forge_sdk.harness.profiles import AgentProfile
from forge_sdk.harness.adaptive import AdaptivePrompt, PromptFragment
from forge_sdk.harness.learning import LearningStore, Episode, Knowledge


@dataclass
class StepResult:
    """Result of a single evolution step."""

    mutated: bool
    summary: str
    mutations: list[dict[str, Any]] = field(default_factory=list)
    score_delta: float = 0.0
    fragments_added: int = 0
    fragments_removed: int = 0
    knowledge_added: int = 0


class EvolutionEngine:
    """A-Evolve style evolution engine for agent harness.

    Implements the Solve → Observe → Evolve → Gate → Reload cycle:

    1. **Observe**: Analyze episodes and extract failure patterns
    2. **Evolve**: Mutate prompts, add/remove fragments, update knowledge
    3. **Gate**: Validate mutations don't break existing capabilities
    4. **Reload**: Apply evolved state to the harness

    The engine is intentionally simple — it works by:
    - Scanning recent episodes for failure patterns
    - Generating new prompt fragments to address failures
    - Removing low-performing fragments
    - Strengthening/weakening knowledge based on outcomes
    """

    def __init__(
        self,
        learning_store: LearningStore,
        mutate_fn: Callable[[str, list[Episode]], str] | None = None,
    ) -> None:
        self._store = learning_store
        self._mutate_fn = mutate_fn  # Optional LLM-driven mutation function
        self._history: list[StepResult] = []

    def step(
        self,
        profile: AgentProfile,
        prompt: AdaptivePrompt,
        recent_episodes: list[Episode] | None = None,
    ) -> StepResult:
        """Run one evolution step.

        Analyzes recent episodes, identifies patterns, and mutates
        the prompt/profile to address failures.
        """
        if recent_episodes is None:
            recent_episodes = self._store.get_episodes(limit=20)

        if not recent_episodes:
            return StepResult(mutated=False, summary="No episodes to analyze")

        mutations: list[dict[str, Any]] = []
        fragments_added = 0
        fragments_removed = 0
        knowledge_added = 0

        # --- Phase 1: Analyze failures ---
        failures = [e for e in recent_episodes if not e.success]
        successes = [e for e in recent_episodes if e.success]

        # --- Phase 2: Generate new fragments from failure patterns ---
        if failures:
            # Extract common failure patterns
            failure_patterns = self._extract_patterns(failures)

            for pattern in failure_patterns:
                # Check if we already have a fragment for this pattern
                existing = [f for f in prompt.fragments
                           if pattern["topic"] in f.content.lower()
                           and f.source == "evolved"]

                if not existing:
                    # Dedup: check if any evolved fragment already addresses this topic
                    topic_root = pattern["topic"].split("_")[0]  # "import_errors" -> "import"
                    similar = [f for f in prompt.fragments
                               if f.source == "evolved"
                               and topic_root in f.content.lower()]

                    if not similar:
                        # Add new fragment to address the failure
                        fragment = prompt.add_fragment(
                            content=pattern["suggestion"],
                            priority=60,
                            source="evolved",
                        )
                        mutations.append({
                            "type": "add_fragment",
                            "fragment_id": fragment.id,
                            "topic": pattern["topic"],
                        })
                        fragments_added += 1

                        # Record as knowledge — F6 fix: UUID not count-based
                        from forge_sdk.security import generate_uuid_id
                        knowledge = Knowledge(
                            id=generate_uuid_id("know"),
                            rule=pattern["suggestion"],
                            confidence=0.5,
                            domain=profile.domain,
                            source_episodes=[e.id for e in failures[:5]],
                        )
                        self._store.add_knowledge(knowledge)
                        knowledge_added += 1

        # --- Phase 3: Remove low-performing fragments ---
        low_performing = prompt.get_low_performing(threshold=0.25)
        for frag in low_performing:
            if frag.id != "base":  # Never remove the base prompt
                prompt.remove_fragment(frag.id)
                mutations.append({
                    "type": "remove_fragment",
                    "fragment_id": frag.id,
                    "score": frag.score,
                })
                fragments_removed += 1

        # --- Phase 4: Strengthen/weaken knowledge from outcomes ---
        for episode in recent_episodes:
            # Find related knowledge and update
            for knowledge in self._store.get_knowledge(domain=episode.domain):
                if any(keyword in episode.task.lower()
                       for keyword in knowledge.rule.lower().split()[:3]):
                    self._store.update_knowledge(
                        knowledge.id, episode.id, episode.success
                    )

        # --- Phase 5: Calculate score delta ---
        if successes and failures:
            new_score = len(successes) / (len(successes) + len(failures))
        elif successes:
            new_score = 1.0
        else:
            new_score = 0.0

        score_delta = new_score - profile.performance_score

        # --- Phase 6: Evolve profile if significant mutations ---
        if mutations:
            profile = profile.evolve({
                "performance_score": new_score,
                "metadata": {
                    **profile.metadata,
                    "last_evolution": time.time(),
                    "fragments_added": fragments_added,
                    "fragments_removed": fragments_removed,
                },
            })

        result = StepResult(
            mutated=bool(mutations),
            summary=self._build_summary(mutations, failures, successes, new_score),
            mutations=mutations,
            score_delta=score_delta,
            fragments_added=fragments_added,
            fragments_removed=fragments_removed,
            knowledge_added=knowledge_added,
        )

        self._history.append(result)
        return result

    def _extract_patterns(self, failures: list[Episode]) -> list[dict[str, Any]]:
        """Extract common patterns from failure episodes."""
        patterns: list[dict[str, Any]] = []
        error_types: dict[str, list[Episode]] = {}

        for episode in failures:
            if episode.error:
                # F1 fix: sanitize untrusted error text before processing
                from forge_sdk.security import sanitize_untrusted_text
                safe_error = sanitize_untrusted_text(episode.error, max_length=300)
                # Simple categorization by error keyword
                category = self._categorize_error(safe_error)
                error_types.setdefault(category, []).append(episode)
            elif episode.lesson:
                category = "lesson"
                error_types.setdefault(category, []).append(episode)

        for category, episodes in error_types.items():
            if len(episodes) >= 2:  # Need at least 2 occurrences
                suggestion = self._generate_suggestion(category, episodes)
                patterns.append({
                    "topic": category,
                    "count": len(episodes),
                    "suggestion": suggestion,
                })

        return patterns

    def _categorize_error(self, error: str) -> str:
        """Simple error categorization."""
        error_lower = error.lower()
        if "timeout" in error_lower:
            return "timeout_handling"
        elif "permission" in error_lower or "access" in error_lower:
            return "permission_errors"
        elif "not found" in error_lower or "no such file" in error_lower:
            return "file_not_found"
        elif "syntax" in error_lower or "parse" in error_lower:
            return "syntax_errors"
        elif "import" in error_lower or "module" in error_lower:
            return "import_errors"
        elif "connection" in error_lower or "network" in error_lower:
            return "network_errors"
        else:
            return "general_errors"

    def _generate_suggestion(self, category: str, episodes: list[Episode]) -> str:
        """Generate a prompt suggestion for a failure pattern."""
        suggestions = {
            "timeout_handling": (
                "When a task involves long-running operations, always set appropriate "
                "timeouts and implement fallback behavior. Use async patterns or "
                "background processing for operations that may exceed time limits."
            ),
            "permission_errors": (
                "Before modifying files or running commands, verify permissions. "
                "Use read-only operations first to check access. If permission is "
                "denied, suggest alternative approaches that don't require elevated "
                "privileges."
            ),
            "file_not_found": (
                "When a file is not found, verify the path exists before attempting "
                "operations. Use glob patterns to find similar files. Check for "
                "case sensitivity and symlink issues."
            ),
            "syntax_errors": (
                "When writing code, verify syntax before execution. Use language-"
                "specific linters or parsers to catch errors early. For Python, "
                "use ast.parse() or py_compile before running."
            ),
            "import_errors": (
                "Before importing modules, verify they are available. Check "
                "requirements.txt or pyproject.toml for dependencies. Use try/except "
                "ImportError with helpful fallback messages."
            ),
            "network_errors": (
                "When making network requests, implement retry logic with exponential "
                "backoff. Set reasonable timeouts. Handle DNS failures and connection "
                "refused errors gracefully."
            ),
            "general_errors": (
                "Analyze error messages carefully before retrying. Check the error "
                "type and context to determine if it's transient or permanent. "
                "Implement appropriate error handling for each case."
            ),
        }

        base_suggestion = suggestions.get(category, suggestions["general_errors"])

        # Add specific context from episodes
        if episodes:
            error_messages = [e.error for e in episodes if e.error]
            if error_messages:
                base_suggestion += (
                    f"\n\nSpecific errors to avoid: {error_messages[0]}"
                )

        return base_suggestion

    def _build_summary(
        self,
        mutations: list[dict[str, Any]],
        failures: list[Episode],
        successes: list[Episode],
        new_score: float,
    ) -> str:
        """Build human-readable evolution summary."""
        if not mutations:
            return "No mutations applied"

        parts = [f"Applied {len(mutations)} mutation(s)"]
        parts.append(f"Score: {new_score:.2f}")

        added = sum(1 for m in mutations if m["type"] == "add_fragment")
        removed = sum(1 for m in mutations if m["type"] == "remove_fragment")

        if added:
            parts.append(f"+{added} fragments")
        if removed:
            parts.append(f"-{removed} fragments")

        return ", ".join(parts)

    @property
    def history(self) -> list[StepResult]:
        return list(self._history)

    def save_history(self, path: str | Path) -> None:
        """Save evolution history to JSON."""
        data = [
            {
                "mutated": r.mutated,
                "summary": r.summary,
                "score_delta": r.score_delta,
                "fragments_added": r.fragments_added,
                "fragments_removed": r.fragments_removed,
                "knowledge_added": r.knowledge_added,
            }
            for r in self._history
        ]
        Path(path).write_text(json.dumps(data, indent=2))
