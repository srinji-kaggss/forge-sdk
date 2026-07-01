"""MeshModelPort — ModelPort that resolves via lgwks_model_mesh.

This bridges forge's ModelPort protocol to lgwks's model mesh.
The mesh is consulted on every call — model routing is dynamic.
"""

from __future__ import annotations

from forge_sdk.models.port import ModelPort
from forge_sdk.models.types import ModelChunk, ModelResponse


class MeshModelPort:
    """ModelPort that resolves via lgwks_model_mesh.model_name_for_role().

    On every complete/complete_stream call, the mesh is queried for the
    current model for the configured role and trust class. The resolved
    provider+model is then delegated to the corresponding ModelPort from
    the ProviderRegistry.

    Falls back to ``fallback_provider`` (or the default model string) when
    the mesh is unavailable or returns an unresolvable name.
    """

    def __init__(
        self,
        role: str = "agent",
        trust_class: str = "deterministic",
        default: str = "ollama:gemma3:4b",
        fallback_provider: ModelPort | None = None,
    ) -> None:
        self._role = role
        self._trust_class = trust_class
        self._default = default
        self._fallback = fallback_provider
        self._providers: dict[str, ModelPort] = {}  # Cache resolved providers

    # -- ModelPort protocol properties (delegated to resolved provider) -------

    @property
    def name(self) -> str:
        provider_name, model_id = self._resolve_model()
        return model_id

    @property
    def provider(self) -> str:
        provider_name, model_id = self._resolve_model()
        return provider_name

    @property
    def context_window(self) -> int:
        provider_name = self._resolve_model()[0]
        return self._get_provider(provider_name).context_window

    @property
    def max_output(self) -> int:
        provider_name = self._resolve_model()[0]
        return self._get_provider(provider_name).max_output

    @property
    def supports_reasoning(self) -> bool:
        provider_name = self._resolve_model()[0]
        return self._get_provider(provider_name).supports_reasoning

    # -- ModelPort protocol methods ------------------------------------------

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> ModelResponse:
        provider_name, model_id = self._resolve_model()
        provider = self._get_provider(provider_name)
        return provider.complete(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop
        )

    def complete_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> list[ModelChunk]:
        provider_name, model_id = self._resolve_model()
        provider = self._get_provider(provider_name)
        return provider.complete_stream(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop
        )

    # -- Internal resolution --------------------------------------------------

    def _resolve_model(self) -> tuple[str, str]:
        """Return (provider_name, model_id) from the mesh, or from default."""
        try:
            import lgwks_model_mesh

            raw = lgwks_model_mesh.model_name_for_role(
                self._role, trust_class=self._trust_class, default=self._default
            )
            if raw:
                provider, model = raw.split(":", 1)
                return provider, model
        except (ImportError, Exception):
            pass
        # Fallback: parse the default string
        provider, model = self._default.split(":", 1)
        return provider, model

    def _get_provider(self, provider_name: str) -> ModelPort:
        """Get or create cached provider instance."""
        if provider_name not in self._providers:
            from forge_sdk.models import registry as _registry

            model_id = self._resolve_model()[1]
            self._providers[provider_name] = _registry.create(provider_name, model=model_id)
        return self._providers[provider_name]
