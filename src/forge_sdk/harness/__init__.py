"""v5 Harness: Self-improving agent framework.

Agent profiles, adaptive system prompts, self-learning loops,
and evolution engine inspired by A-Evolve patterns.

Usage:
    from forge_sdk.harness import AgentProfile, AdaptivePrompt, LearningStore, HarnessRunner

    profile = AgentProfile(
        name="coder",
        domain="python",
        system_prompt="You are a Python expert.",
    )
    prompt = AdaptivePrompt(profile)
    store = LearningStore("./agent-memory")
    runner = HarnessRunner(profile, prompt, store)
    result = runner.run("Fix the bug in main.py")
"""

from forge_sdk.harness.profiles import AgentProfile
from forge_sdk.harness.adaptive import AdaptivePrompt
from forge_sdk.harness.learning import LearningStore, Episode, Knowledge
from forge_sdk.harness.engine import EvolutionEngine, StepResult
from forge_sdk.harness.runner import HarnessRunner

__all__ = [
    "AgentProfile",
    "AdaptivePrompt",
    "LearningStore",
    "Episode",
    "Knowledge",
    "EvolutionEngine",
    "StepResult",
    "HarnessRunner",
]
