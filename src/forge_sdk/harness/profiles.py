"""Agent profiles — typed configuration for agent identity, domain, and constraints."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentProfile:
    """Typed configuration for an agent's identity and behavior.

    Profiles are the first-class citizen of the harness. They define:
    - Who the agent is (name, domain, role)
    - What it can do (tools, capabilities)
    - How it should behave (constraints, style)
    - What model it uses (provider, model name)

    Profiles are serializable to/from JSON and can be evolved
    by the mutation engine.
    """

    # Identity
    name: str = "agent"
    domain: str = "general"
    role: str = "assistant"
    version: str = "1.0.0"

    # Model configuration
    model_provider: str = "ollama"
    model_name: str = "gemma3:4b"
    model_params: dict[str, Any] = field(default_factory=dict)

    # System prompt (the base — AdaptivePrompt layers on top)
    system_prompt: str = "You are a helpful AI assistant."

    # Tool configuration
    enabled_tools: list[str] = field(default_factory=lambda: ["filesystem", "search", "shell"])
    disabled_tools: list[str] = field(default_factory=list)
    tool_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Behavioral constraints
    max_steps: int = 20
    max_tokens: int = 4096
    temperature: float = 0.7
    allowed_domains: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)

    # Learning configuration
    episodic_memory: bool = True
    semantic_memory: bool = True
    max_episodes: int = 1000
    max_knowledge: int = 500

    # Evolution metadata
    generation: int = 0
    parent_version: str | None = None
    mutation_history: list[dict[str, Any]] = field(default_factory=list)
    performance_score: float = 0.0

    # Extensible metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentProfile:
        """Deserialize from dictionary, ignoring unknown fields."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> AgentProfile:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: str | Path) -> AgentProfile:
        """Load profile from a JSON file."""
        return cls.from_json(Path(path).read_text())

    def save(self, path: str | Path) -> None:
        """Save profile to a JSON file."""
        Path(path).write_text(self.to_json())

    def evolve(self, mutations: dict[str, Any]) -> AgentProfile:
        """Create a new profile with mutations applied.

        Returns a new AgentProfile with generation incremented
        and the mutation recorded in history.
        """
        current = self.to_dict()
        current.update(mutations)
        current["generation"] = self.generation + 1
        current["parent_version"] = self.version
        current["mutation_history"] = self.mutation_history + [{
            "generation": self.generation,
            "mutations": list(mutations.keys()),
        }]
        return AgentProfile.from_dict(current)

    def clone(self, **overrides: Any) -> AgentProfile:
        """Create a copy with optional field overrides."""
        data = self.to_dict()
        data.update(overrides)
        return AgentProfile.from_dict(data)


# Pre-built profiles for common use cases
CODER_PROFILE = AgentProfile(
    name="coder",
    domain="python",
    role="developer",
    system_prompt=(
        "You are an expert Python developer. You write clean, type-hinted, "
        "tested code. You follow SOLID principles and existing code conventions. "
        "You never assume a library is available — you check first."
    ),
    enabled_tools=["filesystem", "search", "shell"],
    max_steps=15,
)

REVIEWER_PROFILE = AgentProfile(
    name="reviewer",
    domain="code-review",
    role="reviewer",
    system_prompt=(
        "You are a senior code reviewer. You focus on correctness, security, "
        "performance, and maintainability. You cite specific line numbers and "
        "provide actionable feedback with code suggestions."
    ),
    enabled_tools=["filesystem", "search"],
    max_steps=10,
)

RESEARCHER_PROFILE = AgentProfile(
    name="researcher",
    domain="research",
    role="researcher",
    system_prompt=(
        "You are a research analyst. You gather information from multiple sources, "
        "cross-reference claims, and produce structured reports with citations. "
        "You distinguish facts from opinions and flag uncertainty."
    ),
    enabled_tools=["filesystem", "search"],
    max_steps=20,
)
