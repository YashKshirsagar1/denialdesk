import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from denialdesk.llm.base import LLMError, LLMMessage, LLMProvider, LLMResponse
from denialdesk.llm.anthropic import AnthropicProvider


def _make_anthropic_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 20
    resp = MagicMock()
    resp.content = [content_block]
    resp.usage = usage
    resp.model = "claude-sonnet-4-6"
    return resp


@pytest.mark.asyncio
async def test_complete_returns_llm_response():
    mock_response = _make_anthropic_response("Hello world")

    with patch("denialdesk.llm.anthropic.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.complete([LLMMessage(role="user", content="Hi")])

    assert isinstance(result, LLMResponse)
    assert result.content == "Hello world"
    assert result.input_tokens == 10
    assert result.output_tokens == 20


@pytest.mark.asyncio
async def test_complete_json_parses_json():
    payload = {"root_cause": "coding_error", "score": 0.75}
    mock_response = _make_anthropic_response(json.dumps(payload))

    with patch("denialdesk.llm.anthropic.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-6")
        result = await provider.complete_json([LLMMessage(role="user", content="diagnose")])

    assert result == payload


@pytest.mark.asyncio
async def test_complete_json_raises_llm_error_on_bad_json():
    mock_response = _make_anthropic_response("This is not JSON at all.")

    with patch("denialdesk.llm.anthropic.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-6")
        with pytest.raises(LLMError, match="non-JSON"):
            await provider.complete_json([LLMMessage(role="user", content="diagnose")])


@pytest.mark.asyncio
async def test_complete_wraps_api_error():
    import anthropic as anthropic_lib

    with patch("denialdesk.llm.anthropic.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(
            side_effect=anthropic_lib.APIStatusError(
                "rate limited", response=MagicMock(status_code=429), body={}
            )
        )

        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-6")
        with pytest.raises(LLMError):
            await provider.complete([LLMMessage(role="user", content="hi")])


def test_llm_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]
