"""Configuration — loads from env and config files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ForgeConfig:
    """Unified configuration for the SDK."""

    # Model settings
    provider: str = "deepseek"
    model: str = "deepseek-v4-pro"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.0
    max_tokens: int | None = None

    # Agent settings
    max_steps: int = 50
    cwd: str = "."

    # Eval settings
    eval_limit: int | None = None
    eval_benchmark: str = "humaneval"

    # Tracing
    trace_dir: str = ".forge/traces"

    # Audit
    audit_db: str = ".forge/audit.db"

    # Paths
    config_file: str = ""

    @classmethod
    def load(cls, config_file: str | Path | None = None) -> ForgeConfig:
        """Load config from file and environment. Env overrides file."""
        cfg = cls()

        # Load from file if exists
        path = Path(config_file) if config_file else Path.home() / ".forge" / "config.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)

        # Environment overrides
        env_map = {
            "FORGE_PROVIDER": "provider",
            "FORGE_MODEL": "model",
            # NOTE: provider API keys are resolved provider-aware in
            # resolve_api_key() (DEEPSEEK_API_KEY / OPENROUTER_API_KEY by
            # provider). They are intentionally NOT mapped here — mapping both
            # to `api_key` let whichever was processed last silently clobber the
            # other (a stale OPENROUTER_API_KEY -> 401 against deepseek).
            # FORGE_API_KEY is the single explicit override.
            "FORGE_API_KEY": "api_key",
            "FORGE_BASE_URL": "base_url",
            "FORGE_TEMPERATURE": ("temperature", float),
            "FORGE_MAX_TOKENS": ("max_tokens", int),
            "FORGE_MAX_STEPS": ("max_steps", int),
            "FORGE_CWD": "cwd",
            "FORGE_TRACE_DIR": "trace_dir",
            "FORGE_AUDIT_DB": "audit_db",
        }
        for env_key, target in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                if isinstance(target, tuple):
                    attr, converter = target
                    setattr(cfg, attr, converter(val))
                else:
                    setattr(cfg, target, val)

        return cfg

    def resolve_api_key(self) -> str:
        """Resolve API key from config or environment."""
        if self.api_key:
            return self.api_key
        env_keys = {
            "deepseek": "DEEPSEEK_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "ollama": "OLLAMA_API_KEY",
        }
        env_var = env_keys.get(self.provider, "")
        return os.environ.get(env_var, "") if env_var else ""

    def create_model(self) -> Any:
        """Create a model instance from config."""
        from forge_sdk.models.registry import registry

        api_key = self.resolve_api_key()
        kwargs: dict[str, Any] = {"api_key": api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.model:
            kwargs["model"] = self.model
        return registry.create(self.provider, **kwargs)

    def save(self, path: str | Path | None = None) -> None:
        """Save config to file."""
        target = Path(path) if path else Path.home() / ".forge" / "config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "max_steps": self.max_steps,
            "cwd": self.cwd,
            "trace_dir": self.trace_dir,
            "audit_db": self.audit_db,
            "eval_benchmark": self.eval_benchmark,
            "eval_limit": self.eval_limit,
        }
        with open(target, "w") as f:
            json.dump(data, f, indent=2)
