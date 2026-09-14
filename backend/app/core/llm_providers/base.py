"""LLM interface base."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMError(Exception):
    """Raised on LLM provider errors."""


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


class LLMClient(ABC):
    """Abstract LLM client. Implementations: MiniMax, Anthropic, OpenAI."""

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse: ...

    @abstractmethod
    async def health(self) -> bool: ...