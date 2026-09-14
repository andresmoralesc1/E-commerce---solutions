"""Anthropic provider (Claude API)."""
import httpx

from app.core.config import settings as app_settings
from app.core.llm_providers.base import (
    LLMClient,
    LLMError,
    LLMMessage,
    LLMResponse,
)


class AnthropicClient(LLMClient):
    """Anthropic Messages API."""

    DEFAULT_MODEL = "claude-sonnet-4-5"

    def __init__(self) -> None:
        if not app_settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is empty")
        self._api_key = app_settings.anthropic_api_key
        self._base_url = "https://api.anthropic.com"
        self._model = self.DEFAULT_MODEL
        self._timeout = app_settings.llm_timeout_seconds

    def _separate_system(self, messages: list[LLMMessage]):
        system = None
        chat = []
        for m in messages:
            if m.role == "system":
                system = (system + "\n\n" if system else "") + m.content
            else:
                chat.append({"role": m.role, "content": m.content})
        return system, chat

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse:
        system, chat = self._separate_system(messages)
        payload: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat,
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["response_format"] = {"type": "json"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(
                    f"{self._base_url}/v1/messages",
                    json=payload,
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                )
                if r.status_code != 200:
                    raise LLMError(
                        f"Anthropic API {r.status_code}: {r.text[:300]}"
                    )
                data = r.json()
        except httpx.HTTPError as e:
            raise LLMError(f"Anthropic HTTP error: {e}") from e

        try:
            content = "".join(
                block.get("text", "")
                for block in data["content"]
                if block.get("type") == "text"
            )
            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                model=data.get("model", self._model),
                usage={
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                },
                raw=data,
            )
        except (KeyError, IndexError) as e:
            raise LLMError(f"Anthropic malformed response: {e}\n{data}") from e

    async def health(self) -> bool:
        try:
            await self.complete(
                [LLMMessage("user", "ping")],
                temperature=0,
                max_tokens=4,
            )
            return True
        except LLMError:
            return False