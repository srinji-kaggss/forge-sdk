"""v5 Harness example: adaptive agent that learns from failures.

Demonstrates the full lifecycle:
1. Create an agent profile
2. Run tasks (simulated failures)
3. Watch the harness learn and adapt
4. See improved performance

Usage:
    source .venv/bin/activate
    python examples/harness_v5.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forge_sdk.harness import (
    AgentProfile,
    AdaptivePrompt,
    LearningStore,
    EvolutionEngine,
    HarnessRunner,
)
from forge_sdk.harness.learning import Episode


def main():
    print("=" * 60)
    print("  forge-sdk v5 Harness: Self-Improving Agent Demo")
    print("=" * 60)

    # 1. Create profile
    profile = AgentProfile(
        name="demo-coder",
        domain="python",
        role="developer",
        system_prompt="You are a Python developer. Write clean, tested code.",
        max_steps=10,
    )
    print(f"\n[1] Profile: {profile.name} (gen {profile.generation})")

    # 2. Initialize harness
    runner = HarnessRunner(profile, base_path=".harness-demo")
    print(f"[2] Harness initialized (fragments: {runner.prompt.fragment_count})")

    # 3. Simulate some task runs with failures
    print("\n[3] Simulating task runs...")

    # Simulate episodes manually (no real agent)
    # Need 2+ failures of same type to trigger pattern detection
    failure_episodes = [
        Episode(
            id="ep-001",
            task="Fix the import error in main.py",
            outcome="failure",
            error="ModuleNotFoundError: No module named 'requests'",
            domain="python",
        ),
        Episode(
            id="ep-002",
            task="Fix the import error in api.py",
            outcome="failure",
            error="ModuleNotFoundError: No module named 'pandas'",
            domain="python",
        ),
        Episode(
            id="ep-003",
            task="Fix the timeout in api_call.py",
            outcome="failure",
            error="ConnectionTimeout: Request timed out after 30s",
            domain="python",
        ),
        Episode(
            id="ep-004",
            task="Fix the timeout in async_handler.py",
            outcome="failure",
            error="ReadTimeout: Read timed out after 60s",
            domain="python",
        ),
        Episode(
            id="ep-005",
            task="Fix the permission error in deploy.sh",
            outcome="failure",
            error="Permission denied: /etc/config",
            domain="python",
        ),
        Episode(
            id="ep-006",
            task="Fix the permission error in setup.py",
            outcome="failure",
            error="Permission denied: /usr/local/bin",
            domain="python",
        ),
        Episode(
            id="ep-007",
            task="Fix the syntax error in parser.py",
            outcome="failure",
            error="SyntaxError: unexpected indent on line 42",
            domain="python",
        ),
        Episode(
            id="ep-008",
            task="Fix the syntax error in utils.py",
            outcome="failure",
            error="SyntaxError: invalid syntax on line 15",
            domain="python",
        ),
        Episode(
            id="ep-009",
            task="Fix the file not found in loader.py",
            outcome="failure",
            error="FileNotFoundError: data.csv not found",
            domain="python",
        ),
        Episode(
            id="ep-010",
            task="Fix the file not found in importer.py",
            outcome="failure",
            error="FileNotFoundError: config.yaml not found",
            domain="python",
        ),
    ]

    for ep in failure_episodes:
        runner.store.record_episode(ep)
        print(f"  Recorded: {ep.task[:50]}... [{ep.outcome}]")

    # Simulate some successes
    success_episodes = [
        Episode(
            id="ep-011",
            task="Read config.yaml",
            outcome="success",
            domain="python",
        ),
        Episode(
            id="ep-012",
            task="List files in src/",
            outcome="success",
            domain="python",
        ),
    ]

    for ep in success_episodes:
        runner.store.record_episode(ep)
        print(f"  Recorded: {ep.task[:50]}... [{ep.outcome}]")

    # 4. Run evolution
    print("\n[4] Running evolution cycle...")
    step_result = runner.evolve()
    print(f"  Mutated: {step_result.mutated}")
    print(f"  Summary: {step_result.summary}")
    print(f"  Fragments added: {step_result.fragments_added}")
    print(f"  Fragments removed: {step_result.fragments_removed}")
    print(f"  Knowledge added: {step_result.knowledge_added}")

    # 5. Inspect evolved state
    print("\n[5] Evolved state:")
    print(f"  Generation: {runner.profile.generation}")
    print(f"  Fragments: {runner.prompt.fragment_count}")
    print(f"  Knowledge rules: {len(runner.store.get_knowledge())}")

    print("\n  Prompt fragments:")
    for frag in runner.prompt.fragments:
        print(f"    [{frag.id}] score={frag.score:.2f} src={frag.source}")
        print(f"      {frag.content[:80]}...")

    print("\n  Knowledge rules:")
    for k in runner.store.get_knowledge():
        print(f"    [{k.id}] conf={k.confidence:.2f} domain={k.domain}")
        print(f"      {k.rule[:80]}...")

    # 6. Run another evolution cycle
    print("\n[6] Running second evolution cycle...")
    step_result2 = runner.evolve()
    print(f"  Mutated: {step_result2.mutated}")
    print(f"  Summary: {step_result2.summary}")

    # 7. Show stats
    print("\n[7] Final statistics:")
    stats = runner.store.stats
    print(f"  Total episodes: {stats['total_episodes']}")
    print(f"  Success rate: {stats['success_rate']:.2%}")
    print(f"  Total knowledge: {stats['total_knowledge']}")

    harness_stats = runner.stats
    print(f"  Generation: {harness_stats['generation']}")
    print(f"  Fragment count: {harness_stats['fragment_count']}")

    # 8. Compose the evolved prompt
    print("\n[8] Evolved system prompt:")
    evolved_prompt = runner.prompt.compose(task="Fix a bug in my code")
    print("-" * 60)
    print(evolved_prompt[:500])
    if len(evolved_prompt) > 500:
        print("...")
    print("-" * 60)

    # 9. Save state
    runner.save()
    print("\n[9] State saved to .harness-demo/")

    # Cleanup
    import shutil
    shutil.rmtree(".harness-demo", ignore_errors=True)

    print("\n" + "=" * 60)
    print("  Demo complete! v5 harness learned from failures.")
    print("=" * 60)


if __name__ == "__main__":
    main()
