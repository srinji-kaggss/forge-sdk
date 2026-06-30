"""Model package — providers register themselves on import."""

from forge_sdk.models.port import ModelPort
from forge_sdk.models.registry import ProviderRegistry, registry
from forge_sdk.models.types import ModelChunk, ModelResponse, Usage

__all__ = ["ModelPort", "ModelResponse", "ModelChunk", "Usage", "ProviderRegistry", "registry"]


def _auto_register() -> None:
    """Try to register all known providers. Fail silently if deps missing."""
    from forge_sdk.models.deepseek import DeepSeekProvider
    from forge_sdk.models.openrouter import OpenRouterProvider

    registry.register("deepseek", DeepSeekProvider)
    registry.register("openrouter", OpenRouterProvider)

    try:
        from forge_sdk.models.ollama import OllamaProvider

        registry.register("ollama", OllamaProvider)
    except ImportError:
        pass


_auto_register()
