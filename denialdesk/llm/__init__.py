from .base import LLMError, LLMMessage, LLMProvider, LLMResponse


def get_llm_provider() -> LLMProvider:
    from denialdesk.config import settings

    if settings.llm_provider == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.llm_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")


__all__ = ["LLMError", "LLMMessage", "LLMProvider", "LLMResponse", "get_llm_provider"]
