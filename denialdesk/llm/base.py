from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMError(Exception):
    pass


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...

    @abstractmethod
    async def complete_json(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        """Complete and parse response as JSON."""
        ...
