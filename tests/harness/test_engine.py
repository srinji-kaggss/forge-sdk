"""Regression tests for the evolution engine (harness).

Run with: pytest tests/harness/test_engine.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from forge_sdk.harness.adaptive import AdaptivePrompt, PromptFragment
from forge_sdk.harness.engine import EvolutionEngine
from forge_sdk.harness.learning import Episode, LearningStore
from forge_sdk.harness.profiles import AgentProfile


def _make_episode(episode_id: str, error: str, domain: str = "python") -> Episode:
    return Episode(
        id=episode_id,
        task=f"task for {episode_id}",
        outcome="failure",
        steps=[],
        tokens_used=0,
        duration_ms=0.0,
        error=error,
        domain=domain,
    )


def test_step_dedup_skips_similar_fragment(tmp_path):
    """Regression: engine.step() must not raise UnboundLocalError when the
    dedup branch (`similar` non-empty) fires. Dedup should skip adding a new
    fragment and knowledge, returning fragments_added == 0 and
    knowledge_added == 0 for the deduped pattern.
    """
    store = LearningStore(tmp_path / "memory")
    engine = EvolutionEngine(store)
    profile = AgentProfile(name="coder", domain="python")
    prompt = AdaptivePrompt(profile)

    # Pre-seed an "evolved" fragment whose content contains the topic_root
    # of the import_errors category ("import"), so the `similar` branch is
    # non-empty and dedup fires.
    prompt.add_fragment(
        content=(
            "Always check imports before using a module. "
            "Verify availability in requirements.txt."
        ),
        priority=60,
        source="evolved",
    )

    # Two failure episodes mapping to the SAME category (import_errors),
    # so _extract_patterns returns at least one pattern.
    episodes = [
        _make_episode("ep-1", "ImportError: no module named foo"),
        _make_episode("ep-2", "ImportError: no module named bar"),
    ]

    # Must not raise UnboundLocalError.
    result = engine.step(profile, prompt, episodes)

    assert result.fragments_added == 0, (
        f"expected dedup to skip fragment, got fragments_added={result.fragments_added}"
    )
    assert result.knowledge_added == 0, (
        f"expected dedup to skip knowledge, got knowledge_added={result.knowledge_added}"
    )


def test_step_adds_fragment_when_no_dedup(tmp_path):
    """Sanity check: the non-dedup path still works identically to before —
    when no similar evolved fragment exists, a new fragment AND knowledge are
    added. This guards against the fix accidentally disabling the happy path.
    """
    store = LearningStore(tmp_path / "memory")
    engine = EvolutionEngine(store)
    profile = AgentProfile(name="coder", domain="python")
    prompt = AdaptivePrompt(profile)

    # No pre-seeded evolved fragment → dedup does NOT fire.
    episodes = [
        _make_episode("ep-3", "ImportError: no module named baz"),
        _make_episode("ep-4", "ImportError: no module named qux"),
    ]

    result = engine.step(profile, prompt, episodes)

    assert result.fragments_added == 1, (
        f"expected one fragment added on happy path, got {result.fragments_added}"
    )
    assert result.knowledge_added == 1, (
        f"expected one knowledge added on happy path, got {result.knowledge_added}"
    )