"""OpenAI provider."""
import httpx

from app.core.config import settings as app_settings
from app.core.llm_providers.base import (
    LLMClient,
    LLMError,
    LLMMessage,
    LLMResponse,
)


class OpenAIClient(LLMClient):
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self) -> None:
        if not app_settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is empty")
        self._api_key = app_settings.openai_api_key
        self._base_url = "https://api.openai.com"
        self._model = self.DEFAULT_MODEL
        self._timeout = app_settings.llm_timeout_seconds

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse:
        payload: dict = {
            "model": self._model,
            "messages": [m.__dict__ for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code != 200:
                    raise LLMError(
                        f"OpenAI API {r.status_code}: {r.text[:300]}"
                    )
                data = r.json()
        except httpx.HTTPError as e:
            raise LLMError(f"OpenAI HTTP error: {e}") from e

        try:
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return LLMResponse(
                content=choice["message"]["content"],
                model=data.get("model", self._model),
                usage={
                    "input": usage.get("prompt_tokens", 0),
                    "output": usage.get("completion_tokens", 0),
                },
                raw=data,
            )
        except (KeyError, IndexError) as e:
            raise LLMError(f"OpenAI malformed response: {e}\n{data}") from e

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