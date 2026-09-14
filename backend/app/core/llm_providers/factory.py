"""LLM client factory."""
from functools import lru_cache

from app.core.config import settings
from app.core.llm_providers.base import LLMClient, LLMError


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Returns the configured LLM client (cached singleton)."""
    provider = settings.llm_provider
    if provider == "mock":
        from app.core.llm_providers.mock import MockLLM
        return MockLLM()
    if provider == "minimax":
        from app.core.llm_providers.minimax import MiniMaxClient
        return MiniMaxClient()
    if provider == "anthropic":
        from app.core.llm_providers.anthropic import AnthropicClient
        return AnthropicClient()
    if provider == "openai":
        from app.core.llm_providers.openai import OpenAIClient
        return OpenAIClient()
    raise LLMError(f"Unknown LLM provider: {provider}")