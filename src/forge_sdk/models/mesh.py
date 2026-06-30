"""MeshModelPort — ModelPort that resolves via lgwks_model_mesh.

This bridges forge's ModelPort protocol to lgwks's model mesh.
The mesh is consulted on every call — model routing is dynamic.
"""

from __future__ import annotations

from forge_sdk.models.port import ModelPort
from forge_sdk.models.registry import registry
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
        return self._delegate().context_window

    @property
    def max_output(self) -> int:
        return self._delegate().max_output

    @property
    def supports_reasoning(self) -> bool:
        return self._delegate().supports_reasoning

    # -- ModelPort protocol methods ------------------------------------------

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> ModelResponse:
        return self._delegate().complete(
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
        return self._delegate().complete_stream(
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

    def _delegate(self) -> ModelPort:
        """Create a ModelPort for the currently-resolved provider+model."""
        provider_name, model_id = self._resolve_model()
        try:
            return registry.create(provider_name, model=model_id)
        except KeyError:
            if self._fallback is not None:
                return self._fallback
            raise
