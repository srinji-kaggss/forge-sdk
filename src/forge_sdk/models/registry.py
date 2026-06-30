"""Typed provider registry — strategy pattern over conditionals."""

from __future__ import annotations

from forge_sdk.models.port import ModelPort


class ProviderRegistry:
    """Registry of model providers. Each provider is a strategy with a name key."""

    def __init__(self) -> None:
        self._providers: dict[str, type[ModelPort]] = {}

    def register(self, name: str, provider_cls: type[ModelPort]) -> None:
        self._providers[name] = provider_cls

    def get(self, name: str) -> type[ModelPort] | None:
        return self._providers.get(name)

    def available(self) -> list[str]:
        return list(self._providers.keys())

    def create(self, name: str, **kwargs) -> ModelPort:
        cls = self._providers.get(name)
        if cls is None:
            raise KeyError(f"Unknown provider: {name}. Available: {self.available()}")
        return cls(**kwargs)


# Global registry — providers register themselves on import
registry = ProviderRegistry()
