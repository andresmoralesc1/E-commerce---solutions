"""LLM provider abstraction — interface agnóstica."""
from .base import LLMClient, LLMMessage, LLMResponse, LLMError
from .factory import get_llm_client

__all__ = ["LLMClient", "LLMMessage", "LLMResponse", "LLMError", "get_llm_client"]