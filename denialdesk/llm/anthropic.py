import json

import anthropic

from .base import LLMError, LLMMessage, LLMProvider, LLMResponse

_JSON_SUFFIX = "\n\nRespond with valid JSON only. No prose, no markdown fences — just the raw JSON object."


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            kwargs["system"] = system
        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.APIError as exc:
            raise LLMError(str(exc)) from exc

        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )

    async def complete_json(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        system_with_json = (system or "") + _JSON_SUFFIX
        result = await self.complete(messages, system=system_with_json, max_tokens=max_tokens)
        try:
            return json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model returned non-JSON: {result.content[:200]}") from exc
